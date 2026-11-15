"""Retain exact Pharma sale quantities without narrowing historical capacity."""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261116_118_pharma_qty'
down_revision = 'pg_20261115_117_rest_cancel'
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    table = 'srm_sales_order_lines'
    if not inspector.has_table(table):
        raise RuntimeError('Native sales-order lines must exist before quantity upgrade')
    column = next((item for item in inspector.get_columns(table) if item['name'] == 'quantity'), None)
    if column is None or not isinstance(column['type'], sa.Numeric):
        raise RuntimeError('Native sale quantity requires schema reconciliation')
    if connection.dialect.name == 'sqlite':
        return  # NUMERIC affinity needs no parent-table/history rebuild.
    if connection.dialect.name != 'postgresql':
        raise RuntimeError('Unsupported native sale quantity database')
    precision, scale = column['type'].precision, column['type'].scale
    if precision is None and scale is None:
        return
    if precision is not None and scale is not None and scale >= 3 and precision-scale >= 10:
        return
    if (precision, scale) != (12, 2):
        raise RuntimeError('Native sale quantity capacity requires schema reconciliation')
    op.alter_column(table, 'quantity', existing_type=sa.Numeric(12, 2), type_=sa.Numeric(14, 3))


def downgrade():
    pass  # Never round issued quantities or shrink historical integer capacity.
