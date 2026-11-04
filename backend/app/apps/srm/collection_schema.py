"""Add collection controls to canonical rows; no replacement financial tables."""
import sqlalchemy as sa


def upgrade(op):
    inspector = sa.inspect(op.get_bind())
    columns = {c['name'] for c in inspector.get_columns('srm_invoices')}
    for column in (
        sa.Column('collection_hold', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('collection_hold_reason', sa.String(500)),
        sa.Column('collection_resume_at', sa.DateTime(timezone=True)),
    ):
        if column.name not in columns:
            op.add_column('srm_invoices', column)
    columns = {c['name'] for c in inspector.get_columns('srm_receipt_allocations')}
    if 'request_id' not in columns:
        op.add_column('srm_receipt_allocations', sa.Column('request_id', sa.String(36)))
    constraints = {c['name'] for c in sa.inspect(op.get_bind()).get_unique_constraints('srm_receipt_allocations')}
    if 'uq_srm_allocation_request' not in constraints:
        with op.batch_alter_table('srm_receipt_allocations') as batch:
            batch.create_unique_constraint('uq_srm_allocation_request', ['receipt_id', 'request_id'])


def downgrade(op):
    with op.batch_alter_table('srm_receipt_allocations') as batch:
        batch.drop_constraint('uq_srm_allocation_request', type_='unique')
        batch.drop_column('request_id')
    for name in ('collection_resume_at', 'collection_hold_reason', 'collection_hold'):
        op.drop_column('srm_invoices', name)
