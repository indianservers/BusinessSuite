"""Recoverable saved reports and optimistic revisions."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261118_126_report_crud'
down_revision='pg_20261118_125_srm_reports'
branch_labels=depends_on=None

def upgrade():
    op.add_column('srm_report_views',sa.Column('revision',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('srm_report_views',sa.Column('deleted_at',sa.DateTime(timezone=True),nullable=True))

def downgrade():
    op.drop_column('srm_report_views','deleted_at')
    op.drop_column('srm_report_views','revision')
