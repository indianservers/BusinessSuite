from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import update,delete
from app.models.user import User,Role
from app.apps.srm.pos_customer_fields import _policy

@pytest.mark.parametrize('before,after',[(False,True),(True,False)])
def test_legacy_role_null_transition_requires_fresh_actor_before_field_policy(db,before,after):
    role=Role(name='fls_'+uuid4().hex);db.add(role);db.flush()
    actor=User(email=uuid4().hex+'@example.test',hashed_password='unused',is_active=True,role_id=role.id if before else None)
    db.add(actor);db.flush()
    db.connection().execute(update(User.__table__).where(User.id==actor.id).values(role_id=role.id if after else None))
    with pytest.raises(HTTPException) as error:_policy(db,actor)
    assert error.value.status_code==403
    db.refresh(actor)
    assert _policy(db,actor)==(role.id if after else None,[])


def test_roleless_native_fls_matches_no_profile_and_never_uses_policy_label(db):
    from app.apps.admin_security.services import field_rules
    from app.apps.admin_security.models import AdminProfile,AdminFieldSecurity
    actor=User(email=uuid4().hex+'@example.test',hashed_password='unused',is_active=True,role_id=None)
    profile=AdminProfile(name='Company Admin',active=True)
    db.add_all([actor,profile]);db.flush()
    db.add(AdminFieldSecurity(profile_id=profile.id,module_name='srm',field_name='private_field',can_view=False,can_edit=False,mask_value=True));db.flush()
    assert field_rules(db,'srm',actor)==[]
    assert _policy(db,actor)==(None,[])

@pytest.mark.parametrize('fault',['inactive','deleted_role'])
def test_actual_inactive_or_deleted_native_role_does_not_get_roleless_fallback(db,fault):
    role=Role(name='fls_'+uuid4().hex);db.add(role);db.flush()
    actor=User(email=uuid4().hex+'@example.test',hashed_password='unused',is_active=True,role_id=role.id)
    db.add(actor);db.flush()
    if fault=='inactive':db.connection().execute(update(User.__table__).where(User.id==actor.id).values(is_active=False))
    else:db.connection().execute(delete(Role.__table__).where(Role.id==role.id))
    with pytest.raises(HTTPException) as error:_policy(db,actor)
    assert error.value.status_code==403
