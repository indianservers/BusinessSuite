import uuid
from app.shared.models import ServiceEvent, ServicePolicy
from app.apps.project_management.models import PMSTask, PMSBoardColumn
from tests.test_pipeline_configuration import company, setup_branch
from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import middleware_database

BASE = "/api/v1/pipeline-workspaces"
PMS = "/api/v1/project-management"


def task(client, headers, project, name="Pipeline work", status="To Do"):
    result = client.post(f"{PMS}/projects/{project['id']}/tasks", headers=headers, json={"title":name,"task_key":"PW-"+uuid.uuid4().hex[:8],"status":status})
    assert result.status_code == 200, result.text
    return result.json()


def test_personal_preferences_team_views_and_tenant_scope(client, db, company):
    headers, _, project = company
    scope = f"project:{project['id']}"
    url = f"{BASE}/project_management/{scope}"
    response = client.get(url+"/views",headers=headers[0])
    assert response.status_code == 200, response.text
    assert response.json()["can_share"]
    prefs = {"density":"comfortable","queue":"attention","fields":["subtitle","age"],"sort":"age"}
    assert client.put(url+"/preferences",headers=headers[0],json=prefs).status_code == 200
    saved = client.post(url+"/views",headers=headers[0],json={"name":"Team attention","shared":True,"preferences":prefs})
    assert saved.status_code == 201, saved.text
    loaded = client.get(url+"/views",headers=headers[0]).json()
    assert loaded["preferences"]["density"] == "comfortable"
    assert loaded["views"][0]["shared"] is True
    assert client.get(url+"/views",headers=headers[2]).status_code in (403,404)
    assert client.post(url+"/views",headers=headers[0],json={"name":"Team attention","shared":True,"preferences":prefs}).status_code == 409
    assert db.query(ServicePolicy).filter_by(kind="pipeline_ui").count() == 2


def test_named_project_board_projects_tasks_without_reassigning_storage(client, db, company):
    headers, _, project = company
    work = task(client,headers[0],project)
    original = work["column_id"]
    result = client.post(f"{PMS}/projects/{project['id']}/boards",headers=headers[0],json={"name":"Customer support","template":"support"})
    assert result.status_code == 201, result.text
    board_id = result.json()["id"]
    result = client.get(f"{PMS}/projects/{project['id']}/board",headers=headers[0],params={"board_id":board_id})
    assert result.status_code == 200, result.text
    queued = next(c for c in result.json()["columns"] if c["status_key"]=="TODO")
    assert queued["name"] == "Queued" and queued["tasks"][0]["id"] == work["id"]
    assert queued["tasks"][0]["column_id"] == queued["id"]
    db.expire_all()
    assert db.get(PMSTask,work["id"]).column_id == original
    assert client.get(f"{PMS}/projects/{project['id']}/board",headers=headers[2],params={"board_id":board_id}).status_code in (403,404)


def test_capacity_is_enforced_for_create_and_move_with_transactional_history(client, db, company):
    headers, _, project = company
    db.commit()
    db.join_transaction_mode="create_savepoint"
    first = task(client,headers[0],project)
    board = client.get(f"{PMS}/projects/{project['id']}/board",headers=headers[0]).json()
    column = db.query(PMSBoardColumn).filter_by(board_id=board["id"],status_key="TODO").one()
    column.wip_limit=1;db.commit()
    response=client.post(f"{PMS}/projects/{project['id']}/tasks",headers=headers[0],json={"title":"Over capacity","task_key":"CAPACITY-REJECTED","status":"To Do"})
    assert response.status_code == 409,response.text
    other=task(client,headers[0],project,"Other work","In Progress")
    version=client.get(f"{PMS}/task-studio/tasks/{other['id']}",headers=headers[0]).json()["version"]
    count=db.query(ServiceEvent).filter_by(event_type="pipeline.stage_entered").count()
    move=client.post(f"{PMS}/my-work/tasks/{other['id']}/arrange",headers=headers[0],json={"group_by":"status","status":"To Do","version":version})
    assert move.status_code == 409,move.text
    assert db.query(ServiceEvent).filter_by(event_type="pipeline.stage_entered").count()==count
    history=client.get(f"{BASE}/project_management/records/task/{first['id']}/history",headers=headers[0])
    assert history.status_code==200,history.text
    assert history.json()["items"][0]["stage"]=="To Do"
    ages=client.get(f"{BASE}/project_management/ages",headers=headers[0],params={"kind":"task","ids":str(first['id'])})
    assert ages.status_code==200,ages.text
    assert ages.json()["items"][str(first['id'])]["days"]==0


def test_job_pipeline_quick_add_requirements_and_capacity(client, db, company):
    headers, _, _ = company
    branch_id=int(headers[0]["X-Suite-Branch"])
    job=client.post("/api/v1/recruitment/jobs",headers=headers[0],json={"title":"Pipeline engineer","branch_id":branch_id})
    assert job.status_code==201,job.text
    job_id=job.json()["id"]
    from app.models.recruitment import Candidate
    db.add(Candidate(job_id=job_id,first_name="Legacy",last_name="Offer",email="legacy-offer@example.com",status="Offered"));db.commit()
    url=f"{BASE}/hrms/jobs/{job_id}"
    config=client.get(url+"/configuration",headers=headers[0])
    assert config.status_code==200,config.text
    draft=config.json()
    assert "Offer" in [stage["name"] for stage in draft["stages"]]
    assert "Offered" not in [stage["name"] for stage in draft["stages"]]
    draft["expected_version"]=draft.pop("version")
    draft["stages"].append({"id":"new:1","name":"Technical review","wip_limit":1,"required":["phone"]})
    result=client.put(url+"/configuration",headers=headers[0],json=draft)
    assert result.status_code==200,result.text
    person={"first_name":"Pipeline","last_name":"Candidate","email":"pipeline-candidate@example.com","stage":"Technical review"}
    assert client.post(url+"/candidates",headers=headers[0],json=person).status_code==422
    result=client.post(url+"/candidates",headers=headers[0],json={**person,"phone":"9876543210","phone_country_code":"+91"})
    assert result.status_code==201,result.text
    second=client.post(url+"/candidates",headers=headers[0],json={**person,"email":"second@example.com","phone":"9876543211","phone_country_code":"+91"})
    assert second.status_code==409,second.text
    assert client.put(url+"/configuration",headers=headers[0],json=draft).status_code==409
    assert client.get(url+"/configuration",headers=headers[2]).status_code in (403,404)


def test_sales_operational_pipeline_cannot_change_financial_status(client, db, company):
    from tests.srm_test_utils import seed_invoice_parties, create_sales_order
    from app.apps.srm.models import SRMSalesOrder
    headers, _, _ = company
    seed_invoice_parties(db)
    order=create_sales_order(client,headers[0],"Pipeline order")
    result=client.post(BASE+"/srm/pipelines",headers=headers[0],json={"name":"Delivery operations","stages":[{"id":"new:1","name":"Intake","wip_limit":1},{"id":"new:2","name":"Dispatch","required_statuses":["confirmed"]}]})
    assert result.status_code==201,result.text
    definition=result.json(); intake,dispatch=definition["stages"]
    url=f"{BASE}/srm/orders/{order['id']}/position"
    denied=client.post(url,headers=headers[0],json={"pipeline_id":definition["id"],"stage_id":dispatch["id"]})
    assert denied.status_code==409,denied.text
    moved=client.post(url,headers=headers[0],json={"pipeline_id":definition["id"],"stage_id":intake["id"]})
    assert moved.status_code==200,moved.text
    assert client.post(url,headers=headers[0],json={"pipeline_id":definition["id"],"stage_id":dispatch["id"]}).status_code==409
    positions=client.get(BASE+"/srm/positions",headers=headers[0],params={"ids":str(order["id"])})
    assert positions.status_code==200,positions.text
    assert positions.json()["items"][str(order["id"])]["stage"]==intake["id"]
    again=client.post(url,headers=headers[0],json={"pipeline_id":definition["id"],"stage_id":intake["id"],"expected_event_id":moved.json()["event_id"]})
    assert again.status_code==200 and again.json()["event_id"]==moved.json()["event_id"]
    db.expire_all()
    assert db.get(SRMSalesOrder,order["id"]).status=="draft"
    second=create_sales_order(client,headers[0],"Other pipeline order")
    full=client.post(f"{BASE}/srm/orders/{second['id']}/position",headers=headers[0],json={"pipeline_id":definition["id"],"stage_id":intake["id"]})
    assert full.status_code==409,full.text
    assert client.get(BASE+"/srm/positions",headers=headers[2],params={"ids":str(order["id"])}).status_code in (403,404)


def test_hiring_interview_and_offer_prerequisites_are_enforced(client, db, company):
    headers, _, _ = company
    job=client.post("/api/v1/recruitment/jobs",headers=headers[0],json={"title":"Gated hiring","branch_id":int(headers[0]["X-Suite-Branch"])})
    assert job.status_code==201,job.text
    url=f"{BASE}/hrms/jobs/{job.json()['id']}"
    draft=client.get(url+"/configuration",headers=headers[0]).json()
    draft["expected_version"]=draft.pop("version")
    for stage in draft["stages"]:
        if stage["name"]=="Offer":stage["require_interview"]=True
        if stage["name"]=="Hired":stage["require_offer"]=True
    assert client.put(url+"/configuration",headers=headers[0],json=draft).status_code==200
    candidate=client.post(url+"/candidates",headers=headers[0],json={"first_name":"Test","last_name":"Candidate","email":"gated-candidate@example.com"})
    assert candidate.status_code==201,candidate.text
    ident=candidate.json()["id"]
    for destination in ("Offer","Hired"):
        response=client.put(f"/api/v1/recruitment/candidates/{ident}/status",headers=headers[0],params={"status":destination})
        assert response.status_code==409,response.text
    from app.models.recruitment import Candidate
    db.expire_all()
    assert db.get(Candidate,ident).status=="Applied"
