"""Durable operator jobs, checkpoints, events and revision context."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261024_001"
down_revision = "pg_20261023_009"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("ai_operator_runs")}
    additions = [sa.Column("background", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("execution_mode", sa.String(20), nullable=False, server_default="atomic"),
        sa.Column("parent_run_id", sa.Integer(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("timezone", sa.String(80), nullable=False, server_default="Asia/Kolkata")]
    for column in additions:
        if column.name not in columns:
            op.add_column("ai_operator_runs", column)
    # Explicit named FK; SQLite's migration test uses batch recreation.
    fks = {f["name"] for f in sa.inspect(op.get_bind()).get_foreign_keys("ai_operator_runs")}
    if "fk_operator_parent_run" not in fks:
        with op.batch_alter_table("ai_operator_runs") as batch:
            batch.create_foreign_key("fk_operator_parent_run", "ai_operator_runs", ["parent_run_id"], ["id"])
    if not sa.inspect(op.get_bind()).has_table("ai_operator_jobs"):
        op.create_table("ai_operator_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("ai_operator_runs.id"), nullable=False, index=True),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("dedupe_key", sa.String(100), nullable=False, unique=True),
            sa.Column("status", sa.String(20), nullable=False, index=True),
            sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("failures", sa.Integer(), nullable=False),
            sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("lease_token", sa.String(64)), sa.Column("lease_until", sa.DateTime(timezone=True)),
            sa.Column("error_code", sa.String(60)))
    if not sa.inspect(op.get_bind()).has_table("ai_operator_steps"):
        op.create_table("ai_operator_steps", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("ai_operator_runs.id"), nullable=False, index=True),
            sa.Column("position", sa.Integer(), nullable=False), sa.Column("depends_on", sa.JSON(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
            sa.Column("receipt", sa.JSON()), sa.Column("error_code", sa.String(60)),
            sa.UniqueConstraint("run_id", "position", name="uq_operator_step_position"))
    if not sa.inspect(op.get_bind()).has_table("ai_operator_events"):
        op.create_table("ai_operator_events", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("ai_operator_runs.id"), nullable=False, index=True),
            sa.Column("event_type", sa.String(50), nullable=False), sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))


def downgrade():
    for name in ("ai_operator_events", "ai_operator_steps", "ai_operator_jobs"):
        op.drop_table(name)
    with op.batch_alter_table("ai_operator_runs") as batch:
        batch.drop_constraint("fk_operator_parent_run", type_="foreignkey")
        for name in ("timezone", "revision", "parent_run_id", "execution_mode", "background"):
            batch.drop_column(name)
