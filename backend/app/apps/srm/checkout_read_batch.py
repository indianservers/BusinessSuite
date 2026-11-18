"""Request-local source prefetch; checkout validation still checks every pointer."""
from collections import defaultdict
from contextlib import contextmanager
from sqlalchemy import select

KEY = 'checkout_report_read_batch'


@contextmanager
def checkout_read_batch(db, roots, scope):
    from .models import SRMSalesOrder, SRMSalesOrderLine, SRMInvoice, SRMInvoiceLine, SRMReceipt, SRMReceiptAllocation, SRMPOSSession
    from .industry_models import IndustryRecord
    from .commercial_models import InvoiceContext, ReceiptContext
    from .service_checkout_models import POSCheckoutLine, POSCheckoutPayment, POSServiceOccurrence
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackRecordOwnership, PackMasterAvailability
    objects, children = {}, defaultdict(list)
    def load(model, field, ids):
        ids = {ident for ident in ids if ident is not None}
        rows = db.query(model).filter(getattr(model, field).in_(ids)).all() if ids else []
        for ident in ids:
            children[model, field, ident] = []
        for row in rows:
            objects[model, getattr(row, model.__mapper__.primary_key[0].key)] = row
            children[model, field, getattr(row, field)].append(row)
        return rows
    ids = [root.id for root in roots]
    lines = load(POSCheckoutLine, 'checkout_id', ids)
    payments = load(POSCheckoutPayment, 'checkout_id', ids)
    occurrences = load(POSServiceOccurrence, 'checkout_id', ids)
    load(SRMSalesOrder, 'id', [root.sales_order_id for root in roots])
    load(SRMInvoice, 'id', [root.invoice_id for root in roots])
    load(SRMSalesOrderLine, 'id', [row.sales_order_line_id for row in lines])
    load(SRMInvoiceLine, 'invoice_id', [root.invoice_id for root in roots])
    load(SRMReceipt, 'id', [row.receipt_id for row in payments])
    load(SRMReceiptAllocation, 'receipt_id', [row.receipt_id for row in payments])
    load(SRMPOSSession, 'id', [row.collection_session_id for row in payments])
    load(IndustryRecord, 'id', [ident for row in occurrences for ident in (row.appointment_id, row.provider_resource_id)])
    load(InvoiceContext, 'invoice_id', [root.invoice_id for root in roots])
    load(ReceiptContext, 'receipt_id', [row.receipt_id for row in payments])
    tables = {model.__tablename__ for model, _ in objects}
    keys = {str(ident) for _, ident in objects}
    def proofs(model):
        table = model.__table__
        return {(row['resource_table'], row['resource_key']): row for row in db.connection().execute(
            select(table).where(table.c.resource_table.in_(tables), table.c.resource_key.in_(keys))).mappings()}
    batch = {'scope': scope, 'objects': objects, 'children': children,
             'branch': proofs(BranchOwnership), 'pack': proofs(PackRecordOwnership)}
    available = PackMasterAvailability.__table__
    batch['available'] = {(row.resource_table, row.resource_key) for row in db.connection().execute(
        select(available.c.resource_table, available.c.resource_key).where(available.c.company_id == scope.company_id,
            available.c.branch_id == scope.branch_id, available.c.context_id == scope.context_id,
            available.c.active.is_(True), available.c.resource_table.in_(tables), available.c.resource_key.in_(keys)))}
    previous = db.info.get(KEY)
    db.info[KEY] = batch
    try:
        yield batch
    finally:
        if previous is None:
            db.info.pop(KEY, None)
        else:
            db.info[KEY] = previous
