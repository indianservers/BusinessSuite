"""Workspace task collections reuse task permissions without requiring a user project."""
from alembic import op
import sqlalchemy as sa

revision = "20261031_046_general_tasks"
down_revision = "20261031_045_task_groups"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pms_projects", sa.Column("is_task_collection", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("uq_pms_workspace_task_collection", "pms_projects", ["workspace_id"], unique=True,
        postgresql_where=sa.text("is_task_collection = true"), sqlite_where=sa.text("is_task_collection = 1"))


def downgrade():
    op.drop_index("uq_pms_workspace_task_collection", table_name="pms_projects")
    op.drop_column("pms_projects", "is_task_collection")
