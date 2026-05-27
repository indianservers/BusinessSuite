from datetime import datetime, timezone, timedelta
import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.core.deps import get_current_active_superuser, get_db, get_current_user
from app.core.config import settings
from app.core.email import send_email
from app.core.security import (
    verify_password, create_access_token, create_refresh_token,
    verify_refresh_token, get_password_hash
)
from app.core.mfa import (
    generate_recovery_codes,
    generate_totp_qr_base64,
    generate_totp_secret,
    hash_recovery_code,
    verify_recovery_code,
    verify_totp,
)
from app.models.user import User
from app.models.user import Role, Permission, UserSession, MFAMethod, PasswordPolicy, LoginAttempt
from app.schemas.auth import (
    LoginRequest, TokenResponse, RefreshTokenRequest,
    ChangePasswordRequest, PasswordResetConfirm, PasswordResetRequest, UserCreate, UserSchema,
    RoleCreate, RoleUpdate, RoleSchema, PermissionSchema,
    UserSessionCreate, UserSessionSchema, MFAMethodCreate, MFAMethodSchema,
    PasswordPolicyCreate, PasswordPolicySchema, LoginAttemptSchema,
    MFAVerifyRequest, MFAConfirmRequest, MFACodeRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

MODULE_ROLE_MAP = {
    "hrms": {"super_admin", "hr_manager", "ceo", "manager", "employee"},
    "crm": {
        "crm_super_admin",
        "crm_org_admin",
        "crm_sales_manager",
        "crm_sales_executive",
        "crm_support_agent",
        "crm_marketing_user",
        "crm_viewer",
    },
    "project_management": {
        "pms_super_admin",
        "pms_org_admin",
        "pms_project_manager",
        "pms_team_member",
        "pms_client",
        "pms_viewer",
    },
}


def _normalize_module(module: str | None) -> str | None:
    if not module:
        return None
    value = module.strip().lower().replace("-", "_")
    if value in {"pms", "project", "project_management"}:
        return "project_management"
    if value in {"crm", "hrms"}:
        return value
    return None


def _ensure_module_login_allowed(user: User, module: str | None) -> None:
    module_key = _normalize_module(module)
    if not module_key:
        return
    role_name = user.role.name if user.role else None
    if role_name not in MODULE_ROLE_MAP[module_key]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This account is not allowed to sign in to {module_key.replace('_', ' ').upper()}",
        )


def _token_response(user: User) -> TokenResponse:
    employee = getattr(user, "employee", None)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user_id=user.id,
        email=user.email,
        role=user.role.name if user.role else None,
        is_superuser=user.is_superuser,
        employee_id=employee.id if employee else None,
    )


def _log_attempt(db: Session, user: User | None, email: str, success: bool, failure_reason: str | None = None, request: Request | None = None, mfa_attempted: bool = False, mfa_success: bool | None = None) -> None:
    db.add(LoginAttempt(
        email=email,
        user_id=user.id if user else None,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        status="Success" if success else "Failed",
        success=success,
        failure_reason=failure_reason,
        mfa_attempted=mfa_attempted,
        mfa_success=mfa_success,
    ))


def check_lockout(db: Session, user: User) -> dict | None:
    """Returns lockout details when the account is temporarily locked."""
    policy = db.query(PasswordPolicy).filter((PasswordPolicy.is_default == True) | (PasswordPolicy.is_active == True)).order_by(PasswordPolicy.is_default.desc(), PasswordPolicy.id.desc()).first()
    attempts = policy.lockout_attempts if policy else 0
    if not policy or not attempts:
        return None
    duration = policy.lockout_duration_minutes or policy.lockout_minutes or 30
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=duration)
    recent_failures = db.query(LoginAttempt).filter(
        LoginAttempt.user_id == user.id,
        ((LoginAttempt.success == False) | (LoginAttempt.status == "Failed")),
        LoginAttempt.created_at >= cutoff,
    ).count()
    if recent_failures >= attempts:
        return {"locked": True, "attempts": recent_failures, "unlock_after_minutes": duration}
    return None


def _active_password_policy(db: Session) -> PasswordPolicy | None:
    return db.query(PasswordPolicy).filter(
        (PasswordPolicy.is_default == True) | (PasswordPolicy.is_active == True)
    ).order_by(PasswordPolicy.is_default.desc(), PasswordPolicy.id.desc()).first()


def _validate_password_policy(db: Session, password: str) -> None:
    policy = _active_password_policy(db)
    min_length = policy.min_length if policy else 8
    if len(password) < min_length:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Password must be at least {min_length} characters")
    if policy:
        if policy.require_uppercase and not any(char.isupper() for char in password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must include an uppercase letter")
        if policy.require_lowercase and not any(char.islower() for char in password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must include a lowercase letter")
        if policy.require_number and not any(char.isdigit() for char in password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must include a number")
        if (policy.require_special or policy.require_symbol) and not any(not char.isalnum() for char in password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must include a special character")


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _revoke_user_sessions(db: Session, user_id: int, except_token: str | None = None) -> None:
    query = db.query(UserSession).filter(UserSession.user_id == user_id, UserSession.status != "revoked")
    if except_token:
        query = query.filter(UserSession.session_token_hash != _hash_reset_token(except_token))
    query.update({UserSession.status: "revoked"}, synchronize_session=False)


def _bearer_token(request: Request | None) -> str | None:
    if not request:
        return None
    authorization = request.headers.get("authorization") or request.headers.get("Authorization")
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()


def _create_mfa_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    return jwt.encode({"sub": str(user.id), "scope": "mfa", "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_mfa_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid MFA token")
    if payload.get("scope") != "mfa":
        raise HTTPException(status_code=401, detail="Invalid MFA token")
    return payload


def _active_totp(db: Session, user_id: int) -> MFAMethod | None:
    return db.query(MFAMethod).filter(
        MFAMethod.user_id == user_id,
        MFAMethod.method_type.in_(["totp", "TOTP"]),
        MFAMethod.is_verified == True,
        MFAMethod.is_active == True,
    ).order_by(MFAMethod.id.desc()).first()


@router.post("/login")
def login(request_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request_data.email).first()
    if user:
        lockout = check_lockout(db, user)
        if lockout:
            raise HTTPException(status_code=423, detail=f"Account locked after {lockout['attempts']} failed attempts. Try again in {lockout['unlock_after_minutes']} minutes.")
    if not user or not user.hashed_password or not verify_password(request_data.password, user.hashed_password):
        _log_attempt(db, user, request_data.email, False, "Incorrect credentials", request)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        _log_attempt(db, user, request_data.email, False, "Account disabled", request)
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    _ensure_module_login_allowed(user, request_data.module)

    user.last_login = datetime.now(timezone.utc)
    _log_attempt(db, user, request_data.email, True, request=request)
    db.commit()

    if user.mfa_enabled:
        return {"mfa_required": True, "mfa_token": _create_mfa_token(user), "mfa_methods": ["totp", "recovery"]}

    return _token_response(user)


@router.post("/mfa/verify")
def verify_mfa_login(data: MFAVerifyRequest, request: Request, db: Session = Depends(get_db)):
    """Complete the second login phase using TOTP or a recovery code."""
    payload = _decode_mfa_token(data.mfa_token)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    lockout = check_lockout(db, user)
    if lockout:
        raise HTTPException(status_code=423, detail=f"Account locked after {lockout['attempts']} failed attempts. Try again in {lockout['unlock_after_minutes']} minutes.")
    method = _active_totp(db, user.id)
    valid = False
    if data.method == "totp" and method:
        valid = verify_totp(method.secret or method.secret_ref or "", data.code)
    elif data.method == "recovery" and method:
        codes = method.recovery_codes_json or []
        for item in codes:
            if not item.get("used") and verify_recovery_code(data.code, item.get("hash", "")):
                item["used"] = True
                item["used_at"] = datetime.now(timezone.utc).isoformat()
                method.recovery_codes_json = codes
                valid = True
                break
    if not valid:
        _log_attempt(db, user, user.email, False, "Invalid MFA code", request, True, False)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    if method:
        method.last_used_at = datetime.now(timezone.utc)
    user.last_login = datetime.now(timezone.utc)
    _log_attempt(db, user, user.email, True, request=request, mfa_attempted=True, mfa_success=True)
    db.commit()
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    payload = verify_refresh_token(data.refresh_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    access_token = create_access_token(user.id)
    refresh_token_new = create_refresh_token(user.id)

    employee = getattr(user, "employee", None)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_new,
        user_id=user.id,
        email=user.email,
        role=user.role.name if user.role else None,
        is_superuser=user.is_superuser,
        employee_id=employee.id if employee else None,
    )


@router.get("/me", response_model=UserSchema)
def get_me(current_user: User = Depends(get_current_user)):
    employee = getattr(current_user, "employee", None)
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "role": current_user.role,
        "employee_id": employee.id if employee else None,
    }


@router.post("/forgot-password")
def forgot_password(data: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if user:
        raw_token = secrets.token_urlsafe(32)
        user.password_reset_token = _hash_reset_token(raw_token)
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        reset_link = f"{settings.FRONTEND_PUBLIC_URL.rstrip('/')}/reset-password?token={raw_token}"
        send_email(
            to=user.email,
            subject="Reset your password",
            body=f"Use this link to reset your password: {reset_link}\nThis link expires in 1 hour.",
        )
        db.commit()
    return {"message": "If this email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    token_hash = _hash_reset_token(data.token)
    user = db.query(User).filter(User.password_reset_token == token_hash).first()
    now = datetime.now(timezone.utc)
    expires = user.password_reset_expires if user else None
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not user or not expires or expires <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    _validate_password_policy(db, data.new_password)
    user.hashed_password = get_password_hash(data.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    _revoke_user_sessions(db, user.id)
    db.commit()
    return {"message": "Password reset successful. Please log in."}


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    _validate_password_policy(db, data.new_password)

    current_user.hashed_password = get_password_hash(data.new_password)
    _revoke_user_sessions(db, current_user.id, except_token=_bearer_token(request))
    db.commit()
    return {"message": "Password changed successfully."}


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    # In a stateless JWT setup, logout is client-side token removal
    # For production, implement token blacklisting with Redis
    return {"message": "Logged out successfully"}


@router.post("/mfa/setup")
def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start TOTP MFA setup and return one-time recovery codes."""
    secret = generate_totp_secret()
    qr_base64 = generate_totp_qr_base64(secret, current_user.email)
    codes = generate_recovery_codes(10)
    method = MFAMethod(
        user_id=current_user.id,
        method_type="totp",
        secret=secret,
        secret_ref=secret,
        is_primary=True,
        is_verified=False,
        is_active=True,
        recovery_codes_json=[{"hash": hash_recovery_code(code), "used": False} for code in codes],
    )
    try:
        db.add(method)
        db.commit()
        db.refresh(method)
    except Exception:
        db.rollback()
        raise
    return {"secret": secret, "qr_base64": qr_base64, "recovery_codes": codes, "method_id": method.id}


@router.post("/mfa/confirm")
def confirm_mfa(
    data: MFAConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify the setup code and enable TOTP MFA for the current user."""
    method = db.query(MFAMethod).filter(MFAMethod.id == data.method_id, MFAMethod.user_id == current_user.id).first()
    if not method:
        raise HTTPException(status_code=404, detail="MFA method not found")
    if not verify_totp(method.secret or method.secret_ref or "", data.code):
        raise HTTPException(status_code=401, detail="Incorrect code. Please try again.")
    try:
        db.query(MFAMethod).filter(
            MFAMethod.user_id == current_user.id,
            MFAMethod.method_type.in_(["totp", "TOTP"]),
            MFAMethod.id != method.id,
        ).update({MFAMethod.is_active: False})
        method.is_verified = True
        method.verified_at = datetime.now(timezone.utc)
        method.enabled_at = method.verified_at
        method.is_active = True
        current_user.mfa_enabled = True
        current_user.mfa_enforced_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"success": True, "recovery_code_count": len(method.recovery_codes_json or [])}


@router.delete("/mfa/disable")
def disable_mfa(
    data: MFACodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable TOTP MFA after verifying the current code."""
    method = _active_totp(db, current_user.id)
    if not method or not verify_totp(method.secret or method.secret_ref or "", data.code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    try:
        method.is_active = False
        current_user.mfa_enabled = False
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"success": True}


@router.get("/mfa/status")
def mfa_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return current MFA state for the logged-in user."""
    method = _active_totp(db, current_user.id)
    codes = method.recovery_codes_json if method else []
    remaining = len([code for code in (codes or []) if not code.get("used")])
    return {
        "mfa_enabled": bool(current_user.mfa_enabled and method),
        "method_type": method.method_type if method else None,
        "verified_at": method.verified_at or method.enabled_at if method else None,
        "recovery_codes_remaining": remaining,
    }


@router.post("/mfa/regenerate-recovery-codes")
def regenerate_recovery_codes(
    data: MFACodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Regenerate one-time recovery codes after TOTP verification."""
    method = _active_totp(db, current_user.id)
    if not method or not verify_totp(method.secret or method.secret_ref or "", data.code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    codes = generate_recovery_codes(10)
    try:
        method.recovery_codes_json = [{"hash": hash_recovery_code(code), "used": False} for code in codes]
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"recovery_codes": codes}


@router.get("/users", response_model=list[UserSchema])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    return db.query(User).order_by(User.email).all()


@router.post("/users", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User email already exists")
    if data.role_id:
        role = db.query(Role).filter(Role.id == data.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role_id=data.role_id,
        is_superuser=data.is_superuser,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/permissions", response_model=list[PermissionSchema])
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        from app.core.deps import RequirePermission
        RequirePermission("company_manage")(current_user)
    return db.query(Permission).order_by(Permission.module, Permission.name).all()


@router.get("/roles", response_model=list[RoleSchema])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        from app.core.deps import RequirePermission
        RequirePermission("company_manage")(current_user)
    return db.query(Role).order_by(Role.name).all()


@router.post("/roles", response_model=RoleSchema, status_code=status.HTTP_201_CREATED)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser privileges required")
    role = Role(name=data.name, description=data.description, is_system=False)
    if data.permission_ids:
        role.permissions = db.query(Permission).filter(Permission.id.in_(data.permission_ids)).all()
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.put("/roles/{role_id}", response_model=RoleSchema)
def update_role(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser privileges required")
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permission_ids is not None:
        role.permissions = db.query(Permission).filter(Permission.id.in_(data.permission_ids)).all()
    db.commit()
    db.refresh(role)
    return role


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser privileges required")
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")
    db.delete(role)
    db.commit()
    return {"message": "Role deleted"}


@router.post("/sessions", response_model=UserSessionSchema, status_code=201)
def create_user_session(
    data: UserSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    item = UserSession(**data.model_dump(), last_seen_at=datetime.now(timezone.utc))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/sessions", response_model=list[UserSessionSchema])
def list_user_sessions(
    user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    query = db.query(UserSession)
    if user_id:
        query = query.filter(UserSession.user_id == user_id)
    return query.order_by(UserSession.id.desc()).limit(300).all()


@router.put("/sessions/{session_id}/revoke", response_model=UserSessionSchema)
def revoke_user_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    item = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Session not found")
    item.status = "Revoked"
    db.commit()
    db.refresh(item)
    return item


@router.post("/mfa-methods", response_model=MFAMethodSchema, status_code=201)
def create_mfa_method(
    data: MFAMethodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    item = MFAMethod(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/mfa-methods/{method_id}/verify", response_model=MFAMethodSchema)
def verify_mfa_method(
    method_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    item = db.query(MFAMethod).filter(MFAMethod.id == method_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="MFA method not found")
    item.is_verified = True
    item.enabled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/password-policies", response_model=PasswordPolicySchema, status_code=201)
def create_password_policy(
    data: PasswordPolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    if data.is_active:
        db.query(PasswordPolicy).update({PasswordPolicy.is_active: False})
    if data.is_default:
        db.query(PasswordPolicy).update({PasswordPolicy.is_default: False})
    item = PasswordPolicy(**data.model_dump())
    item.require_symbol = data.require_special or data.require_symbol
    item.expiry_days = data.max_age_days or data.expiry_days
    item.lockout_minutes = data.lockout_duration_minutes or data.lockout_minutes
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/password-policies", response_model=list[PasswordPolicySchema])
def list_password_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    return db.query(PasswordPolicy).order_by(PasswordPolicy.id.desc()).all()


@router.put("/password-policies/{policy_id}", response_model=PasswordPolicySchema)
def update_password_policy(
    policy_id: int,
    data: PasswordPolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Update password, lockout, and MFA policy settings."""
    item = db.query(PasswordPolicy).filter(PasswordPolicy.id == policy_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Password policy not found")
    try:
        if data.is_default:
            db.query(PasswordPolicy).filter(PasswordPolicy.id != policy_id).update({PasswordPolicy.is_default: False})
        for key, value in data.model_dump().items():
            if hasattr(item, key):
                setattr(item, key, value)
        item.require_symbol = data.require_special or data.require_symbol
        item.expiry_days = data.max_age_days or data.expiry_days
        item.lockout_minutes = data.lockout_duration_minutes or data.lockout_minutes
        db.commit()
        db.refresh(item)
    except Exception:
        db.rollback()
        raise
    return item


@router.post("/password-policies/{policy_id}/enforce-mfa")
def enforce_policy_mfa(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
):
    """Enable MFA enforcement on a password policy and report remaining users."""
    item = db.query(PasswordPolicy).filter(PasswordPolicy.id == policy_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Password policy not found")
    try:
        item.mfa_required = True
        users_without_mfa = db.query(User).filter(User.is_active == True, (User.mfa_enabled == False) | (User.mfa_enabled.is_(None))).count()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"updated": True, "users_without_mfa": users_without_mfa}


@router.get("/login-attempts", response_model=list[LoginAttemptSchema])
def list_login_attempts(
    email: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(LoginAttempt)
    if not current_user.is_superuser:
        query = query.filter(LoginAttempt.user_id == current_user.id)
    if email:
        query = query.filter(LoginAttempt.email == email)
    return query.order_by(LoginAttempt.id.desc()).limit(300).all()
