"""Owner portal operations, staff, customer lifecycle and reporting."""
from alembic import op
import sqlalchemy as sa

revision = "owner_002"
down_revision = "owner_001"
branch_labels = depends_on = None


def upgrade():
    for column in [sa.Column("name", sa.String(150), nullable=False, server_default="Platform owner"),
        sa.Column("role", sa.String(30), nullable=False, server_default="owner"),
        sa.Column("permissions", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("assigned_only", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("preferences", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True))]:
        op.add_column("platform_admins", column)
    for column in [sa.Column("assigned_to", sa.Integer, sa.ForeignKey("platform_admins.id")),
        sa.Column("source", sa.String(80), nullable=False, server_default="website"),
        sa.Column("campaign", sa.String(120), nullable=False, server_default=""),
        sa.Column("tags", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("consent_evidence", sa.Text, nullable=False, server_default="Public trial request consent"),
        sa.Column("workflow", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("archived_at", sa.DateTime(timezone=True)), sa.Column("previous_status", sa.String(30)),
        sa.Column("legal_hold", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True))]:
        op.add_column("platform_signup_requests", column)
    # New tables are snapshotted here; future revisions must not change this list.
    op.create_table("platform_sessions", sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("admin_id", sa.Integer, sa.ForeignKey("platform_admins.id"), nullable=False, index=True),
        sa.Column("ip", sa.String(80), nullable=False), sa.Column("device", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("platform_events", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("admin_id", sa.Integer, sa.ForeignKey("platform_admins.id")),
        sa.Column("action", sa.String(100), nullable=False, index=True), sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.Integer), sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("before", sa.JSON, nullable=False), sa.Column("after", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True))
    op.create_table("platform_plans", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("config", sa.JSON, nullable=False), sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("platform_tenants", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("signup_id", sa.Integer, sa.ForeignKey("platform_signup_requests.id"), unique=True, nullable=False),
        sa.Column("company_id", sa.Integer, unique=True, nullable=False), sa.Column("name", sa.String(180), nullable=False),
        sa.Column("admin_email", sa.String(150), nullable=False), sa.Column("status", sa.String(30), nullable=False, index=True),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("platform_plans.id")),
        sa.Column("assigned_to", sa.Integer, sa.ForeignKey("platform_admins.id")),
        sa.Column("config", sa.JSON, nullable=False), sa.Column("usage", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("platform_records", sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False, index=True), sa.Column("title", sa.String(180), nullable=False),
        sa.Column("state", sa.String(30), nullable=False, index=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("platform_admins.id")),
        sa.Column("signup_id", sa.Integer, sa.ForeignKey("platform_signup_requests.id")),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("platform_tenants.id")),
        sa.Column("token_hash", sa.String(64), unique=True), sa.Column("data", sa.JSON, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    for name in ["platform_records", "platform_tenants", "platform_plans", "platform_events", "platform_sessions"]:
        op.drop_table(name)
    for name in ["deleted_at", "legal_hold", "previous_status", "archived_at", "version", "workflow", "consent_evidence", "tags", "campaign", "source", "assigned_to"]:
        op.drop_column("platform_signup_requests", name)
    for name in ["reviewed_at", "preferences", "assigned_only", "permissions", "role", "name"]:
        op.drop_column("platform_admins", name)
