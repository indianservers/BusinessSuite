from datetime import datetime, timedelta, timezone
import jwt
import secrets
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import security, token_record_id
from app.core.security import get_password_hash, verify_password
from app.platform_owner.models import PlatformAdmin, PlatformSession, PlatformRecord
from app.platform_owner import service as svc
from app.platform_owner.session import get_platform_db

ISSUER = "indian-servers-platform"
AUDIENCE = "platform-owner"


class PlatformLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


def validate_platform_bearer(raw: str):
    """Reject missing/wrong-realm credentials before owner storage is opened."""
    if raw.startswith("po_"):
        import re
        if re.fullmatch(r"po_[A-Za-z0-9_-]{32,128}", raw):
            return
        raise HTTPException(401, "Indian Servers platform owner sign-in required")
    try:
        jwt.decode(raw, settings.PLATFORM_SECRET_KEY, algorithms=["HS256"], issuer=ISSUER, audience=AUDIENCE,
            options={"require": ["exp", "sub", "iss", "aud", "version", "sid"]})
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, "Indian Servers platform owner sign-in required") from None


def current_platform_admin(request: Request, credentials=Depends(security), db: Session = Depends(get_platform_db)):
    raw = credentials.credentials if credentials else ""
    if raw.startswith("po_"):
        key = db.query(PlatformRecord).filter_by(kind="api_key", token_hash=svc.digest(raw), state="active").first()
        if not key or not key.expires_at or svc.aware(key.expires_at) <= svc.now():
            raise HTTPException(401, "Expired or invalid platform API key")
        admin = db.get(PlatformAdmin, key.owner_id)
        if not admin or not admin.is_active:
            raise HTTPException(401, "Inactive platform staff account")
        import re
        path = request.url.path.removeprefix("/api/v1")
        required = None
        if request.method == "GET" and path in {"/platform/reports", "/platform/report-export"}: required = "reports.read"
        elif request.method == "GET" and re.fullmatch(r"/platform/signups(?:/\d+)?", path): required = "signup.read"
        elif request.method == "GET" and path == "/auth/signup-requests": required = "signup.read"
        elif request.method == "POST" and path == "/platform/signups": required = "signup.create"
        elif request.method == "GET" and re.fullmatch(r"/platform/customers(?:/\d+)?", path): required = "tenant.read"
        if not required or required not in key.data.get("scopes", []):
            raise HTTPException(403, "This API key does not allow this endpoint")
        admin._api_scopes = set(key.data.get("scopes", []))
        admin._platform_session = None
        db.info["platform_actor"] = admin
        return admin
    try:
        payload = jwt.decode(raw, settings.PLATFORM_SECRET_KEY, algorithms=["HS256"], issuer=ISSUER, audience=AUDIENCE,
            options={"require": ["exp", "sub", "iss", "aud", "version", "sid"]})
        admin = db.get(PlatformAdmin, token_record_id(payload["sub"]))
        session = db.get(PlatformSession, payload["sid"])
        idle = svc.settings_for(db)["idle_minutes"]
        if not admin or not admin.is_active or payload["version"] != admin.token_version or not session or session.admin_id != admin.id or session.status != "active" or svc.aware(session.expires_at) <= svc.now() or svc.aware(session.last_seen_at) + timedelta(minutes=idle) <= svc.now():
            raise ValueError("Inactive platform session")
        admin._platform_session = session.id
        admin._api_scopes = None
        db.info["platform_actor"] = admin
        if svc.aware(session.last_seen_at) < svc.now()-timedelta(minutes=1):
            session.last_seen_at = svc.now(); db.commit()
    except (jwt.PyJWTError, ValueError, HTTPException):
        raise HTTPException(401, "Indian Servers platform owner sign-in required") from None
    if admin.role=='model_trainer':
        path=request.url.path.removeprefix('/api/v1')
        if not (path=='/platform/me' or path=='/platform/nlp-training' or path.startswith('/platform/nlp-training/') or path=='/platform/sessions/revoke'):
            raise HTTPException(403,'This platform account has access only to NLP training')
    return admin


def session_result(admin, request, db):
    from app.core.middleware.audit import client_addresses
    ip = str(client_addresses(request)[0] or "unknown")
    device = request.headers.get("user-agent", "Unknown device")[:300]
    known = db.query(PlatformSession).filter_by(admin_id=admin.id, device=device).first()
    ident = secrets.token_hex(24)
    expires = svc.now()+timedelta(hours=8)
    db.add(PlatformSession(id=ident, admin_id=admin.id, ip=ip, device=device, last_seen_at=svc.now(), expires_at=expires))
    svc.event(db, admin, "login.success", "session", reason=ip, after={"device":device})
    if not known:
        svc.notify(db, "New platform sign-in", f"A new device signed in from {ip}.", owner_id=admin.id)
    db.commit()
    token = jwt.encode({"sub": str(admin.id), "exp": expires, "iss": ISSUER, "aud": AUDIENCE,
                        "version": admin.token_version, "sid": ident}, settings.PLATFORM_SECRET_KEY, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "email": admin.email, "role": admin.role,
            "permissions": sorted(svc.permissions(admin)), "idle_minutes": svc.settings_for(db)["idle_minutes"]}


def login(data: PlatformLogin, request: Request, db: Session):
    from app.core.request_limits import consume
    from app.core.middleware.audit import client_addresses
    email = str(data.email).strip().lower()
    retry = consume(db, [("platform-login-ip:" + str(client_addresses(request)[0]), 20, 900),
                         ("platform-login-account:" + email, 5, 900)])
    db.commit()
    if retry:
        raise HTTPException(429, "Too many platform login attempts", headers={"Retry-After": str(retry)})
    admin = db.query(PlatformAdmin).filter(func.lower(PlatformAdmin.email) == email).first()
    # Verify a hash on misses as well, avoiding a cheap account enumeration path.
    dummy = get_password_hash("platform-invalid-password") if not admin else admin.hashed_password
    valid = verify_password(data.password, dummy)
    if not admin or not valid or not admin.is_active:
        svc.event(db, None, "login.failed", "session", reason=str(client_addresses(request)[0]), after={"account_hash": svc.digest(email)})
        db.commit()
        raise HTTPException(401, "Invalid platform owner credentials")
    return session_result(admin, request, db)
