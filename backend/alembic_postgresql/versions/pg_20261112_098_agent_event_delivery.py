"""Index and deduplicate native event deliveries on existing scheduler storage."""
from alembic import op
import sqlalchemy as sa
revision='pg_20261112_098_event_delivery'
down_revision='pg_20261111_097_agent_schedules'
branch_labels=depends_on=None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table('automation_scheduled_jobs'):return
    table=sa.Table('automation_scheduled_jobs',sa.MetaData(),sa.Column('organization_id',sa.Integer),
        sa.Column('created_by',sa.Integer),sa.Column('job_type',sa.String),sa.Column('payload_json',sa.JSON))
    subscription=table.c.payload_json['event_source']['subscription_id'].as_integer()
    source=table.c.payload_json['event_source']['source_id'].as_integer()
    predicate=sa.and_(table.c.job_type=='ai_agent_schedule',subscription.is_not(None))
    index=sa.Index('uq_ai_agent_event_delivery',table.c.organization_id,table.c.created_by,subscription,source,
        unique=True,postgresql_where=predicate,sqlite_where=predicate)
    op.execute(sa.schema.CreateIndex(index,if_not_exists=True))


def downgrade():
    op.drop_index('uq_ai_agent_event_delivery',table_name='automation_scheduled_jobs',if_exists=True)
