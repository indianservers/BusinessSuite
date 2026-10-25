from typing import Generator, Optional
from datetime import datetime, timezone, timedelta
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.security import verify_access_token
from app.models.user import User, UserSession

security = HTTPBearer(auto_error=False)


def token_record_id(value) -> int:
    """Validate signed claims before using them as database identifiers."""
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise HTTPException(401, "Invalid token payload")
    text = str(value)
    if not text.isascii() or not text.isdecimal() or len(text) > 19:
        raise HTTPException(401, "Invalid token payload")
    result = int(text)
    if result <= 0 or result > 9223372036854775807:
        raise HTTPException(401, "Invalid token payload")
    return result


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
    token = credentials.credentials
    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("portal") == "interns_hub" and not request.url.path.startswith("/api/v1/interns-hub/"):
        raise HTTPException(status_code=403, detail="Intern session is restricted to Interns Hub")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == token_record_id(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user account")
    employee=getattr(user,'employee',None)
    is_intern=(user.role and user.role.name.lower()=='intern') or (employee and (employee.employment_type or '').lower()=='intern')
    if is_intern and not request.url.path.startswith('/api/v1/interns-hub/'):
        raise HTTPException(403,'Intern accounts are restricted to Interns Hub')
    session_id = payload.get("sid")
    if session_id:
        session = db.query(UserSession).filter(UserSession.id == token_record_id(session_id), UserSession.user_id == user.id).first()
        expires_at = session.expires_at if session else None
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if not session or session.status.lower() == "revoked" or (expires_at and expires_at <= datetime.now(timezone.utc)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked or expired")
        last_seen = session.last_seen_at
        if last_seen and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        # Recheck revocation on every call, without turning every read into a
        # contending write on the same session row.
        if last_seen is None or last_seen <= now-timedelta(minutes=5):
            session.last_seen_at = now
            db.commit()
    from app.core.audit_context import set_audit_actor
    set_audit_actor(user)
    return user


def get_current_active_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser privileges required")
    return current_user


class RequirePermission:
    """Dependency factory for RBAC permission checks."""

    def __init__(self, *permissions: str):
        self.permissions = set(permissions)

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user
        user_permissions = {p.name for p in (current_user.role.permissions if current_user.role else [])}
        if not self.permissions.intersection(user_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required permissions: {', '.join(self.permissions)}",
            )
        return current_user


def require_roles(*roles: str):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user
        user_role = current_user.role.name if current_user.role else None
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {', '.join(roles)}",
            )
        return current_user
    return checker
