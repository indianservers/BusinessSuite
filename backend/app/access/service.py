from __future__ import annotations
import copy
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func, inspect
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
    if not schema_ready(db):
        return {primary_company(user)}
    return {primary_company(user)} | {
        row.company_id
        for row in db.query(AccessMembership).filter_by(user_id=user.id, active=True)
    }


def policy_for(db, user, company):
    if not schema_ready(db):
        return None
    cached = db.info.get("suite_access_policies", {})
    if company in cached:
        return cached[company].get(user.id)
    return db.query(AccessPolicy).filter_by(user_id=user.id, company_id=company).first()


def schema_ready(db):
    if "suite_access_schema_ready" not in db.info:
        db.info["suite_access_schema_ready"] = inspect(db.connection()).has_table(
            "suite_access_policies"
        )
    return db.info["suite_access_schema_ready"]


def legacy_grants(db, user, company=None):
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
    employee = getattr(user, "employee", None)
    is_intern = (user.role and user.role.name.lower() == "intern") or (
        employee and (employee.employment_type or "").lower() == "intern"
    )
    if is_intern:
        for key, grant in by_module.items():
            grant["enabled"] = key == "interns_hub"
        if "interns_hub" in by_module:
            by_module["interns_hub"].update(
                role="Intern", actions=["view", "create", "edit"], scope="own"
            )
    from app.access.entitlements import apply

    return apply(
        db,
        company or getattr(user, "organization_id", None) or primary_company(user),
        by_module,
    )


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
                    roleVersion=role.version,
                    permissions=role.permissions,
                    actions=role.actions,
                    scope=grant.get("scope") or role.scope,
                )
    from app.access.entitlements import apply

    return apply(db, policy.company_id, grants)


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
            "roleVersion",
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
        if not isinstance(grant["role"], str) or not 1 <= len(grant["role"]) <= 100:
            raise HTTPException(422, "Invalid role name")
        if (
            not isinstance(grant["permissions"], list)
            or len(grant["permissions"]) > 500
            or any(not isinstance(n, str) for n in grant["permissions"])
        ):
            raise HTTPException(422, "Permissions must be a list of registered names")
        if not isinstance(grant["actions"], list) or any(
            not isinstance(n, str) for n in grant["actions"]
        ):
            raise HTTPException(422, "Actions must be a list")
        if grant["scope"] not in SCOPES or not set(grant["actions"]) <= set(ACTIONS):
            raise HTTPException(422, "Invalid action or scope")
        names = {p["name"] for p in modules[key]["permissions"]}
        if not set(grant["permissions"]) <= names:
            raise HTTPException(422, f"Permission does not belong to {key}")
        if grant.get("roleId"):
            if type(grant["roleId"]) is not int:
                raise HTTPException(422, "Invalid module role identifier")
            role = (
                db.query(AccessRole)
                .filter_by(id=grant["roleId"])
                .with_for_update()
                .populate_existing()
                .first()
            )
            if (
                not role
                or role.company_id != company
                or role.module_key != key
                or not role.active
            ):
                raise HTTPException(422, "Invalid module role")
            if grant.get("roleVersion") != role.version:
                raise HTTPException(
                    409, "Module role changed; reload and review the assignment"
                )
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
        legacy_grants(db, user, company)
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
            policy.status
            if policy and (user.is_active or policy.status == "invited")
            else "active" if user.is_active else "deactivated"
        ),
        "lastLogin": user.last_login.isoformat() if user.last_login else None,
        "updatedAt": user.updated_at.isoformat() if user.updated_at else None,
        "branch": employee.branch.name if employee and employee.branch else None,
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
    if request:
        after = {
            **(after or {}),
            "requestId": getattr(request.state, "request_id", None),
        }
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
        .populate_existing()
        .all()
    )


def apply_user(db, actor, target, company, patch, reason, request):
    if company not in companies_for(db, target):
        raise HTTPException(404, "User is not a member of this organization")
    if target.is_superuser:
        raise HTTPException(
            409,
            "Global Super Admin accounts are read-only in this console",
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
    if status == "active" and not target.is_active:
        if target.password_reset_token:
            raise HTTPException(
                409,
                "Complete the outstanding invitation before activating this account",
            )
        if not actor.is_superuser:
            raise HTTPException(
                403,
                "A global administrator must reactivate a globally inactive account",
            )
        target.is_active = True
    if not policy:
        policy = AccessPolicy(
            user_id=target.id,
            company_id=company,
            grants=legacy_grants(db, target, company),
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
    db.info.pop("suite_access_schema_ready", None)
    db.info.pop("suite_access_catalog", None)
    db.info.pop("suite_access_policies", None)
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
    user._suite_original_organization = getattr(user, "organization_id", None)
    user.organization_id = company
    user._suite_permission_objects = None
    policy = policy_for(db, user, company)
    user._suite_policy_version = (
        policy.version if policy and not user.is_superuser else None
    )
    user._suite_grants = (
        resolved_grants(db, policy) if policy and not user.is_superuser else None
    )
    if policy and policy.status != "active":
        reset_authorization(user)
        raise HTTPException(403, "Access to this organization is " + policy.status)
    module = request_module(request)
    from app.access.entitlements import enforce

    enforce(db, company, module)
    from app.enterprise.controls import governance_module_check
    governance_module_check(db,user,company,module,action_for(request))
    from app.enterprise.controls import reserve_api_request
    reserve_api_request(db,user,company,module)
    user._suite_current_module = module
    if user._suite_grants is None:
        user._suite_permission_objects = list(
            user.role.permissions if user.role else []
        )
        return lambda: reset_authorization(user)
    grants = user._suite_grants
    user._suite_permission_objects = effective_objects(db, grants, module)
    if module:
        grant = grants.get(module, {})
        if not grant.get("enabled"):
            reset_authorization(user)
            raise HTTPException(403, f"Module access revoked: {module}")
        action = action_for(request)
        if action not in grant.get("actions", []):
            reset_authorization(user)
            raise HTTPException(403, f"Module action denied: {module}/{action}")
    if request.url.path.startswith("/api/v1/access/"):
        return lambda: reset_authorization(user)
    from app.access.scope import install_scope

    return install_scope(db, user, company, grants)


def reset_authorization(user):
    user._suite_grants = None
    user._suite_permission_objects = None
    user._suite_current_module = None
    user._suite_policy_version = None
    user._suite_scope_active = False
    if hasattr(user, "_suite_original_organization"):
        previous = user._suite_original_organization
        if previous is None:
            user.__dict__.pop("organization_id", None)
        else:
            user.organization_id = previous
        user.__dict__.pop("_suite_original_organization", None)


def effective_objects(db, grants, module=None):
    selected = {
        name
        for grant in grants.values()
        if grant.get("enabled")
        for name in grant.get("permissions", [])
    }
    prefixes = tuple(key + "_" for key in MODULES) + ("pms_", "intern_", "interns_")
    result = []
    for permission in db.query(Permission).filter(Permission.name.in_(selected)).all():
        if permission.name.startswith(prefixes):
            own = grants.get(permission_module(permission), {})
            if not own.get("enabled") or permission.name not in own.get(
                "permissions", []
            ):
                continue
        elif module and permission.name not in grants.get(module, {}).get(
            "permissions", []
        ):
            continue
        result.append(permission)
    return result


def check_background_access(db, user, module, action="view"):
    company = getattr(user, "organization_id", None) or primary_company(user)
    from app.access.entitlements import enforce

    enforce(db, company, module)
    from app.enterprise.controls import governance_module_check
    governance_module_check(db,user,company,module,action)
    policy = policy_for(db, user, company)
    if user.is_superuser:
        return None
    if not policy:
        from app.access.catalog import permission_objects, permission_module
        relevant = [p.name for p in permission_objects(user) if permission_module(p) == module]
        writes = ("manage", "admin", "create", "edit", "update", "approve", "assign", "delete")
        if not relevant or (action != "view" and not any(any(word in name for word in writes) for name in relevant)):
            raise HTTPException(403, "Background operation requires the current module permission")
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
    from contextlib import ExitStack
    from app.core.tenant_boundary import install as install_boundary
    if not user.is_active:
        raise HTTPException(403, "Background actor is inactive")
    company = getattr(user, "organization_id", None) or primary_company(user)
    with ExitStack() as stack:
        policy = check_background_access(db, user, module, action)
        if policy and not getattr(user, "_suite_scope_active", False):
            from app.access.scope import install_scope
            grants = resolved_grants(db, policy)
            user._suite_grants = grants
            user._suite_current_module = module
            user._suite_permission_objects = None
            stack.callback(install_scope(db, user, policy.company_id, grants))
        stack.callback(install_boundary(db, user, company))
        yield



def activate_run_context(db, user, run):
    scope = str(run.scope_key or "")
    if scope.startswith("company:"):
        try:
            company = int(scope.split(":", 1)[1])
        except ValueError:
            raise HTTPException(403, "Invalid stored run organization")
    elif scope.startswith("workspace:"):
        from app.apps.project_management.models import PMSWorkspace

        workspace = db.get(PMSWorkspace, int(scope.split(":", 1)[1]))
        if not workspace:
            raise HTTPException(403, "Run workspace is no longer available")
        company = workspace.organization_id or 1
    elif scope == f"user:{user.id}":
        company = primary_company(user)
    else:
        raise HTTPException(403, "Unsupported stored run scope")
    if not user.is_superuser and company not in companies_for(db, user):
        raise HTTPException(403, "Run organization membership was revoked")
    if getattr(user, "_suite_scope_active", False) or hasattr(
        user, "_suite_original_organization"
    ):
        if (getattr(user, "organization_id", None) or primary_company(user)) != company:
            raise HTTPException(403, "Switch to the run's authorized organization")
        return
    if "suite_run_context" not in db.info:
        db.info["suite_run_context"] = (user, getattr(user, "organization_id", None))
    user.organization_id = None if scope.startswith("user:") else company


def release_run_context(db):
    previous = db.info.pop("suite_run_context", None)
    if previous:
        user, company = previous
        if company is None:
            user.__dict__.pop("organization_id", None)
        else:
            user.organization_id = company


def isolated_run_context(function):
    from functools import wraps

    @wraps(function)
    def wrapped(db, *args, **kwargs):
        try:
            return function(db, *args, **kwargs)
        finally:
            release_run_context(db)

    return wrapped
