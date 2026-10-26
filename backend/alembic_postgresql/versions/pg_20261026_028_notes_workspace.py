"""Private folder hierarchy, favorites, explicit sharing and note audit events."""
from alembic import op
import sqlalchemy as sa
revision = "pg_20261026_028_notes_workspace"
down_revision = "pg_20261026_027_ai_security"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.project_management.models import PMSNoteFolder, PMSNoteShare, PMSNoteEvent
    PMSNoteFolder.__table__.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("pms_private_notes") as batch:
        batch.add_column(sa.Column("folder_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_foreign_key("fk_pms_note_folder", "pms_note_folders", ["folder_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_pms_private_notes_folder_id", ["folder_id"])
    PMSNoteShare.__table__.create(op.get_bind(), checkfirst=True)
    PMSNoteEvent.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table("pms_note_events")
    op.drop_table("pms_note_shares")
    with op.batch_alter_table("pms_private_notes") as batch:
        batch.drop_index("ix_pms_private_notes_folder_id")
        batch.drop_constraint("fk_pms_note_folder", type_="foreignkey")
        batch.drop_column("favorite")
        batch.drop_column("folder_id")
    op.drop_table("pms_note_folders")
