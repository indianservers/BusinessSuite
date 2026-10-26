import pytest
from fastapi import HTTPException
from app.core.config import settings
from app.api.v1 import auth
from app.models.user import User, Role
from tests.test_intern_signup_settings import firebase_identity


@pytest.fixture(autouse=True)
def firebase_config(monkeypatch):
    monkeypatch.setattr(settings,'FIREBASE_PROJECT_ID','test-project')
    monkeypatch.setattr(settings,'FIREBASE_WEB_CONFIG',{'apiKey':'public-test','authDomain':'test-project.firebaseapp.com','projectId':'test-project','appId':'public-app'})


@pytest.fixture
def pms_account(db):
    role=Role(name='pms_team_member',is_system=True)
    db.add(role);db.flush()
    user=User(email='pms-user@example.com',hashed_password='',is_active=True,role_id=role.id)
    db.add(user);db.commit()
    return user


def login(client,token,**extra):
    return client.post('/api/v1/auth/firebase/login',json={'token':token,'module':'project_management',**extra})


def test_existing_pms_user_can_login_with_google(client,db,pms_account,firebase_identity):
    before=db.query(User).count()
    result=login(client,firebase_identity(email=pms_account.email))
    assert result.status_code==200,result.text
    assert result.json()['email']==pms_account.email
    assert result.json()['access_token'] and result.json()['refresh_token']
    assert db.query(User).count()==before
    assert client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+result.json()['access_token']}).status_code==200


def test_google_does_not_provision_unknown_accounts(client,db,firebase_identity):
    before=db.query(User).count()
    assert login(client,firebase_identity(email='unregistered@example.com')).status_code==403
    assert db.query(User).count()==before


def test_global_super_admin_google_login(client,superuser_headers,firebase_identity):
    response=login(client,firebase_identity(email='testadmin@test.com'))
    assert response.status_code==200,response.text
    assert response.json()['is_superuser'] is True


def test_google_cannot_bypass_mfa(client,db,pms_account,firebase_identity):
    pms_account.mfa_enabled=True;db.commit()
    result=login(client,firebase_identity(email=pms_account.email))
    assert result.status_code==200,result.text
    assert result.json()['mfa_required'] and result.json()['mfa_token']
    assert 'access_token' not in result.json()


def test_google_respects_lockouts(client,pms_account,firebase_identity,monkeypatch):
    monkeypatch.setattr(auth,'check_lockout',lambda db,user:{'attempts':5})
    assert login(client,firebase_identity(email=pms_account.email)).status_code==423


def test_google_respects_ip_policy(client,firebase_identity,monkeypatch):
    def blocked(*args):raise HTTPException(403,'IP policy blocked')
    monkeypatch.setattr(auth,'_check_ip_policy',blocked)
    assert login(client,firebase_identity()).status_code==403


@pytest.mark.parametrize('status',['inactive','unauthorized_role','intern'])
def test_google_preserves_existing_access_rules(client,db,pms_account,firebase_identity,status):
    if status=='inactive':pms_account.is_active=False
    else:
        role=Role(name='employee' if status=='unauthorized_role' else 'intern')
        db.add(role);db.flush();pms_account.role_id=role.id
    db.commit()
    assert login(client,firebase_identity(email=pms_account.email)).status_code==403


def test_firebase_config_exposes_only_public_web_fields(client,monkeypatch):
    monkeypatch.setattr(settings,'FIREBASE_WEB_CONFIG',{**settings.FIREBASE_WEB_CONFIG,'private_key':'never-expose'})
    response=client.get('/api/v1/auth/firebase/config')
    assert response.status_code==200 and response.json()['enabled']
    assert 'private_key' not in response.text and 'never-expose' not in response.text


def test_incorrect_firebase_project_is_disabled(client,monkeypatch):
    monkeypatch.setattr(settings,'FIREBASE_PROJECT_ID','wrong-project')
    assert client.get('/api/v1/auth/firebase/config').json()['enabled'] is False
    assert login(client,'invalid-token-with-enough-characters').status_code==503


def test_firebase_login_requires_google_and_expected_module(client,firebase_identity):
    assert login(client,firebase_identity(firebase={'sign_in_provider':'microsoft.com'})).status_code==401
    assert login(client,firebase_identity(),module='interns_hub').status_code==422
