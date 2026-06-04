from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    module: Optional[str] = None
    trusted_device_token: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    role: Optional[str] = None
    is_superuser: bool = False
    employee_id: Optional[int] = None


class MFAVerifyRequest(BaseModel):
    mfa_token: str
    code: str
    method: str = "totp"
    trust_device: bool = False
    device_name: Optional[str] = None


class MFAConfirmRequest(BaseModel):
    method_id: int
    code: str


class MFACodeRequest(BaseModel):
    code: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class PermissionSchema(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    module: Optional[str] = None

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permission_ids: List[int] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None


class RoleSchema(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_system: bool
    permissions: List[PermissionSchema] = []

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role_id: Optional[int] = None
    is_superuser: bool = False


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserSchema(BaseModel):
    id: int
    email: str
    is_active: bool
    is_superuser: bool
    role: Optional[RoleSchema] = None
    employee_id: Optional[int] = None

    class Config:
        from_attributes = True


class UserSessionCreate(BaseModel):
    user_id: int
    session_token_hash: str
    device_name: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    trusted_device: bool = False
    status: str = "Active"
    expires_at: Optional[datetime] = None


class UserSessionSchema(UserSessionCreate):
    id: int
    last_seen_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MFAMethodCreate(BaseModel):
    user_id: int
    method_type: str
    secret_ref: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False


class MFAMethodSchema(MFAMethodCreate):
    id: int
    is_verified: bool
    enabled_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PasswordPolicyCreate(BaseModel):
    name: str = "Default"
    min_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_number: bool = True
    require_special: bool = False
    require_symbol: bool = False
    max_age_days: int = 90
    expiry_days: int = 90
    lockout_attempts: int = 5
    lockout_duration_minutes: int = 30
    lockout_minutes: int = 30
    mfa_required: bool = False
    is_default: bool = False
    is_active: bool = True


class PasswordPolicySchema(PasswordPolicyCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class LoginAttemptSchema(BaseModel):
    id: int
    email: Optional[str] = None
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    status: str
    success: Optional[bool] = None
    failure_reason: Optional[str] = None
    mfa_attempted: bool = False
    mfa_success: Optional[bool] = None
    created_at: datetime

    class Config:
        from_attributes = True
