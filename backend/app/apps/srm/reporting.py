"""Live native Sales reports. All reads retain the existing ORM boundaries.

Report definitions are explicit: monetary values are never combined across
currencies, document filters select whole documents, and stock uses its ledger.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from typing import Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, or_, case, cast, Date, String, func, literal, select, tuple_

from app.apps.srm.models import (SRMInvoice as Invoice, SRMInvoiceLine as InvoiceLine,
    SRMSalesOrder as Order, SRMSalesOrderLine as OrderLine, SRMReceipt as Receipt,
    SRMReceiptAllocation as Allocation, SRMPOSReturn as Return, SRMPOSReturnLine as ReturnLine,
    SRMProduct as Product, SRMWarehouse as Warehouse, SRMInventoryBalance as Balance,
    SRMInventoryMovement as Movement, SRMSetting as Setting, SRMContract as Contract,
    SRMBillingMilestone as Milestone, SRMBillingPlan as Plan, SRMProfitabilitySnapshot as Profit,
    SRMEngagement as Engagement, SRMPurchaseOrder as Purchase, SRMPurchaseOrderLine as PurchaseLine,
    SRMGoodsReceipt as GoodsReceipt, SRMGoodsReceiptLine as GoodsReceiptLine)
from app.apps.srm.services.commercial import invoice_query, tenant
from app.apps.srm.access import sales_order_query, engagement_query, can_view_all_srm
from app.apps.crm.models import CRMCompany
from app.models.user import User
from app.services.metrics.queries import business_context, business_day
from app.apps.srm.reporting_models import SRMReportFlag

REPORTS = {
    'overview': 'Daily business dashboard', 'invoices': 'Invoice register',
    'sales': 'Sales orders', 'payments': 'Collections & payments', 'returns': 'Returns & refunds',
    'customers': 'Customer insights', 'products': 'Product performance', 'stock': 'Stock & reorder planning',
    'reconciliation': 'Stock reconciliation', 'payment_reconciliation': 'Sales & payment reconciliation',
    'outstanding': 'Outstanding & aging', 'contracts': 'Contracts', 'recurring': 'Recurring invoices',
    'profitability': 'Engagement profitability', 'pipeline': 'Lead to cash',
    'project_profitability':'Project profitability','customer_profitability':'Customer profitability',
    'cash_margin':'Cash margin','sales_to_delivery_margin':'Sales to delivery margin','invoice_aging':'Invoice aging',
}
ISSUED = ('draft', 'pending_approval', 'cancelled', 'canceled', 'void', 'rejected')
ISSUES = ('pos_sale', 'sales_order_issue', 'stock_out', 'delivery_note')
SALES_ISSUES = ('pos_sale','sales_order_issue','delivery_note')
STOCK_RECEIPTS = ('grn_receipt','purchase_receipt','receipt','stock_in')
STOCK_RETURNS = ('pos_return','sales_return','customer_return')
ACTIVE_RECEIPTS = ('confirmed','partially_allocated','allocated')
OfferingKind = Literal["product", "service", "membership", "subscription"]
AudienceChannel = Literal["sms", "whatsapp", "email"]
AUDIENCE_KINDS = ("product", "service", "membership", "subscription")
AUDIENCE_CHANNELS = ("sms", "whatsapp", "email")


class Filters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: date | None = None
    end: date | None = None
    branch_id: int | None = Field(default=None, gt=0)
    warehouse_id: int | None = Field(default=None, gt=0)
    customer_id: int | None = Field(default=None, gt=0)
    product_id: int | None = Field(default=None, gt=0)
    cashier_id: int | None = Field(default=None, gt=0)
    payment_method: str = Field(default='', max_length=60)
    currency: str = Field(default='', max_length=3, pattern=r'^(|[A-Z]{3})$')
    status: str = Field(default='', max_length=40)
    search: str = Field(default='', max_length=100)
    include_test: bool = False
    inactive_days: int = Field(default=90, ge=1, le=3650)
    low_only: bool = False
    customer_segment: str = Field(default='all',pattern='^(all|repeat|inactive|outstanding)$')
    discrepancy_only: bool = False
    period_preset: str = Field(default='custom',pattern='^(custom|today|yesterday|week|month)$')

    @model_validator(mode='after')
    def dates(self):
        if self.start and self.end and self.start > self.end:
            raise ValueError('From date must be before or equal to To date')
        if self.start and self.end and (self.end-self.start).days > 3660:
            raise ValueError('Choose a reporting period of ten years or less')
        return self


def native(db):
    if db.info.get('business_pack_scope') is not None:
        raise HTTPException(409, 'Use the selected Business Pack reporting surface')


def resolved(db, user, filters, *, allow_pack=False):
    if not allow_pack:
        native(db)
    today = business_day(db, user)
    if filters.period_preset!='custom':
        end=today-timedelta(days=1) if filters.period_preset=='yesterday' else today
        start=end-timedelta(days=6) if filters.period_preset=='week' else end.replace(day=1) if filters.period_preset=='month' else end
        return filters.model_copy(update={'start':start,'end':end,'period_preset':'custom'})
    return filters.model_copy(update={'start': filters.start or today-timedelta(days=29), 'end': filters.end or today})


def money(value):
    return str(Decimal(str(value or 0)).quantize(Decimal('.01')))


def number(value):
    return float(value or 0)


def period(query, column, f, db, user):
    if isinstance(column.type, Date) and not hasattr(column.type, 'timezone'):
        return query.filter(column >= f.start, column <= f.end)
    zone = ZoneInfo(business_context(db, user)['timezone'])
    begin = datetime.combine(f.start, time.min, zone).astimezone(timezone.utc)
    until = datetime.combine(f.end+timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    return query.filter(column >= begin, column < until)


def branch_filter(query, model, f, db, user):
    if not f.branch_id:
        return query
    context = db.info.get('branch_context')
    if context is None or (context.branch_id and context.branch_id != f.branch_id) or f.branch_id not in context.allowed:
        raise HTTPException(403, 'Choose a branch within your current authorized scope')
    from app.branches.models import BranchOwnership
    return query.filter(cast(model.id, String).in_(db.query(BranchOwnership.resource_key).filter(
        BranchOwnership.company_id == tenant(user), BranchOwnership.branch_id == f.branch_id,
        BranchOwnership.resource_table == model.__tablename__)))


def flag(db, user, entity, identity, legacy=None):
    # Classification is company metadata for an already-authorized source row.
    # A source transferred between branches retains its test classification.
    from sqlalchemy import exists, select
    table=SRMReportFlag.__table__
    match=(table.c.organization_id==tenant(user),table.c.entity==entity,table.c.resource_id==identity)
    if legacy is None:return exists(select(table.c.id).where(*match,table.c.is_test.is_(True)))
    return case((exists(select(table.c.id).where(*match)),select(table.c.is_test).where(*match).scalar_subquery()),else_=func.coalesce(legacy,False))


def order_test(db, user):
    return flag(db,user,'sales_order',Order.id,or_(Order.metadata_json['is_test'].as_boolean().is_(True),
        Order.metadata_json['test_only'].as_boolean().is_(True)))


def invoice_test(db, user):
    return flag(db,user,'invoice',Invoice.id,Invoice.sales_order_id.in_(
        db.query(Order.id).filter(Order.organization_id == tenant(user), order_test(db, user))))


def product_test(db, user):
    return flag(db,user,'product',Product.id,or_(Product.metadata_json['is_test'].as_boolean().is_(True),
        Product.metadata_json['test_only'].as_boolean().is_(True)))


def test_order_sources(db,user):
    billed=db.query(Invoice.sales_order_id).filter(Invoice.organization_id==tenant(user),Invoice.sales_order_id.is_not(None),invoice_test(db,user))
    return db.query(Order.id).filter(Order.organization_id==tenant(user),or_(order_test(db,user),Order.id.in_(billed)))


def test_engagement_sources(db,user):
    return or_(flag(db,user,'engagement',Engagement.id),Engagement.sales_order_id.in_(test_order_sources(db,user)))


def invoices(db, user, f, *, dates=True):
    q = invoice_query(db, user)
    q = branch_filter(q, Invoice, f, db, user)
    if dates:q = period(q, Invoice.issue_date, f, db, user)
    if not f.include_test:q = q.filter(~func.coalesce(invoice_test(db,user),False))
    if f.customer_id:q = q.filter(Invoice.customer_id == f.customer_id)
    if f.currency:q = q.filter(Invoice.currency == f.currency)
    if f.status:q = q.filter(Invoice.status == f.status)
    if f.cashier_id:q = q.filter(Invoice.created_by == f.cashier_id)
    if f.search:
        customer_ids=db.query(CRMCompany.id).filter(CRMCompany.name.icontains(f.search,autoescape=True))
        q=q.filter(or_(Invoice.invoice_number.icontains(f.search,autoescape=True), Invoice.customer_id.in_(customer_ids)))
    if f.product_id:
        sources = db.query(OrderLine.id).filter(OrderLine.product_id == f.product_id)
        q=q.filter(Invoice.id.in_(db.query(InvoiceLine.invoice_id).filter(
            InvoiceLine.source_type=='sales_order_line', InvoiceLine.source_id.in_(sources))))
    if f.warehouse_id:
        movement_orders=db.query(Order.id).join(Movement, Movement.reference_number==Order.order_number).filter(
            Movement.organization_id==tenant(user), Movement.warehouse_id==f.warehouse_id)
        q=q.filter(Invoice.sales_order_id.in_(movement_orders))
    if f.payment_method:
        receipts=db.query(Receipt.id).filter(Receipt.organization_id==tenant(user), Receipt.payment_method==f.payment_method, Receipt.status.in_(ACTIVE_RECEIPTS))
        q=q.filter(Invoice.id.in_(db.query(Allocation.invoice_id).filter(Allocation.receipt_id.in_(receipts))))
    return q


def invoice_ids(q):
    return q.with_entities(Invoice.id).order_by(None)


def receipt_query(db, user, f, *, dates=True):
    q=db.query(Receipt).filter(Receipt.organization_id==tenant(user))
    q=branch_filter(q,Receipt,f,db,user)
    if dates:q=period(q,Receipt.receipt_date,f,db,user)
    if not can_view_all_srm(user):
        visible=invoices(db,user,f,dates=False)
        q=q.filter(or_(Receipt.created_by==user.id, Receipt.id.in_(db.query(Allocation.receipt_id).filter(Allocation.invoice_id.in_(invoice_ids(visible))))))
    if not f.include_test:
        test_invoices=invoice_query(db,user).filter(invoice_test(db,user))
        q=q.filter(~flag(db,user,'receipt',Receipt.id), ~Receipt.id.in_(db.query(Allocation.receipt_id).filter(Allocation.invoice_id.in_(invoice_ids(test_invoices)))))
    if f.customer_id:q=q.filter(Receipt.customer_id==f.customer_id)
    if f.cashier_id:q=q.filter(Receipt.created_by==f.cashier_id)
    if f.currency:q=q.filter(Receipt.currency==f.currency)
    if f.payment_method:q=q.filter(Receipt.payment_method==f.payment_method)
    if f.status:q=q.filter(Receipt.status==f.status)
    if f.product_id or f.warehouse_id:
        q=q.filter(Receipt.id.in_(db.query(Allocation.receipt_id).filter(Allocation.invoice_id.in_(invoice_ids(invoices(db,user,f,dates=False))))))
    if f.search:q=q.filter(or_(Receipt.receipt_number.icontains(f.search,autoescape=True),Receipt.reference_number.icontains(f.search,autoescape=True)))
    return q


def returns_query(db,user,f):
    # The order must be visible independently; refund totals never widen native sales scope.
    orders=sales_order_query(db,user)
    if not f.include_test:
        excluded=invoices(db,user,f.model_copy(update={'include_test':True,'status':'','search':'','currency':'','customer_id':None,'cashier_id':None,'product_id':None,'warehouse_id':None,'payment_method':''}),dates=False).filter(invoice_test(db,user))
        orders=orders.filter(~func.coalesce(order_test(db,user),False),~Order.id.in_(excluded.filter(Invoice.sales_order_id.is_not(None)).with_entities(Invoice.sales_order_id)))
    q=db.query(Return).filter(Return.organization_id==tenant(user),Return.sales_order_id.in_(orders.with_entities(Order.id)))
    q=branch_filter(q,Return,f,db,user);q=period(q,Return.created_at,f,db,user)
    if f.customer_id:q=q.filter(Return.customer_id==f.customer_id)
    if f.cashier_id:q=q.filter(Return.created_by==f.cashier_id)
    if f.payment_method:q=q.filter(Return.refund_method==f.payment_method)
    if f.status:q=q.filter(Return.status==f.status)
    if f.currency:q=q.filter(Return.sales_order_id.in_(orders.filter(Order.currency==f.currency).with_entities(Order.id)))
    if f.product_id or f.warehouse_id:
        lines=db.query(ReturnLine.return_id)
        if f.product_id:lines=lines.filter(ReturnLine.product_id==f.product_id)
        if f.warehouse_id:lines=lines.filter(ReturnLine.warehouse_id==f.warehouse_id)
        q=q.filter(Return.id.in_(lines))
    return q


def product_query(db,user,f):
    from app.shared.catalog import restrict_workspaces
    from app.shared.catalog_branches import availability_clause, selected_branch
    q=db.query(Product).filter(Product.organization_id==tenant(user), Product.deleted_at.is_(None))
    q=restrict_workspaces(q,Product,db,user).filter(availability_clause(Product,selected_branch(user)))
    q=branch_filter(q,Product,f,db,user)
    if not f.include_test:q=q.filter(~func.coalesce(product_test(db,user),False))
    if f.product_id:q=q.filter(Product.id==f.product_id)
    if f.currency:q=q.filter(func.upper(func.coalesce(Product.metadata_json['currency'].as_string(),'INR'))==f.currency)
    if f.search:q=q.filter(or_(Product.item_name.icontains(f.search,autoescape=True),Product.sku.icontains(f.search,autoescape=True)))
    return q


def paged(query,page,size):
    total=query.order_by(None).limit(None).offset(None).count()
    return query.limit(size).offset((page-1)*size).all(),total


def result(db,user,f,report,rows,total,page,size,columns,**extra):
    return {'report':report,'title':REPORTS[report],'items':rows,'total':total,'page':page,'page_size':size,
        'has_more':page*size<total,'columns':columns,'filters':f.model_dump(mode='json'),
        'context':business_context(db,user),'definitions':{
            'currency':'Each currency is separate. No currency conversion is applied.',
            'dates':'Invoices use issue date; payments use receipt date; returns and orders use company-local creation dates. Undated invoices are excluded from date-filtered results.',
            'document_filters':'Product/warehouse/payment filters select whole financial documents; their values remain full-document totals. Product performance uses linked invoice lines.',
            'test_data':'Only explicit test flags are excluded. Names and amounts never determine test status.'},**extra}


def customer_names(db, ids):
    return dict(db.query(CRMCompany.id,CRMCompany.name).filter(CRMCompany.id.in_(set(ids))).all()) if ids else {}


def invoice_details(db,user,f,report,page,size,*,dates=True):
    q=invoices(db,user,f,dates=dates)
    if report in {'outstanding','invoice_aging'}:q=q.filter(Invoice.balance_amount>0,~Invoice.status.in_(ISSUED))
    items,total=paged(q.order_by(Invoice.issue_date.desc(),Invoice.id.desc()),page,size)
    names=customer_names(db,[x.customer_id for x in items if x.customer_id])
    tested={identity for identity, in q.with_entities(Invoice.id).filter(invoice_test(db,user),Invoice.id.in_([x.id for x in items])).all()}
    rows=[{'id':x.id,'invoice':x.invoice_number,'date':x.issue_date,'due_date':x.due_date,
        'customer':names.get(x.customer_id,f'Customer #{x.customer_id}' if x.customer_id else 'Walk-in'),
        'status':x.status,'currency':x.currency,'gross':money(x.subtotal),'discount':money(x.discount_amount),
        'tax':money(x.tax_amount),'total':money(x.total_amount),'paid':money(x.paid_amount),'balance':money(x.balance_amount),
        'days_overdue':max(0,(business_day(db,user)-x.due_date).days) if x.due_date and x.balance_amount else 0,
        'is_test':x.id in tested,'_url':f'/srm/invoices/{x.id}'} for x in items]
    columns=['invoice','date','customer','status','currency','total','paid','balance','due_date','days_overdue','gross','discount','tax','is_test']
    if report in {'outstanding','invoice_aging'}:
        for row in rows:
            days=row['days_overdue'];row['aging_bucket']='Not overdue' if not days else '1–30 days' if days<=30 else '31–60 days' if days<=60 else '61–90 days' if days<=90 else '90+ days'
        columns.insert(10,'aging_bucket')
    return result(db,user,f,report,rows,total,page,size,columns)


def payment_details(db,user,f,page,size):
    q=receipt_query(db,user,f);items,total=paged(q.order_by(Receipt.receipt_date.desc(),Receipt.id.desc()),page,size)
    names=customer_names(db,[x.customer_id for x in items if x.customer_id])
    allocated=dict(db.query(Allocation.receipt_id,func.sum(Allocation.amount)).filter(Allocation.receipt_id.in_([x.id for x in items])).group_by(Allocation.receipt_id).all())
    rows=[{'id':x.id,'receipt':x.receipt_number,'date':x.receipt_date,'customer':names.get(x.customer_id,f'Customer #{x.customer_id}'),
        'status':x.status,'method':x.payment_method,'currency':x.currency,'amount':money(x.amount),
        'allocated':money(allocated.get(x.id)),'unallocated':money(x.unallocated_amount),'reference':x.reference_number,
        '_url':f'/srm/customers/{x.customer_id}/360' if x.customer_id else '/srm/collections'} for x in items]
    return result(db,user,f,'payments',rows,total,page,size,['receipt','date','customer','status','method','currency','amount','allocated','unallocated','reference'])


def sales_details(db,user,f,page,size,report='sales'):
    q=sales_order_query(db,user);q=branch_filter(q,Order,f,db,user);q=period(q,Order.created_at,f,db,user)
    if not f.include_test:
        tests=invoice_query(db,user).filter(invoice_test(db,user)).with_entities(Invoice.sales_order_id).filter(Invoice.sales_order_id.is_not(None))
        q=q.filter(~func.coalesce(order_test(db,user),False),~Order.id.in_(tests))
    if f.customer_id:q=q.filter(Order.customer_id==f.customer_id)
    if f.cashier_id:q=q.filter(Order.created_by==f.cashier_id)
    if f.currency:q=q.filter(Order.currency==f.currency)
    if f.status:q=q.filter(Order.status==f.status)
    if f.search:q=q.filter(or_(Order.order_number.icontains(f.search,autoescape=True),Order.title.icontains(f.search,autoescape=True)))
    if f.product_id:q=q.filter(Order.id.in_(db.query(OrderLine.sales_order_id).filter(OrderLine.product_id==f.product_id)))
    if f.warehouse_id or f.payment_method:q=q.filter(Order.id.in_(invoices(db,user,f,dates=False).with_entities(Invoice.sales_order_id)))
    items,total=paged(q.order_by(Order.created_at.desc(),Order.id.desc()),page,size)
    names=customer_names(db,[x.customer_id for x in items if x.customer_id])
    billed={}
    if report=='pipeline':
        billed={r[0]:r[1:] for r in invoice_query(db,user).filter(Invoice.sales_order_id.in_([x.id for x in items]),~Invoice.status.in_(ISSUED)).with_entities(
            Invoice.sales_order_id,func.count(Invoice.id),func.sum(Invoice.total_amount),func.sum(Invoice.paid_amount),func.sum(Invoice.balance_amount)).group_by(Invoice.sales_order_id).all()}
    rows=[]
    for x in items:
        row={'id':x.id,'order':x.order_number,'date':x.created_at,'title':x.title,'customer':names.get(x.customer_id,f'Customer #{x.customer_id}' if x.customer_id else 'Walk-in'),
             'status':x.status,'currency':x.currency,'total':money(x.total_amount),'gross':money(x.subtotal),'discount':money(x.discount_amount),'tax':money(x.tax_amount),'_url':f'/srm/sales-orders/{x.id}'}
        if report=='pipeline':
            values=billed.get(x.id,(0,0,0,0));row.update(crm_deal_id=x.crm_deal_id,invoice_count=values[0],invoiced=money(values[1]),paid=money(values[2]),outstanding=money(values[3]))
        rows.append(row)
    columns=['order','date','customer','title','status','currency','total','discount','tax']
    if report=='pipeline':columns+=['crm_deal_id','invoice_count','invoiced','paid','outstanding']
    return result(db,user,f,report,rows,total,page,size,columns)


def return_details(db,user,f,page,size):
    q=returns_query(db,user,f);items,total=paged(q.order_by(Return.created_at.desc(),Return.id.desc()),page,size)
    currencies=dict(sales_order_query(db,user).filter(Order.id.in_([x.sales_order_id for x in items])).with_entities(Order.id,Order.currency).all())
    rows=[{'id':x.id,'return':x.return_number,'date':x.created_at,'customer':x.customer_name or f'Customer #{x.customer_id}',
        'status':x.status,'refund_status':x.refund_status,'method':x.refund_method,'currency':currencies.get(x.sales_order_id),
        'refund':money(x.refund_amount),'tax':money(x.tax_amount),'reason':x.reason,'_url':f'/srm/sales-orders/{x.sales_order_id}'} for x in items]
    return result(db,user,f,'returns',rows,total,page,size,['return','date','customer','status','refund_status','method','currency','refund','tax','reason'])


def overview(db,user,f):
    q=invoices(db,user,f).filter(~Invoice.status.in_(ISSUED));totals={}
    for currency,count,gross,discount,tax,total,paid,balance in q.with_entities(Invoice.currency,func.count(Invoice.id),func.sum(Invoice.subtotal),func.sum(Invoice.discount_amount),func.sum(Invoice.tax_amount),func.sum(Invoice.total_amount),func.sum(Invoice.paid_amount),func.sum(Invoice.balance_amount)).group_by(Invoice.currency).all():
        totals[currency or 'UNKNOWN']={'currency':currency or 'UNKNOWN','transactions':count,'gross':money(gross),'discounts':money(discount),'tax':money(tax),'invoiced':money(total),'invoice_paid':money(paid),'outstanding':money(balance),'returns':'0.00','collections':'0.00','average_bill':money(Decimal(str(total or 0))/count if count else 0)}
    for currency,amount in receipt_query(db,user,f).filter(Receipt.status.in_(ACTIVE_RECEIPTS)).with_entities(Receipt.currency,func.sum(Receipt.amount)).group_by(Receipt.currency).all():
        key=currency or 'UNKNOWN';totals.setdefault(key,{'currency':key,'transactions':0,'gross':'0.00','discounts':'0.00','tax':'0.00','invoiced':'0.00','invoice_paid':'0.00','outstanding':'0.00','returns':'0.00','collections':'0.00','average_bill':'0.00'})['collections']=money(amount)
    rq=returns_query(db,user,f).filter(Return.status=='completed').join(Order,Order.id==Return.sales_order_id)
    for currency,amount in rq.with_entities(Order.currency,func.sum(Return.refund_amount)).group_by(Order.currency).all():
        key=currency or 'UNKNOWN';totals.setdefault(key,{'currency':key,'transactions':0,'gross':'0.00','discounts':'0.00','tax':'0.00','invoiced':'0.00','invoice_paid':'0.00','outstanding':'0.00','returns':'0.00','collections':'0.00','average_bill':'0.00'})['returns']=money(amount)
    for row in totals.values():row['net_billed']=money(Decimal(row['invoiced'])-Decimal(row['returns']))
    trend=[{'date':str(day),'currency':currency,'transactions':count,'amount':money(value)} for day,currency,count,value in q.with_entities(Invoice.issue_date,Invoice.currency,func.count(Invoice.id),func.sum(Invoice.total_amount)).group_by(Invoice.issue_date,Invoice.currency).order_by(Invoice.issue_date).all()]
    previous_end=f.start-timedelta(days=1);previous_start=previous_end-(f.end-f.start)
    previous=invoices(db,user,f.model_copy(update={'start':previous_start,'end':previous_end})).filter(~Invoice.status.in_(ISSUED))
    comparison=[{'currency':currency,'amount':money(value),'transactions':count} for currency,value,count in previous.with_entities(Invoice.currency,func.sum(Invoice.total_amount),func.count(Invoice.id)).group_by(Invoice.currency).all()]
    return result(db,user,f,'overview',list(totals.values()),len(totals),1,100,['currency','transactions','gross','discounts','tax','invoiced','returns','net_billed','collections','outstanding','average_bill'],trend=trend,comparison=comparison,comparison_period={'start':str(previous_start),'end':str(previous_end)})


def customer_details(db,user,f,page,size):
    q=invoices(db,user,f).filter(~Invoice.status.in_(ISSUED))
    selected=q.with_entities(Invoice.customer_id.label('customer'),Invoice.currency.label('currency'),func.count(Invoice.id).label('visits'),func.sum(Invoice.total_amount).label('total'),func.sum(Invoice.paid_amount).label('paid')).group_by(Invoice.customer_id,Invoice.currency).subquery()
    life=invoices(db,user,f,dates=False).filter(~Invoice.status.in_(ISSUED)).with_entities(Invoice.customer_id.label('customer'),Invoice.currency.label('currency'),func.count(Invoice.id).label('visits'),func.sum(Invoice.balance_amount).label('outstanding'),func.max(Invoice.issue_date).label('last_purchase')).group_by(Invoice.customer_id,Invoice.currency).subquery()
    people=invoices(db,user,f.model_copy(update={'currency':''}),dates=False).filter(~Invoice.status.in_(ISSUED)).with_entities(Invoice.customer_id.label('customer'),func.count(Invoice.id).label('visits'),func.max(Invoice.issue_date).label('last_purchase')).group_by(Invoice.customer_id).subquery()
    grouped=db.query(life.c.customer,life.c.currency,func.coalesce(selected.c.visits,0),func.coalesce(selected.c.total,0),func.coalesce(selected.c.paid,0),life.c.outstanding,people.c.last_purchase,people.c.visits).join(people,func.coalesce(people.c.customer,0)==func.coalesce(life.c.customer,0)).outerjoin(selected,and_(func.coalesce(selected.c.customer,0)==func.coalesce(life.c.customer,0),func.coalesce(selected.c.currency,'UNKNOWN')==func.coalesce(life.c.currency,'UNKNOWN')))
    today=business_day(db,user)
    if f.customer_segment=='repeat':grouped=grouped.filter(life.c.customer.is_not(None),people.c.visits>1)
    if f.customer_segment=='inactive':grouped=grouped.filter(life.c.customer.is_not(None),people.c.last_purchase<=today-timedelta(days=f.inactive_days))
    if f.customer_segment=='outstanding':grouped=grouped.filter(life.c.outstanding>0)
    items,total=paged(grouped.order_by(func.coalesce(selected.c.total,0).desc(),life.c.customer,life.c.currency),page,size)
    names=customer_names(db,[x[0] for x in items if x[0]])
    today=business_day(db,user)
    rows=[{'id':f'{ident or 0}:{currency}','customer_id':ident,'customer':names.get(ident,f'Customer #{ident}' if ident else 'Walk-in / anonymous'),
        'currency':currency,'purchases':visits,'lifetime_purchases':lifetime,'repeat_customer':bool(ident and lifetime>1),'total':money(amount),'paid':money(paid),'outstanding':money(outstanding),
        'average_bill':money(Decimal(str(amount or 0))/visits) if visits else None,'last_purchase':last,'days_inactive':(today-last).days if last else None,
        'inactive':bool(ident and last and (today-last).days>=f.inactive_days),'_url':f'/srm/customers/{ident}/360' if ident else None} for ident,currency,visits,amount,paid,outstanding,last,lifetime in items]
    return result(db,user,f,'customers',rows,total,page,size,['customer','currency','purchases','lifetime_purchases','repeat_customer','total','paid','outstanding','average_bill','last_purchase','days_inactive','inactive'],insight_basis='Purchases, total and paid use the selected period. Lifetime visits and last purchase identify the same customer across currencies; financial balances remain separate by currency. Anonymous sales are not repeat or inactive people.')


def offering_line_kind():
    return case(
        (OrderLine.service_type.in_(("product", "membership", "subscription", "bundle")), OrderLine.service_type),
        (Product.product_type.in_(("service", "services")), "service"),
        (Product.product_type.in_(("membership", "subscription", "bundle")), Product.product_type),
        (Product.id.is_not(None), "product"),
        (OrderLine.service_type.in_(("service", "services")), "service"),
        else_="other",
    )


def offering_sales(db, user, filters, kind, page, size):
    """Group billed quantities and amounts by offering and invoice currency."""
    f = resolved(db, user, filters, allow_pack=True)
    if f.start > f.end or (f.end - f.start).days > 3660:
        raise HTTPException(422, "Choose a valid reporting period of ten years or less")
    if db.info.get("business_pack_scope") is None:
        visible = invoices(db, user, f)
    else:
        # Report flags belong to the native reporting workspace. Pack invoices
        # remain scoped by the selected pack and its invoice read authority.
        visible = period(invoice_query(db, user), Invoice.issue_date, f, db, user)
    visible = invoice_ids(visible.filter(Invoice.status.notin_(ISSUED)))
    kind_column = offering_line_kind()
    name = func.coalesce(Product.item_name, OrderLine.item_code, InvoiceLine.description)
    gross = func.sum(InvoiceLine.line_total)
    query = (
        db.query(kind_column.label("kind"), name.label("name"), Invoice.currency, func.max(Product.id).label("offering_id"),
                 func.sum(InvoiceLine.quantity).label("quantity"),
                 func.sum(InvoiceLine.tax_amount).label("tax"), gross.label("gross"))
        .select_from(Invoice)
        .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
        .outerjoin(OrderLine, and_(InvoiceLine.source_type == "sales_order_line",
                                  InvoiceLine.source_id == OrderLine.id))
        .outerjoin(Product, and_(Product.id == OrderLine.product_id,
                                Product.organization_id == Invoice.organization_id))
        .filter(Invoice.id.in_(visible))
    )
    if kind:
        query = query.filter(kind_column == kind)
    grouped = query.group_by(kind_column, OrderLine.product_id, name, Invoice.currency)
    totals = query.with_entities(Invoice.currency, gross).group_by(Invoice.currency).order_by(Invoice.currency).all()
    rows = grouped.order_by(gross.desc(), kind_column, name, Invoice.currency, OrderLine.product_id)
    items = rows.offset((page - 1) * size).limit(size + 1).all()
    return {
        "start": f.start,
        "end": f.end,
        "has_more": len(items) > size,
        "totals": [{"currency": currency, "gross": money(amount)} for currency, amount in totals],
        "items": [
            {"kind": row.kind, "offering_id": row.offering_id, "name": row.name, "currency": row.currency,
             "quantity": number(row.quantity), "tax": money(row.tax), "gross": money(row.gross)}
            for row in items[:size]
        ],
    }


def audience_purchases(db, user, filters, kind, offering_id, *, customer_id=None):
    """Purchase evidence comes from scoped, issued invoices with a linked catalog line."""
    from app.apps.srm.anonymous_cash import installed
    from app.shared.master_data import companies

    pack = db.info.get("business_pack_scope") is not None
    visible = invoice_query(db, user) if pack else invoices(db, user, Filters(), dates=False)
    visible = visible.filter(Invoice.status.notin_(ISSUED), Invoice.issue_date.is_not(None))
    if filters.start:
        visible = visible.filter(Invoice.issue_date >= filters.start)
    if filters.end:
        visible = visible.filter(Invoice.issue_date <= filters.end)

    parties = companies(db, user, "srm")
    if filters.search:
        parties = parties.filter(CRMCompany.name.icontains(filters.search, autoescape=True))
    if installed(db.connection()):
        from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
        table = AnonymousCashAccount.__table__
        anonymous = db.connection().scalars(select(table.c.customer_id).where(
            table.c.organization_id == tenant(user), table.c.customer_id.is_not(None),
        )).all()
        parties = parties.filter(CRMCompany.id.not_in(anonymous))
    if customer_id is not None:
        parties = parties.filter(CRMCompany.id == customer_id)

    if pack:
        from app.apps.srm.service_checkout_models import POSServiceCheckout
        from app.shared.catalog_branches import availability_clause, selected_branch
        offerings = db.query(Product).filter(
            Product.organization_id == tenant(user), Product.deleted_at.is_(None),
            availability_clause(Product, selected_branch(user)),
        )
        if offering_id is not None:
            offerings = offerings.filter(Product.id == offering_id)
    else:
        offerings = product_query(db, user, Filters(product_id=offering_id))
    line_kind = offering_line_kind()
    query = (
        db.query(Invoice.customer_id.label("customer_id"), Invoice.id.label("invoice_id"),
                 Invoice.issue_date.label("purchased_on"), Product.id.label("offering_id"),
                 Product.item_name.label("offering_name"), line_kind.label("kind"))
        .select_from(Invoice)
        .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
        .join(OrderLine, and_(InvoiceLine.source_type == "sales_order_line",
                              InvoiceLine.source_id == OrderLine.id,
                              Invoice.sales_order_id == OrderLine.sales_order_id))
        .join(Product, Product.id == OrderLine.product_id)
        .filter(Invoice.id.in_(invoice_ids(visible)), InvoiceLine.quantity > 0,
                Invoice.customer_id.in_(parties.with_entities(CRMCompany.id)),
                Product.id.in_(offerings.with_entities(Product.id)),
                line_kind.in_(AUDIENCE_KINDS))
    )
    if pack:
        # Retail checkout validates the catalog and enrolls the complete invoice
        # graph in its exact pack context. Other purchase producers are not inferred.
        query = query.join(POSServiceCheckout, POSServiceCheckout.invoice_id == Invoice.id).filter(
            POSServiceCheckout.state == "committed",
            POSServiceCheckout.sales_order_id == Invoice.sales_order_id,
        )
    return query.filter(line_kind == kind) if kind else query


def audience_channels(db, customers, can_prepare, unavailable_reason="Sales export access is required"):
    from app.apps.communication.models import CommunicationConsent, CommunicationOptOut
    from app.apps.communication.services.delivery import normalize_email
    from app.core.input_validation import email_address
    from app.shared.master_data import normalized_phone

    if not can_prepare:
        return {row.id: {channel: (None, unavailable_reason) for channel in AUDIENCE_CHANNELS}
                for row in customers}
    if not customers:
        return {}

    destinations = {}
    emails = set()
    phones = set()
    phone_keys = {}
    for row in customers:
        try:
            email = normalize_email(email_address(row.email))
        except (TypeError, ValueError):
            email = None
        try:
            national, phone = normalized_phone(row.phone, row.phone_country_code)
            phone_keys[row.id] = {(row.phone, row.phone_country_code), (national, row.phone_country_code)}
        except (TypeError, ValueError):
            phone = None
        if email:
            emails.add(email)
        if phone:
            phones.add(phone)
        destinations[row.id] = {"email": email, "sms": phone, "whatsapp": phone}

    consent = CommunicationConsent
    customer_types = ("account", "company", "customer", "companies")
    matches = [and_(consent.record_type.in_(customer_types), consent.record_id.in_(destinations))]
    if emails:
        matches.append(func.lower(consent.email).in_(emails))
    if phone_keys:
        phones_by_code = set().union(*phone_keys.values())
        matches.append(tuple_(consent.phone, consent.phone_country_code).in_(phones_by_code))
        matches.append(consent.phone.in_(phones))
    refusals = db.query(consent).filter(
        consent.consent_type.in_(AUDIENCE_CHANNELS),
        func.lower(consent.status).in_(("opted_out", "unsubscribed", "denied")),
        or_(*matches),
    ).all()
    blocked_records = {(row.record_id, row.consent_type) for row in refusals if row.record_type in customer_types}
    blocked_phones = {(row.phone, row.phone_country_code, row.consent_type) for row in refusals if row.phone}
    blocked_destinations = {(normalize_email(row.email), row.consent_type) for row in refusals if row.email}
    blocked_destinations.update((row.phone, row.consent_type) for row in refusals if row.phone in phones)
    opt_out = CommunicationOptOut
    blocked_destinations.update(db.query(opt_out.email, opt_out.channel).filter(
        opt_out.email.in_(emails | phones), opt_out.channel.in_(AUDIENCE_CHANNELS),
    ).all())

    results = {}
    for row in customers:
        status = (row.status or "").strip().lower().replace("_", " ").replace("-", " ")
        channels = {}
        for channel, destination in destinations[row.id].items():
            denied = (
                (row.id, channel) in blocked_records or (destination, channel) in blocked_destinations
                or (channel != "email" and any((phone, code, channel) in blocked_phones
                                               for phone, code in phone_keys.get(row.id, ())))
            )
            if status in {"do not contact", "blocked", "inactive"} or denied:
                channels[channel] = (None, "Customer preferences block this channel")
            elif not destination:
                missing = "a valid email address" if channel == "email" else "a valid phone number with a country code"
                channels[channel] = (None, f"Add {missing}")
            else:
                channels[channel] = (destination, None)
        results[row.id] = channels
    return results


def offering_audience(db, user, filters, kind, offering_id, page, size, can_prepare):
    if db.info.get("business_pack_scope") is not None:
        return retail_offering_audience(db, user, filters, kind, offering_id, page, size)
    purchases = audience_purchases(db, user, filters, kind, offering_id).subquery()
    latest = func.max(purchases.c.purchased_on)
    summary = (
        db.query(purchases.c.customer_id, func.count(func.distinct(purchases.c.invoice_id)).label("purchase_count"),
                 latest.label("last_purchase"))
        .group_by(purchases.c.customer_id)
        .subquery()
    )
    rows, total = paged(db.query(CRMCompany, summary.c.purchase_count, summary.c.last_purchase)
                        .join(summary, summary.c.customer_id == CRMCompany.id)
                        .order_by(summary.c.last_purchase.desc(), CRMCompany.id), page, size)
    customers = [company for company, _, _ in rows]
    channels = audience_channels(db, customers, can_prepare)
    offerings = defaultdict(list)
    if customers:
        # Keep a customer's result compact, even if they have purchased hundreds of items.
        ranked = (
            db.query(purchases.c.customer_id, purchases.c.offering_id, purchases.c.offering_name, purchases.c.kind,
                     func.row_number().over(partition_by=purchases.c.customer_id,
                                            order_by=(latest.desc(), purchases.c.offering_id)).label("position"))
            .filter(purchases.c.customer_id.in_([row.id for row in customers]))
            .group_by(purchases.c.customer_id, purchases.c.offering_id, purchases.c.offering_name, purchases.c.kind)
            .subquery()
        )
        for row in db.query(ranked).filter(ranked.c.position <= 13).order_by(ranked.c.customer_id, ranked.c.position):
            offerings[row.customer_id].append({"id": row.offering_id, "name": row.offering_name, "kind": row.kind})
    return audience_payload(filters, page, size, rows, total, offerings, channels)


def retail_offering_audience(db, user, filters, kind, offering_id, page, size):
    # Selected-pack ORM guards require mapped sources. Keep the financial
    # grouping on explicit invoice, checkout, customer and catalog models.
    purchases = audience_purchases(db, user, filters, kind, offering_id)
    total = purchases.with_entities(func.count(func.distinct(Invoice.customer_id))).scalar() or 0
    last = func.max(Invoice.issue_date)
    rows = (
        purchases.join(CRMCompany, CRMCompany.id == Invoice.customer_id)
        .with_entities(CRMCompany, func.count(func.distinct(Invoice.id)), last)
        .group_by(CRMCompany.id).order_by(last.desc(), CRMCompany.id)
        .offset((page - 1) * size).limit(size).all()
    )
    customers = [company for company, _, _ in rows]
    groups = defaultdict(list)
    if customers:
        line_kind = offering_line_kind()
        values = (
            purchases.filter(Invoice.customer_id.in_([customer.id for customer in customers]))
            .with_entities(Invoice.customer_id, Product.id, Product.item_name, line_kind)
            .group_by(Invoice.customer_id, Product.id, Product.item_name, line_kind)
            .order_by(Invoice.customer_id, last.desc(), Product.id)
        )
        for customer_id, ident, name, offering_kind in values:
            if len(groups[customer_id]) < 13:
                groups[customer_id].append({"id": ident, "name": name, "kind": offering_kind})
    channels = audience_channels(db, customers, False, "Message drafts are unavailable in the selected Business Pack")
    return audience_payload(filters, page, size, rows, total, groups, channels)


def audience_payload(filters, page, size, rows, total, offerings, channels):
    return {
        "start": filters.start, "end": filters.end, "page": page, "page_size": size,
        "total": total, "has_more": page * size < total,
        "items": [
            {"id": company.id, "name": company.name, "purchase_count": count, "last_purchase": last,
             "offerings": offerings[company.id][:12], "offerings_more": len(offerings[company.id]) > 12,
             "channels": {channel: {"available": destination is not None, "reason": reason}
                          for channel, (destination, reason) in channels[company.id].items()}}
            for company, count, last in rows
        ],
    }


def offering_audience_draft(db, user, filters, kind, offering_id, customer_id, channel):
    purchases = audience_purchases(db, user, filters, kind, offering_id, customer_id=customer_id)
    company = db.query(CRMCompany).filter(CRMCompany.id.in_(purchases.with_entities(Invoice.customer_id))).first()
    if not company:
        raise HTTPException(404, "Customer purchase is unavailable in your scope")
    destination, reason = audience_channels(db, [company], True)[company.id][channel]
    if not destination:
        raise HTTPException(422, reason)
    body = "Hello, we're reaching out to see if you have any questions or need help. Please reply if we can assist."
    subject = "Checking in"
    if channel == "whatsapp":
        compose_url = f"https://wa.me/{destination.lstrip('+')}?text={quote(body, safe='')}"
    elif channel == "sms":
        compose_url = f"sms:{destination}?body={quote(body, safe='')}"
    else:
        compose_url = f"mailto:{quote(destination, safe='@')}?subject={quote(subject, safe='')}&body={quote(body, safe='')}"
    return {"customer_id": company.id, "name": company.name, "channel": channel, "compose_url": compose_url,
            "body": body, "subject": subject if channel == "email" else None}


def product_details(db,user,f,page,size):
    ids=invoice_ids(invoices(db,user,f).filter(~Invoice.status.in_(ISSUED)))
    q=db.query(Product,Invoice.currency,func.sum(InvoiceLine.quantity).label('quantity'),func.sum(InvoiceLine.line_total-InvoiceLine.tax_amount).label('revenue'),func.sum(InvoiceLine.discount_amount).label('discount'),func.sum(InvoiceLine.tax_amount).label('tax'))\
        .join(OrderLine,OrderLine.product_id==Product.id).join(InvoiceLine,and_(InvoiceLine.source_type=='sales_order_line',InvoiceLine.source_id==OrderLine.id)).join(Invoice,Invoice.id==InvoiceLine.invoice_id).filter(Invoice.id.in_(ids))
    if f.product_id:q=q.filter(Product.id==f.product_id)
    q=q.group_by(Product.id,Invoice.currency).order_by(func.sum(InvoiceLine.line_total-InvoiceLine.tax_amount).desc(),Product.id,Invoice.currency)
    items,total=paged(q,page,size)
    order_numbers=sales_order_query(db,user).filter(Order.id.in_(invoices(db,user,f).with_entities(Invoice.sales_order_id))).with_entities(Order.order_number)
    costs={r[0]:r[1:] for r in db.query(Movement.product_id,func.sum(Movement.quantity_out),func.sum(Movement.quantity_out*Movement.rate)).filter(Movement.organization_id==tenant(user),Movement.product_id.in_([p.id for p,*_ in items]),Movement.reference_number.in_(order_numbers),Movement.movement_type.in_(ISSUES)).group_by(Movement.product_id).all()}
    rows=[]
    for p,currency,qty,revenue,discount,tax in items:
        issued,cost=costs.get(p.id,(0,None));known=p.product_type!='service' and Decimal(str(issued or 0))==Decimal(str(qty or 0)) and cost is not None
        rows.append({'id':f'{p.id}:{currency}','product_id':p.id,'product':p.item_name,'sku':p.sku,'currency':currency,'quantity':number(qty),'billed_ex_tax':money(revenue),'discount':money(discount),'tax':money(tax),'recorded_issue_cost':money(cost) if known else None,'gross_profit':money(Decimal(str(revenue or 0))-Decimal(str(cost or 0))) if known else None,'cost_coverage':'Complete matched stock issues' if known else 'Cost unavailable / incomplete','_url':f'/srm/inventory/items/{p.id}'})
    return result(db,user,f,'products',rows,total,page,size,['product','sku','currency','quantity','billed_ex_tax','discount','tax','recorded_issue_cost','gross_profit','cost_coverage'],cost_basis='Historical issue rates of matched order movements. Gross profit is unavailable when cost coverage is incomplete; returns are shown separately.')


def stock_details(db,user,f,page,size,reconcile=False):
    # Aggregate balances and ledger first, then join one row per item. No join multiplication.
    b=db.query(Balance.product_id.label('pid'),func.sum(Balance.quantity).label('quantity'),func.sum(Balance.quantity*Balance.average_cost).label('value')).filter(Balance.organization_id==tenant(user))
    if f.warehouse_id:b=b.filter(Balance.warehouse_id==f.warehouse_id)
    b=b.group_by(Balance.product_id).subquery()
    m=db.query(Movement).filter(Movement.organization_id==tenant(user))
    if f.warehouse_id:m=m.filter(Movement.warehouse_id==f.warehouse_id)
    first_day_opening=and_(Movement.movement_date==f.start,Movement.movement_type=='opening_stock')
    before=m.filter(or_(Movement.movement_date<f.start,first_day_opening)).with_entities(Movement.product_id.label('pid'),func.sum(Movement.quantity_in-Movement.quantity_out).label('opening')).group_by(Movement.product_id).subquery()
    net=Movement.quantity_in-Movement.quantity_out
    during=m.filter(Movement.movement_date>=f.start,Movement.movement_date<=f.end,~func.coalesce(first_day_opening,False)).with_entities(Movement.product_id.label('pid'),func.sum(Movement.quantity_in).label('incoming'),func.sum(Movement.quantity_out).label('outgoing'),func.sum(case((Movement.movement_type.in_(SALES_ISSUES),-net),else_=0)).label('sales_issues'),func.sum(case((Movement.movement_type.in_(STOCK_RECEIPTS),net),else_=0)).label('receipts'),func.sum(case((Movement.movement_type.in_(STOCK_RETURNS),net),else_=0)).label('returns'),func.sum(case((func.coalesce(Movement.movement_type,'').not_in((*SALES_ISSUES,*STOCK_RECEIPTS,*STOCK_RETURNS)),net),else_=0)).label('adjustments')).group_by(Movement.product_id).subquery()
    end=m.filter(Movement.movement_date<=f.end).with_entities(Movement.product_id.label('pid'),func.sum(Movement.quantity_in-Movement.quantity_out).label('ledger_close')).group_by(Movement.product_id).subquery()
    recent=m.filter(Movement.movement_date>=business_day(db,user)-timedelta(days=29),Movement.movement_date<=business_day(db,user),Movement.movement_type.in_(ISSUES)).with_entities(Movement.product_id.label('pid'),func.sum(Movement.quantity_out).label('units')).group_by(Movement.product_id).subquery()
    purchase=branch_filter(db.query(Purchase).filter(Purchase.organization_id==tenant(user),Purchase.deleted_at.is_(None),Purchase.status.in_(('draft','approved','sent','ordered','partially_received'))),Purchase,f,db,user)
    incoming=db.query(PurchaseLine.product_id,func.sum(case((PurchaseLine.quantity>func.coalesce(PurchaseLine.received_quantity,0),PurchaseLine.quantity-func.coalesce(PurchaseLine.received_quantity,0)),else_=0))).filter(PurchaseLine.purchase_order_id.in_(purchase.with_entities(Purchase.id)))
    if f.warehouse_id:incoming=incoming.filter(PurchaseLine.warehouse_id==f.warehouse_id)
    open_units=dict(incoming.group_by(PurchaseLine.product_id).all())
    q=product_query(db,user,f).filter(Product.product_type!='service',Product.track_inventory.is_(True)).outerjoin(b,b.c.pid==Product.id).outerjoin(before,before.c.pid==Product.id).outerjoin(during,during.c.pid==Product.id).outerjoin(end,end.c.pid==Product.id).outerjoin(recent,recent.c.pid==Product.id)
    threshold=case((Product.reorder_level>0,Product.reorder_level),(Product.min_stock>0,Product.min_stock),else_=0)
    quantity=func.coalesce(b.c.quantity,0)
    if f.low_only:q=q.filter(or_(quantity<=0,and_(threshold>0,quantity<=threshold)))
    if reconcile and f.discrepancy_only:
        q=q.filter(quantity!=func.coalesce(end.c.ledger_close,0)) if f.end>=business_day(db,user) else q.filter(literal(False))
    urgency=case((quantity<=0,0),(and_(threshold>0,quantity<=threshold),1),else_=2)
    q=q.with_entities(Product,b.c.quantity,b.c.value,before.c.opening,during.c.incoming,during.c.outgoing,during.c.sales_issues,end.c.ledger_close,recent.c.units,during.c.receipts,during.c.returns,during.c.adjustments).order_by(urgency,quantity,Product.item_name,Product.id)
    items,total=paged(q,page,size);rows=[]
    supplier_orders=branch_filter(db.query(Purchase).filter(Purchase.organization_id==tenant(user),Purchase.deleted_at.is_(None)),Purchase,f,db,user)
    supplier_rows=db.query(PurchaseLine.product_id,Purchase.vendor_id,Purchase.vendor_name,Purchase.po_number).join(Purchase,Purchase.id==PurchaseLine.purchase_order_id).filter(Purchase.id.in_(supplier_orders.with_entities(Purchase.id)),PurchaseLine.product_id.in_([x[0].id for x in items])).order_by(Purchase.id.desc()).all() if items else []
    suppliers={}
    for pid,vid,name,po in supplier_rows:
        if pid not in suppliers and (vid or name):suppliers[pid]=(vid,name,po)
    receipt_sources=branch_filter(db.query(GoodsReceipt).filter(GoodsReceipt.organization_id==tenant(user),GoodsReceipt.status.in_(('posted','received','completed'))),GoodsReceipt,f,db,user)
    receipt_rows=db.query(GoodsReceiptLine.product_id,GoodsReceipt.vendor_id,GoodsReceipt.vendor_name,GoodsReceipt.grn_number).join(GoodsReceipt,GoodsReceipt.id==GoodsReceiptLine.goods_receipt_id).filter(GoodsReceipt.id.in_(receipt_sources.with_entities(GoodsReceipt.id)),GoodsReceiptLine.product_id.in_([x[0].id for x in items])).order_by(GoodsReceipt.receipt_date.desc(),GoodsReceipt.id.desc()).all() if items else []
    receipt_suppliers={}
    for pid,vid,name,grn in receipt_rows:
        if pid not in receipt_suppliers and (vid or name):receipt_suppliers[pid]=(vid,name,grn)
    configured_ids={int((x[0].metadata_json or {}).get('supplier_id') or (x[0].metadata_json or {}).get('vendor_id')) for x in items if str((x[0].metadata_json or {}).get('supplier_id') or (x[0].metadata_json or {}).get('vendor_id') or '').isdigit()}
    supplier_names=customer_names(db,configured_ids)
    for p,qty,value,opening,incoming,outgoing,issues,closing,usage,received,returned,adjustments in items:
        meta=p.metadata_json or {};qty=Decimal(str(qty or 0));level=Decimal(str(p.reorder_level or p.min_stock or 0));daily=Decimal(str(usage or 0))/30
        try:lead=max(0,min(365,int(meta.get('lead_time_days',7))));safety=max(0,min(365,int(meta.get('safety_days',7))))
        except (ValueError,TypeError):lead=safety=7
        pending=Decimal(str(open_units.get(p.id) or 0))
        target=max(Decimal(str(p.max_stock or 0)),level,daily*(lead+safety));suggested=max(Decimal(0),target-qty-pending)
        if p.unit_code in {'PCS','EA','NOS'}:suggested=suggested.to_integral_value(rounding=ROUND_CEILING)
        low=qty<=0 or (level>0 and qty<=level)
        row={'id':p.id,'product':p.item_name,'sku':p.sku,'currency':str(meta.get('currency','INR')),'on_hand':number(qty),'stock_value':money(value),'threshold':number(level),'low_stock':low,'priority':'Out of stock' if qty<=0 else 'Low stock' if low else 'Healthy','average_daily_usage':round(number(daily),3),'days_cover':round(number(qty/daily),1) if daily>0 else None,'lead_time_days':lead,'suggested_reorder':number(suggested),'supplier':str(meta.get('supplier_name') or meta.get('vendor_name') or ''),'supplier_id':meta.get('supplier_id') or meta.get('vendor_id'),'warehouse_id':f.warehouse_id or p.default_warehouse_id,'_url':f'/srm/inventory/items/{p.id}'}
        if reconcile:
            expected=Decimal(str(opening or 0))+Decimal(str(received or 0))+Decimal(str(returned or 0))-Decimal(str(issues or 0))+Decimal(str(adjustments or 0));actual=Decimal(str(closing or 0));current= f.end>=business_day(db,user)
            row.update(opening=number(opening),receipts=number(received),customer_returns=number(returned),adjustments=number(adjustments),receipts_and_returns=number(incoming),sales_and_other_issues=number(outgoing),sales_issues=number(issues),expected_closing=number(expected),ledger_closing=number(actual),quantity_difference=number(qty-actual) if current else None,reconciled=(qty==actual and expected==actual) if current else None,comparison='Current warehouse balance' if current else 'Historical ledger only; no independent historical balance')
        vid,vname,po=suppliers.get(p.id,(None,None,None));grn=None
        if not (vid or vname):vid,vname,grn=receipt_suppliers.get(p.id,(None,None,None))
        configured=row['supplier_id']
        if configured and not row['supplier']:row['supplier']=supplier_names.get(int(configured)) if str(configured).isdigit() else ''
        row['supplier_id']=configured or vid
        row['supplier']=row['supplier'] or (vname if not configured or str(configured)==str(vid) else '') or (f'Supplier #{configured}' if configured else '')
        row['supplier_last_po']=po;row['supplier_source']=po or grn if not configured or str(configured)==str(vid) else 'Product supplier setting'
        row['open_purchase_quantity']=number(pending)
        rows.append(row)
    report='reconciliation' if reconcile else 'stock'
    cols=['product','sku','opening','receipts','customer_returns','sales_issues','adjustments','expected_closing','ledger_closing','on_hand','quantity_difference','reconciled','comparison'] if reconcile else ['product','sku','currency','on_hand','stock_value','threshold','priority','average_daily_usage','days_cover','lead_time_days','open_purchase_quantity','suggested_reorder','supplier','supplier_source']
    return result(db,user,f,report,rows,total,page,size,cols,stock_basis='Opening includes opening-stock postings on the first reporting day. Later opening entries, transfers and production are adjustments. On hand is current scoped warehouse balance; historical periods do not compare against today’s balance.',reorder_basis='Target is max(maximum stock, reorder threshold, recent daily issues × (lead time + safety days)) minus outstanding purchase quantities, including drafts. Review supplier commitments before ordering.')


def low_stock_ids(db,user,f):
    balances=db.query(Balance.product_id.label('pid'),func.sum(Balance.quantity).label('quantity')).filter(Balance.organization_id==tenant(user))
    if f.warehouse_id:balances=balances.filter(Balance.warehouse_id==f.warehouse_id)
    balances=balances.group_by(Balance.product_id).subquery();quantity=func.coalesce(balances.c.quantity,0)
    threshold=case((Product.reorder_level>0,Product.reorder_level),(Product.min_stock>0,Product.min_stock),else_=0)
    q=product_query(db,user,f).filter(Product.product_type!='service',Product.track_inventory.is_(True)).outerjoin(balances,balances.c.pid==Product.id).filter(or_(quantity<=0,and_(threshold>0,quantity<=threshold)))
    return {str(identity) for identity, in q.with_entities(Product.id).yield_per(500)}


def other_details(db,user,f,report,page,size):
    if report=='contracts':
        q=db.query(Contract).filter(Contract.organization_id==tenant(user),Contract.deleted_at.is_(None))
        if not can_view_all_srm(user):q=q.filter(or_(Contract.created_by==user.id,Contract.sales_order_id.in_(sales_order_query(db,user).with_entities(Order.id))))
        if not f.include_test:q=q.filter(~flag(db,user,'contract',Contract.id),~func.coalesce(Contract.sales_order_id.in_(test_order_sources(db,user)),False))
        q=branch_filter(q,Contract,f,db,user)
        if f.customer_id:q=q.filter(Contract.customer_id==f.customer_id)
        if f.status:q=q.filter(Contract.status==f.status)
        if f.currency:q=q.filter(Contract.currency==f.currency)
        if f.search:q=q.filter(Contract.contract_number.icontains(f.search,autoescape=True))
        q=period(q,Contract.created_at,f,db,user);items,total=paged(q.order_by(Contract.id.desc()),page,size)
        rows=[{'id':x.id,'contract':x.contract_number,'customer_id':x.customer_id,'status':x.status,'currency':x.currency,'value':money(x.contract_value),'start':x.effective_date,'end':x.expiry_date,'_url':f'/srm/contracts/{x.id}'} for x in items]
        return result(db,user,f,report,rows,total,page,size,['contract','customer_id','status','currency','value','start','end'])
    if report=='recurring':
        q=db.query(Milestone,Plan,Engagement).join(Plan,Plan.id==Milestone.billing_plan_id).join(Engagement,Engagement.id==Plan.engagement_id).filter(Plan.organization_id==tenant(user),Engagement.id.in_(engagement_query(db,user).with_entities(Engagement.id)),Milestone.metadata_json['recurring'].as_boolean().is_(True))
        if not f.include_test:q=q.filter(~func.coalesce(test_engagement_sources(db,user),False))
        q=period(q,Milestone.due_date,f,db,user)
        if f.customer_id:q=q.filter(Engagement.customer_id==f.customer_id)
        if f.currency:q=q.filter(Plan.currency==f.currency)
        if f.status:q=q.filter(Milestone.status==f.status)
        items,total=paged(q.order_by(Milestone.due_date,Milestone.id),page,size)
        drafts=[m.invoice_draft_id for m,_,_ in items if m.invoice_draft_id]
        billed={row.invoice_draft_id:row for row in invoice_query(db,user).filter(Invoice.invoice_draft_id.in_(drafts)).order_by(Invoice.id).all()} if drafts else {}
        rows=[{'id':m.id,'plan_name':p.name,'customer_id':e.customer_id,'status':billed[m.invoice_draft_id].status if m.invoice_draft_id in billed else m.status,'date':m.due_date,'currency':p.currency,'total':money(m.amount),'invoice_number':billed[m.invoice_draft_id].invoice_number if m.invoice_draft_id in billed else None,'_url':f'/srm/engagements/{e.id}'} for m,p,e in items]
        return result(db,user,f,report,rows,total,page,size,['invoice_number','plan_name','customer_id','status','date','currency','total'])
    if report in {'profitability','project_profitability','customer_profitability','cash_margin','sales_to_delivery_margin'}:
        from app.services.metrics.sales import latest_profitability_query
        q=latest_profitability_query(db,user).join(Engagement,Engagement.id==Profit.engagement_id)
        if not f.include_test:q=q.filter(~func.coalesce(test_engagement_sources(db,user),False))
        q=period(q,Profit.snapshot_at,f,db,user)
        if f.customer_id:q=q.filter(Engagement.customer_id==f.customer_id)
        if f.currency:q=q.filter(Engagement.currency==f.currency)
        if report in {'project_profitability','customer_profitability','cash_margin','sales_to_delivery_margin'}:
            group=Engagement.pms_project_id if report=='project_profitability' else Engagement.customer_id if report=='customer_profitability' else Engagement.currency
            if report=='project_profitability':q=q.filter(Engagement.pms_project_id.is_not(None))
            grouped=q.with_entities(group,Engagement.currency,func.sum(Profit.invoiced_amount),func.sum(Profit.collected_amount),func.sum(Profit.cost_amount),func.sum(Profit.gross_margin_amount),func.sum(Profit.cash_margin_amount)).group_by(group,Engagement.currency)
            items,total=paged(grouped.order_by(group,Engagement.currency),page,size)
            names=customer_names(db,[x[0] for x in items if x[0]]) if report=='customer_profitability' else {}
            rows=[{'id':f'{key}:{currency}','group':names.get(key,f'Project #{key}' if report=='project_profitability' else f'Customer #{key}' if report=='customer_profitability' else currency),'currency':currency,'invoiced':money(inv),'collected':money(paid),'delivery_cost':money(cost),'gross_margin':money(gross),'cash_margin':money(cash)} for key,currency,inv,paid,cost,gross,cash in items]
            return result(db,user,f,report,rows,total,page,size,['group','currency','invoiced','collected','delivery_cost','gross_margin','cash_margin'],cost_basis='Latest authorized profitability snapshot per engagement, grouped by source currency. Snapshot dates use the selected reporting period.')
        items,total=paged(q.add_columns(Engagement.engagement_number,Engagement.customer_id,Engagement.currency).order_by(Profit.snapshot_at.desc(),Profit.id.desc()),page,size)
        rows=[{'id':x.id,'engagement':name,'customer_id':customer,'currency':currency,'snapshot_at':x.snapshot_at,'gross_margin':money(x.gross_margin_amount),'cash_margin':money(x.cash_margin_amount),'_url':f'/srm/engagements/{x.engagement_id}'} for x,name,customer,currency in items]
        return result(db,user,f,report,rows,total,page,size,['engagement','customer_id','currency','snapshot_at','gross_margin','cash_margin'])
    if report=='payment_reconciliation':
        q=invoices(db,user,f);items,total=paged(q.order_by(Invoice.id.desc()),page,size)
        allocated=dict(db.query(Allocation.invoice_id,func.sum(Allocation.amount)).join(Receipt,Receipt.id==Allocation.receipt_id).filter(Allocation.invoice_id.in_([x.id for x in items]),Receipt.status.in_(ACTIVE_RECEIPTS)).group_by(Allocation.invoice_id).all())
        rows=[{'id':x.id,'invoice':x.invoice_number,'currency':x.currency,'invoiced':money(x.total_amount),'invoice_paid':money(x.paid_amount),'confirmed_allocations':money(allocated.get(x.id)),'balance':money(x.balance_amount),'allocation_difference':money(Decimal(str(x.paid_amount or 0))-Decimal(str(allocated.get(x.id) or 0))),'balance_difference':money(Decimal(str(x.total_amount or 0))-Decimal(str(x.paid_amount or 0))-Decimal(str(x.balance_amount or 0))),'review_required':Decimal(str(x.paid_amount or 0))!=Decimal(str(allocated.get(x.id) or 0)),'_url':f'/srm/invoices/{x.id}'} for x in items]
        return result(db,user,f,report,rows,total,page,size,['invoice','currency','invoiced','invoice_paid','confirmed_allocations','balance','allocation_difference','balance_difference','review_required'],reconciliation_basis='Differences require review: credits, write-offs or other authorized adjustments can explain them. No financial records are changed.')
    raise HTTPException(404,'Report not found')


def run(db,user,report,filters,page=1,size=50):
    if report not in REPORTS:raise HTTPException(404,'Report not found')
    f=resolved(db,user,filters)
    if report=='overview':return overview(db,user,f)
    if report in {'invoices','outstanding','invoice_aging'}:return invoice_details(db,user,f,report,page,size)
    if report in {'sales','pipeline'}:return sales_details(db,user,f,page,size,report)
    if report=='payments':return payment_details(db,user,f,page,size)
    if report=='returns':return return_details(db,user,f,page,size)
    if report=='customers':return customer_details(db,user,f,page,size)
    if report=='products':return product_details(db,user,f,page,size)
    if report in {'stock','reconciliation'}:return stock_details(db,user,f,page,size,report=='reconciliation')
    return other_details(db,user,f,report,page,size)
