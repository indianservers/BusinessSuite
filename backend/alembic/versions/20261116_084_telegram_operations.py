"""Telegram identities, native CRM intake, and human handoff."""
revision = '20261116_084_telegram_ops'
down_revision = '20261116_083_employee_categories'
branch_labels = depends_on = None
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('power_telegram_identities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False, index=True),
        sa.Column('environment', sa.String(20), nullable=False),
        sa.Column('resource_id', sa.Integer(), sa.ForeignKey('power_apps_resources.id'), nullable=False),
        sa.Column('telegram_id', sa.String(20), nullable=False),
        sa.Column('interface', sa.String(20), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('employee_id', sa.Integer(), sa.ForeignKey('employees.id')),
        sa.Column('contact_id', sa.Integer()), sa.Column('lead_id', sa.Integer()),
        sa.Column('display_name', sa.String(180), nullable=False, server_default=''),
        sa.Column('verified_at', sa.DateTime(timezone=True)), sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('resource_id','telegram_id','interface', name='uq_telegram_identity'))
    op.create_table('power_telegram_link_challenges',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False),
        sa.Column('environment',sa.String(20),nullable=False),
        sa.Column('resource_id',sa.Integer(),sa.ForeignKey('power_apps_resources.id'),nullable=False),
        sa.Column('token_hash',sa.String(64),nullable=False,unique=True),
        sa.Column('interface',sa.String(20),nullable=False),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('contact_id',sa.Integer()),sa.Column('lead_id',sa.Integer()),
        sa.Column('created_by_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('consumed_at',sa.DateTime(timezone=True)))
    op.create_table('power_telegram_conversations',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False,index=True),
        sa.Column('environment',sa.String(20),nullable=False),
        sa.Column('resource_id',sa.Integer(),sa.ForeignKey('power_apps_resources.id'),nullable=False),
        sa.Column('chat_id',sa.String(20),nullable=False),sa.Column('telegram_id',sa.String(20),nullable=False),
        sa.Column('interface',sa.String(20),nullable=False),
        sa.Column('identity_id',sa.Integer(),sa.ForeignKey('power_telegram_identities.id')),
        sa.Column('status',sa.String(20),nullable=False,server_default='bot'),
        sa.Column('assignee_user_id',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('state',sa.JSON(),nullable=False),sa.Column('lead_id',sa.Integer()),sa.Column('task_id',sa.Integer()),
        sa.Column('last_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('resource_id','chat_id','interface',name='uq_telegram_conversation'))
    op.create_table('power_telegram_messages',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('conversation_id',sa.Integer(),sa.ForeignKey('power_telegram_conversations.id'),nullable=False,index=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False),
        sa.Column('environment',sa.String(20),nullable=False),
        sa.Column('resource_id',sa.Integer(),sa.ForeignKey('power_apps_resources.id'),nullable=False),
        sa.Column('direction',sa.String(20),nullable=False),sa.Column('text',sa.Text(),nullable=False),
        sa.Column('update_id',sa.Integer()),sa.Column('run_id',sa.Integer(),sa.ForeignKey('power_apps_executions.id')),
        sa.Column('created_by_user_id',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('client_key',sa.String(80)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('resource_id','update_id',name='uq_telegram_message_update'),
        sa.UniqueConstraint('conversation_id','client_key',name='uq_telegram_message_client'))


def downgrade():
    for table in ['power_telegram_messages','power_telegram_conversations','power_telegram_link_challenges','power_telegram_identities']:
        op.drop_table(table)
