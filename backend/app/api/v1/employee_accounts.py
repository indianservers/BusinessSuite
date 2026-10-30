"""Super Admin account lifecycle and role administration from HRMS."""
import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.access.api import check_step
from app.core.deps import get_current_active_superuser, get_db
from app.core.input_validation import EmailAddress
from app.core.security import get_password_hash
from app.models.audit import AuditLog
from app.models.employee import Employee
from app.models.user import Permission, Role, User, UserSession

router = APIRouter(prefix="/accounts", tags=["HRMS Users & Roles"])
STATUS_ACTIONS = {"active": "ACCOUNT_ACTIVATE", "suspended": "ACCOUNT_SUSPEND", "terminated": "ACCOUNT_TERMINATE"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Change(Strict):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Enter a reason for this change")
        return value.strip()


class AccountCreate(Change):
    email: EmailAddress
    password: str = Field(min_length=8, max_length=128)
    role_id: int | None = Field(default=None, gt=0)
    employee_id: int | None = Field(default=None, gt=0)
    is_superuser: bool = False


class AccountEdit(Change):
    version: str = Field(min_length=64, max_length=64)
    email: EmailAddress
    role_id: int | None = Field(default=None, gt=0)
    is_superuser: bool = False


class AccountAction(Change):
    version: str = Field(min_length=64, max_length=64)
    action: Literal["active", "suspended", "terminated", "reset_password", "revoke_sessions"]
    password: str | None = Field(default=None, min_length=8, max_length=128)


class RoleEdit(Change):
    name: str = Field(min_length=2, max_length=50)
    description: str = Field(default="", max_length=1000)
    permission_ids: list[int] = Field(default_factory=list, max_length=2000)
    version: str | None = Field(default=None, min_length=64, max_length=64)


def digest(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


def version(user):
    return digest([user.id, user.email, user.role_id, user.is_active, user.is_superuser,
                   user.updated_at, user.hashed_password])


def role_version(role):
    return digest([role.id, role.name, role.description, sorted(p.id for p in role.permissions)])


def serialize(user, state=None):
    employee = user.employee
    return {"id": user.id, "email": user.email, "role_id": user.role_id,
            "role": user.role.name if user.role else None, "is_superuser": user.is_superuser,
            "status": "active" if user.is_active else state or "inactive",
            "employee_id": employee.id if employee else None,
            "employee_code": employee.employee_id if employee else None,
            "employee_name": f"{employee.first_name} {employee.last_name}" if employee else None,
            "last_login": user.last_login, "mfa_enabled": user.mfa_enabled,
            "created_at": user.created_at, "version": version(user)}


def audit(db, actor, target, action, reason, before=None, after=None, request=None, entity="user"):
    db.add(AuditLog(user_id=actor.id, actor_email=actor.email, actor_authenticated=True,
        method=request.method if request else "POST", endpoint=request.url.path if request else None,
        entity_type=entity, entity_id=target, action=action, status_code=200,
        old_values=json.dumps(before, default=str) if before else None,
        new_values=json.dumps(after, default=str) if after else None,
        description=reason, ip_address=request.client.host if request and request.client else None))


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "The account or role changed concurrently; reload and try again") from None


def flush(db):
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account or role already uses those details") from None


def revoke(db, user):
    from app.api.v1.auth import _revoke_user_sessions
    _revoke_user_sessions(db, user.id)


def target_user(db, user_id, expected):
    # A fixed lock order serializes global administrator changes, including concurrent demotions.
    db.query(User).filter(User.is_superuser.is_(True)).order_by(User.id).with_for_update().all()
    user = db.query(User).filter(User.id == user_id).populate_existing().with_for_update().first()
    if not user:
        raise HTTPException(404, "User not found")
    if version(user) != expected:
        raise HTTPException(409, "Account changed; reload before applying this action")
    return user


def protect_admins(db, actor, user, *, enabled, super_admin):
    if user.id == actor.id and (not enabled or not super_admin):
        raise HTTPException(409, "You cannot disable or demote your own Super Admin account")
    if user.is_superuser and user.is_active and (not enabled or not super_admin):
        others = db.query(User.id).filter(User.is_superuser.is_(True), User.is_active.is_(True), User.id != user.id).first()
        if not others:
            raise HTTPException(409, "At least one active Super Admin must remain")


def checked_role(db, role_id):
    if role_id is not None and not db.get(Role, role_id):
        raise HTTPException(422, "Choose an existing role")


@router.get("")
def list_accounts(search: str = Query("", max_length=150), status: str = "", role_id: int | None = None,
    page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db), actor: User = Depends(get_current_active_superuser)):
    query = db.query(User).outerjoin(Employee, Employee.user_id == User.id)
    if search:
        term = "%" + search.strip() + "%"
        query = query.filter(or_(User.email.ilike(term), Employee.first_name.ilike(term),
                                 Employee.last_name.ilike(term), Employee.employee_id.ilike(term)))
    if role_id is not None:
        query = query.filter(User.role_id == role_id)
    latest = db.query(AuditLog.entity_id, func.max(AuditLog.id).label("latest_id")).filter(
        AuditLog.entity_type == "user", AuditLog.action.in_(list(STATUS_ACTIONS.values()))
    ).group_by(AuditLog.entity_id).subquery()
    suspended = db.query(AuditLog.entity_id).join(latest, latest.c.latest_id == AuditLog.id).filter(AuditLog.action == "ACCOUNT_SUSPEND")
    terminated = db.query(AuditLog.entity_id).join(latest, latest.c.latest_id == AuditLog.id).filter(AuditLog.action == "ACCOUNT_TERMINATE")
    if status == "active": query = query.filter(User.is_active.is_(True))
    elif status == "suspended": query = query.filter(User.is_active.is_(False), User.id.in_(suspended))
    elif status == "terminated": query = query.filter(User.is_active.is_(False), User.id.in_(terminated))
    elif status == "inactive": query = query.filter(User.is_active.is_(False))
    elif status: raise HTTPException(422, "Unknown account status")
    total = query.count()
    users = query.options(joinedload(User.employee), joinedload(User.role)).order_by(User.email).offset((page-1)*per_page).limit(per_page).all()
    user_ids = [u.id for u in users]
    states = {row.entity_id: "terminated" if row.action == "ACCOUNT_TERMINATE" else "suspended"
              for row in db.query(AuditLog).join(latest, latest.c.latest_id == AuditLog.id).filter(AuditLog.entity_id.in_(user_ids))}
    return {"items": [serialize(u, states.get(u.id)) for u in users], "total": total, "page": page, "per_page": per_page}


@router.get("/options")
def options(db: Session = Depends(get_db), actor: User = Depends(get_current_active_superuser)):
    roles = db.query(Role).options(selectinload(Role.permissions)).order_by(Role.name).all()
    employees = db.query(Employee).filter(Employee.deleted_at.is_(None), Employee.user_id.is_(None)).order_by(Employee.first_name).all()
    return {"roles": [{"id": r.id, "name": r.name, "description": r.description, "is_system": r.is_system,
                      "permission_ids": [p.id for p in r.permissions], "version": role_version(r)} for r in roles],
            "permissions": [{"id": p.id, "name": p.name, "module": p.module, "description": p.description}
                            for p in db.query(Permission).order_by(Permission.module, Permission.name)],
            "employees": [{"id": e.id, "name": f"{e.employee_id} — {e.first_name} {e.last_name}"} for e in employees]}


@router.post("", status_code=201)
def create_account(data: AccountCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_active_superuser)):
    check_step(request, actor)
    from app.api.v1.auth import _validate_password_policy
    _validate_password_policy(db, data.password)
    checked_role(db, data.role_id)
    if data.role_id is None and not data.is_superuser:
        raise HTTPException(422, "Choose a role for the new account")
    email = data.email.strip().lower()
    if db.query(User.id).filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "An account already uses this email address")
    employee = None
    if data.employee_id:
        employee = db.query(Employee).filter(Employee.id == data.employee_id, Employee.deleted_at.is_(None)).with_for_update().first()
        if not employee: raise HTTPException(404, "Employee not found")
        if employee.user_id: raise HTTPException(409, "Employee already has a login account")
    if not data.is_superuser:
        from app.enterprise.controls import quota
        from app.access.service import primary_company
        quota(db, primary_company(actor), "seats")
    user = User(email=email, hashed_password=get_password_hash(data.password), role_id=data.role_id,
                is_active=True, is_superuser=data.is_superuser)
    db.add(user); flush(db)
    if employee: employee.user_id = user.id
    audit(db, actor, user.id, "ACCOUNT_CREATE", data.reason,
          after={"email": email, "role_id": data.role_id, "is_superuser": data.is_superuser, "employee_id": data.employee_id}, request=request)
    commit(db); db.refresh(user)
    return serialize(user)


@router.patch("/{user_id}")
def edit_account(user_id: int, data: AccountEdit, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_active_superuser)):
    check_step(request, actor)
    user = target_user(db, user_id, data.version)
    protect_admins(db, actor, user, enabled=user.is_active, super_admin=data.is_superuser)
    checked_role(db, data.role_id)
    email = data.email.strip().lower()
    if db.query(User.id).filter(func.lower(User.email) == email, User.id != user.id).first():
        raise HTTPException(409, "An account already uses this email address")
    before = {"email": user.email, "role_id": user.role_id, "is_superuser": user.is_superuser}
    user.email, user.role_id, user.is_superuser = email, data.role_id, data.is_superuser
    user.password_reset_token = None; user.password_reset_expires = None
    revoke(db, user)
    audit(db, actor, user.id, "ACCOUNT_EDIT", data.reason, before,
          {"email": email, "role_id": data.role_id, "is_superuser": data.is_superuser, "sessions_revoked": True}, request)
    commit(db); db.refresh(user)
    return serialize(user)


@router.post("/{user_id}/actions")
def account_action(user_id: int, data: AccountAction, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_active_superuser)):
    check_step(request, actor)
    user = target_user(db, user_id, data.version)
    action = data.action
    if action in STATUS_ACTIONS:
        protect_admins(db, actor, user, enabled=action == "active", super_admin=user.is_superuser)
        user.is_active = action == "active"
    elif action == "reset_password":
        from app.api.v1.auth import _validate_password_policy
        if not data.password: raise HTTPException(422, "Enter the new password")
        _validate_password_policy(db, data.password)
        user.hashed_password = get_password_hash(data.password)
    if action != "active":
        user.password_reset_token = None; user.password_reset_expires = None
    revoke(db, user)
    audit(db, actor, user.id, STATUS_ACTIONS.get(action, "ACCOUNT_PASSWORD_RESET" if action == "reset_password" else "ACCOUNT_REVOKE_SESSIONS"),
          data.reason, after={"action": action, "sessions_revoked": True}, request=request)
    commit(db); db.refresh(user)
    return {"message": "Account action completed; previous sessions revoked", "user": serialize(user, action if action in ("suspended", "terminated") else None)}


@router.get("/{user_id}/history")
def history(user_id: int, db: Session = Depends(get_db), actor: User = Depends(get_current_active_superuser)):
    if not db.get(User, user_id): raise HTTPException(404, "User not found")
    return [{"id": row.id, "action": row.action, "reason": row.description,
             "actor": row.actor_email, "created_at": row.created_at} for row in db.query(AuditLog).filter(
        AuditLog.entity_type == "user", AuditLog.entity_id == user_id, AuditLog.action.like("ACCOUNT_%")
    ).order_by(AuditLog.id.desc()).limit(50)]


def save_role(db, actor, data, request, role=None):
    name = data.name.strip()
    if len(name) < 2: raise HTTPException(422, "Enter a role name")
    if role and role.is_system: raise HTTPException(409, "Built-in roles are read-only; create a custom role instead")
    if role and role_version(role) != data.version: raise HTTPException(409, "Role changed; reload before saving")
    existing = db.query(Role.id).filter(func.lower(Role.name) == name.lower())
    if role: existing = existing.filter(Role.id != role.id)
    if existing.first(): raise HTTPException(409, "Role name already exists")
    permissions = db.query(Permission).filter(Permission.id.in_(set(data.permission_ids))).all()
    if len(permissions) != len(set(data.permission_ids)): raise HTTPException(422, "Unknown permission selected")
    created = role is None
    if created: role = Role(is_system=False); db.add(role)
    role.name, role.description, role.permissions = name, data.description, permissions
    flush(db)
    affected = db.query(User.id).filter(User.role_id == role.id)
    db.query(UserSession).filter(UserSession.user_id.in_(affected)).update({UserSession.status: "revoked"}, synchronize_session=False)
    audit(db, actor, role.id, "ROLE_CREATE" if created else "ROLE_EDIT", data.reason,
          after={"name": name, "permission_ids": sorted(data.permission_ids)}, request=request, entity="role")
    commit(db)
    return {"id": role.id, "name": role.name, "version": role_version(role)}


@router.post("/roles", status_code=201)
def create_role(data: RoleEdit, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_active_superuser)):
    check_step(request, actor)
    return save_role(db, actor, data, request)


@router.put("/roles/{role_id}")
def edit_role(role_id: int, data: RoleEdit, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_active_superuser)):
    check_step(request, actor)
    role = db.query(Role).filter(Role.id == role_id).with_for_update().first()
    if not role: raise HTTPException(404, "Role not found")
    return save_role(db, actor, data, request, role)
