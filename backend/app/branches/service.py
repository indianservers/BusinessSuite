from dataclasses import dataclass
from fastapi import HTTPException
from sqlalchemy import select, inspect, and_, exists, literal
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
    company_admin: bool = False


def definition_target_branch(request):
    """Use the addressed branch for the exact company-definition write."""
    if (request.method in {'PUT', 'DELETE'}
            and request.url.path.rsplit('/', 1)[0] == '/api/v1/company/branches'
            and 'branch_id' in request.path_params):
        return str(request.path_params['branch_id'])
    return None


def company_administrator(db, user, company):
    from app.access.models import AccessMembership
    connection = db.connection()
    if not inspect(connection).has_table(AccessMembership.__tablename__):
        return False
    return bool(connection.execute(select(AccessMembership.id).where(
        AccessMembership.user_id == user.id, AccessMembership.company_id == company,
        AccessMembership.active.is_(True), AccessMembership.is_admin.is_(True),
    )).first())


def _access(db, user, company):
    """Resolve freshly on every request. All DB reads here are control-plane reads."""
    connection = db.connection()
    from app.access.models import AccessMembership
    from app.db.schema_columns import table_columns
    columns=table_columns(connection,(BranchPolicy.__tablename__,BranchLifecycle.__tablename__,
        BranchGrant.__tablename__,AccessMembership.__tablename__))
    required={BranchPolicy.__tablename__:{'id','company_id','user_id','all_branches','manage_access','use_home_branch'},
        BranchLifecycle.__tablename__:{'branch_id','deleted_at'},
        BranchGrant.__tablename__:{'branch_id','can_write','company_id','user_id'}}
    if any(not fields<=columns.get(table,set()) for table,fields in required.items()):
        raise HTTPException(503, "Apply the branch-access and recovery migrations before using the suite")
    membership=AccessMembership.__table__;policy_table=BranchPolicy.__table__
    member_columns=columns.get(membership.name)
    if member_columns is not None and not {'id','user_id','company_id','active','is_admin'}<=member_columns:
        raise HTTPException(503,'Apply the company-access migrations before using the suite')
    admin=exists(select(membership.c.id).where(membership.c.user_id==user.id,membership.c.company_id==company,
        membership.c.active.is_(True),membership.c.is_admin.is_(True))) if member_columns is not None else literal(False)
    control=connection.execute(select(Company.id,admin.label('company_admin'),policy_table.c.id.label('policy_id'),
        policy_table.c.all_branches,policy_table.c.manage_access,policy_table.c.use_home_branch).select_from(
        Company.__table__.outerjoin(policy_table,and_(policy_table.c.user_id==user.id,policy_table.c.company_id==Company.id))).where(
        Company.id==company,Company.is_active.is_(True))).mappings().first()
    if control is None:
        raise HTTPException(403, "Company is unavailable")
    branch_rows = connection.execute(select(Branch.id, Branch.is_active).where(Branch.company_id == company, ~Branch.id.in_(select(BranchLifecycle.branch_id).where(BranchLifecycle.deleted_at.is_not(None))))).all()
    active_branches = {r.id for r in branch_rows if r.is_active}
    available = {r.id for r in branch_rows}
    administrator = user.is_superuser or control['company_admin']
    all_access = bool(administrator or control['all_branches'])
    manager = bool(administrator or control['manage_access'])
    grants = connection.execute(select(BranchGrant.branch_id, BranchGrant.can_write).where(BranchGrant.user_id == user.id, BranchGrant.company_id == company)).all() if not all_access else []
    allowed = available if all_access else {r.branch_id for r in grants} & active_branches
    writable = active_branches.copy() if all_access else {r.branch_id for r in grants if r.can_write} & active_branches
    # All-access already includes every available home and grants write on
    # every active one. No home/grant query can change that result.
    if not all_access and (control['policy_id'] is None or control['use_home_branch']):
        home = connection.execute(select(Employee.branch_id).join(Branch, Branch.id == Employee.branch_id).where(Employee.user_id == user.id, Branch.company_id == company, Employee.deleted_at.is_(None))).scalars().first()
        if home in active_branches:
            allowed.add(home)
            if home not in {r.branch_id for r in grants}:
                writable.add(home)
    return allowed, writable, all_access, manager, bool(control['company_admin'])


def access(db,user,company):
    return _access(db,user,company)[:4]


def context(db, user, company, selected=None, *, definition_administration=False):
    from app.core.tenant_boundary import company_ids
    if not user.is_superuser and company not in company_ids(db, user):
        raise HTTPException(403, "Verified company membership is required")
    allowed, writable, all_access, manager, administrator = _access(db, user, company)
    if definition_administration:
        # Recovery addresses a definition that operational access deliberately
        # excludes. Only branch managers retain that exact native authority.
        if company != user.organization_id or selected in {None, 'all'}:
            raise HTTPException(403, 'Branch administration requires an explicit company branch')
        from app.branches.lifecycle import management_scope
        allowed, writable = management_scope(db, user)
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
    return BranchContext(company, branch_id, frozenset(allowed), frozenset(writable), all_access, manager, bool(user.is_superuser), administrator)


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
