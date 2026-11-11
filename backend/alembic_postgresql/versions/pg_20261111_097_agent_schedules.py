"""Deduplicate reviewed saved-agent schedules on existing scheduler storage."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261111_097_agent_schedules'
down_revision='pg_20261110_096_nlp_training'
branch_labels=depends_on=None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table('automation_scheduled_jobs'):return
    table=sa.Table('automation_scheduled_jobs',sa.MetaData(),sa.Column('organization_id',sa.Integer),
        sa.Column('created_by',sa.Integer),sa.Column('job_type',sa.String),sa.Column('payload_json',sa.JSON))
    predicate=table.c.job_type=='ai_agent_schedule'
    index=sa.Index('uq_ai_agent_schedule_request',table.c.organization_id,table.c.created_by,table.c.job_type,
        table.c.payload_json['ai_request_key'].as_string(),unique=True,postgresql_where=predicate,sqlite_where=predicate)
    op.execute(sa.schema.CreateIndex(index,if_not_exists=True))


def downgrade():
    op.drop_index('uq_ai_agent_schedule_request',table_name='automation_scheduled_jobs',if_exists=True)
