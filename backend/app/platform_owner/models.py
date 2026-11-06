from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import declarative_base

PlatformBase = declarative_base()


class PlatformAdmin(PlatformBase):
    __tablename__ = "platform_admins"
    id = Column(Integer, primary_key=True)
    email = Column(String(150), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    token_version = Column(Integer, nullable=False, default=1)
    name = Column(String(150), nullable=False, default="Platform owner", server_default="Platform owner")
    role = Column(String(30), nullable=False, default="owner", server_default="owner")
    permissions = Column(JSON, nullable=False, default=list, server_default="[]")
    assigned_only = Column(Boolean, nullable=False, default=False, server_default="false")
    preferences = Column(JSON, nullable=False, default=dict, server_default="{}")
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlatformSignupRequest(PlatformBase):
    __tablename__ = "platform_signup_requests"
    id = Column(Integer, primary_key=True)
    applicant_type = Column(String(20), nullable=False)
    name = Column(String(180), nullable=False)
    company_name = Column(String(180))
    email = Column(String(150), nullable=False, unique=True, index=True)
    phone = Column(String(30), nullable=False)
    phone_country_code = Column(String(5), nullable=False)
    requested_modules = Column(JSON, nullable=False, default=list)
    notes = Column(Text)
    status = Column(String(20), nullable=False, default="pending", index=True)
    # External references only: no cross-database foreign keys or user-ID lookup.
    company_id = Column(Integer)
    user_id = Column(Integer)
    reviewed_by = Column(Integer, ForeignKey("platform_admins.id"))
    review_reason = Column(String(500))
    trial_ends_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True))
    assigned_to = Column(Integer, ForeignKey("platform_admins.id"))
    source = Column(String(80), nullable=False, default="website", server_default="website")
    campaign = Column(String(120), nullable=False, default="", server_default="")
    tags = Column(JSON, nullable=False, default=list, server_default="[]")
    consent_evidence = Column(Text, nullable=False, default="Public trial request consent", server_default="Public trial request consent")
    workflow = Column(JSON, nullable=False, default=dict, server_default="{}")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    archived_at = Column(DateTime(timezone=True))
    previous_status = Column(String(30))
    legal_hold = Column(Boolean, nullable=False, default=False, server_default="false")
    deleted_at = Column(DateTime(timezone=True))


class PlatformSession(PlatformBase):
    __tablename__ = "platform_sessions"
    id = Column(String(64), primary_key=True)
    admin_id = Column(Integer, ForeignKey("platform_admins.id"), nullable=False, index=True)
    ip = Column(String(80), nullable=False)
    device = Column(String(300), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class PlatformEvent(PlatformBase):
    __tablename__ = "platform_events"
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey("platform_admins.id"))
    action = Column(String(100), nullable=False, index=True)
    entity = Column(String(40), nullable=False)
    entity_id = Column(Integer)
    reason = Column(String(1000), nullable=False, default="")
    before = Column(JSON, nullable=False, default=dict)
    after = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class PlatformPlan(PlatformBase):
    __tablename__ = "platform_plans"
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(120), nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlatformTenant(PlatformBase):
    __tablename__ = "platform_tenants"
    id = Column(Integer, primary_key=True)
    signup_id = Column(Integer, ForeignKey("platform_signup_requests.id"), unique=True, nullable=False)
    company_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(180), nullable=False)
    admin_email = Column(String(150), nullable=False)
    status = Column(String(30), nullable=False, default="trial", index=True)
    plan_id = Column(Integer, ForeignKey("platform_plans.id"))
    assigned_to = Column(Integer, ForeignKey("platform_admins.id"))
    config = Column(JSON, nullable=False, default=dict)
    usage = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlatformRecord(PlatformBase):
    """Owner-only workflows: notes, tasks, views, templates, local outbox and jobs."""
    __tablename__ = "platform_records"
    id = Column(Integer, primary_key=True)
    kind = Column(String(40), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    state = Column(String(30), nullable=False, default="open", index=True)
    owner_id = Column(Integer, ForeignKey("platform_admins.id"))
    signup_id = Column(Integer, ForeignKey("platform_signup_requests.id"))
    tenant_id = Column(Integer, ForeignKey("platform_tenants.id"))
    token_hash = Column(String(64), unique=True)
    data = Column(JSON, nullable=False, default=dict)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PlatformAudit(PlatformBase):
    __tablename__ = "platform_approval_history"
    id = Column(Integer, primary_key=True)
    signup_id = Column(Integer, ForeignKey("platform_signup_requests.id"), nullable=False)
    admin_id = Column(Integer, ForeignKey("platform_admins.id"), nullable=False)
    decision = Column(String(20), nullable=False)
    reason = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


# Separate throttle state; no dependency on the customer database.
from app.models.security_boundary import SecurityRateBucket
SecurityRateBucket.__table__.to_metadata(PlatformBase.metadata)
