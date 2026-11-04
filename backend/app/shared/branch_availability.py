"""Reusable, permission-checked availability for current active branches."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from fastapi import HTTPException
from sqlalchemy import select, delete
from app.models.company import Branch
from app.branches.models import BranchOwnership, BranchRecordShare, BranchLifecycle
from app.branches.service import access, audit


class BranchAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["current", "selected", "all"] = "current"
    branch_ids: list[int] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_selection(self):
        if len(set(self.branch_ids)) != len(self.branch_ids) or any(x <= 0 for x in self.branch_ids):
            raise ValueError("Choose distinct valid branches")
        if self.scope == "selected" and not self.branch_ids:
            raise ValueError("Choose at least one branch")
        if self.scope != "selected" and self.branch_ids:
            raise ValueError("Branch IDs are only accepted for selected branches")
        return self


def active_branches(db, company):
    return set(db.connection().execute(select(Branch.id).where(Branch.company_id == company, Branch.is_active.is_(True), ~Branch.id.in_(select(BranchLifecycle.branch_id).where(BranchLifecycle.deleted_at.is_not(None))))).scalars())


def resolve(db, actor, value, module, action="edit", validate=None):
    origin = getattr(actor, "_suite_branch_id", None)
    if origin is None:
        raise HTTPException(422, "Select a destination branch before saving availability")
    origin = int(origin)
    active = active_branches(db, actor.organization_id)
    targets = active if value.scope == "all" else set(value.branch_ids) if value.scope == "selected" else {origin}
    if origin not in targets:
        raise HTTPException(422, "Include the current branch in branch availability")
    writable = access(db, actor, actor.organization_id)[1]
    if not targets or not targets <= active or not targets <= writable:
        raise HTTPException(403, "Write access is required for every destination branch")
    check_destinations(db, actor, targets, module, action, validate)
    return targets



def check_destinations(db, actor, targets, module, action, validate=None):
    from app.access.service import check_background_access, policy_for, resolved_grants
    from app.access.service import effective_objects
    from app.branches.roles import effective_grants
    for branch in sorted(targets):
        check_background_access(db, actor, module, action, branch_id=branch)
        if validate is None or actor.is_superuser:
            continue
        policy = policy_for(db, actor, actor.organization_id)
        grants = effective_grants(db, actor, actor.organization_id, branch, resolved_grants(db, policy) if policy else None)
        previous = getattr(actor, "_suite_grants", None), getattr(actor, "_suite_permission_objects", None)
        try:
            actor._suite_grants = grants
            if grants is not None:
                actor._suite_permission_objects = effective_objects(db, grants, module)
            validate()
        finally:
            actor._suite_grants, actor._suite_permission_objects = previous

def profile_availability(db, row):
    table = row.__tablename__
    connection = db.connection()
    origin = connection.execute(select(BranchOwnership.branch_id).where(BranchOwnership.company_id == row.organization_id, BranchOwnership.resource_table == table, BranchOwnership.resource_key == str(row.id))).scalar()
    ids = set(connection.execute(select(BranchRecordShare.branch_id).where(BranchRecordShare.company_id == row.organization_id, BranchRecordShare.resource_table == table, BranchRecordShare.resource_key == str(row.id))).scalars())
    if origin is not None:
        ids.add(origin)
    return {"scope": "selected", "branch_ids": sorted(ids)} if ids else None


def save_profile_availability(db, actor, row, value, module="crm", action="edit"):
    if value is None:
        return
    from app.shared.master_data import authorize
    validate = lambda: authorize(actor, module, True, "companies" if row.__tablename__ == "crm_companies" else "contacts", action)
    targets = resolve(db, actor, value, module, action, validate)
    db.flush()
    connection = db.connection()
    table = row.__tablename__
    origin = connection.execute(select(BranchOwnership.branch_id).where(BranchOwnership.company_id == actor.organization_id, BranchOwnership.resource_table == table, BranchOwnership.resource_key == str(row.id))).scalar()
    if origin != int(actor._suite_branch_id):
        raise HTTPException(403, "Change availability from the owning branch")
    existing = profile_availability(db, row)
    # Removing a share also requires authority in that destination.
    if not set(existing["branch_ids"]) <= access(db, actor, actor.organization_id)[1]:
        raise HTTPException(403, "Write access is required for existing shared branches")
    check_destinations(db, actor, set(existing["branch_ids"]), module, action, validate)
    shares = BranchRecordShare.__table__
    condition = (shares.c.company_id == actor.organization_id, shares.c.resource_table == table, shares.c.resource_key == str(row.id))
    connection.execute(delete(shares).where(*condition))
    for branch in sorted(targets - {origin}):
        connection.execute(shares.insert().values(company_id=actor.organization_id, resource_table=table, resource_key=str(row.id), branch_id=branch))
    audit(db, actor, actor.organization_id, "branch.availability.save", "Update profile branch availability", {"table": table, "id": row.id, "before": existing, "branch_ids": sorted(targets)})

    # The universal directory represents company roles through its linked business
    # contact. Share that identity as well, never its leads or transactions.
    if table == "crm_companies":
        from app.apps.crm.contact_identity import ContactIdentityLink
        link = db.query(ContactIdentityLink).filter(ContactIdentityLink.account_id == row.id).first()
        if link:
            save_profile_availability(db, actor, link.contact, value, module, action)


def capture_availability(payload, db, actor, entity, action):
    """Remove and validate scope before legacy CRM field validation or writes."""
    raw = payload.pop("branch_availability", None)
    if raw is None:
        return None
    from pydantic import ValidationError
    try:
        value = BranchAvailability.model_validate(raw)
    except ValidationError:
        raise HTTPException(422, "Invalid branch availability selection")
    from app.apps.crm.api.router import _assert_entity_permission
    resolve(db, actor, value, "crm", action, lambda: _assert_entity_permission(entity, actor, "manage"))
    return value
