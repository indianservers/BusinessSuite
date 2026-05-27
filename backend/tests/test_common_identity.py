from app.common.models import CommonPerson, CommonProfile
from app.common.services.identity import SharedIdentityService
from app.core.security import get_password_hash
from app.models.user import Role, User


def test_common_identity_creates_person_and_profile(db):
    role = Role(name="identity_role", description="Identity Role")
    db.add(role)
    db.flush()
    user = User(email="person@example.com", hashed_password=get_password_hash("Secret@123"), role_id=role.id)
    db.add(user)
    db.flush()

    person = SharedIdentityService.ensure_person_for_user(
        db,
        user,
        display_name="Person Example",
        organization_id=7,
        phone_number="+919999999999",
        source_module="common",
        source_record_type="user",
        source_record_id=user.id,
    )
    db.flush()

    assert db.query(CommonPerson).count() == 1
    assert db.query(CommonProfile).count() == 1
    assert person.display_name == "Person Example"
    assert person.profile.directory_visibility == "public"


def test_common_identity_search_uses_central_person_table(db):
    user = User(email="owner@example.com", hashed_password=get_password_hash("Secret@123"), is_active=True)
    db.add(user)
    db.flush()
    SharedIdentityService.ensure_person_for_user(db, user, display_name="CRM Owner", organization_id=3)
    db.commit()

    results = SharedIdentityService.search_users(db, query="owner", organization_id=3)

    assert len(results) == 1
    assert results[0].display_name == "CRM Owner"
    assert results[0].person_id is not None
