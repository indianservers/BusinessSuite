from tests.rich_text_test_utils import organization_context
from datetime import date, timedelta
from tests.test_pms_workspaces import account, middleware_database, BASE
from tests.test_pms_people_management import project_fixture
from app.apps.project_management.models import PMSTask, PMSChecklistItem, PMSFileAsset, PMSProject, PMSProjectMember

ROOT=BASE+"/management"


def test_management_scope_quick_task_and_execution_guards(client, db):
    owner, oh, target, th, replacement, rh, wid, pid, tid=project_fixture(client, db)
    other, otherh=account(db,"management-outsider@test.com")
    home=client.get(ROOT+"/home",headers=oh)
    assert home.status_code==200,home.text
    assert any(p["id"]==pid and p["can_edit"] for p in home.json()["projects"])
    assert not client.get(ROOT+"/home",headers=otherh).json()["tasks"]
    assert client.patch(ROOT+f"/tasks/{tid}",headers=otherh,json={"priority":"High"}).status_code==403
    quick=client.post(ROOT+"/quick-task",headers=th,json={"project_id":pid,"title":"Title-only task"})
    assert quick.status_code==201,quick.text
    assert quick.json()["assignee_user_ids"]==[target.id]
    assert client.patch(ROOT+f"/tasks/{tid}",headers=oh,json={"status":"Blocked"}).status_code==409
    execution={"revision":0,"blocked_reason":"Waiting for client input","responsible_user_id":target.id,"review_date":str(date.today()+timedelta(days=1)),"evidence_required":True,"evidence":""}
    saved=client.put(ROOT+f"/tasks/{tid}/execution",headers=oh,json=execution)
    assert saved.status_code==200,saved.text
    assert client.put(ROOT+f"/tasks/{tid}/execution",headers=oh,json=execution).status_code==409
    assert client.patch(ROOT+f"/tasks/{tid}",headers=oh,json={"status":"Blocked"}).status_code==200
    assert client.patch(BASE+f"/tasks/{tid}",headers=oh,json={"status":"Done"}).status_code==409
    execution["revision"]=1;execution["evidence"]="https://example.com/delivery"
    assert client.put(ROOT+f"/tasks/{tid}/execution",headers=oh,json=execution).status_code==200
    check=PMSChecklistItem(task_id=tid,title="Required review",is_completed=False);db.add(check);db.commit()
    assert client.patch(ROOT+f"/tasks/{tid}",headers=oh,json={"status":"Done"}).status_code==409
    check.is_completed=True;db.commit()
    assert client.patch(ROOT+f"/tasks/{tid}",headers=oh,json={"status":"Done"}).status_code==200


def test_move_and_clone_choices_preserve_source(client,db):
    owner, oh, target, th, replacement, rh, wid, pid, tid=project_fixture(client, db)
    destination=client.post(BASE+"/projects",headers=oh,json={"name":"Destination","project_key":"DEST","workspace_id":wid}).json()["id"]
    moved=client.patch(ROOT+f"/tasks/{tid}",headers=oh,json={"project_id":destination,"priority":"High"})
    assert moved.status_code==200,moved.text
    assert moved.json()["project_id"]==destination and moved.json()["assignee_user_ids"]==[target.id]
    task=db.get(PMSTask,tid);task.due_date=date.today()+timedelta(days=4)
    db.add(PMSFileAsset(project_id=destination,task_id=tid,file_name="proof.txt",original_name="proof.txt",storage_path="test/proof.txt",uploaded_by_user_id=owner.id))
    db.add(PMSChecklistItem(task_id=tid,title="Evidence review",is_completed=True));db.commit()
    clone=client.post(BASE+f"/projects/{destination}/clone",headers=oh,json={"name":"Duplicated","project_key":"DUP","include_tasks":True,"include_dates":False,"include_team":False,"include_attachments":True})
    assert clone.status_code==201,clone.text
    newtask=db.query(PMSTask).filter_by(project_id=clone.json()["id"]).one()
    assert newtask.due_date is None and newtask.assignee_user_ids==[] and newtask.status=="To Do"
    assert db.query(PMSFileAsset).filter_by(task_id=newtask.id).one().storage_path=="test/proof.txt"
    assert not db.query(PMSChecklistItem).filter_by(task_id=newtask.id).one().is_completed
    assert db.get(PMSTask,tid).due_date is not None
    assert client.patch(ROOT+f"/projects/{destination}",headers=th,json={"owner_user_id":target.id}).status_code==403


def test_dated_capacity_and_assignment_warnings(client,db):
    owner, oh, target, th, replacement, rh, wid, pid, tid=project_fixture(client, db)
    monday=date.today()-timedelta(days=date.today().weekday())
    save=client.put(ROOT+"/capacity",headers=oh,json={"user_id":target.id,"week_start_date":str(monday),"capacity_hours":20})
    assert save.status_code==200,save.text
    capacity=client.get(ROOT+"/capacity",headers=oh,params={"user_id":target.id,"start":str(monday),"end":str(monday+timedelta(days=6))})
    assert capacity.status_code==200,capacity.text
    assert capacity.json()["capacity_hours"]==20
    task=db.get(PMSTask,tid);task.estimated_hours=30;task.due_date=monday+timedelta(days=1);db.commit()
    warnings=client.get(ROOT+"/assignment-warnings",headers=oh,params={"user_id":target.id,"project_id":pid,"on":str(monday+timedelta(days=1))})
    assert warnings.status_code==200,warnings.text
    assert any("exceeds" in w for w in warnings.json()["warnings"])
    assert client.put(ROOT+"/capacity",headers=th,json={"user_id":target.id,"week_start_date":str(monday),"capacity_hours":100}).status_code==403


def test_note_conversion_owner_and_private_backlink(client,db):
    from uuid import uuid4
    owner, oh, target, th, replacement, rh, wid, pid, tid=project_fixture(client, db)
    note=client.post(BASE+"/notes",headers=oh,json={"title":"Private planning","content":"Confidential context"}).json()
    made=client.post(BASE+f"/notes/{note['id']}/tasks",headers=oh,json={"project_id":pid,"title":"Published action","description":"Reviewed public text","assignee_user_id":target.id,"due_date":str(date.today()+timedelta(days=2)),"publish_to_project":True,"request_key":str(uuid4())})
    assert made.status_code==201,made.text
    task_id=made.json()["id"]
    assert db.get(PMSTask,task_id).assignee_user_ids==[target.id]
    own=client.get(ROOT+f"/tasks/{task_id}",headers=oh).json()
    assert own["note_sources"][0]["id"]==note["id"]
    collaborator=client.get(ROOT+f"/tasks/{task_id}",headers=th)
    assert collaborator.status_code==200,collaborator.text
    assert collaborator.json()["note_sources"]==[]


def test_capacity_respects_holidays_and_half_day_approved_leave(client,db):
    from app.models.employee import Employee
    from app.models.leave import LeaveRequest, LeaveType
    from app.models.attendance import Holiday
    owner, oh, target, th, replacement, rh, wid, pid, tid=project_fixture(client, db)
    monday=date.today()-timedelta(days=date.today().weekday())
    employee=Employee(user_id=target.id,employee_id="CAPACITY-EMP",first_name="Capacity",last_name="Person",date_of_joining=date(2026,1,1),status="Active")
    leave_type=LeaveType(name="Capacity test leave",code="CAP",days_allowed=10)
    db.add_all([employee,leave_type]);db.flush()
    db.add(Holiday(name="Team holiday",holiday_date=monday,is_active=True))
    db.add(LeaveRequest(employee_id=employee.id,leave_type_id=leave_type.id,from_date=monday+timedelta(days=1),to_date=monday+timedelta(days=1),days_count=0.5,is_half_day=True,status="Approved"));db.commit()
    result=client.get(ROOT+"/capacity",headers=oh,params={"user_id":target.id,"start":str(monday),"end":str(monday+timedelta(days=6))})
    assert result.status_code==200,result.text
    assert result.json()["capacity_hours"]==28
    assert result.json()["days"][0]["reason"]=="Holiday"
    assert result.json()["days"][1]["hours"]==4


def test_note_visibility_requires_explicit_audience_and_respects_scope(client,db):
    owner, oh, target, th, replacement, rh, wid, pid, tid=project_fixture(client, db)
    outsider,xh=account(db,"visibility-outsider@test.com")
    note=client.post(BASE+"/notes",headers=oh,json={"title":"Team decisions","content":"Reviewed for sharing","project_id":pid}).json()
    assert note["visibility_scope"]=="private"
    assert client.get(BASE+f"/notes/{note['id']}",headers=th).status_code==404

    route=BASE+f"/notes/{note['id']}/visibility"
    assert client.put(route,headers=oh,json={"version":note["version"],"scope":"project"}).status_code==422
    published=client.put(route,headers=oh,json={"version":note["version"],"scope":"project","confirm_audience":True})
    assert published.status_code==200,published.text
    assert client.get(BASE+f"/notes/{note['id']}",headers=th).json()["can_edit"] is False
    assert client.get(BASE+f"/notes/{note['id']}",headers=xh).status_code==404
    shared=client.get(BASE+"/notes",headers=th,params={"view":"shared"}).json()
    assert any(n["id"]==note["id"] for n in shared)
    # Changing a public note's location cannot silently change its audience.
    body={k:note[k] for k in ("title","content","project_id","task_id","folder_id","tags","pinned","favorite","archived")}
    assert client.put(BASE+f"/notes/{note['id']}",headers=oh,json={**body,"version":published.json()["version"],"project_id":None}).status_code==409
    workspace=client.put(route,headers=oh,json={"version":published.json()["version"],"scope":"workspace","confirm_audience":True})
    assert workspace.status_code==200,workspace.text
    assert client.get(BASE+f"/notes/{note['id']}",headers=th).status_code==200
    private=client.put(route,headers=oh,json={"version":workspace.json()["version"],"scope":"private"})
    assert private.status_code==200,private.text
    assert client.get(BASE+f"/notes/{note['id']}",headers=th).status_code==404


def test_legacy_project_manager_can_check_collaborator_availability(client,db):
    manager,mh=account(db,"legacy-manager@test.com")
    member,_=account(db,"legacy-member@test.com")
    project=PMSProject(organization_id=1,name="Legacy delivery",project_key="LEGACY")
    db.add(project);db.flush()
    db.add_all([PMSProjectMember(project_id=project.id,user_id=manager.id,role="Project Manager"),PMSProjectMember(project_id=project.id,user_id=member.id,role="Member")]);db.commit()
    response=client.get(ROOT+"/assignment-warnings",headers=mh,params={"project_id":project.id,"user_id":member.id})
    assert response.status_code==200,response.text
