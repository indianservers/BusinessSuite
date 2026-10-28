from datetime import datetime, timezone, timedelta
from functools import lru_cache
import time

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from app.apps.interns_hub import signup
from app.core import firebase
from app.core.config import settings
from app.models.user import User
from app.apps.interns_hub.models import InternApplication


@pytest.fixture
def firebase_identity(monkeypatch):
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Firebase test')])
    now=datetime.now(timezone.utc)
    certificate=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(private.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).sign(private,hashes.SHA256())
    pem=certificate.public_bytes(serialization.Encoding.PEM).decode()
    @lru_cache(maxsize=2)
    def certificates(bucket):return {'firebase-test':pem}
    monkeypatch.setattr(firebase,'_certificates',certificates)
    monkeypatch.setattr(settings,'INTERN_SIGNUP_FIREBASE_PROJECT_ID','test-project')
    def token(**changes):
        now=int(time.time())
        claims={'iss':'https://securetoken.google.com/test-project','aud':'test-project','sub':'firebase-user',
            'iat':now,'exp':now+3600,'auth_time':now,'firebase':{'sign_in_provider':'google.com'},
            'email':'applicant@gmail.com','email_verified':True,'name':'Applicant Name',**changes}
        return jwt.encode(claims,private,algorithm='RS256',headers={'kid':'firebase-test'})
    return token


def test_firebase_signup_prefills_without_creating_app_accounts(client,db,firebase_identity):
    users=db.query(User).count()
    result=client.post('/api/v1/interns-hub/signup/firebase',json={'token':firebase_identity()})
    assert result.status_code==200,result.text
    profile=result.json()
    assert {key:profile[key] for key in ['email','full_name','provider']}=={'email':'applicant@gmail.com','full_name':'Applicant Name','provider':'google'}
    assert profile['application_token']
    client.headers['X-Intern-Application-Token']=profile['application_token']
    assert client.get('/api/v1/interns-hub/signup/session').status_code==200
    assert 'no-store' in result.headers['cache-control']
    assert db.query(User).count()==users
    assert db.query(InternApplication).count()==0
    providers=client.get('/api/v1/interns-hub/signup/providers').json()
    assert providers=={'project_id':'test-project','providers':[{'provider':'google','enabled':True}]}


@pytest.mark.parametrize('changes',[
    {'aud':'other-project'}, {'iss':'https://attacker.invalid'}, {'exp':1}, {'iat':int(time.time())+3600},
    {'auth_time':int(time.time())+3600}, {'sub':''}, {'sub':'x'*129}, {'email_verified':False},
    {'firebase':{'sign_in_provider':'password'}}, {'firebase':{'sign_in_provider':'microsoft.com'}},
    {'email':'not-an-email'},
])
def test_firebase_signup_rejects_invalid_claims(client,firebase_identity,changes):
    assert client.post('/api/v1/interns-hub/signup/firebase',json={'token':firebase_identity(**changes)}).status_code==401


def test_firebase_signup_rejects_forged_signature(client,firebase_identity):
    claims=jwt.decode(firebase_identity(),options={'verify_signature':False})
    attacker=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    forged=jwt.encode(claims,attacker,algorithm='RS256',headers={'kid':'firebase-test'})
    assert client.post('/api/v1/interns-hub/signup/firebase',json={'token':forged}).status_code==401


def test_unconfigured_firebase_signup_is_unavailable(client,monkeypatch):
    monkeypatch.setattr(settings,'INTERN_SIGNUP_FIREBASE_PROJECT_ID','')
    result=client.get('/api/v1/interns-hub/signup/providers').json()
    assert result['providers']==[{'provider':'google','enabled':False}]
    assert client.post('/api/v1/interns-hub/signup/firebase',json={'token':'invalid-token-with-enough-characters'}).status_code==503


@pytest.mark.parametrize('path,method',[('/application-options','get'),('/applications','post'),('/applications/corrections','post'),('/application-uploads','post'),('/signup/session','get')])
def test_google_login_is_required_for_application_endpoints(client,path,method):
    assert getattr(client,method)('/api/v1/interns-hub'+path).status_code==401


def test_google_application_session_rejects_forgery_expiry_and_other_organization(client,firebase_identity):
    result=client.post('/api/v1/interns-hub/signup/firebase',json={'token':firebase_identity()})
    token=result.json()['application_token']
    claims=jwt.decode(token,options={'verify_signature':False})
    for changes in [{'exp':1},{'organization':2},{'aud':'access'},{'project':'other-project'}]:
        invalid=jwt.encode({**claims,**changes},settings.SECRET_KEY,algorithm=settings.ALGORITHM)
        assert client.get('/api/v1/interns-hub/signup/session',headers={'X-Intern-Application-Token':invalid}).status_code==401
    assert client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+token}).status_code==401
    assert client.get('/api/v1/interns-hub/signup/session',headers={'X-Intern-Application-Token':token+'forged'}).status_code==401


@pytest.fixture
def returning_application(db):
    item = InternApplication(organization_id=settings.INTERN_HUB_ORGANIZATION_ID,
        reference='APP-RETURNING', email='applicant@gmail.com', full_name='Saved Applicant',
        password_hash='private-hash', identity_number_encrypted='private-cipher', identity_last4='1234',
        details={'college':'Saved University','passout_year':2029,'identity_number':'never-expose',
            'password':'never-expose'}, status='Pending')
    db.add(item); db.commit()
    return item


@pytest.mark.parametrize('status', ['Pending', 'Rejected', 'Correction Requested'])
def test_returning_applicant_sees_saved_status_without_new_record(client, db, firebase_identity, returning_application, status):
    returning_application.status = status
    db.commit()
    result = client.post('/api/v1/interns-hub/signup/firebase', json={'token':firebase_identity()})
    assert result.status_code == 200, result.text
    saved = result.json()['application']
    assert saved['status'] == status and saved['full_name'] == 'Saved Applicant'
    assert saved['details'] == {'college':'Saved University', 'passout_year':2029}
    assert not saved['can_login'] and 'private-hash' not in result.text and 'never-expose' not in result.text
    headers = {'X-Intern-Application-Token':result.json()['application_token']}
    assert client.get('/api/v1/interns-hub/signup/session', headers=headers).json()['application'] == saved
    assert client.post('/api/v1/interns-hub/signup/login', headers=headers).status_code == 403
    assert db.query(InternApplication).count() == 1 and db.query(User).count() == 0


@pytest.fixture
def approved_applicant(db, returning_application):
    from app.models.user import Role
    from app.models.employee import Employee
    from app.core.security import get_password_hash
    from app.models.company import Company, Branch
    company = db.get(Company, settings.INTERN_HUB_ORGANIZATION_ID) or Company(id=settings.INTERN_HUB_ORGANIZATION_ID, name='Intern Company')
    db.add(company); db.flush()
    branch = Branch(name='Intern HQ', company_id=company.id)
    db.add(branch); db.flush()
    role = Role(name='intern', is_system=True)
    db.add(role); db.flush()
    user = User(email='applicant@gmail.com', hashed_password=get_password_hash('Applicant@123456'),
        role_id=role.id, is_active=True)
    db.add(user); db.flush()
    employee = Employee(employee_id='IH-EXISTING', first_name='Saved', last_name='Applicant',
        user_id=user.id, branch_id=branch.id, employment_type='Intern', status='Active', date_of_joining=datetime.now().date())
    db.add(employee); db.flush()
    returning_application.employee_id = employee.id
    returning_application.status = 'Approved'
    db.commit()
    return user


def test_approved_google_applicant_signs_into_existing_restricted_dashboard(client, db, firebase_identity, approved_applicant):
    from app.core.security import verify_access_token
    from app.models.employee import Employee
    before = {model.__name__: db.query(model).count() for model in (User, InternApplication, Employee)}
    employee_id = approved_applicant.employee.id
    application_id = db.query(InternApplication).one().id
    for _ in range(3):
        result = client.post('/api/v1/interns-hub/signup/firebase', json={'token':firebase_identity()})
        assert result.status_code == 200, result.text
        assert result.json()['application']['intern_id'] == 'IH-EXISTING'
        headers = {'X-Intern-Application-Token':result.json()['application_token']}
        login = client.post('/api/v1/interns-hub/signup/login', headers=headers)
        assert login.status_code == 200, login.text
        assert login.json()['user_id'] == approved_applicant.id
        access = login.json()['access_token']
        assert verify_access_token(access)['portal'] == 'interns_hub'
        dashboard_headers = {'Authorization':'Bearer '+access}
        dashboard = client.get('/api/v1/interns-hub/me', headers=dashboard_headers)
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()['employee_id'] == 'IH-EXISTING'
        overview = client.get('/api/v1/interns-hub/overview', headers=dashboard_headers)
        assert overview.status_code == 200, overview.text
        assert db.query(InternApplication).one().id == application_id
        assert approved_applicant.employee.id == employee_id
        after = {model.__name__: db.query(model).count() for model in (User, InternApplication, Employee)}
        assert after == before
    print(f'Approved intern IH-EXISTING: three signup/login attempts; record counts before={before}, after={after}')


def test_approved_google_login_preserves_mfa(client, firebase_identity, approved_applicant, db):
    approved_applicant.mfa_enabled = True
    db.commit()
    result = client.post('/api/v1/interns-hub/signup/firebase', json={'token':firebase_identity()}).json()
    login = client.post('/api/v1/interns-hub/signup/login', headers={'X-Intern-Application-Token':result['application_token']})
    assert login.status_code == 200 and login.json()['mfa_required']
    assert 'access_token' not in login.json()
    assert jwt.decode(login.json()['mfa_token'], options={'verify_signature':False})['module'] == 'interns_hub'


@pytest.mark.parametrize('change', ['inactive', 'former_intern', 'other_organization', 'unapproved', 'sso', 'mismatched_employee'])
def test_google_signup_cannot_grant_ineligible_access(client, db, firebase_identity, approved_applicant, returning_application, change):
    if change == 'inactive': approved_applicant.is_active = False
    if change == 'former_intern': approved_applicant.employee.status = 'Terminated'
    if change == 'other_organization': returning_application.organization_id = 2
    if change == 'unapproved': returning_application.status = 'Pending'
    if change == 'sso': approved_applicant.sso_provider_id = 1
    if change == 'mismatched_employee': returning_application.employee_id = None
    # Model an account explicitly belonging to another organization.
    if change == 'other_organization':
        from app.models.company import Company, Branch
        company = Company(id=settings.INTERN_HUB_ORGANIZATION_ID + 10, name='Other company'); db.add(company); db.flush()
        branch = Branch(name='Other branch', company_id=company.id); db.add(branch); db.flush()
        approved_applicant.employee.branch_id = branch.id
        approved_applicant.employee.branch = branch
    db.commit()
    result = client.post('/api/v1/interns-hub/signup/firebase', json={'token':firebase_identity()}).json()
    assert not (result['application'] or {}).get('can_login')
    assert client.post('/api/v1/interns-hub/signup/login', headers={'X-Intern-Application-Token':result['application_token']}).status_code == 403


def test_google_login_requires_verified_application_identity(client):
    assert client.post('/api/v1/interns-hub/signup/login').status_code == 401


def test_returning_applicant_recognizes_mixed_case_email(client, db, firebase_identity, returning_application):
    returning_application.email = 'Applicant@Gmail.com'
    db.commit()
    result = client.post('/api/v1/interns-hub/signup/firebase', json={'token': firebase_identity()})
    assert result.status_code == 200
    assert result.json()['application']['reference'] == returning_application.reference


def test_existing_intern_without_application_reuses_current_account(client, db, firebase_identity, approved_applicant, returning_application):
    db.delete(returning_application); db.commit()
    result = client.post('/api/v1/interns-hub/signup/firebase', json={'token':firebase_identity()}).json()
    assert result['application']['intern_id'] == 'IH-EXISTING'
    assert result['application']['full_name'] == 'Saved Applicant'
    login = client.post('/api/v1/interns-hub/signup/login', headers={'X-Intern-Application-Token':result['application_token']})
    assert login.status_code == 200, login.text
    assert db.query(User).count() == 1 and db.query(InternApplication).count() == 0
