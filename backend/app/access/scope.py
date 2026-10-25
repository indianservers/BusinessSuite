"""Additional fail-closed tenant/record filters for centrally managed accounts.

Existing module membership checks remain in force. These filters can narrow them;
they do not replace project memberships or document ownership rules.
"""

from fastapi import HTTPException
import re
from sqlalchemy import and_, or_, false, func, select, event, inspect
from sqlalchemy.orm import with_loader_criteria
from app.db.base_class import Base


def model_module(model):
    source = model.__module__
    if source == "app.models.approval_os":
        return "approvals"
    if source == "app.models.workflow_engine":
        return "automation"
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
    from app.models.user import User
    from app.common.models import CommonPerson

    employee = getattr(user, "employee", None)
    branch = employee.branch_id if employee else None
    department = employee.department_id if employee else None
    all_models = {
        mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers
    }
    own_users = [user.id]
    tenant_users = [
        row.id
        for row in db.query(User.id)
        .outerjoin(CommonPerson, CommonPerson.user_id == User.id)
        .outerjoin(Employee, Employee.user_id == User.id)
        .outerjoin(Branch, Branch.id == Employee.branch_id)
        .filter(
            func.coalesce(CommonPerson.organization_id, Branch.company_id, 1) == company
        )
        .all()
    ]
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
        if model.__tablename__ == "notifications":
            enabled = {key for key, grant in grants.items() if grant.get("enabled")}
            if "project_management" in enabled:
                enabled.add("pms")
            if "fam" in enabled:
                enabled.add("finance")
            return and_(
                model.user_id == user.id,
                or_(model.company_id == company, model.company_id.is_(None)),
                or_(
                    model.module.is_(None),
                    model.module.in_([*enabled, "system", "auth", "access", ""]),
                ),
            )
        if model.__module__ == "app.models.company":
            from app.models.company import Company, Branch, Department

            table = model.__table__
            if model is Company:
                allowed = Company.id == company
                if getattr(user, "_suite_current_module", None) in {
                    "srm",
                    "fam",
                    "project_management",
                }:
                    from app.apps.srm.commercial_models import SellerGrant

                    grant = SellerGrant.__table__
                    allowed = or_(
                        allowed,
                        Company.id.in_(
                            select(grant.c.seller_id).where(
                                grant.c.organization_id == company,
                                grant.c.active.is_(True),
                            )
                        ),
                    )
                return allowed
            if "company_id" in table.c:
                return model.company_id == company
            if "branch_id" in table.c:
                return model.branch_id.in_(
                    select(Branch.__table__.c.id).where(
                        Branch.__table__.c.company_id == company
                    )
                )
            if "department_id" in table.c:
                return model.department_id.in_(
                    select(Department.__table__.c.id)
                    .join(
                        Branch.__table__,
                        Branch.__table__.c.id == Department.__table__.c.branch_id,
                    )
                    .where(Branch.__table__.c.company_id == company)
                )
            if "organization_id" in table.c:
                return func.coalesce(model.organization_id, 1) == company
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
        elif not any(
            field in columns
            for field in (
                "employee_id",
                "task_id",
                "project_id",
                "lead_id",
                "invoice_id",
                "workspace_id",
                "request_id",
                "instance_id",
                "form_id",
                "approval_id",
            )
        ):
            for origin in (
                "requester_user_id",
                "initiated_by_user_id",
                "owner_user_id",
                "user_id",
                "created_by_user_id",
                "created_by",
            ):
                if origin in columns:
                    tenant = getattr(model, origin).in_(tenant_users)
                    break
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
                "delegated_to_user_id",
                "escalation_user_id",
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
        guards, parent_access = [], []
        for field in (
            "employee_id",
            "task_id",
            "project_id",
            "lead_id",
            "invoice_id",
            "workspace_id",
            "request_id",
            "instance_id",
            "form_id",
            "approval_id",
        ):
            if field not in columns:
                continue
            for fk in columns[field].foreign_keys:
                parent = all_models.get(fk.column.table.name)
                if parent is None or parent in stack or parent is model:
                    continue
                allowed = predicate(parent, (*stack, model))
                if allowed is not None:
                    access = getattr(model, field).in_(select(parent.id).where(allowed))
                    parent_access.append(access)
                    guards.append(
                        or_(getattr(model, field).is_(None), access)
                        if columns[field].nullable
                        else access
                    )
        if model.__tablename__ == "crm_timeline_events":
            links = []
            for kind, table in (
                ("lead", "crm_leads"),
                ("contact", "crm_contacts"),
                ("company", "crm_companies"),
                ("deal", "crm_deals"),
            ):
                parent = all_models.get(table)
                if parent:
                    links.append(
                        and_(
                            model.record_type == kind,
                            model.record_id.in_(
                                select(parent.id).where(
                                    predicate(parent, (*stack, model))
                                )
                            ),
                        )
                    )
            access = or_(*links) if links else false()
            parent_access.append(access)
            guards.append(access)
        own = or_(*owner) if owner else false()
        inherited = or_(*parent_access) if parent_access else false()
        if scope == "organization":
            result = and_(tenant if tenant is not None else inherited, *guards)
        else:
            roots = {
                "pms_projects",
                "pms_workspaces",
                "pms_tasks",
                "pms_task_assignees",
                "crm_leads",
                "crm_deals",
                "crm_companies",
                "crm_contacts",
            }
            record = own if model.__tablename__ in roots else or_(own, inherited)
            result = and_(*([tenant] if tenant is not None else []), *guards, record)
        cache[model] = result
        return result

    criteria = []
    for model in all_models.values():
        allowed = predicate(model)
        if allowed is not None:
            criteria.append(with_loader_criteria(model, allowed, include_aliases=True))

    def restrict(execution):
        if not execution.is_orm_statement:
            sql = str(execution.statement).lower()
            protected = [
                name
                for name, model in all_models.items()
                if model_module(model) is not None
                or model.__module__ == "app.models.company"
            ]
            if any(
                re.search(r"\b" + re.escape(name) + r"\b", sql) for name in protected
            ):
                raise HTTPException(
                    403,
                    "This legacy query requires an explicit central access scope adapter",
                )
        if execution.is_select or execution.is_update or execution.is_delete:
            execution.statement = execution.statement.options(*criteria)

    def validate(session, flush_context, instances):
        for item in session.new | session.dirty | session.deleted:
            if type(item).__module__ == "app.models.company":
                from app.models.company import Company

                if isinstance(item, Company) and (
                    item in session.new or item.id != company
                ):
                    raise HTTPException(
                        403,
                        "Only a global administrator may create or change another organization",
                    )
                if hasattr(type(item), "company_id") and item.company_id != company:
                    raise HTTPException(403, "Cross-organization configuration blocked")
                if hasattr(type(item), "organization_id"):
                    if item in session.new and item.organization_id is None:
                        item.organization_id = company
                    if (
                        item.organization_id is not None
                        and item.organization_id != company
                    ):
                        raise HTTPException(
                            403, "Cross-organization configuration blocked"
                        )
                elif not isinstance(item, Company) and not any(
                    hasattr(type(item), field)
                    for field in ("company_id", "branch_id", "department_id")
                ):
                    raise HTTPException(
                        403, "Global configuration requires a global Super Admin"
                    )
            key = model_module(type(item))
            if key is None:
                continue
            grant = grants.get(key, {})
            if not grant.get("enabled"):
                raise HTTPException(403, f"Writes to disabled module {key} are blocked")
            columns = type(item).__table__.c
            if (
                item in session.new
                and "organization_id" in columns
                and item.organization_id is None
            ):
                item.organization_id = company
            if grant.get("scope") == "organization" and not any(
                key in columns
                for key in (
                    "company_id",
                    "organization_id",
                    "project_id",
                    "task_id",
                    "employee_id",
                    "lead_id",
                    "invoice_id",
                    "workspace_id",
                    "user_id",
                    "owner_user_id",
                )
            ):
                raise HTTPException(
                    403, "Global configuration requires a global Super Admin"
                )
            value = getattr(item, "organization_id", company)
            if value is not None and value != company:
                raise HTTPException(403, "Cross-organization write blocked")
            if not any(
                field in columns for field in ("organization_id", "company_id")
            ) and not any(
                field in columns and getattr(item, field, None) is not None
                for field in (
                    "employee_id",
                    "task_id",
                    "project_id",
                    "lead_id",
                    "invoice_id",
                    "workspace_id",
                    "request_id",
                    "instance_id",
                    "form_id",
                    "approval_id",
                )
            ):
                origin = next(
                    (
                        field
                        for field in (
                            "requester_user_id",
                            "initiated_by_user_id",
                            "owner_user_id",
                            "user_id",
                            "created_by_user_id",
                            "created_by",
                        )
                        if field in columns
                    ),
                    None,
                )
                if not origin or getattr(item, origin, None) not in tenant_users:
                    raise HTTPException(
                        403, "A tenant-owned record or authorized parent is required"
                    )
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
                    assigned = type(item).__tablename__ == "pms_tasks" and any(
                        a.user_id in ids for a in getattr(item, "assignments", [])
                    )
                    existing = False
                    if (
                        item not in session.new
                        and getattr(item, "id", None) is not None
                    ):
                        with session.no_autoflush:
                            existing = (
                                session.query(type(item).id)
                                .filter(type(item).id == item.id, predicate(type(item)))
                                .first()
                                is not None
                            )
                    if not assigned and not existing:
                        raise HTTPException(
                            403, "Record is outside the assigned data scope"
                        )
                for field in fields:
                    history = inspect(item).attrs[field].history
                    if (
                        item not in session.new
                        and history.has_changes()
                        and any(
                            value is not None and value not in ids
                            for value in history.added
                        )
                    ):
                        raise HTTPException(
                            403, "Assignment is outside the allowed data scope"
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
    original_get, original_refresh = db.get, db.refresh

    def visible_identity(model, ident):
        model = getattr(model, "class_", model)
        if model not in all_models.values():
            return True
        allowed = predicate(model)
        if allowed is None:
            return True
        keys = inspect(model).primary_key
        values = (
            [ident.get(key.key) for key in keys]
            if isinstance(ident, dict)
            else list(ident) if isinstance(ident, (tuple, list)) else [ident]
        )
        if len(keys) != len(values):
            return False
        with db.no_autoflush:
            return (
                db.query(*keys)
                .filter(allowed, *(key == value for key, value in zip(keys, values)))
                .first()
                is not None
            )

    def scoped_get(model, ident, **kwargs):
        return (
            original_get(model, ident, **kwargs)
            if visible_identity(model, ident)
            else None
        )

    def scoped_refresh(instance, *args, **kwargs):
        if not visible_identity(type(instance), inspect(instance).identity):
            raise HTTPException(404, "Record not found in the authorized data scope")
        return original_refresh(instance, *args, **kwargs)

    db.get, db.refresh = scoped_get, scoped_refresh
    user._suite_scope_active = True

    def cleanup():
        db.get, db.refresh = original_get, original_refresh
        event.remove(db, "do_orm_execute", restrict)
        event.remove(db, "before_flush", validate)
        from app.access.service import reset_authorization

        reset_authorization(user)

    return cleanup
