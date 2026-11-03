"""Explicit tenant setup for ordinary authenticated workflow fixtures only.

Security tests that intentionally exercise unverified identities do not call this.
"""
def attach_test_identity(db, user, company_id=1):
    from app.models.company import Company
    from app.common.services.identity import SharedIdentityService
    if not db.get(Company, company_id):
        db.add(Company(id=company_id, name='Workflow Test Company', is_active=True))
        db.flush()
    company = db.get(Company, company_id)
    if not company.email:
        company.email = f"workflow-{company_id}@example.test"
    if not company.country:
        company.country = "India"
    db.flush()
    return SharedIdentityService.ensure_person_for_user(db, user, organization_id=company_id)


def attach_workflow_branch(db, user, company_id=1):
    """Give an ordinary workflow fixture an explicit writable destination."""
    from app.models.company import Branch
    from app.branches.models import BranchGrant
    from app.branches.migration import backfill
    branch = db.query(Branch).filter(Branch.company_id == company_id, Branch.code.in_(["WORKFLOW-TEST", "DIR", "ACCESS-TEST"])).order_by(Branch.id).first()
    if branch is None:
        branch = Branch(company_id=company_id, name="Workflow test branch", code="WORKFLOW-TEST")
        db.add(branch); db.flush()
    if not db.query(BranchGrant).filter_by(company_id=company_id, user_id=user.id, branch_id=branch.id).first():
        db.add(BranchGrant(company_id=company_id, user_id=user.id, branch_id=branch.id, can_write=True))
    db.flush()
    backfill(db.connection(), company_id, table_names={"branches"})
    return branch


def own_workflow_records(db, *rows, company_id=1):
    """Stamp explicitly named synthetic seeds, never infer production ownership."""
    from app.models.company import Branch
    from app.branches.models import BranchOwnership
    from app.branches.catalog import resource_key
    db.flush()
    branch = db.query(Branch).filter_by(company_id=company_id).order_by(Branch.id).first()
    assert branch is not None, "Workflow fixture requires an explicit branch"
    for row in rows:
        table = row.__table__
        explicit_branch = getattr(row, "branch_id", None)
        row_branch = db.query(Branch).filter_by(id=explicit_branch, company_id=company_id).first() if explicit_branch is not None else branch
        assert row_branch is not None, "Synthetic record branch must belong to its fixture company"
        key = resource_key(table, {c.name: getattr(row, c.name) for c in table.primary_key})
        if not db.query(BranchOwnership).filter_by(resource_table=table.name, resource_key=key).first():
            db.add(BranchOwnership(resource_table=table.name, resource_key=key, company_id=company_id, branch_id=row_branch.id, source="explicit-test-fixture"))
    db.flush()
