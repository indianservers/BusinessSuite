"""Telegram memory and exact action approvals."""
revision = '20261116_085_telegram_experience'
down_revision = '20261116_084_telegram_ops'
branch_labels = depends_on = None
from alembic import op
import sqlalchemy as sa


def upgrade():
    for table in ['power_telegram_identities', 'power_telegram_link_challenges']:
        op.add_column(table, sa.Column('customer_id', sa.Integer(), nullable=True))
    op.add_column('power_telegram_conversations', sa.Column('context', sa.JSON(), nullable=False, server_default='{}'))
    op.create_table('power_telegram_action_approvals',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('resource_id',sa.Integer(),sa.ForeignKey('power_apps_resources.id'),nullable=False,index=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False),
        sa.Column('environment',sa.String(20),nullable=False),
        sa.Column('conversation_id',sa.Integer(),sa.ForeignKey('power_telegram_conversations.id'),nullable=False),
        sa.Column('identity_id',sa.Integer(),sa.ForeignKey('power_telegram_identities.id'),nullable=False),
        sa.Column('token_hash',sa.String(64),nullable=False,unique=True),
        sa.Column('kind',sa.String(30),nullable=False),sa.Column('operation',sa.JSON(),nullable=False),
        sa.Column('operation_hash',sa.String(64),nullable=False),
        sa.Column('status',sa.String(20),nullable=False,server_default='pending'),
        sa.Column('result',sa.JSON(),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))


def downgrade():
    op.drop_table('power_telegram_action_approvals')
    op.drop_column('power_telegram_conversations','context')
    for table in ['power_telegram_identities', 'power_telegram_link_challenges']:
        op.drop_column(table, 'customer_id')
