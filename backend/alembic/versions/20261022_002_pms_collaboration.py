"""Persist workspace notes and team conversations."""
from alembic import op
import sqlalchemy as sa
revision = "20261022_002"
down_revision = "20261022_001"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("pms_workspace_entries"):
        op.create_table("pms_workspace_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("pms_workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("kind", sa.String(12), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("pms_tasks.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False))


def downgrade():
    op.drop_table("pms_workspace_entries")
