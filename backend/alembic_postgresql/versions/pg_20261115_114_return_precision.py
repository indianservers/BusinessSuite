"""Preserve exact lot quantities in native return lines; activates no workflow."""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261115_114_return_precision'
down_revision = 'pg_20261115_113_restaurant_tabs'
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table('srm_pos_return_lines'):
        raise RuntimeError('Native return lines must be installed before precision upgrade')
    column = next((item for item in inspector.get_columns('srm_pos_return_lines') if item['name'] == 'quantity'), None)
    if column is None or not isinstance(column['type'], sa.Numeric):
        raise RuntimeError('Native return quantity requires schema reconciliation')
    if connection.dialect.name == 'sqlite':
        # SQLite NUMERIC affinity already stores the exact value; rebuilding
        # this parent-linked native table would risk unrelated history.
        return
    if connection.dialect.name != 'postgresql':
        raise RuntimeError('Unsupported native return quantity database')
    precision, scale = column['type'].precision, column['type'].scale
    if precision is None and scale is None:
        return  # Unconstrained NUMERIC already retains all fractional digits.
    if precision is not None and scale is not None and scale >= 3 and precision - scale >= 11:
        return
    if (precision, scale) != (12, 2):
        raise RuntimeError('Native return quantity precision requires schema reconciliation')
    op.alter_column('srm_pos_return_lines', 'quantity',
                    existing_type=sa.Numeric(12, 2), type_=sa.Numeric(14, 3))


def downgrade():
    # Never round previously issued fractional returns on downgrade.
    pass
