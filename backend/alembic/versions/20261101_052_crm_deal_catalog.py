"""Persist product and service price snapshots on deals."""
from alembic import op
import sqlalchemy as sa

revision = "20261101_052_deal_catalog"
down_revision = "20261101_051_timesheet_tenant"
branch_labels = None
depends_on = None


def upgrade():
    if "catalog_items" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("crm_deals")}:
        op.add_column("crm_deals", sa.Column("catalog_items", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("crm_deals", "catalog_items")
