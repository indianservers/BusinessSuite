import pytest
from sqlalchemy import text
from app.models.user import User, UserSession, MFAMethod
from app.core.security import get_password_hash, verify_password
from app.db.init_common_db import init_common_db
from app.core.config import settings
from scripts.retire_demo_accounts import retire


def test_retire_credentials_preserves_records_and_real_admin(db):
    owner=User(email="real-owner@example.com",hashed_password=get_password_hash("Owner-only-password!"),is_superuser=True,is_active=True)
    fixture=User(email="admin@karyaflow.com",hashed_password=get_password_hash("Password@123"),is_superuser=True,is_active=True,password_reset_token="old-reset")
    db.add_all([owner,fixture]); db.flush()
    session=UserSession(user_id=fixture.id,session_token_hash="old-session",status="Active",trusted_device=True)
    mfa=MFAMethod(user_id=fixture.id,method_type="TOTP",secret="old-secret",is_active=True)
    db.add_all([session,mfa]);db.flush()
    report=retire(db.connection(),owner.email,apply=True)
    db.expire_all()
    assert report["matched"]==1 and report["sessions_revoked"]==1 and report["mfa_methods_removed"]==1
    assert db.get(User,fixture.id) is not None
    assert not fixture.is_active and not fixture.is_superuser and fixture.password_reset_token is None
    assert not verify_password("Password@123",fixture.hashed_password)
    assert session.status=="revoked" and not session.trusted_device and session.session_token_hash!="old-session"
    assert owner.is_active and owner.is_superuser
    assert verify_password("Owner-only-password!",owner.hashed_password)


def test_retirement_refuses_lockout_and_preview_does_not_write(db):
    fixture=User(email="admin@aihrms.com",hashed_password="unchanged",is_superuser=True,is_active=True)
    owner=User(email="safe@example.com",hashed_password="unchanged",is_superuser=True,is_active=True)
    db.add_all([fixture,owner]);db.flush()
    with pytest.raises(RuntimeError): retire(db.connection(),fixture.email,apply=True)
    with pytest.raises(RuntimeError): retire(db.connection(),"missing@example.com",apply=True)
    assert retire(db.connection(),owner.email)["applied"] is False
    db.expire_all()
    assert fixture.is_active and fixture.hashed_password=="unchanged"


def test_bootstrap_cannot_reactivate_fixture_or_disabled_admin(db, monkeypatch):
    owner=User(email="safe@example.com",hashed_password="unchanged",is_superuser=True,is_active=True)
    fixture=User(email="admin@aihrms.com",hashed_password="retired",is_superuser=False,is_active=False)
    db.add_all([owner,fixture]);db.commit()
    monkeypatch.setattr(settings,"BOOTSTRAP_ADMIN_EMAIL",fixture.email)
    init_common_db(db)
    db.refresh(fixture)
    assert not fixture.is_active and not fixture.is_superuser and fixture.hashed_password=="retired"
    monkeypatch.setattr(settings,"BOOTSTRAP_ADMIN_EMAIL",owner.email)
    owner.is_active=False; db.commit()
    init_common_db(db);db.refresh(owner)
    assert owner.is_active is False


def test_production_rejects_even_explicit_demo_seed(db, monkeypatch):
    from app.db.init_db import init_db
    monkeypatch.setattr(settings,"ENVIRONMENT","production")
    monkeypatch.setattr(settings,"SERVERLESS",True)
    with pytest.raises(RuntimeError,match="Demo accounts"):
        init_db(db,seed_demo=True)
