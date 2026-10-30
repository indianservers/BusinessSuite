"""PMS blocked work and completion evidence, without changing existing tasks."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261031_043_pms_execution"
down_revision = "pg_20261028_042_custody"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("pms_task_execution",
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("pms_tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("blocked_reason", sa.Text()),
        sa.Column("responsible_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("review_date", sa.Date()),
        sa.Column("evidence_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evidence", sa.Text()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    op.drop_table("pms_task_execution")
