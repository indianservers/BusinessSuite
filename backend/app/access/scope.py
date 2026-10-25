"""Additional fail-closed tenant/record filters for centrally managed accounts.

Existing module membership checks remain in force. These filters can narrow them;
they do not replace project memberships or document ownership rules.
"""

from fastapi import HTTPException
from sqlalchemy import and_, or_, false, func, select, event
from sqlalchemy.orm import with_loader_criteria
from app.db.base_class import Base


def model_module(model):
    source = model.__module__
    from app.module_registry import APP_MODULES

    for module in APP_MODULES.values():
        if source in module.model_modules and not source.endswith(
            ("models.user", "models.company", "models.audit", "models.notification")
        ):
            return module.key
    if source.startswith("app.apps."):
        key = source.split(".")[2]
        return {"ai_copilot": "ai", "admin_security": "security"}.get(key, key)
    if source.startswith("app.forms."):
        return "forms"
    if source.startswith("app.ai_agents."):
        return "ai"
    if source.startswith("app.ai_operator."):
        return "project_management"
    if source.startswith("app.models.") and source.rsplit(".", 1)[1] not in {
        "user",
        "company",
        "audit",
        "notification",
        "deployment",
        "sso",
    }:
        return "hrms"
    return None


def install_scope(db, user, company, grants):
    from app.models.employee import Employee
    from app.models.company import Branch

    employee = getattr(user, "employee", None)
    branch = employee.branch_id if employee else None
    department = employee.department_id if employee else None
    all_models = {
        mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers
    }
    own_users = [user.id]
    scope_users = {"own": own_users, "assigned": own_users}
    employees = (
        db.query(
            Employee.id,
            Employee.user_id,
            Employee.reporting_manager_id,
            Employee.department_id,
            Employee.branch_id,
        )
        .filter(
            or_(
                Employee.branch.has(Branch.company_id == company),
                (Employee.branch_id.is_(None)) & (company == 1),
            )
        )
        .all()
    )
    scope_users["team"] = [user.id] + [
        e.user_id
        for e in employees
        if employee and e.reporting_manager_id == employee.id and e.user_id
    ]
    scope_users["department"] = [
        e.user_id
        for e in employees
        if department and e.department_id == department and e.user_id
    ]
    scope_users["branch"] = [
        e.user_id for e in employees if branch and e.branch_id == branch and e.user_id
    ]
    cache = {}

    def predicate(model, stack=()):
        if model in cache:
            return cache[model]
        if model in stack:
            return false()
        key = model_module(model)
        if key is None:
            return None
        grant = grants.get(key, {})
        if not grant.get("enabled"):
            return false()
        scope = grant.get("scope", "own")
        columns = model.__table__.c
        tenant = None
        if "organization_id" in columns:
            tenant = func.coalesce(model.organization_id, 1) == company
        elif "company_id" in columns and key not in {"crm", "srm"}:
            tenant = model.company_id == company
        owner = []
        if scope != "organization":
            ids = scope_users.get(scope, own_users)
            fields = (
                "owner_user_id",
                "assignee_user_id",
                "assigned_to_user_id",
                "user_id",
                "manager_user_id",
                "requester_user_id",
            )
            if scope != "assigned":
                fields += ("created_by_user_id", "created_by", "uploaded_by")
            for name in fields:
                if name in columns:
                    owner.append(getattr(model, name).in_(ids))
            if model is Employee:
                owner.append(Employee.user_id.in_(ids))
            if key == "project_management" and model.__tablename__ == "pms_tasks":
                from app.apps.project_management.models import PMSTaskAssignee

                table = PMSTaskAssignee.__table__
                owner.append(
                    model.id.in_(
                        select(table.c.task_id).where(table.c.user_id.in_(ids))
                    )
                )
            if key == "crm" and scope == "team" and "assigned_team_id" in columns:
                from app.apps.crm.models import CRMOwner

                table = CRMOwner.__table__
                owner.append(
                    model.assigned_team_id.in_(
                        select(table.c.team_id).where(
                            table.c.user_id.in_(ids), table.c.organization_id == company
                        )
                    )
                )
            if key == "project_management" and model.__tablename__ == "pms_projects":
                from app.apps.project_management.models import PMSProjectMember

                table = PMSProjectMember.__table__
                owner.append(
                    model.id.in_(
                        select(table.c.project_id).where(table.c.user_id.in_(ids))
                    )
                )
            if key == "project_management" and model.__tablename__ == "pms_workspaces":
                from app.apps.project_management.models import PMSWorkspaceMember

                table = PMSWorkspaceMember.__table__
                owner.append(
                    model.id.in_(
                        select(table.c.workspace_id).where(table.c.user_id.in_(ids))
                    )
                )
            if scope == "branch" and branch and "branch_id" in columns:
                owner.append(model.branch_id == branch)
            if scope == "department" and department and "department_id" in columns:
                owner.append(model.department_id == department)
        parents = []
        # Auxiliary records follow their business parent, not their own creator.
        for field in (
            "employee_id",
            "task_id",
            "project_id",
            "lead_id",
            "invoice_id",
            "workspace_id",
        ):
            if field not in columns:
                continue
            for fk in columns[field].foreign_keys:
                parent = all_models.get(fk.column.table.name)
                if parent is None or parent in stack or parent is model:
                    continue
                allowed = predicate(parent, (*stack, model))
                if allowed is not None:
                    parents.append(
                        getattr(model, field).in_(select(parent.id).where(allowed))
                    )
        if parents:
            # An employee/project/task link never widens access to its parent.
            result = and_(*([tenant] if tenant is not None else []), *parents)
            if (
                model.__tablename__ in {"pms_tasks", "pms_task_assignees"}
                and scope != "organization"
            ):
                result = and_(result, or_(*owner) if owner else false())
        elif scope == "organization":
            result = tenant if tenant is not None else false()
        else:
            result = and_(
                *([tenant] if tenant is not None else []),
                or_(*owner) if owner else false(),
            )
        cache[model] = result
        return result

    criteria = []
    for model in all_models.values():
        allowed = predicate(model)
        if allowed is not None:
            criteria.append(with_loader_criteria(model, allowed, include_aliases=True))

    def restrict(execution):
        if execution.is_select or execution.is_update or execution.is_delete:
            execution.statement = execution.statement.options(*criteria)

    def validate(session, flush_context, instances):
        for item in session.new | session.dirty | session.deleted:
            key = model_module(type(item))
            if key is None:
                continue
            grant = grants.get(key, {})
            if not grant.get("enabled"):
                raise HTTPException(403, f"Writes to disabled module {key} are blocked")
            value = getattr(item, "organization_id", company)
            if value is not None and value != company:
                raise HTTPException(403, "Cross-organization write blocked")
            if grant.get("scope") != "organization":
                ids = scope_users.get(grant.get("scope"), own_users)
                fields = [
                    f
                    for f in (
                        "owner_user_id",
                        "assignee_user_id",
                        "user_id",
                        "created_by_user_id",
                        "created_by",
                    )
                    if hasattr(type(item), f)
                ]
                if fields and not any(getattr(item, f, None) in ids for f in fields):
                    raise HTTPException(
                        403, "Record is outside the assigned data scope"
                    )
                for field in (
                    "employee_id",
                    "task_id",
                    "project_id",
                    "lead_id",
                    "invoice_id",
                ):
                    column = type(item).__table__.c.get(field)
                    value = getattr(item, field, None)
                    if column is None or value is None:
                        continue
                    for fk in column.foreign_keys:
                        parent = all_models.get(fk.column.table.name)
                        if parent is not None and predicate(parent) is not None:
                            with session.no_autoflush:
                                if (
                                    not session.query(parent.id)
                                    .filter(parent.id == value, predicate(parent))
                                    .first()
                                ):
                                    raise HTTPException(
                                        403,
                                        "Linked record is outside the assigned data scope",
                                    )

    event.listen(db, "do_orm_execute", restrict)
    event.listen(db, "before_flush", validate)

    def cleanup():
        event.remove(db, "do_orm_execute", restrict)
        event.remove(db, "before_flush", validate)
        user._suite_permission_objects = None
        user._suite_grants = None

    return cleanup
