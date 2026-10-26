"""Firebase social identity prefill; account creation remains HRMS-approved."""
import time
from functools import lru_cache

import httpx
import jwt
from cryptography import x509
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, TypeAdapter
from app.core.config import settings

router = APIRouter(prefix='/signup', tags=['Intern signup'])
CERT_URL = 'https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com'


@lru_cache(maxsize=2)
def _certificates(bucket):
    # Short cache bounds key rotation while avoiding a Google request per signup.
    response = httpx.get(CERT_URL, timeout=15)
    response.raise_for_status()
    return response.json()


def verify_firebase_identity(token):
    project = settings.INTERN_SIGNUP_FIREBASE_PROJECT_ID
    if not project:
        raise HTTPException(503, 'Google sign-in is not configured yet')
    header = jwt.get_unverified_header(token)
    if header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str):
        raise ValueError('Unexpected identity signing key')
    certificates = _certificates(int(time.monotonic() // 300))
    certificate = certificates.get(header['kid'])
    if not certificate:
        raise ValueError('Unknown Firebase signing key')
    key = x509.load_pem_x509_certificate(certificate.encode()).public_key()
    claims = jwt.decode(token, key, algorithms=['RS256'], audience=project,
        issuer=f'https://securetoken.google.com/{project}',
        options={'require':['exp','iat','auth_time','sub','aud','iss']})
    if (not isinstance(claims['sub'], str) or not 1 <= len(claims['sub']) <= 128
            or type(claims['auth_time']) is not int or claims['auth_time'] > time.time()):
        raise ValueError('Invalid Firebase subject or authentication time')
    provider = claims.get('firebase', {}).get('sign_in_provider')
    if provider not in {'google.com'}:
        raise ValueError('Unsupported signup identity provider')
    if provider == 'google.com' and claims.get('email_verified') is not True:
        raise ValueError('Google email must be verified')
    email = str(TypeAdapter(EmailStr).validate_python(claims.get('email')))
    if len(email) > 150:
        raise ValueError('Email exceeds application limit')
    name = claims.get('name') or ''
    if not isinstance(name, str):
        raise ValueError('Invalid display name')
    return {'email':email, 'full_name':name.strip()[:160], 'provider':'google', 'subject':claims['sub']}


def applicant_session(profile, expires_at=None):
    return jwt.encode({'sub':profile['subject'], 'email':profile['email'], 'full_name':profile['full_name'],
        'provider':'google', 'project':settings.INTERN_SIGNUP_FIREBASE_PROJECT_ID,
        'organization':settings.INTERN_HUB_ORGANIZATION_ID, 'aud':'intern-application',
        'iss':'interns-hub-signup', 'exp':expires_at or int(time.time())+7200},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def require_applicant(request: Request):
    try:
        claims = jwt.decode(request.headers.get('X-Intern-Application-Token', ''), settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM], audience='intern-application', issuer='interns-hub-signup',
            options={'require':['exp','sub','email','full_name','provider','project','organization']})
        if (claims['provider'] != 'google' or not settings.INTERN_SIGNUP_FIREBASE_PROJECT_ID
                or claims['project'] != settings.INTERN_SIGNUP_FIREBASE_PROJECT_ID
                or claims['organization'] != settings.INTERN_HUB_ORGANIZATION_ID):
            raise ValueError('Invalid application identity')
        return {key:claims[key] for key in ['email','full_name','provider','sub']} | {'expires_at':claims['exp']}
    except Exception:
        raise HTTPException(401, 'Sign in with Google to continue your application') from None


@router.get('/session')
def current_applicant(applicant=Depends(require_applicant)):
    return JSONResponse(applicant, headers={'Cache-Control':'no-store'})


@router.get('/providers')
def providers():
    project = settings.INTERN_SIGNUP_FIREBASE_PROJECT_ID
    return {'project_id':project, 'providers':[
        {'provider':name,'enabled':bool(project)} for name in ['google']
    ]}


class FirebaseIdentityInput(BaseModel):
    token: str = Field(min_length=20, max_length=16384)


@router.post('/firebase')
def firebase_identity(data: FirebaseIdentityInput):
    try:
        profile = verify_firebase_identity(data.token)
    except HTTPException:
        raise
    except httpx.HTTPError:
        raise HTTPException(503, 'Social verification is temporarily unavailable; please try again') from None
    except Exception:
        raise HTTPException(401, 'Social identity could not be verified; please sign up again') from None
    # This purpose-bound session cannot authenticate to employee or intern APIs.
    expires_at = int(time.time())+7200
    token = applicant_session(profile, expires_at)
    return JSONResponse({key:profile[key] for key in ['email','full_name','provider']} | {'application_token':token,'expires_at':expires_at}, headers={'Cache-Control':'no-store'})
