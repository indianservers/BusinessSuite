from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Table, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.config import settings
from app.db.base_class import Base

# M2M: role <-> permissions
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255))
    module = Column(String(50))  # employees, attendance, payroll, etc.

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(String(255))
    is_system = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    users = relationship("User", back_populates="role")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    mfa_enforced_at = Column(DateTime(timezone=True), nullable=True)
    sso_provider_id = Column(Integer, ForeignKey("sso_providers.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    role = relationship("Role", back_populates="users")
    person = relationship("CommonPerson", back_populates="user", uselist=False, cascade="all, delete-orphan")
    if "hrms" in [item.strip().lower().replace("-", "_") for item in settings.INSTALLED_APPS]:
        employee = relationship("Employee", back_populates="user", uselist=False, foreign_keys="Employee.user_id")
    audit_logs = relationship("AuditLog", back_populates="user")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token_hash = Column(String(255), nullable=False, index=True)
    device_name = Column(String(150))
    ip_address = Column(String(50))
    user_agent = Column(Text)
    trusted_device = Column(Boolean, default=False)
    status = Column(String(30), default="Active", index=True)
    last_seen_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class MFAMethod(Base):
    __tablename__ = "mfa_methods"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    method_type = Column(String(30), nullable=False)  # TOTP, Email OTP, SMS OTP
    secret = Column(String(255))
    secret_ref = Column(String(255))
    phone_number = Column(String(30))
    email = Column(String(120))
    is_primary = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    enabled_at = Column(DateTime(timezone=True))
    last_used_at = Column(DateTime(timezone=True))
    recovery_codes_json = Column(JSON)
    verified_at = Column(DateTime(timezone=True))
    backup_email = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class PasswordPolicy(Base):
    __tablename__ = "password_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    min_length = Column(Integer, default=8)
    require_uppercase = Column(Boolean, default=True)
    require_lowercase = Column(Boolean, default=True)
    require_number = Column(Boolean, default=True)
    require_special = Column(Boolean, default=False)
    require_symbol = Column(Boolean, default=False)
    max_age_days = Column(Integer, default=90)
    expiry_days = Column(Integer, default=90)
    lockout_attempts = Column(Integer, default=5)
    lockout_duration_minutes = Column(Integer, default=30)
    lockout_minutes = Column(Integer, default=30)
    mfa_required = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(120), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    status = Column(String(30), nullable=False, index=True)
    success = Column(Boolean)
    failure_reason = Column(String(255))
    mfa_attempted = Column(Boolean, default=False)
    mfa_success = Column(Boolean)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class IPAccessPolicy(Base):
    __tablename__ = "ip_access_policies"

    id = Column(Integer, primary_key=True, index=True)
    cidr = Column(String(80), nullable=False, index=True)
    action = Column(String(20), nullable=False, default="allow", index=True)
    description = Column(String(255))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
