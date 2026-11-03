"""Route new inbound WhatsApp conversations to an explicit company branch."""
revision = 'pg_20261103_066_wa_branch'
down_revision = 'pg_20261103_065_whatsapp'
branch_labels = None
depends_on = None


def upgrade():
    from alembic import op
    from sqlalchemy import inspect, Column, Integer, ForeignKey
    if 'inbound_branch_id' not in {c['name'] for c in inspect(op.get_bind()).get_columns('suite_whatsapp_connections')}:
        op.add_column('suite_whatsapp_connections', Column('inbound_branch_id', Integer, ForeignKey('branches.id'), nullable=True))


def downgrade():
    raise RuntimeError('Retain customer routing configuration; use a reviewed restore')
