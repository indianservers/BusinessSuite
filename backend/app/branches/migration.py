"""Deterministic, repeatable backfill from existing branch/parent evidence only."""
from collections import Counter
from fastapi import HTTPException
from sqlalchemy import select, exists, and_
from app.db.base_class import Base
from app.branches.catalog import SHARED, key_expression, resource_key
from app.branches.models import BranchOwnership
from app.branches.boundary import branch_for_row
from app.core.tenant_boundary import tenant_company_column


def backfill(connection, company, max_passes=20):
    models = {m.local_table.name: m.class_ for m in Base.registry.mappers}
    owner = BranchOwnership.__table__
    report = Counter()
    for _ in range(max_passes):
        changed = 0
        for name, model in sorted(models.items(), key=lambda entry: (entry[0] != "branches", entry[0])):
            if name in SHARED:
                continue
            table = model.__table__
            if name in {"branches", "fam_branches"}:
                company_guard = table.c.company_id == company
            elif "organization_id" in table.c:
                company_guard = table.c.organization_id == company
            elif tenant_company_column(model) or name in {"branches", "fam_branches"}:
                company_guard = table.c.company_id == company
            else:
                # Child ownership is verified by its already-owned parents.
                company_guard = True
            query = select(table).where(company_guard, ~exists(select(1).where(owner.c.resource_table == name, owner.c.resource_key == key_expression(table))))
            for row in connection.execute(query).mappings():
                try:
                    branches = branch_for_row(connection, table, row, company, Base.metadata.tables, historical=True)
                except HTTPException:
                    continue
                if len(branches) != 1:
                    continue
                branch = next(iter(branches))
                from app.models.company import Branch
                if not connection.execute(select(Branch.id).where(Branch.id == branch, Branch.company_id == company)).first():
                    continue
                connection.execute(owner.insert().values(resource_table=name, resource_key=resource_key(table, row), company_id=company, branch_id=branch, source="verified-backfill"))
                changed += 1
                report[name] += 1
        if not changed:
            break
    return dict(report)
