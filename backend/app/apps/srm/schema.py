from sqlalchemy import inspect
from sqlalchemy.orm import Session

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


SRM_TABLE_MODELS = [
    SRMSalesOrder,
    SRMSalesOrderLine,
    SRMContract,
    SRMEngagement,
    SRMEngagementLink,
    SRMBillingPlan,
    SRMBillingMilestone,
    SRMInvoiceDraft,
    SRMInvoice,
    SRMInvoiceLine,
    SRMInvoiceHistory,
    SRMReceipt,
    SRMReceiptAllocation,
    SRMCollectionReminder,
    SRMCustomerAging,
    SRMProfitabilitySnapshot,
    SRMRevenueEvent,
    SRMAuditLog,
    SRMSetting,
]


def ensure_srm_schema(db: Session) -> None:
    """Ensure SRM operational tables exist in dev databases.

    Alembic remains the production migration source of truth. This helper keeps
    local create_all-style databases compatible when SRM is enabled after an
    older database already exists.
    """
    inspector = inspect(db.bind)
    existing_tables = set(inspector.get_table_names())
    missing = [model.__table__ for model in SRM_TABLE_MODELS if model.__tablename__ not in existing_tables]
    if missing:
        SRMSalesOrder.metadata.create_all(bind=db.bind, tables=missing)
