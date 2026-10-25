"""Private binary attachments and reviewed note-to-task links."""
from alembic import op
revision = "pg_20261024_012"
down_revision = "pg_20261024_011"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.project_management.models import PMSNoteAttachment, PMSNoteTaskLink
    for model in (PMSNoteAttachment, PMSNoteTaskLink):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table("pms_private_note_task_links")
    op.drop_table("pms_private_note_attachments")
