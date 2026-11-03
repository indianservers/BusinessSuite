"""Customer conversation workflow and per-user reading positions."""
revision = 'pg_20261103_068_comms_engagement'
down_revision = 'pg_20261103_067_customer_comms'
branch_labels = None
depends_on = None


def upgrade():
    from alembic import op
    import sqlalchemy as sa
    op.create_table('communication_conversation_workflows',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False,index=True),
        sa.Column('branch_id',sa.Integer(),sa.ForeignKey('branches.id'),nullable=False,index=True),
        sa.Column('kind',sa.String(20),nullable=False),sa.Column('record_id',sa.Integer(),nullable=False),
        sa.Column('assigned_user_id',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('handover_note',sa.Text(),nullable=False),sa.Column('status',sa.String(20),nullable=False),
        sa.Column('updated_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id','kind','record_id',name='uq_communication_workflow'))
    op.create_table('communication_conversation_reading',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False,index=True),
        sa.Column('branch_id',sa.Integer(),sa.ForeignKey('branches.id'),nullable=False,index=True),
        sa.Column('kind',sa.String(20),nullable=False),sa.Column('record_id',sa.Integer(),nullable=False),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('whatsapp_read_id',sa.Integer(),nullable=False),sa.Column('email_read_id',sa.Integer(),nullable=False),
        sa.Column('snoozed_until',sa.DateTime(timezone=True)),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id','kind','record_id','user_id',name='uq_communication_reading'))


def downgrade():
    raise RuntimeError('Retain customer workflow and reading history; restore through a reviewed recovery')
