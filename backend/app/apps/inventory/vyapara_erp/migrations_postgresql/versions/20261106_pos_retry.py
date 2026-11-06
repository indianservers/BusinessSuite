"""Persist POS retry identity in the same transaction as the sale."""
from alembic import op
import sqlalchemy as sa

revision = "pg_inventory_20261106"
down_revision = "pg_inventory_20261022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sales", sa.Column("pos_request_key", sa.String(64), nullable=True))
    op.add_column("sales", sa.Column("pos_request_fingerprint", sa.String(64), nullable=True))
    op.add_column("sales", sa.Column("pos_change_due", sa.Numeric(12, 2), nullable=True))
    op.create_unique_constraint("uq_sales_pos_request_key", "sales", ["pos_request_key"])


def downgrade():
    op.drop_constraint("uq_sales_pos_request_key", "sales", type_="unique")
    for column in ("pos_change_due", "pos_request_fingerprint", "pos_request_key"):
        op.drop_column("sales", column)
