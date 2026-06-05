"""srm database core

Revision ID: 20260604_002
Revises: 20260604_001
Create Date: 2026-06-04
"""

from alembic import op

from app.apps.srm.models import (
    SRMAuditLog,
    SRMBillingMilestone,
    SRMBillingPlan,
    SRMCollectionReminder,
    SRMContract,
    SRMCustomerAging,
    SRMEngagement,
    SRMEngagementLink,
    SRMInvoice,
    SRMInvoiceDraft,
    SRMInvoiceHistory,
    SRMInvoiceLine,
    SRMProfitabilitySnapshot,
    SRMReceipt,
    SRMReceiptAllocation,
    SRMRevenueEvent,
    SRMSalesOrder,
    SRMSalesOrderLine,
    SRMSetting,
)


revision = "20260604_002"
down_revision = "20260604_001"
branch_labels = None
depends_on = None


SRM_TABLES = [
    SRMSalesOrder.__table__,
    SRMSalesOrderLine.__table__,
    SRMContract.__table__,
    SRMEngagement.__table__,
    SRMEngagementLink.__table__,
    SRMBillingPlan.__table__,
    SRMBillingMilestone.__table__,
    SRMInvoiceDraft.__table__,
    SRMInvoice.__table__,
    SRMInvoiceLine.__table__,
    SRMInvoiceHistory.__table__,
    SRMReceipt.__table__,
    SRMReceiptAllocation.__table__,
    SRMCollectionReminder.__table__,
    SRMCustomerAging.__table__,
    SRMProfitabilitySnapshot.__table__,
    SRMRevenueEvent.__table__,
    SRMAuditLog.__table__,
    SRMSetting.__table__,
]

SRM_TABLE_NAMES = [table.name for table in SRM_TABLES]


def upgrade() -> None:
    bind = op.get_bind()
    for table in SRM_TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(SRM_TABLES):
        table.drop(bind=bind, checkfirst=True)
