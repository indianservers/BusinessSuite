"""Invoice revenue attributed through explicit company-local stock/product links."""
from collections import defaultdict
from decimal import Decimal
from app.apps.fam.models import FAMInventoryIntegrationLink,FAMCompanyFinancialSettings
from app.apps.srm.models import SRMInvoice,SRMInvoiceLine,SRMSalesOrder,SRMSalesOrderLine,SRMProduct,SRMBillingMilestone,SRMBillingPlan,SRMEngagement

def attributed_revenue(db,company_id,item_ids):
    settings=db.query(FAMCompanyFinancialSettings).filter_by(company_id=company_id).first()
    currency=settings.base_currency if settings else 'INR'
    products={p.id:p for p in db.query(SRMProduct).filter(SRMProduct.organization_id==company_id).all()}
    targets=defaultdict(set)
    for link in db.query(FAMInventoryIntegrationLink).filter(
        FAMInventoryIntegrationLink.company_id==company_id,FAMInventoryIntegrationLink.stock_item_id.in_(item_ids),
        FAMInventoryIntegrationLink.target_module=='srm',FAMInventoryIntegrationLink.target_record_type=='product',
        FAMInventoryIntegrationLink.active.is_(True)).all():
        raw=str(link.target_record_id)
        if raw.isascii() and raw.isdecimal() and len(raw)<=10:
            identity=int(raw)
            if identity in products:targets[identity].add(link.stock_item_id)
    order_lines={line.id:(line.product_id,line.sales_order_id) for line in db.query(SRMSalesOrderLine).join(
        SRMSalesOrder,SRMSalesOrder.id==SRMSalesOrderLine.sales_order_id).filter(
        SRMSalesOrder.organization_id==company_id).all()}
    milestone_sources={}
    for milestone,order_id,engagement_id in db.query(SRMBillingMilestone,SRMEngagement.sales_order_id,SRMEngagement.id).join(
        SRMBillingPlan,SRMBillingPlan.id==SRMBillingMilestone.billing_plan_id).join(
        SRMEngagement,SRMEngagement.id==SRMBillingPlan.engagement_id).filter(
        SRMBillingPlan.organization_id==company_id,SRMEngagement.organization_id==company_id).all():
        metadata=milestone.metadata_json if isinstance(milestone.metadata_json,dict) else {}
        source=order_lines.get(product_identity(metadata.get('sales_order_line_id')))
        if source and source[1]==order_id:
            milestone_sources[milestone.id]=(*source,engagement_id)
    rows=db.query(SRMInvoiceLine,SRMInvoice.currency,SRMInvoice.sales_order_id,SRMInvoice.engagement_id).join(SRMInvoice,SRMInvoice.id==SRMInvoiceLine.invoice_id).filter(
        SRMInvoice.organization_id==company_id,SRMInvoice.deleted_at.is_(None),SRMInvoice.approved_at.isnot(None),
        SRMInvoice.status.in_(['approved','sent','partially_paid','paid','overdue'])).all()
    totals=defaultdict(lambda:Decimal('0'))
    unresolved=0
    for line,invoice_currency,invoice_order,invoice_engagement in rows:
        source=(*order_lines[line.source_id],None) if line.source_type=='sales_order_line' and line.source_id in order_lines else milestone_sources.get(line.source_id) if line.source_type=='billing_milestone' else None
        if source and ((invoice_order is not None and invoice_order!=source[1]) or (source[2] is not None and invoice_engagement is not None and invoice_engagement!=source[2])):
            source=None
        product_id=source[0] if source else None
        product=products.get(product_id)
        if product and product.product_type=='service':continue
        owners=targets.get(product_id,set())
        if invoice_currency!=currency or len(owners)!=1:
            unresolved+=1
            continue
        stock_id=next(iter(owners))
        totals[stock_id]+=Decimal(line.line_total or 0)-Decimal(line.tax_amount or 0)
    linked={identity for owners in targets.values() if len(owners)==1 for identity in owners}
    return totals,linked,{'currency':currency,'unattributed_invoice_lines':unresolved,
        'ambiguous_product_links':sum(len(owners)>1 for owners in targets.values()),
        'basis':'Explicit stock-to-Sales product link and invoice order-line or validated milestone source; tax excluded. No description matching.'}


def product_identity(value):
    raw=str(value)
    if not raw.isascii() or not raw.isdecimal() or len(raw)>10 or not 0<int(raw)<=2147483647:
        return None
    return int(raw)


def validate_product_link(db,company_id,stock_item_id,value):
    from fastapi import HTTPException
    from sqlalchemy import select
    identity=product_identity(value)
    product=db.query(SRMProduct).filter(SRMProduct.id==identity,SRMProduct.organization_id==company_id,
        SRMProduct.active.is_(True),SRMProduct.product_type=='product').with_for_update().first() if identity else None
    if not product:raise HTTPException(422,'Select an active Sales product from this company')
    # The product row serializes competing writes. Inspect only company-local IDs
    # across branches so a hidden existing owner cannot silently become ambiguous.
    table=FAMInventoryIntegrationLink.__table__
    links=db.connection().execute(select(table.c.stock_item_id,table.c.target_record_id).where(
        table.c.company_id==company_id,table.c.target_module=='srm',table.c.target_record_type=='product',
        table.c.active.is_(True))).all()
    if any(owner!=stock_item_id and product_identity(target)==identity for owner,target in links):
        raise HTTPException(409,'This Sales product is already linked to another stock item')
    return str(identity)
