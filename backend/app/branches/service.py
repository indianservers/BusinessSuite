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


def company_administrator(db, user, company):
    from app.access.models import AccessMembership
    connection = db.connection()
    if not inspect(connection).has_table(AccessMembership.__tablename__):
        return False
    return bool(connection.execute(select(AccessMembership.id).where(
        AccessMembership.user_id == user.id, AccessMembership.company_id == company,
        AccessMembership.active.is_(True), AccessMembership.is_admin.is_(True),
    )).first())


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
    administrator = user.is_superuser or company_administrator(db, user, company)
    all_access = bool(administrator or policy and policy["all_branches"])
    manager = bool(administrator or policy and policy["manage_access"])
    grants = connection.execute(select(BranchGrant.branch_id, BranchGrant.can_write).where(BranchGrant.user_id == user.id, BranchGrant.company_id == company)).all()
    allowed = available if all_access else {r.branch_id for r in grants} & active_branches
    writable = active_branches.copy() if all_access else {r.branch_id for r in grants if r.can_write} & active_branches
    if not policy or policy["use_home_branch"]:
        home = connection.execute(select(Employee.branch_id).join(Branch, Branch.id == Employee.branch_id).where(Employee.user_id == user.id, Branch.company_id == company, Employee.deleted_at.is_(None))).scalars().first()
        if home in active_branches:
            allowed.add(home)
            if home not in {r.branch_id for r in grants}:
                writable.add(home)
    return allowed, writable, all_access, manager


def context(db, user, company, selected=None):
    from app.core.tenant_boundary import company_ids
    if not user.is_superuser and company not in company_ids(db, user):
        raise HTTPException(403, "Verified company membership is required")
    allowed, writable, all_access, manager = access(db, user, company)
    # Older clients can retain the retired "all" selection in session storage.
    # Resolve writes before authorization too, so module roles and ownership use
    # the same concrete branch. Explicit all-branch reads remain available to
    # authorized reporting/control-plane callers.
    if selected == "all" and db.info.get("security_write_request"):
        selected = None
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
        # Default to a concrete destination, including for administrators.
        # Cross-branch reports can still request an explicit read-only scope.
        branch_id = home if home in writable else min(writable) if writable else home if home in allowed else min(allowed) if allowed else None
    return BranchContext(company, branch_id, frozenset(allowed), frozenset(writable), all_access, manager, bool(user.is_superuser))


def audit(db, user, company, operation, reason, details):
    db.connection().execute(BranchAudit.__table__.insert().values(company_id=company, actor_id=user.id, operation=operation, reason=reason, details=details))


def assert_manager(db, user):
    _, _, _, manager = access(db, user, user.organization_id)
    if not manager:
        raise HTTPException(403, "Branch access administration is required")


def create_owned_branch(db, user, values, *, reason):
    """Create through the company control plane, including legacy API adapters."""
    from sqlalchemy import select, func, or_
    from app.models.company import Branch
    from app.branches.models import BranchOwnership
    assert_manager(db, user)
    company = user.organization_id
    if values.get("company_id") not in {None, company} or values.get("organization_id") not in {None, company}:
        raise HTTPException(403, "Branch belongs to another company")
    data = {key:value for key,value in values.items() if key in Branch.__table__.c and key not in {"id", "created_by", "created_at", "updated_at"}}
    name = str(data.get("name", "")).strip()
    if not name:
        raise HTTPException(422, "Branch name is required")
    duplicates = [func.lower(Branch.name) == name.casefold()]
    if data.get("code"):
        duplicates.append(func.lower(Branch.code) == data["code"].strip().casefold())
    connection = db.connection()
    if connection.execute(select(Branch.id).where(Branch.company_id==company, or_(*duplicates))).first():
        raise HTTPException(409, "Branch name or code already exists in this company")
    data.update(name=name, company_id=company, organization_id=company, created_by=user.id, is_active=True)
    row = dict(connection.execute(Branch.__table__.insert().values(**data).returning(*Branch.__table__.c)).mappings().one())
    connection.execute(BranchOwnership.__table__.insert().values(resource_table="branches", resource_key=str(row["id"]), company_id=company, branch_id=row["id"], source="branch-created"))
    audit(db, user, company, "branch.create", reason, {"branch_id":row["id"], "name":name, "code":row.get("code")})
    db.commit()
    return row
