from dataclasses import dataclass
from fastapi import HTTPException
from sqlalchemy import select, inspect
from app.branches.models import BranchPolicy, BranchGrant, BranchAudit, BranchLifecycle
from app.models.company import Branch, Company
from app.models.employee import Employee


@dataclass(frozen=True)
class BranchContext:
    company_id: int
    branch_id: int | None
    allowed: frozenset[int]
    writable: frozenset[int]
    all_branches: bool
    manage_access: bool
    superuser: bool


def access(db, user, company):
    """Resolve freshly on every request. All DB reads here are control-plane reads."""
    connection = db.connection()
    if not inspect(connection).has_table(BranchPolicy.__tablename__) or not inspect(connection).has_table(BranchLifecycle.__tablename__):
        raise HTTPException(503, "Apply the branch-access and recovery migrations before using the suite")
    if not connection.execute(select(Company.id).where(Company.id == company, Company.is_active.is_(True))).first():
        raise HTTPException(403, "Company is unavailable")
    branch_rows = connection.execute(select(Branch.id, Branch.is_active).where(Branch.company_id == company, ~Branch.id.in_(select(BranchLifecycle.branch_id).where(BranchLifecycle.deleted_at.is_not(None))))).all()
    active_branches = {r.id for r in branch_rows if r.is_active}
    available = {r.id for r in branch_rows}
    policy = connection.execute(select(BranchPolicy.__table__).where(BranchPolicy.user_id == user.id, BranchPolicy.company_id == company)).mappings().first()
    all_access = bool(user.is_superuser or policy and policy["all_branches"])
    manager = bool(user.is_superuser or policy and policy["manage_access"])
    grants = connection.execute(select(BranchGrant.branch_id, BranchGrant.can_write).where(BranchGrant.user_id == user.id, BranchGrant.company_id == company)).all()
    allowed = available if all_access else {r.branch_id for r in grants} & active_branches
    writable = active_branches.copy() if all_access else {r.branch_id for r in grants if r.can_write} & active_branches
    if not policy or policy["use_home_branch"]:
        home = connection.execute(select(Employee.branch_id).join(Branch, Branch.id == Employee.branch_id).where(Employee.user_id == user.id, Branch.company_id == company, Employee.deleted_at.is_(None))).scalars().first()
        if home in active_branches:
            allowed.add(home)
            writable.add(home)
    return allowed, writable, all_access, manager


def context(db, user, company, selected=None):
    from app.core.tenant_boundary import company_ids
    if not user.is_superuser and company not in company_ids(db, user):
        raise HTTPException(403, "Verified company membership is required")
    allowed, writable, all_access, manager = access(db, user, company)
    if selected == "all":
        if not all_access:
            raise HTTPException(403, "All-branches access is required")
        branch_id = None
    elif selected is not None:
        if not str(selected).isascii() or not str(selected).isdigit() or len(str(selected)) > 10:
            raise HTTPException(403, "Invalid branch context")
        branch_id = int(selected)
        if branch_id not in allowed:
            raise HTTPException(403, "Branch access is unavailable or revoked")
    else:
        home = db.connection().execute(select(Employee.branch_id).where(Employee.user_id == user.id, Employee.branch_id.in_(allowed), Employee.deleted_at.is_(None))).scalar()
        branch_id = None if all_access else home if home in allowed else min(allowed) if allowed else None
    return BranchContext(company, branch_id, frozenset(allowed), frozenset(writable), all_access, manager, bool(user.is_superuser))


def audit(db, user, company, operation, reason, details):
    db.connection().execute(BranchAudit.__table__.insert().values(company_id=company, actor_id=user.id, operation=operation, reason=reason, details=details))


def assert_manager(db, user):
    _, _, _, manager = access(db, user, user.organization_id)
    if not manager:
        raise HTTPException(403, "Branch access administration is required")
