"""phase 10 saas packaging

Revision ID: 20260605_009
Revises: 20260605_008
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_009"
down_revision = "20260605_008"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def upgrade() -> None:
    op.create_table(
        "portal_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("portal_type", sa.String(30), nullable=False),
        sa.Column("permissions_json", sa.JSON()),
        *_timestamps(),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "portal_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("portal_type", sa.String(30), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("portal_roles.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(30), default="invited"),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "portal_access_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_user_id", sa.Integer(), sa.ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("permissions_json", sa.JSON()),
        sa.Column("active", sa.Boolean(), default=True),
        *_timestamps(),
        sa.UniqueConstraint("portal_user_id", "resource_type", "resource_id", name="uq_portal_grant_resource"),
    )
    op.create_table(
        "portal_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_user_id", sa.Integer(), sa.ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token_hash", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), default="active"),
        sa.Column("ip_address", sa.String(80)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("session_token_hash"),
    )
    op.create_table(
        "portal_customer_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_user_id", sa.Integer(), sa.ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("crm_account_id", sa.Integer()),
        sa.Column("crm_contact_id", sa.Integer()),
        sa.Column("srm_customer_id", sa.Integer()),
        sa.Column("active", sa.Boolean(), default=True),
        *_timestamps(),
    )
    op.create_table(
        "portal_partner_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_user_id", sa.Integer(), sa.ForeignKey("portal_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("partner_name", sa.String(180)),
        sa.Column("active", sa.Boolean(), default=True),
        *_timestamps(),
    )
    op.create_table(
        "portal_activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal_user_id", sa.Integer(), sa.ForeignKey("portal_users.id", ondelete="SET NULL")),
        sa.Column("portal_type", sa.String(30), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(80)),
        sa.Column("resource_id", sa.Integer()),
        sa.Column("status", sa.String(30), default="completed"),
        sa.Column("detail_json", sa.JSON()),
        *_timestamps(),
    )
    op.create_table(
        "developer_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("scopes_json", sa.JSON()),
        sa.Column("status", sa.String(30), default="active"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("revoked_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_table(
        "developer_webhooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("target_url", sa.String(500), nullable=False),
        sa.Column("events_json", sa.JSON()),
        sa.Column("secret_hash", sa.String(255)),
        sa.Column("status", sa.String(30), default="active"),
        sa.Column("retry_enabled", sa.Boolean(), default=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
    )
    op.create_table(
        "developer_webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("webhook_id", sa.Integer(), sa.ForeignKey("developer_webhooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload_json", sa.JSON()),
        sa.Column("status", sa.String(30), default="queued"),
        sa.Column("attempt_count", sa.Integer(), default=0),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_body", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "developer_api_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_key_id", sa.Integer(), sa.ForeignKey("developer_api_keys.id", ondelete="SET NULL")),
        sa.Column("key_prefix", sa.String(20)),
        sa.Column("endpoint", sa.String(240), nullable=False),
        sa.Column("method", sa.String(12), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
    )
    op.create_table(
        "developer_apps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(140), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(30), default="draft"),
        *_timestamps(),
    )
    op.create_table(
        "marketplace_apps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(140), nullable=False),
        sa.Column("category", sa.String(80), default="internal"),
        sa.Column("description", sa.Text()),
        sa.Column("internal_only", sa.Boolean(), default=True),
        sa.Column("configuration_schema_json", sa.JSON()),
        sa.Column("status", sa.String(30), default="listed"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
    )
    op.create_table(
        "marketplace_installs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("app_id", sa.Integer(), sa.ForeignKey("marketplace_apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), default="installed"),
        sa.Column("configuration_json", sa.JSON()),
        sa.Column("installed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("installed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("uninstalled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("app_id", "status", name="uq_marketplace_app_status"),
    )
    op.create_table(
        "sandbox_environments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(140), nullable=False),
        sa.Column("source_environment", sa.String(80), default="production"),
        sa.Column("status", sa.String(30), default="requested"),
        sa.Column("access_url_placeholder", sa.String(500)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("refreshed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "sandbox_copy_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sandbox_id", sa.Integer(), sa.ForeignKey("sandbox_environments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("copy_type", sa.String(80), default="metadata"),
        sa.Column("status", sa.String(30), default="queued"),
        sa.Column("detail_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "tenant_company_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(180), nullable=False, default="Business Suite"),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("fiscal_year_start_month", sa.Integer(), default=4),
        sa.Column("base_currency", sa.String(12), default="INR"),
        sa.Column("timezone", sa.String(80), default="Asia/Calcutta"),
        sa.Column("tax_defaults_json", sa.JSON()),
        sa.Column("business_hours_json", sa.JSON()),
        sa.Column("numbering_settings_json", sa.JSON()),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "tenant_feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feature_key", sa.String(120), nullable=False),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("upgrade_message", sa.String(255)),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("feature_key"),
    )
    op.create_table(
        "tenant_subscription_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("features_json", sa.JSON()),
        sa.Column("active", sa.Boolean(), default=True),
        *_timestamps(),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("tenant_subscription_plans.id", ondelete="SET NULL")),
        sa.Column("edition", sa.String(60), default="ultimate"),
        sa.Column("status", sa.String(30), default="active"),
        sa.Column("admin_override", sa.Boolean(), default=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "tenant_usage_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("metric_key", sa.String(120), nullable=False),
        sa.Column("metric_value", sa.Integer(), default=0),
        sa.Column("period", sa.String(30), default="current"),
        sa.Column("detail_json", sa.JSON()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "mobile_sales_visit_checkins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer()),
        sa.Column("deal_id", sa.Integer()),
        sa.Column("customer_name", sa.String(180), nullable=False),
        sa.Column("latitude", sa.String(40)),
        sa.Column("longitude", sa.String(40)),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(30), default="checked_in"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
    )


def downgrade() -> None:
    for table_name in (
        "mobile_sales_visit_checkins",
        "tenant_usage_metrics",
        "tenant_subscriptions",
        "tenant_subscription_plans",
        "tenant_feature_flags",
        "tenant_company_settings",
        "sandbox_copy_jobs",
        "sandbox_environments",
        "marketplace_installs",
        "marketplace_apps",
        "developer_apps",
        "developer_api_logs",
        "developer_webhook_deliveries",
        "developer_webhooks",
        "developer_api_keys",
        "portal_activity_logs",
        "portal_partner_links",
        "portal_customer_links",
        "portal_sessions",
        "portal_access_grants",
        "portal_users",
        "portal_roles",
    ):
        op.drop_table(table_name)
