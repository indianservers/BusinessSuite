from datetime import date, datetime, timedelta, timezone
import json
from app.apps.project_management.models import PMSTask, PMSTaskAssignee, PMSTimeLog, PMSActivity, PMSWorkspaceMember, PMSWorkspaceTeam
from tests.test_pms_workspaces import account, middleware_database, BASE


def setup_analytics(client, db):
    owner, headers = account(db, 'analytics-owner@test.com', True)
    member, member_headers = account(db, 'analytics-member@test.com')
    outsider, outsider_headers = account(db, 'analytics-outsider@test.com')
    wid = client.post(BASE+'/workspaces', headers=headers, json={'name':'Analytics workspace'}).json()['id']
    db.add(PMSWorkspaceMember(workspace_id=wid,user_id=member.id,role='Member'))
    project = client.post(BASE+'/projects', headers=headers, json={'workspace_id':wid,'name':'Analytics project','project_key':'ANA'}).json()
    now = datetime.now(timezone.utc)
    shared = PMSTask(project_id=project['id'],title='Shared delivery',task_key='ANA-1',status='To Do',due_date=now.date()-timedelta(days=1),created_at=now)
    done = PMSTask(project_id=project['id'],title='Delivered',task_key='ANA-2',status='Done',completed_at=now,created_at=now)
    blocked = PMSTask(project_id=project['id'],title='Blocked',task_key='ANA-3',status='Blocked',created_at=now)
    deleted = PMSTask(project_id=project['id'],title='Deleted',task_key='ANA-4',status='To Do',deleted_at=now,created_at=now)
    db.add_all([shared,done,blocked,deleted]);db.flush()
    db.add_all([PMSTaskAssignee(task_id=shared.id,user_id=owner.id),PMSTaskAssignee(task_id=shared.id,user_id=member.id)])
    db.add_all([PMSTimeLog(project_id=project['id'],task_id=shared.id,user_id=owner.id,log_date=now.date(),duration_minutes=30),PMSTimeLog(project_id=project['id'],task_id=shared.id,user_id=member.id,log_date=now.date(),duration_minutes=90),PMSTimeLog(project_id=project['id'],user_id=owner.id,log_date=now.date(),duration_minutes=60)])
    db.add(PMSActivity(project_id=project['id'],task_id=shared.id,actor_user_id=member.id,action='task.updated',entity_type='task',summary='Updated',created_at=now))
    team=PMSWorkspaceTeam(workspace_id=wid,name='Delivery',alias='delivery',member_ids_json=json.dumps([member.id]));db.add(team);db.commit()
    return headers,member_headers,outsider_headers,project['id'],wid,team.id,member.id


def test_analytics_counts_shared_assignments_and_time_without_duplication(client, db):
    headers,_,_,pid,wid,tid,mid=setup_analytics(client,db)
    response=client.get(BASE+'/analytics/overview',headers=headers,params={'project_id':pid})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['summary']['total']==3
    assert data['summary']['completed']==1
    assert data['summary']['blocked']==1
    assert data['summary']['overdue']==1
    assert data['summary']['tracked_minutes']==180
    assert sum(x['completed'] for x in data['trend'])==1
    assert sum(x['people'] for x in data['hourly_activity'])==2
    person=next(p for p in data['people'] if p['id']==mid)
    assert person['total']==1 and person['tracked_minutes']==90
    assert person['focus'][0]['percent']==100
    assert person['recently_active'] is True
    filtered=client.get(BASE+'/analytics/overview',headers=headers,params={'workspace_id':wid,'team_id':tid}).json()
    assert filtered['summary']['total']==1
    assert filtered['summary']['tracked_minutes']==90
    assert len(filtered['people'])==1


def test_analytics_access_and_date_validation(client, db):
    headers,mh,outsider,pid,wid,tid,mid=setup_analytics(client,db)
    assert client.get(BASE+'/analytics/overview',headers=outsider,params={'project_id':pid}).status_code==403
    assert client.get(BASE+'/analytics/overview',headers=outsider,params={'workspace_id':wid}).status_code==403
    assert client.get(BASE+'/analytics/overview',headers=outsider).json()['summary']['total']==0
    db.query(PMSWorkspaceMember).filter_by(workspace_id=wid,user_id=mid).update({'role':'Guest'});db.commit()
    assert client.get(BASE+'/analytics/overview',headers=mh,params={'workspace_id':wid}).status_code==403
    assert client.get(BASE+'/analytics/overview',headers=headers,params={'start_date':'2026-02-01','end_date':'2026-01-01'}).status_code==422
    assert client.get(BASE+'/analytics/overview',headers=headers,params={'start_date':'2020-01-01','end_date':'2026-01-01'}).status_code==422
    historical=client.get(BASE+'/analytics/overview',headers=headers,params={'project_id':pid,'start_date':'2020-01-01','end_date':'2020-01-02'}).json()
    assert historical['summary']['total']==3
    assert historical['summary']['tracked_minutes']==0
    assert not any(p['recently_active'] for p in historical['people'])


def test_status_updates_record_completion_and_clear_on_reopen(client, db):
    headers,_,_,pid,_,_,_=setup_analytics(client,db)
    task=db.query(PMSTask).filter_by(project_id=pid,task_key='ANA-1').one()
    response=client.patch(f'{BASE}/tasks/{task.id}',headers=headers,json={'status':'Done'})
    assert response.status_code==200,response.text
    assert response.json()['completed_at'] is not None
    data=client.get(BASE+'/analytics/overview',headers=headers,params={'project_id':pid}).json()
    assert sum(item['completed'] for item in data['trend'])==2
    client.patch(f'{BASE}/tasks/{task.id}',headers=headers,json={'status':'To Do'})
    db.refresh(task)
    assert task.completed_at is None
    data=client.get(BASE+'/analytics/overview',headers=headers,params={'project_id':pid}).json()
    assert sum(item['completed'] for item in data['trend'])==1


def test_empty_workspace_still_shows_collaborators(client, db):
    owner, headers=account(db,'empty-analytics@test.com',True)
    wid=client.post(BASE+'/workspaces',headers=headers,json={'name':'Empty workspace'}).json()['id']
    response=client.get(BASE+'/analytics/overview',headers=headers,params={'workspace_id':wid})
    assert response.status_code==200,response.text
    assert response.json()['summary']['total']==0
    assert response.json()['summary']['people']==1
