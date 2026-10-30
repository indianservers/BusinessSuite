from datetime import date, datetime, timedelta, timezone
import secrets
import hashlib
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, RedirectResponse
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_current_active_superuser, get_db
from app.models.employee import Employee
from app.models.sso import SSOProvider, SSOSession
from app.models.user import User
from app.services.sso_service import (
    exchange_oidc_code,
    extract_user_attributes,
    generate_pkce_pair,
    get_oidc_authorization_url,
)


router = APIRouter(prefix="/auth/sso", tags=["SSO"])


def _public_provider(provider: SSOProvider) -> dict:
    return {
        "id": provider.id,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "button_label": provider.button_label,
        "button_icon": provider.button_icon,
        "domain_hint": provider.domain_hint,
    }


def _admin_provider(provider: SSOProvider) -> dict:
    data = {column.name: getattr(provider, column.name) for column in provider.__table__.columns}
    if data.get("client_secret"):
        data["client_secret"] = "***"
    return data


def _safe_relay_state(next_url: str | None) -> str:
    value = next_url or "/dashboard"
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/"):
        return "/dashboard"
    return value


def _validate_provider_config(data: dict) -> None:
    provider_type = str(data.get("provider_type") or "").lower()
    if provider_type == "google":
        endpoints = {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth", "token_url": "https://oauth2.googleapis.com/token", "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo"}
        for key, expected in endpoints.items():
            data.setdefault(key, expected)
            if data[key] != expected:
                raise HTTPException(400, "Google Workspace must use Google's official identity endpoints")
        if not data.get("domain_hint"):
            raise HTTPException(400, "Google Workspace requires an allowed email domain")
    if provider_type not in {"google", "microsoft", "okta", "azure_ad", "custom_oidc", "saml"}:
        raise HTTPException(status_code=400, detail="Unsupported SSO provider type")
    domain_hint = (data.get("domain_hint") or "").strip()
    if domain_hint and ("@" in domain_hint or "/" in domain_hint):
        raise HTTPException(status_code=400, detail="Domain hint must be a bare email domain")
    if provider_type == "saml":
        required = ["idp_entity_id", "idp_sso_url", "idp_x509_cert"]
    else:
        required = ["client_id", "client_secret", "authorization_url", "token_url", "userinfo_url"]
    missing = [key for key in required if not data.get(key) or data.get(key) == "***"]
    if missing:
        raise HTTPException(status_code=400, detail={"message": "SSO provider configuration is incomplete", "missing": missing})
    for key in ["authorization_url", "token_url", "userinfo_url", "idp_sso_url"]:
        value = data.get(key)
        if value:
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise HTTPException(status_code=400, detail=f"{key} must be an HTTPS URL")
    if provider_type == "saml" and "BEGIN CERTIFICATE" not in str(data.get("idp_x509_cert", "")):
        raise HTTPException(status_code=400, detail="SAML IdP certificate must be PEM formatted")


def _domain_allowed(provider: SSOProvider, email: str) -> bool:
    domain_hint = (provider.domain_hint or "").strip().lower()
    if not domain_hint:
        return True
    return email.lower().endswith(f"@{domain_hint}")


def _requires_step_up(db: Session, provider: SSOProvider, user: User | None) -> bool:
    from app.api.v1.auth import _active_policy_mfa_required, _active_totp
    return bool(provider.force_mfa or _active_policy_mfa_required(db) or (user and _active_totp(db, user.id)))


@router.get("/providers/active")
def active_sso_providers(db: Session = Depends(get_db)):
    """Return active SSO providers safe for the login page."""
    providers = db.query(SSOProvider).filter(SSOProvider.is_active == True).order_by(SSOProvider.is_default.desc(), SSOProvider.name).all()
    return [_public_provider(provider) for provider in providers]


@router.get("/initiate/{provider_id}")
async def initiate_sso(provider_id: int, next: str = Query("/dashboard"), db: Session = Depends(get_db)):
    """Start an OIDC SSO login by creating a stateful short-lived session."""
    provider = db.query(SSOProvider).filter(SSOProvider.id == provider_id, SSOProvider.is_active == True).first()
    if not provider:
        raise HTTPException(status_code=404, detail="SSO provider not found")
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
    session = SSOSession(
        provider_id=provider.id,
        state=state,
        nonce=nonce,
        code_verifier=verifier,
        relay_state=_safe_relay_state(next),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(session)
    db.commit()
    if provider.provider_type.lower() == "saml":
        return {"error": "SAML not yet implemented", "provider": provider.name}
    url = await get_oidc_authorization_url(provider, state, nonce, challenge)
    response = RedirectResponse(url, status_code=302)
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(f"sso_state_{provider.id}", state, max_age=600, httponly=True,
        secure=settings.ENVIRONMENT == "production", samesite="lax", path="/api/v1/auth/sso")
    return response


@router.get("/callback/oidc/{provider_id}")
async def oidc_callback(provider_id: int, request: Request, code: str | None = None, state: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    """Handle an OIDC callback, provision the user if allowed, and redirect to the frontend."""
    frontend = settings.FRONTEND_PUBLIC_URL.rstrip("/")
    if error:
        return RedirectResponse(f"{frontend}/login?sso_error={error}")
    browser_state = request.cookies.get(f"sso_state_{provider_id}")
    if not state or not browser_state or not secrets.compare_digest(state, browser_state):
        return RedirectResponse(f"{frontend}/login?sso_error=invalid_state")
    provider = db.query(SSOProvider).filter(SSOProvider.id == provider_id, SSOProvider.is_active == True).first()
    session = db.query(SSOSession).filter(SSOSession.state == state, SSOSession.provider_id == provider_id).with_for_update().first()
    if not provider or not session or session.completed or not code or not state:
        return RedirectResponse(f"{frontend}/login?sso_error=invalid_state")
    expires_at = session.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        return RedirectResponse(f"{frontend}/login?sso_error=invalid_state")
    try:
        userinfo = await exchange_oidc_code(provider, code, state, session.code_verifier, nonce=session.nonce)
        attrs = extract_user_attributes(userinfo, provider)
        if not attrs.get("email"):
            return RedirectResponse(f"{frontend}/login?sso_error=email_missing")
        if not _domain_allowed(provider, attrs["email"]):
            return RedirectResponse(f"{frontend}/login?sso_error=domain_not_allowed")
        user = db.query(User).filter(User.email == attrs["email"]).first()
        if user and not user.is_active:
            from app.apps.project_management.people_management import restore_due_suspension
            restore_due_suspension(db, user)
        if user and not user.is_active:
            return RedirectResponse(f"{frontend}/login?sso_error=account_disabled")
        from app.api.v1.auth import _check_ip_policy
        _check_ip_policy(db, request)
        if _requires_step_up(db, provider, user):
            return RedirectResponse(f"{frontend}/login?sso_error=mfa_required")
        if not user:
            if not provider.auto_provision:
                return RedirectResponse(f"{frontend}/login?sso_error=user_not_found")
            user = User(email=attrs["email"], hashed_password="", is_active=True, sso_provider_id=provider.id, role_id=provider.default_role_id)
            db.add(user)
            db.flush()
            employee_id = f"SSO{user.id:06d}"
            db.add(Employee(
                employee_id=employee_id,
                first_name=attrs["first_name"] or attrs["email"].split("@")[0],
                last_name=attrs["last_name"] or "-",
                date_of_joining=date.today(),
                personal_email=attrs["email"],
                user_id=user.id,
            ))
        session.completed = True
        session.user_id = user.id
        handoff = secrets.token_urlsafe(32)
        session.code_verifier = hashlib.sha256(handoff.encode()).hexdigest()
        session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=1)
        db.commit()
        response = RedirectResponse(f"{frontend}{session.relay_state}#sso_code={handoff}&provider={provider.id}")
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception:
        db.rollback()
        return RedirectResponse(f"{frontend}/login?sso_error=exchange_failed")


@router.post("/complete/{provider_id}")
def complete_sso(provider_id: int, data: dict, request: Request, db: Session = Depends(get_db)):
    """Exchange a single-use, browser-bound handoff without putting JWTs in URLs."""
    from app.api.v1.auth import _token_response, _check_ip_policy
    state = request.cookies.get(f"sso_state_{provider_id}")
    code = data.get("code")
    if not state or not isinstance(code, str) or not 20 <= len(code) <= 200:
        raise HTTPException(401, "Invalid or expired SSO handoff")
    session = db.query(SSOSession).filter_by(provider_id=provider_id, state=state, completed=True).with_for_update().first()
    expiry = session.expires_at if session else None
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if not session or not expiry or expiry <= datetime.now(timezone.utc) or not session.code_verifier or not secrets.compare_digest(session.code_verifier, hashlib.sha256(code.encode()).hexdigest()):
        raise HTTPException(401, "Invalid or expired SSO handoff")
    user = db.get(User, session.user_id)
    provider = db.get(SSOProvider, provider_id)
    if not user or not user.is_active or not provider or not provider.is_active:
        raise HTTPException(401, "SSO account or provider is disabled")
    _check_ip_policy(db, request)
    if _requires_step_up(db, provider, user):
        raise HTTPException(403, "Use password login to complete the required MFA challenge")
    session.code_verifier = None
    tokens = _token_response(db, user, request)
    db.commit()
    from fastapi.responses import JSONResponse
    response = JSONResponse(tokens.model_dump(mode="json"))
    response.delete_cookie(f"sso_state_{provider_id}", path="/api/v1/auth/sso")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/providers")
def list_sso_providers(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_superuser)):
    """List all SSO providers for administrators."""
    return [_admin_provider(provider) for provider in db.query(SSOProvider).order_by(SSOProvider.id.desc()).all()]


@router.post("/providers", status_code=201)
def create_sso_provider(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_superuser)):
    """Create an SSO provider configuration."""
    _validate_provider_config(data)
    if data.get("is_default"):
        db.query(SSOProvider).update({SSOProvider.is_default: False})
    provider = SSOProvider(**data)
    try:
        db.add(provider)
        db.commit()
        db.refresh(provider)
    except Exception:
        db.rollback()
        raise
    return _admin_provider(provider)


@router.put("/providers/{provider_id}")
def update_sso_provider(provider_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_superuser)):
    """Update an SSO provider; masked secrets are preserved."""
    provider = db.query(SSOProvider).filter(SSOProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="SSO provider not found")
    try:
        merged = {column.name: getattr(provider, column.name) for column in provider.__table__.columns}
        merged.update({key: value for key, value in data.items() if not (key == "client_secret" and value == "***")})
        _validate_provider_config(merged)
        if data.get("is_default"):
            db.query(SSOProvider).filter(SSOProvider.id != provider_id).update({SSOProvider.is_default: False})
        for key, value in data.items():
            if key == "client_secret" and value == "***":
                continue
            if hasattr(provider, key):
                setattr(provider, key, value)
        db.commit()
        db.refresh(provider)
    except Exception:
        db.rollback()
        raise
    return _admin_provider(provider)


@router.delete("/providers/{provider_id}")
def delete_sso_provider(provider_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_superuser)):
    """Soft-delete an SSO provider by disabling it."""
    provider = db.query(SSOProvider).filter(SSOProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="SSO provider not found")
    provider.is_active = False
    db.commit()
    return {"deleted": True}


@router.get("/providers/{provider_id}/test")
async def test_sso_provider(provider_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_superuser)):
    """Check whether configured OIDC endpoint URLs respond."""
    provider = db.query(SSOProvider).filter(SSOProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="SSO provider not found")
    results = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for key in ["authorization_url", "token_url", "userinfo_url"]:
            url = getattr(provider, key)
            if not url:
                results[f"{key}_reachable"] = False
                continue
            try:
                response = await client.get(url)
                results[f"{key}_reachable"] = response.status_code < 500 and response.status_code != 404
            except Exception:
                results[f"{key}_reachable"] = False
    overall = "ok" if all(results.values()) else "warning" if any(results.values()) else "error"
    return {**results, "overall": overall}


@router.get("/providers/{provider_id}/sp-metadata")
def sp_metadata(provider_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_superuser)):
    """Return minimal SAML SP metadata XML for a provider."""
    provider = db.query(SSOProvider).filter(SSOProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="SSO provider not found")
    entity_id = provider.sp_entity_id or f"{settings.BACKEND_PUBLIC_URL}/saml/{provider.id}"
    acs = f"{settings.BACKEND_PUBLIC_URL}/api/v1/auth/sso/callback/saml/{provider.id}"
    cert = provider.sp_certificate or ""
    xml = f"""<?xml version="1.0"?>
<EntityDescriptor entityID="{entity_id}" xmlns="urn:oasis:names:tc:SAML:2.0:metadata">
  <SPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <KeyDescriptor use="signing"><KeyInfo xmlns="http://www.w3.org/2000/09/xmldsig#"><X509Data><X509Certificate>{cert}</X509Certificate></X509Data></KeyInfo></KeyDescriptor>
    <AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="{acs}" index="1" />
  </SPSSODescriptor>
</EntityDescriptor>"""
    return Response(content=xml, media_type="application/xml")
