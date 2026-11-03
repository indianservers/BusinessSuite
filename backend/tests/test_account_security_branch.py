"""Own-account security mail does not borrow business branch privileges."""
import pytest
from fastapi import HTTPException
from types import SimpleNamespace
from app.models.user import User
from app.models.email_outbox import EmailOutbox
from app.core.security import get_password_hash, verify_password
from test_identity_utils import attach_test_identity


def test_password_change_without_business_branch(client, db):
    user = User(email="branchless-security@example.com", hashed_password=get_password_hash("Before@12345"), is_active=True)
    db.add(user)
    attach_test_identity(db, user)
    db.commit()
    login = client.post("/api/v1/auth/login", json={"email":user.email,"password":"Before@12345"})
    assert login.status_code == 200, login.text
    changed = client.post("/api/v1/auth/change-password", headers={"Authorization":"Bearer "+login.json()["access_token"]}, json={"current_password":"Before@12345","new_password":"After@123456"})
    assert changed.status_code == 200, changed.text
    db.refresh(user)
    assert verify_password("After@123456", user.hashed_password)
    assert db.query(EmailOutbox).filter_by(recipient_user_id=user.id,module="security").count() > 0


@pytest.mark.parametrize("module,recipient,org", [("customer_communication","own@example.com",1),("security","other@example.com",1),("security","own@example.com",2)])
def test_security_mail_exception_never_widens_business_or_recipient_access(db, module, recipient, org):
    from app.branches.boundary import install
    actor = User(email="own@example.com", hashed_password="unused", is_active=True)
    db.add(actor)
    attach_test_identity(db,actor)
    db.commit()
    ctx = SimpleNamespace(company_id=1,branch_id=None,allowed=set(),writable=set(),superuser=False,all_branches=False)
    cleanup = install(db,actor,ctx)
    db.info["account_security_change"] = actor.id
    try:
        db.add(EmailOutbox(event_key=f"scope-{module}-{recipient}-{org}",organization_id=org,module=module,recipient_user_id=actor.id,recipient=recipient,subject="Test",body="Test"))
        with pytest.raises(HTTPException):
            db.flush()
    finally:
        db.rollback()
        db.info.pop("account_security_change",None)
        cleanup()
