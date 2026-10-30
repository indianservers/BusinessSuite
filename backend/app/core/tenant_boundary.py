"""Company isolation for every authenticated ORM session, including legacy roles.

Module record/ownership permissions still narrow this boundary. Tenantless global
catalogues are read-only to ordinary accounts; unknown ownership fails closed.
"""

import logging
import re
from fastapi import HTTPException
from sqlalchemy import and_, or_, false, select, event, inspect, func, literal, cast, String
from sqlalchemy.orm import with_loader_criteria, Session
from app.db.base_class import Base

logger = logging.getLogger("businesssuite.security")
# These are installation-wide reference catalogues, not private business records.
GLOBAL_CATALOGUES = frozenset(
    {
        "roles",
        "permissions",
        "role_permissions",
        "password_policies",
        "ip_access_policies",
        "tax_regimes",
        "tax_sections",
        "pf_rules",
        "esi_rules",
        "professional_tax_slabs",
        "lwf_slabs",
        "gratuity_rules",
        "feature_plans",
        "tenant_subscription_plans",
        "bos_modules",
        "bos_module_dependencies",
        "ai_agents",
        "ai_agent_tools",
        "portal_roles",
    }
)
INTERNAL_TABLES = frozenset(
    {
        "security_rate_buckets",
        "power_automation_workers",
        "security_work_leases",
        "suite_form_rate_buckets",
        "security_resource_ownership",
    }
)
# Pure actor stamps are not ownership: an admin may create a row in another company.
ACTOR_FIELDS = frozenset(
    {
        "created_by",
        "created_by_user_id",
        "updated_by",
        "updated_by_user_id",
        "approved_by",
        "reviewed_by",
        "uploaded_by",
        "actor_id",
        "actor_user_id",
        "invited_by",
        "deleted_by",
        "rejected_by",
        "cancelled_by",
        "sent_by_user_id",
        "reporter_user_id",
        "author_user_id",
        "assigned_by",
        "added_by",
        "submitted_by",
    }
)


def company_ids(db, user):
    from app.common.models import CommonPerson
    from app.models.company import Branch
    from app.models.employee import Employee
    from app.access.models import AccessMembership

    person = CommonPerson.__table__
    employee, branch = Employee.__table__, Branch.__table__
    ids = set(
        db.connection()
        .execute(
            select(person.c.organization_id).where(
                person.c.user_id == user.id, person.c.organization_id.is_not(None)
            )
        )
        .scalars()
    )
    ids.update(
        db.connection()
        .execute(
            select(branch.c.company_id)
            .select_from(employee.join(branch, employee.c.branch_id == branch.c.id))
            .where(employee.c.user_id == user.id)
        )
        .scalars()
    )
    membership = AccessMembership.__table__
    ids.update(
        db.connection()
        .execute(
            select(membership.c.company_id).where(
                membership.c.user_id == user.id, membership.c.active.is_(True)
            )
        )
        .scalars()
    )
    return {int(value) for value in ids if value is not None}


def install(db, user, company, *, verified_portal=False):
    if db.info.get("security_boundary"):
        return lambda: None
    if (
        not verified_portal
        and not user.is_superuser
        and company not in company_ids(db, user)
    ):
        raise HTTPException(403, "Verified company membership is required")
    if user.is_superuser:
        return lambda: None
    from app.models.company import Company

    if (
        not db.connection()
        .execute(
            select(Company.id).where(Company.id == company, Company.is_active.is_(True))
        )
        .first()
    ):
        raise HTTPException(403, "Company context is unavailable")
    # Global Super Admin is the existing installation-wide authority, not a role string.
    if user.is_superuser:
        return lambda: None
    from app.models.user import User
    from app.common.models import CommonPerson
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.access.models import AccessMembership

    models = {
        mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers
    }
    person, emp, branch, membership = (
        CommonPerson.__table__,
        Employee.__table__,
        Branch.__table__,
        AccessMembership.__table__,
    )
    member_users = select(User.__table__.c.id).where(
        or_(
            User.__table__.c.id.in_(
                select(person.c.user_id).where(person.c.organization_id == company)
            ),
            User.__table__.c.id.in_(
                select(emp.c.user_id)
                .select_from(emp.join(branch, emp.c.branch_id == branch.c.id))
                .where(branch.c.company_id == company)
            ),
            User.__table__.c.id.in_(
                select(membership.c.user_id).where(
                    membership.c.company_id == company, membership.c.active.is_(True)
                )
            ),
        )
    )
    cache = {}

    def predicate(model, stack=()):
        if model in cache:
            return cache[model]
        table = model.__table__
        if table.name in GLOBAL_CATALOGUES:
            return None
        if table.name in INTERNAL_TABLES:
            return false()
        if model in stack:
            return None
        if model is Company:
            result = table.c.id == company
            if getattr(user, "_suite_current_module", None) in {
                "srm",
                "fam",
                "project_management",
            }:
                from app.apps.srm.commercial_models import SellerGrant

                sellers = SellerGrant.__table__
                result = or_(
                    result,
                    table.c.id.in_(
                        select(sellers.c.seller_id).where(
                            sellers.c.organization_id == company,
                            sellers.c.active.is_(True),
                        )
                    ),
                )
        elif table.name in {"ai_operator_providers", "ai_operator_api_logs"}:
            result = table.c.scope_key.in_([f"company:{company}", f"user:{user.id}"])
            workspace_model = models.get("pms_workspaces")
            if workspace_model is not None:
                workspace = workspace_model.__table__
                workspace_scopes = select(literal("workspace:") + cast(workspace.c.id, String)).where(predicate(workspace_model, (*stack, model)))
                result = or_(result, table.c.scope_key.in_(workspace_scopes))
        elif model is User:
            result = table.c.id.in_(member_users)
        elif model.__module__ == "app.models.company" and any(
            name in table.c for name in ("company_id", "branch_id", "department_id")
        ):
            parent_guard = None
            if "company_id" in table.c:
                parent_guard = table.c.company_id == company
                anchor = table.c.company_id
            else:
                field = "branch_id" if "branch_id" in table.c else "department_id"
                anchor = table.c[field]
                parent = models[next(iter(anchor.foreign_keys)).column.table.name]
                parent_guard = anchor.in_(
                    select(parent.__table__.c.id).where(
                        predicate(parent, (*stack, model))
                    )
                )
            if "organization_id" in table.c:
                result = and_(
                    or_(
                        table.c.organization_id == company,
                        and_(table.c.organization_id.is_(None), parent_guard),
                    ),
                    or_(anchor.is_(None), parent_guard),
                )
            else:
                result = parent_guard
        elif table.name == "notifications":
            result = and_(
                table.c.user_id == user.id,
                or_(table.c.company_id == company, table.c.company_id.is_(None)),
            )
        elif model is Employee:
            reports = emp.alias("security_reporting_employee")
            managed = (
                select(reports.c.reporting_manager_id)
                .select_from(reports.join(branch, reports.c.branch_id == branch.c.id))
                .where(
                    branch.c.company_id == company,
                    reports.c.reporting_manager_id.is_not(None),
                )
            )
            result = or_(
                table.c.branch_id.in_(
                    select(branch.c.id).where(branch.c.company_id == company)
                ),
                and_(
                    table.c.branch_id.is_(None),
                    or_(
                        table.c.user_id.in_(member_users),
                        and_(table.c.user_id.is_(None), table.c.id.in_(managed)),
                    ),
                ),
            )
        elif table.name in {
            "user_sessions",
            "mfa_methods",
            "trusted_devices",
            "login_attempts",
        }:
            result = table.c.user_id == user.id
        else:
            direct = []
            if "organization_id" in table.c:
                direct.append(func.coalesce(table.c.organization_id, 1) == company)
            # FK targets decide whether company_id is a tenant or CRM customer.
            if tenant_company_column(model):
                direct.append(table.c.company_id == company)
            if direct:
                result = and_(*direct)
                cache[model] = result
                return result
            links = []
            anchors = {
                "branch_id",
                "employee_id",
                "task_id",
                "project_id",
                "workspace_id",
                "note_id",
                "folder_id",
                "lead_id",
                "invoice_id",
                "quotation_id",
                "batch_id",
                "application_id",
                "form_id",
                "instance_id",
                "request_id",
                "submission_id",
                "review_id",
                "conversation_id",
                "ticket_id",
                "job_id",
                "plan_id",
                "profile_id",
                "rule_id",
                "template_id",
            }
            candidates = [
                column
                for column in table.c
                if column.name in anchors and column.foreign_keys
            ]
            if not candidates:
                candidates = [
                    column
                    for column in table.c
                    if column.name not in ACTOR_FIELDS
                    and any(
                        fk.column.table.name != "users"
                        and fk.column.table.name not in GLOBAL_CATALOGUES
                        for fk in column.foreign_keys
                    )
                ]
            if not candidates:
                candidates = list(table.c)
            owner_fields = {
                "owner_id",
                "owner_user_id",
                "user_id",
                "assignee_user_id",
                "assigned_to_user_id",
                "requester_user_id",
                "target_user_id",
                "sender_user_id",
                "recipient_user_id",
            }
            candidates += [
                column
                for column in table.c
                if column.name in owner_fields
                and column.key not in {candidate.key for candidate in candidates}
            ]
            for column in candidates:
                if column.name in ACTOR_FIELDS:
                    continue
                for fk in column.foreign_keys:
                    parent = models.get(fk.column.table.name)
                    if (
                        parent is None
                        or parent is model
                        or parent in stack
                        or parent.__table__.name in GLOBAL_CATALOGUES
                    ):
                        continue
                    parent_guard = predicate(parent, (*stack, model))
                    if parent_guard is not None:
                        links.append(
                            (column, column.in_(select(fk.column).where(parent_guard)))
                        )
            if direct:
                result = and_(*direct)
            elif links:
                # Nullable links cannot make an unowned row visible.
                result = and_(
                    or_(*(access for _, access in links)),
                    *(
                        or_(column.is_(None), access) if column.nullable else access
                        for column, access in links
                    ),
                )
            else:
                if legacy_root(model):
                    from app.models.security_boundary import SecurityResourceOwnership

                    ownership = SecurityResourceOwnership.__table__
                    result = table.c.id.in_(
                        select(ownership.c.resource_id).where(
                            ownership.c.resource_table == table.name,
                            ownership.c.company_id == company,
                        )
                    )
                else:
                    result = false()
        cache[model] = result
        return result

    criteria = {model: predicate(model) for model in models.values()}
    options = [
        with_loader_criteria(
            model, guard, include_aliases=True, propagate_to_loaders=False
        )
        for model, guard in criteria.items()
        if guard is not None
    ]
    protected_names = [
        model.__table__.name for model, guard in criteria.items() if guard is not None
    ]

    def denied(action, model, ident=None):
        logger.warning(
            "security_event=company_access_denied actor=%s company=%s action=%s resource=%s",
            user.id,
            company,
            action,
            model.__table__.name,
        )
        raise HTTPException(
            403, "Resource is outside the authorized company or writable scope"
        )

    def visible(model, ident):
        guard = criteria.get(model)
        if guard is None:
            return True
        keys = inspect(model).primary_key
        values = (
            [ident.get(key.key) for key in keys]
            if isinstance(ident, dict)
            else list(ident)
            if isinstance(ident, (tuple, list))
            else [ident]
        )
        if len(keys) != len(values):
            return False
        with db.no_autoflush:
            return (
                db.query(*keys)
                .filter(guard, *(key == value for key, value in zip(keys, values)))
                .first()
                is not None
            )

    def validate_fields(model, values, new=False):
        table = model.__table__
        if table.name in {"ai_operator_providers", "ai_operator_api_logs"} and values.get("scope_key") not in {None, f"company:{company}", f"user:{user.id}"}:
            scope_value = str(values.get("scope_key"))
            workspace_id = scope_value.removeprefix("workspace:")
            workspace_model = models.get("pms_workspaces")
            if not (scope_value.startswith("workspace:") and workspace_id.isascii() and workspace_id.isdigit() and len(workspace_id)<=10 and int(workspace_id)<=2147483647 and workspace_model is not None and visible(workspace_model, int(workspace_id))):
                denied("provider_scope_write", model)
        for name, value in values.items():
            if name == "organization_id" or (
                name == "company_id" and tenant_company_column(model)
            ):
                if value is not None and value != company:
                    denied("tenant_write", model)
            column = table.c.get(name)
            if column is None or value is None:
                continue
            if name in ACTOR_FIELDS and value == user.id:
                continue
            if column.primary_key and not column.foreign_keys:
                continue
            if not column.foreign_keys:
                inferred = {
                    "branch_id": "branches",
                    "department_id": "departments",
                    "designation_id": "designations",
                }.get(name)
                if name.endswith("_user_id"):
                    inferred = "users"
                parent = models.get(inferred)
                if parent is not None and criteria.get(parent) is not None:
                    with db.no_autoflush:
                        if (
                            not db.query(parent.id)
                            .filter(parent.id == value, criteria[parent])
                            .first()
                        ):
                            denied("legacy_foreign_key:" + name, model)
            for fk in column.foreign_keys:
                parent = models.get(fk.column.table.name)
                if parent is not None and criteria.get(parent) is not None:
                    with db.no_autoflush:
                        guard = criteria[parent]
                        if parent is User and (
                            name == "reviewer_user_id" or name in ACTOR_FIELDS
                        ):
                            guard = or_(guard, User.__table__.c.is_superuser.is_(True))
                        if (
                            not db.query(fk.column)
                            .filter(fk.column == value, guard)
                            .first()
                        ):
                            denied("foreign_key_write:" + name, model)

    def restrict(execution):
        if not execution.is_orm_statement:
            sql = str(execution.statement).lower()
            if any(
                re.search(r"\b" + re.escape(name) + r"\b", sql)
                for name in protected_names
            ):
                raise HTTPException(403, "Unscoped business SQL is not permitted")
        if execution.is_insert:
            raise HTTPException(403, "Use validated ORM writes for tenant resources")
        if execution.is_update:
            model = execution.bind_mapper.class_ if execution.bind_mapper else None
            if model:
                parameter_sets = (
                    execution.parameters
                    if isinstance(execution.parameters, list)
                    else [execution.parameters or {}]
                )
                for parameters in parameter_sets:
                    values = {
                        key: value
                        for key, value in parameters.items()
                        if key in model.__table__.c
                    }
                    for key, value in (
                        getattr(execution.statement, "_values", None) or {}
                    ).items():
                        key = getattr(key, "key", key)
                        if not hasattr(value, "value") and (
                            key
                            in {
                                "organization_id",
                                "company_id",
                                "role_id",
                                "is_superuser",
                            }
                            or key.endswith("_id")
                        ):
                            denied("bulk_expression", model)
                        values[key] = parameters.get(
                            getattr(value, "key", None), getattr(value, "value", None)
                        )
                    if model.__table__.name in GLOBAL_CATALOGUES:
                        denied("global_catalogue_write", model)
                    if model is User and any(
                        key in values
                        for key in {"role_id", "is_superuser", "is_active"}
                    ):
                        denied("privilege_write", model)
                    if isinstance(execution.parameters, list):
                        keys = inspect(model).primary_key
                        if not all(
                            key.key in parameters for key in keys
                        ) or not visible(
                            model, tuple(parameters[key.key] for key in keys)
                        ):
                            denied("bulk_target", model)
                    validate_fields(model, values)
        if (
            execution.is_delete
            and execution.bind_mapper
            and execution.bind_mapper.local_table.name in GLOBAL_CATALOGUES
        ):
            denied("global_catalogue_delete", execution.bind_mapper.class_)
        if execution.is_select or execution.is_update or execution.is_delete:
            execution.statement = execution.statement.options(*options)
            if (
                execution.is_select
                and not execution.is_relationship_load
                and not execution.is_column_load
            ):
                # Keep legacy .all() endpoints bounded as well as paginated APIs.
                limit = getattr(execution.statement, "_limit_clause", None)
                if limit is None:
                    execution.statement = execution.statement.limit(5000)

    def validate(session, *args):
        for item in session.new | session.dirty | session.deleted:
            model = type(item)
            if model not in criteria:
                continue
            state = inspect(item)
            if model.__table__.name in GLOBAL_CATALOGUES:
                denied("global_catalogue_write", model)
            if item not in session.new and any(
                state.attrs[column.key].history.has_changes()
                for column in state.mapper.primary_key
            ):
                denied("primary_key_write", model)
            if (
                item not in session.new
                and state.identity
                and not visible(model, state.identity)
            ):
                denied("write", model)
            if model is Company and (item in session.new or item.id != company):
                denied("company_write", model)
            if model is User:
                protected = {"is_superuser", "role_id", "is_active"}
                # A scoped employee lifecycle action may toggle only this
                # already-validated employee's login. Role and Super Admin
                # changes retain the global privilege-write guard.
                if (
                    item.id == session.info.get("hr_employee_access_target")
                    and item.id != user.id
                    and not item.is_superuser
                    and getattr(user, "_suite_current_module", None) == "hrms"
                ):
                    from app.core.masking import user_has_permission
                    if user_has_permission(user, "employee_update"):
                        protected.remove("is_active")
                if (item in session.new and item.is_superuser) or (
                    item not in session.new
                    and any(
                        state.attrs[field].history.has_changes() for field in protected
                    )
                ):
                    denied("privilege_write", model)
            if (
                item in session.new
                and "organization_id" in model.__table__.c
                and getattr(item, "organization_id", None) is None
            ):
                item.organization_id = company
            values = {
                column.key: getattr(item, column.key)
                for column in state.mapper.columns
                if column.key not in ACTOR_FIELDS
                or item in session.new
                or state.attrs[column.key].history.has_changes()
            }
            validate_fields(model, values, item in session.new)
            if (
                item in session.new
                and criteria[model] is not None
                and str(criteria[model]) == str(false())
            ):
                denied("unowned_write", model)

    event.listen(db, "do_orm_execute", restrict)
    event.listen(db, "before_flush", validate)
    original_get, original_refresh = db.get, db.refresh

    def scoped_get(model, ident, **kwargs):
        return original_get(model, ident, **kwargs) if visible(model, ident) else None

    def scoped_refresh(item, *args, **kwargs):
        if not visible(type(item), inspect(item).identity):
            denied("refresh", type(item))
        return original_refresh(item, *args, **kwargs)

    original_bulk = {
        name: getattr(db, name)
        for name in (
            "bulk_insert_mappings",
            "bulk_update_mappings",
            "bulk_save_objects",
        )
    }

    def bulk_insert(mapper, mappings, return_defaults=False, **kwargs):
        from app.core.config import settings

        model = getattr(mapper, "class_", mapper)
        rows = list(mappings)
        if len(rows) > settings.SECURITY_MAX_BATCH:
            raise HTTPException(422, "Batch exceeds the configured item limit")
        allowed = set(inspect(model).columns.keys())
        if any(set(row) - allowed for row in rows):
            raise HTTPException(422, "Unsupported bulk field")
        if any(
            any(
                key.primary_key
                and not key.foreign_keys
                and row.get(key.key) is not None
                for key in inspect(model).columns
            )
            for row in rows
        ):
            raise HTTPException(
                422, "Server-generated identifiers cannot be supplied for bulk creation"
            )
        items = [model(**row) for row in rows]
        db.add_all(items)
        db.flush()
        if return_defaults:
            for row, item in zip(rows, items):
                row.update(
                    {
                        key.key: getattr(item, key.key)
                        for key in inspect(model).primary_key
                    }
                )

    def bulk_update(mapper, mappings):
        from app.core.config import settings

        model = getattr(mapper, "class_", mapper)
        rows = list(mappings)
        if len(rows) > settings.SECURITY_MAX_BATCH:
            raise HTTPException(422, "Batch exceeds the configured item limit")
        keys = inspect(model).primary_key
        allowed = set(inspect(model).columns.keys())
        for row in rows:
            if set(row) - allowed or not all(key.key in row for key in keys):
                raise HTTPException(422, "Unsupported bulk field or missing identifier")
            item = scoped_get(model, tuple(row[key.key] for key in keys))
            if item is None:
                denied("bulk_target", model)
            for field, value in row.items():
                if field not in {key.key for key in keys}:
                    setattr(item, field, value)
        db.flush()

    def bulk_save(objects, **kwargs):
        from app.core.config import settings

        items = list(objects)
        if len(items) > settings.SECURITY_MAX_BATCH:
            raise HTTPException(422, "Batch exceeds the configured item limit")
        for item in items:
            identity = inspect(item).identity
            if identity is not None:
                if not visible(type(item), identity):
                    denied("bulk_target", type(item))
                db.merge(item)
            else:
                db.add(item)
        db.flush()

    db.bulk_insert_mappings, db.bulk_update_mappings, db.bulk_save_objects = (
        bulk_insert,
        bulk_update,
        bulk_save,
    )
    db.get, db.refresh = scoped_get, scoped_refresh
    db.info["security_boundary"] = company

    def cleanup():
        db.get, db.refresh = original_get, original_refresh
        for name, function in original_bulk.items():
            setattr(db, name, function)
        db.info.pop("security_boundary", None)
        event.remove(db, "do_orm_execute", restrict)
        event.remove(db, "before_flush", validate)

    return cleanup


@event.listens_for(Session, "before_flush")
def bind_new_account_company(session, *args):
    actor = session.info.get("shared_actor")
    if not actor:
        return
    from app.models.user import User
    from app.common.models import CommonPerson

    for item in list(session.new):
        if isinstance(item, User) and item.person is None:
            session.add(
                CommonPerson(
                    user=item,
                    primary_email=item.email,
                    display_name=item.email,
                    organization_id=actor[1],
                )
            )


def legacy_root(model):
    table = model.__table__
    if (
        table.name in GLOBAL_CATALOGUES | INTERNAL_TABLES
        or "id" not in table.c
        or any(name in table.c for name in ("company_id", "organization_id"))
    ):
        return False
    if table.name in {"companies", "users"}:
        return False
    return not any(
        column.name not in ACTOR_FIELDS
        and any(
            fk.column.table.name not in GLOBAL_CATALOGUES for fk in column.foreign_keys
        )
        for column in table.c
    )


@event.listens_for(Session, "before_flush")
def collect_legacy_ownership(session, *args):
    roots = [
        item
        for item in session.new
        if hasattr(type(item), "__table__") and legacy_root(type(item))
    ]
    if not roots:
        return
    actor = session.info.get("shared_actor")
    company = actor[1] if actor else session.info.get("security_company")
    if company is None:
        # Bootstrap/migration code may infer a tenant only in a single-company DB.
        from app.models.company import Company

        companies = (
            session.connection()
            .execute(select(Company.__table__.c.id).limit(2))
            .scalars()
            .all()
        )
        company = companies[0] if len(companies) == 1 else None
    if company is not None:
        session.info.setdefault("security_new_ownership", []).extend(
            (item, company) for item in roots
        )


@event.listens_for(Session, "after_flush_postexec")
def persist_legacy_ownership(session, *args):
    from app.models.security_boundary import SecurityResourceOwnership

    ownership = SecurityResourceOwnership.__table__
    for item, company in session.info.pop("security_new_ownership", []):
        if getattr(item, "id", None) is not None:
            session.connection().execute(
                ownership.insert().values(
                    resource_table=item.__table__.name,
                    resource_id=item.id,
                    company_id=company,
                )
            )


def claim_single_company_legacy(session):
    """Bootstrap only: no inference is made in a multi-company installation."""
    from app.models.company import Company
    from app.models.security_boundary import SecurityResourceOwnership

    connection = session.connection()
    companies = (
        connection.execute(select(Company.__table__.c.id).limit(2)).scalars().all()
    )
    if len(companies) != 1:
        return
    ownership = SecurityResourceOwnership.__table__
    from sqlalchemy import literal, exists

    for mapper in Base.registry.mappers:
        if legacy_root(mapper.class_):
            table = mapper.local_table
            missing = select(
                literal(table.name), table.c.id, literal(companies[0])
            ).where(
                ~exists(
                    select(ownership.c.resource_id).where(
                        ownership.c.resource_table == table.name,
                        ownership.c.resource_id == table.c.id,
                    )
                )
            )
            connection.execute(
                ownership.insert().from_select(
                    ["resource_table", "resource_id", "company_id"], missing
                )
            )


def tenant_company_column(model):
    column = model.__table__.c.get("company_id")
    if column is None:
        return False
    if column.foreign_keys:
        return any(fk.column.table.name == "companies" for fk in column.foreign_keys)
    return not model.__module__.startswith(("app.apps.crm.", "app.apps.srm."))


@event.listens_for(Session, "after_soft_rollback")
def discard_pending_ownership(session, previous_transaction):
    session.info.pop("security_new_ownership", None)
