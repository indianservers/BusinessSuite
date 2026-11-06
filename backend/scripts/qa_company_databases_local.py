"""Provision/verify seven disposable local companies through real HTTP sessions."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,re,time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse,parse_qs
import requests
from psycopg import connect
from sqlalchemy import text
from app.core.config import settings
from app.platform_owner.session import platform_factory
from app.platform_owner.models import PlatformTenantDatabase as D
from app.db.tenant import lookup_route,tenant_session,tenant_engine,registry_factory

BASE="http://127.0.0.1:1534/api/v1"
PASSWORD="TenantDbQa@2026!"
checks=[];companies=[]


def check(name,condition):
    checks.append({"name":name,"passed":bool(condition)})
    if not condition:print("FAIL",name,flush=True)


def call(method,path,session=None,data=None,status=200,headers=None):
    for _ in range(4):
        r=(session or requests).request(method,BASE+path,json=data,headers=headers,timeout=120)
        if r.status_code!=429:break
        time.sleep(min(60,int(r.headers.get("Retry-After","30")))+0.1)
    check(method+" "+path.split("?")[0]+" -> "+str(status),r.status_code==status)
    if r.status_code!=status:raise RuntimeError(str(r.status_code)+": "+str(r.json().get("detail","Unexpected response"))[:150])
    return r.json()


def login(email,workspace=None):
    r=call("POST","/auth/login",data={"email":email,"password":PASSWORD},headers={"X-Suite-Tenant":workspace} if workspace else None)
    s=requests.Session();s.headers["Authorization"]="Bearer "+r["access_token"]
    return s,r


def run():
    auth=call("POST","/auth/platform/login",data={"email":"owner@indianservers.com","password":"Admin@123456"})
    owner=requests.Session();owner.headers["Authorization"]="Bearer "+auth["access_token"]
    for number in range(1,8):
        email=f"tdbqa.{number}@example.com"
        found=call("GET","/platform/signups?status=all&search="+email,owner)["items"]
        row=found[0] if found else call("POST","/platform/signups",owner,{"applicant_type":"company","name":f"TDBQA Contact {number}",
            "company_name":f"TDBQA Company {number}","email":email,"phone":f"202555030{number}","requested_modules":["crm"],
            "consent":True,"consent_evidence":"Disposable local database isolation QA company","source":"tenant-db-qa","campaign":"TDBQA7"},201)
        if row["status"]!="approved":
            call("PATCH",f'/platform/signups/{row["id"]}',owner,{"version":row["version"],"reason":"Dedicated DB QA checklist","checklist":{"identity":True,"duplicates":True,"modules":True}})
            approval=call("POST",f'/platform/signups/{row["id"]}/review',owner,{"decision":"approve","reason":"Dedicated local DB QA approval","modules":["crm"],"trial_days":14,"seats":5,"storage_mib":1024})
            url=approval["invitation_url"]
            params=parse_qs(urlparse(url).query)
            call("POST","/auth/reset-password",data={"token":params["token"][0],"new_password":PASSWORD},headers={"X-Suite-Tenant":params["tenant"][0]})
        directory=call("GET","/platform/databases",owner)
        database=next(x for x in directory if x["signup_id"]==row["id"])
        workspace=database["workspace_code"]
        with tenant_session(lookup_route(workspace)) as company_db:
            inactive=company_db.execute(text("SELECT NOT is_active FROM users WHERE email=:email"),{"email":email}).scalar()
        if inactive:
            tenant=next(x for x in call("GET","/platform/customers?search=TDBQA",owner) if x["signup_id"]==row["id"])
            invitation=call("POST",f'/platform/customers/{tenant["id"]}/action',owner,{"action":"resend_invitation","reason":"Resume interrupted local QA activation"})
            params=parse_qs(urlparse(invitation["url"]).query)
            call("POST","/auth/reset-password",data={"token":params["token"][0],"new_password":PASSWORD},headers={"X-Suite-Tenant":workspace})
        session,tokens=login(email,workspace)
        me=call("GET","/auth/me",session)
        access=call("GET","/access/me",session)
        check(f"company{number} is scoped admin",me["is_superuser"] is False and access.get("isAccessAdmin") is True)
        check(f"company{number} correct company",access.get("companyId")==database["company_id"])
        health=call("POST",f'/platform/databases/{database["id"]}/check',owner)
        check(f"company{number} single-company database",health["healthy"] and health["company_count"]==1 and health["database_name"]==database["database_name"])
        # Existing hidden legacy CRM creation route is still a real DB write.
        leads=call("GET","/crm/leads?search=TDBQA",session)
        if not leads.get("items"):
            lead=call("POST","/crm/lead-management/leads",session,{"values":{"firstName":"TDBQA","lastName":f"Only Company {number}","fullName":f"TDBQA Only Company {number}","email":f"tdbqa.lead.{number}@example.com","status":"New"}},201)
        leads=call("GET","/crm/leads?search=TDBQA",session)
        check(f"company{number} private business record",len(leads.get("items",[]))==1 and leads["items"][0].get("email")==f"tdbqa.lead.{number}@example.com")
        for path in ["/platform/me","/platform/signups","/platform/databases","/auth/signup-requests"]:
            call("GET",path,session,status=401)
        refreshed=call("POST","/auth/refresh",data={"refresh_token":tokens["refresh_token"]})
        refreshed_session=requests.Session();refreshed_session.headers["Authorization"]="Bearer "+refreshed["access_token"]
        call("GET","/auth/me",refreshed_session)
        companies.append({"number":number,"signup_id":row["id"],"email":email,"workspace":workspace,"tenant_uuid":database["tenant_uuid"],
            "company_id":database["company_id"],"database_name":database["database_name"],"database_id":database["id"],"session":refreshed_session})
        print("Verified",workspace,database["database_name"],flush=True)
    check("seven distinct databases",len({c["database_name"] for c in companies})==7)
    for number,c in enumerate(companies):
        other=companies[(number+1)%7]
        call("GET","/auth/me",c["session"],status=403,headers={"X-Suite-Tenant":other["workspace"]})
        call("GET","/access/me",c["session"],status=403,headers={"X-Suite-Organization":str(other["company_id"])})
        call("POST","/auth/login",data={"email":c["email"],"password":PASSWORD},headers={"X-Suite-Tenant":other["workspace"]},status=401)
        route=lookup_route(c["workspace"])
        with tenant_session(route) as db:
            check(c["workspace"]+" SQL identity",db.execute(text("SELECT current_database()")).scalar()==c["database_name"])
            check(c["workspace"]+" user IDs may overlap safely",db.execute(text("SELECT id FROM users LIMIT 1")).scalar()==1)
            try:db.execute(text("UPDATE suite_tenant_identity SET company_id=1"));check("identity write denied",False)
            except Exception:db.rollback();check("identity write denied",True)
        engine=tenant_engine(route)
        for forbidden in [other["database_name"],"indian_servers_platform","business_suite"]:
            try:
                with connect(engine.url.set(drivername="postgresql",database=forbidden).render_as_string(hide_password=False),connect_timeout=3):pass
                check(c["workspace"]+" cannot connect "+forbidden,False)
            except Exception:check(c["workspace"]+" cannot connect "+forbidden,True)
    # Alternating concurrent requests must never borrow another tenant context.
    def concurrent_read(c):
        r=requests.get(BASE+"/crm/leads?search=TDBQA",headers=dict(c["session"].headers),timeout=30)
        return r.status_code==200 and len(r.json().get("items",[]))==1 and r.json()["items"][0]["email"]==f'tdbqa.lead.{c["number"]}@example.com'
    with ThreadPoolExecutor(max_workers=7) as executor:
        outcomes=list(executor.map(concurrent_read,companies*3))
    check("21 concurrent company requests isolated",all(outcomes))
    with platform_factory()() as registry:
        row=registry.get(D,companies[-1]["database_id"])
        original=row.status;row.status="moving";registry.commit()
        try:call("GET","/auth/me",companies[-1]["session"],status=503)
        finally:row.status=original;registry.commit()
    call("GET","/auth/me",companies[-1]["session"])
    with registry_factory()() as registry:
        try:registry.execute(text("SELECT count(*) FROM platform_signup_requests"));check("router cannot read signups",False)
        except Exception:registry.rollback();check("router cannot read signups",True)
    from app.db.session import LegacySessionLocal
    with LegacySessionLocal() as db:check("legacy database has no new company accounts",db.execute(text("SELECT count(*) FROM users WHERE email LIKE 'tdbqa.%@example.com'")).scalar()==0)
    outbox=call("GET","/platform/records/outbox",owner)
    check("all QA invitations remain local",all(r["state"] in {"queued_local","preview_delivered"} for r in outbox if r["data"].get("recipient","").startswith("tdbqa.")))


if __name__=="__main__":
    try:run()
    finally:
        output=Path(__file__).resolve().parents[2]/"outputs/company-databases-local.json"
        output.write_text(json.dumps({"passed":sum(c["passed"] for c in checks),"failed":sum(not c["passed"] for c in checks),
            "companies":[{k:v for k,v in c.items() if k!="session"} for c in companies],"checks":checks},indent=2))
        print("Results:",sum(c["passed"] for c in checks),"passed;",sum(not c["passed"] for c in checks),"failed",flush=True)
