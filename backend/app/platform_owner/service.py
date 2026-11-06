"""Product workflows for Indian Servers. Never imports client permission helpers."""
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from fastapi import HTTPException
from sqlalchemy import or_
from app.platform_owner.models import PlatformAdmin, PlatformEvent, PlatformRecord, PlatformSignupRequest, PlatformTenant

ALL_PERMISSIONS = {"signup.read", "signup.create", "signup.edit", "signup.review", "signup.archive", "signup.delete", "signup.export",
    "tenant.read", "tenant.manage", "billing.read", "billing.manage", "staff.manage", "reports.read", "settings.manage", "audit.read", "tools.manage"}
ROLES = {
    "owner": ALL_PERMISSIONS,
    "reviewer": {"signup.read", "signup.edit", "signup.review", "signup.archive", "tenant.read", "reports.read"},
    "sales": {"signup.read", "signup.create", "signup.edit", "tenant.read", "reports.read"},
    "support": {"signup.read", "tenant.read", "tools.manage"},
    "billing": {"tenant.read", "billing.read", "billing.manage", "reports.read"},
    "analyst": {"reports.read"},
}
DEFAULT_SETTINGS = {"trial_days": 14, "seats": 5, "storage_mib": 1024, "sla_hours": 24,
    "retention_days": 90, "idle_minutes": 60, "business_start": 9, "business_end": 18,
    "business_days": [0, 1, 2, 3, 4], "timezone": "Asia/Kolkata", "grace_days": 3,
    "require_checklist": True, "notify_new_signup": True}
REVIEWABLE = {"pending", "under_review", "awaiting_applicant"}


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def encode(row, exclude=()):
    return {c.name: (getattr(row, c.name).isoformat() if isinstance(getattr(row, c.name), datetime) else getattr(row, c.name))
            for c in row.__table__.columns if c.name not in set(exclude) | {"hashed_password", "token_hash", "encrypted_password"}}


def permissions(actor):
    # An explicit override may narrow a role, never add undeclared capabilities.
    base = ROLES.get(actor.role, set())
    effective = base if not actor.permissions else base.intersection(actor.permissions)
    scopes = getattr(actor, "_api_scopes", None)
    return effective if scopes is None else effective.intersection(scopes)


def require(actor, permission):
    if permission not in permissions(actor):
        raise HTTPException(403, "Your platform role does not allow this action")


def scoped(query, actor, model):
    if actor.assigned_only and actor.role != "owner":
        query = query.filter(model.assigned_to == actor.id)
    return query


def signup_for(db, actor, ident, permission="signup.read", lock=False):
    require(actor, permission)
    query = scoped(db.query(PlatformSignupRequest), actor, PlatformSignupRequest).filter_by(id=ident)
    if lock:
        query = query.with_for_update().populate_existing()
    row = query.first()
    if not row or row.deleted_at:
        raise HTTPException(404, "Signup request not found")
    return row


def tenant_for(db, actor, ident, permission="tenant.read", lock=False):
    require(actor, permission)
    query = scoped(db.query(PlatformTenant), actor, PlatformTenant).filter_by(id=ident)
    if lock:
        query = query.with_for_update().populate_existing()
    row = query.first()
    if not row:
        raise HTTPException(404, "Customer not found")
    return row


def event(db, actor, action, entity="platform", entity_id=None, reason="", before=None, after=None):
    db.add(PlatformEvent(admin_id=actor.id if actor else None, action=action, entity=entity, entity_id=entity_id,
                         reason=reason, before=before or {}, after=after or {}))


def settings_for(db):
    row = db.query(PlatformRecord).filter_by(kind="settings").first()
    return {**DEFAULT_SETTINGS, **(row.data if row else {})}


def notify(db, title, body, owner_id=None, signup_id=None, tenant_id=None):
    db.add(PlatformRecord(kind="notification", title=title, state="unread", owner_id=owner_id,
                         signup_id=signup_id, tenant_id=tenant_id, data={"body": body}))


def local_mail(db, recipient, subject, body, actor=None, signup_id=None, tenant_id=None, permission="signup.review"):
    row = PlatformRecord(kind="outbox", title=subject, state="queued_local", owner_id=actor.id if actor else None,
        signup_id=signup_id, tenant_id=tenant_id, data={"recipient": recipient, "body": body,
        "transport": "local_preview", "attempts": 0, "permission": permission})
    db.add(row)
    return row


def issue_link(db, kind, title, recipient, actor=None, signup_id=None, tenant_id=None, data=None, hours=48):
    from app.core.config import settings
    raw = secrets.token_urlsafe(40)
    row = PlatformRecord(kind=kind, title=title, state="pending", owner_id=actor.id if actor else None,
        signup_id=signup_id, tenant_id=tenant_id, token_hash=digest(raw),
        data={**(data or {}), "recipient": recipient}, expires_at=now()+timedelta(hours=hours))
    db.add(row); db.flush()
    url = settings.FRONTEND_PUBLIC_URL.rstrip("/") + "/platform/public/" + raw
    permission = "staff.manage" if kind in {"staff_invitation","password_reset"} else "tenant.manage" if kind=="transfer_consent" else "tools.manage" if kind=="support_consent" else "signup.review"
    local_mail(db, recipient, title, f"{title}\n\n{url}\n\nThis private link expires {row.expires_at.isoformat()}.", actor, signup_id, tenant_id,permission)
    return row, url


def public_record(db, token, kinds=None):
    row = db.query(PlatformRecord).filter_by(token_hash=digest(token)).with_for_update().first()
    if not row or (kinds and row.kind not in kinds) or row.state not in {"pending", "open"} or (row.expires_at and aware(row.expires_at) <= now()):
        raise HTTPException(404, "This link is invalid, expired or already used")
    return row


def duplicate_candidates(db, row):
    domain = row.email.split("@")[-1]
    shared_domains = {"gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com", "icloud.com", "example.com"}
    query = db.query(PlatformSignupRequest).filter(PlatformSignupRequest.id != row.id,
        PlatformSignupRequest.deleted_at.is_(None), or_(PlatformSignupRequest.phone == row.phone,
        PlatformSignupRequest.company_name == row.company_name if row.company_name else False,
        PlatformSignupRequest.email.ilike("%@"+domain) if domain not in shared_domains else False))
    actor = db.info.get("platform_actor")
    if actor: query = scoped(query, actor, PlatformSignupRequest)
    return [{"id": r.id, "name": r.company_name or r.name, "status": r.status,
             "match": "phone" if r.phone == row.phone else "company" if r.company_name and r.company_name == row.company_name else "email domain"}
            for r in query.limit(20)]


def business_hours_between(start, end, settings):
    from zoneinfo import ZoneInfo
    zone = ZoneInfo(settings["timezone"])
    start, end = aware(start).astimezone(zone), aware(end).astimezone(zone)
    total = 0
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end:
        if day.weekday() in settings["business_days"]:
            lo = max(start, day.replace(hour=settings["business_start"]))
            hi = min(end, day+timedelta(hours=settings["business_end"]))
            total += max(0, (hi-lo).total_seconds())/3600
        day += timedelta(days=1)
    return round(total, 2)


def safe_csv(value):
    value = str(value if value is not None else "")
    return "'"+value if value.lstrip()[:1] in {"=", "+", "-", "@"} or value[:1] in {"\t", "\r"} else value
