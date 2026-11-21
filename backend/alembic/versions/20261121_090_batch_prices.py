"""Store the selling price of each stock batch."""
from alembic import op
import sqlalchemy as sa

revision = '20261121_090_batch_prices'
down_revision = '20261119_089_inventory_reports'
branch_labels = depends_on = None


def upgrade():
    op.add_column('srm_inventory_batches', sa.Column('selling_price', sa.Numeric(14, 2)))
    op.execute("""
        UPDATE srm_inventory_batches
        SET selling_price = COALESCE((
            SELECT sales_rate FROM srm_products
            WHERE srm_products.id = srm_inventory_batches.product_id
        ), 0)
    """)


def downgrade():
    op.drop_column('srm_inventory_batches', 'selling_price')
