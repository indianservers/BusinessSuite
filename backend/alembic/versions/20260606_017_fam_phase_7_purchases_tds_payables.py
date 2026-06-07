"""fam phase 7 purchases expenses tds payables

Revision ID: 20260606_017
Revises: 20260606_016
Create Date: 2026-06-06
"""

from alembic import op


revision = "20260606_017"
down_revision = "20260606_016"
branch_labels = None
depends_on = None


TABLES = (
    "fam_tds_sections",
    "fam_tds_rates",
    "fam_purchase_bills",
    "fam_purchase_bill_lines",
    "fam_expense_claims",
    "fam_expense_lines",
    "fam_tds_transactions",
    "fam_vendor_payment_runs",
    "fam_vendor_payment_items",
    "fam_purchase_audit_logs",
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
