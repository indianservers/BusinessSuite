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
    monkeypatch.setattr(signup,'_certificates',certificates)
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
    assert result.json()=={'email':'applicant@gmail.com','full_name':'Applicant Name','provider':'google'}
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
