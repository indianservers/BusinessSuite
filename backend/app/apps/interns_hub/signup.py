"""Firebase social identity prefill; account creation remains HRMS-approved."""
import time
from datetime import datetime, timezone

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.deps import get_db
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.user import User
from .models import InternApplication

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


def existing_records(db, email):
    from app.apps.srm.services.commercial import tenant
    organization = settings.INTERN_HUB_ORGANIZATION_ID
    application = db.query(InternApplication).filter(
        func.lower(InternApplication.email) == email.casefold(),
        InternApplication.organization_id == organization).first()
    user = db.query(User).filter(func.lower(User.email) == email.casefold()).first()
    if user and tenant(user) != organization:
        user = None
    return application, user


def eligible_account(application, user):
    from .router import ensure_intern
    if not user or not user.is_active or user.sso_provider_id:
        return False
    if application and (application.status != 'Approved' or application.employee_id != getattr(user.employee, 'id', None)):
        return False
    try:
        ensure_intern(user)
    except HTTPException:
        return False
    return True


def applicant_profile(db, profile):
    application, user = existing_records(db, profile['email'])
    result = dict(profile)
    result['application'] = None
    if application:
        # Return saved form fields, never credentials or government ID numbers.
        safe_fields = {'parent_name', 'mobile', 'mobile_country_code', 'gender', 'date_of_birth',
            'city', 'state', 'tenth_marks', 'twelfth_marks', 'degree', 'current_year', 'college',
            'specialization', 'passout_year', 'area_of_interest', 'skills', 'role', 'mode',
            'available_from', 'duration', 'address', 'pincode', 'linkedin', 'portfolio', 'github',
            'emergency_contact', 'emergency_contact_country_code', 'employment_type', 'department'}
        details = {key: value for key, value in (application.details or {}).items() if key in safe_fields}
        allowed = eligible_account(application, user)
        result['application'] = {'reference': application.reference, 'status': application.status,
            'full_name': application.full_name, 'email': application.email, 'details': details,
            'review_note': application.review_note,
            'intern_id': user.employee.employee_id if allowed else None,
            'can_login': allowed}
    elif user:
        allowed = eligible_account(None, user)
        employee = user.employee if allowed else None
        details = {key: getattr(employee, field, None) for key, field in {
            'mobile':'phone_number', 'mobile_country_code':'phone_number_country_code',
            'city':'present_city', 'state':'present_state', 'address':'present_address',
            'pincode':'present_pincode'}.items()} if employee else {}
        result['application'] = {'status': 'Approved' if allowed else 'Account Exists',
            'email': user.email, 'full_name': ' '.join(filter(None, [employee.first_name, employee.last_name])) if employee else profile['full_name'], 'details': details,
            'intern_id': user.employee.employee_id if allowed else None, 'can_login': allowed}
    return result


@router.get('/session')
def current_applicant(applicant=Depends(require_applicant), db: Session = Depends(get_db)):
    return JSONResponse(applicant_profile(db, applicant), headers={'Cache-Control':'no-store'})


@router.post('/login')
def login_existing_applicant(request: Request, applicant=Depends(require_applicant), db: Session = Depends(get_db)):
    from app.api.v1.auth import (_check_ip_policy, check_lockout, _active_policy_mfa_required,
        _create_mfa_token, _token_response, _log_attempt)
    _check_ip_policy(db, request)
    application, user = existing_records(db, applicant['email'])
    if not eligible_account(application, user):
        raise HTTPException(403, 'Intern access requires an approved, active account')
    if check_lockout(db, user, request):
        raise HTTPException(423, 'Account is temporarily locked; please try again later')
    if user.mfa_enabled or _active_policy_mfa_required(db):
        return {'mfa_required': True, 'mfa_token': _create_mfa_token(user, 'interns_hub'),
            'mfa_methods': ['totp', 'recovery']}
    user.last_login = datetime.now(timezone.utc)
    _log_attempt(db, user, user.email, True, request=request)
    response = _token_response(db, user, request, portal='interns_hub')
    db.commit()
    return response


@router.get('/providers')
def providers():
    project = settings.INTERN_SIGNUP_FIREBASE_PROJECT_ID
    return {'project_id':project, 'providers':[
        {'provider':name,'enabled':bool(project)} for name in ['google']
    ]}


class FirebaseIdentityInput(BaseModel):
    token: str = Field(min_length=20, max_length=16384)


@router.post('/firebase')
def firebase_identity(data: FirebaseIdentityInput, db: Session = Depends(get_db)):
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
    result = applicant_profile(db, {key:profile[key] for key in ['email','full_name','provider']})
    return JSONResponse(result | {'application_token':token,'expires_at':expires_at}, headers={'Cache-Control':'no-store'})
