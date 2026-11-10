"""Public identity prefill, operational policies and coarse signup telemetry."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.config import settings
from app.platform_owner.session import get_platform_db
from app.platform_owner.models import PlatformRecord
from app.platform_owner import service as s
from app.core.deps import get_db

router = APIRouter(prefix="/signup")


class IdentityInput(BaseModel):
    token: str = Field(min_length=20, max_length=10000)


def throttle(db, request, key, count=20):
    from app.core.request_limits import consume
    from app.core.middleware.audit import client_addresses
    retry = consume(db, [(key + str(client_addresses(request)[0]), count, 3600)])
    db.commit()
    if retry:
        raise HTTPException(429, "Please wait before trying again.", headers={"Retry-After": str(retry)})


@router.post("/identity")
def identity(data: IdentityInput, request: Request, db: Session = Depends(get_platform_db)):
    throttle(db, request, "signup-identity:")
    from app.core.firebase import verify_google_identity
    import jwt
    try:
        who = verify_google_identity(data.token, settings.FIREBASE_PROJECT_ID)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Google identity could not be verified") from None
    proof = jwt.encode({"email": who["email"].lower(), "exp": s.now() + __import__('datetime').timedelta(minutes=30),
        "purpose": "signup-prefill", "iss": "besterp-signup"}, settings.PLATFORM_SECRET_KEY, algorithm="HS256")
    return {"email": who["email"], "name": who["full_name"], "identity_proof": proof}


@router.get("/policies")
def policies():
    return {"version": "2026-11-10", "terms": [
        "Applying does not grant business access. Our team reviews company and individual requests before approval.",
        "Approval confirms your applications, seats, storage allowance and trial-start rule. Your approval email explains those limits.",
        "Use an email address you control. Google sign-in must use the application email; email/password users set a password after approval.",
        "Sample data is optional and must be explicitly imported by the company administrator. It can be removed.",
        "Contact support through Help before your trial ends to discuss continued service. Submitting this form does not purchase a subscription."],
        "privacy": [
        "We store the application contact details, requested applications, consent choices, review history and delivery records to process your request and provide access.",
        "Authorized platform staff can review applications. Pending status links are private and expire; do not share them.",
        "Essential receipt, review, correction, approval and security messages are separate from optional marketing consent.",
        "Draft saving is optional on this device and expires after 24 hours. Clearing the draft removes its local copy.",
        "Application lifecycle analytics use event names, source and requested application categories, not your form answers. Declining analytics does not affect review.",
        "Contact Help & support for correction or deletion requests. Archived non-customer applications can be purged after the configured retention period, subject to legal holds. Deletion is an operator action, not an automatic promise."]}


@router.get("/invitation")
def invitation(token:str,tenant:str|None=None,business:Session=Depends(get_db)):
    from contextlib import nullcontext
    from app.models.user import User
    from app.api.v1.auth import _hash_reset_token
    context=nullcontext(business)
    if tenant:
        from app.db.tenant import lookup_route,tenant_session
        context=tenant_session(lookup_route(tenant))
    with context as db:
        user=db.query(User).filter_by(password_reset_token=_hash_reset_token(token)).first() if 20<=len(token)<=300 else None
        if not user or not user.password_reset_expires or s.aware(user.password_reset_expires)<=s.now():
            raise HTTPException(404,"This setup link expired or was already used. Request a fresh link below.")
        return {"email":user.email,"expires_at":user.password_reset_expires,"login_url":"/login"+("?tenant="+tenant if tenant else "")}


class TelemetryInput(BaseModel):
    event: str = Field(pattern="^(started|identity_complete|needs_complete|submitted)$")
    session: str = Field(pattern="^[a-f0-9-]{20,50}$")
    source: str = Field(default="website", pattern="^[A-Za-z0-9_-]{1,40}$")


@router.post("/telemetry", status_code=202)
def telemetry(data: TelemetryInput, request: Request, db: Session = Depends(get_platform_db)):
    throttle(db, request, "signup-metric:", 100)
    key = s.digest("signup-metric:" + data.session + ":" + data.event)
    if not db.query(PlatformRecord.id).filter_by(token_hash=key).first():
        db.add(PlatformRecord(kind="signup_metric", title=data.event, token_hash=key, state="recorded", data={"source": data.source}))
        db.commit()
    return {"recorded": True}
