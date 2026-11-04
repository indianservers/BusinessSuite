"""Frozen additive migration shared by the SQLite and PostgreSQL chains."""
import sqlalchemy as sa


def upgrade(op):
    op.create_table('pms_task_record_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('pms_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('crm_contacts.id', ondelete='RESTRICT')),
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('crm_leads.id', ondelete='RESTRICT')),
        sa.Column('linked_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint('(contact_id IS NOT NULL AND lead_id IS NULL) OR (lead_id IS NOT NULL AND contact_id IS NULL)', name='ck_pms_task_record_target'),
        sa.UniqueConstraint('task_id', 'contact_id', name='uq_pms_task_contact'),
        sa.UniqueConstraint('task_id', 'lead_id', name='uq_pms_task_lead'))
    op.create_index('ix_pms_task_record_links_task_id', 'pms_task_record_links', ['task_id'])
    op.create_index('ix_pms_task_contact_scope', 'pms_task_record_links', ['organization_id', 'contact_id', 'task_id'])
    op.create_index('ix_pms_task_lead_scope', 'pms_task_record_links', ['organization_id', 'lead_id', 'task_id'])


def downgrade(op):
    op.drop_table('pms_task_record_links')
