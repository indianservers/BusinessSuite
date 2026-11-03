from app.models.company import Company, Branch
from app.branches.models import BranchOwnership
from app.apps.interns_hub.models import InternApplication
from app.apps.interns_hub.management_models import ApplicationEvent
from app.apps.interns_hub.branch_ownership import repair_pending


def test_pending_intake_repair_preserves_assignments_and_company_boundaries(db):
    if not db.get(Company, 1):
        db.add(Company(id=1, name="Main company", is_active=True))
    db.add(Company(id=2, name="Other company", is_active=True))
    db.flush()
    main = Branch(company_id=1, name="Main", is_active=True)
    other = Branch(company_id=1, name="Other branch", is_active=True)
    db.add_all([main, other])
    db.flush()
    def application(ident, company=1):
        return InternApplication(organization_id=company, reference=f"APP-{ident}",
            email=f"applicant{ident}@example.com", full_name="Test applicant", password_hash="unused",
            details={}, identity_number_encrypted="encrypted", identity_last4="1234", status="Pending")
    unresolved, assigned, foreign = application(1), application(2), application(3, 2)
    db.add_all([unresolved, assigned, foreign])
    db.flush()
    db.add(BranchOwnership(resource_table=assigned.__tablename__, resource_key=str(assigned.id),
        company_id=1, branch_id=other.id, source="existing"))
    first_event = ApplicationEvent(application_id=unresolved.id, state="Registered")
    assigned_event = ApplicationEvent(application_id=assigned.id, state="Registered")
    db.add_all([first_event, assigned_event])
    db.flush()
    connection = db.connection()
    preview = repair_pending(connection, 1)
    assert preview["applications"] == 1 and preview["children"] == 2
    assert not db.query(BranchOwnership).filter_by(resource_key=str(unresolved.id), resource_table=unresolved.__tablename__).count()
    assert repair_pending(connection, 1, apply=True) == preview
    def owner(item):
        return db.query(BranchOwnership).filter_by(resource_table=item.__tablename__, resource_key=str(item.id)).one()
    assert owner(unresolved).branch_id == main.id
    assert owner(first_event).branch_id == main.id
    assert owner(assigned).branch_id == other.id and owner(assigned).source == "existing"
    assert owner(assigned_event).branch_id == other.id
    assert not db.query(BranchOwnership).filter_by(resource_table=foreign.__tablename__, resource_key=str(foreign.id)).count()
    again = repair_pending(connection, 1, apply=True)
    assert again["applications"] == again["children"] == 0
