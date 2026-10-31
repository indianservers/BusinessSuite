"""Explicit team and batch responsibility; existing individual assignments are untouched."""
from alembic import op
import sqlalchemy as sa

revision = "20261031_045_task_groups"
down_revision = "20261031_044_note_visibility"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("pms_task_group_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("pms_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("task_id", "kind", "target_id"))
    op.create_index("ix_pms_task_group_targets_task_id", "pms_task_group_targets", ["task_id"])
    op.create_index("ix_pms_task_group_targets_target_id", "pms_task_group_targets", ["target_id"])


def downgrade():
    op.drop_table("pms_task_group_targets")
