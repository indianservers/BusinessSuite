"""Phase 1 control center over existing identity, organization and security models."""

from collections import Counter
from datetime import datetime, timedelta, timezone
import csv
import io
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import Field
from app.core.input_validation import EmailAddress
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.access.api import (
    admin,
    company_access,
    check_step,
    Strict,
    serialize,
    users_in_company,
)
from app.access import service, entitlements
from app.access.catalog import catalog
from app.access.models import AccessAudit, AccessMembership
from app.apps.business_os.models import BOSEnabledModule
from app.models.company import Company, Branch, Department
from app.models.employee import Employee
from app.models.user import User, UserSession, LoginAttempt, PasswordPolicy
from app.core.deps import get_db

router = APIRouter(prefix="/access/control", tags=["Master Suite Control Center"])


def target_user(db, actor, company, user_id):
    company_access(db, actor, company)
    target = db.get(User, user_id)
    if not target or company not in service.companies_for(db, target):
        raise HTTPException(404, "User not found in this organization")
    return target


def mutate(request, actor):
    check_step(request, actor)
    from sqlalchemy.orm import object_session

    db = object_session(actor)
    if actor.is_superuser:
        service.lock_admins(db)
    else:
        db.query(User).filter_by(id=actor.id).with_for_update().one()
    recent = datetime.now(timezone.utc) - timedelta(minutes=1)
    if (
        db.query(AccessAudit)
        .filter(AccessAudit.actor_id == actor.id, AccessAudit.created_at >= recent)
        .count()
        >= 30
    ):
        raise HTTPException(
            429, "Administrative change limit reached; retry in a minute"
        )


def record(db, actor, company, operation, data, request, before=None, target=None):
    after = dict(data)
    after["requestId"] = getattr(request.state, "request_id", None)
    service.audit(
        db,
        actor,
        company,
        operation,
        data.get("reason", "Administrative update"),
        before=before,
        after=after,
        target=target,
        request=request,
    )


def organizations(db, actor):
    if actor.is_superuser:
        return db.query(Company).order_by(Company.name).all()
    ids = [
        m.company_id
        for m in db.query(AccessMembership).filter_by(
            user_id=actor.id, active=True, is_admin=True
        )
    ]
    return db.query(Company).filter(Company.id.in_(ids)).order_by(Company.name).all()


@router.get("/organizations")
def organization_tree(db: Session = Depends(get_db), actor: User = Depends(admin)):
    companies = organizations(db, actor)
    result = []
    for company in companies:
        users = users_in_company(db, company.id)
        branches = db.query(Branch).filter_by(company_id=company.id).all()
        departments = (
            db.query(Department)
            .filter(Department.branch_id.in_([b.id for b in branches]))
            .all()
        )
        employees = (
            db.query(Employee)
            .filter(Employee.branch_id.in_([b.id for b in branches]))
            .all()
        )
        result.append(
            {
                **serialize(company),
                "userCount": len(users),
                "admins": [
                    m.user_id
                    for m in db.query(AccessMembership).filter_by(
                        company_id=company.id, active=True, is_admin=True
                    )
                ],
                "enabledModules": [
                    m["key"]
                    for m in catalog(db)
                    if m["installed"]
                    and entitlements.states(db, company.id).get(m["key"], True)
                ],
                "branches": [
                    {
                        **serialize(b),
                        "departments": [
                            {
                                **serialize(d),
                                "employeeCount": sum(
                                    e.department_id == d.id for e in employees
                                ),
                            }
                            for d in departments
                            if d.branch_id == b.id
                        ],
                    }
                    for b in branches
                ],
                "reportingTeams": [
                    {
                        "managerId": manager.id,
                        "manager": f"{manager.first_name} {manager.last_name or ''}".strip(),
                        "departmentId": manager.department_id,
                        "users": [
                            {
                                "employeeId": employee.id,
                                "userId": employee.user_id,
                                "name": f"{employee.first_name} {employee.last_name or ''}".strip(),
                            }
                            for employee in employees
                            if employee.reporting_manager_id == manager.id
                        ],
                    }
                    for manager in employees
                    if any(e.reporting_manager_id == manager.id for e in employees)
                ],
                "employees": [
                    {
                        "id": e.id,
                        "name": f"{e.first_name} {e.last_name or ''}".strip(),
                        "userId": e.user_id,
                    }
                    for e in employees
                ],
            }
        )
    return result


class CompanyEdit(Strict):
    name: str = Field(min_length=1, max_length=150)
    legal_name: str | None = Field(None, max_length=200)
    country: str = Field("India", min_length=1, max_length=100)
    registration_number: str | None = Field(None, max_length=100)
    gstin: str | None = Field(None, max_length=20)
    default_currency: str = Field("INR", pattern=r"^[A-Z]{3}$")
    default_timezone: str = Field("Asia/Kolkata", max_length=80)
    is_active: bool = True
    expectedUpdatedAt: str | None = None
    reason: str = Field(min_length=3, max_length=500)


@router.post("/organizations", status_code=201)
def create_company(
    data: CompanyEdit,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    if not actor.is_superuser:
        raise HTTPException(403, "Only global Super Admins can create companies")
    mutate(request, actor)
    validate_timezone(data.default_timezone)
    item = Company(**data.model_dump(exclude={"reason", "expectedUpdatedAt"}))
    db.add(item)
    db.flush()
    record(db, actor, item.id, "company_created", data.model_dump(), request)
    db.commit()
    return serialize(item)


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Unknown timezone")


def optimistic(item, expected):
    current = item.updated_at.isoformat() if item.updated_at else None
    if current != expected:
        raise HTTPException(409, "Record changed; reload before saving")


@router.put("/organizations/{company_id}")
def edit_company(
    company_id: int,
    data: CompanyEdit,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, company_id)
    mutate(request, actor)
    validate_timezone(data.default_timezone)
    item = (
        db.query(Company)
        .filter_by(id=company_id)
        .with_for_update()
        .populate_existing()
        .one()
    )
    optimistic(item, data.expectedUpdatedAt)
    if not actor.is_superuser and item.is_active != data.is_active:
        raise HTTPException(403, "Only global administrators may suspend a company")
    before = serialize(item)
    for key, value in data.model_dump(exclude={"reason", "expectedUpdatedAt"}).items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)
    record(db, actor, company_id, "company_updated", data.model_dump(), request, before)
    db.commit()
    return serialize(item)


class UnitEdit(Strict):
    companyId: int
    name: str = Field(min_length=1, max_length=150)
    code: str | None = Field(None, max_length=20)
    branch_id: int | None = None
    head_employee_id: int | None = None
    manager_employee_id: int | None = None
    country: str = Field("India", max_length=100)
    city: str | None = Field(None, max_length=100)
    is_active: bool = True
    expectedUpdatedAt: str | None = None
    reason: str = Field(min_length=3, max_length=500)


@router.post("/units/{kind}", status_code=201)
@router.put("/units/{kind}/{unit_id}")
def save_unit(
    kind: str,
    data: UnitEdit,
    request: Request,
    unit_id: int | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, data.companyId)
    mutate(request, actor)
    if kind not in {"branches", "departments"}:
        raise HTTPException(404, "Unknown organization unit")
    model = Branch if kind == "branches" else Department
    if kind == "departments":
        branch = db.get(Branch, data.branch_id)
        if not branch or branch.company_id != data.companyId:
            raise HTTPException(422, "Choose a branch in this company")
    employee_id = (
        data.head_employee_id if kind == "departments" else data.manager_employee_id
    )
    if employee_id:
        employee = (
            db.query(Employee)
            .join(Branch, Employee.branch_id == Branch.id)
            .filter(Employee.id == employee_id, Branch.company_id == data.companyId)
            .first()
        )
        if not employee:
            raise HTTPException(422, "Head must be an employee in this company")
    item = (
        db.query(model)
        .filter_by(id=unit_id)
        .with_for_update()
        .populate_existing()
        .first()
        if unit_id
        else model()
    )
    if not item:
        raise HTTPException(404, "Unit not found")
    if unit_id:
        owner = item.company_id if kind == "branches" else item.branch.company_id
        if owner != data.companyId:
            raise HTTPException(404, "Unit not found")
        optimistic(item, data.expectedUpdatedAt)
    before = serialize(item) if unit_id else None
    values = {
        "name": data.name,
        "code": data.code,
        "is_active": data.is_active,
        "organization_id": data.companyId,
    }
    values.update(
        {
            "company_id": data.companyId,
            "country": data.country,
            "city": data.city,
            "manager_employee_id": data.manager_employee_id,
        }
        if kind == "branches"
        else {"branch_id": data.branch_id, "head_employee_id": data.head_employee_id}
    )
    for key, value in values.items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)
    db.add(item)
    db.flush()
    record(
        db,
        actor,
        data.companyId,
        kind + "_saved",
        {**data.model_dump(), "entityId": item.id},
        request,
        before,
    )
    db.commit()
    return serialize(item)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), actor: User = Depends(admin)):
    companies = organizations(db, actor)
    rows, by_company = {}, {}
    accounts_by_id={}
    registered_ids=set()
    restricted_ids=set()
    from app.services.metrics.queries import registered_users
    by_module_users = {}
    for c in companies:
        people = users_in_company(db, c.id)
        accounts_by_id.update({u.id:u for u in people})
        registered_ids.update(r[0] for r in registered_users(db,actor,organization_id=c.id).with_entities(User.id))
        by_company[c.name] = len(people)
        for u in people:
            snapshot = service.snapshot(db, u, c.id)
            if snapshot["status"] in {"suspended","deactivated"}:restricted_ids.add(u.id)
            rows.setdefault(u.id, snapshot)
            for key, grant in snapshot["grants"].items():
                if grant.get("enabled"):
                    by_module_users.setdefault(key, set()).add(u.id)
    users = list(rows.values())
    modules = catalog(db)
    events = (
        db.query(AccessAudit)
        .filter(AccessAudit.company_id.in_([c.id for c in companies]))
        .order_by(AccessAudit.id.desc())
        .limit(12)
        .all()
    )
    return {
        "context":{"scope":"All organizations this administrator can manage; not just the active organization","organizations":[c.id for c in companies],"user_definition":"Unique User.id across organizations; company charts count memberships and may overlap"},
        "summary": {
            "Total companies": len(companies),
            "Total branches": db.query(Branch)
            .filter(Branch.company_id.in_([c.id for c in companies]))
            .count(),
            "Total users": len(users),
            "Registered users":len(registered_ids),
            "Active users": sum(u.is_active and u.id in registered_ids for u in accounts_by_id.values()),
            "Suspended users": len(restricted_ids),
            "Registered modules": len(modules),
            "Active Super Admins": sum(
                u.is_superuser and u.is_active for u in accounts_by_id.values()
            ),
            "Pending invitations": sum(u["status"] == "invited" for u in users),
        },
        "charts": {
            "Users by module": {
                m["label"]: len(by_module_users.get(m["key"], set())) for m in modules
            },
            "Users by company": by_company,
            "Users by department": dict(
                Counter(u["department"] or "Unassigned" for u in users)
            ),
            "Role distribution": dict(
                Counter(u["role"] or "Unassigned" for u in users)
            ),
            "Account status": dict(Counter(u["status"] for u in users)),
        },
        "activity": [serialize(e) for e in events],
    }


@router.get("/modules")
def modules(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    people = users_in_company(db, companyId)
    rows = [service.snapshot(db, u, companyId) for u in people]
    current = {
        r.module_key: r
        for r in db.query(BOSEnabledModule).filter_by(company_id=companyId)
    }
    companies = organizations(db, actor)
    return [
        {
            **m,
            "companyEnabled": (
                current[m["key"]].enabled
                if m["key"] in current
                else bool(m["installed"])
            ),
            "entitlementVersion": (
                (current[m["key"]].metadata_json or {}).get("accessVersion", 0)
                if m["key"] in current
                else 0
            ),
            "authorizedUsers": sum(
                u["grants"].get(m["key"], {}).get("enabled", False) for u in rows
            ),
            "companiesUsing": sum(
                entitlements.states(db, c.id).get(m["key"], m["installed"])
                for c in companies
            ),
            "integrationStatus": "Native permission checks + fail-closed scope filters; legacy queries may require adapters",
        }
        for m in catalog(db)
    ]


class EntitlementEdit(Strict):
    companyId: int
    enabled: bool
    version: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=500)


@router.put("/modules/{module_key}")
def entitlement(
    module_key: str,
    data: EntitlementEdit,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, data.companyId)
    mutate(request, actor)
    if not actor.is_superuser:
        raise HTTPException(403, "Company entitlements require a global Super Admin")
    meta = next((m for m in catalog(db) if m["key"] == module_key), None)
    if not meta or (data.enabled and not meta["installed"]):
        raise HTTPException(422, "Module is not installed")
    # Company lock serializes first insert as well as subsequent updates.
    db.query(Company).filter_by(id=data.companyId).with_for_update().one()
    row = (
        db.query(BOSEnabledModule)
        .filter_by(company_id=data.companyId, module_key=module_key)
        .with_for_update()
        .populate_existing()
        .first()
    )
    version = (row.metadata_json or {}).get("accessVersion", 0) if row else 0
    if data.version != version:
        raise HTTPException(409, "Entitlement changed; reload before saving")
    before = {"enabled": row.enabled if row else meta["installed"], "version": version}
    if not row:
        row = BOSEnabledModule(
            company_id=data.companyId, module_key=module_key, display_name=meta["label"]
        )
        db.add(row)
    row.enabled = data.enabled
    row.metadata_json = {**(row.metadata_json or {}), "accessVersion": version + 1}
    row.enabled_by = actor.id if data.enabled else row.enabled_by
    row.disabled_by = actor.id if not data.enabled else row.disabled_by
    record(
        db,
        actor,
        data.companyId,
        "company_module_enabled" if data.enabled else "company_module_disabled",
        {**data.model_dump(), "module": module_key},
        request,
        before,
    )
    db.commit()
    return {"enabled": data.enabled, "version": version + 1}


@router.get("/users/{user_id}/360")
def user360(
    user_id: int,
    companyId: int = 1,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    user = target_user(db, actor, companyId, user_id)
    employee = getattr(user, "employee", None)
    security_visible = actor.is_superuser or (
        not user.is_superuser and service.companies_for(db, user) == {companyId}
    )
    sessions = (
        db.query(UserSession)
        .filter_by(user_id=user.id)
        .order_by(UserSession.id.desc())
        .limit(50)
        .all()
        if security_visible
        else []
    )
    attempts = (
        db.query(LoginAttempt)
        .filter_by(user_id=user.id)
        .order_by(LoginAttempt.id.desc())
        .limit(50)
        .all()
        if security_visible
        else []
    )
    from app.api.v1.auth import check_lockout

    return {
        "overview": service.snapshot(db, user, companyId),
        "memberships": [
            c
            for c in service.companies_for(db, user)
            if actor.is_superuser or c in service.companies_for(db, actor)
        ],
        "security": {
            "restricted": not security_visible,
            "lockout": check_lockout(db, user) if security_visible else None,
            "mfaEnabled": user.mfa_enabled,
            "sessions": [safe_session(s) for s in sessions],
            "loginHistory": [
                {"id": a.id, "status": a.status, "at": a.created_at, "ip": a.ip_address}
                for a in attempts
            ],
            "recentFailures": sum(
                a.success is False
                and a.created_at.replace(tzinfo=timezone.utc)
                > datetime.now(timezone.utc) - timedelta(minutes=30)
                for a in attempts
            ),
        },
        "linked": {
            "employeeId": employee.id if employee else None,
            "employeeCode": employee.employee_id if employee else None,
            "intern": bool(
                employee and (employee.employment_type or "").lower() == "intern"
            ),
            "departmentId": employee.department_id if employee else None,
            "reportingManagerId": employee.reporting_manager_id if employee else None,
        },
        "history": [
            serialize(e)
            for e in db.query(AccessAudit)
            .filter_by(target_id=user.id, company_id=companyId)
            .order_by(AccessAudit.id.desc())
            .limit(100)
        ],
    }


class IdentityEdit(Strict):
    companyId: int
    name: str = Field(min_length=1, max_length=180)
    email: EmailAddress = Field(max_length=150)
    expectedUpdatedAt: str | None = None
    reason: str = Field(min_length=3, max_length=500)


@router.put("/users/{user_id}/identity")
def edit_identity(
    user_id: int,
    data: IdentityEdit,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    email = str(data.email)
    if not data.name.strip():
        raise HTTPException(422, "Name must not be blank")
    user = target_user(db, actor, data.companyId, user_id)
    mutate(request, actor)
    if (
        user.is_superuser
        or user.id == actor.id
        or (not actor.is_superuser and len(service.companies_for(db, user)) > 1)
    ):
        raise HTTPException(
            403,
            "This shared or privileged identity requires a global identity workflow",
        )
    user = (
        db.query(User).filter_by(id=user_id).with_for_update().populate_existing().one()
    )
    optimistic(user, data.expectedUpdatedAt)
    if db.query(User).filter(User.email == email, User.id != user.id).first():
        raise HTTPException(409, "Email is already in use")
    before = {
        "email": user.email,
        "name": user.person.display_name if user.person else None,
    }
    user.email = email
    if user.person:
        user.person.display_name = data.name.strip()
    else:
        from app.common.models import CommonPerson

        db.add(
            CommonPerson(
                user_id=user.id,
                organization_id=data.companyId,
                display_name=data.name.strip(),
                primary_email=email,
            )
        )
    if user.person:
        user.person.primary_email = email
    user.updated_at = datetime.now(timezone.utc)
    db.query(UserSession).filter_by(user_id=user.id, status="Active").update(
        {UserSession.status: "Revoked"}, synchronize_session=False
    )
    record(
        db,
        actor,
        data.companyId,
        "identity_updated",
        data.model_dump(),
        request,
        before,
        user.id,
    )
    db.commit()
    return {**service.snapshot(db, user, data.companyId), "updatedAt": user.updated_at}


def safe_session(s):
    return {
        "id": s.id,
        "userId": s.user_id,
        "device": s.device_name,
        "ip": s.ip_address,
        "status": s.status,
        "expiresAt": s.expires_at,
        "lastSeen": s.last_seen_at,
    }


@router.get("/security")
def security(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    users = users_in_company(db, companyId)
    ids = [
        u.id
        for u in users
        if actor.is_superuser
        or (not u.is_superuser and service.companies_for(db, u) == {companyId})
    ]
    now = datetime.now(timezone.utc)
    sessions = (
        db.query(UserSession)
        .filter(
            UserSession.user_id.in_(ids),
            UserSession.status == "Active",
            or_(UserSession.expires_at > now, UserSession.expires_at.is_(None)),
        )
        .order_by(UserSession.id.desc())
        .limit(200)
        .all()
    )
    failures = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.user_id.in_(ids), LoginAttempt.success.is_(False))
        .order_by(LoginAttempt.id.desc())
        .limit(100)
        .all()
    )
    return {
        "sessions": [safe_session(s) for s in sessions],
        "failures": [
            {
                "userId": f.user_id,
                "status": f.status,
                "at": f.created_at,
                "ip": f.ip_address,
            }
            for f in failures
        ],
        "privileged": [
            {"id": u.id, "email": u.email, "mfaEnabled": u.mfa_enabled}
            for u in users
            if u.is_superuser
            or any(
                m.is_admin
                for m in db.query(AccessMembership).filter_by(
                    user_id=u.id, company_id=companyId, active=True
                )
            )
        ],
        "passwordPolicies": (
            [serialize(p) for p in db.query(PasswordPolicy).all()]
            if actor.is_superuser
            else []
        ),
        "policyScope": "deployment-global; global administrators only",
    }


class SessionEdit(Strict):
    companyId: int
    userId: int
    reason: str = Field(min_length=3, max_length=500)


@router.post("/sessions/revoke")
def revoke_sessions(
    data: SessionEdit,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    user = target_user(db, actor, data.companyId, data.userId)
    mutate(request, actor)
    if user.is_superuser or (
        not actor.is_superuser and len(service.companies_for(db, user)) > 1
    ):
        raise HTTPException(403, "Cannot revoke privileged or cross-company sessions")
    count = (
        db.query(UserSession)
        .filter_by(user_id=user.id, status="Active")
        .update({UserSession.status: "Revoked"}, synchronize_session=False)
    )
    record(
        db,
        actor,
        data.companyId,
        "sessions_revoked",
        {**data.model_dump(), "count": count},
        request,
        target=user.id,
    )
    db.commit()
    return {"revoked": count}


class PolicyEdit(Strict):
    name: str = Field("Suite default", min_length=1, max_length=120)
    min_length: int = Field(8, ge=8, le=128)
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_number: bool = True
    require_special: bool = False
    max_age_days: int = Field(90, ge=1, le=365)
    lockout_attempts: int = Field(5, ge=3, le=20)
    lockout_duration_minutes: int = Field(30, ge=1, le=1440)
    mfa_required: bool = False
    expected: dict = Field(default_factory=dict)
    reason: str = Field(min_length=3, max_length=500)


@router.put("/password-policy")
def update_policy(
    data: PolicyEdit,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    if not actor.is_superuser:
        raise HTTPException(403, "Password policy is deployment-global")
    mutate(request, actor)
    service.lock_admins(db)
    # Require existing administrator MFA enrollment before making it mandatory.
    if (
        data.mfa_required
        and db.query(User)
        .filter_by(is_superuser=True, is_active=True, mfa_enabled=False)
        .count()
    ):
        raise HTTPException(
            409, "Enroll active Super Admins in MFA before requiring it"
        )
    policy = (
        db.query(PasswordPolicy)
        .filter_by(is_active=True)
        .order_by(PasswordPolicy.id.desc())
        .with_for_update()
        .populate_existing()
        .first()
    )
    before = serialize(policy) if policy else {}
    if before != data.expected:
        raise HTTPException(409, "Password policy changed; reload before saving")
    if not policy:
        policy = PasswordPolicy()
        db.add(policy)
    for key, value in data.model_dump(exclude={"expected", "reason"}).items():
        setattr(policy, key, value)
    policy.require_symbol = data.require_special
    policy.expiry_days = data.max_age_days
    policy.lockout_minutes = data.lockout_duration_minutes
    policy.is_active = True
    policy.is_default = True
    record(
        db,
        actor,
        service.primary_company(actor),
        "password_policy_updated",
        data.model_dump(exclude={"expected"}),
        request,
        before,
    )
    db.commit()
    return serialize(policy)


@router.get("/audit")
def audit_events(
    companyId: int = 1,
    action: str = Query("", max_length=80),
    userId: int | None = None,
    result: str = "",
    module: str = "",
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = Query(1, ge=1),
    export: bool = False,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    query = db.query(AccessAudit).filter_by(company_id=companyId)
    if action:
        query = query.filter(AccessAudit.operation.contains(action, autoescape=True))
    if userId:
        query = query.filter(
            or_(AccessAudit.actor_id == userId, AccessAudit.target_id == userId)
        )
    if result:
        query = query.filter_by(outcome=result)
    if start:
        query = query.filter(AccessAudit.created_at >= start)
    if end:
        query = query.filter(AccessAudit.created_at <= end)
    rows = [
        serialize(row)
        for row in query.order_by(AccessAudit.id.desc()).limit(10001).all()
    ]
    # Consolidate existing authentication and rejected-admin events without
    # copying secrets or exposing unrelated tenants' account metadata.
    from app.models.audit import AuditLog

    ids = [u.id for u in users_in_company(db, companyId) if service.companies_for(db, u) == {companyId}]
    attempts = db.query(LoginAttempt).filter(LoginAttempt.user_id.in_(ids))
    denied = db.query(AuditLog).filter(
        AuditLog.user_id.in_(ids),
        AuditLog.endpoint.startswith("/api/v1/access/"),
        AuditLog.status_code >= 400,
    )
    if start:
        attempts = attempts.filter(LoginAttempt.created_at >= start)
        denied = denied.filter(AuditLog.created_at >= start)
    if end:
        attempts = attempts.filter(LoginAttempt.created_at <= end)
        denied = denied.filter(AuditLog.created_at <= end)
    for event in attempts.order_by(LoginAttempt.id.desc()).limit(1000):
        rows.append(
            {
                "id": f"login-{event.id}",
                "created_at": event.created_at.isoformat(),
                "actor_id": event.user_id,
                "target_id": event.user_id,
                "company_id": companyId,
                "operation": "login_security",
                "outcome": "success" if event.success else "denied",
                "reason": event.status,
                "source_ip": event.ip_address,
                "before_json": None,
                "after_json": None,
            }
        )
    for event in denied.order_by(AuditLog.id.desc()).limit(1000):
        rows.append(
            {
                "id": f"request-{event.id}",
                "created_at": event.created_at.isoformat(),
                "actor_id": event.user_id,
                "target_id": None,
                "company_id": companyId,
                "operation": "administrative_request_denied",
                "outcome": "denied",
                "reason": f"{event.method} {event.endpoint} ({event.status_code})",
                "source_ip": event.ip_address,
                "before_json": None,
                "after_json": {"requestId": event.request_id},
            }
        )
    rows = [
        row
        for row in rows
        if (not action or action in row["operation"])
        and (not result or result == row["outcome"])
        and (not userId or userId in {row["actor_id"], row["target_id"]})
        and (
            not module
            or module in (row["after_json"] or {}).get("grants", {})
            or (row["after_json"] or {}).get("module") == module
        )
    ]
    rows.sort(key=lambda row: row["created_at"], reverse=True)
    if export:
        if not actor.is_superuser:
            raise HTTPException(403, "Global administrator required for audit export")
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(
            [
                "ID",
                "Timestamp",
                "Actor",
                "Target",
                "Company",
                "Action",
                "Result",
                "Reason",
            ]
        )
        for row in rows[:10000]:
            cells = [
                row[key]
                for key in (
                    "id",
                    "created_at",
                    "actor_id",
                    "target_id",
                    "company_id",
                    "operation",
                    "outcome",
                    "reason",
                )
            ]
            writer.writerow(
                [
                    (
                        "'" + str(c)
                        if str(c).lstrip().startswith(("=", "+", "-", "@"))
                        else c
                    )
                    for c in cells
                ]
            )
        return Response(
            stream.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=access-audit.csv"},
        )
    return {
        "total": len(rows),
        "items": rows[(page - 1) * 50 : page * 50],
        "capped": len(rows) > 10000,
    }


class SuperAdminInput(Strict):
    companyId: int = Field(default=1, gt=0)
    email: str = Field(min_length=3, max_length=254)
    password: str | None = Field(default=None, max_length=256)
    reason: str = Field(min_length=3, max_length=500)


@router.post("/super-admins")
def add_super_admin(data: SuperAdminInput, request: Request,
                    db: Session = Depends(get_db), actor: User = Depends(admin)):
    if not actor.is_superuser:
        raise HTTPException(403, "Global Super Admin required")
    company_access(db, actor, data.companyId)
    if not db.get(Company, data.companyId):
        raise HTTPException(404, "Company not found")
    mutate(request, actor)
    from app.core.input_validation import EmailAddress
    from pydantic import TypeAdapter
    from app.core.security import get_password_hash
    from app.api.v1.auth import _validate_password_policy
    try:
        email = str(TypeAdapter(EmailAddress).validate_python(data.email)).lower()
    except ValueError:
        raise HTTPException(422, "Enter a valid email address")
    target = db.query(User).filter(func.lower(User.email) == email).with_for_update().first()
    created = target is None
    if target and not target.is_active:
        raise HTTPException(409, "Activate the account before granting Super Admin access")
    if target and target.is_superuser:
        raise HTTPException(409, "This account is already a Super Admin")
    if created:
        if not data.password:
            raise HTTPException(422, "A password is required for a new account")
        _validate_password_policy(db, data.password)
        target = User(email=email, hashed_password=get_password_hash(data.password), is_active=True, is_superuser=True)
        db.add(target)
        db.flush()
    else:
        if data.password:
            raise HTTPException(422, "Leave the password empty for an existing account")
        target.is_superuser = True
    record(db, actor, data.companyId, "super_admin.granted",
           {"reason": data.reason, "created": created, "isSuperuser": True}, request,
           before={"isSuperuser": False}, target=target.id)
    db.commit()
    return {"id": target.id, "email": target.email, "isSuperuser": True}
