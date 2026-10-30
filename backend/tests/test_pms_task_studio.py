import json
from datetime import date
import pytest
from tests.test_pms_workspaces import BASE, account, middleware_database
from app.apps.project_management.models import PMSWorkspaceMember, PMSWorkspaceTeam, PMSTask, PMSActivity, PMSTaskAssignee
from app.apps.interns_hub.management_models import InternBatch, InternBatchMembership
from app.models.employee import Employee
from app.models.company import Department, Branch, Company

@pytest.fixture
def studio(client, db):
    owner, headers = account(db, "studio-owner@test.com", True)
    member, member_headers = account(db, "studio-member@test.com")
    other, other_headers = account(db, "studio-outsider@test.com")
    wid = client.post(BASE + "/workspaces", json={"name":"Task Studio"}, headers=headers).json()["id"]
    project = client.post(BASE + "/projects", json={"name":"Studio Project","project_key":"STU","workspace_id":wid}, headers=headers).json()
    db.add(PMSWorkspaceMember(workspace_id=wid, user_id=member.id, role="Member"))
    team=PMSWorkspaceTeam(workspace_id=wid, name="Delivery Team", alias="delivery", member_ids_json=json.dumps([owner.id, member.id]))
    db.add(team)
    if not db.get(Company,1): db.add(Company(id=1,name="Studio Company")); db.flush()
    branch=Branch(name="Studio HQ",company_id=1);db.add(branch);db.flush()
    department=Department(name="Studio Department",branch_id=branch.id)
    db.add(department); db.flush()
    employee=Employee(employee_id="STU-INT",first_name="Studio",last_name="Intern",user_id=member.id,employment_type="Intern",department_id=department.id,date_of_joining=date(2026,1,1),status="Active")
    db.add(employee); db.flush()
    batch=InternBatch(organization_id=1,name="Studio Batch",code="STU",department_id=department.id,manager_user_id=owner.id,mentor_user_id=owner.id,project_id=project["id"],start_date=date(2026,1,1),end_date=date(2026,12,31),capacity=10,status="Active")
    db.add(batch); db.flush();db.add(InternBatchMembership(batch_id=batch.id,employee_id=employee.id,assigned_by=owner.id,status="Active"));db.commit()
    return owner, member, other, headers, member_headers, other_headers, project, team, batch


def payload(studio):
    owner, member, other, headers, mh, oh, project, team, batch=studio
    return {"task":{"title":"Design login page","task_key":"stu-001","priority":"High"},"assignment":{"people":[owner.id],"teams":[team.id],"batches":[batch.id],"owner":owner.id,"reviewer":owner.id}}


def test_multiple_people_teams_batches_persist_deduplicate_and_retry(client,db,studio):
    owner, member, _, headers, _, _, project, team, batch=studio
    options=client.get(BASE+"/task-studio/options",params={"project_id":project["id"]},headers=headers)
    assert options.status_code==200, options.text
    assert options.json()["teams"][0]["member_ids"]==sorted([owner.id,member.id])
    assert options.json()["batches"][0]["member_ids"]==[member.id]
    body=payload(studio)
    r=client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks",json=body,headers=headers)
    assert r.status_code==201, r.text
    record=r.json(); tid=record["task"]["id"]
    assert record["task"]["assignee_user_ids"]==sorted([owner.id,member.id])
    assert record["assignment"]["teams"]==[team.id]
    assert record["assignment"]["batches"]==[batch.id]
    assert all(a.reviewer_user_id==owner.id for a in db.query(PMSTaskAssignee).filter_by(task_id=tid))
    retry=client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks",json=body,headers=headers)
    assert retry.status_code==201 and retry.json()["task"]["id"]==tid
    assert db.query(PMSTask).count()==1
    reread=client.get(f"{BASE}/task-studio/tasks/{tid}",headers=headers).json()
    assert reread["assignment"]==record["assignment"]
    updated=client.put(f"{BASE}/task-studio/tasks/{tid}",headers=headers,json={"task":{"title":"Updated login"},"assignment":{"people":[member.id]},"version":record["version"]})
    assert updated.status_code==200, updated.text
    assert updated.json()["task"]["assignee_user_ids"]==[member.id]
    stale=client.put(f"{BASE}/task-studio/tasks/{tid}",headers=headers,json={"task":{"title":"Stale overwrite"},"assignment":{"people":[]},"version":record["version"]})
    assert stale.status_code==409
    assert client.delete(f"{BASE}/tasks/{tid}",headers=headers).status_code==200
    assert client.get(f"{BASE}/task-studio/tasks/{tid}",headers=headers).status_code==404


def test_scoped_groups_inactive_accounts_and_permissions(client,db,studio):
    owner, member, outsider, headers, member_headers, outsider_headers, project, team, batch=studio
    assert client.get(BASE+"/task-studio/options",params={"project_id":project["id"]},headers=outsider_headers).status_code in (403,404)
    body=payload(studio)
    body["assignment"]["people"]=[outsider.id]
    assert client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks",json=body,headers=headers).status_code==422
    body=payload(studio);body["assignment"]["teams"]=[99999]
    assert client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks",json=body,headers=headers).status_code==422
    body=payload(studio);body["assignment"]["reviewer"]=member.id
    assert client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks",json=body,headers=headers).status_code==422
    member.is_active=False;db.commit()
    body=payload(studio)
    result=client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks",json=body,headers=headers)
    assert result.status_code==422, result.text
    assert db.query(PMSTask).count()==0
    body["assignment"]["batches"]=[];body["assignment"]["allow_partial_groups"]=True
    result=client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks",json=body,headers=headers)
    assert result.status_code==201, result.text
    assert result.json()["task"]["assignee_user_ids"]==[owner.id]


def test_source_managed_members_cannot_be_removed(client,db,studio):
    owner, member, _, headers, _, _, project, _, _=studio
    body=payload(studio);body["assignment"]={"people":[member.id]}
    response=client.post(f"{BASE}/task-studio/projects/{project['id']}/tasks",headers=headers,json=body)
    assert response.status_code==201,response.text
    tid=response.json()["task"]["id"]
    assignment=db.query(PMSTaskAssignee).filter_by(task_id=tid,user_id=member.id).one();assignment.source_key="batch:protected";db.commit()
    current=client.get(f"{BASE}/task-studio/tasks/{tid}",headers=headers).json()
    response=client.put(f"{BASE}/task-studio/tasks/{tid}",headers=headers,json={"task":{"title":"Do not drop work"},"assignment":{"people":[]},"version":current["version"]})
    assert response.status_code==409
    assert db.query(PMSTaskAssignee).filter_by(task_id=tid,user_id=member.id).one().source_key=="batch:protected"

    member.is_active = False
    db.commit()
    current=client.get(f"{BASE}/task-studio/tasks/{tid}",headers=headers).json()
    retained=client.put(f"{BASE}/task-studio/tasks/{tid}",headers=headers,json={"task":{"title":"Preserve inactive program member"},"assignment":{"people":[member.id]},"version":current["version"]})
    assert retained.status_code==200,retained.text
    assert retained.json()["task"]["assignee_user_ids"]==[member.id]
