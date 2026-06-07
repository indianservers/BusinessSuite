"""fam phase 8 inventory merge

Revision ID: 20260606_018
Revises: 20260606_017
Create Date: 2026-06-06
"""

from alembic import op


revision = "20260606_018"
down_revision = "20260606_017"
branch_labels = None
depends_on = None


TABLES = (
    "fam_stock_groups",
    "fam_units_of_measure",
    "fam_warehouses",
    "fam_stock_items",
    "fam_stock_opening_balances",
    "fam_stock_movements",
    "fam_stock_movement_lines",
    "fam_inventory_valuation_layers",
    "fam_stock_transfers",
    "fam_stock_adjustments",
    "fam_inventory_ai_logs",
    "fam_inventory_reports",
)


def upgrade() -> None:
    import app.db.base  # noqa: F401
    import app.apps.fam.models  # noqa: F401
    from app.db.base_class import Base

    bind = op.get_bind()
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    import app.db.base  # noqa: F401
    import app.apps.fam.models  # noqa: F401
    from app.db.base_class import Base

    bind = op.get_bind()
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
