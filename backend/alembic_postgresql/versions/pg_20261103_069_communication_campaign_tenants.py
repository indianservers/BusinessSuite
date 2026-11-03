"""Explicit company ownership for campaign work and email attachment metadata."""
revision='pg_20261103_069_comms_tenants'
down_revision='pg_20261103_068_comms_engagement'
branch_labels=None
depends_on=None


def upgrade():
    from alembic import op
    import sqlalchemy as sa
    tables=['communication_campaigns','communication_campaign_members','communication_campaign_sends','communication_email_attachments']
    for name in tables:
        op.add_column(name,sa.Column('organization_id',sa.Integer(),nullable=True))
        op.create_foreign_key('fk_'+name+'_organization',name,'companies',['organization_id'],['id'])
        op.create_index('ix_'+name+'_organization_id',name,['organization_id'])
    # Preserve explicit ownership first; infer only from a verified parent.
    # Unresolved legacy rows stay unclaimed instead of defaulting to company 1.
    op.execute("UPDATE communication_campaigns c SET organization_id=o.company_id FROM security_resource_ownership o WHERE o.resource_table='communication_campaigns' AND o.resource_id=c.id")
    op.execute("UPDATE communication_campaigns c SET organization_id=t.organization_id FROM communication_email_templates t WHERE c.organization_id IS NULL AND c.template_id=t.id AND t.organization_id IS NOT NULL")
    op.execute('UPDATE communication_campaign_members m SET organization_id=c.organization_id FROM communication_campaigns c WHERE m.campaign_id=c.id')
    op.execute('UPDATE communication_campaign_sends s SET organization_id=c.organization_id FROM communication_campaigns c WHERE s.campaign_id=c.id')
    op.execute('UPDATE communication_email_attachments a SET organization_id=m.organization_id FROM communication_email_messages m WHERE a.message_id=m.id')


def downgrade():
    raise RuntimeError('Retain explicit company ownership; use a reviewed recovery')
