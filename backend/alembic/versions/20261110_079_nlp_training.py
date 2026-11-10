"""Server-only NLP dataset storage and durable training-job idempotency."""
from alembic import op
import sqlalchemy as sa
revision='20261110_079_nlp_training'
down_revision='20261110_078_nlp_queries'
branch_labels=depends_on=None


def job_index(training):
    bind=op.get_bind()
    if not sa.inspect(bind).has_table('automation_scheduled_jobs'):return
    op.drop_index('uq_ai_job_request',table_name='automation_scheduled_jobs',if_exists=True)
    t=sa.Table('automation_scheduled_jobs',sa.MetaData(),sa.Column('organization_id',sa.Integer),sa.Column('created_by',sa.Integer),
        sa.Column('job_type',sa.String),sa.Column('payload_json',sa.JSON))
    predicate=t.c.job_type.in_(['ai_reminder','ai_commitments']+(['ai_nlp_training'] if training else []))
    index=sa.Index('uq_ai_job_request',t.c.organization_id,t.c.created_by,t.c.job_type,t.c.payload_json['ai_request_key'].as_string(),
        unique=True,postgresql_where=predicate,sqlite_where=predicate)
    op.execute(sa.schema.CreateIndex(index))


def upgrade():
    if not sa.inspect(op.get_bind()).has_table('ai_nlp_datasets'):
        op.create_table('ai_nlp_datasets',
            sa.Column('id',sa.Integer,primary_key=True),
            sa.Column('company_id',sa.Integer,sa.ForeignKey('companies.id',ondelete='CASCADE'),nullable=False),
            sa.Column('branch_id',sa.Integer,nullable=False),
            sa.Column('workspace_id',sa.Integer,sa.ForeignKey('pms_workspaces.id',ondelete='SET NULL')),
            sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id',ondelete='SET NULL')),
            sa.Column('name',sa.String(180),nullable=False),
            sa.Column('samples',sa.JSON,nullable=False),sa.Column('counts',sa.JSON,nullable=False),
            sa.Column('content_hash',sa.String(64),nullable=False),
            sa.Column('status',sa.String(20),nullable=False,server_default='pending'),
            sa.Column('revision',sa.Integer,nullable=False,server_default='1'),
            sa.Column('reviewed_by',sa.Integer,sa.ForeignKey('users.id',ondelete='SET NULL')),
            sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
        op.create_index('ix_ai_nlp_datasets_company_id','ai_nlp_datasets',['company_id'])
        op.create_index('ix_ai_nlp_datasets_branch_id','ai_nlp_datasets',['branch_id'])
    job_index(True)


def downgrade():
    job_index(False)
    if sa.inspect(op.get_bind()).has_table('ai_nlp_datasets'):op.drop_table('ai_nlp_datasets')
