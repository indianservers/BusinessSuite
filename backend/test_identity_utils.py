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
    branch = db.query(Branch).filter_by(company_id=company_id, code="WORKFLOW-TEST").first()
    if branch is None:
        branch = Branch(company_id=company_id, name="Workflow test branch", code="WORKFLOW-TEST")
        db.add(branch); db.flush()
    if not db.query(BranchGrant).filter_by(company_id=company_id, user_id=user.id, branch_id=branch.id).first():
        db.add(BranchGrant(company_id=company_id, user_id=user.id, branch_id=branch.id, can_write=True))
    db.flush()
    backfill(db.connection(), company_id, table_names={"branches"})
    return branch
