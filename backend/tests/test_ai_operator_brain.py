from uuid import uuid4
import pytest
from tests.test_ai_operator import setup_operator, mock_provider, isolate_generic_http_audit, plan_for
from app.ai_operator.models import OperatorApiLog
from app.apps.project_management.models import PMSTask
from ai_test_utils import auth_headers

ROOT = '/api/v1/ai-operator/brain/sessions'


def session(client, headers, project):
    response = client.post(ROOT, headers=headers, json={'project_id': project})
    assert response.status_code == 200, response.text
    return response.json()


def test_private_memory_followups_revisions_clear_and_no_provider_calls(client, db, monkeypatch):
    headers, user, project, task = setup_operator(client, db)
    calls = mock_provider(monkeypatch, {})
    row = session(client, headers, project)
    body = {'request_key': str(uuid4()), 'revision': 0, 'text': 'Plan a release',
            'reply': {'kind': 'ask', 'message': 'I can prepare the plan.', 'question': 'What is the deadline?'},
            'runtime': 'browser', 'model': 'SmolLM2-135M-Instruct-tfjs'}
    endpoint = f"{ROOT}/{row['id']}"
    response = client.post(endpoint+'/turns', headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()['revision'] == 1
    assert client.post(endpoint+'/turns', headers=headers, json=body).json()['revision'] == 1
    changed = {**body, 'request_key': str(uuid4()), 'text': 'Tomorrow'}
    assert client.post(endpoint+'/turns', headers=headers, json=changed).status_code == 409
    changed['revision'] = 1
    changed['reply'] = {'kind': 'answer', 'message': 'The draft deadline is tomorrow.'}
    assert client.post(endpoint+'/turns', headers=headers, json=changed).status_code == 200
    packet = client.get(endpoint+'/context', headers=headers).json()
    assert [t['text'] for t in packet['session']['turns']] == ['Plan a release', 'Tomorrow']
    assert all(t['execution'] == 'draft_only' for t in packet['session']['turns'])
    other_headers, _ = auth_headers(client, db, email=f'other-{uuid4()}@example.com',
                                   permissions=['ai_assistant', 'pms_manage_tasks', 'pms_manage_projects'])
    assert client.get(endpoint+'/context', headers=other_headers).status_code in (403, 404)
    cleared = client.delete(endpoint+'/memory', headers=headers)
    assert cleared.status_code == 200 and cleared.json()['turns'] == []
    assert cleared.json()['revision'] == 3
    assert calls == []


def test_local_multi_step_draft_reuses_approval_and_rejects_invalid_tools(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    calls = mock_provider(monkeypatch, {})
    row = session(client, headers, project)
    reply = {'kind': 'task_plan', 'message': 'Review this draft.', 'task_ids': [task], 'task_plan': plan_for(task)}
    endpoint = f"{ROOT}/{row['id']}/validate"
    response = client.post(endpoint, headers=headers, json={'reply': reply})
    assert response.status_code == 200, response.text
    assert db.get(PMSTask, task).priority != 'High'
    invalid = {**reply, 'task_ids': [999999]}
    assert client.post(endpoint, headers=headers, json={'reply': invalid}).status_code in (400, 403, 404, 422)
    reply['task_plan']['steps'][0]['tool'] = 'delete_project'
    assert client.post(endpoint, headers=headers, json={'reply': reply}).status_code == 422
    assert calls == []


@pytest.mark.parametrize('provider', ['openai', 'gemini', 'claude'])
def test_cloud_fallback_uses_existing_provider_and_metering(client, db, monkeypatch, provider):
    headers, _, project, _ = setup_operator(client, db, provider)
    row = session(client, headers, project)
    calls = mock_provider(monkeypatch, {'kind': 'ask', 'message': 'I need one detail.', 'question': 'What date?'})
    response = client.post(f"{ROOT}/{row['id']}/cloud", headers=headers, json={
        'text': 'Plan an involved release', 'provider': provider, 'fallback_reason': 'invalid_output'})
    assert response.status_code == 200, response.text
    assert response.json()['kind'] == 'ask' and len(calls) == 1
    logs = db.query(OperatorApiLog).filter_by(provider=provider).all()
    assert any(log.purpose == 'brain_fallback' for log in logs)
