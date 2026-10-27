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
    monkeypatch.setattr(auth,'check_lockout',lambda db,user,request=None:{'attempts':5})
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


MODULE_ROLES = [("hrms", "employee"), ("crm", "crm_viewer"), ("project_management", "pms_viewer"), ("srm", "srm_viewer"), ("fam", "fam_viewer")]

@pytest.mark.parametrize("module,role_name", MODULE_ROLES)
def test_google_login_for_every_module_preserves_module_access(client, db, firebase_identity, module, role_name):
    role = Role(name=role_name, is_system=True)
    db.add(role); db.flush()
    user = User(email=f"google-{module}@example.com", hashed_password="", is_active=True, role_id=role.id)
    db.add(user); db.commit()
    token = firebase_identity(email=user.email)
    result = login(client, token, module=module)
    assert result.status_code == 200, result.text
    assert result.json()["email"] == user.email and result.json()["access_token"]
    other = "crm" if module != "crm" else "hrms"
    assert login(client, token, module=other).status_code == 403
    user.is_active = False; db.commit()
    assert login(client, token, module=module).status_code == 403

@pytest.mark.parametrize("module,_", MODULE_ROLES)
def test_super_admin_google_login_and_mfa_for_every_module(client, db, superuser_headers, firebase_identity, module, _):
    user = db.query(User).filter_by(email="testadmin@test.com").one()
    token = firebase_identity(email=user.email)
    assert login(client, token, module=module).status_code == 200
    user.mfa_enabled = True; db.commit()
    response = login(client, token, module=module)
    assert response.status_code == 200 and response.json()["mfa_required"]
    assert auth._decode_mfa_token(response.json()["mfa_token"])["module"] == module
    assert "access_token" not in response.json()

def test_google_config_and_login_respect_installed_modules(client, firebase_identity, monkeypatch):
    monkeypatch.setattr(settings,"INSTALLED_APPS",["hrms"])
    assert client.get("/api/v1/auth/firebase/config").json()["modules"] == ["hrms"]
    assert login(client,firebase_identity(),module="crm").status_code == 403


@pytest.mark.parametrize("module,role_name", MODULE_ROLES)
def test_microsoft_login_preserves_module_access(client, db, firebase_identity, module, role_name):
    role = Role(name=role_name, is_system=True)
    db.add(role); db.flush()
    user = User(email=f"microsoft-{module}@example.com", hashed_password="", is_active=True, role_id=role.id)
    db.add(user); db.commit()
    token = firebase_identity(email=user.email, firebase={"sign_in_provider": "microsoft.com"})
    result = login(client, token, module=module, provider="microsoft")
    assert result.status_code == 200, result.text
    assert result.json()["email"] == user.email and result.json()["access_token"]
    assert login(client, token, module=module).status_code == 401
    other = "crm" if module != "crm" else "hrms"
    assert login(client, token, module=other, provider="microsoft").status_code == 403
    user.mfa_enabled = True; db.commit()
    result = login(client, token, module=module, provider="microsoft")
    assert result.json()["mfa_required"] and "access_token" not in result.json()


def test_microsoft_rejects_unverified_email(client, firebase_identity):
    token = firebase_identity(email_verified=False, firebase={"sign_in_provider": "microsoft.com"})
    assert login(client, token, provider="microsoft").status_code == 401


def test_suite_google_login_without_module(client, pms_account, firebase_identity):
    response = client.post('/api/v1/auth/firebase/login', json={'token': firebase_identity(email=pms_account.email)})
    assert response.status_code == 200, response.text
    assert response.json()['email'] == pms_account.email
