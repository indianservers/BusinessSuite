import json
import pytest
from app.core.security import create_access_token
from app.models.user import User
from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember, PMSTask, PMSProject, PMSCustomFieldValue, PMSProjectCustomFieldValue
from tests.tenant_test_utils import assign_company
from tests.test_pms_workspaces import middleware_database
BASE="/api/v1/project-management"

@pytest.fixture
def company(db,client):
 users=[User(email=f"column{i}@test.com",hashed_password="unused",is_superuser=i in (0,2),is_active=True) for i in range(3)]
 db.add_all(users);db.flush()
 for i,u in enumerate(users):assign_company(db,u,2 if i==2 else 1)
 w=PMSWorkspace(name="Columns",organization_id=1);db.add(w);db.flush()
 db.add_all([PMSWorkspaceMember(workspace_id=w.id,user_id=u.id,role="Owner" if i==0 else "Member") for i,u in enumerate(users[:2])]);db.commit()
 h=[{"Authorization":"Bearer "+create_access_token(str(u.id))} for u in users]
 r=client.post(BASE+"/projects",headers=h[0],json={"name":"Audit","project_key":"COL","workspace_id":w.id});assert r.status_code==200,r.text
 return h,w,r.json()

def field(client,h,**extra):
 r=client.post(BASE+"/custom-fields",headers=h,json={"name":"Financial Year","field_type":"dropdown","options":["2025-26","2026-27"],"entity_type":"both",**extra});assert r.status_code==201,r.text
 return r.json()

def test_shared_columns_native_create_update_batch_and_archive(client,db,company):
 h,w,p=company;f=field(client,h[0]);fid=f["id"]
 r=client.post(BASE+"/projects",headers=h[0],json={"name":"Tax","project_key":"TAX","workspace_id":w.id,"custom_fields":{str(fid):"2026-27"}});assert r.status_code==200,r.text
 second=r.json()
 r=client.post(BASE+f"/projects/{p['id']}/tasks",headers=h[0],json={"task_key":"AUTO","title":"Annual audit","custom_fields":{str(fid):{"value":"2025-26"}}});assert r.status_code==200,r.text
 task=r.json()
 def values(entity,ids,actor=0):
  r=client.post(BASE+"/custom-fields/records",headers=h[actor],json={"entity":entity,"ids":ids});assert r.status_code==200,r.text;return r.json()["records"]
 assert values("task",[task["id"]])[str(task["id"])]["fields"][0]["value"]=="2025-26"
 assert values("project",[second["id"]])[str(second["id"])]["fields"][0]["value"]=="2026-27"
 r=client.patch(BASE+f"/tasks/{task['id']}",headers=h[0],json={"custom_fields":{str(fid):"2026-27"}});assert r.status_code==200,r.text
 r=client.put(BASE+f"/custom-fields/{fid}",headers=h[0],json={"name":"Assessment period","options":["2025-26","2026-27","2027-28"]});assert r.status_code==200,r.text
 assert values("task",[task["id"]])[str(task["id"])]["fields"][0]["name"]=="Assessment period"
 r=client.put(BASE+f"/custom-fields/{fid}",headers=h[0],json={"name":"Assessment period","options":["2025-26"],"archived":True});assert r.status_code==409,r.text
 for archive in (True,False):
  r=client.put(BASE+f"/custom-fields/{fid}",headers=h[0],json={"name":"Assessment period","options":["2025-26","2026-27"],"archived":archive});assert r.status_code==200,r.text
  fields=values("task",[task["id"]])[str(task["id"])]["fields"]
  assert (not fields) if archive else fields[0]["value"]=="2026-27"
 assert db.query(PMSCustomFieldValue).filter_by(field_id=fid).count()==1
 assert db.query(PMSProjectCustomFieldValue).filter_by(field_id=fid).count()==1

def test_scope_permissions_and_atomic_invalid_values(client,db,company):
 h,w,p=company;f=field(client,h[0]);fid=str(f["id"])
 assert client.post(BASE+"/custom-fields",headers=h[1],json={"name":"Hidden","field_type":"text"}).status_code==403
 assert client.get(BASE+"/custom-fields",headers=h[2]).json()["fields"]==[]
 assert client.put(BASE+f"/custom-fields/{fid}",headers=h[2],json={"name":"Stolen","options":["2025-26"]}).status_code in (403,404)
 assert client.post(BASE+"/custom-fields/records",headers=h[2],json={"entity":"project","ids":[p["id"]]}).status_code in (403,404)
 count=db.query(PMSTask).count()
 for invalid in ["bad",True,{},["2025-26"]]:
  r=client.post(BASE+f"/projects/{p['id']}/tasks",headers=h[0],json={"task_key":"AUTO","title":"Invalid","custom_fields":{fid:invalid}});assert r.status_code==422,r.text
  assert db.query(PMSTask).count()==count
 r=client.post(BASE+"/projects",headers=h[0],json={"name":"Invalid project","project_key":"BAD","workspace_id":w.id,"custom_fields":{fid:"wrong"}});assert r.status_code==422,r.text
 assert db.query(PMSProject).filter_by(project_key="BAD").count()==0
 local=field(client,h[0],name="Project code",field_type="text",options=[],scope="project",project_id=p["id"],entity_type="project")
 r=client.post(BASE+f"/projects/{p['id']}/tasks",headers=h[0],json={"task_key":"AUTO","title":"Wrong target","custom_fields":{str(local["id"]):"x"}});assert r.status_code==422,r.text

def test_typed_values_and_legacy_fields(client,db,company):
 h,w,p=company
 r=client.post(BASE+f"/projects/{p['id']}/custom-fields",headers=h[0],json={"name":"Legacy","field_type":"text"});assert r.status_code==201,r.text
 legacy=r.json()
 r=client.post(BASE+f"/projects/{p['id']}/tasks",headers=h[0],json={"task_key":"AUTO","title":"Typed task"});assert r.status_code==200,r.text
 task=r.json()
 for name,kind,value,invalid in [("Hours","number",0,True),("Approved","checkbox",False,"false"),("Rating","rating",5,5.1),("Progress","progress",100,101),("Date","date","2026-10-27","2026-02-30")]:
  f=field(client,h[0],name=name,field_type=kind,options=[],entity_type="task")
  path=BASE+f"/tasks/{task['id']}/custom-fields/{f['id']}"
  r=client.put(path,headers=h[0],json={"value":value});assert r.status_code==200,r.text
  assert client.put(path,headers=h[0],json={"value":invalid}).status_code==422
 r=client.put(BASE+f"/tasks/{task['id']}/custom-fields/{legacy['id']}",headers=h[0],json={"value":"preserved"});assert r.status_code==200,r.text
 data=client.get(BASE+f"/tasks/{task['id']}/custom-fields",headers=h[0]).json()["fields"]
 assert next(f for f in data if f["name"]=="Hours")["value"]==0
 assert next(f for f in data if f["name"]=="Approved")["value"] is False
 assert next(f for f in data if f["name"]=="Legacy")["value"]=="preserved"


def test_project_clone_and_recurrence_preserve_custom_columns(client,db,company):
 h,w,p=company;shared=field(client,h[0]);local=field(client,h[0],name="Client reference",field_type="text",options=[],scope="project",project_id=p["id"])
 values={str(shared["id"]):"2026-27",str(local["id"]):"AUD-42"}
 r=client.patch(BASE+f"/projects/{p['id']}",headers=h[0],json={"custom_fields":{str(shared["id"]):"2025-26"}});assert r.status_code==200,r.text
 r=client.post(BASE+f"/projects/{p['id']}/tasks",headers=h[0],json={"title":"Repeat audit","task_key":"REPEAT","due_date":"2026-10-31","recurrence_rule":"monthly","recurrence_interval":1,"custom_fields":values});assert r.status_code==200,r.text
 task=r.json()
 r=client.patch(BASE+f"/tasks/{task['id']}",headers=h[0],json={"status":"Done"});assert r.status_code==200,r.text
 following=db.query(PMSTask).filter_by(task_key=f"REPEAT-{task['id']}").one()
 assert db.query(PMSCustomFieldValue).filter_by(task_id=following.id).count()==2
 r=client.post(BASE+f"/projects/{p['id']}/clone",headers=h[0],json={"name":"Audit copy","project_key":"COPY"});assert r.status_code==201,r.text
 clone=r.json();cloned_task=db.query(PMSTask).filter_by(project_id=clone["id"],title="Repeat audit").order_by(PMSTask.id).first()
 fields=client.get(BASE+f"/tasks/{cloned_task.id}/custom-fields",headers=h[0]).json()["fields"]
 assert {f["name"]:f["value"] for f in fields}=={"Financial Year":"2026-27","Client reference":"AUD-42"}
 copied_local=next(f for f in fields if f["name"]=="Client reference");assert copied_local["id"]!=local["id"] and copied_local["project_id"]==clone["id"]
 fields=client.get(BASE+f"/projects/{clone['id']}/field-values",headers=h[0]).json()["fields"]
 assert fields[0]["value"]=="2025-26"
