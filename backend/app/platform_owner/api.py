"""Indian Servers operator API. All private endpoints use platform-only identity."""
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
import csv
import io
import json
import secrets
import statistics
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy import String, cast, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_db
from app.core.security import get_password_hash
from app.platform_owner.auth import current_platform_admin
from app.platform_owner.models import PlatformAdmin, PlatformEvent, PlatformPlan, PlatformRecord, PlatformSession, PlatformSignupRequest as Signup, PlatformTenant
from app.platform_owner.session import get_platform_db
from app.platform_owner import service as s
from app.access.signup import SignupInput, ReviewInput, review_signup, available_modules

router = APIRouter(prefix="/platform", tags=["Indian Servers Platform Owner"])


@router.get("/databases")
def tenant_databases(actor=Depends(current_platform_admin),db: Session=Depends(get_platform_db)):
    from app.platform_owner.models import PlatformTenantDatabase as D,PlatformDatabaseServer as S
    from app.core.config import settings
    s.require(actor,"settings.manage")
    result=[]
    for row,server in db.query(D,S).join(S,S.id==D.server_id).order_by(D.id.desc()):
        signup=db.get(Signup,row.signup_id)
        result.append({**s.encode(row),"company_name":signup.company_name if signup else "Unknown company",
            "server_name":server.name,"host":server.host,"port":server.port,
            "login_url":settings.FRONTEND_PUBLIC_URL.rstrip("/")+"/login?tenant="+row.workspace_code})
    return result


@router.get("/database-servers")
def database_servers(actor=Depends(current_platform_admin),db: Session=Depends(get_platform_db)):
    from app.platform_owner.models import PlatformTenantDatabase as D,PlatformDatabaseServer as S
    s.require(actor,"settings.manage")
    return [{**s.encode(server),"database_count":db.query(D).filter_by(server_id=server.id).count()} for server in db.query(S).order_by(S.id)]


@router.post("/databases/{ident}/check")
def check_database(ident:int,actor=Depends(current_platform_admin),db: Session=Depends(get_platform_db)):
    from app.platform_owner.models import PlatformTenantDatabase as D
    from app.db.tenant import lookup_route,tenant_session
    from sqlalchemy import text
    s.require(actor,"settings.manage")
    row=db.get(D,ident)
    if not row:raise HTTPException(404,"Company database not found")
    with tenant_session(lookup_route(row.tenant_uuid)) as company:
        identity=company.execute(text("SELECT current_database(),current_user")).one()
        companies=company.execute(text("SELECT count(*) FROM companies")).scalar()
    return {"healthy":True,"database_name":identity[0],"runtime_role":identity[1],"company_count":companies,"tenant_uuid":row.tenant_uuid}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Change(Input):
    action: str = Field(min_length=1, max_length=50)
    reason: str = Field(min_length=3, max_length=1000)
    values: dict = Field(default_factory=dict)


class SignupCreate(SignupInput):
    source: str = Field(default="manual", min_length=1, max_length=80)
    campaign: str = Field(default="", max_length=120)
    consent_evidence: str = Field(min_length=5, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class SignupEdit(Input):
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)
    name: str | None = Field(default=None, min_length=2, max_length=150)
    company_name: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=5, max_length=20)
    source: str | None = Field(default=None, min_length=1, max_length=80)
    campaign: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    requested_modules: list[str] | None = Field(default=None, min_length=1, max_length=5)
    tags: list[str] | None = Field(default=None, max_length=20)
    assigned_to: int | None = None
    priority: Literal["low", "normal", "high"] | None = None
    checklist: dict[str, bool] | None = None


class Bulk(Input):
    ids: list[int] = Field(min_length=1, max_length=100)
    action: Literal["archive", "restore", "assign", "under_review"]
    reason: str = Field(min_length=3, max_length=1000)
    assigned_to: int | None = None
    preview: bool = True
    versions: dict[str, int] = Field(default_factory=dict)


def validate_assignee(db, ident):
    if ident is not None and (isinstance(ident, bool) or not isinstance(ident, int) or not 1 <= ident <= 2147483647):
        raise HTTPException(422, "Choose an active platform staff member")
    if ident is not None and not db.query(PlatformAdmin).filter_by(id=ident, is_active=True).first():
        raise HTTPException(422, "Choose an active platform staff member")


def signup_dict(db, row):
    result = s.encode(row)
    result["duplicates"] = s.duplicate_candidates(db, row)
    result["age_hours"] = s.business_hours_between(row.created_at, row.reviewed_at or s.now(), s.settings_for(db))
    result["overdue"] = row.status in s.REVIEWABLE and result["age_hours"] > s.settings_for(db)["sla_hours"]
    return result


@router.get("/me")
def me(actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    return {**s.encode(actor), "permissions": sorted(s.permissions(actor)), "session_id": getattr(actor, "_platform_session", None),
            "settings": s.settings_for(db), "modules": available_modules(), "roles": list(s.ROLES),
            "role_permissions": {key: sorted(value) for key,value in s.ROLES.items()}, "available_permissions": sorted(s.ALL_PERMISSIONS)}


@router.patch("/profile")
def profile(data: Change, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    if getattr(actor, "_api_scopes", None) is not None:
        raise HTTPException(403, "Interactive platform session required")
    before = s.encode(actor)
    if data.action == "profile":
        name = str(data.values.get("name", "")).strip()
        if not 2 <= len(name) <= 150:
            raise HTTPException(422, "Enter a name between 2 and 150 characters")
        actor.name = name
    elif data.action == "preferences":
        allowed = {"timezone", "date_format", "default_page", "page_size", "favorites", "email_notifications", "compact_rows"}
        if set(data.values)-allowed:
            raise HTTPException(422, "Unknown preference")
        if "page_size" in data.values and (not isinstance(data.values["page_size"],int) or data.values["page_size"] not in {10,25,50,100}): raise HTTPException(422,"Choose 10, 25, 50 or 100 rows per page")
        if "favorites" in data.values and (not isinstance(data.values["favorites"],list) or len(data.values["favorites"])>12 or not all(isinstance(x,str) for x in data.values["favorites"]) or not set(data.values["favorites"]) <= {"overview","signups","customers","plans","team","tasks","communications","reports","operations","audit","settings","profile","databases"}):
            raise HTTPException(422,"Unknown navigation favorite")
        actor.preferences = {**actor.preferences, **data.values}
    else:
        raise HTTPException(422, "Unknown profile action")
    s.event(db, actor, "profile.updated", "staff", actor.id, data.reason,before,s.encode(actor))
    db.commit()
    return s.encode(actor)


@router.get("/sessions")
def sessions(actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    return [s.encode(row) for row in db.query(PlatformSession).filter_by(admin_id=actor.id).order_by(PlatformSession.created_at.desc()).limit(100)]


@router.post("/sessions/revoke")
def revoke_sessions(data: Change, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    query = db.query(PlatformSession).filter_by(admin_id=actor.id)
    if data.values.get("id"):
        query = query.filter_by(id=data.values["id"])
    elif data.action == "others":
        query = query.filter(PlatformSession.id != getattr(actor, "_platform_session", None))
    elif data.action != "all":
        raise HTTPException(422, "Choose one session, other sessions, or all sessions")
    count = query.update({"status": "revoked"}, synchronize_session=False)
    s.event(db, actor, "sessions.revoked", "staff", actor.id, data.reason, after={"count": count})
    db.commit()
    return {"revoked": count}


@router.get("/signups")
def list_signups(status: str = "active", search: str = Query("", max_length=180), applicant_type: str = "",
                 source: str = "", module: str = "", assignee: int | None = None,
                 start: datetime | None = None, end: datetime | None = None, priority: str = "",
                 page: int = Query(1, ge=1), page_size: int = Query(25, ge=10, le=100),
                 actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "signup.read")
    query = s.scoped(db.query(Signup).filter(Signup.deleted_at.is_(None)), actor, Signup)
    if status == "active": query = query.filter(Signup.archived_at.is_(None))
    elif status != "all": query = query.filter(Signup.status == status)
    if applicant_type: query = query.filter(Signup.applicant_type == applicant_type)
    if source: query = query.filter(Signup.source == source)
    if assignee == 0: query = query.filter(Signup.assigned_to.is_(None))
    elif assignee: query = query.filter(Signup.assigned_to == assignee)
    if start: query = query.filter(Signup.created_at >= start)
    if end: query = query.filter(Signup.created_at <= end)
    if module: query = query.filter(cast(Signup.requested_modules, String).contains('"'+module+'"'))
    if search:
        query = query.filter(or_(*[col.ilike("%"+search+"%") for col in [Signup.name, Signup.company_name, Signup.email, Signup.phone, Signup.campaign]]))
    if priority: query = query.filter(cast(Signup.workflow, String).contains('"'+priority+'"'))
    total = query.count()
    rows = query.order_by(Signup.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"items": [signup_dict(db, row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/signups", status_code=201)
def create_signup(data: SignupCreate, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "signup.create")
    if db.query(Signup.id).filter_by(email=str(data.email).lower()).first():
        raise HTTPException(409, "A signup already uses this email")
    row = Signup(**data.model_dump(exclude={"consent", "website"}), assigned_to=actor.id)
    db.add(row); db.flush()
    s.event(db, actor, "signup.created", "signup", row.id, data.consent_evidence)
    db.commit()
    return signup_dict(db, row)


@router.get("/signups/{ident}")
def signup_detail(ident: int, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    row = s.signup_for(db, actor, ident)
    history = db.query(PlatformEvent).filter_by(entity="signup", entity_id=ident).order_by(PlatformEvent.id.desc()).limit(100)
    records = db.query(PlatformRecord).filter(PlatformRecord.signup_id == ident, PlatformRecord.kind.in_(["note", "task", "provisioning", "customer_invitation"]))
    return {**signup_dict(db, row), "history": [s.encode(r) for r in history], "records": [s.encode(r) for r in records]}


@router.patch("/signups/{ident}")
def edit_signup(ident: int, data: SignupEdit, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    row = s.signup_for(db, actor, ident, "signup.edit", lock=True)
    if row.version != data.version: raise HTTPException(409, "This signup changed. Refresh before saving.")
    if row.status not in s.REVIEWABLE: raise HTTPException(409, "Only pending applications can be edited")
    values = data.model_dump(exclude_unset=True, exclude={"version", "reason"})
    before = s.encode(row)
    if "assigned_to" in values: validate_assignee(db, values["assigned_to"])
    if values.get("requested_modules") and not set(values["requested_modules"]) <= {m["key"] for m in available_modules()}:
        raise HTTPException(422, "Choose installed applications")
    if values.get("phone"):
        from app.core.input_validation import normalize_phone
        values["phone"] = normalize_phone(values["phone"], row.phone_country_code)[0]
    if values.get("email"):
        values["email"] = str(values["email"]).lower()
        if db.query(Signup.id).filter(Signup.email == values["email"], Signup.id != row.id).first():
            raise HTTPException(409, "A signup already uses this email")
    if row.applicant_type == "company" and "company_name" in values and not values["company_name"]:
        raise HTTPException(422, "Company name is required")
    workflow = {**row.workflow}
    for key in ["priority", "checklist"]:
        if key in values:
            if values[key] is None: raise HTTPException(422, "Required fields cannot be cleared")
            workflow[key] = values.pop(key)
    for key, value in values.items():
        if value is None and key not in {"assigned_to", "company_name"}: raise HTTPException(422, "Required fields cannot be cleared")
        setattr(row, key, value)
    row.workflow, row.version = workflow, row.version+1
    s.event(db, actor, "signup.edited", "signup", row.id, data.reason, before, s.encode(row))
    db.commit()
    return signup_dict(db, row)


def apply_signup_action(db, actor, row, action, reason, values):
    before = s.encode(row)
    if action == "archive":
        s.require(actor, "signup.archive")
        if row.archived_at: raise HTTPException(409, "Already archived")
        row.previous_status, row.status, row.archived_at = row.status, "archived", s.now()
    elif action == "restore":
        s.require(actor, "signup.archive")
        if not row.archived_at: raise HTTPException(409, "This request is not archived")
        row.status, row.archived_at = row.previous_status or "pending", None
    elif action == "assign":
        s.require(actor, "signup.edit"); validate_assignee(db, values.get("assigned_to"))
        row.assigned_to = values.get("assigned_to")
    elif action in {"under_review", "pending", "withdrawn"}:
        s.require(actor, "signup.edit")
        if row.status not in s.REVIEWABLE | {"withdrawn"}: raise HTTPException(409, "This review is already complete")
        row.status = action
    elif action == "legal_hold":
        s.require(actor, "signup.delete")
        if not isinstance(values.get("enabled"), bool): raise HTTPException(422, "Legal hold enabled must be a boolean")
        row.legal_hold = values["enabled"]
    elif action == "delete":
        s.require(actor, "signup.delete")
        retention = s.settings_for(db)["retention_days"]
        if row.legal_hold or not row.archived_at or s.aware(row.archived_at)+timedelta(days=retention) > s.now() or row.company_id:
            raise HTTPException(409, "Deletion requires an archived, non-customer request past retention with no legal hold")
        # Preserve decision evidence and IDs while purging contact data and notes.
        row.name, row.company_name, row.email = "Deleted applicant", None, f"deleted-signup-{row.id}@example.com"
        row.phone, row.notes, row.tags, row.consent_evidence, row.workflow = "", "", [], "Retention purge", {}
        row.deleted_at = s.now()
        row.source, row.campaign, row.review_reason = "purged", "", "Retention purge"
        for record in db.query(PlatformRecord).filter_by(signup_id=row.id):
            db.query(PlatformEvent).filter_by(entity="record",entity_id=record.id).update({"before":{},"after":{},"reason":"Contact data purged after retention"})
            record.data, record.title, record.token_hash, record.state = {}, "Deleted applicant record", None, "purged"
        # Prior edits may contain contact values; purge them using an explicit retention operation.
        db.query(PlatformEvent).filter_by(entity="signup", entity_id=row.id).update({"before": {}, "after": {}, "reason": "Contact data purged after retention"})
        from app.platform_owner.models import PlatformAudit
        db.query(PlatformAudit).filter_by(signup_id=row.id).update({"reason": "Contact data purged after retention"})
        before = {"id": row.id, "status": before["status"]}
    else: raise HTTPException(422, "Unknown signup action")
    row.version += 1
    s.event(db, actor, "signup."+action, "signup", row.id, reason, before, s.encode(row))


@router.post("/signups/{ident}/action")
def signup_action(ident: int, data: Change, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    row = s.signup_for(db, actor, ident, lock=True)
    apply_signup_action(db, actor, row, data.action, data.reason, data.values)
    db.commit()
    return s.encode(row)


@router.post("/signup-bulk")
def bulk(data: Bulk, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    rows, errors = [], []
    for ident in sorted(set(data.ids)):
        try:
            row = s.signup_for(db, actor, ident, lock=not data.preview)
            s.require(actor, "signup.archive" if data.action in {"archive", "restore"} else "signup.edit")
            if data.action == "restore" and not row.archived_at: raise HTTPException(409, "Not archived")
            if data.action == "archive" and row.archived_at: raise HTTPException(409, "Already archived")
            if data.action == "under_review" and row.status not in s.REVIEWABLE: raise HTTPException(409, "Review complete")
            if not data.preview and data.versions.get(str(ident)) != row.version: raise HTTPException(409, "Changed since preview")
            rows.append(row)
        except HTTPException as exc: errors.append({"id": ident, "error": exc.detail})
    validate_assignee(db, data.assigned_to)
    preview = {"items": [{"id": r.id, "name": r.company_name or r.name, "status": r.status, "version": r.version} for r in rows], "errors": errors}
    if data.preview: return preview
    if errors: raise HTTPException(409, {"message": "Nothing changed. Resolve preview errors first.", **preview})
    for row in rows: apply_signup_action(db, actor, row, data.action, data.reason, {"assigned_to": data.assigned_to})
    db.commit()
    return {"changed": len(rows)}


@router.post("/signups/{ident}/review")
def review(ident: int, data: ReviewInput, request: Request, actor=Depends(current_platform_admin),
           db: Session = Depends(get_platform_db), business: Session = Depends(get_db)):
    try:
        return review_signup(ident, data, request, actor, db, business)
    except HTTPException as exc:
        if exc.status_code in {409, 422}:
            row = s.signup_for(db, actor, ident, "signup.review")
            db.add(PlatformRecord(kind="provisioning", title="Review needs attention", state="failed", owner_id=actor.id,
                signup_id=row.id, data={"error": str(exc.detail), "review": data.model_dump(), "retryable": row.status in s.REVIEWABLE}))
            db.commit()
        raise


@router.post("/signups/{ident}/request-info")
def request_info(ident: int, data: Change, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    row = s.signup_for(db, actor, ident, "signup.edit", lock=True)
    if row.status not in s.REVIEWABLE: raise HTTPException(409, "Review already complete")
    record, url = s.issue_link(db, "correction", "Please update your trial application", row.email, actor, signup_id=row.id,
                              data={"message": data.reason})
    row.status, row.version = "awaiting_applicant", row.version+1
    s.event(db, actor, "signup.information_requested", "signup", row.id, data.reason)
    db.commit()
    return {"url": url, "expires_at": record.expires_at}


@router.post("/signups/{ident}/tracking-link")
def tracking_link(ident: int, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    row = s.signup_for(db, actor, ident)
    record, url = s.issue_link(db, "tracking", "Your private trial application status", row.email, actor, signup_id=row.id, hours=24*30)
    s.event(db, actor, "signup.tracking_link", "signup", row.id)
    db.commit()
    return {"url": url, "expires_at": record.expires_at}


@router.get("/signup-export")
def export_signups(actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "signup.export")
    rows = s.scoped(db.query(Signup).filter(Signup.deleted_at.is_(None)), actor, Signup).order_by(Signup.id).limit(10000)
    output = io.StringIO(); writer = csv.writer(output)
    fields = ["id", "applicant_type", "name", "company_name", "email", "phone", "status", "source", "campaign", "created_at"]
    writer.writerow(fields)
    count = 0
    for row in rows:
        writer.writerow([s.safe_csv(getattr(row, field)) for field in fields]); count += 1
    s.event(db, actor, "signup.exported", reason="CSV download", after={"count": count}); db.commit()
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="platform-signups.csv"'})


class StaffInvite(Input):
    email: EmailStr
    name: str = Field(min_length=2, max_length=150)
    role: Literal["owner", "reviewer", "sales", "support", "billing", "analyst"]
    assigned_only: bool = False
    permissions: list[str] = Field(default_factory=list)


@router.get("/staff-directory")
def directory(actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    return [{"id": r.id, "name": r.name, "role": r.role} for r in db.query(PlatformAdmin).filter_by(is_active=True)]


@router.get("/staff")
def staff(actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "staff.manage")
    return [s.encode(r) for r in db.query(PlatformAdmin).order_by(PlatformAdmin.id)]


@router.post("/staff/invite")
def invite_staff(data: StaffInvite, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "staff.manage")
    if not set(data.permissions) <= s.ROLES[data.role]: raise HTTPException(422, "Permissions cannot exceed the selected role")
    email = str(data.email).lower()
    if db.query(PlatformAdmin).filter_by(email=email).first(): raise HTTPException(409, "An owner portal account already uses this email")
    record, url = s.issue_link(db, "staff_invitation", "Join the Indian Servers owner team", email, actor, data=data.model_dump(mode="json"))
    s.event(db, actor, "staff.invited", "record", record.id, after={"email": email, "role": data.role})
    db.commit()
    return {"id": record.id, "url": url, "expires_at": record.expires_at}


@router.patch("/staff/{ident}")
def change_staff(ident: int, data: Change, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "staff.manage")
    owners = db.query(PlatformAdmin).filter_by(role="owner", is_active=True).with_for_update().all()
    row = db.get(PlatformAdmin, ident)
    if not row: raise HTTPException(404, "Staff member not found")
    before = s.encode(row)
    if data.action == "access":
        values = data.values
        role = values.get("role", row.role)
        if not isinstance(role,str) or role not in s.ROLES: raise HTTPException(422, "Unknown role")
        for flag in ["is_active", "assigned_only"]:
            if flag in values and not isinstance(values[flag],bool): raise HTTPException(422, f"{flag} must be a boolean")
        active = values.get("is_active", row.is_active)
        overrides = values.get("permissions", [])
        if not isinstance(overrides, list) or not all(isinstance(x,str) for x in overrides) or not set(overrides) <= s.ROLES[role]: raise HTTPException(422, "Invalid permission override")
        if row.role == "owner" and row.is_active and len(owners) <= 1 and (role != "owner" or not active or (values.get("permissions") and "staff.manage" not in values["permissions"])):
            raise HTTPException(409, "Keep at least one active platform owner")
        row.role, row.is_active, row.permissions, row.assigned_only = role, active, overrides, bool(values.get("assigned_only", row.assigned_only))
        row.token_version += 1
        db.query(PlatformSession).filter_by(admin_id=row.id).update({"status": "revoked"})
    elif data.action == "review": row.reviewed_at = s.now()
    else: raise HTTPException(422, "Unknown staff operation")
    s.event(db, actor, "staff."+data.action, "staff", row.id, data.reason, before, s.encode(row))
    db.commit()
    return s.encode(row)


RECORD_READ = {"view": None, "template": "signup.read", "task": None, "note": None, "notification": None,
    "outbox": "signup.review", "provisioning": "signup.review", "customer_invitation": "signup.review", "staff_invitation": "staff.manage",
    "password_reset": "staff.manage", "api_key": "settings.manage", "support": "tools.manage", "backup": "tenant.manage",
    "billing_entry": "billing.read", "scheduled_report": "reports.read", "report_snapshot": "reports.read",
    "scheduled_change": "billing.read", "escalation": "signup.review", "admin_transfer": "tenant.manage", "support_consent": "tools.manage"}
RECORD_WRITE = {"view": None, "template": "signup.review", "task": None, "note": None, "support": "tools.manage", "scheduled_report": "reports.read"}


def record_access(db, actor, row):
    if row.kind == "notification" and row.owner_id not in {None, actor.id}:
        raise HTTPException(404, "Notification not found")
    if row.kind == "outbox":
        s.require(actor,row.data.get("permission", "staff.manage" if not row.signup_id and not row.tenant_id else "signup.review"))
    if row.signup_id: s.signup_for(db, actor, row.signup_id)
    if row.tenant_id: s.tenant_for(db, actor, row.tenant_id)
    if row.kind in {"view", "task", "notification", "scheduled_report", "report_snapshot"} and row.owner_id not in {None, actor.id} and actor.role != "owner":
        raise HTTPException(404, "Record not found")
    if row.kind == "view" and row.owner_id != actor.id and not row.data.get("shared"):
        raise HTTPException(404, "View not found")


@router.get("/records/{kind}")
def list_records(kind: str, signup_id: int | None = None, tenant_id: int | None = None,
                 actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    if kind not in RECORD_READ: raise HTTPException(404, "Unknown record type")
    if RECORD_READ[kind]: s.require(actor, RECORD_READ[kind])
    query = db.query(PlatformRecord).filter_by(kind=kind)
    if signup_id: s.signup_for(db, actor, signup_id); query = query.filter_by(signup_id=signup_id)
    if tenant_id: s.tenant_for(db, actor, tenant_id); query = query.filter_by(tenant_id=tenant_id)
    result = []
    for row in query.order_by(PlatformRecord.id.desc()).limit(500):
        try: record_access(db, actor, row)
        except HTTPException: continue
        result.append(s.encode(row))
    return result


class RecordInput(Input):
    title: str = Field(min_length=2, max_length=180)
    signup_id: int | None = None
    tenant_id: int | None = None
    owner_id: int | None = None
    data: dict = Field(default_factory=dict)


def validate_record_data(kind, values):
    if not isinstance(values, dict) or len(json.dumps(values)) > 16000:
        raise HTTPException(422, "Record data is too large or invalid")
    if kind == "scheduled_report" and values.get("frequency", "daily") not in {"daily", "weekly"}:
        raise HTTPException(422, "Choose daily or weekly reports")
    for key in ["due_at", "next_run_at"]:
        if values.get(key):
            try: datetime.fromisoformat(values[key])
            except (ValueError, TypeError): raise HTTPException(422, f"Invalid {key}") from None
    if kind == "view":
        filters = values.get("filters", {})
        if not isinstance(filters, dict) or set(filters)-{"status","search","applicant_type","source","module","assignee","start","end","priority"}:
            raise HTTPException(422, "Unknown saved-view filter")


@router.post("/records/{kind}", status_code=201)
def create_record(kind: str, data: RecordInput, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    if kind not in RECORD_WRITE: raise HTTPException(422, "This record type is managed by its own workflow")
    if RECORD_WRITE[kind]: s.require(actor, RECORD_WRITE[kind])
    if data.signup_id: s.signup_for(db, actor, data.signup_id, "signup.edit")
    if data.tenant_id: s.tenant_for(db, actor, data.tenant_id)
    if kind in {"note", "support"} and not (data.signup_id or data.tenant_id): raise HTTPException(422, "Link this record to a signup or customer")
    validate_assignee(db, data.owner_id)
    owner = data.owner_id or actor.id
    if owner != actor.id and actor.role not in {"owner", "reviewer"}: raise HTTPException(403, "Only owners or reviewers can assign tasks")
    if kind == "view" and data.data.get("shared") and actor.role != "owner": raise HTTPException(403, "Only owners can share views")
    validate_record_data(kind, data.data)
    row = PlatformRecord(kind=kind, title=data.title, owner_id=owner, signup_id=data.signup_id, tenant_id=data.tenant_id, data=data.data)
    db.add(row); db.flush(); s.event(db, actor, kind+".created", "record", row.id,after=s.encode(row))
    if kind == "task" and owner != actor.id: s.notify(db, "New assigned task", data.title, owner_id=owner)
    db.commit()
    return s.encode(row)


@router.post("/record/{ident}/action")
def record_action(ident: int, data: Change, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    row = db.query(PlatformRecord).filter_by(id=ident).with_for_update().first()
    if not row or row.kind not in RECORD_READ: raise HTTPException(404, "Record not found")
    if RECORD_READ[row.kind]: s.require(actor, RECORD_READ[row.kind])
    record_access(db, actor, row)
    before = s.encode(row,exclude={"data"} if row.kind not in RECORD_WRITE else ())
    if row.kind == "notification" and data.action == "read": row.state = "read"
    elif row.kind in RECORD_WRITE:
        if RECORD_WRITE[row.kind]: s.require(actor, RECORD_WRITE[row.kind])
        if row.kind in {"note", "view", "scheduled_report"} and row.owner_id != actor.id and actor.role != "owner": raise HTTPException(403, "Only its author or an owner can edit this record")
        if data.action == "complete": row.state = "completed"
        elif data.action == "reopen": row.state = "open"
        elif data.action == "archive": row.state = "archived"
        elif data.action == "edit":
            title = str(data.values.get("title", row.title))
            if not 2 <= len(title) <= 180: raise HTTPException(422, "Title must have 2–180 characters")
            changes = data.values.get("data", {})
            if not isinstance(changes,dict): raise HTTPException(422, "Record data must be an object")
            updated = {**row.data, **changes}
            validate_record_data(row.kind, updated)
            row.title, row.data = title, updated
            if "owner_id" in data.values:
                if actor.role not in {"owner","reviewer"}: raise HTTPException(403,"This role cannot reassign team work")
                validate_assignee(db,data.values["owner_id"])
                row.owner_id=data.values["owner_id"]
        else: raise HTTPException(422, "Unknown record operation")
    elif row.kind == "outbox" and data.action in {"preview_delivered", "retry"}:
        row.state = "preview_delivered" if data.action == "preview_delivered" else "queued_local"
        row.data = {**row.data, "attempts": row.data.get("attempts", 0)+1,
                    "preview_delivered_at": s.now().isoformat() if data.action == "preview_delivered" else None}
    elif row.kind in {"staff_invitation", "api_key", "password_reset"} and data.action == "revoke":
        row.state, row.token_hash = "revoked", None
    else: raise HTTPException(422, "Use the relevant workflow for this record")
    s.event(db, actor, row.kind+"."+data.action, "record", row.id, data.reason,before,
            s.encode(row,exclude={"data"} if row.kind not in RECORD_WRITE else ())); db.commit()
    return s.encode(row)


class ApiKeyInput(Input):
    title: str = Field(min_length=2, max_length=100)
    days: int = Field(default=30, ge=1, le=365)
    scopes: list[str] = Field(min_length=1)


@router.post("/api-keys")
def api_key(data: ApiKeyInput, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "settings.manage")
    if not set(data.scopes) <= {"signup.read", "signup.create", "reports.read", "tenant.read"}: raise HTTPException(422, "API keys support read-only reporting and signup intake scopes")
    raw = "po_"+secrets.token_urlsafe(36)
    row = PlatformRecord(kind="api_key", title=data.title, state="active", owner_id=actor.id, token_hash=s.digest(raw),
        data={"scopes": data.scopes, "prefix": raw[:10]}, expires_at=s.now()+timedelta(days=data.days))
    db.add(row); s.event(db, actor, "api_key.created", after={"title": data.title, "scopes": data.scopes}); db.commit()
    return {"id": row.id, "key": raw, "expires_at": row.expires_at}


@router.get("/events")
def events(search: str = "", page: int = Query(1, ge=1), actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "audit.read")
    query = db.query(PlatformEvent)
    if search: query = query.filter(PlatformEvent.action.ilike("%"+search[:100]+"%"))
    return {"items": [s.encode(r) for r in query.order_by(PlatformEvent.id.desc()).offset((page-1)*50).limit(50)], "total": query.count()}


@router.get("/login-history")
def login_history(actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    query = db.query(PlatformEvent).filter(PlatformEvent.action.in_(["login.success", "login.failed", "sessions.revoked"]))
    if actor.role != "owner": query = query.filter_by(admin_id=actor.id)
    return [s.encode(r) for r in query.order_by(PlatformEvent.id.desc()).limit(100)]


@router.get("/search")
def global_search(q: str = Query(min_length=2, max_length=100), actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    result = {"signups": [], "customers": []}
    if "signup.read" in s.permissions(actor):
        result["signups"] = [{"id": r.id, "name": r.company_name or r.name, "status": r.status} for r in
            s.scoped(db.query(Signup).filter(Signup.deleted_at.is_(None), or_(Signup.name.ilike("%"+q+"%"), Signup.email.ilike("%"+q+"%"), Signup.company_name.ilike("%"+q+"%"))), actor, Signup).limit(15)]
    if "tenant.read" in s.permissions(actor):
        result["customers"] = [{"id": r.id, "name": r.name, "status": r.status} for r in
            s.scoped(db.query(PlatformTenant).filter(PlatformTenant.name.ilike("%"+q+"%")), actor, PlatformTenant).limit(15)]
    return result


@router.get("/settings")
def settings_get(actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "settings.manage"); return s.settings_for(db)


@router.put("/settings")
def settings_save(data: Change, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    s.require(actor, "settings.manage")
    values = {**s.settings_for(db), **data.values}
    if set(values)-set(s.DEFAULT_SETTINGS): raise HTTPException(422, "Unknown setting")
    bounds = {"trial_days": (1,90), "seats": (1,10000), "storage_mib": (100,1048576), "sla_hours": (1,720),
              "retention_days": (1,3650), "idle_minutes": (15,480), "business_start": (0,23), "business_end": (1,24), "grace_days": (0,30)}
    for key, (low, high) in bounds.items():
        if not isinstance(values[key], int) or isinstance(values[key], bool) or not low <= values[key] <= high:
            raise HTTPException(422, f"Invalid {key}")
    if values["business_start"] >= values["business_end"]: raise HTTPException(422, "Business end must follow business start")
    if not isinstance(values["business_days"], list) or not values["business_days"] or not all(isinstance(day,int) and not isinstance(day,bool) for day in values["business_days"]) or not set(values["business_days"]) <= set(range(7)):
        raise HTTPException(422, "Choose at least one business weekday")
    try: ZoneInfo(values["timezone"])
    except (ZoneInfoNotFoundError, TypeError): raise HTTPException(422, "Unknown timezone") from None
    for key in ["require_checklist", "notify_new_signup"]:
        if not isinstance(values[key], bool): raise HTTPException(422, f"Invalid {key}")
    row = db.query(PlatformRecord).filter_by(kind="settings").first()
    if not row: row = PlatformRecord(kind="settings", title="Portal settings", data={}); db.add(row)
    before = row.data; row.data = values
    s.event(db, actor, "settings.updated", reason=data.reason, before=before, after=values); db.commit()
    return values


class PlanInput(Input):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    modules: list[str] = Field(min_length=1, max_length=5)
    seats: int = Field(ge=1, le=10000)
    storage_mib: int = Field(ge=100, le=1048576)
    monthly_price_minor: int = Field(ge=0, le=1000000000)
    currency: Literal["INR", "USD", "AED"] = "INR"
    active: bool = True


@router.get("/plans")
def plans(actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    if not {"signup.review", "billing.read", "billing.manage", "tenant.read"}.intersection(s.permissions(actor)):
        raise HTTPException(403, "Plan access required")
    return [s.encode(r) for r in db.query(PlatformPlan).order_by(PlatformPlan.id)]


@router.post("/plans", status_code=201)
def plan_create(data: PlanInput, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "billing.manage")
    if db.query(PlatformPlan.id).filter_by(code=data.code).first(): raise HTTPException(409, "Plan code already exists")
    if not set(data.modules) <= {m["key"] for m in available_modules()}: raise HTTPException(422, "Choose installed modules")
    row = PlatformPlan(code=data.code, name=data.name, active=data.active, config=data.model_dump(exclude={"code", "name", "active"}))
    db.add(row); db.flush(); s.event(db, actor, "plan.created", "plan", row.id, after=s.encode(row)); db.commit()
    return s.encode(row)


@router.put("/plans/{ident}")
def plan_edit(ident: int, data: PlanInput, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "billing.manage")
    row = db.get(PlatformPlan, ident)
    if not row: raise HTTPException(404, "Plan not found")
    if db.query(PlatformPlan.id).filter(PlatformPlan.code == data.code, PlatformPlan.id != ident).first(): raise HTTPException(409, "Plan code already exists")
    if not set(data.modules) <= {m["key"] for m in available_modules()}: raise HTTPException(422, "Choose installed modules")
    before = s.encode(row)
    row.code, row.name, row.active, row.config = data.code, data.name, data.active, data.model_dump(exclude={"code", "name", "active"})
    s.event(db, actor, "plan.updated", "plan", row.id, "Plan catalogue changed; existing contracts retain their effective configuration", before, s.encode(row))
    db.commit(); return s.encode(row)


@router.get("/customers")
def customers(search: str = "", status: str = "", actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    s.require(actor, "tenant.read")
    query = s.scoped(db.query(PlatformTenant), actor, PlatformTenant)
    if search: query = query.filter(or_(PlatformTenant.name.ilike("%"+search[:150]+"%"), PlatformTenant.admin_email.ilike("%"+search[:150]+"%")))
    if status: query = query.filter_by(status=status)
    return [s.encode(r) for r in query.order_by(PlatformTenant.id.desc()).limit(1000)]


@router.get("/customers/{ident}")
def customer(ident: int, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    row = s.tenant_for(db, actor, ident)
    return {**s.encode(row), "history": [s.encode(e) for e in db.query(PlatformEvent).filter_by(entity="tenant", entity_id=ident).order_by(PlatformEvent.id.desc()).limit(100)]}


def int_value(values, key, default, low, high):
    value = values.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise HTTPException(422, f"{key} must be an integer between {low} and {high}")
    return value


@router.post("/customers/{ident}/action")
def customer_action(ident: int, data: Change, actor=Depends(current_platform_admin),
                    db: Session = Depends(get_platform_db), business: Session = Depends(get_db)):
    from app.platform_owner import bridge
    row = s.tenant_for(db, actor, ident, "billing.manage" if data.action in {"convert_paid", "plan", "payment"} else "tools.manage" if data.action == "support_request" else "tenant.manage", lock=True)
    before, config, status = s.encode(row), {**row.config}, row.status
    result = {}
    if data.action == "sync_usage":
        row.usage = bridge.usage(business, row)
        if row.usage["activated"] and not config.get("activated_at"): config["activated_at"] = s.now().isoformat()
        for invitation in db.query(PlatformRecord).filter_by(kind="customer_invitation", signup_id=row.signup_id):
            if row.usage["activated"]: invitation.state = "accepted"
            elif invitation.expires_at and s.aware(invitation.expires_at) < s.now(): invitation.state = "expired"
    elif data.action == "extend_trial":
        if status != "trial": raise HTTPException(409, "Only trials can be extended")
        days = int_value(data.values, "days", 7, 1, 90)
        old_end = s.aware(datetime.fromisoformat(config["trial_ends_at"]))
        end = max(s.now(), old_end)+timedelta(days=days)
        config["trial_ends_at"], config["grace_until"] = end.isoformat(), (end+timedelta(days=s.settings_for(db)["grace_days"])).isoformat()
    elif data.action in {"plan", "convert_paid"}:
        plan = db.get(PlatformPlan, int_value(data.values, "plan_id", 0, 1, 2147483647))
        if not plan or not plan.active: raise HTTPException(422, "Select an active platform plan")
        effective = data.values.get("effective_at")
        if effective:
            try: effective_date = s.aware(datetime.fromisoformat(effective))
            except (ValueError, TypeError): raise HTTPException(422, "Invalid effective date") from None
            if effective_date > s.now():
                db.add(PlatformRecord(kind="scheduled_change", title=f"Plan change for {row.name}", state="pending", owner_id=actor.id,
                    tenant_id=row.id, data={"plan_id": plan.id, "effective_at": effective_date.isoformat(), "reason": data.reason, "convert_paid": data.action == "convert_paid"}))
                s.event(db, actor, "tenant.plan_scheduled", "tenant", row.id, data.reason, after={"plan_id": plan.id, "effective_at": effective})
                db.commit(); return {"scheduled": True}
        used = bridge.usage(business, row)
        if used["seats"] > plan.config["seats"] or used["storage_bytes"] > plan.config["storage_mib"]*1048576:
            raise HTTPException(409, "Current usage exceeds this plan; reduce usage or choose another plan")
        config.update(plan.config); row.plan_id = plan.id
        if data.action == "convert_paid":
            status = "active"; config["paid_at"] = config.get("paid_at") or s.now().isoformat()
    elif data.action == "entitlements":
        config["seats"] = int_value(data.values, "seats", config.get("seats", 5), 1, 10000)
        config["storage_mib"] = int_value(data.values, "storage_mib", config.get("storage_mib", 1024), 100, 1048576)
        modules = data.values.get("modules", config["modules"])
        if not isinstance(modules, list) or not modules or not all(isinstance(m,str) for m in modules) or not set(modules) <= {m["key"] for m in available_modules()}:
            raise HTTPException(422, "Choose installed modules")
        config["modules"] = modules
        used = bridge.usage(business, row)
        if used["seats"] > config["seats"] or used["storage_bytes"] > config["storage_mib"]*1048576:
            raise HTTPException(409, "Entitlements cannot be lower than current usage")
    elif data.action == "suspend":
        if status == "suspended": raise HTTPException(409, "Already suspended")
        config["resume_status"], status = status, "suspended"
    elif data.action == "resume":
        if status not in {"suspended", "cancelled"}: raise HTTPException(409, "This customer is not suspended or cancelled")
        status = config.get("resume_status", "trial")
    elif data.action == "cancel":
        config["cancelled_at"], config["cancellation_reason"], status = s.now().isoformat(), data.reason, "cancelled"
    elif data.action == "offboard":
        if status != "cancelled": raise HTTPException(409, "Cancel the subscription before offboarding")
        config["retention_until"] = (s.now()+timedelta(days=s.settings_for(db)["retention_days"])).isoformat()
        config["offboarded_at"], status = s.now().isoformat(), "offboarded"
        db.add(PlatformRecord(kind="task", title=f"Review retention and export for {row.name}", owner_id=actor.id, tenant_id=row.id,
            data={"due_at": config["retention_until"], "body": "Confirm customer export and legal holds before any separate business-data deletion."}))
    elif data.action in {"resend_invitation", "revoke_invitation"}:
        url = bridge.invitation(business, row, revoke=data.action == "revoke_invitation")
        for invite in db.query(PlatformRecord).filter_by(kind="customer_invitation", signup_id=row.signup_id):
            if invite.state not in {"accepted", "revoked"}: invite.state = "revoked"
        if url:
            s.local_mail(db, row.admin_email, "Your company admin invitation", url, actor, row.signup_id, row.id)
            db.add(PlatformRecord(kind="customer_invitation", title="Company admin activation", owner_id=actor.id, signup_id=row.signup_id,
                tenant_id=row.id, state="ready_local", expires_at=s.now()+timedelta(hours=48), data={"recipient": row.admin_email}))
            result["url"] = url
    elif data.action == "admin_transfer":
        try: new_email = str(StaffInvite(email=data.values.get("email"), name="Customer admin", role="owner").email).lower()
        except Exception: raise HTTPException(422, "Enter a valid new company admin email") from None
        if new_email == row.admin_email: raise HTTPException(422, "Choose a different email")
        parent = PlatformRecord(kind="admin_transfer", title="Company admin ownership transfer", state="pending", tenant_id=row.id,
            owner_id=actor.id, data={"old_email": row.admin_email, "new_email": new_email, "old_confirmed": False, "new_confirmed": False})
        db.add(parent); db.flush()
        for party, recipient in [("old", row.admin_email), ("new", new_email)]:
            _, url = s.issue_link(db, "transfer_consent", "Confirm company admin transfer", recipient, actor, tenant_id=row.id,
                                  data={"parent_id": parent.id, "party": party})
        result["message"] = "Both current and new admin verification links are in the local outbox."
    elif data.action == "support_request":
        record, url = s.issue_link(db, "support_consent", "Approve an Indian Servers support request", row.admin_email, actor, tenant_id=row.id,
            data={"reason": data.reason, "hours": int_value(data.values, "hours", 4, 1, 24)})
        result["url"] = url
    elif data.action == "snapshot":
        db.add(PlatformRecord(kind="backup", title=f"Configuration snapshot · {row.name}", state="ready", tenant_id=row.id, owner_id=actor.id,
            data={"config": config, "status": status, "plan_id": row.plan_id, "scope": "Customer subscription configuration; excludes ERP records and credentials"}))
    elif data.action == "restore_snapshot":
        snapshot = db.get(PlatformRecord, int_value(data.values, "snapshot_id", 0, 1, 2147483647))
        if not snapshot or snapshot.kind != "backup" or snapshot.tenant_id != row.id: raise HTTPException(404, "Customer snapshot not found")
        config, status, row.plan_id = snapshot.data["config"], snapshot.data["status"], snapshot.data["plan_id"]
        used = bridge.usage(business, row)
        if used["seats"] > config["seats"] or used["storage_bytes"] > config["storage_mib"]*1048576: raise HTTPException(409, "Snapshot limits are below current usage")
    elif data.action == "assign":
        validate_assignee(db, data.values.get("assigned_to")); row.assigned_to = data.values.get("assigned_to")
    elif data.action == "payment":
        amount = int_value(data.values, "amount_minor", 0, 1, 1000000000)
        currency = data.values.get("currency", "INR")
        if not isinstance(currency,str) or currency not in {"INR", "USD", "AED"}: raise HTTPException(422, "Unknown currency")
        reference = str(data.values.get("reference", "")).strip()
        if not 3 <= len(reference) <= 120: raise HTTPException(422, "Enter the offline payment reference")
        existing = db.query(PlatformRecord).filter_by(kind="billing_entry", tenant_id=row.id, title=reference).first()
        if existing: raise HTTPException(409, "This payment reference has already been recorded")
        db.add(PlatformRecord(kind="billing_entry", title=reference, state="recorded", owner_id=actor.id, tenant_id=row.id,
            data={"amount_minor": amount, "currency": currency, "type": "offline_payment", "reason": data.reason}))
    else: raise HTTPException(422, "Unknown customer operation")
    if config != row.config or status != row.status:
        bridge.sync_subscription(business, row, config, status)
    row.config, row.status = config, status
    s.event(db, actor, "tenant."+data.action, "tenant", row.id, data.reason, before, s.encode(row))
    db.commit()
    return {"customer": s.encode(row), **result}


@router.get("/customers/{ident}/export")
def customer_export(ident: int, actor=Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    row = s.tenant_for(db, actor, ident, "tenant.manage")
    s.event(db, actor, "tenant.configuration_exported", "tenant", row.id); db.commit()
    return Response(json.dumps({"scope": "Platform customer configuration only; no business records", "exported_at": s.now().isoformat(), "customer": s.encode(row)}, indent=2),
        media_type="application/json", headers={"Content-Disposition": f'attachment; filename="customer-{ident}-configuration.json"'})


def report_data(db, actor, start=None, end=None):
    from zoneinfo import ZoneInfo
    s.require(actor, "reports.read")
    end = s.aware(end or s.now()); start = s.aware(start or (end-timedelta(days=30)))
    if start >= end or (end-start).days > 730: raise HTTPException(422, "Choose an increasing date range of up to two years")
    query = s.scoped(db.query(Signup).filter(Signup.deleted_at.is_(None)), actor, Signup)
    cohort = query.filter(Signup.created_at >= start, Signup.created_at <= end).all()
    previous = query.filter(Signup.created_at >= start-(end-start), Signup.created_at < start).count()
    tenants = s.scoped(db.query(PlatformTenant), actor, PlatformTenant).all()
    ids = {r.id for r in cohort}; tenant_ids = {r.id for r in tenants}
    cohort_tenants = [r for r in tenants if r.signup_id in ids]
    approved = sum(r.reviewed_at is not None and r.company_id is not None for r in cohort)
    rejected = sum(r.reviewed_at is not None and r.company_id is None for r in cohort)
    reviewed = approved+rejected
    settings = s.settings_for(db); zone = ZoneInfo(settings["timezone"])
    duration = [s.business_hours_between(r.created_at, r.reviewed_at, settings) for r in cohort if r.reviewed_at]
    durations = sorted(duration)
    trends, modules, sources, campaigns, reviewers = Counter(), Counter(), Counter(), Counter(), Counter()
    for row in cohort:
        trends[s.aware(row.created_at).astimezone(zone).date().isoformat()] += 1
        modules.update(row.requested_modules)
        sources[row.source] += 1; campaigns[row.campaign or "Unattributed"] += 1
        if row.reviewed_by: reviewers[str(row.reviewed_by)] += 1
    overdue = sum(r.status in s.REVIEWABLE and s.business_hours_between(r.created_at,s.now(),settings)>settings["sla_hours"] for r in cohort)
    mrr, collected = Counter(), Counter()
    for tenant in tenants:
        if tenant.status == "active": mrr[tenant.config.get("currency","INR")] += tenant.config.get("monthly_price_minor",0)
    payments = db.query(PlatformRecord).filter_by(kind="billing_entry").filter(PlatformRecord.created_at >= start, PlatformRecord.created_at <= end)
    for record in payments:
        if record.tenant_id in tenant_ids:
            collected[record.data.get("currency","INR")] += record.data.get("amount_minor",0)
    failed_jobs = db.query(PlatformRecord).filter_by(kind="provisioning",state="failed")
    if actor.assigned_only and actor.role != "owner": failed_jobs = failed_jobs.filter(PlatformRecord.signup_id.in_(ids))
    cancelled = [r for r in tenants if r.config.get("cancelled_at") and start <= s.aware(datetime.fromisoformat(r.config["cancelled_at"])) <= end]
    beginning_paid = [r for r in tenants if r.config.get("paid_at") and s.aware(datetime.fromisoformat(r.config["paid_at"])) < start and
        (not r.config.get("cancelled_at") or s.aware(datetime.fromisoformat(r.config["cancelled_at"])) >= start)]
    cohort_churn = sum(r in beginning_paid for r in cancelled)
    invitation_states = Counter()
    for record in db.query(PlatformRecord).filter_by(kind="customer_invitation"):
        if record.signup_id in ids: invitation_states[record.state] += 1
    return {"start": start.isoformat(), "end": end.isoformat(), "timezone": settings["timezone"],
        "summary": {"signups":len(cohort), "companies":sum(r.applicant_type=="company" for r in cohort),
            "individuals":sum(r.applicant_type=="individual" for r in cohort), "pending":sum(r.status in s.REVIEWABLE for r in cohort),
            "approved":approved, "rejected":rejected, "overdue":overdue, "approval_rate":round(100*approved/reviewed,1) if reviewed else None,
            "rejection_rate":round(100*rejected/reviewed,1) if reviewed else None,
            "median_review_hours":statistics.median(duration) if duration else None,
            "p90_review_hours":durations[max(0,__import__('math').ceil(.9*len(durations))-1)] if durations else None,
            "previous_signups": previous, "growth_pct":round(100*(len(cohort)-previous)/previous,1) if previous else None,
            "customers":len(tenants), "active_customers":sum(r.status=="active" for r in tenants),
            "cancelled_in_period":len(cancelled), "churn_pct":round(100*cohort_churn/len(beginning_paid),1) if beginning_paid else None},
        "trends":[{"date":day,"signups":count} for day,count in sorted(trends.items())],
        "modules":dict(modules), "sources":dict(sources), "campaigns":dict(campaigns), "reviewer_decisions":dict(reviewers),
        "funnel":{"Submitted":len(cohort),"Approved":approved,
            "Invited":len({r.signup_id for r in db.query(PlatformRecord).filter_by(kind="customer_invitation") if r.signup_id in ids}), "Activated":sum(bool(r.config.get("activated_at")) for r in cohort_tenants),
            "Paid":sum(bool(r.config.get("paid_at")) for r in cohort_tenants)},
        "customer_status":dict(Counter(r.status for r in tenants)), "invitations":dict(invitation_states),
        "mrr_minor_by_currency":dict(mrr), "offline_receipts_minor_by_currency":dict(collected),
        "health":{"failed_provisioning_attempts":failed_jobs.count(), "overdue_reviews":overdue,
            "failed_logins_30d":db.query(PlatformEvent).filter(PlatformEvent.action=="login.failed",PlatformEvent.created_at>=s.now()-timedelta(days=30)).count() if actor.role=="owner" else None},
        "definitions":{"approval_rate":"Approved / (approved + rejected) within the submission cohort",
            "turnaround":"Business hours from submission to decision", "revenue":"Manually recorded offline receipts; no payment gateway transactions",
            "mrr":"Current active customer monthly contract value, grouped by currency", "churn":"Paid customers active at period start that cancelled during the period"}}


@router.get("/reports")
def reports(start: datetime | None=None, end: datetime | None=None, actor=Depends(current_platform_admin), db: Session=Depends(get_platform_db)):
    return report_data(db, actor, start, end)


@router.get("/report-export")
def report_export(start: datetime | None=None, end: datetime | None=None, actor=Depends(current_platform_admin), db: Session=Depends(get_platform_db)):
    report = report_data(db, actor, start, end)
    s.event(db, actor, "report.exported", after={"start":report["start"],"end":report["end"]}); db.commit()
    return Response(json.dumps(report,indent=2),media_type="application/json",headers={"Content-Disposition":'attachment; filename="platform-report.json"'})


@router.post("/operations/run-checks")
def run_checks(actor=Depends(current_platform_admin), db: Session=Depends(get_platform_db), business: Session=Depends(get_db)):
    s.require(actor,"tools.manage")
    return run_due_work(db,business,actor)


def run_due_work(db,business,actor):
    from app.platform_owner import bridge
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy import text
        if not db.execute(text("SELECT pg_try_advisory_xact_lock(121057769, 1)")).scalar():
            return {"processed":{},"already_running":True,"checked_at":s.now().isoformat()}
    counts = Counter(); settings=s.settings_for(db)
    if actor.role!="owner": raise HTTPException(403,"Only platform owners can run maintenance")
    for row in db.query(Signup).filter(Signup.deleted_at.is_(None),Signup.status.in_(s.REVIEWABLE)):
        if s.business_hours_between(row.created_at,s.now(),settings)>settings["sla_hours"] and not db.query(PlatformRecord.id).filter_by(kind="escalation",signup_id=row.id,state="open").first():
            db.add(PlatformRecord(kind="escalation",title="Overdue review",signup_id=row.id,owner_id=row.assigned_to or actor.id,data={"sla_hours":settings["sla_hours"]}))
            s.notify(db,"Overdue signup review",row.company_name or row.name,owner_id=row.assigned_to or actor.id,signup_id=row.id); counts["escalations"]+=1
    for row in db.query(PlatformTenant).filter_by(status="trial"):
        end=s.aware(datetime.fromisoformat(row.config["trial_ends_at"]))
        if end-s.now()<=timedelta(days=3):
            title="Trial expired" if end<s.now() else "Trial ending soon"
            if not db.query(PlatformRecord.id).filter_by(kind="outbox",title=title,tenant_id=row.id).first():
                s.local_mail(db,row.admin_email,title,f"Your trial ends {end.isoformat()}. Contact Indian Servers to continue.",actor,tenant_id=row.id); counts["trial_notices"]+=1
    for change in db.query(PlatformRecord).filter_by(kind="scheduled_change",state="pending").with_for_update():
        if s.aware(datetime.fromisoformat(change.data["effective_at"]))>s.now(): continue
        tenant=db.get(PlatformTenant,change.tenant_id); plan=db.get(PlatformPlan,change.data["plan_id"])
        if not tenant or not plan or not plan.active: change.state="failed"; continue
        used=bridge.usage(business,tenant)
        if used["seats"]>plan.config["seats"] or used["storage_bytes"]>plan.config["storage_mib"]*1048576: change.state="failed"; continue
        config={**tenant.config,**plan.config}; status="active" if change.data.get("convert_paid") else tenant.status
        if status=="active":config["paid_at"]=config.get("paid_at") or s.now().isoformat()
        bridge.sync_subscription(business,tenant,config,status)
        tenant.config,tenant.status,tenant.plan_id,change.state=config,status,plan.id,"completed";counts["plan_changes"]+=1
        s.event(db,actor,"tenant.scheduled_plan_applied","tenant",tenant.id,change.data["reason"])
    for invitation in db.query(PlatformRecord).filter(PlatformRecord.kind.in_(["staff_invitation","customer_invitation","support"]),PlatformRecord.expires_at<s.now(),PlatformRecord.state.in_(["pending","ready_local","authorized"])):
        invitation.state="expired";counts["expired_invitations"]+=1
    for scheduled in db.query(PlatformRecord).filter_by(kind="scheduled_report",state="open"):
        due=scheduled.data.get("next_run_at")
        if due and s.aware(datetime.fromisoformat(due))>s.now():continue
        reporter=db.get(PlatformAdmin,scheduled.owner_id)
        if not reporter or not reporter.is_active or "reports.read" not in s.permissions(reporter):continue
        report=report_data(db,reporter)
        db.add(PlatformRecord(kind="report_snapshot",title=scheduled.title,owner_id=reporter.id,state="ready",data=report))
        scheduled.data={**scheduled.data,"next_run_at":(s.now()+timedelta(days=7 if scheduled.data.get("frequency")=="weekly" else 1)).isoformat()}
        s.notify(db,"Scheduled report ready",scheduled.title,owner_id=reporter.id);counts["reports"]+=1
    s.event(db,actor,"operations.checked",after=dict(counts));db.commit()
    return {"processed":dict(counts),"checked_at":s.now().isoformat()}
