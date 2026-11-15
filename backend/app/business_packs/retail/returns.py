"""Atomic original-sale return, original-warehouse stock and native CN/PV refund."""
from decimal import Decimal
from datetime import datetime,timezone
from hashlib import sha256
import json
from sqlalchemy import inspect,select,func
from app.apps.srm.models import SRMInvoice,SRMPOSReturn,SRMPOSReturnLine
from app.apps.srm.service_checkout_models import POSServiceCheckout,POSCheckoutLine
from app.apps.srm.service_checkout import (_authority,_scope,_source_scope,_validate_group_sources,
    _collection_register)
from .schemas import ReturnInput
from .models import RetailReturn,RetailReturnLine,RetailSaleStockSource,MODELS
from .valuation import allocate_return
from .accounting import authority,fail


def _ready(db):
    inspector=inspect(db.connection())
    if not all(inspector.has_table(model.__tablename__) and set(model.__table__.c.keys())<={column['name'] for column in inspector.get_columns(model.__tablename__)} for model in MODELS):
        fail('Install the Retail return extension before using returns',503)


def _selected(db,actor,*,write=True):
    company,branch,scope=_authority(db,actor,payments=True,write=write)
    if scope is None or scope.pack_key!='retail':fail('Select an authorized Retail context')
    bound=db.info.get('business_pack_scope')
    if bound is None or bound!=scope:fail('Retail return requires its verified request context')
    scope=bound
    authority(db,actor,scope,write=write)
    _ready(db)
    return company,branch,scope


def _query(db,model,company,branch,scope):
    return db.query(model).filter(model.organization_id==company,model.branch_id==branch,model.pack_context_id==scope.context_id)


def state(ident,db,actor):
    company,branch,scope=_selected(db,actor,write=False)
    row=_query(db,RetailReturn,company,branch,scope).filter(RetailReturn.id==ident).one_or_none()
    if row is None:fail('Retail return not found',404)
    _source_scope(db,scope,company,branch,RetailReturn,row.id)
    return _result(row,db,scope)


def recovery(request_key,db,actor):
    company,branch,scope=_selected(db,actor,write=False)
    row=_query(db,RetailReturn,company,branch,scope).filter_by(request_key=str(request_key),created_by=actor.id).one_or_none()
    if row is None:fail('Completed refund request not found',404)
    if row.state!='committed':return {'state':'pending','result':None}
    return {'state':'committed','result':_result(row,db,scope)}


def sale_options(checkout_id,db,actor):
    company,branch,scope=_selected(db,actor,write=False)
    checkout=_scope(db.query(POSServiceCheckout),POSServiceCheckout,company,branch,scope).filter_by(id=checkout_id).one_or_none()
    if checkout is None:fail('Original Retail checkout not found',404)
    _validate_group_sources(checkout,db,scope)
    invoice=db.get(SRMInvoice,checkout.invoice_id)
    if invoice is None:fail('Original invoice is unavailable',409)
    from app.apps.srm.models import SRMSalesOrderLine
    result=[]
    for line in db.query(POSCheckoutLine).filter_by(checkout_id=checkout.id).order_by(POSCheckoutLine.id):
        if line.line_kind!='product':continue
        proof=db.query(RetailSaleStockSource).filter_by(sales_order_line_id=line.sales_order_line_id,
            organization_id=company,branch_id=branch,pack_context_id=scope.context_id).one_or_none()
        if proof is None:continue
        original=db.get(SRMSalesOrderLine,line.sales_order_line_id)
        if original is None:fail('Original sale line is unavailable',409)
        prior=db.query(RetailReturnLine).join(RetailReturn,RetailReturn.id==RetailReturnLine.return_id).filter(
            RetailReturn.checkout_id==checkout.id,RetailReturn.state=='committed',RetailReturnLine.checkout_line_id==line.id).all()
        quantity=line.quantity-sum((item.quantity for item in prior),Decimal(0))
        if quantity>0:result.append({'id':line.id,'description':original.description,
            'remaining_quantity':format(Decimal(quantity).normalize(),'f'),'issued_total':format(Decimal(line.line_total),'.2f')})
    from app.apps.fam.models import FAMSRMMapping,FAMVoucher
    from app.apps.srm.service_checkout_models import POSCheckoutPayment
    table=FAMSRMMapping.__table__;voucher=FAMVoucher.__table__
    def posted(kind,ident):
        return db.connection().execute(select(table.c.id).join(voucher,voucher.c.id==table.c.fam_record_id).where(
            table.c.company_id==company,table.c.srm_record_type==kind,table.c.srm_record_id==ident,
            table.c.fam_record_type=='voucher',table.c.mapping_status=='active',voucher.c.company_id==company,
            voucher.c.source_module=='srm',voucher.c.source_record_type==kind,voucher.c.source_record_id==str(ident),voucher.c.status=='posted')).first() is not None
    accounting_ready=posted('invoice',invoice.id) and all(posted('receipt',item.receipt_id) for item in db.query(POSCheckoutPayment).filter_by(checkout_id=checkout.id))
    fully_paid=invoice.status not in ('draft','pending_approval','cancelled') and Decimal(invoice.balance_amount)==0 and Decimal(invoice.paid_amount)==Decimal(invoice.total_amount)>0
    reason=None if result and fully_paid and accounting_ready else 'Post the original invoice and collected receipts in Accounting before refunding.' if not accounting_ready else 'Returns currently require a fully paid sale with remaining physical items.'
    return {'checkout_id':checkout.id,'revision':checkout.revision,'invoice_number':invoice.invoice_number,
        'currency':checkout.currency,'ready':bool(result and fully_paid and accounting_ready),'unavailable_reason':reason,
        'lines':result,'methods':['cash','card'],'quantity_decimal_places':2}


def _result(row,db,scope):
    checkout=db.get(POSServiceCheckout,row.checkout_id)
    if checkout is None or (checkout.organization_id,checkout.branch_id,checkout.pack_context_id)!=(row.organization_id,row.branch_id,row.pack_context_id):fail('Return original sale is unavailable',409)
    if (row.sales_order_id,row.invoice_id)!=(checkout.sales_order_id,checkout.invoice_id):fail('Return original financial source differs',409)
    _validate_group_sources(checkout,db,scope)
    native=db.get(SRMPOSReturn,row.native_return_id)
    if native is None or (native.organization_id,native.sales_order_id,native.customer_id,native.session_id,native.refund_method,
            Decimal(native.refund_amount),native.refund_status)!=(row.organization_id,row.sales_order_id,checkout.customer_id,
            row.collection_session_id,row.refund_method,Decimal(row.refund_amount),'refunded'):fail('Native return differs from its issued refund',409)
    _source_scope(db,scope,row.organization_id,row.branch_id,SRMPOSReturn,native.id)
    if row.refund_method=='cash':
        from app.apps.srm.models import SRMPOSCashMovement
        cash=db.get(SRMPOSCashMovement,row.cash_movement_id)
        if cash is None or (cash.organization_id,cash.session_id,cash.movement_type,Decimal(cash.amount),cash.created_by)!=(
                row.organization_id,row.collection_session_id,'cash_out',Decimal(row.refund_amount),row.created_by):fail('Native cash refund differs from its issued return',409)
        _source_scope(db,scope,row.organization_id,row.branch_id,SRMPOSCashMovement,cash.id)
    # This is an exact source projection, never a company voucher list.
    from app.apps.fam.models import FAMVoucher,FAMVoucherType
    vouchers={}
    for key,ident in (('credit_note',row.credit_voucher_id),('refund',row.refund_voucher_id)):
        table=FAMVoucher.__table__
        kind=FAMVoucherType.__table__
        record=db.connection().execute(select(table.c.id,table.c.voucher_number,table.c.status,table.c.total_debit,table.c.total_credit).join(kind,kind.c.id==table.c.voucher_type_id).where(
            table.c.id==ident,table.c.company_id==row.organization_id,table.c.source_module=='srm',
            table.c.source_record_type=='retail_return',table.c.source_record_id==str(row.id),table.c.status=='posted',
            kind.c.company_id==row.organization_id,kind.c.voucher_type_code==('CN' if key=='credit_note' else 'PV'))).mappings().first()
        if record is None or Decimal(record['total_debit'])!=row.refund_amount or Decimal(record['total_credit'])!=row.refund_amount:fail('Native refund accounting needs reconciliation',409)
        vouchers[key]={'id':record['id'],'number':record['voucher_number'],'status':record['status']}
    lines=[]
    for line in db.query(RetailReturnLine).filter_by(return_id=row.id):
        _source_scope(db,scope,row.organization_id,row.branch_id,RetailReturnLine,line.id)
        original=db.get(POSCheckoutLine,line.checkout_line_id)
        returned=db.get(SRMPOSReturnLine,line.native_return_line_id)
        if original is None or returned is None or original.checkout_id!=checkout.id or (line.sales_order_line_id,line.invoice_line_id,line.product_id)!=(original.sales_order_line_id,original.invoice_line_id,original.product_id):fail('Return line original source differs',409)
        _source_scope(db,scope,row.organization_id,row.branch_id,SRMPOSReturnLine,returned.id)
        if (returned.return_id,returned.sales_order_line_id,returned.product_id,returned.quantity,returned.tax_amount,returned.line_total,returned.restock)!=(
                native.id,line.sales_order_line_id,line.product_id,line.quantity,line.tax_amount,line.gross_amount,line.restock):fail('Native return line charge differs',409)
        if line.stock_movement_id is not None:
            from app.apps.srm.models import SRMInventoryMovement
            movement=db.get(SRMInventoryMovement,line.stock_movement_id)
            if movement is None:fail('Return stock restoration is unavailable',409)
            _source_scope(db,scope,row.organization_id,row.branch_id,SRMInventoryMovement,movement.id)
            if (movement.product_id,movement.warehouse_id,movement.quantity_in,movement.quantity_out,movement.movement_type)!=(
                    line.product_id,returned.warehouse_id,line.quantity,0,'pos_return'):fail('Return stock movement differs from its issued source',409)
        lines.append({'checkout_line_id':line.checkout_line_id,'quantity':format(Decimal(line.quantity).normalize(),'f'),
            'net':format(Decimal(line.net_amount),'.2f'),'tax':format(Decimal(line.tax_amount),'.2f'),'total':format(Decimal(line.gross_amount),'.2f'),
            'restocked':line.restock,'stock_movement_id':line.stock_movement_id})
    return {'id':row.id,'revision':row.revision,'state':row.state,'checkout_id':row.checkout_id,
        'original_invoice_id':row.invoice_id,'native_return_id':row.native_return_id,
        'return_number':native.return_number,'currency':row.currency,'net':format(Decimal(row.net_amount),'.2f'),
        'tax':format(Decimal(row.tax_amount),'.2f'),'refund_amount':format(Decimal(row.refund_amount),'.2f'),'refund_method':row.refund_method,
        'collection_session_id':row.collection_session_id,'accounting':vouchers,'lines':lines}


def create(data,db,actor,request,*,commit=True):
    try:
        return _create(data,db,actor,request,commit=commit)
    except BaseException:
        # Fixed stock commands update a canonical shared cache through Core;
        # savepoint rollback must also invalidate its committed ORM projection.
        if commit:db.rollback()
        else:db.expire_all()
        raise


def _create(data,db,actor,request,*,commit=True):
    data=ReturnInput.model_validate(data.model_dump())
    company,branch,scope=_selected(db,actor)
    from app.apps.srm.services.commercial import lock_tenant
    lock_tenant(db,actor)
    if _selected(db,actor)!=(company,branch,scope):fail('Retail refund authorization changed')
    fingerprint=sha256(json.dumps(data.model_dump(mode='json'),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    previous=_query(db,RetailReturn,company,branch,scope).filter_by(request_key=str(data.request_key)).one_or_none()
    if previous is not None:
        if previous.created_by!=actor.id or previous.request_sha256!=fingerprint:fail('Return request key was already used for another command',409)
        if previous.state!='committed':fail('Original return has not completed',409)
        return _result(previous,db,scope)
    with db.begin_nested():
        checkout=_scope(db.query(POSServiceCheckout),POSServiceCheckout,company,branch,scope).filter_by(id=data.checkout_id).with_for_update().one_or_none()
        if checkout is None:fail('Original Retail checkout not found',404)
        _source_scope(db,scope,company,branch,POSServiceCheckout,checkout.id)
        if checkout.state!='committed' or checkout.revision!=data.expected_checkout_revision:fail('Original checkout changed; review the sale before returning',409)
        _validate_group_sources(checkout,db,scope)
        invoice=db.get(SRMInvoice,checkout.invoice_id)
        if invoice is None or invoice.status in ('draft','pending_approval','cancelled') or Decimal(invoice.total_amount)<=0 or Decimal(invoice.balance_amount)!=0 or Decimal(invoice.paid_amount)!=Decimal(invoice.total_amount):
            fail('The first Retail return workflow requires a fully paid issued sale; credit returns are not yet supported',409)
        register=_collection_register(db,actor,company,branch,scope,data.refund.session_id,cash=data.refund.method=='cash',currency=checkout.currency)
        if register is None:fail('An open authorized refund register is required',409)
        selected=[]
        from .stock_returns import original
        for command in data.lines:
            line=db.query(POSCheckoutLine).filter_by(id=command.checkout_line_id,checkout_id=checkout.id).one_or_none()
            if line is None:fail('Return line is outside the original sale',404)
            _source_scope(db,scope,company,branch,POSCheckoutLine,line.id)
            if line.line_kind!='product':fail('Service and appointment returns require their separate cancellation policy and are not supported here',409)
            if command.quantity!=command.quantity.quantize(Decimal('.01')):fail('Native return quantity supports at most two decimal places',422)
            stock=original(db,scope,line)
            prior=db.query(RetailReturnLine).join(RetailReturn,RetailReturn.id==RetailReturnLine.return_id).filter(
                RetailReturn.checkout_id==checkout.id,RetailReturn.pack_context_id==scope.context_id,
                RetailReturn.state=='committed',RetailReturnLine.checkout_line_id==line.id).all()
            try:
                charge=allocate_return(sold_quantity=line.quantity,issued_gross=line.line_total,issued_tax=line.tax_amount,
                    prior_quantity=sum((p.quantity for p in prior),Decimal(0)),prior_gross=sum((p.gross_amount for p in prior),Decimal(0)),
                    prior_tax=sum((p.tax_amount for p in prior),Decimal(0)),requested_quantity=command.quantity)
            except ValueError as error:fail(str(error),409)
            selected.append((command,line,stock,charge))
        total=sum((item[3].gross for item in selected),Decimal(0))
        if total<=0:fail('A positive original charge is required for a refund',409)
        if data.refund.method=='cash':
            from app.apps.srm.models import SRMPOSCashMovement
            from app.apps.srm.service_checkout_register import group_register_cash
            received=group_register_cash(db,register,[])
            if received['unattributed_cash_count']:fail('Reconcile the actual register collections before refunding',409)
            def cash_total(kind):
                return Decimal(db.query(func.coalesce(func.sum(SRMPOSCashMovement.amount),0)).filter(
                    SRMPOSCashMovement.organization_id==company,SRMPOSCashMovement.session_id==register.id,
                    SRMPOSCashMovement.movement_type==kind).scalar())
            capacity=Decimal(register.opening_cash or 0)+received['cash_received']+cash_total('cash_in')-cash_total('cash_out')
            if capacity<total:
                fail('Fund the actual refund register before paying this cash refund',409)
        root=RetailReturn(organization_id=company,branch_id=branch,pack_context_id=scope.context_id,checkout_id=checkout.id,
            request_key=str(data.request_key),request_sha256=fingerprint,created_by=actor.id,sales_order_id=checkout.sales_order_id,
            invoice_id=checkout.invoice_id,collection_session_id=register.id,refund_method=data.refund.method,
            payment_reference=data.refund.reference,currency=checkout.currency,reason=data.reason.strip(),
            net_amount=sum((item[3].net for item in selected),Decimal(0)),tax_amount=sum((item[3].tax for item in selected),Decimal(0)),refund_amount=total)
        db.add(root);db.flush()
        from .posting_plan import build
        plan=build(db,actor,scope,root,checkout)
        from app.apps.srm.services.commercial_numbering import reserve_number
        native=SRMPOSReturn(organization_id=company,
            return_number=reserve_number(db,SRMPOSReturn,'RET','return_number',company,actor=actor),
            sales_order_id=checkout.sales_order_id,session_id=register.id,customer_id=checkout.customer_id,
            status='completed',refund_method=data.refund.method,refund_status='pending',subtotal=root.net_amount,
            tax_amount=root.tax_amount,refund_amount=total,reason=root.reason,created_by=actor.id)
        db.add(native);db.flush()
        root.native_return_id=native.id;db.flush()
        from .stock_returns import restore
        for command,line,stock,charge in selected:
            native_line=SRMPOSReturnLine(return_id=native.id,sales_order_line_id=line.sales_order_line_id,
                product_id=line.product_id,warehouse_id=stock.warehouse_id,description='Original-sale return',
                quantity=charge.quantity,unit_price=(charge.net/charge.quantity).quantize(Decimal('.01')),
                tax_amount=charge.tax,line_total=charge.gross,condition='sellable' if command.restock else 'damaged',restock=command.restock)
            db.add(native_line);db.flush()
            movement=restore(db,actor,scope,native_line,stock,checkout.currency) if command.restock else None
            db.add(RetailReturnLine(return_id=root.id,checkout_id=checkout.id,organization_id=company,branch_id=branch,
                pack_context_id=scope.context_id,checkout_line_id=line.id,product_id=line.product_id,
                sales_order_line_id=line.sales_order_line_id,invoice_line_id=line.invoice_line_id,
                native_return_line_id=native_line.id,stock_movement_id=movement.id if movement else None,
                quantity=charge.quantity,net_amount=charge.net,tax_amount=charge.tax,gross_amount=charge.gross,restock=command.restock))
            db.flush()
        from .accounting import post
        root.credit_voucher_id,root.refund_voucher_id=post(plan,db,actor,request,scope)
        if data.refund.method=='cash':
            from app.apps.srm.models import SRMPOSCashMovement
            cash=SRMPOSCashMovement(organization_id=company,session_id=register.id,movement_type='cash_out',
                amount=total,reason='Retail refund '+native.return_number,created_by=actor.id)
            db.add(cash);db.flush();root.cash_movement_id=cash.id
        native.refund_status='refunded'
        root.committed_at=datetime.now(timezone.utc);root.state='committed'
        db.flush()
        result=_result(root,db,scope)
    if commit:db.commit()
    return result
