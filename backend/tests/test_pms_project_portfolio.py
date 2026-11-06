from datetime import date, timedelta
from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import account, middleware_database, BASE
from tests.test_pms_automations import setup_workspace
from app.apps.project_management.models import PMSTask, PMSMilestone


def test_portfolio_summaries_are_scoped_and_exclude_deleted_tasks(client, db):
    wid, pid, owner, headers, *_ = setup_workspace(client, db)
    tasks = [PMSTask(project_id=pid, title="Done", task_key="D", status="Done"),
             PMSTask(project_id=pid, title="Blocked", task_key="B", status="Blocked", due_date=date.today()-timedelta(days=1)),
             PMSTask(project_id=pid, title="Removed", task_key="R", status="Done", deleted_at=__import__('datetime').datetime.now())]
    db.add_all(tasks)
    db.add(PMSMilestone(project_id=pid, name="Delivery", status="Completed"))
    db.commit()
    response = client.get(BASE+"/projects", headers=headers)
    assert response.status_code == 200, response.text
    row = next(p for p in response.json() if p['id'] == pid)
    assert row['task_count'] == 2
    assert row['completed_task_count'] == 1
    assert row['calculated_progress'] == 50
    assert row['blocked_task_count'] == row['overdue_task_count'] == 1
    assert row['milestone_count'] == row['completed_milestone_count'] == 1
    assert any(m['id'] == owner.id for m in row['team'])
    outsider, other_headers = account(db, 'portfolio-outsider@test.com')
    assert client.get(BASE+'/projects', headers=other_headers).json() == []
    assert client.get(BASE+'/projects', params={'skip':1,'limit':1}, headers=headers).json() == []


def test_inline_edits_validate_dates_enums_and_membership(client, db):
    wid, pid, owner, headers, ah, member, mh, guest, gh = setup_workspace(client, db)
    url = f'{BASE}/projects/{pid}'
    for payload in ({'name':' '}, {'status':'anything'}, {'priority':'anything'},
                    {'start_date':'2026-12-01','due_date':'2026-11-01'}, {'owner_user_id':999999}):
        response = client.patch(url, headers=headers, json=payload)
        assert response.status_code == 422, response.text
    assert client.patch(url, headers=mh, json={'priority':'High'}).status_code == 403
    assert client.patch(url, headers=headers, json={'priority':'High','name':'Renamed'}).status_code == 200
    row = next(p for p in client.get(BASE+'/projects', headers=headers).json() if p['id']==pid)
    assert row['priority'] == 'High' and row['name'] == 'Renamed'
