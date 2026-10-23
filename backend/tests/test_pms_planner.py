from datetime import date, datetime, timezone
from app.apps.project_management.models import PMSTask, PMSMilestone, PMSWorkspaceMember, PMSTaskAssignee
from tests.test_pms_workspaces import account, middleware_database, BASE


def test_planner_includes_full_schedule_and_enforces_visibility(client, db):
    owner, headers = account(db, 'planner-owner@test.com', True)
    guest, gh = account(db, 'planner-guest@test.com')
    outsider, oh = account(db, 'planner-outsider@test.com', True)
    wid=client.post(BASE+'/workspaces',headers=headers,json={'name':'Planner workspace'}).json()['id']
    pid=client.post(BASE+'/projects',headers=headers,json={'name':'Planner project','project_key':'PLAN','workspace_id':wid,'due_date':'2026-11-30'}).json()['id']
    db.add(PMSWorkspaceMember(workspace_id=wid,user_id=guest.id,role='Guest'))
    for index in range(25):
        db.add(PMSTask(project_id=pid,title=f'Scheduled task {index}',task_key=f'PLAN-{index}',due_date=date(2026,11,15),status='To Do'))
    db.add(PMSTask(project_id=pid,title='Removed task',task_key='PLAN-X',deleted_at=datetime.now(timezone.utc)))
    db.add(PMSMilestone(project_id=pid,name='Release milestone',due_date=date(2026,11,20)))
    db.commit()
    response=client.get(BASE+'/planner',headers=headers)
    assert response.status_code==200,response.text
    data=response.json()
    assert len(data['tasks'])==25
    assert data['projects'][0]['due_date']=='2026-11-30'
    assert data['milestones'][0]['title']=='Release milestone'
    assert all(t['can_schedule'] for t in data['tasks'])
    guest_data=client.get(BASE+'/planner',headers=gh).json()
    assert len(guest_data['tasks'])==25
    assert not any(t['can_schedule'] for t in guest_data['tasks'])
    assert client.get(BASE+'/planner',headers=oh).json()['tasks']==[]
    tid=data['tasks'][0]['id']
    assert client.patch(f'{BASE}/tasks/{tid}',headers=gh,json={'due_date':'2026-11-21'}).status_code==403
    assert client.patch(f'{BASE}/tasks/{tid}',headers=headers,json={'due_date':'2026-11-21'}).status_code==200
    assert next(t for t in client.get(BASE+'/planner',headers=headers).json()['tasks'] if t['id']==tid)['due_date']=='2026-11-21'


def test_planner_empty_and_unauthenticated(client, db):
    _, headers=account(db,'planner-empty@test.com')
    assert client.get(BASE+'/planner',headers=headers).json()['tasks']==[]
    assert client.get(BASE+'/planner').status_code in (401,403)
