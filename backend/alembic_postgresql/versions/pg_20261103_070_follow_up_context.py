"""Bring follow-up context and reminder delivery fields in line with models."""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261103_070_followup_ctx'
down_revision = 'pg_20261103_069_comms_tenants'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {c['name'] for c in sa.inspect(bind).get_columns('service_follow_ups')}
    for name, target in {
        'order_line_id': 'srm_sales_order_lines', 'lead_id': 'crm_leads',
        'contact_id': 'crm_contacts', 'deal_id': 'crm_deals',
        'quotation_id': 'crm_quotations', 'invoice_id': 'srm_invoices',
        'assigned_team_id': 'crm_teams',
    }.items():
        if name not in columns:
            op.add_column('service_follow_ups', sa.Column(name, sa.Integer(), nullable=True))
            op.create_foreign_key('fk_followup_'+name, 'service_follow_ups', target, [name], ['id'])
            op.create_index('ix_service_follow_ups_'+name, 'service_follow_ups', [name])
    columns = {c['name'] for c in sa.inspect(bind).get_columns('service_follow_up_reminders')}
    for column in [
        sa.Column('delivery_status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('attempt_history', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
    ]:
        if column.name not in columns:
            op.add_column('service_follow_up_reminders', column)


def downgrade():
    raise RuntimeError('Retain follow-up delivery history; use a reviewed recovery.')
