"""Owner-only personal notes and revision history."""
from alembic import op
revision = "pg_20261024_011"
down_revision = "pg_20261024_010"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.project_management.models import PMSNote, PMSNoteRevision
    for model in (PMSNote, PMSNoteRevision):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table("pms_private_note_revisions")
    op.drop_table("pms_private_notes")
