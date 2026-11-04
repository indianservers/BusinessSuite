from datetime import date, datetime, timezone
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from app.models.user import User, Role
from app.apps.crm.models import CRMNote
from app.apps.project_management.models import PMSTask, PMSProjectMember, PMSWorkspace, PMSWorkspaceMember, PMSTaskAssignee
from app.shared.record_360 import queue, events
from app.apps.project_management.task_visibility import visible_task_query
from app.apps.project_management.task_workspace import scoped_task
from tests.test_record_360 import seeded
from tests.test_pms_workspaces import account, middleware_database


def test_followup_page_checks_each_task_once_and_rechecks_next_request(db, monkeypatch):
    from app.apps.project_management.models import PMSTaskUpdateEntry
    from app.apps.project_management import task_workspace
    actor,_,_,_,project,task,_=seeded(db)
    db.add_all([PMSTaskUpdateEntry(task_id=task.id,author_id=actor.id,kind='followup',body=f'Follow-up {i}',follow_up_date=date.today()) for i in range(12)])
    db.commit()
    checked=[]
    def check(*args,**kwargs):
        checked.append(args[1])
        return scoped_task(*args,**kwargs)
    monkeypatch.setattr(task_workspace,'scoped_task',check)
    first=queue(1,5,'all','','pms_followup',project.id,None,db,actor,cursor_mode=True)
    assert len(first['items'])==5 and checked==[task.id]
    queue(1,5,'all','','pms_followup',project.id,None,db,actor,cursor_mode=True,cursor=first['next_cursor'])
    assert checked==[task.id,task.id]


def test_feed_authorization_does_not_reload_assignees_per_task(db):
    actor,_,_,_,project,_,_=seeded(db)
    db.add_all([PMSTask(project_id=project.id,task_key=f'PAGE-{i}',title=f'Page task {i}',due_date=date.today()) for i in range(4)])
    db.commit()
    statements=[]
    def capture(connection,cursor,statement,parameters,context,executemany):
        if statement.lstrip().startswith('SELECT pms_task_assignees.'):
            statements.append(statement)
    engine=db.get_bind()
    event.listen(engine,'before_cursor_execute',capture)
    try:
        result=queue(1,5,'all','','pms_task',project.id,None,db,actor,cursor_mode=True)
        assert len(result['items'])==5
        assert len(statements)==1, 'Page authorization must reuse the already loaded task assignees'
    finally:event.remove(engine,'before_cursor_execute',capture)
from tests.tenant_test_utils import assign_company


def test_more_than_5000_tasks_are_sql_filtered_and_load_only_a_page(db):
    actor,_,company,_,project,task,_=seeded(db)
    actor_id,project_id=actor.id,project.id
    db.add_all([PMSTask(project_id=project_id,task_key=f'LARGE-{i}',title=f'Large task {i}',due_date=date(2026,11,4)) for i in range(6005)])
    db.commit();db.expunge_all();actor=db.get(User,actor_id)
    loaded=[]
    def received(session,row):
        if isinstance(row,PMSTask):loaded.append(row.id)
    event.listen(db,'loaded_as_persistent',received)
    try:
        first=queue(1,5,'all','','pms_task',project_id,None,db,actor,cursor_mode=True)
        assert len(first['items'])==5 and first['total'] is None and first['has_more']
        assert len(loaded)<=6
        second=queue(1,5,'all','','pms_task',project_id,None,db,actor,cursor=first['next_cursor'],cursor_mode=True)
        assert not ({i['id'] for i in first['items']} & {i['id'] for i in second['items']})
        assert len(loaded)<=12
        selected=queue(1,5,'all','Large task 6004','pms_task',project_id,None,db,actor,cursor_mode=True)
        assert [i['title'] for i in selected['items']]==['Large task 6004']
    finally:event.remove(db,'loaded_as_persistent',received)


def test_history_snapshot_paging_excludes_new_and_backdated_inserts(db):
    actor,_,company,*_=seeded(db)
    stamp=datetime(2026,11,4,9,tzinfo=timezone.utc)
    notes=[CRMNote(organization_id=1,company_id=company.id,body=f'Original {i}',created_at=stamp) for i in range(12)]
    db.add_all(notes);db.commit();expected={note.id for note in notes}
    first=events('company',company.id,'crm',1,3,'note',db,actor,cursor_mode=True)
    db.add_all([CRMNote(organization_id=1,company_id=company.id,body='New'),CRMNote(organization_id=1,company_id=company.id,body='Backdated',created_at=datetime(2025,1,1))]);db.commit()
    seen=[i['source_id'] for i in first['items']];cursor=first['next_cursor']
    while cursor:
        result=events('company',company.id,'crm',1,3,'note',db,actor,cursor=cursor,cursor_mode=True)
        seen.extend(i['source_id'] for i in result['items']);cursor=result['next_cursor']
    assert len(seen)==len(set(seen))==12
    assert set(seen)==expected


def test_cursors_reject_tampering_and_scope_changes(db):
    actor,_,company,other,project,task,entry=seeded(db)
    first=queue(1,1,'all','','',project.id,None,db,actor,cursor_mode=True)
    cursor=first['next_cursor'];assert cursor
    for value,search in [(cursor+'x',''),(cursor,'changed')]:
        with pytest.raises(HTTPException) as error:queue(1,1,'all',search,'',project.id,None,db,actor,cursor=value,cursor_mode=True)
        assert error.value.status_code==422
    db.info['branch_context']=SimpleNamespace(branch_id=99,allowed=[99])
    try:
        with pytest.raises(HTTPException):queue(1,1,'all','','',project.id,None,db,actor,cursor=cursor,cursor_mode=True)
    finally:db.info.pop('branch_context',None)


@pytest.mark.parametrize('role', ['Viewer','Member','Lead','Client Viewer'])
@pytest.mark.parametrize('intern', [False,True])
def test_feed_task_visibility_matches_native_project_roles(db,role,intern):
    actor,_,company,_,project,task,entry=seeded(db)
    viewer,_=account(db,f'feed-{role}-{intern}@test.com');assign_company(db,viewer,1)
    if intern:
        viewer.role=db.query(Role).filter_by(name='intern').first() or Role(name='intern')
    db.add(PMSProjectMember(project_id=project.id,user_id=viewer.id,role=role))
    project.is_client_visible=True
    assigned=PMSTask(project_id=project.id,task_key='ASSIGNED',title='Assigned',assignee_user_id=viewer.id)
    db.add(assigned);db.flush()
    secondary=PMSTask(project_id=project.id,task_key='SECONDARY',title='Secondary')
    db.add(secondary);db.flush();db.add(PMSTaskAssignee(task_id=secondary.id,user_id=viewer.id));db.commit()
    native=set()
    for item in (task,assigned,secondary):
        try:scoped_task(db,item.id,viewer);native.add(item.id)
        except HTTPException:pass
    assert {r.id for r in visible_task_query(db,viewer)}==native
    result=queue(1,25,'all','','pms_task',project.id,None,db,viewer)
    assert {i['source_id'] for i in result['items']}==native
    assert result['total']==len(native)


@pytest.mark.parametrize('role',['Owner','Admin','Member','Guest'])
def test_feed_task_visibility_matches_native_workspace_roles(db,role):
    actor,_,company,_,project,task,entry=seeded(db)
    viewer,_=account(db,f'feed-workspace-{role}@test.com');assign_company(db,viewer,1)
    viewer.role=Role(name='intern')
    workspace=PMSWorkspace(organization_id=1,name='Feed workspace');db.add(workspace);db.flush()
    project.workspace_id=workspace.id
    db.add(PMSWorkspaceMember(workspace_id=workspace.id,user_id=viewer.id,role=role))
    task.assignee_user_id=viewer.id;db.commit()
    try:scoped_task(db,task.id,viewer);expected={task.id}
    except HTTPException:expected=set()
    assert {r.id for r in visible_task_query(db,viewer)}==expected


def test_cursor_contract_over_http_keeps_branch_scoping(client,db):
    actor,headers,company,other,project,task,entry=seeded(db)
    url='/api/v1/record-360/work/queue/items'
    response=client.get(url,params={'view':'all','per_page':1,'cursor_mode':True},headers=headers)
    assert response.status_code==200,response.text
    first=response.json();assert first['next_cursor'] and first['total'] is None
    response=client.get(url,params={'view':'all','per_page':1,'cursor_mode':True,'cursor':first['next_cursor']},headers=headers)
    assert response.status_code==200,response.text
    assert response.json()['items'][0]['id']!=first['items'][0]['id']


def test_mixed_calendar_timed_and_unscheduled_work_pages_without_gaps(db):
    from app.apps.crm.models import CRMTask
    from app.shared.follow_ups import FollowUp
    actor,_,company,_,project,task,entry=seeded(db)
    midnight=datetime(2026,11,4,tzinfo=timezone.utc)
    task.due_date=date(2026,11,4);entry.follow_up_date=task.due_date
    db.add_all([CRMTask(organization_id=1,company_id=company.id,title='Timed at midnight',due_date=midnight),CRMTask(organization_id=1,company_id=company.id,title='Unscheduled'),FollowUp(organization_id=1,customer_id=company.id,title='Service at midnight',assigned_user_id=actor.id,created_by=actor.id,due_at=midnight,timezone='Asia/Kolkata')]);db.commit()
    from app.shared.record_360 import record_work
    result=record_work('company',company.id,'crm',1,1,db,actor,cursor_mode=True)
    seen=[i['id'] for i in result['items']]
    while result['next_cursor']:
        result=record_work('company',company.id,'crm',1,1,db,actor,cursor=result['next_cursor'],cursor_mode=True)
        seen.extend(i['id'] for i in result['items'])
        assert len(seen)<=5
    assert len(seen)==len(set(seen))==5


def test_intern_team_responsibility_and_membership_revocation_match_native(db):
    from app.apps.project_management.models import PMSWorkspaceTeam, PMSWorkspaceTeamMember, PMSTaskGroupTarget
    actor,_,company,_,project,task,entry=seeded(db)
    intern,_=account(db,'feed-team-intern@test.com');assign_company(db,intern,1);intern.role=Role(name='intern')
    workspace=PMSWorkspace(organization_id=1,name='Team access');db.add(workspace);db.flush();project.workspace_id=workspace.id
    member=PMSWorkspaceMember(workspace_id=workspace.id,user_id=intern.id,role='Member');db.add(member)
    team=PMSWorkspaceTeam(workspace_id=workspace.id,name='Delivery team',alias='delivery');db.add(team);db.flush()
    db.add(PMSWorkspaceTeamMember(team_id=team.id,user_id=intern.id))
    db.add(PMSTaskGroupTarget(task_id=task.id,kind='teams',target_id=team.id,name=team.name,member_count=1));db.commit()
    assert scoped_task(db,task.id,intern)[0].id==task.id
    assert {r.id for r in visible_task_query(db,intern)}=={task.id}
    db.delete(member);db.commit()
    with pytest.raises(HTTPException):scoped_task(db,task.id,intern)
    assert visible_task_query(db,intern).count()==0
