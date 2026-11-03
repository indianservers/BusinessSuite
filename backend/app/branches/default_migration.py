"""Explicitly approved default-branch migration; never runs during app startup.

Unknown ownership components go to the approved branch. Components with trusted
existing ownership retain it; conflicting or foreign-company evidence is held
for review. Business amounts, record IDs and non-ownership links are unchanged.
"""
from collections import Counter, defaultdict
import hashlib
import json
from sqlalchemy import select, func, exists, and_, or_, Integer, Numeric, Float
from fastapi import HTTPException
from app.db.base_class import Base
from app.models.company import Company, Branch
from app.branches.models import BranchOwnership, AccountingBranchMap, BranchGrant, BranchPolicy
from app.branches.catalog import SHARED, parents, polymorphic_parents, key_expression, resource_key
from app.branches.migration import backfill
from app.core.tenant_boundary import tenant_company_column


def reconcile_snapshot(connection):
    """Counts and exact monetary/quantity sums, excluding control-plane tables."""
    snapshot = {}
    amount_names = {"amount", "total", "total_amount", "paid_amount", "debit_amount", "credit_amount", "opening_balance_dr", "opening_balance_cr", "current_balance_dr", "current_balance_cr", "quantity", "qty"}
    for mapper in Base.registry.mappers:
        table = mapper.local_table
        if table.name in SHARED:
            continue
        columns = [c for c in table.c if c.name in amount_names and isinstance(c.type, (Numeric, Integer)) and not isinstance(c.type, Float)]
        row = connection.execute(select(func.count(), *(func.coalesce(func.sum(c), 0) for c in columns)).select_from(table)).one()
        identity_columns = list(table.primary_key.columns)
        identity_columns += [c for c in table.c if c.foreign_keys and not c.primary_key and c.name not in {"branch_id", "organization_id"} and not (c.name == "company_id" and tenant_company_column(mapper.class_))]
        digest = hashlib.sha256()
        for identity in connection.execute(select(*identity_columns).order_by(*table.primary_key)):
            digest.update(json.dumps(list(identity), default=str, separators=(",", ":")).encode())
            digest.update(b"\n")
        snapshot[table.name] = {"rows": row[0], "totals": {c.name: str(value) for c, value in zip(columns, row[1:])}, "identity_and_links_digest": digest.hexdigest()}
    return snapshot


def assign_default(connection, company, branch, *, actor):
    if not actor.is_active or not actor.is_superuser:
        raise HTTPException(403, "Super Admin approval is required for default-branch migration")
    if not connection.execute(select(Branch.id).where(Branch.id == branch, Branch.company_id == company, Branch.is_active.is_(True))).first():
        raise HTTPException(422, "Choose an active branch in this company")
    company_ids = set(connection.execute(select(Company.id)).scalars())
    sole_company = company_ids == {company}
    models = {m.local_table.name: m.class_ for m in Base.registry.mappers}
    tables = Base.metadata.tables
    owner = BranchOwnership.__table__
    valid_branches = set(connection.execute(select(Branch.id).where(Branch.company_id == company)).scalars())
    mappings = dict(connection.execute(select(AccountingBranchMap.accounting_branch_id, AccountingBranchMap.branch_id).where(AccountingBranchMap.company_id == company)).all())
    mapping_count = 0
    fam = tables.get("fam_branches")
    if fam is not None:
        for ident in connection.execute(select(fam.c.id).where(fam.c.company_id == company)).scalars():
            if ident not in mappings:
                prior = connection.execute(select(owner.c.branch_id).where(owner.c.company_id == company, owner.c.resource_table == "fam_branches", owner.c.resource_key == str(ident))).scalar()
                chosen = prior or branch
                connection.execute(AccountingBranchMap.__table__.insert().values(accounting_branch_id=ident, company_id=company, branch_id=chosen))
                mappings[ident] = chosen
                mapping_count += 1
    inferred = backfill(connection, company)
    existing = {(r.resource_table, r.resource_key): (r.company_id, r.branch_id) for r in connection.execute(select(owner))}
    nodes = {}
    foreign_rows = Counter()

    def marker(model, row):
        columns = model.__table__.c
        values = []
        if "organization_id" in columns: values.append(row["organization_id"])
        if tenant_company_column(model): values.append(row["company_id"])
        return values

    for name, model in models.items():
        if name in SHARED:
            continue
        table = model.__table__
        missing = ~exists(select(1).where(owner.c.resource_table == name, owner.c.resource_key == key_expression(table)))
        for row in connection.execute(select(table).where(missing)).mappings():
            if name == "fam_ledgers" and row["system_ledger"]:
                continue  # Company-shared account definitions have no branch owner.
            values = marker(model, row)
            if any(v is not None and v != company for v in values):
                foreign_rows[name] += 1
                continue
            if not sole_company and (not values or all(v is None for v in values)):
                foreign_rows[name] += 1
                continue  # A default branch must never imply a default company.
            node = name, resource_key(table, row)
            nodes[node] = dict(row)
    roots = {node: node for node in nodes}
    evidence = defaultdict(set)
    issues = defaultdict(set)
    cache = {}

    def root(node):
        while roots[node] != node:
            roots[node] = roots[roots[node]]
            node = roots[node]
        return node

    def union(a, b):
        a, b = root(a), root(b)
        if a != b: roots[b] = a

    def link(node, parent, key, value):
        lookup = parent.name, key.name, str(value)
        if lookup not in cache:
            cache[lookup] = connection.execute(select(parent).where(key == value)).mappings().first()
        row = cache[lookup]
        if row is None:
            issues[node].add("missing-parent")
            return
        if parent.name == "fam_ledgers" and row["system_ledger"]:
            return
        parent_model = models.get(parent.name)
        if parent_model and any(v is not None and v != company for v in marker(parent_model, row)):
            issues[node].add("foreign-company-parent")
            return
        parent_node = parent.name, resource_key(parent, row)
        if parent_node in nodes:
            union(node, parent_node)
        elif parent_node in existing:
            source_company, source_branch = existing[parent_node]
            if source_company != company:
                issues[node].add("foreign-company-parent")
            else:
                evidence[node].add(source_branch)
        else:
            issues[node].add("unresolved-parent")

    for node, row in nodes.items():
        table = models[node[0]].__table__
        if "branch_id" in table.c and row.get("branch_id") is not None:
            accounting = any(fk.column.table.name == "fam_branches" for fk in table.c.branch_id.foreign_keys)
            direct = mappings.get(row["branch_id"]) if accounting else row["branch_id"]
            if direct in valid_branches: evidence[node].add(direct)
            else: issues[node].add("invalid-branch")
        for column, parent, key in parents(table, tables):
            # Historical transactions retain their migration-approved branch;
            # an employee's current placement is not historical evidence.
            if parent.name == "employees" or row.get(column.name) is None:
                continue
            link(node, parent, key, row[column.name])
        for parent, value in polymorphic_parents(table, row, tables):
            link(node, parent, parent.c.id, value)
    components = defaultdict(list)
    known = defaultdict(set)
    problems = defaultdict(set)
    for node in nodes:
        group = root(node)
        components[group].append(node)
        known[group].update(evidence[node])
        problems[group].update(issues[node])
    assigned = Counter()
    held = Counter()
    reasons = Counter()
    for group, members in components.items():
        choices = known[group]
        if len(choices) > 1: problems[group].add("conflicting-branches")
        if problems[group]:
            for node in members: held[node[0]] += 1
            reasons.update(problems[group])
            continue
        chosen = next(iter(choices), branch)
        for node in members:
            table = models[node[0]].__table__
            row = nodes[node]
            updates = {}
            if "branch_id" in table.c and row.get("branch_id") is None and not any(fk.column.table.name == "fam_branches" for fk in table.c.branch_id.foreign_keys):
                updates["branch_id"] = chosen
            # Ownership is recorded separately. Rewriting nullable company
            # columns can merge distinct historical/global configuration rows
            # into an existing company-unique setting. The company boundary
            # recognizes an explicit approved owner for these null markers.
            if updates:
                # Structural migration must not reset business activity dates.
                updates.update({c.name: row[c.name] for c in table.c if c.onupdate is not None})
                connection.execute(table.update().where(*(c == row[c.name] for c in table.primary_key)).values(**updates))
            connection.execute(owner.insert().values(resource_table=node[0], resource_key=node[1], company_id=company, branch_id=chosen, source="approved-default-main" if chosen == branch else "verified-component"))
            assigned[node[0]] += 1
    # Preserve effective branch/module permissions. Only verified company users
    # without an existing branch assignment or explicit policy receive Main.
    from app.models.user import User
    from app.models.employee import Employee
    from app.common.models import CommonPerson
    from app.access.models import AccessMembership
    users = User.__table__
    people, memberships, employees = CommonPerson.__table__, AccessMembership.__table__, Employee.__table__
    member_ids = select(people.c.user_id).where(people.c.organization_id == company).union(select(memberships.c.user_id).where(memberships.c.company_id == company, memberships.c.active.is_(True)))
    granted = 0
    for ident in connection.execute(select(users.c.id).where(users.c.id.in_(member_ids), users.c.is_active.is_(True), users.c.is_superuser.is_(False))).scalars():
        has_policy = connection.execute(select(BranchPolicy.id).where(BranchPolicy.company_id == company, BranchPolicy.user_id == ident)).first()
        has_grant = connection.execute(select(BranchGrant.id).where(BranchGrant.company_id == company, BranchGrant.user_id == ident)).first()
        home = connection.execute(select(employees.c.branch_id).where(employees.c.user_id == ident, employees.c.branch_id.is_not(None))).first()
        if not has_policy and not has_grant and not home:
            connection.execute(BranchGrant.__table__.insert().values(company_id=company, user_id=ident, branch_id=branch, can_write=True))
            granted += 1
    return {"company_id": company, "default_branch_id": branch, "inferred": inferred, "assigned": dict(assigned), "assigned_total": sum(assigned.values()), "held": dict(held), "held_total": sum(held.values()), "hold_reasons": dict(reasons), "foreign_or_ambiguous_company_rows": dict(foreign_rows), "accounting_mappings": mapping_count, "main_only_user_grants": granted}
