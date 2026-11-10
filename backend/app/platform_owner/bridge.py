"""Narrow provisioning bridge. Owner pages never acquire a business user session."""
from datetime import datetime, timedelta, timezone
import secrets
from fastapi import HTTPException
from sqlalchemy import func
from app.access.models import AccessMembership, AccessPolicy
from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
from app.models.user import User
from app.platform_owner import service as s
from functools import wraps


def tenant_bridge(function):
    @wraps(function)
    def routed(db,tenant,*args,**kwargs):
        from app.platform_owner.tenant_provisioning import company_business_session
        with company_business_session(tenant,db) as target:
            result=function(target,tenant,*args,**kwargs)
            if isinstance(result,str) and "/invite-access?token=" in result and target.info.get("tenant_uuid"):
                result+="&tenant="+target.info["tenant_uuid"]
            return result
    return routed


def customer_subscription(db, tenant):
    row = db.query(TenantSubscription).filter_by(company_id=tenant.company_id).with_for_update().first()
    if not row: raise HTTPException(409, "Customer subscription is unavailable; reconcile provisioning first")
    return row


@tenant_bridge
def usage(db, tenant):
    from app.models.company import Company
    db.query(Company).filter_by(id=tenant.company_id).with_for_update().first()
    members = db.query(AccessMembership.user_id).filter_by(company_id=tenant.company_id, active=True)
    users = db.query(User).filter(User.id.in_(members)).all()
    from app.models.file_storage import StorageObject
    size = db.query(func.coalesce(func.sum(StorageObject.size), 0)).filter_by(organization_id=tenant.company_id).scalar()
    activated = any(user.is_active and user.last_login for user in users)
    since = s.now()-timedelta(days=30)
    from sqlalchemy import text, inspect
    from app.models.audit import AuditLog
    last_login = max((s.aware(u.last_login) for u in users if u.last_login), default=None)
    audits = db.query(AuditLog).filter(AuditLog.organization_id == tenant.company_id, AuditLog.created_at >= since)
    requests = audits.count()
    errors = audits.filter(AuditLog.status_code >= 500).count()
    last_activity = audits.with_entities(func.max(AuditLog.created_at)).scalar()
    daily = {str(day): int(count) for day, count in audits.with_entities(func.date(AuditLog.created_at), func.count(AuditLog.id)).group_by(func.date(AuditLog.created_at))}
    counts = {}
    inspector = inspect(db.get_bind())
    # Fixed allowlist; never interpolate names supplied by a browser.
    for module, tables in {"crm": ["crm_leads", "crm_contacts", "crm_deals", "crm_activities"],
                           "project_management": ["pms_projects", "pms_tasks"]}.items():
        if module not in tenant.config.get("modules", []): continue
        for table in tables:
            if not inspector.has_table(table): continue
            columns = {c["name"] for c in inspector.get_columns(table)}
            if table == "pms_tasks":
                clause = " AND t.deleted_at IS NULL" if "deleted_at" in columns else ""
                counts[table] = int(db.execute(text("SELECT count(*) FROM pms_tasks t JOIN pms_projects p ON p.id=t.project_id WHERE p.organization_id=:company" + clause), {"company": tenant.company_id}).scalar())
                continue
            clause = " AND deleted_at IS NULL" if "deleted_at" in columns else ""
            counts[table] = int(db.execute(text(f"SELECT count(*) FROM {table} WHERE organization_id=:company{clause}"), {"company": tenant.company_id}).scalar())
    database_bytes = None
    if db.info.get("tenant_uuid") and db.get_bind().dialect.name == "postgresql":
        database_bytes = int(db.execute(text("SELECT pg_database_size(current_database())")).scalar())
    return {"seats": len(users), "active_seats": sum(bool(u.is_active) for u in users),
            "active_30d": sum(bool(u.last_login and s.aware(u.last_login) >= since) for u in users),
            "storage_bytes": int(size or 0), "activated": activated, "recorded_at": s.now().isoformat(),
            "last_login_at": last_login.isoformat() if last_login else None,
            "last_activity_at": s.aware(last_activity).isoformat() if last_activity else None,
            "requests_30d": requests, "server_errors_30d": errors, "requests_by_day": daily,
            "record_counts": counts, "database_bytes": database_bytes}


@tenant_bridge
def sync_subscription(db, tenant, config, status):
    subscription = customer_subscription(db, tenant)
    values = {**subscription.config_json, "enforce": True, "modules": config.get("modules", []),
        "seats": config.get("seats", 5), "storage_mib": config.get("storage_mib", 1024), "expiry_policy": "restrict"}
    if status == "trial":
        values["renewal_at"] = config["trial_ends_at"]
        values["grace_until"] = config.get("grace_until", config["trial_ends_at"])
    elif status == "active":
        values["renewal_at"], values["grace_until"] = None, None
    elif status in {"cancelled", "offboarded"}:
        values["grace_until"] = s.now().isoformat()
    subscription.status = "suspended" if status in {"suspended", "cancelled", "offboarded"} else status
    subscription.config_json, subscription.version = values, subscription.version+1
    # Module grants remain bounded to this customer's existing admin memberships.
    from app.access.catalog import catalog, ACTIONS
    selected = set(values["modules"])
    grants = {m["key"]: {"enabled": True, "role": "Workspace Admin", "permissions": [p["name"] for p in m["permissions"]],
        "actions": list(ACTIONS), "scope": "organization"} for m in catalog(db) if m["key"] in selected}
    admins = db.query(AccessMembership.user_id).filter_by(company_id=tenant.company_id, active=True, is_admin=True)
    for policy in db.query(AccessPolicy).filter(AccessPolicy.company_id == tenant.company_id, AccessPolicy.user_id.in_(admins)):
        policy.grants, policy.version = grants, policy.version+1
    db.commit()


@tenant_bridge
def invitation(db, tenant, revoke=False):
    membership = db.query(AccessMembership).filter_by(company_id=tenant.company_id, active=True, is_admin=True).order_by(AccessMembership.id).first()
    if not membership: raise HTTPException(409, "Customer admin membership is unavailable")
    user = db.get(User, membership.user_id)
    if not user or user.email != tenant.admin_email: raise HTTPException(409, "Reconcile the customer's primary admin first")
    if user.is_active and user.last_login and not revoke: raise HTTPException(409, "The customer already activated their account")
    if revoke:
        user.password_reset_token, user.password_reset_expires = None, None; db.commit(); return None
    from app.api.v1.auth import _hash_reset_token
    from app.core.config import settings
    raw = secrets.token_urlsafe(40)
    user.password_reset_token, user.password_reset_expires = _hash_reset_token(raw), s.now()+timedelta(hours=48)
    db.commit()
    return settings.FRONTEND_PUBLIC_URL.rstrip("/")+"/invite-access?token="+raw


@tenant_bridge
def transfer_admin(db, tenant, old_email, new_email):
    from app.models.user import UserSession
    from app.api.v1.auth import _hash_reset_token
    from app.core.config import settings
    from app.common.models import CommonPerson
    from app.branches.models import BranchPolicy
    from app.core.security import get_password_hash
    user = db.query(User).filter_by(email=old_email).with_for_update().first()
    membership = db.query(AccessMembership).filter_by(company_id=tenant.company_id, user_id=user.id if user else 0, active=True, is_admin=True).first()
    replacement = db.query(User).filter_by(email=new_email).first()
    if replacement:
        recovered = db.query(AccessMembership).filter_by(company_id=tenant.company_id,user_id=replacement.id,active=True,is_admin=True).first()
        if not recovered or membership or replacement.is_superuser or replacement.is_active:
            raise HTTPException(409,"New admin email already has a business identity")
    else:
        if not user or not membership or user.is_superuser:
            raise HTTPException(409, "This identity cannot be transferred automatically; verify its company memberships")
        old_policy = db.query(AccessPolicy).filter_by(company_id=tenant.company_id,user_id=user.id).one()
        replacement = User(email=new_email,hashed_password=get_password_hash(secrets.token_urlsafe(40)),is_active=False,is_superuser=False,
            person=CommonPerson(organization_id=tenant.company_id,primary_email=new_email,display_name="Company administrator",status="active"))
        db.add(replacement);db.flush()
        db.add(AccessMembership(user_id=replacement.id,company_id=tenant.company_id,active=True,is_admin=True))
        db.add(AccessPolicy(user_id=replacement.id,company_id=tenant.company_id,grants=old_policy.grants,status="invited",version=1))
        db.add(BranchPolicy(user_id=replacement.id,company_id=tenant.company_id,all_branches=True,manage_access=True))
        membership.is_admin,membership.active=False,False
        # Preserve the former administrator's identity and historical business records.
        old_policy.grants={};old_policy.version+=1
        user.password_reset_token,user.password_reset_expires=None,None
        db.query(BranchPolicy).filter_by(user_id=user.id,company_id=tenant.company_id).update({"manage_access":False})
        db.query(UserSession).filter_by(user_id=user.id).update({"status": "Revoked"})
    raw = secrets.token_urlsafe(40)
    replacement.password_reset_token, replacement.password_reset_expires = _hash_reset_token(raw), s.now()+timedelta(hours=48)
    db.commit()
    return settings.FRONTEND_PUBLIC_URL.rstrip("/")+"/invite-access?token="+raw
