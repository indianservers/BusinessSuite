from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.ai_operator.briefing import local_date, rank_items
from app.ai_operator.evidence import issue_sources, select_sources
from app.apps.crm.models import CRMTask
from tests.test_suite_operator import setup_suite, approve, tick
from tests.test_ai_operator import mock_provider, isolate_generic_http_audit

ROOT = '/api/v1/ai-operator/suite'


def test_ranking_personal_scope_timezone_completed_and_evidence():
    packets = [{'tool': 'crm.tasks', 'records': [
        {'id': 1, 'title': 'Mine blocked', 'status': 'Blocked', 'owner_user_id': 7},
        {'id': 2, 'title': 'Other owner', 'owner_user_id': 8, 'due_date': '2026-11-09'},
        {'id': 3, 'title': 'Completed', 'owner_user_id': 7, 'status': 'Done', 'due_date': '2026-11-09'},
        {'id': 4, 'title': 'Today in India', 'owner_user_id': 7, 'due_date': '2026-11-09T20:00:00Z'},
        {'id': 5, 'title': 'No signal', 'owner_user_id': 7},
    ]}]
    sources = issue_sources(packets, '2026-11-10T00:00:00Z')
    rows = rank_items(packets, sources, date(2026, 11, 10), 'Asia/Kolkata', 7)
    assert [row['record_id'] for row in rows] == [1, 4]
    assert rows[1]['reasons'] == ['Due today']
    assert rows[0]['source']['record_id'] == 1
    assert local_date('invalid', 'Asia/Kolkata') is None


def test_evidence_rejects_unknown_ids_and_deduplicates():
    from fastapi import HTTPException
    sources = issue_sources([{'tool': 'pms.tasks', 'record_id': 9, 'records': [{'id': 1, 'title': 'Check'}]}], 'now')
    assert select_sources(['s1:1', 's1:1'], sources) == sources
    assert sources[0]['href'] == '/pms/tasks/1'
    with pytest.raises(HTTPException):
        select_sources(['invented'], sources)


def test_briefing_reads_real_crm_and_project_sources_without_cloud(client, db, monkeypatch):
    from app.ai_operator import suite
    headers, user, project, task_id = setup_suite(client, db)
    yesterday = (date.today() - timedelta(days=2)).isoformat()
    created = client.post('/api/v1/crm/tasks', headers=headers, json={'title': 'Call customer', 'due_date': yesterday + 'T12:00:00Z'})
    assert created.status_code in (200, 201), created.text
    client.patch(f'/api/v1/crm/tasks/{created.json()["id"]}', headers=headers, json={'priority': 'High'})
    from app.apps.project_management.models import PMSTask
    db.get(PMSTask, task_id).status = 'Blocked'
    db.commit()
    def forbidden(*args, **kwargs):
        raise AssertionError('Briefing must not call a model')
    monkeypatch.setattr(suite, 'generate_json', forbidden)
    response = client.get(ROOT + '/briefing', headers=headers, params={'project_id': project, 'mine': False})
    assert response.status_code == 200, response.text
    body = response.json()
    assert any(row['record_id'] == created.json()['id'] and row['module'] == 'CRM' for row in body['priorities']), body
    assert any(row['record_id'] == task_id and 'Blocked' in row['reasons'] for row in body['delivery_risks']), body
    assert all(row['source']['retrieved_at'] for row in body['priorities'])
    assert any(row['status'] == 'unavailable' for row in body['coverage'])  # No employee profile.
    assert body['limited'] is True


def test_briefing_denied_source_never_leaks_records(client, db, monkeypatch):
    from app.ai_operator import suite
    from fastapi import HTTPException
    headers, _, _, _ = setup_suite(client, db)
    async def denied(*args, **kwargs):
        raise HTTPException(403, 'Secret data must not be returned')
    monkeypatch.setattr(suite, 'api_call', denied)
    response = client.get(ROOT + '/briefing', headers=headers, params={'module': 'CRM'})
    assert response.status_code == 200, response.text
    assert response.json()['priorities'] == []
    assert response.json()['coverage'][0]['status'] == 'unavailable'
    assert 'Secret' not in response.text
    assert client.get(ROOT + '/briefing', headers=headers, params={'timezone': 'invalid'}).status_code == 422
    assert client.get(ROOT + '/briefing', headers=headers, params={'module': 'FAM'}).status_code == 422


def test_local_task_draft_requires_existing_approval_and_does_not_call_cloud(client, db, monkeypatch):
    from app.ai_operator import suite
    headers, _, _, _ = setup_suite(client, db)
    from app.ai_operator.models import OperatorProvider
    db.query(OperatorProvider).delete()
    db.commit()
    def forbidden(*args, **kwargs):
        raise AssertionError('Local mode must not invoke the cloud')
    monkeypatch.setattr(suite, 'generate_json', forbidden)
    response = client.post(ROOT + '/commands', headers=headers, json={
        'request_key': str(uuid4()), 'text': 'Create CRM task: Call Acme', 'provider': 'local', 'module': 'CRM',
    })
    assert response.status_code == 200, response.text
    run = response.json()
    assert run['status'] == 'awaiting_approval', run
    assert db.query(CRMTask).count() == 0
    approve(client, headers, run)
    assert tick(client, db) == 1
    assert db.query(CRMTask).one().title == 'Call Acme'
    assert tick(client, db) == 0


def test_briefing_real_denied_actor_does_not_receive_crm_content(client, db):
    from ai_test_utils import auth_headers
    headers, _, _, _ = setup_suite(client, db)
    client.post('/api/v1/crm/tasks', headers=headers, json={'title': 'Private customer escalation', 'priority': 'High'})
    other, _ = auth_headers(client, db, email=f'{uuid4()}@example.com', permissions=['ai_assistant'])
    response = client.get(ROOT + '/briefing', headers=other, params={'module': 'CRM', 'mine': False})
    assert response.status_code in (200, 403), response.text
    assert 'Private customer escalation' not in response.text
    if response.status_code == 200:
        assert response.json()['coverage'][0]['status'] == 'unavailable'


def test_briefing_caps_records_and_marks_partial_coverage(client, db, monkeypatch):
    from app.ai_operator import suite
    headers, _, _, _ = setup_suite(client, db)
    async def sample(*args, **kwargs):
        return {'items': [{'id': ident, 'title': f'Task {ident}', 'priority': 'High'} for ident in range(1, 56)], 'total': 100}
    monkeypatch.setattr(suite, 'api_call', sample)
    response = client.get(ROOT + '/briefing', headers=headers, params={'module': 'CRM', 'mine': False})
    assert response.status_code == 200, response.text
    assert len(response.json()['priorities']) == 50
    assert response.json()['limited'] is True
    assert response.json()['coverage'][0]['limited'] is True


@pytest.mark.parametrize('provider', ['openai', 'gemini'])
def test_cloud_answer_citations_use_real_authorized_evidence(client, db, monkeypatch, provider):
    headers, _, _, _ = setup_suite(client, db)
    if provider == 'openai':
        configured = client.put('/api/v1/ai-operator/providers/openai', headers=headers, json={
            'model': 'test-model', 'api_key': 'unit-test-secret-key', 'enabled': True, 'data_sharing_allowed': True})
        assert configured.status_code == 200, configured.text
    task = client.post('/api/v1/crm/tasks', headers=headers, json={'title': 'Evidence task'}).json()
    calls = mock_provider(monkeypatch, {'summary': 'The selected task is Evidence task.', 'steps': [], 'source_ids': [f's1:{task["id"]}']})
    response = client.post(ROOT + '/commands', headers=headers, json={
        'request_key': str(uuid4()), 'text': 'Summarize the source', 'provider': provider, 'context': [{'tool': 'crm.tasks'}],
    })
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'answered', response.text
    assert response.json()['result']['citations'][0]['record_id'] == task['id']
    assert len(calls) == 1
    mock_provider(monkeypatch, {'summary': 'Unsupported claim', 'steps': [], 'source_ids': ['invented']})
    invalid = client.post(ROOT + '/commands', headers=headers, json={
        'request_key': str(uuid4()), 'text': 'Summarize', 'provider': provider, 'context': [{'tool': 'crm.tasks'}],
    })
    assert invalid.json()['status'] == 'failed', invalid.text


def test_local_pms_task_draft_executes_through_canonical_api(client, db):
    headers, _, project, _ = setup_suite(client, db)
    response = client.post(ROOT + '/commands', headers=headers, json={
        'request_key': str(uuid4()), 'text': 'Create PMS task: Verify launch', 'provider': 'local', 'module': 'PMS', 'project_id': project,
    })
    assert response.status_code == 200, response.text
    run = response.json()
    assert run['status'] == 'awaiting_approval', run
    approve(client, headers, run)
    tick(client, db)
    final = client.get(ROOT + f'/runs/{run["id"]}', headers=headers).json()
    assert final['status'] == 'succeeded', final
    assert final['receipts'][0]['record_id']
