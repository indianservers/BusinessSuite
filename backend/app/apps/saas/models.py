from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base_class import Base


class PortalRole(Base):
    __tablename__ = "portal_roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), unique=True, nullable=False, index=True)
    portal_type = Column(String(30), nullable=False, index=True)
    permissions_json = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PortalUser(Base):
    __tablename__ = "portal_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(160), unique=True, nullable=False, index=True)
    display_name = Column(String(160), nullable=False)
    portal_type = Column(String(30), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("portal_roles.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="invited", index=True)
    password_hash = Column(String(255))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    last_login_at = Column(DateTime(timezone=True))


class PortalAccessGrant(Base):
    __tablename__ = "portal_access_grants"

    id = Column(Integer, primary_key=True, index=True)
    portal_user_id = Column(Integer, ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type = Column(String(80), nullable=False, index=True)
    resource_id = Column(Integer, nullable=False, index=True)
    permissions_json = Column(JSON, default=list)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("portal_user_id", "resource_type", "resource_id", name="uq_portal_grant_resource"),)


class PortalSession(Base):
    __tablename__ = "portal_sessions"

    id = Column(Integer, primary_key=True, index=True)
    portal_user_id = Column(Integer, ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token_hash = Column(String(255), nullable=False, unique=True, index=True)
    status = Column(String(30), default="active", index=True)
    ip_address = Column(String(80))
    user_agent = Column(Text)
    expires_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True))


class PortalCustomerLink(Base):
    __tablename__ = "portal_customer_links"

    id = Column(Integer, primary_key=True, index=True)
    portal_user_id = Column(Integer, ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(Integer, nullable=False, index=True)
    crm_account_id = Column(Integer, index=True)
    crm_contact_id = Column(Integer, index=True)
    srm_customer_id = Column(Integer, index=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PortalPartnerLink(Base):
    __tablename__ = "portal_partner_links"

    id = Column(Integer, primary_key=True, index=True)
    portal_user_id = Column(Integer, ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False, index=True)
    partner_id = Column(Integer, nullable=False, index=True)
    partner_name = Column(String(180))
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PortalActivityLog(Base):
    __tablename__ = "portal_activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    portal_user_id = Column(Integer, ForeignKey("portal_users.id", ondelete="SET NULL"), nullable=True, index=True)
    portal_type = Column(String(30), nullable=False, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    resource_type = Column(String(80), index=True)
    resource_id = Column(Integer, index=True)
    status = Column(String(30), default="completed", index=True)
    detail_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class DeveloperAPIKey(Base):
    __tablename__ = "developer_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    key_prefix = Column(String(20), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    scopes_json = Column(JSON, default=list)
    status = Column(String(30), default="active", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    revoked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    revoked_at = Column(DateTime(timezone=True))
    last_used_at = Column(DateTime(timezone=True))


class DeveloperWebhook(Base):
    __tablename__ = "developer_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    target_url = Column(String(500), nullable=False)
    events_json = Column(JSON, default=list)
    secret_hash = Column(String(255))
    status = Column(String(30), default="active", index=True)
    retry_enabled = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class DeveloperWebhookDelivery(Base):
    __tablename__ = "developer_webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    webhook_id = Column(Integer, ForeignKey("developer_webhooks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    payload_json = Column(JSON)
    status = Column(String(30), default="queued", index=True)
    attempt_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime(timezone=True), index=True)
    response_status = Column(Integer)
    response_body = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    delivered_at = Column(DateTime(timezone=True))


class DeveloperAPILog(Base):
    __tablename__ = "developer_api_logs"

    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, ForeignKey("developer_api_keys.id", ondelete="SET NULL"), nullable=True, index=True)
    key_prefix = Column(String(20), index=True)
    endpoint = Column(String(240), nullable=False, index=True)
    method = Column(String(12), nullable=False)
    status_code = Column(Integer, nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class DeveloperApp(Base):
    __tablename__ = "developer_apps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(140), nullable=False, index=True)
    description = Column(Text)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="draft", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MarketplaceApp(Base):
    __tablename__ = "marketplace_apps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(140), nullable=False, index=True)
    category = Column(String(80), default="internal", index=True)
    description = Column(Text)
    internal_only = Column(Boolean, default=True, index=True)
    configuration_schema_json = Column(JSON, default=dict)
    status = Column(String(30), default="listed", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MarketplaceInstall(Base):
    __tablename__ = "marketplace_installs"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("marketplace_apps.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), default="installed", index=True)
    configuration_json = Column(JSON, default=dict)
    installed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    installed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    uninstalled_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("app_id", "status", name="uq_marketplace_app_status"),)


class SandboxEnvironment(Base):
    __tablename__ = "sandbox_environments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(140), nullable=False, index=True)
    source_environment = Column(String(80), default="production")
    status = Column(String(30), default="requested", index=True)
    access_url_placeholder = Column(String(500))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    refreshed_at = Column(DateTime(timezone=True))


class SandboxCopyJob(Base):
    __tablename__ = "sandbox_copy_jobs"

    id = Column(Integer, primary_key=True, index=True)
    sandbox_id = Column(Integer, ForeignKey("sandbox_environments.id", ondelete="CASCADE"), nullable=False, index=True)
    copy_type = Column(String(80), default="metadata")
    status = Column(String(30), default="queued", index=True)
    detail_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))


class TenantCompanySetting(Base):
    __tablename__ = "tenant_company_settings"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(180), nullable=False, default="Business Suite")
    logo_url = Column(String(500))
    fiscal_year_start_month = Column(Integer, default=4)
    base_currency = Column(String(12), default="INR")
    timezone = Column(String(80), default="Asia/Calcutta")
    tax_defaults_json = Column(JSON, default=dict)
    business_hours_json = Column(JSON, default=dict)
    numbering_settings_json = Column(JSON, default=dict)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TenantFeatureFlag(Base):
    __tablename__ = "tenant_feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    feature_key = Column(String(120), unique=True, nullable=False, index=True)
    enabled = Column(Boolean, default=True, index=True)
    upgrade_message = Column(String(255))
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TenantSubscriptionPlan(Base):
    __tablename__ = "tenant_subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(60), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    features_json = Column(JSON, default=list)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("tenant_subscription_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    edition = Column(String(60), default="ultimate", index=True)
    status = Column(String(30), default="active", index=True)
    admin_override = Column(Boolean, default=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TenantUsageMetric(Base):
    __tablename__ = "tenant_usage_metrics"

    id = Column(Integer, primary_key=True, index=True)
    metric_key = Column(String(120), nullable=False, index=True)
    metric_value = Column(Integer, default=0)
    period = Column(String(30), default="current", index=True)
    detail_json = Column(JSON, default=dict)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class MobileSalesVisitCheckIn(Base):
    __tablename__ = "mobile_sales_visit_checkins"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, index=True)
    deal_id = Column(Integer, index=True)
    customer_name = Column(String(180), nullable=False)
    latitude = Column(String(40))
    longitude = Column(String(40))
    notes = Column(Text)
    status = Column(String(30), default="checked_in", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
