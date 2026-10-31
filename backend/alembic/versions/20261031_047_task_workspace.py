"""Persist task collaboration updates and blockers without rewriting existing work."""
from alembic import op
import sqlalchemy as sa
revision = "20261031_047_task_workspace"
down_revision = "20261031_046_general_tasks"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("pms_task_watchers", sa.Column("task_id", sa.Integer(), sa.ForeignKey("pms_tasks.id", ondelete="CASCADE"), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("pms_task_read_positions", sa.Column("task_id", sa.Integer(), sa.ForeignKey("pms_tasks.id", ondelete="CASCADE"), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True), sa.Column("last_comment_id", sa.Integer(), nullable=False))

    op.add_column("pms_comments", sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("pms_comment_reactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("comment_id", sa.Integer(), sa.ForeignKey("pms_comments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("emoji", sa.String(20), nullable=False), sa.UniqueConstraint("comment_id", "user_id", "emoji"))
    op.create_index("ix_pms_comment_reactions_comment_id", "pms_comment_reactions", ["comment_id"])

    op.create_table("pms_task_workspace_state",
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("pms_tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("progress", sa.Integer(), nullable=False), sa.Column("progress_mode", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False))
    op.create_table("pms_task_update_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(20), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("progress", sa.Integer()), sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("follow_up_date", sa.Date()), sa.Column("category", sa.String(40)), sa.Column("severity", sa.String(20)),
        sa.Column("responsible_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("assistance", sa.Text()), sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("file_ids", sa.JSON(), nullable=False), sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_index("ix_pms_task_update_entries_task_id", "pms_task_update_entries", ["task_id"])

def downgrade():
    op.drop_table("pms_task_read_positions")
    op.drop_table("pms_task_watchers")
    op.drop_table("pms_comment_reactions")
    op.drop_column("pms_comments", "is_resolved")
    op.drop_table("pms_task_update_entries")
    op.drop_table("pms_task_workspace_state")
