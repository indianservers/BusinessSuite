from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.ai_operator.deadline_radar import RadarConfig, build_radar
from app.apps.project_management.models import PMSTask
from tests.test_ai_operator import setup_operator, isolate_generic_http_audit


def test_radar_buckets_dates_and_excludes_completed():
    today = date(2026, 11, 7)
    tasks = [SimpleNamespace(id=i, project_id=1, task_key=f'T-{i}', title='Deadline',
                             status=status, priority='High', due_date=due)
             for i, (due, status) in enumerate([
                 (today-timedelta(days=1), 'In Progress'), (today, 'To Do'),
                 (today+timedelta(days=7), 'To Do'), (today+timedelta(days=8), 'To Do'),
                 (None, 'To Do'), (today-timedelta(days=5), 'Completed')], 1)]
    result = build_radar(tasks, today, RadarConfig(horizon_days=7))
    assert result['counts'] == dict(overdue=1, today=1, upcoming=1, later=1, undated=1, completed=1)
    assert [r['id'] for r in result['items']] == [1, 2, 3, 5]
    assert result['items'][0]['days_remaining'] == -1
    assert build_radar(tasks, today, RadarConfig(include_completed=True))['items'][-1]['bucket'] == 'completed'


@pytest.mark.parametrize('payload', [{'horizon_days':0}, {'horizon_days':366}, {'horizon_days':True},
                                     {'timezone':'Invalid/Zone'}, {'include_completed':'false'}, {'script':'alert(1)'}])
def test_radar_rejects_invalid_or_executable_configuration(payload):
    with pytest.raises(ValidationError):
        RadarConfig.model_validate(payload)


def test_live_radar_save_reopen_conflict_and_access(client, db):
    headers, user, project, task = setup_operator(client, db)
    row = db.get(PMSTask, task)
    row.due_date = date.today()-timedelta(days=2)
    db.commit()
    root = '/api/v1/ai-operator'
    response = client.get(root+'/workspace/deadline-radar', headers=headers, params={'project_id':project})
    assert response.status_code == 200, response.text
    assert response.json()['counts']['overdue'] == 1
    assert response.json()['coverage']['complete'] is True
    payload = {'project_id':project, 'kind':'deadline_radar', 'title':'Client deadlines',
               'payload':{'horizon_days':14, 'include_completed':False, 'timezone':'Asia/Kolkata'}}
    saved = client.post(root+'/workbench/items', headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    artifact = saved.json()
    assert 'items' not in artifact['payload']  # No cached task data persisted.
    assert client.put(root+f'/workbench/items/{artifact["id"]}', headers=headers,
                      json={**payload, 'revision':0}).status_code == 422
    update = client.put(root+f'/workbench/items/{artifact["id"]}', headers=headers,
                        json={**payload, 'revision':artifact['revision']})
    assert update.status_code == 200, update.text
    assert client.put(root+f'/workbench/items/{artifact["id"]}', headers=headers,
                      json={**payload, 'revision':artifact['revision']}).status_code == 409
    assert client.get(root+'/workbench/items', headers=headers, params={'project_id':project}).json()['items'][0]['kind'] == 'deadline_radar'
    row.status = 'Completed'
    db.commit()
    refreshed = client.get(root+'/workspace/deadline-radar', headers=headers, params={'project_id':project}).json()
    assert refreshed['counts']['overdue'] == 0 and refreshed['items'] == []
    assert client.get(root+'/workspace/deadline-radar', params={'project_id':project}).status_code in (401,403)
    from ai_test_utils import auth_headers
    outsider_headers, _ = auth_headers(client, db, email='radar-outsider@example.com', permissions=['ai_assistant'])
    denied = client.get(root+'/workspace/deadline-radar', headers=outsider_headers, params={'project_id':project})
    assert denied.status_code in (403,404), denied.text
