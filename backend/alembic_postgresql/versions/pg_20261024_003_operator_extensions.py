"""Operator setup proposals and recurring monitors."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261024_003"
down_revision = "pg_20261024_002"
branch_labels = None
depends_on = None


def upgrade():
    existing = sa.inspect(op.get_bind()).get_table_names()
    if "ai_operator_proposals" not in existing:
        op.create_table("ai_operator_proposals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("scope_key", sa.String(100), nullable=False, index=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("pms_workspaces.id")),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("approval_id", sa.Integer(), sa.ForeignKey("ai_action_approvals.id")),
            sa.Column("request_key", sa.String(100), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("plan_hash", sa.String(64), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("result", sa.JSON()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "request_key", name="uq_operator_proposal_request"))
    if "ai_operator_monitors" not in existing:
        op.create_table("ai_operator_monitors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("pms_projects.id"), nullable=False, index=True),
            sa.Column("scope_key", sa.String(100), nullable=False),
            sa.Column("name", sa.String(180), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("interval_minutes", sa.Integer(), nullable=False),
            sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("finding_hash", sa.String(64)),
            sa.Column("findings", sa.JSON()),
            sa.Column("checked_at", sa.DateTime(timezone=True)),
            sa.Column("error_code", sa.String(60)))


def downgrade():
    op.drop_table("ai_operator_monitors")
    op.drop_table("ai_operator_proposals")
