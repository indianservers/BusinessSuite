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
    complete_workflow_company(db, company_id)
    from app.models.company import Branch
    from app.branches.models import BranchGrant
    from app.branches.migration import backfill
    branch = db.query(Branch).filter(Branch.company_id == company_id, Branch.is_active.is_(True)).order_by(Branch.id).first()
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
        if "organization_id" in table.c and getattr(row, "organization_id", None) is None:
            row.organization_id = company_id
        if "branch_id" in table.c and explicit_branch is None and any(fk.column.table.name == "branches" for fk in table.c.branch_id.foreign_keys):
            row.branch_id = row_branch.id
        key = resource_key(table, {c.name: getattr(row, c.name) for c in table.primary_key})
        if not db.query(BranchOwnership).filter_by(resource_table=table.name, resource_key=key).first():
            db.add(BranchOwnership(resource_table=table.name, resource_key=key, company_id=company_id, branch_id=row_branch.id, source="explicit-test-fixture"))
    db.flush()


def complete_workflow_company(db, company_id=1):
    """Provision readiness for ordinary workflow fixtures, without elevating actors.

    Setup/readiness tests deliberately construct their own incomplete companies.
    This helper is only used by fixtures that promise a provisioned workflow.
    """
    from app.models.company import Company
    from app.models.user import User
    from app.access.models import AccessMembership
    from app.access.setup import essentials
    company = db.get(Company, company_id)
    assert company is not None, "Provision a fixture company before completing setup"
    company.email = company.email or f"workflow-{company_id}@example.test"
    company.country = company.country or "India"
    db.flush()
    if not next(item["ready"] for item in essentials(db, company_id) if item["id"] == "administrator"):
        # A separate non-login administrator satisfies company readiness. The
        # actor's memberships, role, module permissions and branch grants stay intact.
        admin = User(email=f"setup-admin-{company_id}@example.test", hashed_password="!fixture-no-login!", is_active=True)
        db.add(admin); db.flush()
        db.add(AccessMembership(user_id=admin.id, company_id=company_id, active=True, is_admin=True))
        db.flush()


def provision_workflow_workspace(db, user, company_id=1):
    from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember
    workspace = db.query(PMSWorkspace).filter_by(organization_id=company_id, name="Workflow test workspace").first()
    if workspace is None:
        workspace = PMSWorkspace(organization_id=company_id, name="Workflow test workspace")
        db.add(workspace); db.flush()
        own_workflow_records(db, workspace, company_id=company_id)
    if not db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace.id, user_id=user.id).first():
        member = PMSWorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="Owner")
        db.add(member); db.flush()
        own_workflow_records(db, member, company_id=company_id)
    return workspace
