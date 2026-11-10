"""Create a scoped query curation table; no historical prompts are backfilled."""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261110_095_nlp_queries'
down_revision = 'pg_20261110_094_ai_job_requests'
branch_labels = depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('ai_nlp_queries'):
        return
    op.create_table('ai_nlp_queries',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('company_id',sa.Integer(),sa.ForeignKey('companies.id',ondelete='CASCADE'),nullable=False),
        sa.Column('branch_id',sa.Integer()),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('workspace_id',sa.Integer(),sa.ForeignKey('pms_workspaces.id',ondelete='SET NULL')),
        sa.Column('project_id',sa.Integer()),
        sa.Column('suite_run_id',sa.Integer(),sa.ForeignKey('ai_suite_runs.id',ondelete='SET NULL')),
        sa.Column('request_key_hash',sa.String(64),nullable=False),
        sa.Column('submission_hash',sa.String(64),nullable=False),
        sa.Column('query_text',sa.Text(),nullable=False),
        sa.Column('normalized_query',sa.Text(),nullable=False),
        sa.Column('query_hash',sa.String(64),nullable=False),
        sa.Column('module',sa.String(20),nullable=False),
        sa.Column('provider',sa.String(20),nullable=False),
        sa.Column('input_mode',sa.String(20),nullable=False),
        sa.Column('predicted_intent',sa.String(80)),
        sa.Column('confidence',sa.Float()),
        sa.Column('model_version',sa.String(160)),
        sa.Column('outcome',sa.String(40),nullable=False,server_default='received'),
        sa.Column('error_code',sa.String(80)),
        sa.Column('review_status',sa.String(20),nullable=False,server_default='pending'),
        sa.Column('reviewed_module',sa.String(20)),
        sa.Column('reviewed_intent',sa.String(80)),
        sa.Column('training_text',sa.Text()),
        sa.Column('privacy_reviewed',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('reviewed_by',sa.Integer(),sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('reviewed_at',sa.DateTime(timezone=True)),
        sa.Column('revision',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('user_id','request_key_hash',name='uq_nlp_query_request'),
        sa.UniqueConstraint('suite_run_id',name='uq_nlp_query_run'),
        sa.CheckConstraint("review_status IN ('pending','approved','rejected','deleted')",name='ck_nlp_review_status'),
        sa.CheckConstraint('revision >= 1',name='ck_nlp_revision'))
    op.create_index('ix_nlp_query_review_scope','ai_nlp_queries',['company_id','branch_id','module','review_status','id'])
    op.create_index('ix_ai_nlp_queries_query_hash','ai_nlp_queries',['query_hash'])


def downgrade():
    if sa.inspect(op.get_bind()).has_table('ai_nlp_queries'):
        op.drop_table('ai_nlp_queries')
