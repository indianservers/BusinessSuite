"""Allow several workspace collaborators to share a task."""
from alembic import op
import sqlalchemy as sa

revision = "pg_20261022_004"
down_revision = "pg_20261022_003"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("pms_task_assignees"):
        op.create_table("pms_task_assignees",
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("pms_tasks.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True))
        op.create_index("ix_pms_task_assignees_user_id", "pms_task_assignees", ["user_id"])
    op.execute("INSERT INTO pms_task_assignees (task_id, user_id) SELECT id, assignee_user_id FROM pms_tasks t WHERE assignee_user_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM pms_task_assignees a WHERE a.task_id=t.id AND a.user_id=t.assignee_user_id)")


def downgrade():
    op.drop_table("pms_task_assignees")
