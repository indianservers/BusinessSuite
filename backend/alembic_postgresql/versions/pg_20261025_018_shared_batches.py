"""Shared employee batches and verified application lifecycle."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261025_018_shared_batches'
down_revision='pg_20261025_017_intern_pms'
branch_labels=None
depends_on=None

def upgrade():
    from app.apps.interns_hub.management_models import ApplicationEvent,ApplicationDocument
    bind=op.get_bind()
    additions={
        'intern_task_schedules':[sa.Column('interval_days',sa.Integer(),nullable=False,server_default='1')],
        'intern_hub_reports':[sa.Column('task_entries',sa.JSON()),sa.Column('evidence',sa.JSON()),sa.Column('in_progress',sa.Text()),sa.Column('submitted_at',sa.DateTime(timezone=True))],
        'intern_report_reviews':[sa.Column('report_snapshot',sa.JSON())],
        'intern_batches':[sa.Column('batch_type',sa.String(20),nullable=False,server_default='Intern'),sa.Column('coordinator_user_id',sa.Integer()),sa.Column('project_ids',sa.JSON()),sa.Column('task_templates',sa.JSON())],
        'intern_hub_applications':[sa.Column('organization_id',sa.Integer(),nullable=False,server_default='1'),sa.Column('lifecycle',sa.String(40),nullable=False,server_default='Pending Verification')],
        'pms_task_assignees':[sa.Column('progress_percent',sa.Integer(),nullable=False,server_default='0'),sa.Column('work_notes',sa.Text()),sa.Column('cancelled_at',sa.DateTime(timezone=True))]}
    for table,columns in additions.items():
        existing={c['name'] for c in sa.inspect(bind).get_columns(table)}
        for column in columns:
            if column.name not in existing:op.add_column(table,column)
    for model in [ApplicationEvent,ApplicationDocument]:model.__table__.create(bind,checkfirst=True)

def downgrade():
    pass # Preserve approval, document and membership history.
