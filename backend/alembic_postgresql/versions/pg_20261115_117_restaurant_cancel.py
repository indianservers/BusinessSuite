"""Preserve original Restaurant charge identity across native draft-line deletion."""
from alembic import op
import sqlalchemy as sa
revision = 'pg_20261115_117_rest_cancel'
down_revision = 'pg_20261115_116_accounts_birth'
branch_labels = depends_on = None
TABLE = 'business_restaurant_tab_lines'
NAMING = {'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s'}


def _live_fk():
    return next(fk for fk in sa.inspect(op.get_bind()).get_foreign_keys(TABLE) if fk['constrained_columns'] == ['sales_order_line_id'])


def upgrade():
    op.add_column(TABLE, sa.Column('original_sales_order_line_id', sa.Integer(), nullable=True))
    op.execute(sa.text('UPDATE business_restaurant_tab_lines SET original_sales_order_line_id = sales_order_line_id'))
    fk = _live_fk()
    name = fk['name'] or 'fk_business_restaurant_tab_lines_sales_order_line_id_srm_sales_order_lines'
    with op.batch_alter_table(TABLE, naming_convention=NAMING) as batch:
        batch.drop_constraint(name, type_='foreignkey')
        batch.alter_column('original_sales_order_line_id', existing_type=sa.Integer(), nullable=False)
        batch.alter_column('sales_order_line_id', existing_type=sa.Integer(), nullable=True)
        batch.create_check_constraint('ck_restaurant_tab_original_identity', 'original_sales_order_line_id > 0 AND (sales_order_line_id IS NULL OR sales_order_line_id = original_sales_order_line_id)')
        batch.create_foreign_key('fk_restaurant_tab_live_line', 'srm_sales_order_lines', ['sales_order_line_id'], ['id'], ondelete='SET NULL')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM business_restaurant_tab_lines WHERE sales_order_line_id IS NULL')):
        raise RuntimeError('Cannot discard original provenance after a Restaurant cancellation')
    fk = _live_fk()
    with op.batch_alter_table(TABLE, naming_convention=NAMING) as batch:
        batch.drop_constraint(fk['name'], type_='foreignkey')
        batch.alter_column('sales_order_line_id', existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key('fk_restaurant_tab_live_line', 'srm_sales_order_lines', ['sales_order_line_id'], ['id'], ondelete='RESTRICT')
        batch.drop_constraint('ck_restaurant_tab_original_identity', type_='check')
        batch.drop_column('original_sales_order_line_id')
