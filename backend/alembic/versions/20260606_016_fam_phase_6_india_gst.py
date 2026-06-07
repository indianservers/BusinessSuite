"""fam phase 6 india gst einvoice ewaybill

Revision ID: 20260606_016
Revises: 20260606_015
Create Date: 2026-06-06
"""

from alembic import op


revision = "20260606_016"
down_revision = "20260606_015"
branch_labels = None
depends_on = None


GST_TABLES = (
    "fam_tax_registrations",
    "fam_gst_rates",
    "fam_hsn_sac_codes",
    "fam_gst_transaction_lines",
    "fam_gst_return_periods",
    "fam_gstr1_records",
    "fam_gstr3b_records",
    "fam_gst_reconciliation_items",
    "fam_einvoice_settings",
    "fam_einvoice_jobs",
    "fam_ewaybill_settings",
    "fam_ewaybill_jobs",
    "fam_gst_audit_logs",
)


def upgrade() -> None:
    import app.db.base  # noqa: F401
    import app.apps.fam.models  # noqa: F401
    from app.db.base_class import Base

    bind = op.get_bind()
    for table_name in GST_TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    import app.db.base  # noqa: F401
    import app.apps.fam.models  # noqa: F401
    from app.db.base_class import Base

    bind = op.get_bind()
    for table_name in reversed(GST_TABLES):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
