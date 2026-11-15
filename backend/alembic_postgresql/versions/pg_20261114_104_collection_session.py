"""Bind service payment mappings to their actual collection register.

Native receipt amounts and native register totals remain untouched. Future rows
have no default: a later collection must name its actual register explicitly.
"""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261114_104_collection'
down_revision = 'pg_20261114_103_service_checkout'
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    name = 'srm_pos_checkout_payments'
    if not inspector.has_table(name):
        raise RuntimeError('Service checkout schema must be installed before collection registers')
    was_missing = 'collection_session_id' not in {column['name'] for column in inspector.get_columns(name)}
    if was_missing:
        if connection.dialect.name == 'sqlite':
            # SQLite supports an additive nullable REFERENCES column directly;
            # avoid rebuilding sources with generated scope columns and history.
            connection.exec_driver_sql('ALTER TABLE srm_pos_checkout_payments ADD COLUMN collection_session_id INTEGER REFERENCES srm_pos_sessions(id) ON DELETE RESTRICT')
        else:
            op.add_column(name, sa.Column('collection_session_id', sa.Integer(), nullable=True))
    inspector = sa.inspect(connection)
    if connection.dialect.name != 'sqlite' and not any(
            fk['constrained_columns'] == ['collection_session_id'] for fk in inspector.get_foreign_keys(name)):
        op.create_foreign_key('fk_checkout_payment_collection_session', name, 'srm_pos_sessions', ['collection_session_id'], ['id'], ondelete='RESTRICT')
    # No historical backfill is provable: initial and later receipts use the
    # same native numbering and contain no immutable register reference. The
    # checkout's original register is not collection provenance. Timestamps
    # (including transaction/second precision equality) cannot establish it.
    # Preserve historical NULL and every explicit binding; re-running this
    # revision must never adopt future intentional non-counter NULL payments.


def downgrade():
    # Retain issued collection provenance; removing it would erase cash history.
    pass
