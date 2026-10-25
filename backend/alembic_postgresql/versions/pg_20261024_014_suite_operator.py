"""Multi-module operator and explicit workspace credential inheritance."""
from alembic import op
import sqlalchemy as sa
revision = 'pg_20261024_014_suite'
down_revision = 'pg_20261024_013'
branch_labels = None
depends_on = None


def upgrade():
    from app.ai_operator.suite_models import SuiteRun
    bind = op.get_bind()
    SuiteRun.__table__.create(bind, checkfirst=True)
    for table, column in [
        ('ai_operator_providers', sa.Column('allow_workspace_inheritance', sa.Boolean(), nullable=False, server_default=sa.false())),
        ('ai_operator_api_logs', sa.Column('module', sa.String(40), nullable=False, server_default='PMS')),
        ('ai_operator_api_logs', sa.Column('suite_run_id', sa.Integer(), nullable=True)),
    ]:
        if column.name not in {c['name'] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table, column)
    if 'ix_ai_operator_api_logs_suite_run_id' not in {i['name'] for i in sa.inspect(bind).get_indexes('ai_operator_api_logs')}:
        op.create_index('ix_ai_operator_api_logs_suite_run_id', 'ai_operator_api_logs', ['suite_run_id'])


def downgrade():
    # Retain approval and usage evidence; rolling back code must not erase receipts.
    pass
