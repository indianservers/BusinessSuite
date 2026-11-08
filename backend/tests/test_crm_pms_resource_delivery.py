from datetime import date, datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from tests.test_pms_workspaces import middleware_database, BASE
from tests.test_pms_automations import setup_workspace
from tests.test_pms_advanced_scheduling import task
from app.apps.project_management.models import PMSTask, PMSUserCapacity
from app.apps.automation.models import AutomationScheduledJob as Job
from app.apps.project_management import external_queue as external
from app.services import domain_report_delivery as delivery
from app.models.email_outbox import EmailOutbox
import os


@pytest.mark.skipif(os.environ.get("RUN_CRM_PMS_RESOURCE_BROWSER")!="1",reason="Disposable browser integration")
def test_resource_delivery_browser(client,db,monkeypatch):
    from tests.workflow_browser_utils import run_browser
    from tests.test_crm_deal_workspace import create
    wid,pid,owner,oh,_,_,_,_,_=setup_workspace(client,db)
    for key in ("LEVEL-A","LEVEL-B"):
        tid=task(client,pid,oh,key,"2026-11-09","2026-11-09")
        row=db.get(PMSTask,tid);row.assignee_user_id=owner.id;row.estimated_hours=8
    db.commit()
    create(client,db,oh)
    report=client.post("/api/v1/crm/report-builder",headers=oh,json={"name":"UI scheduled sales"})
    assert report.status_code==201,report.text
    monkeypatch.setattr(external.integrations,"destination",lambda u:(None,"8.8.8.8"))
    monkeypatch.setattr(external.integrations,"send",lambda *args: (_ for _ in ()).throw(AssertionError("Browser must never send external events")))
    run_browser(client,db,"test-resource-delivery.cjs",{"WORKFLOW_TEST_TOKEN":oh["Authorization"].split(" ",1)[1],"WORKFLOW_TEST_PROJECT":str(pid),"WORKFLOW_TEST_WORKSPACE":str(wid),"WORKFLOW_TEST_REPORT":str(report.json()["id"])})


def test_resource_leveling_preview_apply_and_staleness(client, db):
    _, pid, owner, oh, _, _, _, _, gh = setup_workspace(client, db)
    a = task(client,pid,oh,"LEVEL-A","2026-11-09","2026-11-09")
    b = task(client,pid,oh,"LEVEL-B","2026-11-09","2026-11-09")
    for tid in (a,b):
        t=db.get(PMSTask,tid);t.assignee_user_id=owner.id;t.estimated_hours=8
    db.commit()
    path=f"{BASE}/projects/{pid}"
    request={"level_resources":True}
    r=client.post(path+"/schedule-preview",headers=oh,json=request)
    assert r.status_code==200,r.text
    p=r.json();assert [t["due_date"] for t in p["tasks"]]==["2026-11-09","2026-11-10"]
    assert not p["critical_task_ids"] and all(t["slack_workdays"] is None for t in p["tasks"])
    assert db.get(PMSTask,b).due_date==date(2026,11,9)
    capacity=PMSUserCapacity(organization_id=1,user_id=owner.id,week_start_date=date(2026,11,9),capacity_hours=20)
    db.add(capacity)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db,capacity);db.commit()
    assert client.post(path+"/schedule-apply",headers=oh,json={**request,"expected_revision":p["revision"]}).status_code==409
    p=client.post(path+"/schedule-preview",headers=oh,json=request).json()
    assert [t["due_date"] for t in p["tasks"]]==["2026-11-10","2026-11-12"]
    assert client.post(path+"/schedule-apply",headers=gh,json={**request,"expected_revision":p["revision"]}).status_code==403
    r=client.post(path+"/schedule-apply",headers=oh,json={**request,"expected_revision":p["revision"]})
    assert r.status_code==200,r.text
    db.expire_all();assert db.get(PMSTask,b).due_date==date(2026,11,12)
    db.get(PMSTask,b).remaining_estimate_hours=0;db.commit()
    assert client.post(path+"/schedule-preview",headers=oh,json=request).status_code==422


def test_leveling_holiday_half_day_leave_and_assignment_change(client,db):
    from app.models.employee import Employee
    from app.models.leave import LeaveRequest, LeaveType
    from app.models.attendance import Holiday
    from test_identity_utils import own_workflow_records
    _,pid,owner,oh,_,member,_,_,_=setup_workspace(client,db)
    tid=task(client,pid,oh,"LEAVE-LEVEL","2026-11-09","2026-11-09")
    row=db.get(PMSTask,tid);row.assignee_user_id=owner.id;row.estimated_hours=8
    employee=Employee(user_id=owner.id,employee_id="LEVEL-EMP",first_name="Level",last_name="Person",date_of_joining=date(2026,1,1),status="Active")
    leave_type=LeaveType(name="Leveling leave",code="LEVEL",days_allowed=10)
    db.add_all([employee,leave_type]);db.flush()
    holiday=Holiday(name="Resource holiday",holiday_date=date(2026,11,9),is_active=True)
    leave=LeaveRequest(employee_id=employee.id,leave_type_id=leave_type.id,from_date=date(2026,11,10),to_date=date(2026,11,10),days_count=0.5,is_half_day=True,status="Approved")
    db.add_all([holiday,leave]);own_workflow_records(db,employee,leave_type,holiday,leave);db.commit()
    path=f"{BASE}/projects/{pid}"
    r=client.post(path+"/schedule-preview",headers=oh,json={"level_resources":True})
    assert r.status_code==200,r.text
    p=r.json();assert p["tasks"][0]["start_date"]=="2026-11-10"
    assert p["tasks"][0]["due_date"]=="2026-11-11"
    assert [a["hours"] for a in p["resource_allocations"]]==[4,4]
    assert "Approved leave" not in str(p["resource_allocations"])
    row.assignee_user_id=member.id;db.commit()
    assert client.post(path+"/schedule-apply",headers=oh,json={"level_resources":True,"expected_revision":p["revision"]}).status_code==409


@pytest.mark.parametrize("kind",["Finish To Start","Start To Start","Finish To Finish","Start To Finish"])
def test_resource_precedence_and_multi_assignee_capacity(kind):
    from types import SimpleNamespace as Obj
    from app.apps.project_management.scheduling import calculate, CalendarSpec, PlanInput
    from app.apps.project_management.resource_leveling import level
    tasks=[Obj(id=1,task_key="A",title="A",start_date=date(2026,11,9),due_date=date(2026,11,9),assignee_user_ids=[1],remaining_estimate_hours=16,estimated_hours=16,actual_hours=0,status="To Do"),Obj(id=2,task_key="B",title="B",start_date=date(2026,11,9),due_date=date(2026,11,9),assignee_user_ids=[1,2],remaining_estimate_hours=16,estimated_hours=16,actual_hours=0,status="To Do")]
    deps=[Obj(depends_on_task_id=1,task_id=2,dependency_type=kind,lag_days=0)]
    capacities={uid:{(date(2026,11,9)+timedelta(days=i)).isoformat():(0 if i==1 else 8) for i in range(366)} for uid in (1,2)}
    cal=CalendarSpec();p=level(tasks,deps,cal,PlanInput(),capacities,calculate(tasks,deps,cal))
    assert p["tasks"][0]["due_date"]=="2026-11-11"
    a,b=p["tasks"]
    if kind=="Finish To Start":assert b["start_date"]>a["due_date"]
    elif kind=="Start To Start":assert b["start_date"]>=a["start_date"]
    elif kind=="Finish To Finish":assert b["due_date"]>=a["due_date"]
    else:assert b["due_date"]>=a["start_date"]
    from collections import defaultdict
    used=defaultdict(float)
    for item in p["resource_allocations"]:used[item["user_id"],item["date"]]+=item["hours"]
    assert all(hours<=capacities[uid][day] for (uid,day),hours in used.items())
    assert sum(a["hours"] for a in p["resource_allocations"] if a["task_id"]==2)==16


def fixture_queue(client,db,monkeypatch):
    wid,pid,owner,oh,_,_,_,_,gh=setup_workspace(client,db)
    monkeypatch.setattr(external.integrations,"destination",lambda u: (None,"8.8.8.8"))
    path=f"{BASE}/workspaces/{wid}"
    conn=client.post(path+"/external-connections",headers=oh,json={"name":"Receiver","url":"https://receiver.example/hook","secret":"test-secret-with-24-characters","receiver_deduplicates_delivery_id":True})
    assert conn.status_code==201,conn.text
    assert "secret" not in conn.json()
    rid=client.post(path+"/automations",headers=oh,json={"name":"Notify receiver","project_id":pid,"trigger":"task.created","action":"webhook","connection_id":conn.json()["id"]})
    assert rid.status_code==201,rid.text
    sent=[]
    monkeypatch.setattr(external.integrations,"send",lambda *args: sent.append(args))
    task(client,pid,oh,"QUEUE-A","2026-11-09","2026-11-09")
    assert sent==[],"Task transaction must not send external calls"
    jobs=db.query(Job).filter_by(job_type="pms_external").all();assert len(jobs)==1
    return path,oh,gh,jobs[0],sent


def test_external_retry_acceptance_and_redaction(client,db,monkeypatch):
    path,oh,gh,job,sent=fixture_queue(client,db,monkeypatch)
    delivery_id=job.payload_json["delivery_id"]
    def reject(*args):
        e=HTTPException(502,"rejected");e.connector_status=503;raise e
    monkeypatch.setattr(external.integrations,"send",reject)
    now=datetime.now(timezone.utc)+timedelta(seconds=2)
    assert external.dispatch(db,now)["processed"]==1
    db.refresh(job);assert job.status=="scheduled" and job.attempts==1,job.last_error
    assert external.dispatch(db,now)["processed"]==0
    monkeypatch.setattr(external.integrations,"send",lambda *args: sent.append(args))
    external.dispatch(db,now+timedelta(minutes=2));db.refresh(job)
    assert job.status=="accepted" and job.attempts==2,job.last_error
    assert sent[0][2]["delivery_id"]==delivery_id
    r=client.get(path+"/external-deliveries",headers=oh)
    assert r.status_code==200 and r.json()[0]["status"]=="accepted",r.text
    assert "secret" not in r.text
    assert client.get(path+"/external-deliveries",headers=gh).status_code==403
    assert client.post(path+f"/external-deliveries/{job.id}/retry",headers=oh).status_code==409


def test_external_timeout_is_never_blindly_retried(client,db,monkeypatch):
    path,oh,_,job,_=fixture_queue(client,db,monkeypatch)
    monkeypatch.setattr(external.integrations,"send",lambda *args: (_ for _ in ()).throw(TimeoutError()))
    now=datetime.now(timezone.utc)+timedelta(seconds=2)
    external.dispatch(db,now);db.refresh(job)
    assert job.status=="reconciliation_required",job.last_error
    assert external.dispatch(db,now+timedelta(days=1))["processed"]==0
    assert client.post(path+f"/external-deliveries/{job.id}/retry",headers=oh).status_code==409


def test_external_dead_letter_retry_cancel(client,db,monkeypatch):
    path,oh,_,job,_=fixture_queue(client,db,monkeypatch)
    def reject(*args):
        e=HTTPException(502,"rejected");e.connector_status=429;raise e
    monkeypatch.setattr(external.integrations,"send",reject)
    now=datetime.now(timezone.utc)
    for i in range(5):external.dispatch(db,now+timedelta(hours=i+1))
    db.refresh(job);assert job.status=="dead_letter" and job.attempts==5,job.last_error
    assert client.post(path+f"/external-deliveries/{job.id}/retry",headers=oh).status_code==200
    assert client.post(path+f"/external-deliveries/{job.id}/cancel",headers=oh).status_code==200
    assert external.dispatch(db,now+timedelta(days=1))["processed"]==0


def test_external_paused_source_is_not_sent_and_credentials_are_encrypted(client,db,monkeypatch):
    from app.apps.project_management.models import PMSWorkspaceEntry
    import json
    path,oh,_,job,sent=fixture_queue(client,db,monkeypatch)
    connection=db.get(PMSWorkspaceEntry,job.payload_json["connection_id"])
    assert "test-secret-with-24-characters" not in connection.body
    rule=job.payload_json["rule_id"]
    assert client.patch(path+f"/automations/{rule}",headers=oh,json={"enabled":False}).status_code==200
    external.dispatch(db,datetime.now(timezone.utc)+timedelta(minutes=1));db.refresh(job)
    assert job.status=="dead_letter" and job.attempts==0 and not sent


@pytest.mark.parametrize("url",["http://example.com/hook","https://127.0.0.1/hook","https://example.com/hook?secret=hidden"])
def test_external_destination_validation(url):
    with pytest.raises(HTTPException) as error: external.integrations.destination(url)
    assert error.value.status_code==422


def test_report_schedule_local_weekly():
    config={"frequency":"weekly","weekday":0,"at":"09:00","timezone":"Asia/Kolkata"}
    assert delivery.next_occurrence(config,datetime(2026,11,8,tzinfo=timezone.utc))==datetime(2026,11,9,3,30,tzinfo=timezone.utc)


def test_pms_report_link_queue_pause_and_revocation(client,db,monkeypatch):
    _,pid,owner,oh,_,_,_,_,_=setup_workspace(client,db)
    task(client,pid,oh,"REPORT-A","2026-11-09","2026-11-09")
    base=f"{BASE}/projects/{pid}"
    rev=client.get(base+"/schedule-analysis",headers=oh).json()["revision"]
    assert client.post(base+"/schedule-baselines",headers=oh,json={"name":"Delivery baseline","expected_revision":rev}).status_code==201
    path=f"{BASE}/report-delivery/pms/{pid}/delivery-schedule"
    config={"enabled":True,"frequency":"daily","at":"09:00","timezone":"Asia/Kolkata","weekday":0}
    r=client.put(path,headers=oh,json=config);assert r.status_code==200,r.text
    job=db.get(Job,r.json()["id"]);now=datetime.now(timezone.utc)+timedelta(days=1)
    assert delivery.dispatch(db,now)["processed"]==1
    db.refresh(job);assert job.status=="scheduled",job.last_error
    outbox=db.query(EmailOutbox).filter(EmailOutbox.event_key.startswith(f"domain-report:{job.id}:")).one()
    assert outbox.status=="queued" and outbox.recipient_user_id==owner.id
    assert "REPORT-A" not in outbox.body and "historical snapshot" in outbox.body
    assert delivery.outbox_allowed(db,outbox)
    from app.services.email_dispatch import _deliver_authorized
    from app.core import email
    sent=[]
    monkeypatch.setattr(email,"send_email",lambda *args: sent.append(args) or "test-provider-id")
    _deliver_authorized(db,outbox)
    assert outbox.status=="accepted" and outbox.provider_message_id=="test-provider-id"
    assert len(sent)==1
    assert delivery.dispatch(db,now)["processed"]==0
    assert client.get(path,headers=oh).json()["delivery_status"]=="accepted"
    assert client.put(path,headers=oh,json={**config,"enabled":False}).status_code==200
    assert not delivery.outbox_allowed(db,outbox)
    _deliver_authorized(db,outbox)
    assert outbox.status=="suppressed" and len(sent)==1
    assert client.put(path,headers=oh,json=config).status_code==200
    owner.is_active=False;db.commit()
    assert not delivery.outbox_allowed(db,outbox)
    delivery.dispatch(db,now+timedelta(days=1));db.refresh(job);assert job.status=="blocked"


def test_crm_private_scheduled_report_workflow(client,db,superuser_headers):
    from tests.test_crm_deal_workspace import create
    create(client,db,superuser_headers)
    report=client.post("/api/v1/crm/report-builder",headers=superuser_headers,json={"name":"Scheduled sales"})
    assert report.status_code==201,report.text
    path=f"/api/v1/crm/report-builder/report-delivery/crm/{report.json()['id']}/delivery-schedule"
    r=client.put(path,headers=superuser_headers,json={"frequency":"weekly","weekday":0})
    assert r.status_code==200,r.text
    job=db.get(Job,r.json()["id"])
    delivery.dispatch(db,datetime.now(timezone.utc)+timedelta(days=8));db.refresh(job)
    assert job.status=="scheduled",job.last_error
    assert client.get(path,headers=superuser_headers).json()["delivery_status"]=="queued"
    client.delete(f"/api/v1/crm/report-builder/{report.json()['id']}",headers=superuser_headers)
    delivery.dispatch(db,datetime.now(timezone.utc)+timedelta(days=16));db.refresh(job)
    assert job.status=="blocked"
