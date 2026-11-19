"""Recoverable saved reports and optimistic revisions."""
from alembic import op
import sqlalchemy as sa
revision='20261118_087_report_crud'
down_revision='20261118_086_srm_reporting'
branch_labels=depends_on=None

def upgrade():
    op.add_column('srm_report_views',sa.Column('revision',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('srm_report_views',sa.Column('deleted_at',sa.DateTime(timezone=True),nullable=True))

def downgrade():
    op.drop_column('srm_report_views','deleted_at')
    op.drop_column('srm_report_views','revision')
