from sqlalchemy import inspect, select
from app.branches.models import BranchOwnership
from app.branches.catalog import resource_key
from app.models.company import Branch


def record_branch_name(record):
    state = inspect(record)
    db = state.session
    if db is None:
        return None
    table = state.mapper.local_table
    company = getattr(record, "organization_id", None)
    ctx = db.info.get("branch_context")
    if company is None and ctx:
        company = ctx.company_id
    if company is None:
        return None
    key = resource_key(table, {c.name: getattr(record, c.name) for c in table.primary_key})
    branch = db.connection().execute(select(BranchOwnership.branch_id).where(BranchOwnership.resource_table == table.name, BranchOwnership.resource_key == key, BranchOwnership.company_id == company)).scalar()
    if branch is None:
        branch = getattr(record, "branch_id", None)
    if branch is None:
        return None
    cache = db.info.setdefault("branch_display_names", {})
    if (company, branch) not in cache:
        cache[company, branch] = db.connection().execute(select(Branch.name).where(Branch.id == branch, Branch.company_id == company)).scalar()
    return cache[company, branch]
