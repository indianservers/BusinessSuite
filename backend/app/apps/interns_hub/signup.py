"""Firebase social identity prefill; account creation remains HRMS-approved."""
import time

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from app.core.config import settings

router = APIRouter(prefix='/signup', tags=['Intern signup'])
def verify_firebase_identity(token):
    from app.core.firebase import verify_google_identity
    profile = verify_google_identity(token, settings.INTERN_SIGNUP_FIREBASE_PROJECT_ID)
    if len(profile['email']) > 150:
        raise ValueError('Email exceeds application limit')
    return profile


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
