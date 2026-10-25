"""Live, metered provider QA against a labelled disposable PMS project.

Uses only keys already encrypted in PMS settings. No mock transport or fake
provider response. Explicitly approve every generated action after checking its
targets and contents. Evidence contains metadata only, never keys or prompts.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=int, required=True)
    parser.add_argument('--provider', choices=['gemini', 'openai', 'claude'], required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = root / '.local/operator-live-qa'
    auth = json.loads((out / 'auth.json').read_text())
    client = httpx.Client(base_url='http://127.0.0.1:1534/api/v1',
                          headers={'Authorization': 'Bearer ' + auth['token']}, timeout=65)
    checks = []
    evidence = {'provider': args.provider, 'project_id': args.project,
                'started_at': datetime.now(timezone.utc).isoformat(), 'checks': checks}

    def call(method, path, body=None):
        response = client.request(method, path, json=body)
        detail = response.json().get('detail') if response.status_code != 200 else None
        safe_code = detail if isinstance(detail, str) and detail.startswith('PROVIDER_') else ''
        assert response.status_code == 200, f'{method} {path}: HTTP {response.status_code} {safe_code}'
        return response.json()

    def record(name, detail):
        checks.append({'name': name, 'status': 'passed', 'evidence': detail})
        print('PASS', name, flush=True)

    def wait_run(ident, expected):
        for _ in range(150):
            run = call('GET', f'/ai-operator/runs/{ident}')
            if run['status'] == expected:
                return run
            assert run['status'] not in ['failed', 'cancelled', 'paused', 'needs_clarification'], f'Run {ident}: {run["status"]} {run.get("error_code")}'
            time.sleep(1)
        raise AssertionError(f'Run {ident} timed out waiting for {expected}')

    try:
        projects = call('GET', '/project-management/projects')
        project = next(p for p in projects if p['id'] == args.project)
        assert project['name'].startswith('AI Operator live QA '), 'Use a labelled QA project only'
        assert not project.get('workspace_id'), 'This verifier uses company/personal QA scope'
        configs = call('GET', '/ai-operator/providers')['items']
        config = next(p for p in configs if p['provider'] == args.provider)
        assert config['has_key'] and config['enabled'] and config['data_sharing_allowed']
        evidence['model'] = config['model']
        before = call('GET', '/ai-operator/analytics')
        baseline = max([r['id'] for r in before['logs']], default=0)
        record('Encrypted settings exposed without key material', {'model': config['model'], 'has_key': True})
        call('POST', f'/ai-operator/providers/{args.provider}/test', {})
        record('Real provider connectivity through PMS gateway', {'provider': args.provider})
        stamp = uuid4().hex[:8]
        task = call('POST', f'/project-management/projects/{args.project}/tasks',
                    {'title': 'Live provider QA ' + stamp, 'task_key': 'PROV-' + stamp.upper()})
        ident = task['id']
        checklist = 'Provider verification ' + stamp
        command = {'project_id': args.project, 'task_ids': [ident], 'provider': args.provider,
                   'command': f'Set the selected task priority to High and add exactly one checklist item titled "{checklist}". Do not change anything else.',
                   'request_key': str(uuid4()), 'input_mode': 'text', 'background': True}
        created = call('POST', '/ai-operator/commands', command)
        run = wait_run(created['id'], 'awaiting_approval')
        steps = run['plan']['steps']
        assert len(steps) == 2 and all(s['task_id'] == ident for s in steps)
        updates = [s for s in steps if s['tool'] == 'update_task']
        additions = [s for s in steps if s['tool'] == 'add_checklist']
        assert len(updates) == len(additions) == 1
        assert updates[0]['changes'] == {'priority': 'High'} and additions[0]['title'] == checklist
        current = call('GET', f'/project-management/projects/{args.project}/tasks')
        assert next(t for t in current if t['id'] == ident)['priority'] != 'High'
        replay = call('POST', '/ai-operator/commands', command)
        assert replay['id'] == run['id']
        call('POST', f'/ai-operator/runs/{run["id"]}/approve', {'plan_hash': run['plan_hash']})
        finished = wait_run(run['id'], 'succeeded')
        assert len(finished['result']['receipts']) == 2
        current = call('GET', f'/project-management/projects/{args.project}/tasks')
        assert next(t for t in current if t['id'] == ident)['priority'] == 'High'
        record('Real model multi-step plan, idempotent replay, approval and worker execution',
               {'run_id': run['id'], 'task_id': ident, 'receipts': finished['result']['receipts']})

        session = call('POST', '/ai-operator/brain/sessions', {'project_id': args.project})
        for attempt in range(2):
            try:
                reply = call('POST', f'/ai-operator/brain/sessions/{session["id"]}/cloud',
                             {'text': 'Prepare a new release. Ask me for its deadline. Do not draft any task changes yet.',
                              'provider': args.provider, 'fallback_reason': 'unsupported', 'task_ids': [ident]})
                break
            except AssertionError as exc:
                if attempt or not any(code in str(exc) for code in ['PROVIDER_HTTP_503', 'PROVIDER_HTTP_502', 'PROVIDER_TIMEOUT']):
                    raise
                print('Retrying one transient fallback failure; its log is retained', flush=True)
                time.sleep(2)
        assert reply['kind'] == 'ask' and reply.get('question')
        remembered = call('POST', f'/ai-operator/brain/sessions/{session["id"]}/turns',
                          {'request_key': str(uuid4()), 'revision': 0,
                           'text': 'Prepare a new release; ask for deadline', 'reply': reply,
                           'runtime': 'cloud', 'model': config['model'], 'fallback_reason': 'unsupported'})
        assert remembered['revision'] == 1
        record('Real cloud fallback, validated follow-up and persisted routing reason', {'session_id': session['id'], 'kind': reply['kind']})
        after = call('GET', '/ai-operator/analytics')
        logs = [r for r in after['logs'] if r['id'] > baseline and r['provider'] == args.provider]
        successful = [r for r in logs if r['status'] == 'success']
        assert len(successful) == 3 and len(logs) <= 4, 'Connectivity, one planning call, fallback and at most one transient retry'
        assert {r['purpose'] for r in logs} == {'test', 'plan', 'brain_fallback'}
        for row in logs:
            if row['status'] != 'success':
                assert row['error_code'] and row['http_status'] in (502, 503, None)
                continue
            assert row['status'] == 'success' and row['http_status'] == 200
            assert row['input_tokens'] > 0 and row['output_tokens'] > 0 and row['duration_ms'] > 0
            assert not {'prompt', 'response', 'api_key', 'encrypted_key'} & row.keys()
            if config['input_price'] is not None and config['output_price'] is not None:
                expected = (row['input_tokens'] * float(config['input_price']) + row['output_tokens'] * float(config['output_price'])) / 1_000_000
                assert row['estimated_cost'] is not None and abs(float(row['estimated_cost']) - expected) <= 0.00000001
        evidence['logs'] = logs
        evidence['groups'] = [g for g in after['groups'] if g['provider'] == args.provider]
        evidence['cost_note'] = after['cost_note']
        metrics = call('GET', f'/ai-operator/workbench/metrics?project_id={args.project}')
        assert metrics['routing']['cloud'] >= 1
        record('Usage analytics: actual tokens, latency, estimated cost and sanitized logs', {'log_ids': [r['id'] for r in logs]})
        evidence['status'] = 'passed'
    except Exception as exc:
        evidence['status'] = 'failed'
        evidence['error'] = str(exc)
        print('FAIL', str(exc), flush=True)
    finally:
        client.close()
        (out / f'{args.provider}-results.json').write_text(json.dumps(evidence, indent=2, default=str))
    return 0 if evidence['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
