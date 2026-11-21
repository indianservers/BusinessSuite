"""Store the selling price of each stock batch."""
from alembic import op
import sqlalchemy as sa

revision = 'pg_20261121_129_batch_prices'
down_revision = 'pg_20261119_128_inv_reports'
branch_labels = depends_on = None


def upgrade():
    columns = sa.inspect(op.get_bind()).get_columns('srm_inventory_batches')
    if not any(column['name'] == 'selling_price' for column in columns):
        op.add_column('srm_inventory_batches', sa.Column('selling_price', sa.Numeric(14, 2)))
    op.execute("""
        UPDATE srm_inventory_batches
        SET selling_price = COALESCE((
            SELECT sales_rate FROM srm_products
            WHERE srm_products.id = srm_inventory_batches.product_id
        ), 0)
        WHERE selling_price IS NULL
    """)


def downgrade():
    op.drop_column('srm_inventory_batches', 'selling_price')
