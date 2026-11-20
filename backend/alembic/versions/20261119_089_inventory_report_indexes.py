"""Composite indexes for scoped inventory report scans; no transaction changes."""
revision='20261119_089_inventory_reports'
down_revision='20261119_088_customer_plans'
branch_labels=depends_on=None
from alembic import op

INDEXES = [
    ("ix_fam_movement_report_scope", "fam_stock_movements", ["company_id", "status", "movement_date", "id"]),
    ("ix_fam_lines_report_scope", "fam_stock_movement_lines", ["company_id", "stock_item_id", "warehouse_id", "movement_id"]),
    ("ix_srm_movement_report_scope", "srm_inventory_movements", ["organization_id", "product_id", "warehouse_id", "movement_date", "id"]),
    ("ix_fam_reservation_report_scope", "fam_inventory_reservations", ["company_id", "stock_item_id", "status", "expires_at"]),
]


def upgrade():
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade():
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
