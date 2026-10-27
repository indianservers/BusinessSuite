from __future__ import annotations
import copy
import csv
import hashlib
import io
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
import jwt
from jwt import PyJWTError as JWTError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.access import service, entitlements
from app.access.catalog import catalog, preset, SCOPES, ACTIONS, permission_names
from app.access.models import (
    AccessPolicy,
    AccessMembership,
    AccessRole,
    AccessTemplate,
    AccessAudit,
)
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.security import verify_password, get_password_hash
from app.core.input_validation import EmailAddress
from app.models.user import User, UserSession, Role
from app.models.company import Company
from app.common.services.identity import SharedIdentityService

router = APIRouter(prefix="/access", tags=["Master Suite Users & Access"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def company_access(db, actor, company):
    if not db.get(Company, company):
        raise HTTPException(404, "Organization not found")
    if actor.is_superuser:
        return
    member = (
        db.query(AccessMembership)
        .filter_by(user_id=actor.id, company_id=company, active=True, is_admin=True)
        .first()
    )
    if not member:
        raise HTTPException(403, "Organization access administrator required")


def admin(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not service.schema_ready(db):
        raise HTTPException(
            503, "Apply the suite access database migration before managing access"
        )
    if not actor.is_superuser:
        company_access(
            db, actor, getattr(actor, "organization_id", service.primary_company(actor))
        )
    return actor


def authority(actor, grants):
    if actor.is_superuser:
        return
    allowed_names = permission_names(actor)
    own = getattr(actor, "_suite_grants", None) or {}
    for key, grant in grants.items():
        if not grant.get("enabled"):
            continue
        ceiling = own.get(key, {})
        if not set(grant.get("permissions", [])) <= allowed_names:
            raise HTTPException(403, "Cannot grant permissions above your authority")
        if not ceiling.get("enabled") or not set(grant.get("actions", [])) <= set(
            ceiling.get("actions", [])
        ):
            raise HTTPException(403, "Cannot grant module actions above your authority")
        scopes = {
            "own": {"own", "assigned"},
            "assigned": {"assigned"},
            "team": {"own", "assigned", "team"},
            "department": {"own", "assigned", "department"},
            "branch": {"own", "assigned", "department", "branch"},
            "organization": set(SCOPES),
        }
        if grant.get("scope", "own") not in scopes.get(
            ceiling.get("scope", "own"), set()
        ):
            raise HTTPException(403, "Cannot widen scope above your authority")


class StepUp(Strict):
    password: str = Field(min_length=1, max_length=500)


def session_fingerprint(request):
    return hashlib.sha256(request.headers.get("authorization", "").encode()).hexdigest()


@router.post("/step-up")
def step_up(
    data: StepUp,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    from app.models.user import LoginAttempt

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    if (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.user_id == actor.id,
            LoginAttempt.status == "Access Step-up Failed",
            LoginAttempt.created_at > cutoff,
        )
        .count()
        >= 5
    ):
        raise HTTPException(
            429, "Too many reauthentication attempts; try again in ten minutes"
        )
    if not verify_password(data.password, actor.hashed_password):
        db.add(
            LoginAttempt(
                user_id=actor.id,
                email=actor.email,
                status="Access Step-up Failed",
                success=False,
                ip_address=request.client.host if request.client else None,
            )
        )
        service.audit(
            db,
            actor,
            actor.organization_id,
            "step_up",
            "Reauthentication failed",
            request=request,
            outcome="denied",
        )
        db.commit()
        raise HTTPException(403, "Current password is incorrect")
    token = jwt.encode(
        {
            "sub": str(actor.id),
            "purpose": "suite-access",
            "session": session_fingerprint(request),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"token": token, "expiresIn": 600}


def check_step(request, actor):
    try:
        payload = jwt.decode(
            request.headers.get("X-Access-Step-Up", ""),
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if (
            payload.get("purpose") != "suite-access"
            or payload.get("sub") != str(actor.id)
            or payload.get("session") != session_fingerprint(request)
        ):
            raise ValueError()
    except (JWTError, ValueError):
        raise HTTPException(403, "Reauthenticate before applying access changes")


@router.get("/me")
def my_access(
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    company = actor.organization_id
    policy = service.policy_for(db, actor, company)
    return {
        "managed": bool(policy and not actor.is_superuser),
        "companyId": company,
        "grants": (
            service.resolved_grants(db, policy)
            if policy and not actor.is_superuser
            else service.legacy_grants(db, actor)
        ),
        "permissions": sorted(permission_names(actor)),
        "isGlobalAdmin": actor.is_superuser,
        "isAccessAdmin": actor.is_superuser
        or (
            service.schema_ready(db)
            and bool(
                db.query(AccessMembership)
                .filter_by(
                    user_id=actor.id, company_id=company, active=True, is_admin=True
                )
                .first()
            )
        ),
        "companyDisabledModules": [key for key, enabled in entitlements.states(db, company).items() if not enabled],
        "modules": catalog(db),
        "memberships": sorted(service.companies_for(db, actor)),
    }


@router.get("/catalog")
def get_catalog(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    modules = catalog(db)
    roles = db.query(AccessRole).filter_by(company_id=companyId, active=True).all()
    legacy = db.query(Role).all()
    return {
        "modules": modules,
        "presets": {
            m["key"]: {
                tier: preset(m["key"], tier, m["permissions"])
                for tier in ("viewer", "contributor", "editor", "manager", "admin")
            }
            for m in modules
        },
        "roles": [serialize(r) for r in roles],
        "legacyRoles": [
            {"id": r.id, "name": r.name, "permissions": [p.name for p in r.permissions]}
            for r in legacy
        ],
        "scopes": SCOPES,
        "actions": ACTIONS,
        "companies": [
            {"id": c.id, "name": c.name}
            for c in db.query(Company).all()
            if actor.is_superuser or c.id in service.companies_for(db, actor)
        ],
    }


def serialize(item):
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(
        {column.name: getattr(item, column.name) for column in item.__table__.columns}
    )


def users_in_company(db, company):
    # Legacy users remain in their existing primary company; memberships extend it explicitly.
    from sqlalchemy.orm import joinedload, selectinload
    from app.models.employee import Employee

    options = [
        joinedload(User.person),
        joinedload(User.role).selectinload(Role.permissions),
    ]
    if hasattr(User, "employee"):
        options += [
            joinedload(User.employee).joinedload(Employee.branch),
            joinedload(User.employee).joinedload(Employee.department),
        ]
    members = {
        m.user_id
        for m in db.query(AccessMembership).filter_by(company_id=company, active=True)
    }
    db.info.setdefault("suite_access_policies", {})[company] = {
        p.user_id: p for p in db.query(AccessPolicy).filter_by(company_id=company)
    }
    return [
        u
        for u in db.query(User).options(*options).order_by(User.email).all()
        if u.id in members or service.primary_company(u) == company
    ]


@router.get("/users")
def list_users(
    companyId: int = 1,
    search: str = Query("", max_length=150),
    branch: int | None = None,
    department: int | None = None,
    role: str = "",
    status: str = "",
    module: str = "",
    page: int = Query(1, ge=1),
    perPage: int = Query(50, ge=1, le=200),
    sort: str = Query("name", pattern="^(name|email|status|lastLogin|role)$"),
    descending: bool = False,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    rows = [service.snapshot(db, u, companyId) for u in users_in_company(db, companyId)]
    summary = {
        "total": len(rows),
        "active": sum(u["status"] == "active" for u in rows),
        "invited": sum(u["status"] == "invited" for u in rows),
        "suspended": sum(u["status"] == "suspended" for u in rows),
        "modules": sum(m["installed"] for m in catalog(db)),
        "admins": sum(
            u["isSuperuser"]
            or any(
                g.get("enabled")
                and (g.get("role") == "admin" or "manage_users" in g.get("actions", []))
                for g in u["grants"].values()
            )
            for u in rows
        ),
    }
    stats = {
        "byModule": {
            m["key"]: sum(
                bool(u["grants"].get(m["key"], {}).get("enabled")) for u in rows
            )
            for m in catalog(db)
        },
        "byRole": {},
        "byDepartment": {},
        "dormant": [],
    }
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    for u in rows:
        for key, field in (("byRole", "role"), ("byDepartment", "department")):
            stats[key][u[field] or "Unassigned"] = (
                stats[key].get(u[field] or "Unassigned", 0) + 1
            )
        if (
            not u["lastLogin"]
            or datetime.fromisoformat(u["lastLogin"]).replace(tzinfo=timezone.utc)
            < cutoff
        ):
            stats["dormant"].append(u["id"])
    rows = [
        u
        for u in rows
        if (
            not search
            or search.casefold()
            in " ".join(
                str(u.get(k) or "")
                for k in ("name", "email", "employeeCode", "department")
            ).casefold()
        )
        and (not branch or u["branchId"] == branch)
        and (not department or u["departmentId"] == department)
        and (
            not role
            or u["role"] == role
            or any(
                g.get("enabled") and g.get("role") == role for g in u["grants"].values()
            )
        )
        and (not status or u["status"] == status)
        and (not module or u["grants"].get(module, {}).get("enabled"))
    ]
    rows.sort(key=lambda row: str(row.get(sort) or "").casefold(), reverse=descending)
    return {
        "items": rows[(page - 1) * perPage : page * perPage],
        "total": len(rows),
        "page": page,
        "perPage": perPage,
        "summary": summary,
        "analytics": stats,
    }


@router.get("/users/{user_id}")
def get_user_access(
    user_id: int,
    companyId: int = 1,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    user = db.get(User, user_id)
    if not user or companyId not in service.companies_for(db, user):
        raise HTTPException(404, "User not found in this organization")
    return service.snapshot(db, user, companyId)


class UserChange(Strict):
    userId: int = Field(gt=0)
    version: int = Field(ge=0)
    grants: dict = Field(default_factory=dict, max_length=100)
    status: str | None = None


class Changes(Strict):
    companyId: int = Field(gt=0)
    changes: list[UserChange] = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=3, max_length=1000)
    atomic: bool = True
    templateId: int | None = None
    templateVersion: int | None = None


def validate_change(db, actor, data, change):
    target = db.get(User, change.userId)
    if not target or data.companyId not in service.companies_for(db, target):
        raise HTTPException(404, "User not found in this organization")
    if target.is_superuser:
        raise HTTPException(409, "Super Admin accounts are protected")
    if target.id == actor.id and not actor.is_superuser:
        raise HTTPException(
            403, "Delegated administrators cannot change their own access"
        )
    before = service.snapshot(db, target, data.companyId)
    if change.version != before["version"]:
        raise HTTPException(409, "Access changed since it was loaded")
    clean = service.validate_grants(db, change.grants, data.companyId)
    authority(actor, clean)
    if change.status and change.status not in {
        "active",
        "invited",
        "suspended",
        "deactivated",
    }:
        raise HTTPException(422, "Invalid status")
    after = {**before["grants"], **clean}
    if (target.role and target.role.name.lower() == "intern") or (
        getattr(target, "employee", None)
        and (target.employee.employment_type or "").lower() == "intern"
    ):
        if any(
            g.get("enabled") and k not in {"project_management", "interns_hub", "forms"}
            for k, g in after.items()
        ):
            raise HTTPException(
                422,
                "Interns may only receive restricted PMS, forms and Intern Hub access",
            )
        for key in ("project_management", "forms"):
            if after.get(key, {}).get("enabled") and after[key].get("scope") not in {
                "own",
                "assigned",
            }:
                raise HTTPException(
                    422,
                    "Intern access must remain restricted to own or assigned records",
                )
    return target, before, after


@router.post("/changes/preview")
def preview_changes(
    data: Changes, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, data.companyId)
    items = []
    for change in data.changes:
        target, before, after = validate_change(db, actor, data, change)
        items.append(
            {
                "userId": target.id,
                "name": before["name"],
                "before": before["grants"],
                "after": after,
                "oldStatus": before["status"],
                "newStatus": change.status or before["status"],
            }
        )
    return {"items": items, "count": len(items), "sessionsWillBeRevoked": True}


@router.post("/changes/apply")
def apply_changes(
    data: Changes,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, data.companyId)
    check_step(request, actor)
    if len({c.userId for c in data.changes}) != len(data.changes):
        raise HTTPException(422, "Duplicate users in update")
    if data.templateId:
        template = db.get(AccessTemplate, data.templateId)
        if (
            not template
            or template.company_id != data.companyId
            or template.version != data.templateVersion
            or not template.active
        ):
            raise HTTPException(409, "Template changed; preview it again")
    service.lock_admins(db)
    db.query(User).filter(User.id.in_([c.userId for c in data.changes])).order_by(
        User.id
    ).with_for_update().populate_existing().all()
    results = []
    transaction = db.begin_nested()
    try:
        if data.atomic:
            for change in data.changes:
                validate_change(db, actor, data, change)
        for change in data.changes:
            try:
                with db.begin_nested():
                    target, _, _ = validate_change(db, actor, data, change)
                    result = service.apply_user(
                        db,
                        actor,
                        target,
                        data.companyId,
                        change.model_dump(exclude_none=True),
                        data.reason,
                        request,
                    )
                    results.append(
                        {"userId": target.id, "success": True, "user": result}
                    )
            except HTTPException as error:
                if data.atomic:
                    raise
                results.append(
                    {"userId": change.userId, "success": False, "error": error.detail}
                )
                service.audit(
                    db,
                    actor,
                    data.companyId,
                    "access.updated",
                    data.reason,
                    target=change.userId if db.get(User, change.userId) else None,
                    request=request,
                    outcome="denied",
                )
        transaction.commit()
        db.commit()
    except HTTPException as error:
        transaction.rollback()
        service.audit(
            db,
            actor,
            data.companyId,
            "access.updated",
            str(error.detail),
            request=request,
            outcome="denied",
        )
        db.commit()
        raise
    return {"results": results, "updated": sum(r["success"] for r in results)}


class RolePayload(Strict):
    companyId: int = Field(gt=0)
    module: str
    name: str = Field(min_length=2, max_length=100)
    description: str = Field("", max_length=500)
    permissions: list[str] = Field(max_length=500)
    actions: list[str] = Field(max_length=20)
    scope: str
    version: int = Field(0, ge=0)
    active: bool = True
    reason: str = Field(min_length=3, max_length=1000)
    expectedUserIds: list[int] = Field(default_factory=list, max_length=10000)


@router.post("/roles")
@router.put("/roles/{role_id}")
def save_role(
    data: RolePayload,
    request: Request,
    role_id: int | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, data.companyId)
    check_step(request, actor)
    grant = {
        "enabled": True,
        "role": data.name,
        "permissions": data.permissions,
        "actions": data.actions,
        "scope": data.scope,
    }
    authority(actor, service.validate_grants(db, {data.module: grant}, data.companyId))
    item = (
        db.query(AccessRole)
        .filter_by(id=role_id, company_id=data.companyId)
        .with_for_update()
        .populate_existing()
        .first()
        if role_id
        else None
    )
    if role_id and not item:
        raise HTTPException(404, "Role not found")
    if item and (item.version != data.version or item.module_key != data.module):
        raise HTTPException(409, "Role changed since it was loaded")
    affected = (
        [
            p
            for p in db.query(AccessPolicy)
            .filter_by(company_id=data.companyId)
            .with_for_update()
            .populate_existing()
            .all()
            if any(g.get("roleId") == role_id for g in p.grants.values())
        ]
        if item
        else []
    )
    if item and sorted(data.expectedUserIds) != sorted(p.user_id for p in affected):
        raise HTTPException(
            409, "Assigned users changed; review the role's affected users again"
        )
    if affected and not data.active:
        raise HTTPException(409, "Reassign users before retiring this role")
    if not item:
        item = AccessRole(company_id=data.companyId, module_key=data.module, version=0)
        db.add(item)
    before = serialize(item) if item.id else None
    for key in ("name", "description", "permissions", "actions", "scope", "active"):
        setattr(item, key, getattr(data, key))
    item.version += 1
    for policy in affected:
        policy.version += 1
        db.query(UserSession).filter_by(user_id=policy.user_id).update(
            {UserSession.status: "Revoked"}
        )
    db.flush()
    service.audit(
        db,
        actor,
        data.companyId,
        "role.updated",
        data.reason,
        before,
        {**serialize(item), "affectedUserIds": [p.user_id for p in affected]},
        request=request,
    )
    db.commit()
    return {**serialize(item), "affectedUsers": [p.user_id for p in affected]}


@router.get("/roles/{role_id}/users")
def role_users(
    role_id: int,
    companyId: int,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    return {
        "items": [
            service.snapshot(db, db.get(User, p.user_id), companyId)
            for p in db.query(AccessPolicy).filter_by(company_id=companyId)
            if any(g.get("roleId") == role_id for g in p.grants.values())
        ]
    }


class TemplatePayload(Strict):
    companyId: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=100)
    description: str = Field("", max_length=500)
    grants: dict = Field(max_length=100)
    version: int = Field(0, ge=0)
    active: bool = True
    reason: str = Field(min_length=3, max_length=1000)


@router.get("/templates")
def templates(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    return {
        "items": [
            serialize(t)
            for t in db.query(AccessTemplate).filter_by(
                company_id=companyId, active=True
            )
        ]
    }


@router.post("/templates")
@router.put("/templates/{template_id}")
def save_template(
    data: TemplatePayload,
    request: Request,
    template_id: int | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, data.companyId)
    check_step(request, actor)
    clean = service.validate_grants(db, data.grants, data.companyId)
    authority(actor, clean)
    item = (
        db.query(AccessTemplate)
        .filter_by(id=template_id, company_id=data.companyId)
        .with_for_update()
        .populate_existing()
        .first()
        if template_id
        else None
    )
    if template_id and not item:
        raise HTTPException(404, "Template not found")
    if item and item.version != data.version:
        raise HTTPException(409, "Template changed")
    if not item:
        item = AccessTemplate(company_id=data.companyId, version=0)
        db.add(item)
    before = serialize(item) if item.id else None
    item.name, item.description, item.grants, item.active = (
        data.name,
        data.description,
        clean,
        data.active,
    )
    item.version += 1
    db.flush()
    service.audit(
        db,
        actor,
        data.companyId,
        "template.updated",
        data.reason,
        before,
        serialize(item),
        request=request,
    )
    db.commit()
    return serialize(item)


class CreateUser(Strict):
    companyId: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=150)
    email: EmailAddress
    password: str | None = Field(None, min_length=8, max_length=200)
    invite: bool = False
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/users", status_code=201)
def create_user(
    data: CreateUser,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, data.companyId)
    check_step(request, actor)
    from app.api.v1.auth import _validate_password_policy, _hash_reset_token
    from app.common.models import CommonPerson

    if db.query(User).filter(func_lower(User.email) == data.email.lower()).first():
        raise HTTPException(
            409,
            "Email already has a login. Add an authorized organization membership instead",
        )
    if not data.invite and not data.password:
        raise HTTPException(422, "A password is required for Add User")
    password = data.password or secrets.token_urlsafe(40)
    _validate_password_policy(db, password)
    # Attach the existing identity relationship before flush so the shared
    # tenant-account hook does not provision a second CommonPerson row.
    user = User(
        email=data.email,
        hashed_password=get_password_hash(password),
        is_active=not data.invite,
        is_superuser=False,
        person=CommonPerson(
            organization_id=data.companyId,
            primary_email=data.email,
            display_name=data.name,
            status="active",
        ),
    )
    db.add(user)
    db.flush()
    db.add(
        AccessPolicy(
            user_id=user.id,
            company_id=data.companyId,
            grants={},
            status="invited" if data.invite else "active",
            version=1,
            updated_by=actor.id,
        )
    )
    raw = None
    if data.invite:
        raw = secrets.token_urlsafe(40)
        user.password_reset_token = _hash_reset_token(raw)
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=48)
    service.audit(
        db,
        actor,
        data.companyId,
        "user.invited" if data.invite else "user.created",
        data.reason,
        target=user.id,
        request=request,
    )
    db.commit()
    return {
        "user": service.snapshot(db, user, data.companyId),
        "invitationToken": raw,
        "delivery": "manual" if data.invite else None,
        "message": (
            "Secure invitation created. Email delivery is not configured; share the invitation link directly."
            if data.invite
            else "User created with no module access. Assign modules next."
        ),
    }


def func_lower(column):
    from sqlalchemy import func

    return func.lower(column)


class MembershipPayload(Strict):
    companyId: int = Field(gt=0)
    userId: int = Field(gt=0)
    active: bool = True
    isAdmin: bool = False
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/memberships")
def membership(
    data: MembershipPayload,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    if not actor.is_superuser:
        raise HTTPException(
            403, "Only global Super Admins can authorize organization membership"
        )
    company_access(db, actor, data.companyId)
    check_step(request, actor)
    user = db.get(User, data.userId)
    if not user or user.is_superuser:
        raise HTTPException(409, "User is missing or is a protected administrator")
    row = (
        db.query(AccessMembership)
        .filter_by(company_id=data.companyId, user_id=data.userId)
        .first()
    )
    if data.active and user.is_active and data.companyId not in service.companies_for(db,user):
        from app.enterprise.controls import quota
        quota(db,data.companyId,"seats")
    if not row:
        row = AccessMembership(company_id=data.companyId, user_id=data.userId)
        db.add(row)
    row.active, row.is_admin = data.active, data.isAdmin
    if data.active and not service.policy_for(db, user, data.companyId):
        db.add(
            AccessPolicy(
                user_id=user.id,
                company_id=data.companyId,
                grants={},
                version=1,
                status="active",
            )
        )
    db.query(UserSession).filter_by(user_id=user.id).update(
        {UserSession.status: "Revoked"}
    )
    service.audit(
        db,
        actor,
        data.companyId,
        "membership.updated",
        data.reason,
        after=data.model_dump(),
        target=user.id,
        request=request,
    )
    db.commit()
    return {"updated": True}


@router.get("/audit")
def audit_log(
    companyId: int = 1,
    target: int | None = None,
    search: str = "",
    page: int = Query(1, ge=1),
    export: bool = False,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    query = db.query(AccessAudit).filter_by(company_id=companyId)
    if target:
        query = query.filter_by(target_id=target)
    if search:
        from sqlalchemy import or_, select
        from app.common.models import CommonPerson

        term = "%" + search[:100] + "%"
        matching = (
            select(User.id)
            .outerjoin(CommonPerson, CommonPerson.user_id == User.id)
            .where(or_(User.email.ilike(term), CommonPerson.display_name.ilike(term)))
        )
        query = query.filter(
            or_(
                AccessAudit.operation.ilike(term),
                AccessAudit.reason.ilike(term),
                AccessAudit.actor_id.in_(matching),
                AccessAudit.target_id.in_(matching),
            )
        )
    total = query.count()
    rows = (
        query.order_by(AccessAudit.id.desc())
        .offset((page - 1) * 50)
        .limit(10000 if export else 50)
        .all()
    )
    items = [serialize(r) for r in rows]
    ids = {ident for row in rows for ident in (row.actor_id, row.target_id) if ident}
    people = {user.id: user for user in db.query(User).filter(User.id.in_(ids)).all()}

    def label(ident):
        user = people.get(ident)
        if not user or (
            not user.is_superuser and companyId not in service.companies_for(db, user)
        ):
            return f"User {ident}" if ident else "—"
        return user.person.display_name if user.person else user.email

    for item in items:
        item["actorName"], item["targetName"] = label(item["actor_id"]), label(
            item["target_id"]
        )
    if export:
        return csv_response(items, "access-audit.csv")
    return {"items": items, "total": total}


def csv_response(rows, filename):
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: ("'" + str(v) if str(v).startswith(("=", "+", "-", "@")) else v)
                    for k, v in row.items()
                }
            )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/report")
def access_report(
    companyId: int = 1,
    ids: str = "",
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    selected = set(ids.split(",")) if ids else None
    rows = []
    for user in users_in_company(db, companyId):
        if selected and str(user.id) not in selected:
            continue
        data = service.snapshot(db, user, companyId)
        for key, grant in data["grants"].items():
            rows.append(
                {
                    "user": data["name"],
                    "email": user.email,
                    "employee": data["employeeCode"],
                    "company": companyId,
                    "module": key,
                    "enabled": grant.get("enabled", False),
                    "role": grant.get("role"),
                    "scope": grant.get("scope"),
                    "actions": ",".join(grant.get("actions", [])),
                    "permissions": ",".join(grant.get("permissions", [])),
                    "status": data["status"],
                }
            )
    return csv_response(rows[:200000], "user-access.csv")
