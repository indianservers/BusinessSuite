from datetime import datetime,timedelta,timezone,date
from tests.rich_text_test_utils import organization_context
from tests.test_crm_lead_management import create
from tests.test_crm_lead_assignment import employee_account
from app.apps.crm.models import CRMLead,CRMDeal,CRMActivity,CRMTask,CRMQuotation,CRMPipeline,CRMPipelineStage,CRMTimelineEvent
from app.apps.crm.lead_models import CRMLeadOperatingState
from app.models.user import User
from app.core.security import create_access_token
ROOT="/api/v1/crm/productivity"


def deal(db,owner):
    pipeline=CRMPipeline(organization_id=1,name="Sales");db.add(pipeline);db.flush()
    stage=CRMPipelineStage(organization_id=1,pipeline_id=pipeline.id,name="Qualify");db.add(stage);db.flush()
    d=CRMDeal(organization_id=1,owner_user_id=owner,name="Stale opportunity",pipeline_id=pipeline.id,stage_id=stage.id,amount=2500,currency="USD",created_at=datetime.now(timezone.utc)-timedelta(days=20),updated_at=datetime.now(timezone.utc)-timedelta(days=15))
    db.add(d);db.commit();return d


def test_contact_next_home_and_exception_reasons(client,db,superuser_headers):
    owner=db.query(User).filter_by(email="testadmin@test.com").one()
    lead=create(client,superuser_headers,full_name="Promised call",email="promise@example.com")
    row=db.get(CRMLead,lead["id"]);row.next_follow_up_at=datetime.now(timezone.utc)-timedelta(days=2)
    unassigned=create(client,superuser_headers,full_name="Unassigned enquiry",source="Website")
    db.get(CRMLead,unassigned["id"]).owner_user_id=None
    archived=create(client,superuser_headers,full_name="Archived",email="archived@example.com")
    state=db.query(CRMLeadOperatingState).filter_by(lead_id=archived["id"]).one();state.data_json={**state.data_json,"archived":True}
    opportunity=deal(db,owner.id)
    db.add(CRMQuotation(organization_id=1,owner_user_id=owner.id,quote_number="EXPIRED-1",issue_date=date.today()-timedelta(days=10),expiry_date=date.today()-timedelta(days=1),status="Sent"));db.commit()
    result=client.get(ROOT+"/home",headers=superuser_headers,params={"scope":"all"})
    assert result.status_code==200,result.text
    data=result.json();assert data["next_contacts"][0]["id"]==lead["id"]
    assert "overdue" in data["next_contacts"][0]["why"][0]
    assert data["buckets"]["overdue"]==1
    assert all(l["id"]!=archived["id"] for l in data["leads"])
    assert {e["issue"] for e in data["exceptions"]}>={"Unassigned lead","Missing next action","Overdue quotation"}
    assert data["deals"][0]["currency"]=="USD" and data["deals"][0]["stage_age_days"]>=19


def test_duplicate_warning_normalized_and_scope_safe(client,db,superuser_headers):
    lead=create(client,superuser_headers,full_name="Existing",email="duplicate@example.com",phone="9876543210",phone_country_code="+91")
    response=client.get(ROOT+"/duplicate-check",headers=superuser_headers,params={"email":"DUPLICATE@example.com"})
    assert response.status_code==200,response.text
    assert response.json()["matched"] and response.json()["items"][0]["id"]==lead["id"]
    phone=client.get(ROOT+"/duplicate-check",headers=superuser_headers,params={"phone":"98765 43210","phone_country_code":"+91"})
    assert phone.json()["matched"]
    person,_=employee_account(db,"search-scope",permissions=("crm_leads_view",))
    headers={"Authorization":"Bearer "+create_access_token(str(person.id))}
    warning=client.get(ROOT+"/duplicate-check",headers=headers,params={"email":"duplicate@example.com"})
    assert warning.status_code==200,warning.text
    assert warning.json()["matched"] and warning.json()["items"]==[]
    search=client.get(ROOT+"/search",headers=headers,params={"q":"Existing"})
    assert search.status_code==200 and search.json()["items"]==[]


def test_handover_preview_transfers_open_work_with_reason_and_stale_guard(client,db,superuser_headers):
    old,_=employee_account(db,"departing",permissions=("crm_manage",))
    new,_=employee_account(db,"replacement",permissions=("crm_manage",))
    lead=create(client,superuser_headers,full_name="Departing sales work",owner_user_id=old.id)
    d=deal(db,old.id)
    a=CRMActivity(organization_id=1,owner_user_id=old.id,lead_id=lead["id"],activity_type="call",subject="Promised follow-up",status="Pending")
    task=CRMTask(organization_id=1,owner_user_id=old.id,deal_id=d.id,title="Prepare proposal",status="To Do")
    db.add_all([a,task]);db.commit()
    payload={"from_user_id":old.id,"to_user_id":new.id,"reason":"Salesperson departure; preserve commitments"}
    preview=client.post(ROOT+"/handover/preview",headers=superuser_headers,json=payload)
    assert preview.status_code==200,preview.text
    assert preview.json()["counts"]=={"leads":1,"deals":1,"activities":1,"tasks":1}
    assert client.post(ROOT+"/handover/apply",headers=superuser_headers,json={**payload,"preview_version":"stale"}).status_code==409
    apply=client.post(ROOT+"/handover/apply",headers=superuser_headers,json={**payload,"preview_version":preview.json()["version"]})
    assert apply.status_code==200,apply.text
    db.expire_all()
    assert db.get(CRMLead,lead["id"]).owner_user_id==new.id
    assert db.get(CRMDeal,d.id).owner_user_id==new.id
    assert db.get(CRMActivity,a.id).owner_user_id==new.id
    assert db.get(CRMTask,task.id).owner_user_id==new.id
    history=db.query(CRMTimelineEvent).filter_by(record_type="lead",record_id=lead["id"],event_type="assignment").order_by(CRMTimelineEvent.id.desc()).first()
    assert history.metadata_json["reason"]==payload["reason"]


def test_interaction_requires_next_step_and_keeps_previous_commitment(client,db,superuser_headers):
    owner=db.query(User).filter_by(email="testadmin@test.com").one()
    lead=create(client,superuser_headers,email="outcome@example.com")
    at=datetime.now(timezone.utc);item=CRMActivity(organization_id=1,owner_user_id=owner.id,lead_id=lead["id"],activity_type="call",subject="Old promise",due_date=at+timedelta(days=1),status="Pending")
    db.add(item);db.commit()
    base={"entity":"leads","record_id":lead["id"],"channel":"call","outcome":"Callback Requested","timezone":"Asia/Kolkata"}
    assert client.post(ROOT+"/interaction",headers=superuser_headers,json=base).status_code==422
    moved=client.post(ROOT+f"/activities/{item.id}/reschedule",headers=superuser_headers,json={"due_at":(at+timedelta(days=3)).isoformat(),"reason":"Customer requested a later call"})
    assert moved.status_code==200,moved.text
    db.refresh(item);assert item.metadata_json["commitmentHistory"][0]["reason"]
    saved=client.post(ROOT+"/interaction",headers=superuser_headers,json={**base,"next_follow_up":(at+timedelta(days=4)).isoformat(),"complete_activity_id":item.id})
    assert saved.status_code==200,saved.text
    db.refresh(item);assert item.status=="Completed"
    state=db.query(CRMLeadOperatingState).filter_by(lead_id=lead["id"]).one()
    assert state.data_json["customerTimezone"]=="Asia/Kolkata"


def test_stage_preview_corrections_loss_reason_and_reactivation(client,db,superuser_headers):
    owner=db.query(User).filter_by(email="testadmin@test.com").one();d=deal(db,owner.id)
    lost=CRMPipelineStage(organization_id=1,pipeline_id=d.pipeline_id,name="Lost",stage_type="lost",is_lost=True);db.add(lost);db.commit()
    plan=client.get(ROOT+f"/deals/{d.id}/stages",headers=superuser_headers)
    assert plan.status_code==200,plan.text
    assert "lost_reason" in next(s for s in plan.json()["stages"] if s["id"]==lost.id)["missing"]
    payload={"stage_id":lost.id,"lost_reason":"no"}
    assert client.post(ROOT+f"/deals/{d.id}/transition",headers=superuser_headers,json=payload).status_code==422
    saved=client.post(ROOT+f"/deals/{d.id}/transition",headers=superuser_headers,json={**payload,"lost_reason":"Customer deferred the budget","reactivate_at":(datetime.now(timezone.utc)+timedelta(days=90)).isoformat()})
    assert saved.status_code==200,saved.text
    db.refresh(d);assert d.status=="Lost" and d.lost_reason=="Customer deferred the budget"
    assert db.query(CRMTask).filter_by(deal_id=d.id,title="Review lost opportunity for reactivation").count()==1


def test_shared_views_and_mapped_import_preserve_duplicate_validation(client,db,superuser_headers):
    shared=client.post(ROOT+"/shared-views",headers=superuser_headers,json={"name":"Team overdue","queue":"overdue","view":"table"})
    assert shared.status_code==200,shared.text
    assert client.get(ROOT+"/shared-views",headers=superuser_headers).json()["items"][0]["name"]=="Team overdue"
    content=b"Prospect,Email Address,Discard\nNew Person,newperson@example.com,unused\n"
    endpoint="/api/v1/crm/lead-management/excel"
    columns=client.post(endpoint+"/columns",headers=superuser_headers,files={"file":("leads.csv",content,"text/csv")})
    assert columns.status_code==200,columns.text
    import json
    preview=client.post(endpoint+"/preview",headers=superuser_headers,files={"file":("leads.csv",content,"text/csv")},data={"field_mapping":json.dumps({"prospect":"full_name","email_address":"email","discard":""})})
    assert preview.status_code==200,preview.text
    assert preview.json()["ready"]==1 and preview.json()["rows"][0]["full_name"]=="New Person"
    assert "discard" not in preview.json()["rows"][0]


def test_sales_manager_role_alias_allows_scoped_direct_assignment(client,db,superuser_headers):
    from app.models.user import Role
    manager,_=employee_account(db,"manager-alias",permissions=("crm_manage",))
    manager.role.name="crm_sales_manager";db.commit()
    replacement,_=employee_account(db,"assignment-target",permissions=("crm_manage",))
    headers={"Authorization":"Bearer "+create_access_token(str(manager.id))}
    settings=client.get("/api/v1/crm/lead-management/settings",headers=headers)
    assert settings.status_code==200,settings.text
    assert settings.json()["canAssign"]
    lead=create(client,superuser_headers,owner_user_id=manager.id)
    updated=client.patch(f"/api/v1/crm/lead-management/leads/{lead['id']}",headers=headers,json={"values":{"owner_user_id":replacement.id},"details":{"assignmentReason":"Balance current team workload"}})
    assert updated.status_code==200,updated.text
    event=db.query(CRMTimelineEvent).filter_by(record_type="lead",record_id=lead["id"],event_type="assignment").order_by(CRMTimelineEvent.id.desc()).first()
    assert event.metadata_json["reason"]=="Balance current team workload"
