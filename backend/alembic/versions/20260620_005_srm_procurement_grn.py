"""srm procurement and grn

Revision ID: 20260620_005
Revises: 20260620_004
Create Date: 2026-06-20
"""

from alembic import op

from app.apps.srm.models import (
    SRMGoodsReceipt,
    SRMGoodsReceiptLine,
    SRMPurchaseOrder,
    SRMPurchaseOrderLine,
)


revision = "20260620_005"
down_revision = "20260620_004"
branch_labels = None
depends_on = None


TABLES = [
    SRMPurchaseOrder.__table__,
    SRMPurchaseOrderLine.__table__,
    SRMGoodsReceipt.__table__,
    SRMGoodsReceiptLine.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
