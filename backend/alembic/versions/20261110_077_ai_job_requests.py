"""Deduplicate assistant schedules and source extraction requests."""
from alembic import op
import sqlalchemy as sa

revision = '20261110_077_ai_job_requests'
down_revision = '20261110_076_crm_business_profile'
branch_labels = depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table('automation_scheduled_jobs'):
        return
    table = sa.Table('automation_scheduled_jobs', sa.MetaData(), sa.Column('organization_id', sa.Integer), sa.Column('created_by', sa.Integer),
                     sa.Column('job_type', sa.String), sa.Column('payload_json', sa.JSON))
    predicate = table.c.job_type.in_(['ai_reminder', 'ai_commitments'])
    index = sa.Index('uq_ai_job_request', table.c.organization_id, table.c.created_by, table.c.job_type,
                     table.c.payload_json['ai_request_key'].as_string(), unique=True,
                     postgresql_where=predicate, sqlite_where=predicate)
    op.execute(sa.schema.CreateIndex(index, if_not_exists=True))


def downgrade():
    op.drop_index('uq_ai_job_request', table_name='automation_scheduled_jobs', if_exists=True)
