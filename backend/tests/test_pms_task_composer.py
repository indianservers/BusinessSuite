from datetime import date
from app.apps.project_management.models import PMSTask
from app.apps.project_management.recurrence import create_next_occurrence, validate_recurrence
from tests.test_pms_workspaces import account, middleware_database, BASE


def test_recurring_completion_is_idempotent_and_honors_end_date(client, db):
    _, headers = account(db, 'repeat-owner@test.com', True)
    workspace = client.post(BASE + '/workspaces', json={'name': 'Repeat audit'}, headers=headers).json()
    project = client.post(BASE + '/projects', json={'name': 'Repeat project', 'project_key': 'REP', 'workspace_id': workspace['id']}, headers=headers).json()
    response = client.post(f"{BASE}/projects/{project['id']}/tasks", headers=headers, json={'title':'Monthly close','task_key':'REP-1','work_type':'Feature','due_date':'2026-01-31','recurrence_rule':'monthly','recurrence_interval':1,'recurrence_until':'2026-02-28'})
    assert response.status_code == 200, response.text
    task_id = response.json()['id']
    response = client.patch(f'{BASE}/tasks/{task_id}', headers=headers, json={'status':'Done'})
    assert response.status_code == 200, response.text
    following = db.query(PMSTask).filter_by(task_key=f'REPEAT-{task_id}').one()
    assert following.due_date == date(2026,2,28)
    assert following.status == 'To Do'
    client.patch(f'{BASE}/tasks/{task_id}', headers=headers, json={'status':'To Do'})
    client.patch(f'{BASE}/tasks/{task_id}', headers=headers, json={'status':'Done'})
    assert db.query(PMSTask).filter_by(task_key=f'REPEAT-{task_id}').count() == 1
    client.patch(f'{BASE}/tasks/{following.id}', headers=headers, json={'status':'Done'})
    assert db.query(PMSTask).filter_by(task_key=f'REPEAT-{following.id}').count() == 0
