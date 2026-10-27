"""Owner-only personal notes; frozen DDL must not import future ORM columns."""
from alembic import op
import sqlalchemy as sa
revision = "20261024_011"
down_revision = "20261024_010"
branch_labels = None
depends_on = None


def upgrade():
    available = sa.inspect(op.get_bind()).get_table_names()
    if "pms_private_notes" not in available:
        op.create_table("pms_private_notes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(180), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("pms_projects.id", ondelete="SET NULL")),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("pms_tasks.id", ondelete="SET NULL")),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("pinned", sa.Boolean(), nullable=False),
            sa.Column("archived", sa.Boolean(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True)))
        op.create_index("ix_pms_private_notes_owner_id", "pms_private_notes", ["owner_id"])
    if "pms_private_note_revisions" not in available:
        op.create_table("pms_private_note_revisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("note_id", sa.Integer(), sa.ForeignKey("pms_private_notes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(180), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("note_id", "version", name="uq_private_note_revision"))
        op.create_index("ix_pms_private_note_revisions_note_id", "pms_private_note_revisions", ["note_id"])


def downgrade():
    op.drop_table("pms_private_note_revisions")
    op.drop_table("pms_private_notes")
