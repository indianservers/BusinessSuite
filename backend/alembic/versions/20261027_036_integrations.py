"""Add isolated encrypted connector records and external-operation journal. No native data changes."""

from alembic import op
import sqlalchemy as sa

revision = "20261027_036_integrations"
down_revision = "20261027_035_power_runtime"
branch_labels = None
depends_on = None


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "power_connector_credentials" not in existing:
        op.create_table(
            "power_connector_credentials",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("connector_id", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("auth_type", sa.String(length=30), nullable=False),
            sa.Column("encrypted_value", sa.Text(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sharing", sa.JSON(), nullable=False),
            sa.Column("hosts", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
        )
    if "power_connector_connections" not in existing:
        op.create_table(
            "power_connector_connections",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("connector_id", sa.String(length=80), nullable=False),
            sa.Column("connector_version", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column(
                "credential_id",
                sa.Integer(),
                sa.ForeignKey("power_connector_credentials.id"),
                nullable=True,
            ),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("scopes", sa.JSON(), nullable=False),
            sa.Column("sharing", sa.JSON(), nullable=False),
            sa.Column("writes_enabled", sa.Boolean(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("health", sa.String(length=30), nullable=False),
            sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("refresh_token", sa.String(length=36), nullable=True),
            sa.Column("refresh_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
        )
        op.create_index(
            "ix_power_connections_scope",
            "power_connector_connections",
            ["organization_id", "environment", "connector_id"],
            unique=False,
        )
    if "power_connector_oauth_states" not in existing:
        op.create_table(
            "power_connector_oauth_states",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "connection_id",
                sa.Integer(),
                sa.ForeignKey("power_connector_connections.id"),
                nullable=False,
            ),
            sa.Column("state_hash", sa.String(length=64), nullable=False),
            sa.Column("encrypted_verifier", sa.Text(), nullable=False),
            sa.Column("redirect_uri", sa.String(length=500), nullable=False),
            sa.Column("scopes", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("connection_revision", sa.Integer(), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.UniqueConstraint("state_hash", name=None),
        )
    if "power_connector_egress_grants" not in existing:
        op.create_table(
            "power_connector_egress_grants",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("host", sa.String(length=253), nullable=False),
            sa.Column("port", sa.Integer(), nullable=False),
            sa.Column("addresses", sa.JSON(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.UniqueConstraint(
                "organization_id",
                "environment",
                "host",
                "port",
                name="uq_power_egress_target",
            ),
        )
    if "power_connector_operations" not in existing:
        op.create_table(
            "power_connector_operations",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "run_id",
                sa.Integer(),
                sa.ForeignKey("power_apps_executions.id"),
                nullable=True,
            ),
            sa.Column(
                "step_id",
                sa.Integer(),
                sa.ForeignKey("power_automation_steps.id"),
                nullable=True,
            ),
            sa.Column(
                "connection_id",
                sa.Integer(),
                sa.ForeignKey("power_connector_connections.id"),
                nullable=False,
            ),
            sa.Column("connector_id", sa.String(length=80), nullable=False),
            sa.Column("action_id", sa.String(length=80), nullable=False),
            sa.Column("operation_key", sa.String(length=64), nullable=False),
            sa.Column("input_hash", sa.String(length=64), nullable=False),
            sa.Column("credential_version", sa.Integer(), nullable=True),
            sa.Column("mutates", sa.Boolean(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("output", sa.JSON(), nullable=True),
            sa.Column("error_category", sa.String(length=60), nullable=True),
            sa.Column("error", sa.String(length=400), nullable=True),
            sa.Column("correlation_id", sa.String(length=64), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.UniqueConstraint("step_id", name=None),
            sa.UniqueConstraint("operation_key", name=None),
        )
        op.create_index(
            "ix_power_operations_monitor",
            "power_connector_operations",
            ["organization_id", "environment", "connector_id", "status"],
            unique=False,
        )
    if "power_connector_requests" not in existing:
        op.create_table(
            "power_connector_requests",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "operation_id",
                sa.Integer(),
                sa.ForeignKey("power_connector_operations.id"),
                nullable=True,
            ),
            sa.Column(
                "connection_id",
                sa.Integer(),
                sa.ForeignKey("power_connector_connections.id"),
                nullable=True,
            ),
            sa.Column("connector_id", sa.String(length=80), nullable=False),
            sa.Column("action_id", sa.String(length=80), nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=True),
            sa.Column("correlation_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=False),
            sa.Column("error_category", sa.String(length=60), nullable=True),
            sa.Column("attempt", sa.Integer(), nullable=False),
            sa.Column("response_preview", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
        )
        op.create_index(
            "ix_power_requests_scope_time",
            "power_connector_requests",
            ["organization_id", "environment", "created_at"],
            unique=False,
        )
    if "power_connector_audit" not in existing:
        op.create_table(
            "power_connector_audit",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("connection_id", sa.Integer(), nullable=True),
            sa.Column("credential_id", sa.Integer(), nullable=True),
            sa.Column(
                "actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column("action", sa.String(length=60), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
        )
    if "power_connector_gates" not in existing:
        op.create_table(
            "power_connector_gates",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "connection_id",
                sa.Integer(),
                sa.ForeignKey("power_connector_connections.id"),
                nullable=False,
            ),
            sa.Column("window_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("request_count", sa.Integer(), nullable=False),
            sa.Column("failures", sa.Integer(), nullable=False),
            sa.Column("open_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("leases", sa.JSON(), nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.UniqueConstraint("connection_id", name=None),
        )
    if "power_connector_custom_actions" not in existing:
        op.create_table(
            "power_connector_custom_actions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column(
                "connection_id",
                sa.Integer(),
                sa.ForeignKey("power_connector_connections.id"),
                nullable=False,
            ),
            sa.Column("request", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("companies.id"),
                nullable=False,
            ),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column(
                "owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
        )


def downgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "power_connector_custom_actions" in existing:
        op.drop_table("power_connector_custom_actions")
    if "power_connector_gates" in existing:
        op.drop_table("power_connector_gates")
    if "power_connector_audit" in existing:
        op.drop_table("power_connector_audit")
    if "power_connector_requests" in existing:
        op.drop_table("power_connector_requests")
    if "power_connector_operations" in existing:
        op.drop_table("power_connector_operations")
    if "power_connector_egress_grants" in existing:
        op.drop_table("power_connector_egress_grants")
    if "power_connector_oauth_states" in existing:
        op.drop_table("power_connector_oauth_states")
    if "power_connector_connections" in existing:
        op.drop_table("power_connector_connections")
    if "power_connector_credentials" in existing:
        op.drop_table("power_connector_credentials")
