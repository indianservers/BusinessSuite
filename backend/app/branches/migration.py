"""Deterministic, repeatable backfill from existing branch/parent evidence only."""
from collections import Counter
from fastapi import HTTPException
from sqlalchemy import select, exists, and_, or_
from app.db.base_class import Base
from app.branches.catalog import SHARED, key_expression, resource_key
from app.branches.models import BranchOwnership
from app.branches.boundary import branch_for_row
from app.core.tenant_boundary import tenant_company_column


def backfill(connection, company, max_passes=20, *, table_names=None):
    models = {m.local_table.name: m.class_ for m in Base.registry.mappers}
    if table_names is not None:
        models = {name: model for name, model in models.items() if name in table_names}
    owner = BranchOwnership.__table__
    from app.models.company import Branch
    local_branches = set(connection.execute(select(Branch.id).where(Branch.company_id == company)).scalars())
    report = Counter()
    for _ in range(max_passes):
        changed = 0
        # Historical evidence is stable within a pass; rebuild after inserting
        # parents so previously unresolved children can resolve next pass.
        owner_cache = {}
        for name, model in sorted(models.items(), key=lambda entry: (entry[0] != "branches", entry[0])):
            if name in SHARED:
                continue
            table = model.__table__
            if name in {"branches", "fam_branches"}:
                company_guard = table.c.company_id == company
            else:
                # Older rows can lack a company stamp while still carrying a
                # verified branch/parent. NULL is not foreign-company evidence;
                # branch_for_row must still prove exactly one local branch.
                guards = []
                if "organization_id" in table.c:
                    guards.append(or_(table.c.organization_id == company, table.c.organization_id.is_(None)))
                if tenant_company_column(model):
                    guards.append(or_(table.c.company_id == company, table.c.company_id.is_(None)))
                company_guard = and_(*guards) if guards else True
            query = select(table).where(company_guard, ~exists(select(1).where(owner.c.resource_table == name, owner.c.resource_key == key_expression(table))))
            assignments = []
            for row in connection.execute(query).mappings():
                try:
                    branches = branch_for_row(connection, table, row, company, Base.metadata.tables, historical=True, owner_cache=owner_cache)
                except HTTPException:
                    continue
                if len(branches) != 1:
                    continue
                branch = next(iter(branches))
                if branch not in local_branches:
                    continue
                assignments.append(dict(resource_table=name, resource_key=resource_key(table, row), company_id=company, branch_id=branch, source="verified-backfill"))
                changed += 1
                report[name] += 1
            if assignments:
                connection.execute(owner.insert(), assignments)
        if not changed:
            break
    return dict(report)
