"""Local Power Apps Automations: real timer, signed ingress and HTTP connector checks.

Run from backend with venv/Scripts/python.exe ../qa/power_automations_events_e2e.py.
Public HTTP echo requests contain synthetic fixture data only. Scheduled examples
are one-shot; this runner never installs a recurring test schedule.
"""
import argparse
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
import requests
from power_automations_logic_e2e import API, ROOT, session, request, node, edge, graph

RESULTS = []


def save(name, value, background=False):
    name = 'E2E · ' + name
    rows = request('GET', '/power-apps/automations', params={'search': name, 'limit': 100})['items']
    row = next((r for r in rows if r['name'] == name), None)
    if row:
        row = request('GET', f'/power-apps/automations/{row["id"]}')
        state = request('GET', f'/power-apps/automations/{row["id"]}/runtime')
        if state['status'] == 'active':
            return row
        row = request('PUT', f'/power-apps/automations/{row["id"]}', json={'name': name, 'description': row['description'], 'definition': value, 'expected_version': row['version']})
    else:
        row = request('POST', '/power-apps/automations', json={'name': name, 'description': 'Automation-only timer, webhook and synthetic HTTP test.', 'definition': value})
    policy = {'identity': 'owner', 'delegated_owner': True} if background else {'identity': 'initiator'}
    for action in ['validate', 'publish', 'activate']:
        request('POST', f'/power-apps/automations/{row["id"]}/runtime/{action}', json={'expected_version': row['version'], 'policy': policy})
    print(f'Saved {name}: workflow #{row["id"]}', flush=True)
    return row


def execute(row, data=None):
    return request('POST', f'/power-apps/automations/{row["id"]}/execute', json={'input': data or {}, 'idempotency_key': 'events-e2e-' + uuid.uuid4().hex})['id']


def history(id):
    return request('GET', f'/power-apps/executions/{id}')


def wait(id, expected='completed', seconds=65):
    deadline, seen_waiting = time.monotonic() + seconds, False
    while time.monotonic() < deadline:
        report = history(id)
        status = report['execution']['status']
        seen_waiting |= status == 'waiting'
        if status in {'completed', 'failed', 'cancelled'}:
            assert status == expected, {'status': status, 'error': report['run'].get('error'), 'steps': [(s['node_id'], s['error']) for s in report['steps'] if s.get('error')]}
            return report, seen_waiting
        time.sleep(.6)
    raise AssertionError(f'Execution #{id} did not finish')


def log_messages(report):
    return [e['details'].get('message') for e in report['events'] if e['kind'] == 'structured_log']


def timer(kind='delay', **config):
    return graph([node('before', 'log_event', message='Before timer'), node('wait', kind, **config), node('after', 'log_event', message='After timer')],
                 [edge('start', 'before'), edge('before', 'wait'), edge('wait', 'after')])


def delay():
    row = save('Delay and Resume', timer(seconds=3))
    id = execute(row)
    report, seen = wait(id)
    assert seen, 'Waiting state was not observed'
    assert log_messages(report) == ['Before timer', 'After timer'], log_messages(report)
    assert any(e['kind'] == 'resumed' for e in report['events']), 'Resume event missing'
    return {'workflow_id': row['id'], 'run_id': id, 'logs': len(log_messages(report))}


def cancel_delay():
    row = save('Cancel a Delay', timer(seconds=30))
    id, deadline = execute(row), time.monotonic() + 30
    while time.monotonic() < deadline and history(id)['execution']['status'] != 'waiting':
        time.sleep(.5)
    assert history(id)['execution']['status'] == 'waiting'
    request('POST', f'/power-apps/executions/{id}/cancel')
    report, _ = wait(id, 'cancelled')
    assert 'After timer' not in log_messages(report)
    return {'workflow_id': row['id'], 'run_id': id, 'cancelled': True}


def wait_until():
    value = timer('wait_until', until='2099-01-01T00:00:00+00:00')
    next(item for item in value['nodes'] if item['id'] == 'wait')['mappings'] = {'until': {'source': '{{trigger.input.at}}', 'target_type': 'datetime'}}
    row = save('Wait Until', value)
    at = datetime.now(timezone.utc) + timedelta(seconds=10)
    id = execute(row, {'at': at.isoformat()})
    report, seen = wait(id)
    assert seen and datetime.now(timezone.utc) >= at
    assert log_messages(report) == ['Before timer', 'After timer']
    return {'workflow_id': row['id'], 'run_id': id, 'logs': len(log_messages(report))}


def schedule():
    value = graph([node('done', 'log_event', message='One-shot schedule fired')], [edge('start', 'done')])
    value['nodes'][0] = {**node('start', 'scheduled_trigger', schedule='* * * * *', timezone='Asia/Kolkata'), 'position': value['nodes'][0]['position']}
    row = save('One Shot Schedule', value, True)
    before = {r['id'] for r in request('GET', '/power-apps/executions', params={'workflow': row['id']})['items']}
    at = datetime.now(timezone.utc) + timedelta(seconds=12)
    request('PUT', f'/power-apps/automations/{row["id"]}/triggers/scheduled', json={'enabled': True, 'config': {'mode': 'once', 'timezone': 'Asia/Kolkata', 'at': at.isoformat()}})
    deadline, created = time.monotonic() + 45, []
    while time.monotonic() < deadline:
        created = [r for r in request('GET', '/power-apps/executions', params={'workflow': row['id']})['items'] if r['id'] not in before]
        if created:
            break
        time.sleep(1)
    assert len(created) == 1, 'Expected one branch-visible scheduled execution'
    report, _ = wait(created[0]['id'])
    assert log_messages(report) == ['One-shot schedule fired']
    trigger = next(t for t in request('GET', f'/power-apps/automations/{row["id"]}/triggers')['items'] if t['kind'] == 'scheduled')
    assert trigger['enabled'] is False, 'One-shot schedule must disable itself'
    return {'workflow_id': row['id'], 'run_id': created[0]['id'], 'one_shot_disabled': True}


def webhook():
    value = graph([node('done', 'log_event', message='Webhook: {{trigger.input.message}}')], [edge('start', 'done')])
    value['nodes'][0] = {**node('start', 'webhook_trigger', event_name='e2e.synthetic'), 'position': value['nodes'][0]['position']}
    row = save('Signed Webhook', value, True)
    hook = request('PUT', f'/power-apps/automations/{row["id"]}/triggers/webhook', json={'enabled': True, 'config': {'schema': {'type': 'object', 'properties': {'message': {'type': 'string', 'maxLength': 100}}, 'required': ['message']}}})
    if not hook.get('secret'):
        hook['secret'] = request('POST', f'/power-apps/automations/{row["id"]}/triggers/webhook/rotate')['secret']
    url = API.removesuffix('/api/v1') + hook['endpoint']
    body = b'{"message":"synthetic fixture"}'
    def headers(secret, raw=body):
        timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
        digest = hmac.new(secret.encode(), timestamp.encode() + b'.' + nonce.encode() + b'.' + raw, hashlib.sha256).hexdigest()
        return {'Content-Type': 'application/json', 'X-Power-Timestamp': timestamp, 'X-Power-Nonce': nonce, 'X-Power-Signature': digest}
    signed = headers(hook['secret'])
    accepted = requests.post(url, data=body, headers=signed, timeout=20)
    assert accepted.status_code == 202, accepted.text
    id = accepted.json()['id']
    assert requests.post(url, data=body, headers=signed, timeout=20).status_code == 409
    assert requests.post(url, data=body, headers=headers('invalid-fixture'), timeout=20).status_code == 401
    wrong = b'{"message":123}'
    assert requests.post(url, data=wrong, headers=headers(hook['secret'], wrong), timeout=20).status_code == 422
    report, _ = wait(id)
    assert log_messages(report) == ['Webhook: synthetic fixture']
    request('POST', f'/power-apps/automations/{row["id"]}/triggers/webhook/rotate')
    assert requests.post(url, data=body, headers=headers(hook['secret']), timeout=20).status_code == 401
    return {'workflow_id': row['id'], 'run_id': id, 'replay_rejected': True, 'bad_signature_rejected': True, 'schema_checked': True, 'rotation_checked': True}


def http_case(method='GET', failure=False):
    name = 'API Failure Logging' if failure else f'API {method}'
    rows = request('GET', '/power-apps/integrations/connections')['items']
    connection = next((r for r in rows if r['name'] == 'E2E synthetic HTTP'), None)
    if not connection:
        connection = request('POST', '/power-apps/integrations/connections', json={'connector_id': 'http', 'name': 'E2E synthetic HTTP', 'auth_type': 'none', 'config': {'hosts': ['api.github.com', 'httpbin.org']}, 'writes_enabled': True})
    input = {'url': 'https://api.github.com/rate_limit', 'method': method, 'headers': {'Accept': 'application/json', 'User-Agent': 'BusinessSuite-Automation-E2E'}}
    if method == 'POST':
        input.update(url='https://httpbin.org/post', body={'scenario': 'power-apps-automation-e2e', 'value': 42})
    if failure:
        input['url'] = 'https://httpbin.org/status/404'
    call = node('api', 'connector_http', action='request', input=input, confirm_write=method == 'POST')
    call['credential_reference'] = str(connection['id'])
    call['advanced'] = {'retry_attempts': 1, 'error_strategy': 'stop', 'timeout_seconds': 15}
    value = graph([call, node('done', 'log_event', message='API request completed')], [edge('start', 'api'), edge('api', 'done')])
    row = save(name, value)
    id = execute(row)
    report, _ = wait(id, 'failed' if failure else 'completed')
    step = next(s for s in report['steps'] if s['original_node_id'] == 'api')
    if failure:
        assert step['error'] and any(e['kind'] in {'step_failed', 'failed', 'run_failed'} for e in report['events']), report['events']
        assert step.get('error_type') == 'remote' and 'HTTP 404' in step['error'], 'Failure must come from the remote 404, not a local network or egress rejection'
        assert 'API request completed' not in log_messages(report)
    else:
        assert step['output']['status_code'] == 200, step['output']
        assert log_messages(report) == ['API request completed']
        if method == 'POST':
            assert step['output']['body']['json']['value'] == 42
    return {'workflow_id': row['id'], 'run_id': id, 'expected_failure': failure, 'error_logged': bool(step.get('error'))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', action='append', default=[])
    parser.add_argument('--output', default='automation-events-e2e.json')
    args = parser.parse_args()
    cases = {'delay': delay, 'cancel_delay': cancel_delay, 'wait_until': wait_until, 'schedule': schedule, 'webhook': webhook, 'api_get': http_case, 'api_post': lambda: http_case('POST'), 'api_failure': lambda: http_case(failure=True)}
    for name, case in cases.items():
        if args.case and name not in args.case:
            continue
        try:
            result = {'case': name, 'passed': True, **case()}
        except Exception as exc:
            result = {'case': name, 'passed': False, 'error': str(exc)[:1800]}
        RESULTS.append(result)
        print(json.dumps(result), flush=True)
    (ROOT / '.local' / args.output).write_text(json.dumps(RESULTS, indent=2), encoding='utf-8')
    return 0 if all(r['passed'] for r in RESULTS) else 1


if __name__ == '__main__':
    raise SystemExit(main())
