"""Provider credentials, task operator runs and API telemetry."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261023_009"
down_revision = "pg_20261023_008"
branch_labels = None
depends_on = None


def upgrade():
    def create_if_missing(name, *columns):
        if not sa.inspect(op.get_bind()).has_table(name):
            op.create_table(name, *columns)

    create_if_missing("ai_operator_providers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_key", sa.String(100), nullable=False, index=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("data_sharing_allowed", sa.Boolean(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("input_price", sa.Numeric(14, 6)),
        sa.Column("output_price", sa.Numeric(14, 6)),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("scope_key", "provider", name="uq_operator_provider_scope"))
    create_if_missing("ai_operator_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_key", sa.String(100), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("pms_projects.id"), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("input_mode", sa.String(10), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("selection", sa.JSON(), nullable=False),
        sa.Column("snapshots", sa.JSON(), nullable=False),
        sa.Column("plan", sa.JSON()),
        sa.Column("plan_hash", sa.String(64)),
        sa.Column("approval_id", sa.Integer(), sa.ForeignKey("ai_action_approvals.id")),
        sa.Column("result", sa.JSON()),
        sa.Column("error_code", sa.String(60)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "request_key", name="uq_operator_command_request"))
    create_if_missing("ai_operator_api_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_key", sa.String(100), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("ai_operator_runs.id"), index=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(60)),
        sa.Column("http_status", sa.Integer()),
        sa.Column("provider_request_id", sa.String(180)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost", sa.Numeric(18, 8)),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True))


def downgrade():
    op.drop_table("ai_operator_api_logs")
    op.drop_table("ai_operator_runs")
    op.drop_table("ai_operator_providers")
