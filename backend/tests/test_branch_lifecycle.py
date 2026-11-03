from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.branches.models import BranchLifecycle, BranchPolicy, BranchGrant, BranchAudit
from app.branches.lifecycle import branch_list, change_branch
from app.branches.service import context
from app.branches.boundary import install
from app.models.company import Branch, Company
from app.apps.crm.models import CRMCompany
from tests.test_branch_access import setup


def manager(db):
    user, a, b, first, second, contact = setup(db)
    db.add(BranchPolicy(user_id=user.id, company_id=1, manage_access=True, use_home_branch=False))
    db.commit()
    return user, a, b, first


def failure(status, fn):
    with pytest.raises(HTTPException) as exc:
        fn()
    assert exc.value.status_code == status


def test_delete_protect_restore_preserves_business_data_and_saved_grants(db):
    user, a, b, customer = manager(db)
    grant = db.query(BranchGrant).filter_by(user_id=user.id, branch_id=a.id).one()
    grant.module_grants = {"crm": {"enabled": True, "role": "viewer"}}
    db.commit()
    now = datetime(2026, 11, 3, tzinfo=timezone.utc)
    change_branch(db, user, a.id, "trash", "Close office for local QA", 0, now=now)
    assert a.id not in context(db, user, 1).allowed
    assert db.connection().execute(select(CRMCompany.id).where(CRMCompany.id == customer.id)).scalar() == customer.id
    assert db.connection().execute(select(BranchGrant.module_grants).where(BranchGrant.id == grant.id)).scalar() == {"crm": {"enabled": True, "role": "viewer"}}
    # Even after 60 days in Trash, deleting from Trash starts a new 45 days.
    protected = change_branch(db, user, a.id, "protect", "Delete from ordinary Trash", 1, now=now + timedelta(days=60))
    assert protected["retain_until"] == now + timedelta(days=105)
    assert protected["permanently_deleted"] is False
    assert branch_list(db, user)["branches"][0]["state"] == "protected"
    change_branch(db, user, a.id, "restore", "Restore retained branch", 2, now=now + timedelta(days=200))
    assert a.id in context(db, user, 1).writable
    cleanup = install(db, user, context(db, user, 1, str(a.id)))
    try:
        assert db.query(CRMCompany).filter_by(id=customer.id).one().name == customer.name
    finally:
        cleanup()
    assert db.connection().execute(select(BranchLifecycle.deleted_at).where(BranchLifecycle.branch_id == a.id)).scalar() is None
    assert db.connection().execute(select(BranchAudit.operation).where(BranchAudit.company_id == 1)).scalars().all()[-3:] == ["branch.trash", "branch.protect", "branch.restore"]


def test_rename_keeps_identity_and_rejects_stale_version(db):
    user, a, _, customer = manager(db)
    change_branch(db, user, a.id, "rename", "Rename the Chennai office", 0, name="Chennai Central")
    row = db.connection().execute(select(Branch.name, Branch.code).where(Branch.id == a.id)).one()
    assert row.name == "Chennai Central" and row.code == "CHE"
    assert db.connection().execute(select(CRMCompany.branch_id).where(CRMCompany.id == customer.id)).scalar() == a.id
    failure(409, lambda: change_branch(db, user, a.id, "trash", "Stale administrator action", 0))
    failure(422, lambda: change_branch(db, user, a.id, "rename", "Reject whitespace branch name", 1, name="   "))


def test_restricted_manager_cannot_change_other_branch_or_company(db):
    user, a, b, _ = manager(db)
    db.add(Company(id=2, name="Other company", is_active=True)); db.flush()
    foreign = Branch(company_id=2, organization_id=2, name="Foreign", code="FOREIGN", is_active=True)
    db.add(foreign); db.commit()
    assert {r["id"] for r in branch_list(db, user)["branches"]} == {a.id}
    for branch_id in [b.id, foreign.id]:
        failure(404, lambda: change_branch(db, user, branch_id, "trash", "Attempt outside branch authority", 0))
    db.connection().execute(BranchPolicy.__table__.update().where(BranchPolicy.user_id == user.id).values(manage_access=False))
    db.commit()
    failure(403, lambda: branch_list(db, user))


def test_last_active_branch_cannot_be_deleted_and_archived_branch_can_restore(db):
    user, a, b, _ = manager(db)
    db.connection().execute(Branch.__table__.update().where(Branch.id == b.id).values(is_active=False)); db.commit()
    failure(409, lambda: change_branch(db, user, a.id, "trash", "Cannot delete last branch", 0))
    db.add(BranchGrant(user_id=user.id, company_id=1, branch_id=b.id, can_write=True)); db.commit()
    change_branch(db, user, b.id, "restore", "Activate previously archived branch", 0)
    assert b.id in context(db, user, 1).allowed
    change_branch(db, user, a.id, "trash", "Another branch is now active", 0)


def test_invalid_lifecycle_transitions_do_not_create_recovery_rows(db):
    user, a, _, _ = manager(db)
    failure(409, lambda: change_branch(db, user, a.id, "protect", "Not in Trash yet", 0))
    failure(409, lambda: change_branch(db, user, a.id, "restore", "Already active branch", 0))
    assert db.connection().execute(select(BranchLifecycle.branch_id)).first() is None


def test_delegated_manager_can_preserve_deleted_branch_grants_during_access_review(db):
    from starlette.requests import Request
    from app.models.user import User
    from app.branches.api import read_policy, save_policy, PolicyInput
    from tests.tenant_test_utils import assign_company
    user, a, _, _ = manager(db)
    target = User(email="recovery.member@example.test", hashed_password="unused", is_active=True)
    db.add(target); db.flush(); assign_company(db, target, 1)
    db.add(BranchGrant(user_id=target.id, company_id=1, branch_id=a.id, can_write=True)); db.commit()
    change_branch(db, user, a.id, "trash", "Retain memberships while branch is closed", 0)
    policy = read_policy(target.id, db, user)
    assert [g["branch_id"] for g in policy["grants"]] == [a.id]
    payload = PolicyInput(**{k:v for k,v in policy.items() if k != "version"}, expected_version=policy["version"], reason="Preserve inactive branch grant during review")
    save_policy(target.id, payload, Request({"type":"http", "headers":[]}), db, user)
    change_branch(db, user, a.id, "restore", "Restore reviewed branch membership", 1)
    assert a.id in context(db, target, 1).writable
