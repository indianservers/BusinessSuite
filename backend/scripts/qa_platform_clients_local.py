"""Authenticated, disposable client-management QA against the local API only."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import re
from datetime import timedelta
from urllib.parse import urlparse, parse_qs
import requests
from app.db.base import Base
from app.platform_owner.session import platform_factory
from app.platform_owner.models import PlatformTenant, PlatformAdmin, PlatformRecord
from app.platform_owner import service as service
from app.core.security import get_password_hash
from app.db.tenant import lookup_route, tenant_session
from sqlalchemy import text

BASE = "http://127.0.0.1:1534/api/v1"
assert urlparse(BASE).hostname == "127.0.0.1"
STATE = Path(__file__).resolve().parents[2] / ".local/client-management-qa-state.json"
OUT = Path(__file__).resolve().parents[2] / "outputs/platform-clients-full-api.json"
PASSWORD = "ClientMgmtQa@2026!"
checks = []


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})
    if not condition: print("FAIL", name, flush=True)


def call(session, method, path, data=None, expected=200):
    response = session.request(method, BASE+path, json=data, timeout=120)
    check(f"{method} {path.split('?')[0]} returns {expected}", response.status_code == expected)
    if response.status_code != expected:
        raise RuntimeError(f"{method} {path.split('?')[0]} expected {expected}, got {response.status_code}")
    return response.json() if "application/json" in response.headers.get("content-type", "") else response.text


def login(email, password=PASSWORD, workspace=None, platform=False):
    session = requests.Session()
    if workspace: session.headers["X-Suite-Tenant"] = workspace
    result = call(session, "POST", "/auth/platform/login" if platform else "/auth/login", {"email": email, "password": password})
    session.headers["Authorization"] = "Bearer "+result["access_token"]
    return session


def action(owner, ident, command, values=None, expected=200):
    return call(owner, "POST", f"/platform/customers/{ident}/action", {"action": command, "reason": "Disposable local client-management QA", "values": values or {}}, expected)


def setup(owner):
    if STATE.exists(): return json.loads(STATE.read_text(encoding="utf-8"))
    fixtures = []
    for number in (1, 2):
        email = f"cmqa1107.{number}@example.com"
        row = call(owner, "POST", "/platform/signups", {"applicant_type": "company", "name": f"CMQA Contact {number}",
            "company_name": f"CMQA1107 Company {number}", "email": email, "phone": f"202555070{number}",
            "requested_modules": ["crm", "project_management"], "consent": True, "consent_evidence": "Disposable local API and browser QA fixture", "source": "local-client-qa"}, 201)
        call(owner, "PATCH", f'/platform/signups/{row["id"]}', {"version": row["version"], "reason": "QA fixture review", "checklist": {"identity": True, "duplicates": True, "modules": True}})
        approval = call(owner, "POST", f'/platform/signups/{row["id"]}/review', {"decision": "approve", "reason": "Disposable local client QA approval", "modules": ["crm", "project_management"], "trial_days": 14, "seats": 5, "storage_mib": 1024})
        params = parse_qs(urlparse(approval["invitation_url"]).query)
        workspace = f'company-{row["id"]}'
        if number == 1:
            anonymous = requests.Session(); anonymous.headers["X-Suite-Tenant"] = workspace
            call(anonymous, "POST", "/auth/reset-password", {"token": params["token"][0], "new_password": PASSWORD})
        tenant = call(owner, "GET", "/platform/client-directory?search="+email)["items"][0]
        fixtures.append({"id": tenant["id"], "signup_id": row["id"], "email": email, "workspace": workspace, "company_id": tenant["company_id"]})
    STATE.write_text(json.dumps(fixtures, indent=2), encoding="utf-8")
    return fixtures


def run(owner, fixtures):
    a, b = fixtures
    previous = call(owner, "GET", f'/platform/records/backup?tenant_id={a["id"]}')
    if previous:
        action(owner, a["id"], "restore_snapshot", {"snapshot_id": previous[-1]["id"]})
    company = login(a["email"], workspace=a["workspace"])
    check("company login has own tenant", call(company, "GET", "/access/me")["companyId"] == a["company_id"])
    for path in ["/platform/client-directory", "/platform/client-directory/export", "/platform/customers", f'/platform/customers/{a["id"]}', f'/platform/clients/{a["id"]}/statistics', "/platform/databases"]:
        call(company, "GET", path, expected=401)
        call(requests.Session(), "GET", path, expected=401)
    call(company, "PATCH", f'/platform/clients/{a["id"]}/profile', {"reason": "Forbidden client test"}, 401)
    call(company, "POST", "/platform/client-usage-refresh", {"ids": [a["id"]]}, 401)
    action(company, a["id"], "suspend", expected=401)
    wrong = company.get(BASE+"/auth/me", headers={"X-Suite-Tenant": b["workspace"]}, timeout=30)
    check("company token cannot override database routing", wrong.status_code == 403)
    directory = call(owner, "GET", "/platform/client-directory?search=CMQA1107")
    check("both QA clients in directory", directory["total"] == 2)
    for key, value in [("status", "trial"), ("module", "crm"), ("attention", "activation_pending"), ("priority", "normal")]:
        filtered = call(owner, "GET", f"/platform/client-directory?search=CMQA1107&{key}={value}")
        check(f"filter {key} matches returned records", bool(filtered["items"]) and filtered["summary"]["total"] == filtered["total"])
    for sort in ["newest", "name", "seats", "attention", "last_login"]:
        call(owner, "GET", "/platform/client-directory?search=CMQA1107&sort="+sort)
    first = call(owner, "GET", "/platform/client-directory?search=CMQA1107&page_size=1&page=1")
    second = call(owner, "GET", "/platform/client-directory?search=CMQA1107&page_size=1&page=2")
    check("pagination contains distinct clients with stable totals", len(first["items"]) == len(second["items"]) == 1 and first["items"][0]["id"] != second["items"][0]["id"] and first["total"] == second["total"] == 2)
    for query in ["page=0", "page_size=101", "sort=unknown"]: call(owner, "GET", "/platform/client-directory?"+query, expected=422)
    check("empty search returns empty summary", call(owner, "GET", "/platform/client-directory?search=cmqa-does-not-exist")["summary"]["total"] == 0)
    csv = call(owner, "GET", "/platform/client-directory/export?search=CMQA1107")
    check("CSV is filtered", "CMQA1107 Company 1" in csv and "TDBQA" not in csv)
    current = call(owner, "GET", f'/platform/customers/{a["id"]}')
    version = current["config"].get("account_profile", {}).get("version", 0)
    profile = {"version": version, "priority": "critical", "stage": "at_risk", "contact_name": "CMQA Business Contact", "contact_phone": "2025550701", "industry": "QA", "tags": ["cmqa", "attention"],
        "next_review_at": (service.now()-timedelta(days=1)).isoformat(), "renewal_at": (service.now()+timedelta(days=7)).isoformat(), "reason": "QA profile roundtrip"}
    saved = call(owner, "PATCH", f'/platform/clients/{a["id"]}/profile', profile)
    check("profile increments optimistic version", saved["version"] == version+1)
    call(owner, "PATCH", f'/platform/clients/{a["id"]}/profile', profile, 409)
    for fields in [{"priority": "urgent"}, {"tags": ["x"*51]}, {"version": -1}, {"renewal_at": "invalid"}, {"unknown": "field"}]:
        call(owner, "PATCH", f'/platform/clients/{a["id"]}/profile', {**profile, "version": saved["version"], **fields}, 422)
    flagged = call(owner, "GET", "/platform/client-directory?search=cmqa1107.1&attention=review_due")["items"][0]
    check("review and renewal flags derived from dates", {"review_due", "renewal_due"} <= set(flagged["flags"]))
    refreshed = call(owner, "POST", "/platform/client-usage-refresh", {"ids": [a["id"], b["id"]]})
    check("both dedicated database refreshes succeed", all(r["ok"] for r in refreshed["items"]))
    action(owner, a["id"], "sync_usage")
    stats = call(owner, "GET", f'/platform/clients/{a["id"]}/statistics')
    check("statistics correctly routed", stats["database"]["workspace"] == a["workspace"] and stats["usage"]["database_bytes"] > 0 and len(stats["snapshots"]) >= 2)
    call(owner, "POST", "/platform/client-usage-refresh", {"ids": []}, 422)
    call(owner, "POST", "/platform/client-usage-refresh", {"ids": [a["id"]]*11}, 422)
    call(owner, "POST", "/platform/client-usage-refresh", {"ids": [a["id"], 2147483647]}, 404)
    # Notes and snapshots keep tenant references in the independent owner store.
    note = call(owner, "POST", "/platform/records/note", {"tenant_id": a["id"], "title": "CMQA API note", "data": {"body": "Local account note"}}, 201)
    check("note listed only for its client", any(n["id"] == note["id"] for n in call(owner, "GET", f'/platform/records/note?tenant_id={a["id"]}')) and not any(n["id"] == note["id"] for n in call(owner, "GET", f'/platform/records/note?tenant_id={b["id"]}')))
    exported = call(owner, "GET", f'/platform/customers/{a["id"]}/export')
    check("configuration export excludes business records and credentials", "customer" in exported and "hashed_password" not in json.dumps(exported) and "encrypted_password" not in json.dumps(exported))
    action(owner, a["id"], "snapshot")
    snapshot = call(owner, "GET", f'/platform/records/backup?tenant_id={a["id"]}')[0]
    old_end = current["config"]["trial_ends_at"]
    changed = action(owner, a["id"], "extend_trial", {"days": 3})["customer"]
    check("trial extension changes end", changed["config"]["trial_ends_at"] > old_end)
    action(owner, a["id"], "extend_trial", {"days": 0}, 422)
    action(owner, a["id"], "entitlements", {"seats": 7, "storage_mib": 2048, "modules": ["crm", "project_management"]})
    action(owner, a["id"], "entitlements", {"modules": []}, 422)
    action(owner, a["id"], "entitlements", {"seats": True}, 422)
    action(owner, a["id"], "restore_snapshot", {"snapshot_id": snapshot["id"]})
    restored = call(owner, "GET", f'/platform/customers/{a["id"]}')
    check("snapshot restores subscription configuration", restored["config"]["seats"] == 5 and restored["config"]["trial_ends_at"] == old_end)
    action(owner, b["id"], "restore_snapshot", {"snapshot_id": snapshot["id"]}, 404)
    plans = call(owner, "GET", "/platform/plans")
    plan = next((p for p in plans if p["code"] == "cmqa1107"), None) or call(owner, "POST", "/platform/plans", {"code": "cmqa1107", "name": "CMQA local plan", "modules": ["crm", "project_management"], "seats": 10, "storage_mib": 2048, "monthly_price_minor": 125000, "currency": "INR"}, 201)
    action(owner, a["id"], "convert_paid", {"plan_id": plan["id"]})
    action(owner, a["id"], "extend_trial", {"days": 1}, 409)
    action(owner, a["id"], "plan", {"plan_id": plan["id"]})
    reference = "CMQA-API-"+service.now().strftime("%H%M%S")
    action(owner, a["id"], "payment", {"reference": reference, "amount_minor": 125000, "currency": "INR"})
    action(owner, a["id"], "payment", {"reference": reference, "amount_minor": 125000, "currency": "INR"}, 409)
    action(owner, a["id"], "payment", {"reference": "CMQA-invalid", "amount_minor": 0}, 422)
    action(owner, a["id"], "cancel")
    action(owner, a["id"], "resume")
    check("paid cancellation reactivation preserves paid status without prior suspension", call(owner, "GET", f'/platform/customers/{a["id"]}')["status"] == "active")
    action(owner, a["id"], "suspend")
    action(owner, a["id"], "suspend", expected=409)
    denied = company.get(BASE+"/crm/leads", timeout=30)
    check("suspended company cannot read CRM", denied.status_code in {402, 403})
    action(owner, a["id"], "resume")
    check("reactivation restores correct paid lifecycle", call(owner, "GET", f'/platform/customers/{a["id"]}')["status"] == "active")
    action(owner, a["id"], "cancel")
    action(owner, a["id"], "resume")
    check("cancelled paid client reactivates as paid", call(owner, "GET", f'/platform/customers/{a["id"]}')["status"] == "active")
    # Restore original trial after testing paid lifecycle.
    action(owner, a["id"], "restore_snapshot", {"snapshot_id": snapshot["id"]})
    # Separate inactive client exercises invitation and two-party transfer without touching a real identity.
    invitation = action(owner, b["id"], "resend_invitation")
    check("invitation retains dedicated tenant routing", "tenant=" in invitation["url"])
    params = parse_qs(urlparse(invitation["url"]).query)
    action(owner, b["id"], "revoke_invitation")
    anon = requests.Session(); anon.headers["X-Suite-Tenant"] = b["workspace"]
    call(anon, "POST", "/auth/reset-password", {"token": params["token"][0], "new_password": PASSWORD}, 400)
    action(owner, b["id"], "resend_invitation")
    support = action(owner, a["id"], "support_request", {"hours": 1})
    token = support["url"].rsplit("/", 1)[-1]
    call(requests.Session(), "GET", "/platform/public/"+token)
    call(requests.Session(), "POST", "/platform/public/"+token, {"action": "approve"})
    call(requests.Session(), "POST", "/platform/public/"+token, {"action": "approve"}, 404)
    # Role boundaries use disposable local staff, narrowed by assigned client.
    with platform_factory()() as db:
        for role in ["support", "billing", "analyst"]:
            email = f"cmqa1107.{role}@indianservers.com"
            actor = db.query(PlatformAdmin).filter_by(email=email).first()
            if not actor:
                actor = PlatformAdmin(email=email, name="CMQA "+role, role=role, assigned_only=True, hashed_password=get_password_hash(PASSWORD)); db.add(actor); db.flush()
            if role == "support": db.get(PlatformTenant, a["id"]).assigned_to = actor.id
        db.commit()
    for role in ["support", "billing", "analyst"]:
        staff = login(f"cmqa1107.{role}@indianservers.com", platform=True)
        who = call(staff, "GET", "/platform/me"); check(role+" authenticated with correct role", who["role"] == role)
        if role == "support":
            result = call(staff, "GET", "/platform/client-directory")
            check("assigned support sees only its client and aggregates", result["total"] == 1 and result["items"][0]["id"] == a["id"])
            call(staff, "GET", f'/platform/clients/{b["id"]}/statistics', expected=404)
            call(staff, "PATCH", f'/platform/clients/{a["id"]}/profile', {"reason": "Forbidden role edit"}, 403)
        else:
            call(staff, "GET", "/platform/client-directory", expected=403 if role == "analyst" else 200)
        call(staff, "POST", "/platform/client-usage-refresh", {"ids": [a["id"]]}, 403)
    # Physical placement proof after account operations.
    with tenant_session(lookup_route(a["workspace"])) as db:
        check("client subscription rows remain in own company DB", db.execute(text("select count(*) from companies")).scalar() == 1)
    check("history records management operations", {"tenant.profile_updated", "tenant.snapshot", "tenant.payment", "tenant.suspend", "tenant.resume"} <= {h["action"] for h in call(owner, "GET", f'/platform/customers/{a["id"]}')["history"]})


def remaining(owner, fixtures):
    a, b = fixtures
    plan = next(p for p in call(owner, "GET", "/platform/plans") if p["code"] == "cmqa1107")
    result = action(owner, a["id"], "convert_paid", {"plan_id": plan["id"], "effective_at": (service.now()+timedelta(days=1)).isoformat()})
    check("future plan change schedules without immediate activation", result.get("scheduled") and call(owner, "GET", f'/platform/customers/{a["id"]}')["status"] == "trial")
    with platform_factory()() as db:
        pending = db.query(PlatformRecord).filter_by(kind="scheduled_change", tenant_id=a["id"], state="pending").order_by(PlatformRecord.id.desc()).first()
        pending.data = {**pending.data, "effective_at": (service.now()-timedelta(minutes=1)).isoformat()}; db.commit()
    call(owner, "POST", "/platform/operations/run-checks")
    check("due-work applies scheduled plan", call(owner, "GET", f'/platform/customers/{a["id"]}')["status"] == "active")
    action(owner, a["id"], "cancel"); action(owner, a["id"], "offboard")
    for command in ["cancel", "resume", "suspend", "plan", "convert_paid", "resend_invitation", "admin_transfer"]:
        action(owner, a["id"], command, expected=409)
    offboarded = call(owner, "GET", f'/platform/customers/{a["id"]}')
    check("offboarding records retention while preserving company DB", bool(offboarded["config"].get("retention_until")))
    with tenant_session(lookup_route(a["workspace"])) as db:
        check("offboarding preserves user and company rows", db.execute(text("select count(*) from users")).scalar() == 1 and db.execute(text("select count(*) from companies")).scalar() == 1)
    snapshot = call(owner, "GET", f'/platform/records/backup?tenant_id={a["id"]}')[-1]
    action(owner, a["id"], "restore_snapshot", {"snapshot_id": snapshot["id"]})
    # Activate only the second disposable client, then test replacement consent.
    invitation = action(owner, b["id"], "resend_invitation")
    params = parse_qs(urlparse(invitation["url"]).query)
    anonymous = requests.Session(); anonymous.headers["X-Suite-Tenant"] = b["workspace"]
    call(anonymous, "POST", "/auth/reset-password", {"token": params["token"][0], "new_password": PASSWORD})
    old_session = login(b["email"], workspace=b["workspace"])
    replacement = "cmqa1107.replacement@example.com"
    action(owner, b["id"], "admin_transfer", {"email": replacement})
    with platform_factory()() as db:
        mail = db.query(PlatformRecord).filter_by(kind="outbox", tenant_id=b["id"]).order_by(PlatformRecord.id.desc()).limit(2).all()
        tokens = [re.search(r"/platform/public/([A-Za-z0-9_-]+)", r.data["body"]).group(1) for r in mail]
    call(requests.Session(), "POST", "/platform/public/"+tokens[0], {"action": "approve"})
    check("one party cannot complete admin transfer", call(owner, "GET", f'/platform/customers/{b["id"]}')["admin_email"] == b["email"])
    call(requests.Session(), "POST", "/platform/public/"+tokens[1], {"action": "approve"})
    check("two-party consent changes primary admin", call(owner, "GET", f'/platform/customers/{b["id"]}')["admin_email"] == replacement)
    # The original account remains present for attribution but loses company access.
    check("former administrator loses company authorization", old_session.get(BASE+"/access/me", timeout=30).status_code in {401, 403, 404})
    with platform_factory()() as db:
        mail = db.query(PlatformRecord).filter_by(kind="outbox", tenant_id=b["id"]).order_by(PlatformRecord.id.desc()).first()
        url = re.search(r"http://[^\s]+", mail.data["body"]).group(0)
    params = parse_qs(urlparse(url).query)
    check("transferred invite still routes to own tenant", bool(params.get("tenant")))
    call(anonymous, "POST", "/auth/reset-password", {"token": params["token"][0], "new_password": PASSWORD})
    new_session = login(replacement, workspace=b["workspace"])
    check("replacement remains scoped company admin", call(new_session, "GET", "/access/me")["companyId"] == b["company_id"] and not call(new_session, "GET", "/auth/me")["is_superuser"])
    call(new_session, "GET", "/platform/client-directory", expected=401)


if __name__ == "__main__":
    owner = login("owner@indianservers.com", "Admin@123456", platform=True)
    check("owner authenticated independently", call(owner, "GET", "/platform/me")["role"] == "owner")
    fixtures = setup(owner)
    if "--setup" in sys.argv:
        print(json.dumps(fixtures, indent=2)); sys.exit(0)
    try:
        if "--remaining" in sys.argv:
            checks[:] = json.loads(OUT.read_text(encoding="utf-8"))["checks"]
            remaining(owner, fixtures)
        else: run(owner, fixtures)
    finally:
        OUT.write_text(json.dumps({"fixtures": fixtures, "checks": checks, "passed": sum(x["passed"] for x in checks), "failed": sum(not x["passed"] for x in checks)}, indent=2), encoding="utf-8")
        print(json.dumps({"checks": len(checks), "failed": sum(not x["passed"] for x in checks)}), flush=True)
