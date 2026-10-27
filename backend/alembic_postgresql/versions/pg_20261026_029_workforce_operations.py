"""Resumable workforce operations and acknowledged notices."""
from alembic import op

revision = "pg_20261026_029_workforce_ops"
down_revision = "pg_20261026_028_notes_workspace"
branch_labels = None
depends_on = None


def upgrade():
    from app.apps.interns_hub.operations_models import WorkforceJob, WorkforceMessage, WorkforceJobFailure
    WorkforceJob.__table__.create(op.get_bind(), checkfirst=True)
    WorkforceMessage.__table__.create(op.get_bind(), checkfirst=True)
    WorkforceJobFailure.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    op.drop_table("workforce_job_failures")
    op.drop_table("workforce_messages")
    op.drop_table("workforce_jobs")
