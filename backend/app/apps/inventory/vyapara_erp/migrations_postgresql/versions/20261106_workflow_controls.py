"""Evidence-gated stock adjustments and persisted manufacturing component sources."""
from alembic import op
import sqlalchemy as sa
revision='pg_inventory_controls_20261106'
down_revision='pg_inventory_20261106'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('stock_adjustment_reviews',
        sa.Column('adjustment_id',sa.Integer(),sa.ForeignKey('stock_adjustments.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('status',sa.String(20),nullable=False,server_default='Pending'),
        sa.Column('evidence',sa.LargeBinary()),sa.Column('evidence_name',sa.String(255)),
        sa.Column('evidence_mime',sa.String(100)),sa.Column('evidence_sha256',sa.String(64)),
        sa.Column('uploaded_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('approved_by',sa.Integer(),sa.ForeignKey('users.id')),sa.Column('approved_at',sa.DateTime()))
    op.create_table('manufacturing_component_sources',
        sa.Column('order_id',sa.Integer(),sa.ForeignKey('manufacturing_orders.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('bom_item_id',sa.Integer(),sa.ForeignKey('bom_items.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('warehouse_id',sa.Integer(),sa.ForeignKey('warehouses.id'),nullable=False))

def downgrade():
    op.drop_table('manufacturing_component_sources')
    op.drop_table('stock_adjustment_reviews')
