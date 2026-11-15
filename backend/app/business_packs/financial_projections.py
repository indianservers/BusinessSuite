"""Status-only projections for native-authorized, context-owned financial rows.

These do not grant project, communication or FAM record access.
"""
from fastapi import HTTPException
from sqlalchemy import select,exists,inspect,or_


def _source(db,item,kind):
    from app.apps.srm.models import SRMInvoice,SRMReceipt,SRMReceiptAllocation,SRMSalesOrder
    from app.apps.srm.service_checkout import _source_scope
    from app.business_packs.boundary import _current
    from app.branches.models import BranchOwnership
    scope=db.info.get('business_pack_scope')
    models={'invoice':SRMInvoice,'receipt':SRMReceipt,'allocation':SRMReceiptAllocation,'order':SRMSalesOrder}
    model=models.get(kind);state=inspect(item,raiseerr=False) if item is not None else None
    def deny():raise HTTPException(403,'Financial source authorization changed')
    if scope is None or model is None or type(item) is not model or state.session is not db or not state.persistent or state.modified:deny()
    shared=db.info.get('shared_actor');branch=db.info.get('branch_context')
    if (shared is not None and shared!=(scope.user_id,scope.company_id)) or getattr(branch,'company_id',None)!=scope.company_id or getattr(branch,'branch_id',None)!=scope.branch_id:deny()
    connection=db.connection();_current(scope,connection)
    _source_scope(db,scope,scope.company_id,scope.branch_id,model,item.id)
    table=model.__table__;owner=BranchOwnership.__table__
    if kind=='allocation':
        receipt=db.get(SRMReceipt,item.receipt_id);invoice=db.get(SRMInvoice,item.invoice_id)
        _source(db,receipt,'receipt');_source(db,invoice,'invoice')
        actual=connection.execute(select(table.c.receipt_id,table.c.invoice_id).where(table.c.id==item.id)).first()
        if actual is None or tuple(actual)!=(receipt.id,invoice.id):deny()
    elif not connection.scalar(select(exists().where(table.c.id==item.id,table.c.organization_id==scope.company_id))):deny()
    if not connection.scalar(select(exists().where(owner.c.resource_table==table.name,owner.c.resource_key==str(item.id),owner.c.company_id==scope.company_id,owner.c.branch_id==scope.branch_id))):deny()
    return scope


def assert_contextless_order(db,order):
    from app.apps.srm.models import SRMContract,SRMEngagement
    from app.apps.srm.commercial_models import ProjectCommercial
    _source(db,order,'order')
    for model,column in ((SRMContract,'sales_order_id'),(SRMEngagement,'sales_order_id'),(ProjectCommercial,'sales_order_id')):
        table=model.__table__
        if db.connection().scalar(select(exists().where(table.c[column]==order.id))):
            raise HTTPException(503,'Linked commercial context is not integrated in this selected workflow')


def delivery_status(db,invoice):
    from app.apps.srm.commercial_models import InvoiceDelivery
    _source(db,invoice,'invoice');table=InvoiceDelivery.__table__
    value=db.connection().scalar(select(table.c.status).where(table.c.invoice_id==invoice.id).order_by(table.c.id.desc()).limit(1))
    if value is None:return 'legacy_sent' if invoice.sent_at else 'not_sent'
    return value if value in {'queued','pending','sending','sent','delivered','failed','cancelled'} else 'unknown'


def delivery_records(db, invoice):
    """Bounded delivery status/history for one native-authorized private invoice."""
    from app.apps.srm.commercial_models import InvoiceDelivery
    _source(db, invoice, 'invoice')
    assert_common_invoice(db, invoice)
    table = InvoiceDelivery.__table__
    rows = db.connection().execute(select(table.c.id, table.c.invoice_id, table.c.request_id,
        table.c.status, table.c.error, table.c.created_at).where(table.c.invoice_id == invoice.id)
        .order_by(table.c.id.desc()).limit(100)).mappings()
    return [dict(row) for row in rows]


def accounting_status(db,item,kind):
    from app.apps.fam.models import FAMPostingJob
    scope=_source(db,item,kind);table=FAMPostingJob.__table__
    value=db.connection().scalar(select(table.c.status).where(table.c.company_id==scope.company_id,table.c.source_module=='srm',table.c.source_record_type==kind,table.c.source_record_id==item.id).order_by(table.c.id.desc()).limit(1))
    status='not_posted' if value is None else value if value in {'pending','processing','posted','failed','cancelled','retrying'} else 'unknown'
    return {'status':status,'mappings':[]}


def own_invoice_query(query,db,actor):
    """Native Own visibility for the reviewed order/customer checkout graph."""
    from app.apps.srm.models import SRMInvoice,SRMSalesOrder
    from app.apps.crm.models import CRMCompany
    scope=db.info.get('business_pack_scope')
    if scope is None or scope.user_id!=actor.id:raise HTTPException(403,'Financial source authorization changed')
    orders=select(SRMSalesOrder.id).where(SRMSalesOrder.organization_id==scope.company_id,SRMSalesOrder.assigned_user_id==actor.id)
    customers=select(CRMCompany.id).where(CRMCompany.organization_id==scope.company_id,CRMCompany.owner_user_id==actor.id)
    return query.filter(or_(SRMInvoice.created_by==actor.id,SRMInvoice.sales_order_id.in_(orders),SRMInvoice.customer_id.in_(customers)))


def assert_common_invoice(db,invoice):
    from app.apps.srm.models import SRMSalesOrder
    from app.apps.srm.commercial_models import InvoiceContext
    _source(db,invoice,'invoice')
    if db.info['business_pack_scope'].pack_key=='accounting_firm':
        from .accounting_firm.billing import assert_invoice_source
        if assert_invoice_source(db,invoice):
            return
    if db.info['business_pack_scope'].pack_key=='construction':
        from .construction_billing import assert_invoice_source
        if assert_invoice_source(db,invoice):
            return
    if invoice.engagement_id is not None or invoice.sales_order_id is None:
        raise HTTPException(503,'This selected invoice source requires a reviewed adapter')
    table=InvoiceContext.__table__
    if db.connection().scalar(select(exists().where(table.c.invoice_id==invoice.id,table.c.project_id.is_not(None)))):
        raise HTTPException(503,'Project-linked invoice context requires a reviewed adapter')
    order=db.get(SRMSalesOrder,invoice.sales_order_id)
    if order is None:raise HTTPException(403,'Financial source authorization changed')
    assert_contextless_order(db,order)
