"""Blind canonical-resource eligibility for native quantity-only commands."""
from sqlalchemy import select,exists,inspect
from .models import PharmaBatchReceipt,PackBatchAvailability


def managed_product(db,company,product_id,warehouse_id=None):
    """One boolean, never private receipt/case data or inferred lot adoption.

    Every valid initial receipt creates both durable receipt and availability.
    Availability remains historical evidence even when later deactivated, so a
    revoke cannot reactivate quantity-only stock consumption of managed lots.
    """
    if type(company) is not int or company<=0 or type(product_id) is not int or product_id<=0:return False
    r=PharmaBatchReceipt.__table__;a=PackBatchAvailability.__table__
    inspector=inspect(db.connection())
    if not inspector.has_table(r.name) or not inspector.has_table(a.name):return False
    conditions=[r.c.organization_id==company,r.c.product_id==product_id,a.c.organization_id==company,a.c.batch_id==r.c.batch_id]
    if warehouse_id is not None:conditions.append(r.c.warehouse_id==warehouse_id)
    return bool(db.connection().scalar(select(exists(select(1).select_from(r.join(a,a.c.batch_id==r.c.batch_id)).where(*conditions)))))
