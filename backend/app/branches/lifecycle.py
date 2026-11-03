"""Company-scoped branch administration, with reversible lifecycle transitions."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, update, func
from app.models.company import Branch, Company
from app.models.employee import Employee
from app.branches.models import BranchLifecycle, BranchGrant, BranchPolicy
from app.branches.service import access, assert_manager, audit

RETENTION_DAYS = 45


def management_scope(db, user):
    assert_manager(db, user)
    company = user.organization_id
    connection = db.connection()
    allowed, writable, all_access, _ = access(db, user, company)
    if all_access:
        ids = set(connection.execute(select(Branch.id).where(Branch.company_id == company)).scalars())
        return ids, ids
    # Retain authority over deleted branches so delegated heads can restore them.
    grants = connection.execute(select(BranchGrant.branch_id, BranchGrant.can_write).join(Branch, Branch.id == BranchGrant.branch_id).where(BranchGrant.user_id == user.id, BranchGrant.company_id == company, Branch.company_id == company)).all()
    visible = set(allowed) | {g.branch_id for g in grants}
    editable = set(writable) | {g.branch_id for g in grants if g.can_write}
    policy = connection.execute(select(BranchPolicy.use_home_branch).where(BranchPolicy.user_id == user.id, BranchPolicy.company_id == company)).scalar()
    if policy is not False:
        homes = set(connection.execute(select(Employee.branch_id).join(Branch, Branch.id == Employee.branch_id).where(Employee.user_id == user.id, Employee.deleted_at.is_(None), Branch.company_id == company)).scalars())
        visible |= homes
        editable |= homes
    return visible, editable


def branch_list(db, user):
    visible, editable = management_scope(db, user)
    active_count = db.connection().execute(select(func.count()).select_from(Branch).where(Branch.company_id == user.organization_id, Branch.is_active.is_(True), ~Branch.id.in_(select(BranchLifecycle.branch_id).where(BranchLifecycle.deleted_at.is_not(None))))).scalar_one()
    rows = db.connection().execute(select(Branch.id, Branch.name, Branch.code, Branch.is_active, BranchLifecycle.deleted_at, BranchLifecycle.protected_at, BranchLifecycle.retain_until, BranchLifecycle.version).outerjoin(BranchLifecycle, BranchLifecycle.branch_id == Branch.id).where(Branch.company_id == user.organization_id, Branch.id.in_(visible)).order_by(Branch.name)).mappings()
    return {"retention_days": RETENTION_DAYS, "permanent_delete_available": False, "branches": [{**r, "version": r["version"] or 0, "can_manage": r["id"] in editable, "can_trash": r["id"] in editable and r["is_active"] and not r["deleted_at"] and active_count > 1, "state": "protected" if r["protected_at"] else "trash" if r["deleted_at"] else "active" if r["is_active"] else "archived"} for r in rows]}


def change_branch(db, user, branch_id, operation, reason, expected_version, *, name=None, now=None, commit=True):
    _, editable = management_scope(db, user)
    if branch_id not in editable:
        raise HTTPException(404, "Branch not found or branch administration is unavailable")
    connection = db.connection()
    # Serialize company lifecycle changes, including the last-active-branch check.
    connection.execute(select(Company.id).where(Company.id == user.organization_id).with_for_update()).first()
    branch = connection.execute(select(Branch.__table__).where(Branch.id == branch_id, Branch.company_id == user.organization_id).with_for_update()).mappings().first()
    if not branch:
        raise HTTPException(404, "Branch not found")
    row = connection.execute(select(BranchLifecycle.__table__).where(BranchLifecycle.branch_id == branch_id).with_for_update()).mappings().first()
    version = row["version"] if row else 0
    if expected_version != version:
        raise HTTPException(409, "Branch changed. Refresh and try again.")
    if not reason or not 5 <= len(reason.strip()) <= 1000:
        raise HTTPException(422, "Provide a reason between 5 and 1000 characters")
    now = now or datetime.now(timezone.utc)
    state = dict(row) if row else dict(branch_id=branch_id, company_id=user.organization_id, deleted_at=None, deleted_by=None, protected_at=None, protected_by=None, retain_until=None, version=0)
    before = {"name": branch["name"], "is_active": branch["is_active"], "state": "protected" if state["protected_at"] else "trash" if state["deleted_at"] else "active" if branch["is_active"] else "archived", "version": version}
    values = {}
    if operation == "rename":
        if state["deleted_at"]:
            raise HTTPException(409, "Restore this branch before renaming it")
        name = (name or "").strip()
        if not name or len(name) > 150:
            raise HTTPException(422, "Enter a branch name between 1 and 150 characters")
        values["name"] = name
    elif operation == "trash":
        if state["deleted_at"]:
            raise HTTPException(409, "Branch is already in recovery")
        remaining = connection.execute(select(func.count()).select_from(Branch).where(Branch.company_id == user.organization_id, Branch.is_active.is_(True), Branch.id != branch_id, ~Branch.id.in_(select(BranchLifecycle.branch_id).where(BranchLifecycle.deleted_at.is_not(None))))).scalar_one()
        if not remaining:
            raise HTTPException(409, "Keep at least one active branch. Create or restore another branch first.")
        state.update(deleted_at=now, deleted_by=user.id, retain_until=now + timedelta(days=RETENTION_DAYS))
        values["is_active"] = False
    elif operation == "protect":
        if not state["deleted_at"]:
            raise HTTPException(409, "Move this branch to Trash first")
        # Starting protected recovery always guarantees another full 45 days.
        previous = state["retain_until"]
        if previous and previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        state.update(protected_at=now, protected_by=user.id, retain_until=max(previous or now, now + timedelta(days=RETENTION_DAYS)))
    elif operation == "restore":
        if not state["deleted_at"] and branch["is_active"]:
            raise HTTPException(409, "Branch is already active")
        state.update(deleted_at=None, deleted_by=None, protected_at=None, protected_by=None, retain_until=None)
        values["is_active"] = True
    else:
        raise HTTPException(422, "Unsupported branch action")
    if values:
        connection.execute(update(Branch.__table__).where(Branch.id == branch_id, Branch.company_id == user.organization_id).values(**values))
    state["version"] = version + 1
    if row:
        connection.execute(update(BranchLifecycle.__table__).where(BranchLifecycle.branch_id == branch_id).values(**state))
    else:
        connection.execute(BranchLifecycle.__table__.insert().values(**state))
    audit(db, user, user.organization_id, "branch." + operation, reason, {"branch_id": branch_id, "before": before, "after": {"name": values.get("name", branch["name"]), "is_active": values.get("is_active", branch["is_active"]), "version": version + 1, "retain_until": state["retain_until"].isoformat() if state["retain_until"] else None}})
    if commit:
        db.commit()
    return {"id": branch_id, "operation": operation, "version": version + 1, "retention_days": RETENTION_DAYS, "retain_until": state["retain_until"], "permanently_deleted": False}
