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


def test_project_capabilities_stay_distinct_for_each_workspace_and_actor(client, db):
    from app.apps.project_management.models import PMSWorkspaceMember
    from test_identity_utils import own_workflow_records
    wid,pid,owner,oh,ah,member,mh,guest,gh=setup_workspace(client,db)
    other=client.post(BASE+"/workspaces",headers=oh,json={"name":"Read-only comparison"}).json()["id"]
    membership=PMSWorkspaceMember(workspace_id=other,user_id=member.id,role="Guest");db.add(membership);own_workflow_records(db,membership);db.commit()
    writable=[pid];readonly=[]
    for target,workspace,key in [(writable,wid,"CAP-A"),(readonly,other,"CAP-B"),(readonly,other,"CAP-C")]:
        response=client.post(BASE+"/projects",headers=oh,json={"name":key,"project_key":key,"workspace_id":workspace});assert response.status_code==200,response.text;target.append(response.json()["id"])
    response=client.get(BASE+"/projects",headers=mh);assert response.status_code==200,response.text
    rows={row["id"]:row for row in response.json()}
    for project in writable:
        assert rows[project]["can_manage_tasks"] and rows[project]["can_log_time"]
        assert not rows[project]["can_edit_project"]
    for project in readonly:
        assert not rows[project]["can_manage_tasks"] and not rows[project]["can_log_time"]
        assert not rows[project]["can_edit_project"]
    response=client.get(BASE+"/projects",headers=oh);assert response.status_code==200,response.text
    assert all(row["can_edit_project"] and row["can_log_time"] for row in response.json() if row["id"] in writable+readonly)
