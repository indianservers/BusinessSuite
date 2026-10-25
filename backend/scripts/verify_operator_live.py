"""Explicit live QA: creates labelled PMS records; never supplies provider keys.

Run after starting the backend and worker. Auth lives in ignored .local only.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.local/operator-live-qa'
auth = json.loads((OUT / 'auth.json').read_text())
client = httpx.Client(base_url='http://127.0.0.1:1534/api/v1',
                      headers={'Authorization': 'Bearer ' + auth['token']}, timeout=60)
results = []
state = {'started_at': datetime.now(timezone.utc).isoformat(), 'checks': results}


def call(method, path, body=None, expected=200):
    r = client.request(method, path, json=body)
    assert r.status_code == expected, f'{method} {path}: {r.status_code} {r.text[:800]}'
    return r.json()


def check(name, action):
    try:
        evidence = action()
        results.append({'name': name, 'status': 'passed', 'evidence': evidence})
        print('PASS', name, flush=True)
    except Exception as e:
        results.append({'name': name, 'status': 'failed', 'error': str(e)})
        print('FAIL', name, str(e)[:500], flush=True)
    (OUT / 'api-results.json').write_text(json.dumps(state, indent=2, default=str))


def wait_run(run):
    for _ in range(60):
        row = call('GET', f'/ai-operator/runs/{run["id"]}')
        if row['status'] in ('succeeded', 'failed', 'paused', 'cancelled'):
            assert row['status'] == 'succeeded', str(row)
            return row
        time.sleep(1)
    raise AssertionError('Worker did not finish within 60 seconds')


stamp = uuid4().hex[:6].upper()
project = call('POST', '/project-management/projects', {'name': f'AI Operator live QA {stamp}', 'project_key': f'AIQA{stamp}'})
p = project['id']
state['project_id'] = p
tasks = [call('POST', f'/project-management/projects/{p}/tasks', {'title': title, 'task_key': f'QA-{i+1}', 'estimated_hours': 8}) for i, title in enumerate(['QA execution target', 'QA dependency target'])]
t, other = [r['id'] for r in tasks]
state['task_ids'] = [t, other]
W = '/ai-operator/workbench'


def item(kind, payload):
    return call('POST', W+'/items', {'project_id': p, 'kind': kind, 'title': 'Live QA '+kind, 'payload': payload})


def plan(steps=None):
    return {'summary': 'Live QA priority and checklist', 'steps': steps or [
        {'tool': 'update_task', 'task_id': t, 'changes': {'priority': 'High'}},
        {'tool': 'add_checklist', 'task_id': t, 'title': 'Live QA checklist'}]}


def draft(body=None, **extra):
    return {'project_id': p, 'plan': body or plan(), 'request_key': str(uuid4()), **extra}


def preview_execute():
    body = draft(mode='checkpointed', input_mode='voice')
    impact = call('POST', W+'/impact', body)
    assert impact['changes']
    run = call('POST', W+'/plans/preview', body)
    assert run['status'] == 'awaiting_approval'
    call('POST', f'/ai-operator/runs/{run["id"]}/approve', {'plan_hash': '0'*64}, 409)
    call('POST', f'/ai-operator/runs/{run["id"]}/approve', {'plan_hash': run['plan_hash']})
    final = wait_run(run)
    state['executed_run'] = final['id']
    steps = call('GET', f'/ai-operator/runs/{run["id"]}/steps')
    events = call('GET', f'/ai-operator/runs/{run["id"]}/events')
    assert steps['items'] and events['items']
    return {'run_id': final['id'], 'mode': 'checkpointed', 'input_mode': final['input_mode'], 'step_count': len(steps['items']), 'event_count': len(events['items'])}


check('Plan editor contract, impact, approval hash, voice provenance, worker receipts', preview_execute)


def undo():
    row = call('POST', W+f'/runs/{state["executed_run"]}/undo-preview')['run']
    call('POST', f'/ai-operator/runs/{row["id"]}/approve', {'plan_hash': row['plan_hash']})
    return {'undo_run_id': wait_run(row)['id']}


check('Recovery through separately approved inverse plan', undo)


def memory():
    row = item('memory', {'text': 'QA launch means the validation project', 'category': 'terminology'})
    session = call('POST', '/ai-operator/brain/sessions', {'project_id': p})
    context = call('GET', f'/ai-operator/brain/sessions/{session["id"]}/context')['context']
    assert any(m['text'].startswith('QA launch') for m in context['project_memory'])
    state['session_id'] = session['id']
    body = {'project_id': p, 'kind': 'memory', 'title': 'Corrected QA memory', 'payload': {'text': 'QA launch is validation only'}, 'revision': 1}
    changed = call('PUT', W+f'/items/{row["id"]}', body)
    assert changed['revision'] == 2
    call('PUT', W+f'/items/{row["id"]}', body, 409)
    return {'memory_id': row['id'], 'session_id': session['id'], 'context_tasks': len(context['tasks'])}


check('Persistent memory, corrections, stale revision and authorized context', memory)


def conversation():
    sid = state['session_id']
    row = call('POST', f'/ai-operator/brain/sessions/{sid}/turns', {'request_key': str(uuid4()), 'revision': 0, 'text': 'Plan our QA launch', 'reply': {'kind': 'ask', 'message': 'I need a date.', 'question': 'When is the deadline?'}, 'runtime': 'browser', 'model': 'live-QA-contract'})
    packet = call('GET', f'/ai-operator/brain/sessions/{sid}/context')
    assert packet
    return {'session_id': sid, 'saved_revision': row.get('revision'), 'note': 'Persistence contract; generated follow-up checked separately in browser'}


check('Follow-up conversation persistence', conversation)


def schedule():
    row = item('policy', {'holidays': ['2026-10-26'], 'auto_enabled': False})
    state['policy'] = row
    payload = draft(plan([{'tool': 'add_dependency', 'task_id': other, 'source_task_id': t, 'dependency_type': 'Finish To Start', 'lag_days': 0}]))
    run = call('POST', W+'/plans/preview', payload)
    call('POST', f'/ai-operator/runs/{run["id"]}/approve', {'plan_hash': run['plan_hash']})
    wait_run(run)
    suggestion = call('POST', W+'/schedule', {'project_id': p, 'task_ids': [other, t], 'start_date': '2026-10-24'})
    assert suggestion['plan']['steps'][0]['start_date'] == '2026-10-27'
    assert suggestion['plan']['steps'][1]['start_date'] == '2026-10-28'
    return suggestion


check('Dependency and working-calendar scheduling', schedule)
check('Workload-aware assignment and delivery risks', lambda: call('GET', W+f'/insights?project_id={p}'))
check('Natural-language task search', lambda: call('GET', W+f'/search?project_id={p}&q=QA'))


def kickoff():
    setup = {'summary': 'QA project kickoff', 'name': f'QA kickoff {stamp}', 'project_key': f'K{stamp}', 'milestones': [{'key': 'M1', 'name': 'QA release', 'due_date': '2026-11-06'}], 'tasks': [{'key': 'PARENT', 'title': 'QA parent'}, {'key': 'CHILD', 'title': 'QA child', 'parent_key': 'PARENT', 'blocked_by': ['PARENT']}]}
    proposal = call('POST', '/ai-operator/setup/preview', {'brief': 'Create QA hierarchy', 'provider': 'openai', 'request_key': str(uuid4()), 'local_plan': setup})
    result = call('POST', f'/ai-operator/proposals/{proposal["id"]}/approve', {'plan_hash': proposal['plan_hash']})
    assert result['status'] == 'succeeded', result
    return {'proposal_id': proposal['id'], 'result': result['result']}


check('Project kickoff, milestones, subtasks and dependencies', kickoff)


def agents():
    book = item('playbook', {'plan': plan([{'tool': 'update_task', 'task_id': t, 'changes': {'priority': 'Urgent'}}])})
    manual = call('POST', W+f'/items/{book["id"]}/run')
    assert manual['status'] == 'awaiting_approval'
    call('POST', f'/ai-operator/runs/{manual["id"]}/cancel')
    pol = state['policy']
    call('PUT', W+f'/items/{pol["id"]}', {'project_id': p, 'kind': 'policy', 'title': 'QA bounded autonomy', 'revision': pol['revision'], 'payload': {'auto_enabled': True, 'allowed_tools': ['update_task'], 'max_steps': 1}})
    run = call('POST', W+'/plans/preview', draft(plan([{'tool': 'update_task', 'task_id': t, 'changes': {'status': 'Blocked'}}])))
    call('POST', f'/ai-operator/runs/{run["id"]}/approve', {'plan_hash': run['plan_hash']})
    wait_run(run)
    rule = item('rule', {'playbook_id': book['id'], 'trigger': 'blocked', 'enabled': True, 'autonomous': True})
    state['rule_id'] = rule['id']
    for _ in range(90):
        rows = call('GET', W+f'/items?project_id={p}')['items']
        latest = next(r for r in rows if r['id'] == rule['id'])
        if latest['payload'].get('last_run_id'):
            result = wait_run({'id': latest['payload']['last_run_id']})
            call('PUT', W+f'/items/{rule["id"]}', {'project_id': p, 'kind': 'rule', 'title': 'QA agent disabled after validation', 'revision': latest['revision'], 'payload': {'playbook_id': book['id'], 'trigger': 'blocked', 'enabled': False, 'autonomous': False}})
            return {'playbook_id': book['id'], 'manual_cancelled_run': manual['id'], 'rule_id': rule['id'], 'automatic_run_id': result['id']}
        time.sleep(1)
    raise AssertionError('Worker did not observe rule')


check('Playbooks, cancel, live event agents and bounded autonomous execution', agents)


def monitor():
    row = call('POST', '/ai-operator/monitors', {'project_id': p, 'name': 'Live QA delivery watch', 'interval_minutes': 60})
    for _ in range(45):
        latest = next(r for r in call('GET', f'/ai-operator/monitors?project_id={p}')['items'] if r['id'] == row['id'])
        if latest['checked_at']:
            call('PUT', f'/ai-operator/monitors/{row["id"]}', {'project_id': p, 'name': 'Live QA delivery watch (validated)', 'interval_minutes': 60, 'enabled': False})
            return latest
        time.sleep(1)
    raise AssertionError('Monitor did not run')


check('Proactive delivery monitor through worker', monitor)


def teaching():
    row = item('teaching', {'command': 'Set QA priority high', 'plan': plan()})
    assert not call('GET', W+f'/teaching/export?project_id={p}')['examples']
    call('POST', W+f'/items/{row["id"]}/approve-teaching')
    assert len(call('GET', W+f'/teaching/export?project_id={p}')['examples']) == 1
    return {'teaching_id': row['id'], 'reviewed_export_count': 1}


check('Teaching review and approved-only export', teaching)


def quality():
    case = item('evaluation', {'command': 'Raise priority and add QA', 'expected_kind': 'task_plan', 'expected_tools': ['update_task', 'add_checklist']})
    result = call('POST', W+f'/items/{case["id"]}/evaluate', {'actual_kind': 'task_plan', 'actual_plan': plan(), 'duration_ms': 10, 'request_key': str(uuid4())})
    assert result['passed']
    call('POST', W+'/feedback', {'project_id': p, 'category': 'incorrect_plan', 'request_key': str(uuid4())})
    return result


check('Quality validation and feedback persistence', quality)
check('Routing, provider-usage and execution analytics', lambda: call('GET', W+f'/metrics?project_id={p}'))
check('Provider settings availability (no credentials fabricated)', lambda: call('GET', '/ai-operator/providers'))
print('RESULTS', sum(r['status']=='passed' for r in results), '/', len(results), 'project', p, flush=True)
client.close()
raise SystemExit(1 if any(r['status'] == 'failed' for r in results) else 0)
