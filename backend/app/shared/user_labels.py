"""Display labels for business-record owners within the record's company."""
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from app.access.models import AccessMembership
from app.common.models import CommonPerson
from app.common.services.identity import SharedIdentityService
from app.models.user import User


def user_labels(db, organization_id, user_ids):
    ids = {ident for ident in user_ids if ident is not None}
    if not ids:
        return {}
    members = select(AccessMembership.user_id).where(
        AccessMembership.company_id == organization_id,
        AccessMembership.active.is_(True),
    )
    people = db.query(User).options(joinedload(User.person)).filter(
        User.id.in_(ids),
        or_(User.person.has(CommonPerson.organization_id == organization_id), User.id.in_(members)),
    ).all()
    return {person.id: SharedIdentityService.display_name_for_user(person) for person in people}
