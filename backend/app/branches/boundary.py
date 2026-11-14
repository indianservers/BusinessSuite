"""Branch ownership applies in addition to company, module and workspace guards.

Private legacy rows use an indexed ownership register. New writes are stamped in
the same transaction; unknown historical ownership is never publicly visible.
Core/raw SQL via Session is rejected for private tables, including bulk writes.
"""
import re
from functools import lru_cache
from threading import RLock
from types import MappingProxyType
import logging
from fastapi import HTTPException
from sqlalchemy import and_, or_, event, exists, select, inspect, delete, literal
from sqlalchemy.orm import with_loader_criteria
from app.db.base_class import Base
from app.branches.models import BranchOwnership, AccountingBranchMap, BranchRecordShare
from app.branches.catalog import SHARED, parents, polymorphic_parents, key_expression, resource_key


def deny(message="Record is outside the selected branch or writable scope"):
    raise HTTPException(403, message)


def branch_for_row(connection, table, values, company, tables, target_branch=None, historical=False, owner_cache=None):
    """Trusted direct ownership and parent evidence; actors never decide it."""
    branches = set()
    if table.name == "branches":
        if values.get("company_id") != company:
            deny()
        return {values["id"]}
    if table.name == "fam_branches":
        accounting_id = values.get("id")
    elif "branch_id" in table.c and values.get("branch_id") is not None:
        column = table.c.branch_id
        accounting_id = values["branch_id"] if any(fk.column.table.name == "fam_branches" for fk in column.foreign_keys) else None
        if accounting_id is None:
            branches.add(values["branch_id"])
    else:
        accounting_id = None
    if accounting_id is not None:
        mapping = AccountingBranchMap.__table__
        mapped = connection.execute(select(mapping.c.branch_id).where(mapping.c.accounting_branch_id == accounting_id, mapping.c.company_id == company)).scalar()
        if mapped is None:
            deny("Accounting branch has no verified suite-branch mapping")
        branches.add(mapped)
    ownership = BranchOwnership.__table__
    for column, parent, key in parents(table, tables):
        value = values.get(column.name)
        if value is None:
            continue
        if historical and parent.name == "employees":
            # A present-day employment assignment cannot establish the branch
            # of old payroll, attendance, expenses, or other historical rows.
            continue
        if parent.name == "fam_ledgers" and connection.execute(select(parent.c.id).where(key == value, parent.c.company_id == company, parent.c.system_ledger.is_(True))).first():
            continue
        cache_key = (parent.name, key.name, value, company)
        if owner_cache is not None and cache_key in owner_cache:
            found = owner_cache[cache_key]
        else:
            found = connection.execute(select(ownership.c.branch_id).select_from(parent.join(ownership, and_(ownership.c.resource_table == parent.name, ownership.c.resource_key == key_expression(parent), ownership.c.company_id == company))).where(key == value)).scalar()
            if owner_cache is not None:
                owner_cache[cache_key] = found
        if found is not None:
            if target_branch is not None and parent.name in {"crm_companies", "crm_contacts"}:
                shares = BranchRecordShare.__table__
                shared = connection.execute(select(shares.c.branch_id).select_from(parent.join(shares, and_(shares.c.resource_table == parent.name, shares.c.resource_key == key_expression(parent), shares.c.company_id == company, shares.c.branch_id == target_branch))).where(key == value)).first()
                if shared:
                    found = target_branch
            branches.add(found)
        else:
            # A populated private parent cannot be ignored and replaced with the
            # user's current branch. Its migration must resolve first.
            deny(f"Parent ownership is unresolved: {table.name}.{column.name}")
    for parent, key in polymorphic_parents(table, values, tables):
        cache_key = (parent.name, "polymorphic", key, company)
        if owner_cache is not None and cache_key in owner_cache:
            found = owner_cache[cache_key]
        else:
            found = connection.execute(select(ownership.c.branch_id).where(ownership.c.resource_table == parent.name, ownership.c.resource_key == key, ownership.c.company_id == company)).scalar()
            if owner_cache is not None:
                owner_cache[cache_key] = found
        if found is None:
            deny("Linked record ownership is unresolved or outside this company")
        branches.add(found)
    return branches


# Only immutable SQL structure is reused. Every request still resolves current
# company/branch rights, and the predicates read live ownership rows at execution.
# Serialize initial construction to avoid rebuilding the same graph on fan-out.
_read_guard_lock = RLock()


@lru_cache(maxsize=32)
def _read_guards(model_items, actor_id, company_id, branch_id, selected, superuser, identity_administration):
    models = dict(model_items)
    ownership = BranchOwnership.__table__
    criteria = {}
    for name, model in models.items():
        if superuser and branch_id is None:
            continue
        if identity_administration and name in {"users", "common_people", "common_profiles"}:
            continue
        if name in {"users", "common_people", "common_profiles"} and not (superuser and branch_id is None):
            from app.models.employee import Employee
            from app.branches.models import BranchGrant, BranchPolicy
            branch_users = select(Employee.__table__.c.user_id).where(Employee.__table__.c.branch_id.in_(selected), Employee.__table__.c.deleted_at.is_(None)).union(
                select(BranchGrant.__table__.c.user_id).where(BranchGrant.__table__.c.company_id == company_id, BranchGrant.__table__.c.branch_id.in_(selected)),
                select(BranchPolicy.__table__.c.user_id).where(BranchPolicy.__table__.c.company_id == company_id, BranchPolicy.__table__.c.all_branches.is_(True), literal(bool(selected))),
            )
            if name == "common_profiles":
                from app.common.models import CommonPerson
                person = CommonPerson.__table__
                employee = Employee.__table__
                # Cross-branch application membership exposes a usable identity,
                # not the private HR/onboarding profile from its home branch.
                no_employee = ~exists(select(1).where(employee.c.user_id == person.c.user_id, employee.c.deleted_at.is_(None))).correlate(person)
                home_visible = person.c.user_id.in_(select(employee.c.user_id).where(employee.c.branch_id.in_(selected), employee.c.deleted_at.is_(None)))
                criteria[model] = model.__table__.c.person_id.in_(select(person.c.id).where(or_(person.c.user_id == actor_id, and_(person.c.user_id.in_(branch_users), or_(no_employee, home_visible)))))
            else:
                field = model.__table__.c.id if name == "users" else model.__table__.c.user_id
                criteria[model] = or_(field == actor_id, field.in_(branch_users))
            continue
        if name in SHARED:
            continue
        table = model.__table__
        guard = exists(select(1).where(ownership.c.resource_table == name, ownership.c.resource_key == key_expression(table), ownership.c.company_id == company_id, ownership.c.branch_id.in_(selected))).correlate(table)
        if name in {"crm_companies", "crm_contacts"}:
            shares = BranchRecordShare.__table__
            guard = or_(guard, exists(select(1).where(shares.c.company_id == company_id, shares.c.resource_table == name, shares.c.resource_key == key_expression(table), shares.c.branch_id.in_(selected))).correlate(table))
        if name == "fam_ledgers":
            # Only system account definitions are company-shared. Customer and
            # bank ledgers remain private. Their amounts are derived from scoped
            # entries by the accounting response layer.
            guard = or_(guard, and_(table.c.company_id == company_id, table.c.system_ledger.is_(True)))
        criteria[model] = guard
    options = [with_loader_criteria(model, guard, include_aliases=True, propagate_to_loaders=False) for model, guard in criteria.items()]
    return MappingProxyType(criteria), tuple(options)


def install(db, user, ctx, *, identity_administration=False):
    if db.info.get("branch_context") is not None:
        if db.info["branch_context"] != ctx:
            deny("Branch context cannot change inside a transaction")
        return lambda: None
    models = {m.local_table.name: m.class_ for m in Base.registry.mappers}
    tables = Base.metadata.tables
    ownership = BranchOwnership.__table__
    selected = {ctx.branch_id} if ctx.branch_id else set(ctx.allowed)
    with _read_guard_lock:
        criteria, options = _read_guards(tuple(sorted(models.items())), user.id, ctx.company_id,
            ctx.branch_id, tuple(sorted(selected)), ctx.superuser, identity_administration)
    protected = set(models) - SHARED
    pattern = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in protected) + r")\b", re.I)
    pending = []
    original_get = db.get
    original_refresh = db.refresh
    original_bulk = {name: getattr(db, name) for name in ("bulk_insert_mappings", "bulk_update_mappings", "bulk_save_objects")}

    def visible(model, identity):
        if model not in criteria:
            return True
        keys = inspect(model).primary_key
        values = list(identity) if isinstance(identity, (list, tuple)) else [identity]
        if isinstance(identity, dict):
            values = [identity.get(k.key) for k in keys]
        with db.no_autoflush:
            return db.connection().execute(select(*keys).where(criteria[model], *(k == v for k, v in zip(keys, values)))).first() is not None

    def restrict(execution):
        if not execution.is_orm_statement:
            if pattern.search(str(execution.statement)):
                deny("Unscoped business SQL is not permitted in a branch session")
            return
        if execution.is_insert or execution.is_update or execution.is_delete:
            write_table = execution.bind_mapper.local_table if execution.bind_mapper else None
            if write_table is not None and ctx.branch_id is not None and ctx.branch_id not in ctx.writable and write_table.name not in {"users", "user_sessions", "mfa_methods", "trusted_devices", "login_attempts"} and not write_table.name.startswith(("suite_access_", "suite_branch_", "security_")):
                deny("The selected branch is read-only")
            # ORM unit-of-work writes run through flush; SQL bulk writes do not.
            if execution.bind_mapper and execution.bind_mapper.local_table.name not in SHARED:
                if execution.is_update:
                    table = execution.bind_mapper.local_table
                    for column in (getattr(execution.statement, "_values", None) or {}):
                        name = getattr(column, "key", column)
                        if name in {"organization_id", "company_id", "branch_id", "entity_type", "entity", "related_type", "related_entity_type", "scope_key"} or str(name).endswith("_id") or name in {key.name for key in table.primary_key} or name in table.c and table.c[name].foreign_keys:
                            deny("Relationship and ownership changes require validated record writes")
                    if execution.parameters:
                        deny("Use validated record writes for parameterized bulk updates")
                    if ctx.branch_id is not None and ctx.branch_id not in ctx.writable:
                        deny("The selected branch is read-only")
                    write_guard = exists(select(1).where(ownership.c.resource_table == table.name, ownership.c.resource_key == key_expression(table), ownership.c.company_id == ctx.company_id, ownership.c.branch_id.in_(ctx.writable))).correlate(table)
                    execution.statement = execution.statement.options(with_loader_criteria(execution.bind_mapper.class_, write_guard, include_aliases=True, propagate_to_loaders=False))
                else:
                    deny("Use validated record writes for branch-owned resources")
        if execution.is_select or execution.is_update:
            # Branch guards are dynamic even when a superuser has no separate
            # tenant listener. Avoid building cache keys for the full guard graph.
            execution.update_execution_options(compiled_cache=None)
            # Keep one copy of each current-context guard on relationship loads.
            inherited = {id(option) for option in getattr(execution.statement, '_with_options', ())}
            execution.statement = execution.statement.options(*(option for option in options if id(option) not in inherited))

    def validate(session, *args):
        for item in session.new | session.dirty | session.deleted:
            table = inspect(item).mapper.local_table
            # Own-account password changes are identity operations. Their trusted
            # security notification must not require business-branch membership.
            # No business email, other recipient or existing row is exempted.
            if (table.name == "email_outbox" and item in session.new
                    and session.info.get("account_security_change") == user.id
                    and item.module == "security" and item.recipient_user_id == user.id
                    and item.recipient.casefold() == user.email.casefold()
                    and item.organization_id in {None, ctx.company_id}):
                continue
            if table.name in SHARED:
                if ctx.branch_id is not None and ctx.branch_id not in ctx.writable and table.name not in {"users", "user_sessions", "mfa_methods", "trusted_devices", "login_attempts"} and not table.name.startswith(("suite_access_", "suite_branch_", "security_")):
                    deny("The selected branch is read-only")
                continue
            state = inspect(item)
            from app.core.tenant_boundary import tenant_company_column
            tenant_fields = (["organization_id"] if "organization_id" in table.c else []) + (["company_id"] if tenant_company_column(type(item)) else [])
            for name in tenant_fields:
                value = getattr(item, name)
                if value is None and item in session.new:
                    setattr(item, name, ctx.company_id)
                elif value is not None and value != ctx.company_id:
                    deny("Record belongs to another company")
            if table.name == "fam_ledgers" and item.system_ledger:
                changes = {c.name for c in table.c if state.attrs[c.name].history.has_changes()}
                materialized = {"current_balance_dr", "current_balance_cr", "updated_at"}
                if item.id in session.info.get("fam_opening_post_targets", set()):
                    materialized |= {"opening_balance_dr", "opening_balance_cr"}
                if item in session.new or item not in session.deleted and changes <= materialized:
                    continue
            if item not in session.new:
                if not visible(type(item), state.identity):
                    deny()
                for key in table.primary_key:
                    if state.attrs[key.key].history.has_changes():
                        deny("Record identifiers cannot change")
                stamp = session.connection().execute(select(ownership.c.branch_id).where(ownership.c.resource_table == table.name, ownership.c.resource_key == resource_key(table, {c.name: getattr(item, c.name) for c in table.primary_key}), ownership.c.company_id == ctx.company_id)).scalar()
                if stamp is None or stamp not in ctx.writable or ctx.branch_id and stamp != ctx.branch_id:
                    deny()
            elif ctx.branch_id is None:
                # Admin control-plane creation has its own guarded API. Business
                # transactions always require a destination branch.
                logging.getLogger("businesssuite.security").warning("branch_write_requires_destination table=%s", table.name)
                deny("Select a destination branch before creating business records")
            elif ctx.branch_id not in ctx.writable:
                deny("The selected branch is read-only")
            if "branch_id" in table.c and item in session.new and getattr(item, "branch_id") is None:
                if not any(fk.column.table.name == "fam_branches" for fk in table.c.branch_id.foreign_keys):
                    item.branch_id = ctx.branch_id
            if "branch_id" in table.c and item not in session.new and state.attrs.branch_id.history.has_changes():
                deny("Use an authorized branch transfer to change ownership")
            if item in session.deleted:
                session.connection().execute(delete(ownership).where(ownership.c.resource_table == table.name, ownership.c.resource_key == resource_key(table, {c.name: getattr(item, c.name) for c in table.primary_key})))
            else:
                pending.append(item)

    def stamp(session, *args):
        # Flush assigned generated IDs and relationship FKs. Resolve new parents
        # before children, regardless of the ordering in session.new.
        queue = list(dict.fromkeys(pending))
        pending.clear()
        connection = session.connection()
        while queue:
            unresolved = []
            progress = False
            last_error = None
            for item in queue:
                table = inspect(item).mapper.local_table
                values = {c.name: getattr(item, c.name) for c in table.c}
                key = resource_key(table, values)
                current = connection.execute(select(ownership.c.branch_id).where(ownership.c.resource_table == table.name, ownership.c.resource_key == key, ownership.c.company_id == ctx.company_id)).scalar()
                try:
                    evidence = branch_for_row(connection, table, values, ctx.company_id, tables, ctx.branch_id or current, historical=current is not None)
                except HTTPException as error:
                    last_error = error
                    unresolved.append(item)
                    continue
                if len(evidence) > 1:
                    deny("Cross-branch record links require an explicit supported workflow")
                branch = next(iter(evidence), ctx.branch_id or current)
                if branch is None or branch not in ctx.writable or ctx.branch_id and branch != ctx.branch_id:
                    deny()
                if current is not None and current != branch:
                    deny("Record ownership cannot change through an ordinary update")
                if current is None:
                    connection.execute(ownership.insert().values(resource_table=table.name, resource_key=key, company_id=ctx.company_id, branch_id=branch, source="validated-write"))
                progress = True
            if unresolved and not progress:
                raise last_error
            queue = unresolved

    def scoped_get(model, identity, **kwargs):
        return original_get(model, identity, **kwargs) if visible(model, identity) else None

    def scoped_refresh(item, *args, **kwargs):
        if not visible(type(item), inspect(item).identity):
            deny()
        return original_refresh(item, *args, **kwargs)

    def discard_pending(*args):
        pending.clear()

    def bulk_insert(mapper, mappings, **kwargs):
        model = getattr(mapper, "class_", mapper)
        from app.core.config import settings
        rows = list(mappings)
        if len(rows) > settings.SECURITY_MAX_BATCH:
            raise HTTPException(422, "Batch exceeds the configured item limit")
        items = [model(**values) for values in rows]
        db.add_all(items)
        db.flush()

    def bulk_update(mapper, mappings, **kwargs):
        model = getattr(mapper, "class_", mapper)
        keys = inspect(model).primary_key
        for values in mappings:
            item = scoped_get(model, tuple(values.get(k.key) for k in keys))
            if item is None:
                deny()
            for key, value in values.items():
                if key not in {k.key for k in keys}:
                    setattr(item, key, value)
        db.flush()

    def bulk_save(objects, **kwargs):
        for item in objects:
            db.merge(item) if inspect(item).identity else db.add(item)
        db.flush()

    db.info["branch_context"] = ctx
    db.get, db.refresh = scoped_get, scoped_refresh
    db.bulk_insert_mappings, db.bulk_update_mappings, db.bulk_save_objects = bulk_insert, bulk_update, bulk_save
    event.listen(db, "do_orm_execute", restrict)
    event.listen(db, "before_flush", validate)
    event.listen(db, "after_flush_postexec", stamp)
    event.listen(db, "after_soft_rollback", discard_pending)

    def cleanup():
        db.get, db.refresh = original_get, original_refresh
        for name, method in original_bulk.items():
            setattr(db, name, method)
        for name, callback in (("do_orm_execute", restrict), ("before_flush", validate), ("after_flush_postexec", stamp), ("after_soft_rollback", discard_pending)):
            event.remove(db, name, callback)
        db.info.pop("branch_context", None)
    return cleanup
