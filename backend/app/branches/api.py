from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, delete, update, func, exists, and_, or_
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.company import Branch
from app.models.user import User
from app.branches.models import BranchGrant, BranchPolicy, BranchOwnership, AccountingBranchMap, BranchRecordShare, BranchLifecycle
from app.branches.service import context, access, assert_manager, audit

router = APIRouter(prefix="/branches", tags=["Branch access"])


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BranchInput(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    reason: str = Field(min_length=5, max_length=1000)


class GrantInput(StrictModel):
    branch_id: int = Field(gt=0)
    can_write: bool = False
    module_grants: dict | None = None


class LifecycleInput(StrictModel):
    reason: str = Field(min_length=5, max_length=1000)
    expected_version: int = Field(ge=0)


class RenameInput(LifecycleInput):
    name: str = Field(min_length=1, max_length=150)


@router.get("/manage")
def managed_branches(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.branches.lifecycle import branch_list
    return branch_list(db, user)


@router.patch("/{branch_id}")
def rename_branch(branch_id: int, data: RenameInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.branches.lifecycle import change_branch
    return change_branch(db, user, branch_id, "rename", data.reason.strip(), data.expected_version, name=data.name)


@router.delete("/{branch_id}")
@router.post("/{branch_id}/trash")
def trash_branch(branch_id: int, data: LifecycleInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.branches.lifecycle import change_branch
    return change_branch(db, user, branch_id, "trash", data.reason.strip(), data.expected_version)


@router.post("/{branch_id}/protect")
def protect_branch(branch_id: int, data: LifecycleInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.branches.lifecycle import change_branch
    return change_branch(db, user, branch_id, "protect", data.reason.strip(), data.expected_version)


@router.post("/{branch_id}/restore")
def restore_branch(branch_id: int, data: LifecycleInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.branches.lifecycle import change_branch
    return change_branch(db, user, branch_id, "restore", data.reason.strip(), data.expected_version)


class PolicyInput(StrictModel):
    all_branches: bool = False
    manage_access: bool = False
    use_home_branch: bool = True
    grants: list[GrantInput] = Field(default_factory=list, max_length=500)
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=1000)


@router.get("/context")
def current_context(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Ignore a stale branch header only for discovery; business requests reject it.
    ctx = context(db, user, user.organization_id)
    rows = db.connection().execute(select(Branch.id, Branch.name, Branch.code, Branch.is_active).where(Branch.company_id == ctx.company_id, Branch.id.in_(ctx.allowed)).order_by(Branch.name)).mappings().all()
    default_branch_id = ctx.branch_id if ctx.branch_id in ctx.writable else None
    selected = request.headers.get("X-Suite-Branch")
    if selected and selected != "all":
        try:
            ctx = context(db, user, user.organization_id, selected)
        except HTTPException:
            pass
    return {"company_id": ctx.company_id, "default_branch_id": default_branch_id, "selected": ctx.branch_id, "all_branches": ctx.all_branches, "manage_access": ctx.manage_access,
            "branches": [{**row, "can_write": row["id"] in ctx.writable} for row in rows]}


@router.post("", status_code=201)
def create_branch(data: BranchInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_manager(db, user)
    connection = db.connection()
    name, code = data.name.strip(), data.code.strip()
    if not name:
        raise HTTPException(422, "Branch name is required")
    if connection.execute(select(Branch.id).where(Branch.company_id == user.organization_id, func.lower(Branch.code) == code.lower())).first():
        raise HTTPException(409, "Branch code already exists in this company")
    ident = connection.execute(Branch.__table__.insert().values(name=name, code=code, company_id=user.organization_id, organization_id=user.organization_id, is_active=True, created_by=user.id).returning(Branch.id)).scalar_one()
    connection.execute(BranchOwnership.__table__.insert().values(resource_table="branches", resource_key=str(ident), company_id=user.organization_id, branch_id=ident, source="branch-created"))
    audit(db, user, user.organization_id, "branch.create", data.reason, {"branch_id": ident, "name": name, "code": code})
    db.commit()
    return {"id": ident, "name": name, "code": code}


@router.get("/access/users")
def users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_manager(db, user)
    from app.common.models import CommonPerson
    from app.models.employee import Employee
    from app.access.models import AccessMembership
    c = user.organization_id
    # Use the same company roster as Users & Permissions, including legacy
    # default-company accounts. This only exposes administration metadata;
    # assigning access still requires verified company membership below.
    from app.services.metrics.queries import registered_users
    ids = registered_users(db, None, include_invited=True, organization_id=c).with_entities(User.id).statement

    allowed, _, all_access, _ = access(db, user, c)
    if not user.is_superuser:
        from app.branches.lifecycle import management_scope
        allowed = management_scope(db, user)[0]
    visible = select(Employee.user_id).join(Branch, Branch.id == Employee.branch_id).where(Branch.company_id == c, Employee.branch_id.in_(allowed), Employee.deleted_at.is_(None)).union(
        select(BranchGrant.user_id).where(BranchGrant.company_id == c, BranchGrant.branch_id.in_(allowed)))
    query = select(User.id, User.email, User.is_superuser).where(User.id.in_(ids))
    if not user.is_superuser and not all_access:
        query = query.where(User.id.in_(visible))
    return [dict(row) for row in db.connection().execute(query.order_by(User.email)).mappings()]


@router.get("/access/{user_id}")
def read_policy(user_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_manager(db, user)
    if user_id not in {r["id"] for r in users(db, user)}:
        raise HTTPException(404, "Company member not found")
    row = db.connection().execute(select(BranchPolicy.__table__).where(BranchPolicy.user_id == user_id, BranchPolicy.company_id == user.organization_id)).mappings().first()
    grants = db.connection().execute(select(BranchGrant.branch_id, BranchGrant.can_write, BranchGrant.module_grants).where(BranchGrant.user_id == user_id, BranchGrant.company_id == user.organization_id)).mappings().all()
    if not user.is_superuser:
        from app.branches.lifecycle import management_scope
        allowed = management_scope(db, user)[0]
        grants = [g for g in grants if g['branch_id'] in allowed]
    return {"all_branches": bool(row and row["all_branches"]), "manage_access": bool(row and row["manage_access"]), "use_home_branch": row["use_home_branch"] if row else True, "version": row["version"] if row else 0, "grants": [dict(g) for g in grants]}


@router.put("/access/{user_id}")
def save_policy(user_id: int, data: PolicyInput, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_manager(db, user)
    if user_id == user.id:
        raise HTTPException(403, "You cannot change your own branch authority")
    before = read_policy(user_id, db, user)
    # A delegated head may inspect only their branches. Replacement still checks
    # the complete stored policy, so hidden grants can never be erased or widened.
    before['grants'] = [dict(g) for g in db.connection().execute(select(BranchGrant.branch_id, BranchGrant.can_write, BranchGrant.module_grants).where(BranchGrant.user_id == user_id, BranchGrant.company_id == user.organization_id)).mappings()]
    from app.access.service import validate_grants
    old_roles = {g['branch_id']: g.get('module_grants') for g in before['grants']}
    roles_changed = {g.branch_id: g.module_grants for g in data.grants if g.module_grants is not None} != {branch: roles for branch, roles in old_roles.items() if roles is not None}
    if roles_changed:
        from app.access.api import company_access, authority, check_step
        company_access(db, user, user.organization_id)
        check_step(request, user)
    for grant in data.grants:
        if grant.module_grants is not None:
            grant.module_grants = validate_grants(db, grant.module_grants, user.organization_id)
            if roles_changed:
                authority(user, grant.module_grants)
    if db.connection().execute(select(User.is_superuser).where(User.id == user_id)).scalar():
        raise HTTPException(403, "Super Admin branch authority cannot be changed here")
    allowed, writable, all_access, _ = access(db, user, user.organization_id)
    inactive_ids = set(db.connection().execute(select(Branch.id).outerjoin(BranchLifecycle, BranchLifecycle.branch_id == Branch.id).where(Branch.company_id == user.organization_id, or_(Branch.is_active.is_(False), BranchLifecycle.deleted_at.is_not(None)))).scalars())
    before_grants = {g["branch_id"]: g for g in before["grants"]}
    preserved_inactive = {g.branch_id for g in data.grants if g.branch_id in inactive_ids and g.model_dump() == before_grants.get(g.branch_id)}
    if not user.is_superuser:
        if data.manage_access or data.all_branches or before["manage_access"] or before["all_branches"]:
            raise HTTPException(403, "Only Super Admin can grant or revoke company-wide branch authority")
        if any(g.branch_id not in preserved_inactive and (g.branch_id not in allowed or g.can_write and g.branch_id not in writable) for g in data.grants):
            raise HTTPException(403, "Cannot grant branch access above your authority")
        from app.branches.lifecycle import management_scope
        managed_ids = management_scope(db, user)[0]
        if any(g["branch_id"] not in allowed and g["branch_id"] not in managed_ids for g in before["grants"]):
            raise HTTPException(403, "Cannot replace grants outside your authority")
    branch_ids = [g.branch_id for g in data.grants]
    if len(branch_ids) != len(set(branch_ids)):
        raise HTTPException(422, "Duplicate branch grants")
    actual = set(db.connection().execute(select(Branch.id).where(Branch.company_id == user.organization_id, Branch.is_active.is_(True), Branch.id.in_(branch_ids))).scalars())
    if (actual - inactive_ids) | preserved_inactive != set(branch_ids):
        raise HTTPException(422, "Every branch must be active and belong to this company")
    if not user.is_superuser and data.use_home_branch != before["use_home_branch"]:
        from app.models.employee import Employee
        home = db.connection().execute(select(Employee.branch_id).join(Branch, Branch.id == Employee.branch_id).where(Employee.user_id == user_id, Employee.deleted_at.is_(None), Branch.company_id == user.organization_id)).scalars().first()
        if home is not None and (home not in allowed or home not in writable):
            raise HTTPException(403, "Cannot change home-branch access outside your authority")
    if before["version"] != data.expected_version:
        raise HTTPException(409, "Branch access changed; reload before saving")
    from app.core.tenant_boundary import company_ids
    from types import SimpleNamespace
    if user.organization_id not in company_ids(db, SimpleNamespace(id=user_id)):
        from app.access.api import company_access, check_step
        from app.access.models import AccessMembership
        company_access(db, user, user.organization_id)
        check_step(request, user)
        member = db.query(AccessMembership).filter_by(user_id=user_id, company_id=user.organization_id).first()
        if member is not None:
            raise HTTPException(403, "Company membership was revoked. Restore it in Organization membership before assigning branches")
        db.add(AccessMembership(user_id=user_id, company_id=user.organization_id, active=True, is_admin=False))
        db.flush()
        audit(db, user, user.organization_id, "branch.legacy-membership.link", data.reason, {"user_id":user_id,"is_admin":False})
    table = BranchPolicy.__table__
    values = {"all_branches": data.all_branches, "manage_access": data.manage_access, "use_home_branch": data.use_home_branch, "version": before["version"] + 1}
    if before["version"]:
        changed = db.connection().execute(update(table).where(table.c.company_id == user.organization_id, table.c.user_id == user_id, table.c.version == data.expected_version).values(**values))
        if changed.rowcount != 1:
            raise HTTPException(409, "Branch access changed; reload before saving")
    else:
        db.connection().execute(table.insert().values(user_id=user_id, company_id=user.organization_id, **values))
    db.connection().execute(delete(BranchGrant).where(BranchGrant.user_id == user_id, BranchGrant.company_id == user.organization_id))
    for grant in data.grants:
        db.connection().execute(BranchGrant.__table__.insert().values(user_id=user_id, company_id=user.organization_id, **grant.model_dump()))
    audit(db, user, user.organization_id, "branch.access.replace", data.reason, {"user_id": user_id, "before": before, "after": data.model_dump(exclude={"reason"})})
    db.commit()
    return read_policy(user_id, db, user)


@router.get("/ownership/inventory")
def ownership_inventory(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_manager(db, user)
    from app.branches.catalog import inventory
    from app.db.base_class import Base
    return {"tables": inventory(Base.metadata)}


class ReasonInput(StrictModel):
    reason: str = Field(min_length=5, max_length=1000)


class MappingInput(ReasonInput):
    accounting_branch_id: int = Field(gt=0)
    branch_id: int = Field(gt=0)


@router.put("/accounting-map")
def map_accounting_branch(data: MappingInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_manager(db, user)
    from app.db.base_class import Base
    fam = Base.metadata.tables.get("fam_branches")
    if fam is None:
        raise HTTPException(409, "Accounting is not installed")
    connection = db.connection()
    allowed, writable, _, _ = access(db, user, user.organization_id)
    if data.branch_id not in writable:
        raise HTTPException(403, "Writable branch access is required")
    if not connection.execute(select(fam.c.id).where(fam.c.id == data.accounting_branch_id, fam.c.company_id == user.organization_id)).first():
        raise HTTPException(404, "Accounting branch not found in this company")
    existing = connection.execute(select(AccountingBranchMap.__table__).where(AccountingBranchMap.accounting_branch_id == data.accounting_branch_id)).mappings().first()
    if existing and (existing["company_id"] != user.organization_id or existing["branch_id"] != data.branch_id):
        raise HTTPException(409, "An existing accounting mapping cannot be silently reassigned")
    if not existing:
        connection.execute(AccountingBranchMap.__table__.insert().values(company_id=user.organization_id, **data.model_dump(exclude={"reason"})))
    audit(db, user, user.organization_id, "branch.accounting.map", data.reason, data.model_dump(exclude={"reason"}))
    db.commit()
    return {"mapped": True}


@router.post("/ownership/backfill")
def backfill_ownership(data: ReasonInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_manager(db, user)
    # Backfill is company-wide administration, not an ordinary branch write.
    if not user.is_superuser:
        raise HTTPException(403, "Super Admin is required for historical-data migration")
    from app.branches.migration import backfill
    assigned = backfill(db.connection(), user.organization_id)
    audit(db, user, user.organization_id, "branch.ownership.backfill", data.reason, assigned)
    db.commit()
    return {"assigned": assigned, "total": sum(assigned.values())}


def migration_table(db, user, table_name):
    from app.db.base_class import Base
    from app.branches.catalog import SHARED
    from app.core.tenant_boundary import tenant_company_column
    assert_manager(db, user)
    if not user.is_superuser:
        raise HTTPException(403, "Super Admin is required for historical-data migration")
    models = {m.local_table.name: m.class_ for m in Base.registry.mappers}
    model = models.get(table_name)
    if model is None or table_name in SHARED:
        raise HTTPException(422, "Choose a private business table")
    table = model.__table__
    if "organization_id" in table.c:
        guard = table.c.organization_id == user.organization_id
    elif tenant_company_column(model):
        guard = table.c.company_id == user.organization_id
    else:
        from app.branches.catalog import parents, key_expression
        ownership = BranchOwnership.__table__
        links = []
        for column, parent, key in parents(table, Base.metadata.tables):
            company_parent = column.in_(select(key).select_from(parent.join(ownership, and_(ownership.c.resource_table == parent.name, ownership.c.resource_key == key_expression(parent), ownership.c.company_id == user.organization_id))))
            links.append((column, company_parent))
        if not links:
            raise HTTPException(409, "Company ownership must be resolved before assigning this record")
        guard = and_(or_(*(access for _, access in links)), *(or_(column.is_(None), access) if column.nullable else access for column, access in links))
    return table, guard


@router.get("/ownership/unassigned")
def unassigned(table_name: str = Query(min_length=1, max_length=120), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.branches.catalog import key_expression
    table, guard = migration_table(db, user, table_name)
    ownership = BranchOwnership.__table__
    missing = ~exists(select(1).where(ownership.c.resource_table == table.name, ownership.c.resource_key == key_expression(table)))
    columns = [key_expression(table).label("resource_key")]
    for name in ("name", "title", "order_number", "invoice_number", "branch_id"):
        if name in table.c: columns.append(table.c[name])
    rows = db.connection().execute(select(*columns).where(guard, missing).order_by(*table.primary_key).limit(100)).mappings().all()
    total = db.connection().execute(select(func.count()).select_from(table).where(guard, missing)).scalar_one()
    return {"table": table_name, "total": total, "items": [dict(row) for row in rows]}


class AssignmentInput(ReasonInput):
    table_name: str = Field(min_length=1, max_length=120)
    resource_keys: list[str] = Field(min_length=1, max_length=100)
    branch_id: int = Field(gt=0)


@router.post("/ownership/assign")
def assign_ownership(data: AssignmentInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.branches.catalog import key_expression
    from app.branches.boundary import branch_for_row
    from app.db.base_class import Base
    table, guard = migration_table(db, user, data.table_name)
    if data.branch_id not in access(db, user, user.organization_id)[1]:
        raise HTTPException(403, "Writable branch access is required")
    connection = db.connection()
    rows = connection.execute(select(table).where(guard, key_expression(table).in_(data.resource_keys)).with_for_update()).mappings().all()
    if len(rows) != len(set(data.resource_keys)):
        raise HTTPException(404, "One or more company records are unavailable")
    from app.branches.catalog import resource_key
    for row in rows:
        key = resource_key(table, row)
        if connection.execute(select(BranchOwnership.branch_id).where(BranchOwnership.resource_table == table.name, BranchOwnership.resource_key == key)).first():
            raise HTTPException(409, "A record already has ownership; refresh the review list")
        evidence = branch_for_row(connection, table, row, user.organization_id, Base.metadata.tables, historical=True)
        if evidence and evidence != {data.branch_id}:
            raise HTTPException(409, "Assignment conflicts with existing branch or parent ownership")
        connection.execute(BranchOwnership.__table__.insert().values(resource_table=table.name, resource_key=key, company_id=user.organization_id, branch_id=data.branch_id, source="admin-reviewed"))
    audit(db, user, user.organization_id, "branch.ownership.assign", data.reason, data.model_dump(exclude={"reason"}))
    db.commit()
    return {"assigned": len(rows)}


class ShareInput(ReasonInput):
    table_name: str
    resource_key: str = Field(min_length=1, max_length=500)
    branch_id: int = Field(gt=0)
    shared: bool = True


@router.post("/records/share")
def share_profile(data: ShareInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_manager(db, user)
    from app.core.masking import user_has_permission
    if not user.is_superuser and not user_has_permission(user, "crm_manage"):
        raise HTTPException(403, "CRM management permission is required")
    if data.table_name not in {"crm_companies", "crm_contacts"}:
        raise HTTPException(422, "Only customer and contact profiles can be shared; transactions remain private")
    connection = db.connection()
    stamp = connection.execute(select(BranchOwnership.branch_id).where(BranchOwnership.company_id == user.organization_id, BranchOwnership.resource_table == data.table_name, BranchOwnership.resource_key == data.resource_key).with_for_update()).scalar()
    allowed, writable, _, _ = access(db, user, user.organization_id)
    if stamp is None or stamp not in writable or data.branch_id not in allowed:
        raise HTTPException(403, "Source write access and destination branch access are required")
    table = BranchRecordShare.__table__
    condition = (table.c.company_id == user.organization_id, table.c.resource_table == data.table_name, table.c.resource_key == data.resource_key, table.c.branch_id == data.branch_id)
    connection.execute(delete(table).where(*condition))
    if data.shared:
        connection.execute(table.insert().values(company_id=user.organization_id, resource_table=data.table_name, resource_key=data.resource_key, branch_id=data.branch_id))
    audit(db, user, user.organization_id, "branch.profile.share" if data.shared else "branch.profile.unshare", data.reason, data.model_dump(exclude={"reason"}))
    db.commit()
    return {"shared": data.shared}
