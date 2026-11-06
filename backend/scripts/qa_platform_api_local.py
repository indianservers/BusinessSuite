"""Live, authenticated Platform Owner API checks. Local server only; QA data only.

Run from backend: venv/Scripts/python scripts/qa_platform_api_local.py
Results contain no passwords, bearer tokens, API keys or private-link URLs.
"""
import csv
import io
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

BASE = os.environ.get("PLATFORM_QA_BASE", "http://127.0.0.1:1534/api/v1")
if urlparse(BASE).hostname not in {"127.0.0.1", "localhost", "::1"}:
    raise SystemExit("This test runner is restricted to localhost.")
ROOT = Path(__file__).resolve().parents[2]
RUN = "APIQA" + datetime.now(timezone.utc).strftime("%m%d%H%M%S")
PASSWORD = "LocalQa@" + secrets.token_hex(12)
results = []
routes = {}
created_staff = []
created_keys = []
throttles = []
owner = None


def check(name, ok, detail=""):
    results.append({"name": name, "passed": bool(ok), "detail": detail})
    if not ok:
        print("FAIL:", name, detail, flush=True)


def request(name, method, path, session=None, payload=None, expected=200):
    started = time.monotonic()
    for attempt in range(4):
        response = (session or requests).request(method, BASE + path,
            json=payload, timeout=40, headers={"User-Agent": "BusinessSuite-local-API-QA"})
        if response.status_code != 429 or expected == 429:
            break
        retry = min(60, max(1, int(response.headers.get("Retry-After", "60"))))
        throttles.append({"name":name,"retry_after_seconds":retry})
        print("Respecting local rate limit; retry in",retry,"seconds",flush=True)
        time.sleep(retry + 0.1)
    expected = [expected] if isinstance(expected, int) else expected
    detail = ""
    if response.status_code not in expected:
        # Never persist response payloads containing activation/reset secrets.
        try:
            value = response.json().get("detail", "Unexpected response")
            detail = re.sub(r"https?://\S+", "[private URL omitted]", str(value))[:350]
        except Exception:
            detail = "Non-JSON error response"
    check(name, response.status_code in expected, detail)
    results[-1].update(method=method.upper(), path=re.sub(r"/public/[^/?]+", "/public/{token}", path),
        status=response.status_code, expected=expected, elapsed_ms=round((time.monotonic()-started)*1000))
    try:
        return response.json()
    except ValueError:
        return response.text


def login(email, password, platform=True, name="login"):
    data = request(name, "POST", "/auth/platform/login" if platform else "/auth/login",
        payload={"email": email, "password": password})
    if not isinstance(data, dict) or "access_token" not in data:
        raise RuntimeError("Authentication failed: " + name)
    session = requests.Session()
    session.headers["Authorization"] = "Bearer " + data["access_token"]
    return session


def p(name, method, path, payload=None, expected=200, session=None):
    return request(name, method, "/platform"+path, session or owner, payload, expected)


def action(ident, operation, values=None, expected=200):
    return p("customer " + operation, "POST", f"/customers/{ident}/action",
        {"action": operation, "reason": RUN+" disposable local QA", "values": values or {}}, expected)


def public(url, action=None, values=None, expected=200):
    path = "/platform/public/" + url.rsplit("/", 1)[-1]
    return request("private capability " + (action or "preview"), "POST" if action else "GET", path,
        payload={"action": action, "values": values or {}} if action else None, expected=expected)


def signup(suffix, company=True):
    data = {"applicant_type": "company" if company else "individual", "name": RUN+" Contact "+suffix,
        "company_name": RUN+" Company "+suffix if company else None,
        "email": (RUN+"."+suffix+"@example.com").lower(), "phone": "20255501"+suffix.zfill(2),
        "phone_country_code": "+91", "requested_modules": ["crm"], "consent": True,
        "source": "local-api-qa", "campaign": RUN, "consent_evidence": "Disposable synthetic API QA; no real applicant"}
    return p("create " + suffix, "POST", "/signups", data, 201)


def main():
    global owner
    spec = requests.get(BASE+"/openapi.json", timeout=40).json()
    for path, operations in spec["paths"].items():
        if path.startswith("/api/v1/platform/") or path.startswith("/api/v1/auth/platform/") or path.startswith("/api/v1/auth/signup"):
            for verb in operations:
                if verb in {"get", "post", "patch", "put", "delete"}:
                    routes[(verb.upper(), path.removeprefix("/api/v1"))] = operations[verb].get("summary", "")
    owner = login(os.environ.get("PLATFORM_QA_OWNER", "owner@indianservers.com"),
        os.environ.get("PLATFORM_QA_OWNER_PASSWORD", "Admin@123456"), name="owner real session login")
    me = p("owner identity", "GET", "/me")
    check("owner identity authenticated", me.get("role") == "owner" and bool(me.get("session_id")))
    request("legacy platform identity", "GET", "/auth/platform/me", owner)
    client = login("admin@aihrms.com", "Admin@123456", False, "business global admin login")
    company = login("bqa1106.next-admin@example.com", "PortalQa@2026!", False, "actual company admin login")
    company_me = request("company identity", "GET", "/auth/me", company)
    check("company admin is not global superuser", company_me.get("is_superuser") is False)
    request("platform token rejected by business identity", "GET", "/auth/me", owner, expected=401)
    # All protected route/method pairs: real client/global and company sessions,
    # no session, malformed token. Safe IDs and deliberately invalid writes.
    bad = requests.Session(); bad.headers["Authorization"] = "Bearer invalid-token"
    for (method, path) in routes:
        if path in {"/auth/platform/login", "/auth/signup", "/auth/signup/options", "/platform/password-reset"} or "/public/" in path:
            continue
        concrete = path.replace("{ident}", "2147483000").replace("{kind}", "task")
        if concrete.endswith("/search"): concrete += "?q="+RUN
        for label, session in [("anonymous", None), ("business superuser", client), ("company admin", company), ("malformed token", bad)]:
            request(label+" denied "+method+" "+path, method, concrete, session,
                {} if method != "GET" else None, expected=401)
    a, b = signup("01"), signup("02", False)
    aid, bid = a["id"], b["id"]
    p("owner list filters", "GET", "/signups?source=local-api-qa&search="+RUN+"&module=crm&applicant_type=company")
    p("owner detail", "GET", f"/signups/{aid}")
    p("owner legacy signup list", "GET", "/me")
    request("legacy signup list", "GET", "/auth/signup-requests", owner)
    edited = p("versioned edit", "PATCH", f"/signups/{aid}", {"version":a["version"], "reason":RUN,
        "name":RUN+" Corrected", "priority":"high", "checklist":{"identity":True,"duplicates":True,"modules":True}})
    p("stale version conflict", "PATCH", f"/signups/{aid}", {"version":a["version"],"reason":RUN,"name":"Stale QA"},409)
    p("bulk preview", "POST", "/signup-bulk", {"ids":[bid],"action":"under_review","reason":RUN})
    p("bulk requires versions", "POST", "/signup-bulk", {"ids":[bid],"action":"under_review","reason":RUN,"preview":False},409)
    p("bulk commit", "POST", "/signup-bulk", {"ids":[bid],"action":"under_review","reason":RUN,"preview":False,"versions":{str(bid):b["version"]}})
    for operation in ["archive", "restore", "under_review", "legal_hold"]:
        p("signup "+operation,"POST",f"/signups/{bid}/action",{"action":operation,"reason":RUN,"values":{"enabled":True}})
    p("retention guard", "POST", f"/signups/{bid}/action", {"action":"delete","reason":RUN},409)
    correction = p("request correction", "POST", f"/signups/{bid}/request-info", {"action":"request_info","reason":RUN+" correction"})
    public(correction["url"])
    public(correction["url"], "correct", {"name":RUN+" Applicant corrected"})
    public(correction["url"], "correct", {"name":"Replay applicant"},404)
    track = p("prepare private tracking", "POST", f"/signups/{bid}/tracking-link")
    public(track["url"])
    public(track["url"], "withdraw")
    check("withdraw persisted",p("read withdrawn", "GET",f"/signups/{bid}").get("status")=="withdrawn")
    # One disposable staff identity per role, through actual invitation/activation.
    staff_sessions = {}
    for role in ["reviewer","sales","support","billing","analyst"]:
        email = (RUN+"."+role+"@example.com").lower()
        invite=p("invite "+role,"POST","/staff/invite",{"email":email,"name":RUN+" "+role,"role":role,"assigned_only":True})
        public(invite["url"])
        public(invite["url"],"activate",{"password":PASSWORD})
        session=login(email,PASSWORD,name=role+" real session login")
        identity=p(role+" identity","GET","/me",session=session)
        created_staff.append(identity["id"])
        staff_sessions[role]=session
        p(role+" cannot manage staff","GET","/staff",expected=403,session=session)
        p(role+" cannot change settings","PUT","/settings",{"action":"settings","reason":RUN},403,session)
        p(role+" cannot run owner jobs","POST","/operations/run-checks",expected=403,session=session)
        p(role+" isolated personal tasks","GET","/records/task",session=session)
        p(role+" isolated signups","GET","/signups",expected=403 if role in {"billing","analyst"} else 200,session=session)
        p(role+" report permission","GET","/reports",expected=403 if role=="support" else 200,session=session)
    staff_id=created_staff[0]
    p("assign signup reviewer","POST",f"/signups/{bid}/action",{"action":"assign","reason":RUN,"values":{"assigned_to":staff_id}})
    scoped=p("assigned-only list","GET","/signups?status=all",session=staff_sessions["reviewer"])
    check("exact assignment scope",[r["id"] for r in scoped.get("items",[])]==[bid])
    p("foreign signup invisible","GET",f"/signups/{aid}",expected=404,session=staff_sessions["reviewer"])
    p("reviewer CSV forbidden","GET","/signup-export",expected=403,session=staff_sessions["reviewer"])
    p("staff review","PATCH",f"/staff/{staff_id}",{"action":"review","reason":RUN})
    p("narrow staff permissions","PATCH",f"/staff/{staff_id}",{"action":"access","reason":RUN,"values":{"permissions":["signup.read"]}})
    p("access change revoked old token","GET","/me",expected=401,session=staff_sessions["reviewer"])
    p("staff directory","GET","/staff-directory")
    p("staff listing","GET","/staff")
    analyst_email=(RUN+".analyst@example.com").lower()
    request("prepare disposable staff password reset","POST","/platform/password-reset",payload={"email":analyst_email})
    reset_outbox=p("read local reset outbox","GET","/records/outbox")
    reset_mail=next(r for r in reset_outbox if r.get("data",{}).get("recipient")==analyst_email and "Reset" in r["title"])
    reset_url=re.search(r"http://127\.0\.0\.1:5191/platform/public/[A-Za-z0-9_-]+",reset_mail["data"]["body"]).group()
    public(reset_url);public(reset_url,"reset",{"password":PASSWORD+"x"})
    public(reset_url,"reset",{"password":PASSWORD+"x"},404)
    p("reset revoked previous sessions","GET","/me",expected=401,session=staff_sessions["analyst"])
    staff_sessions["analyst"]=login(analyst_email,PASSWORD+"x",name="reset password login verified")
    # CRUD record kinds and local-only communication transitions.
    for kind in ["view","template","task","note","scheduled_report"]:
        record=p("create "+kind,"POST","/records/"+kind,{"title":RUN+" "+kind,"signup_id":aid if kind=="note" else None,
            "data":{"frequency":"weekly","next_run_at":(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()} if kind=="scheduled_report" else {"body":"Local QA","shared":kind=="view"}},201)
        for operation in ["edit","complete","reopen","archive"]:
            p(kind+" "+operation,"POST",f'/record/{record["id"]}/action',{"action":operation,"reason":RUN,"values":{"title":RUN+" edited "+kind}})
    for kind in ["view","template","task","note","notification","outbox","provisioning","customer_invitation","staff_invitation","password_reset","api_key","support","backup","billing_entry","scheduled_report","report_snapshot","scheduled_change","escalation","admin_transfer","support_consent"]:
        p("owner records "+kind,"GET","/records/"+kind)
    outbox=p("QA outbox", "GET", "/records/outbox")
    qa_mail=next(r for r in outbox if RUN.lower() in r.get("data",{}).get("recipient","").lower())
    for operation in ["preview_delivered","retry"]:
        p("local outbox "+operation,"POST",f'/record/{qa_mail["id"]}/action',{"action":operation,"reason":RUN})
    # Customer provisioning, contracts and preservation workflow.
    approval=p("approve QA company","POST",f"/signups/{aid}/review",{"decision":"approve","reason":RUN,"trial_days":2,"modules":["crm"],"seats":2,"storage_mib":100})
    customers=p("customers list","GET","/customers?search="+RUN)
    tenant=next(r for r in customers if r["signup_id"]==aid);tid=tenant["id"]
    p("customer detail","GET",f"/customers/{tid}")
    plan_data={"code":RUN.lower(),"name":RUN+" Plan","modules":["crm"],"seats":3,"storage_mib":200,"monthly_price_minor":12345,"currency":"INR"}
    plan=p("create catalogue plan","POST","/plans",plan_data,201)
    p("duplicate plan rejected","POST","/plans",plan_data,409)
    p("edit catalogue plan","PUT",f'/plans/{plan["id"]}',{**plan_data,"name":RUN+" Edited plan"})
    p("plan list","GET","/plans")
    action(tid,"sync_usage");action(tid,"snapshot")
    snapshots=p("customer snapshots","GET",f"/records/backup?tenant_id={tid}")
    action(tid,"extend_trial",{"days":2})
    action(tid,"restore_snapshot",{"snapshot_id":snapshots[0]["id"]})
    action(tid,"entitlements",{"seats":3,"storage_mib":200,"modules":["crm"]})
    action(tid,"plan",{"plan_id":plan["id"],"effective_at":(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
    action(tid,"convert_paid",{"plan_id":plan["id"]})
    receipt={"reference":RUN+"-OFFLINE","amount_minor":12345,"currency":"INR"}
    action(tid,"payment",receipt);action(tid,"payment",receipt,409)
    action(tid,"suspend");action(tid,"resume")
    action(tid,"revoke_invitation");action(tid,"resend_invitation")
    action(tid,"admin_transfer",{"email":(RUN+".new-admin@example.com").lower()})
    transfer_mail=p("transfer local outbox","GET",f"/records/outbox?tenant_id={tid}")
    transfer_urls=[re.search(r"http://127\.0\.0\.1:5191/platform/public/[A-Za-z0-9_-]+",r["data"]["body"]).group()
        for r in transfer_mail if r["title"]=="Confirm company admin transfer"]
    check("two transfer capabilities",len(transfer_urls)==2)
    for url in transfer_urls: public(url);public(url,"approve")
    support=action(tid,"support_request",{"hours":1});public(support["url"]);public(support["url"],"approve")
    action(tid,"assign",{"assigned_to":created_staff[2]})
    p("foreign tenant invisible","GET",f"/customers/{tid}",expected=404,session=staff_sessions["sales"])
    p("assigned support can view","GET",f"/customers/{tid}",session=staff_sessions["support"])
    p("configuration export","GET",f"/customers/{tid}/export")
    action(tid,"cancel");action(tid,"offboard")
    # Integration capabilities cannot become interactive owner sessions.
    key=p("create report key","POST","/api-keys",{"title":RUN,"days":1,"scopes":["reports.read"]})
    created_keys.append(key["id"])
    key_session=requests.Session();key_session.headers["Authorization"]="Bearer "+key["key"]
    p("key report allowed","GET","/reports",session=key_session)
    for path in ["/me","/sessions","/signups","/customers","/staff","/records/outbox"]:
        p("key denied "+path,"GET",path,expected=403,session=key_session)
    p("key cannot revoke sessions","POST","/sessions/revoke",{"action":"all","reason":RUN},403,key_session)
    p("revoke API key","POST",f'/record/{key["id"]}/action',{"action":"revoke","reason":RUN})
    p("revoked key denied","GET","/reports",expected=401,session=key_session)
    p("profile name validation","PATCH","/profile",{"action":"profile","reason":RUN,"values":{"name":"x"}},422)
    p("profile preferences same values","PATCH","/profile",{"action":"preferences","reason":RUN,"values":{"page_size":me.get("preferences",{}).get("page_size",25)}})
    p("settings same values","PUT","/settings",{"action":"settings","reason":RUN,"values":p("settings read","GET","/settings")})
    p("invalid settings rejected","PUT","/settings",{"action":"settings","reason":RUN,"values":{"idle_minutes":0}},422)
    p("global search","GET","/search?q="+RUN)
    p("audit events","GET","/events?search=signup")
    p("login history","GET","/login-history")
    p("reports","GET","/reports");p("JSON report export","GET","/report-export")
    p("reverse report date validation","GET","/reports?start=2026-11-06T00:00:00Z&end=2026-11-05T00:00:00Z",expected=422)
    p("run due jobs","POST","/operations/run-checks")
    export=p("CSV export","GET","/signup-export")
    check("CSV header present",isinstance(export,str) and next(csv.reader(io.StringIO(export)))[0]=="id")
    p("sessions list","GET","/sessions")
    request("public signup options","GET","/auth/signup/options")
    public_signup={"applicant_type":"individual","name":RUN+" Public lead","email":(RUN+".public@example.com").lower(),
        "phone":"2025550199","phone_country_code":"+91","requested_modules":["crm"],"consent":True,"campaign":RUN}
    request("public signup intake","POST","/auth/signup",payload=public_signup,expected=202)
    public_rows=p("find public intake","GET","/signups?search="+public_signup["email"])
    if public_rows.get("items"):
        request("legacy review rejection","POST",f'/auth/signup-requests/{public_rows["items"][0]["id"]}/review',owner,
            {"decision":"reject","reason":RUN+" synthetic QA rejection"})
    # Revoke only this runner's new owner session, never the user's browser sessions.
    p("revoke runner session","POST","/sessions/revoke",{"action":"one","reason":RUN,"values":{"id":me["session_id"]}})
    p("revoked session rejected","GET","/me",expected=401)
    owner=login("owner@indianservers.com",os.environ.get("PLATFORM_QA_OWNER_PASSWORD","Admin@123456"),name="cleanup owner login")


def finish():
    if owner:
        for key in created_keys:
            p("cleanup key","POST",f"/record/{key}/action",{"action":"revoke","reason":RUN})
        for staff in created_staff:
            p("cleanup disable QA staff","PATCH",f"/staff/{staff}",{"action":"access","reason":RUN,"values":{"is_active":False}})
        identity=p("cleanup runner identity","GET","/me")
        if isinstance(identity,dict) and identity.get("session_id"):
            p("cleanup revoke runner session","POST","/sessions/revoke",{"action":"one","reason":RUN,"values":{"id":identity["session_id"]}})
    coverage=[]
    for (method,path),summary in routes.items():
        pattern="^"+re.sub(r"\\\{[^}]+\\\}",r"[^/?]+",re.escape(path))+"$"
        hits=[r for r in results if r.get("method")==method and re.match(pattern,r.get("path","").split("?")[0])]
        coverage.append({"method":method,"path":"/api/v1"+path,"summary":summary,"checks":len(hits),
            "authenticated_success":any(r.get("status",0) in range(200,300) and r["passed"] for r in hits)})
    report={"run":RUN,"local_base":BASE,"utc":datetime.now(timezone.utc).isoformat(),
        "passed":sum(r["passed"] for r in results),"failed":sum(not r["passed"] for r in results),
        "routes":coverage,"checks":results,"throttle_retries":throttles,"residue":"Synthetic signup/customer/plan/history records remain labelled with run; QA staff disabled and keys revoked."}
    output=ROOT/"outputs/platform-owner-api-local.json";output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ["run","passed","failed"]}),flush=True)
    print("Evidence:",output,flush=True)


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        check("runner completed",False,type(exc).__name__+": "+str(exc)[:150])
        raise
    finally:
        finish()
