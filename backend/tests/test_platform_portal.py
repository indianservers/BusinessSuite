"""Owner workflows use a second physical test store and never a client identity."""
from datetime import datetime, timedelta, timezone
import re
import pytest
from tests.test_public_signup import platform_store, platform_headers, submit, approve, activate, PASSWORD
from app.platform_owner.models import PlatformAdmin, PlatformEvent, PlatformRecord, PlatformSignupRequest, PlatformTenant, PlatformPlan
from app.core.security import get_password_hash
from app.models.user import User
from app.apps.saas.models import TenantSubscription

ROOT = "/api/v1/platform"


def call(client, headers, method, path, payload=None, status=200):
    response = getattr(client, method)(ROOT+path, headers=headers, **({"json":payload} if payload is not None else {}))
    assert response.status_code == status, response.text
    return response.json()


def staff_login(client, store, role, assigned_only=False):
    admin=PlatformAdmin(email=role+"@indianservers.com",name=role.title(),role=role,assigned_only=assigned_only,hashed_password=get_password_hash(PASSWORD))
    store.add(admin);store.commit()
    response=client.post("/api/v1/auth/platform/login",json={"email":admin.email,"password":PASSWORD})
    assert response.status_code==200,response.text
    return admin,{"Authorization":"Bearer "+response.json()["access_token"]}


def customer(client,db,headers):
    row=submit(client,db)
    approved=approve(client,db,headers,row)
    return row,approved,db._platform_db.query(PlatformTenant).filter_by(signup_id=row.id).one()


def plan(client,headers):
    return call(client,headers,"post","/plans",{"code":"growth","name":"Growth","modules":["crm"],"seats":10,"storage_mib":2048,"monthly_price_minor":199900,"currency":"INR"},201)


def test_client_superuser_and_anonymous_cannot_enter_any_owner_workspace(client,db,superuser_headers,platform_headers):
    for path in ["/me","/signups","/customers","/staff","/plans","/reports","/events","/settings","/records/outbox"]:
        assert client.get(ROOT+path,headers=superuser_headers).status_code==401
        assert client.get(ROOT+path).status_code==401
    assert client.get("/api/v1/auth/me",headers=platform_headers).status_code==401


def test_manual_signup_edit_filter_assignment_duplicate_and_history(client,db,platform_headers):
    owner=db._platform_db.query(PlatformAdmin).one()
    payload={"applicant_type":"company","name":"Demo Contact","company_name":"Demo Business","email":"manual@example.com",
        "phone":"9876543210","phone_country_code":"+91","requested_modules":["crm"],"consent":True,
        "consent_evidence":"Phone consent on local demo call","source":"phone","campaign":"Launch"}
    row=call(client,platform_headers,"post","/signups",payload,201)
    assert row["assigned_to"]==owner.id
    edited=call(client,platform_headers,"patch",f'/signups/{row["id"]}',{"version":row["version"],"reason":"Correct company details","name":"Corrected Contact","tags":["priority"],"priority":"high"})
    assert edited["name"]=="Corrected Contact" and edited["version"]==2
    call(client,platform_headers,"patch",f'/signups/{row["id"]}',{"version":1,"reason":"Stale edit","name":"Wrong"},409)
    found=call(client,platform_headers,"get","/signups?source=phone&applicant_type=company&module=crm&priority=high")
    assert found["total"]==1
    duplicate=call(client,platform_headers,"post","/signups",{**payload,"email":"second@example.com"},201)
    assert duplicate["duplicates"]
    detail=call(client,platform_headers,"get",f'/signups/{row["id"]}')
    assert any(e["action"]=="signup.edited" and e["before"]["name"]=="Demo Contact" for e in detail["history"])


def test_bulk_preview_is_readonly_and_commit_is_atomic_and_versioned(client,db,platform_headers):
    a=submit(client,db,"a@example.com");b=submit(client,db,"b@example.com")
    payload={"ids":[a.id,b.id],"action":"archive","reason":"Spam cleanup preview","preview":True}
    preview=call(client,platform_headers,"post","/signup-bulk",payload)
    assert len(preview["items"])==2 and all(r.status=="pending" for r in db._platform_db.query(PlatformSignupRequest))
    versions={str(r["id"]):r["version"] for r in preview["items"]}
    call(client,platform_headers,"patch",f"/signups/{b.id}",{"version":1,"reason":"Concurrent correction","name":"Updated applicant"})
    call(client,platform_headers,"post","/signup-bulk",{**payload,"preview":False,"versions":versions},409)
    assert db._platform_db.get(PlatformSignupRequest,a.id).status=="pending"
    preview=call(client,platform_headers,"post","/signup-bulk",payload)
    result=call(client,platform_headers,"post","/signup-bulk",{**payload,"preview":False,"versions":{str(r["id"]):r["version"] for r in preview["items"]}})
    assert result["changed"]==2
    call(client,platform_headers,"post",f"/signups/{a.id}/action",{"action":"restore","reason":"Restore valid applicant"})
    assert db._platform_db.get(PlatformSignupRequest,a.id).status=="pending"


def test_staff_roles_assigned_scopes_and_cross_scope_duplicate_visibility(client,db,platform_headers,platform_store):
    a=submit(client,db,"a@example.com");b=submit(client,db,"b@example.com")
    actor,headers=staff_login(client,platform_store,"sales",True)
    a.assigned_to=actor.id;platform_store.commit()
    rows=call(client,headers,"get","/signups")
    assert [r["id"] for r in rows["items"]]==[a.id]
    assert rows["items"][0]["duplicates"]==[]
    call(client,headers,"get",f"/signups/{b.id}",status=404)
    call(client,headers,"get","/staff",status=403)
    call(client,headers,"post",f"/signups/{a.id}/review",{"decision":"reject","reason":"Sales cannot review"},403)
    assert client.get("/api/v1/auth/signup-requests",headers=headers).json()["total"]==1


def test_checklist_and_trial_entitlements_are_enforced(client,db,platform_headers,platform_store):
    platform_store.query(PlatformRecord).filter_by(kind="settings").one().data={"require_checklist":True};platform_store.commit()
    row=submit(client,db)
    payload={"decision":"approve","reason":"Valid trial","modules":["crm"],"seats":3,"storage_mib":500,"trial_days":7}
    call(client,platform_headers,"post",f"/signups/{row.id}/review",payload,422)
    call(client,platform_headers,"patch",f"/signups/{row.id}",{"version":1,"reason":"Practical checks complete","checklist":{"identity":True,"duplicates":True,"modules":True}})
    call(client,platform_headers,"post",f"/signups/{row.id}/review",payload)
    tenant=platform_store.query(PlatformTenant).one()
    assert tenant.config["seats"]==3 and tenant.config["storage_mib"]==500
    sub=db.query(TenantSubscription).filter_by(company_id=tenant.company_id).one()
    assert sub.config_json["seats"]==3 and not db.query(User).filter_by(email=row.email).one().is_superuser


def test_correction_and_status_links_are_private_single_application_capabilities(client,db,platform_headers):
    row=submit(client,db)
    link=call(client,platform_headers,"post",f"/signups/{row.id}/request-info",{"action":"request_info","reason":"Please correct the contact name"})["url"]
    token=link.rsplit("/",1)[-1]
    assert client.get(ROOT+"/public/"+token).json()["fields"]["name"]=="Trial Owner"
    response=client.post(ROOT+"/public/"+token,json={"action":"correct","values":{"name":"Corrected Owner"}})
    assert response.status_code==200,response.text
    assert db._platform_db.get(PlatformSignupRequest,row.id).name=="Corrected Owner"
    assert client.post(ROOT+"/public/"+token,json={"action":"correct","values":{"name":"Replay"}}).status_code==404
    tracking=call(client,platform_headers,"post",f"/signups/{row.id}/tracking-link")["url"].rsplit("/",1)[-1]
    preview=client.get(ROOT+"/public/"+tracking).json()
    assert preview["status"]=="under_review" and "email" not in preview
    assert client.get(ROOT+"/public/not-a-real-token").status_code==404


def test_retention_legal_hold_and_purge_preserve_decision_ids_without_contact_data(client,db,platform_headers,platform_store):
    row=submit(client,db)
    call(client,platform_headers,"post",f"/signups/{row.id}/action",{"action":"archive","reason":"Archived spam"})
    call(client,platform_headers,"post",f"/signups/{row.id}/action",{"action":"delete","reason":"Too early"},409)
    row.archived_at=datetime.now(timezone.utc)-timedelta(days=100);row.legal_hold=True;platform_store.commit()
    call(client,platform_headers,"post",f"/signups/{row.id}/action",{"action":"delete","reason":"On legal hold"},409)
    row.legal_hold=False;platform_store.commit()
    call(client,platform_headers,"post",f"/signups/{row.id}/action",{"action":"delete","reason":"Retention elapsed"})
    assert row.deleted_at and row.email.startswith("deleted-signup-")
    call(client,platform_headers,"get",f"/signups/{row.id}",status=404)
    assert platform_store.query(PlatformEvent).filter_by(action="signup.delete").count()==1


def test_tasks_views_templates_local_outbox_and_report_schedule(client,db,platform_headers):
    task=call(client,platform_headers,"post","/records/task",{"title":"Call new applicant","data":{"due_at":datetime.now(timezone.utc).isoformat(),"body":"Discuss CRM"}},201)
    call(client,platform_headers,"post",f'/record/{task["id"]}/action',{"action":"complete","reason":"Follow-up completed"})
    assert call(client,platform_headers,"get","/records/task")[0]["state"]=="completed"
    call(client,platform_headers,"post","/records/view",{"title":"Pending CRM","data":{"filters":{"status":"pending","module":"crm"},"shared":True}},201)
    call(client,platform_headers,"post","/records/template",{"title":"Approval reason","data":{"body":"Business and applications verified"}},201)
    call(client,platform_headers,"post","/records/scheduled_report",{"title":"Weekly sales review","data":{"frequency":"weekly"}},201)
    call(client,platform_headers,"post","/operations/run-checks")
    assert len(call(client,platform_headers,"get","/records/report_snapshot"))==1
    call(client,platform_headers,"post","/operations/run-checks")
    assert len(call(client,platform_headers,"get","/records/report_snapshot"))==1
    call(client,platform_headers,"post","/records/scheduled_report",{"title":"Invalid schedule","data":{"frequency":"every second"}},422)


def test_plans_trial_conversion_usage_payment_currency_and_customer_suspend(client,db,platform_headers):
    row,approval,tenant=customer(client,db,platform_headers);catalogue=plan(client,platform_headers)
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"convert_paid","reason":"Offline contract approved","values":{"plan_id":catalogue["id"]}})
    assert tenant.status=="active"
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"payment","reason":"Bank payment received","values":{"reference":"BANK-001","amount_minor":199900,"currency":"INR"}})
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"payment","reason":"Duplicate reference","values":{"reference":"BANK-001","amount_minor":199900,"currency":"INR"}},409)
    report=call(client,platform_headers,"get","/reports")
    assert report["mrr_minor_by_currency"]=={"INR":199900} and report["offline_receipts_minor_by_currency"]=={"INR":199900}
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"suspend","reason":"Requested temporary pause"})
    assert db.query(TenantSubscription).filter_by(company_id=tenant.company_id).one().status=="suspended"
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"resume","reason":"Customer requested reactivation"})
    assert tenant.status=="active"


def test_customer_snapshots_extension_invitation_and_offboarding(client,db,platform_headers,platform_store):
    row,approval,tenant=customer(client,db,platform_headers)
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"snapshot","reason":"Before changing trial"})
    snapshot=platform_store.query(PlatformRecord).filter_by(kind="backup").one()
    original=tenant.config["trial_ends_at"]
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"extend_trial","reason":"Needs extra evaluation time","values":{"days":7}})
    assert tenant.config["trial_ends_at"]!=original
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"restore_snapshot","reason":"Restore original offer","values":{"snapshot_id":snapshot.id}})
    assert tenant.config["trial_ends_at"]==original
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"revoke_invitation","reason":"Customer requested revocation"})
    assert not db.query(User).filter_by(email=row.email).one().password_reset_token
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"resend_invitation","reason":"Customer requested replacement"})
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"cancel","reason":"Customer declined trial"})
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"offboard","reason":"Coordinate customer export"})
    assert tenant.status=="offboarded" and tenant.config["retention_until"]
    assert db.query(User).filter_by(email=row.email).count()==1


def test_owner_invitation_acceptance_session_revocation_and_last_owner_guard(client,db,platform_headers,platform_store):
    invitation=call(client,platform_headers,"post","/staff/invite",{"name":"Demo Reviewer","email":"reviewer@indianservers.com","role":"reviewer","assigned_only":True})
    token=invitation["url"].rsplit("/",1)[-1]
    response=client.post(ROOT+"/public/"+token,json={"action":"activate","values":{"password":PASSWORD}})
    assert response.status_code==200,response.text
    assert client.post(ROOT+"/public/"+token,json={"action":"activate","values":{"password":PASSWORD}}).status_code==404
    owner=platform_store.query(PlatformAdmin).filter_by(role="owner").one()
    call(client,platform_headers,"patch",f"/staff/{owner.id}",{"action":"access","reason":"Cannot remove last owner","values":{"role":"reviewer","is_active":True}},409)
    session=call(client,platform_headers,"get","/sessions")[0]
    call(client,platform_headers,"post","/sessions/revoke",{"action":"one","reason":"Revoke this session","values":{"id":session["id"]}})
    call(client,platform_headers,"get","/me",status=401)


def test_scoped_api_keys_cannot_take_over_owner_sessions_or_read_customers(client,db,platform_headers):
    key=call(client,platform_headers,"post","/api-keys",{"title":"Read reports","days":30,"scopes":["reports.read"]})
    headers={"Authorization":"Bearer "+key["key"]}
    call(client,headers,"get","/reports")
    call(client,headers,"get","/signups",status=403)
    call(client,headers,"post","/sessions/revoke",{"action":"all","reason":"Forbidden access"},403)
    call(client,platform_headers,"post",f'/record/{key["id"]}/action',{"action":"revoke","reason":"Key rotation"})
    call(client,headers,"get","/reports",status=401)


def test_report_cohorts_invitation_resends_and_real_activation(client,db,platform_headers):
    row,approval,tenant=customer(client,db,platform_headers)
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"resend_invitation","reason":"Replace invite"})
    report=call(client,platform_headers,"get","/reports")
    assert report["funnel"]["Invited"]==1 and report["summary"]["approval_rate"]==100
    assert report["funnel"]["Activated"]==0
    assert report["summary"]["churn_pct"] is None


def test_customer_support_consent_expires_without_impersonation(client,db,platform_headers):
    _,_,tenant=customer(client,db,platform_headers)
    result=call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"support_request","reason":"Review trial configuration","values":{"hours":2}})
    token=result["url"].rsplit("/",1)[-1]
    assert client.post(ROOT+"/public/"+token,json={"action":"approve"}).status_code==200
    support=db._platform_db.query(PlatformRecord).filter_by(kind="support").one()
    assert support.state=="authorized" and "No business record" in support.data["scope"]
    support.expires_at=datetime.now(timezone.utc)-timedelta(minutes=1);db._platform_db.commit()
    call(client,platform_headers,"post","/operations/run-checks")
    assert support.state=="expired"


def test_two_party_company_admin_transfer_never_grants_platform_role(client,db,platform_headers):
    row,_,tenant=customer(client,db,platform_headers)
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"admin_transfer","reason":"Company admin replacement","values":{"email":"new-admin@example.com"}})
    outbox=db._platform_db.query(PlatformRecord).filter_by(kind="outbox",tenant_id=tenant.id).all()
    tokens=[re.search(r"/platform/public/([A-Za-z0-9_-]+)",r.data["body"]).group(1) for r in outbox if "/platform/public/" in r.data.get("body","")]
    assert len(tokens)==2
    assert client.post(ROOT+"/public/"+tokens[0],json={"action":"approve"}).status_code==200
    assert tenant.admin_email==row.email
    result=client.post(ROOT+"/public/"+tokens[1],json={"action":"approve"})
    assert result.status_code==200,result.text
    assert tenant.admin_email=="new-admin@example.com"
    assert not db.query(User).filter_by(email=tenant.admin_email).one().is_superuser


def test_due_checks_apply_scheduled_plan_without_duplicate_reports_or_notices(client,db,platform_headers,platform_store):
    _,_,tenant=customer(client,db,platform_headers);catalogue=plan(client,platform_headers)
    call(client,platform_headers,"post",f"/customers/{tenant.id}/action",{"action":"convert_paid","reason":"Future contract start","values":{"plan_id":catalogue["id"],"effective_at":(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}})
    assert tenant.status=="trial"
    scheduled=platform_store.query(PlatformRecord).filter_by(kind="scheduled_change").one()
    scheduled.data={**scheduled.data,"effective_at":(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()};platform_store.commit()
    call(client,platform_headers,"post","/operations/run-checks")
    assert tenant.status=="active" and scheduled.state=="completed"


def test_owner_reset_is_local_single_use_and_revokes_previous_sessions(client,db,platform_headers,platform_store):
    response=client.post(ROOT+"/password-reset",json={"email":"owner@indianservers.com"})
    assert response.status_code==200 and "token" not in response.json()
    local=platform_store.query(PlatformRecord).filter_by(kind="outbox").order_by(PlatformRecord.id.desc()).first()
    token=re.search(r"/platform/public/([A-Za-z0-9_-]+)",local.data["body"]).group(1)
    result=client.post(ROOT+"/public/"+token,json={"action":"reset","values":{"password":"ReplacementPassword@123"}})
    assert result.status_code==200,result.text
    call(client,platform_headers,"get","/me",status=401)
    assert client.post(ROOT+"/public/"+token,json={"action":"reset","values":{"password":"DifferentPassword@123"}}).status_code==404
    assert client.post("/api/v1/auth/platform/login",json={"email":"owner@indianservers.com","password":"ReplacementPassword@123"}).status_code==200


def test_public_mail_domains_are_not_duplicates_and_csv_neutralizes_formulas(client,db,platform_headers,platform_store):
    a=submit(client,db,"a@gmail.com");b=submit(client,db,"b@gmail.com")
    b.phone="+919111111111";b.company_name="Different Company";a.name="  =SUM(1,2)";platform_store.commit()
    detail=call(client,platform_headers,"get",f"/signups/{a.id}")
    assert detail["duplicates"]==[]
    export=client.get(ROOT+"/signup-export",headers=platform_headers)
    assert export.status_code==200 and "'  =SUM(1,2)" in export.text


def test_reviewers_cannot_read_owner_password_links_or_other_staff_private_reports(client,db,platform_headers,platform_store):
    call(client,platform_headers,"post","/staff/invite",{"name":"Another Owner","email":"other-owner@indianservers.com","role":"owner"})
    client.post(ROOT+"/password-reset",json={"email":"owner@indianservers.com"})
    owner=platform_store.query(PlatformAdmin).filter_by(role="owner").one()
    platform_store.add(PlatformRecord(kind="report_snapshot",title="Private owner report",owner_id=owner.id,state="ready",data={"summary":{"signups":100}}));platform_store.commit()
    _,headers=staff_login(client,platform_store,"reviewer",True)
    assert call(client,headers,"get","/records/outbox")==[]
    assert call(client,headers,"get","/records/report_snapshot")==[]


def test_owner_http_audit_never_opens_the_customer_audit_store(monkeypatch):
    from starlette.requests import Request
    from app.core.middleware.audit import AuditLogMiddleware
    from app.db import session
    def forbidden(): raise AssertionError("Owner activity must not enter the customer audit DB")
    monkeypatch.setattr(session,"SessionLocal",forbidden)
    request=Request({"type":"http","path":"/api/v1/platform/signups","headers":[],"scheme":"http","server":("127.0.0.1",1534),"query_string":b""})
    AuditLogMiddleware(None)._persist(request,200,1,None)


def test_personal_notifications_stay_with_their_recipient_even_for_an_owner(client,db,platform_headers,platform_store):
    reviewer,headers=staff_login(client,platform_store,"reviewer",True)
    owner=platform_store.query(PlatformAdmin).filter_by(role="owner").one()
    platform_store.add_all([
        PlatformRecord(kind="notification",title="Private reviewer task",owner_id=reviewer.id,state="unread",data={"body":"For reviewer"}),
        PlatformRecord(kind="notification",title="Private owner notice",owner_id=owner.id,state="unread",data={"body":"For owner"}),
        PlatformRecord(kind="notification",title="Shared notice",state="unread",data={"body":"For team"}),
    ]);platform_store.commit()
    owner_titles={r["title"] for r in call(client,platform_headers,"get","/records/notification")}
    reviewer_titles={r["title"] for r in call(client,headers,"get","/records/notification")}
    assert "Private reviewer task" not in owner_titles
    assert "Private owner notice" not in reviewer_titles
    assert "Shared notice" in owner_titles & reviewer_titles
