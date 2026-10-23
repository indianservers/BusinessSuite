"""Persist module schedule starts, dependency graphs and optimistic revisions."""
from alembic import op
import sqlalchemy as sa

revision = "20261023_008"
down_revision = "20261023_007"
branch_labels = None
depends_on = None


def upgrade():
    if "schedule_boards" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "schedule_boards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_key", sa.String(100), nullable=False),
        sa.Column("module", sa.String(30), nullable=False),
        sa.Column("source", sa.String(60), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("starts", sa.JSON(), nullable=False),
        sa.Column("links", sa.JSON(), nullable=False),
        sa.UniqueConstraint("tenant_key", "module", "source", name="uq_schedule_board_scope"),
    )


def downgrade():
    if "schedule_boards" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("schedule_boards")
