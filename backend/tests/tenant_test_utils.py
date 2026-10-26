"""Persist tenant identities so HTTP auth resolves the intended test company."""
from app.common.models import CommonPerson
from app.models.company import Company

def assign_company(db, user, company_id):
    if not db.get(Company, company_id):
        db.add(Company(id=company_id, name=f"Audit tenant {company_id}", is_active=True))
        db.flush()
    person = db.query(CommonPerson).filter_by(user_id=user.id).first()
    if person is None:
        person = CommonPerson(user_id=user.id, primary_email=user.email, display_name=user.email, organization_id=company_id)
        db.add(person)
    else:
        person.organization_id = company_id
    user.person = person
    user.organization_id = company_id
    db.flush()
