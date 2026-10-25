from __future__ import annotations
import copy
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func
from app.access.catalog import (
    MODULES,
    ACTIONS,
    SCOPES,
    catalog,
    permission_module,
    permission_objects,
    request_module,
    action_for,
)
from app.access.models import AccessPolicy, AccessMembership, AccessRole, AccessAudit
from app.models.user import User, Permission, UserSession


def primary_company(user):
    person = getattr(user, "person", None)
    if person and person.organization_id:
        return int(person.organization_id)
    employee = getattr(user, "employee", None)
    return int(employee.branch.company_id if employee and employee.branch else 1)


def companies_for(db, user):
    return {primary_company(user)} | {
        row.company_id
        for row in db.query(AccessMembership).filter_by(user_id=user.id, active=True)
    }


def policy_for(db, user, company):
    return db.query(AccessPolicy).filter_by(user_id=user.id, company_id=company).first()


def legacy_grants(db, user):
    names = {p.name for p in (user.role.permissions if user.role else [])}
    by_module = {}
    for module in catalog(db):
        module_names = {p["name"] for p in module["permissions"]}
        selected = sorted(names & module_names)
        by_module[module["key"]] = {
            "enabled": bool(selected or user.is_superuser),
            "role": user.role.name if user.role else "Legacy",
            "roleId": None,
            "permissions": selected,
            "actions": (
                ACTIONS
                if user.is_superuser
                or any("manage" in n or "admin" in n for n in selected)
                else ["view"]
            ),
            "scope": "organization" if user.is_superuser else "own",
        }
    return by_module


def resolved_grants(db, policy):
    grants = copy.deepcopy(policy.grants)
    for key, grant in grants.items():
        if grant.get("roleId"):
            role = db.get(AccessRole, grant["roleId"])
            if (
                not role
                or not role.active
                or role.company_id != policy.company_id
                or role.module_key != key
            ):
                grant["enabled"] = False
            else:
                grant.update(
                    role=role.name,
                    permissions=role.permissions,
                    actions=role.actions,
                    scope=grant.get("scope") or role.scope,
                )
    return grants


def validate_grants(db, grants, company):
    modules = {m["key"]: m for m in catalog(db)}
    clean = {}
    for key, original in grants.items():
        if key not in modules:
            raise HTTPException(422, f"Unknown registered module: {key}")
        if not isinstance(original, dict):
            raise HTTPException(422, "Module grants must be objects")
        if set(original) - {
            "enabled",
            "role",
            "roleId",
            "permissions",
            "actions",
            "scope",
        }:
            raise HTTPException(422, "Unsupported grant fields")
        grant = copy.deepcopy(original)
        if type(grant.get("enabled")) is not bool:
            raise HTTPException(422, "Each module requires an enabled checkbox")
        if grant.get("enabled") and not modules[key]["installed"]:
            raise HTTPException(422, "Module is not installed")
        grant.setdefault("scope", "own")
        grant.setdefault("actions", ["view"])
        grant.setdefault("permissions", [])
        grant.setdefault("role", "Custom")
        if grant["scope"] not in SCOPES or not set(grant["actions"]) <= set(ACTIONS):
            raise HTTPException(422, "Invalid action or scope")
        names = {p["name"] for p in modules[key]["permissions"]}
        if not set(grant["permissions"]) <= names:
            raise HTTPException(422, f"Permission does not belong to {key}")
        if grant.get("roleId"):
            role = db.get(AccessRole, grant["roleId"])
            if (
                not role
                or role.company_id != company
                or role.module_key != key
                or not role.active
            ):
                raise HTTPException(422, "Invalid module role")
            grant.update(
                role=role.name,
                permissions=list(role.permissions),
                actions=list(role.actions),
            )
        clean[key] = grant
    return clean


def snapshot(db, user, company):
    policy = policy_for(db, user, company)
    employee = getattr(user, "employee", None)
    person = getattr(user, "person", None)
    grants = (
        legacy_grants(db, user)
        if not policy or user.is_superuser
        else resolved_grants(db, policy)
    )
    name = (
        person.display_name
        if person
        else (
            " ".join(filter(None, [employee.first_name, employee.last_name]))
            if employee
            else user.email.split("@")[0]
        )
    )
    return {
        "id": user.id,
        "name": name,
        "email": user.email,
        "employeeCode": employee.employee_id if employee else None,
        "department": (
            employee.department.name if employee and employee.department else None
        ),
        "departmentId": employee.department_id if employee else None,
        "branchId": employee.branch_id if employee else None,
        "companyId": company,
        "accountType": (
            "Super Admin"
            if user.is_superuser
            else employee.employment_type if employee else "User"
        ),
        "role": user.role.name if user.role else None,
        "isSuperuser": user.is_superuser,
        "status": (
            policy.status if policy else "active" if user.is_active else "deactivated"
        ),
        "lastLogin": user.last_login.isoformat() if user.last_login else None,
        "version": policy.version if policy else 0,
        "managed": bool(policy),
        "grants": grants,
        "moduleCount": sum(bool(g.get("enabled")) for g in grants.values()),
    }


def audit(
    db,
    actor,
    company,
    operation,
    reason,
    before=None,
    after=None,
    target=None,
    request=None,
    outcome="success",
):
    from app.core.security import verify_access_token

    token = (
        request.headers.get("authorization", "").partition(" ")[2] if request else ""
    )
    payload = verify_access_token(token) or {} if token else {}
    db.add(
        AccessAudit(
            actor_id=actor.id,
            target_id=target,
            company_id=company,
            operation=operation,
            reason=reason,
            before_json=before,
            after_json=after,
            source_ip=request.client.host if request and request.client else None,
            session_id=int(payload["sid"]) if payload.get("sid") else None,
            outcome=outcome,
        )
    )


def lock_admins(db):
    # Serialize changes against the same rows, including concurrent demotions.
    return (
        db.query(User)
        .filter(User.is_superuser.is_(True))
        .order_by(User.id)
        .with_for_update()
        .all()
    )


def apply_user(db, actor, target, company, patch, reason, request):
    if company not in companies_for(db, target):
        raise HTTPException(404, "User is not a member of this organization")
    if target.is_superuser:
        raise HTTPException(
            409,
            "Super Admin access is protected; use the dedicated administrator lifecycle",
        )
    policy = policy_for(db, target, company)
    if patch["version"] != (policy.version if policy else 0):
        raise HTTPException(
            409, "Access changed since it was loaded. Refresh and review again"
        )
    before = snapshot(db, target, company)
    grants = validate_grants(db, patch.get("grants", {}), company)
    status = patch.get("status", before["status"])
    if status not in {"active", "invited", "suspended", "deactivated"}:
        raise HTTPException(422, "Invalid account status")
    if not policy:
        policy = AccessPolicy(
            user_id=target.id,
            company_id=company,
            grants=legacy_grants(db, target),
            version=0,
        )
        db.add(policy)
    policy.grants = {**policy.grants, **grants}
    policy.status = status
    policy.version += 1
    policy.updated_by = actor.id
    db.query(UserSession).filter_by(user_id=target.id).update(
        {UserSession.status: "Revoked"}, synchronize_session="fetch"
    )
    audit(
        db,
        actor,
        company,
        "access.updated",
        reason,
        before={"grants": before["grants"], "status": before["status"]},
        after={"grants": policy.grants, "status": status},
        target=target.id,
        request=request,
    )
    db.flush()
    return snapshot(db, target, company)


def bind_authorization(db, user, request):
    company = primary_company(user)
    requested = request.headers.get("X-Suite-Organization")
    if requested:
        try:
            requested = int(requested)
        except ValueError:
            raise HTTPException(403, "Invalid organization context")
        if not user.is_superuser and requested not in companies_for(db, user):
            raise HTTPException(403, "Organization membership required")
        company = requested
    user.organization_id = company
    user._suite_permission_objects = None
    policy = policy_for(db, user, company)
    user._suite_grants = (
        resolved_grants(db, policy) if policy and not user.is_superuser else None
    )
    if policy and policy.status != "active":
        raise HTTPException(403, "Access to this organization is " + policy.status)
    module = request_module(request)
    if user._suite_grants is None:
        return lambda: None
    grants = user._suite_grants
    objects = db.query(Permission).all()
    selected = set()
    for grant in grants.values():
        if grant.get("enabled"):
            selected.update(grant.get("permissions", []))
    user._suite_permission_objects = [p for p in objects if p.name in selected]
    if module:
        grant = grants.get(module, {})
        if not grant.get("enabled"):
            raise HTTPException(403, f"Module access revoked: {module}")
        action = action_for(request)
        if action not in grant.get("actions", []):
            raise HTTPException(403, f"Module action denied: {module}/{action}")
    if request.url.path.startswith("/api/v1/access/"):
        return lambda: setattr(user, "_suite_permission_objects", None)
    from app.access.scope import install_scope

    return install_scope(db, user, company, grants)


def check_background_access(db, user, module, action="view"):
    company = getattr(user, "organization_id", primary_company(user))
    policy = policy_for(db, user, company)
    if user.is_superuser or not policy:
        return None
    grant = resolved_grants(db, policy).get(module, {})
    if (
        policy.status != "active"
        or not grant.get("enabled")
        or action not in grant.get("actions", [])
    ):
        raise HTTPException(
            403,
            "Effective access changed; background operation is no longer authorized",
        )
    return policy


from contextlib import contextmanager


@contextmanager
def background_scope(db, user, module, action="view"):
    policy = check_background_access(db, user, module, action)
    cleanup = None
    if policy and getattr(user, "_suite_grants", None) is None:
        from app.access.scope import install_scope

        grants = resolved_grants(db, policy)
        user._suite_grants = grants
        user._suite_permission_objects = None
        cleanup = install_scope(db, user, policy.company_id, grants)
    try:
        yield
    finally:
        if cleanup:
            cleanup()
