from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.apps.srm.models import (
    SRMAuditLog,
    SRMBillingMilestone,
    SRMBillingPlan,
    SRMBillOfMaterial,
    SRMBOMComponent,
    SRMCollectionReminder,
    SRMContract,
    SRMCustomerAging,
    SRMEngagement,
    SRMEngagementLink,
    SRMInvoice,
    SRMInvoiceDraft,
    SRMInvoiceHistory,
    SRMInvoiceLine,
    SRMInventoryBatch,
    SRMGoodsReceipt,
    SRMGoodsReceiptLine,
    SRMProfitabilitySnapshot,
    SRMPOSCashMovement,
    SRMPOSCashierClosing,
    SRMPOSHeldBill,
    SRMPOSReturn,
    SRMPOSReturnLine,
    SRMPOSSession,
    SRMPriceList,
    SRMPriceListLine,
    SRMProductionOrder,
    SRMInventoryBalance,
    SRMInventoryMovement,
    SRMProduct,
    SRMProductCategory,
    SRMPurchaseOrder,
    SRMPurchaseOrderLine,
    SRMReceipt,
    SRMReceiptAllocation,
    SRMRevenueEvent,
    SRMSalesOrder,
    SRMSalesOrderLine,
    SRMSerialNumber,
    SRMSetting,
    SRMWarehouse,
)


SRM_TABLE_MODELS = [
    SRMSalesOrder,
    SRMSalesOrderLine,
    SRMContract,
    SRMEngagement,
    SRMEngagementLink,
    SRMBillingPlan,
    SRMBillingMilestone,
    SRMBillOfMaterial,
    SRMBOMComponent,
    SRMInvoiceDraft,
    SRMInvoice,
    SRMInvoiceLine,
    SRMInvoiceHistory,
    SRMReceipt,
    SRMReceiptAllocation,
    SRMCollectionReminder,
    SRMCustomerAging,
    SRMProfitabilitySnapshot,
    SRMPOSSession,
    SRMPOSCashMovement,
    SRMPOSCashierClosing,
    SRMPOSHeldBill,
    SRMPOSReturn,
    SRMPOSReturnLine,
    SRMProductCategory,
    SRMWarehouse,
    SRMProduct,
    SRMInventoryBalance,
    SRMInventoryMovement,
    SRMInventoryBatch,
    SRMPurchaseOrder,
    SRMPurchaseOrderLine,
    SRMGoodsReceipt,
    SRMGoodsReceiptLine,
    SRMPriceList,
    SRMPriceListLine,
    SRMProductionOrder,
    SRMRevenueEvent,
    SRMAuditLog,
    SRMSerialNumber,
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
