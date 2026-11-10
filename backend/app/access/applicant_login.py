"""Verified applicants receive status-only capabilities, never customer tokens."""
import secrets
from datetime import timedelta
from sqlalchemy import func
from app.core.config import settings
from app.platform_owner.models import PlatformRecord, PlatformSignupRequest
from app.platform_owner.session import platform_factory
from app.platform_owner import service as s


def status_link(db, signup):
    raw = secrets.token_urlsafe(40)
    db.add(PlatformRecord(kind="tracking", title="Your signup application", state="pending",
        signup_id=signup.id, token_hash=s.digest(raw), data={"recipient": signup.email},
        expires_at=s.now() + timedelta(hours=24)))
    return settings.FRONTEND_PUBLIC_URL.rstrip("/") + "/platform/public/" + raw


def verified_applicant_login(email):
    if not settings.PLATFORM_DATABASE_URL:
        return None
    with platform_factory()() as db:
        signup = db.query(PlatformSignupRequest).filter(func.lower(PlatformSignupRequest.email) == email.lower(),
            PlatformSignupRequest.deleted_at.is_(None)).first()
        if not signup or signup.status not in s.REVIEWABLE:
            return None
        url = status_link(db, signup)
        db.commit()
        return {"approval_required": True, "application_status": signup.status,
                "application_url": url, "message": "Waiting for approval", "email": email}
