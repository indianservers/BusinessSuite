"""Atomic original-lot quarantine and native posted credit/refund command."""
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
import json
from sqlalchemy import select,inspect,func
from fastapi import HTTPException

from .return_models import MODELS,PharmaReturn,PharmaReturnLine,PharmaReturnLot,_complete_return
from .return_schemas import PharmaReturnInput
from .return_plan import SoldLot,plan_return
from .receipts import authority as pharma_authority
from app.apps.srm.service_checkout_models import POSServiceCheckout,POSCheckoutLine
from app.apps.srm.service_checkout import _scope,_source_scope,_validate_group_sources
from app.apps.srm.models import SRMInvoice,SRMPOSReturn,SRMPOSReturnLine,SRMPOSCashMovement


def fail(message,status=409):raise HTTPException(status,message)


def refund_native_authority(db,actor,*,write=True):
    """Fixed outgoing original-lot purpose; never grants incoming collection."""
    from app.apps.srm.service_checkout import _authority
    from app.apps.srm.services.commercial import require
    from app.business_packs.native_checkout_authority import capture
    company,branch,scope=_authority(db,actor,payments=False,write=write)
    if scope is None or scope.pack_key!='pharma' or 'pharma.returns.approve' not in scope.capabilities:
        fail('Assigned Pharma role cannot approve original-lot refunds',403)
    require(actor,'srm_collection_create','srm_admin')
    epoch=capture(db,actor,scope,order=True,billing=False,payments=True,write=write)
    return company,branch,scope,epoch


def assert_refund_epoch(db,actor,scope,epoch):
    """Fresh revocation facts for an already verified, writer-bound lease."""
    from app.business_packs.common_core import _native_authority
    from app.business_packs.boundary import _current
    from app.access.entitlements import enforce
    if (not isinstance(epoch,str) or not epoch or scope.pack_key!='pharma'
            or 'pharma.returns.approve' not in scope.capabilities
            or db.info.get('business_pack_scope') is not scope or scope.user_id!=actor.id):
        fail('Original-lot refund lease authority is unavailable',403)
    _current(scope,db.connection())
    if _native_authority(db,actor,scope.company_id)!=epoch:
        fail('Medicine refund authority changed during its native command',403)
    enforce(db,scope.company_id,'srm');enforce(db,scope.company_id,'fam')


def authority(db,actor,*,write=True):
    from app.apps.srm.service_checkout import _authority
    from app.apps.srm.services.commercial import require
    from app.access.service import check_background_access
    from app.apps.fam.access import FAM_SRM_POSTING_MANAGE_PERMISSIONS
    from app.business_packs.catalog_management import _module_grant
    from app.business_packs.common_core import _native_authority
    company,branch,scope=pharma_authority(db,actor,'returns.approve',write=write)
    native_company,native_branch,native_scope,epoch=refund_native_authority(db,actor,write=write)
    if (native_company,native_branch,native_scope)!=(company,branch,scope):fail('Medicine refund scope changed',403)
    require(actor,*FAM_SRM_POSTING_MANAGE_PERMISSIONS)
    check_background_access(db,actor,'fam','create' if write else 'view')
    if write:check_background_access(db,actor,'fam','approve')
    grant=_module_grant(db,actor,scope,'fam')
    if not actor.is_superuser and (not grant.get('enabled') or not set(grant.get('permissions',())).intersection(FAM_SRM_POSTING_MANAGE_PERMISSIONS)
            or not ({'create','approve'} if write else {'view'})<=set(grant.get('actions',()))):
        fail('Fresh native Accounting posting permissions and approval are required',403)
    inspector=inspect(db.connection())
    for model in MODELS:
        if not inspector.has_table(model.__tablename__) or not set(model.__table__.c.keys())<={c['name'] for c in inspector.get_columns(model.__tablename__)}:
            fail('Install original-lot return schema115 before issuing a medicine refund',503)
    return company,branch,scope,epoch


def query(db,model,company,branch,scope):
    return db.query(model).filter(model.organization_id==company,model.branch_id==branch,model.pack_context_id==scope.context_id)


def quantity_text(value):
    return format(Decimal(value).quantize(Decimal('0.001')),'f')


def money_text(value):
    return format(Decimal(value).quantize(Decimal('0.01')),'f')


def result(row,db,scope):
    _source_scope(db,scope,row.organization_id,row.branch_id,PharmaReturn,row.id)
    if row.state!='committed':fail('Medicine return has not completed')
    checkout=db.get(POSServiceCheckout,row.checkout_id)
    if checkout is None:fail('Original medicine sale is unavailable')
    _validate_group_sources(checkout,db,scope)
    try:_complete_return(db.connection(),row)
    except ValueError:fail('Original medicine return requires native source reconciliation')
    _source_scope(db,scope,row.organization_id,row.branch_id,SRMPOSReturn,row.native_return_id)
    if row.cash_movement_id:_source_scope(db,scope,row.organization_id,row.branch_id,SRMPOSCashMovement,row.cash_movement_id)
    lines=[]
    for line in db.query(PharmaReturnLine).filter_by(return_id=row.id).order_by(PharmaReturnLine.id):
        _source_scope(db,scope,row.organization_id,row.branch_id,PharmaReturnLine,line.id)
        _source_scope(db,scope,row.organization_id,row.branch_id,SRMPOSReturnLine,line.native_return_line_id)
        lots=[]
        for lot in db.query(PharmaReturnLot).filter_by(return_line_id=line.id).order_by(PharmaReturnLot.id):
            _source_scope(db,scope,row.organization_id,row.branch_id,PharmaReturnLot,lot.id)
            from app.apps.srm.models import SRMInventoryMovement
            _source_scope(db,scope,row.organization_id,row.branch_id,SRMInventoryMovement,lot.stock_movement_id)
            lots.append({'allocation_id':lot.allocation_id,'original_batch_id':lot.original_batch_id,
                'original_batch_number':lot.original_batch_number,'quantity':quantity_text(lot.quantity),
                'quarantine_batch_id':lot.quarantine_batch_id,'disposition':'quarantine'})
        lines.append({'checkout_line_id':line.checkout_line_id,'quantity':quantity_text(line.quantity),
            'net_amount':money_text(line.net_amount),'tax_amount':money_text(line.tax_amount),'gross_amount':money_text(line.gross_amount),'lots':lots})
    from app.apps.fam.models import FAMVoucher
    table=FAMVoucher.__table__
    vouchers={key:dict(db.connection().execute(select(table.c.id,table.c.voucher_number,table.c.status).where(table.c.id==ident)).mappings().one())
        for key,ident in (('credit_note',row.credit_voucher_id),('refund',row.refund_voucher_id))}
    return {'id':row.id,'state':row.state,'revision':row.revision,'checkout_id':row.checkout_id,
        'native_return_id':row.native_return_id,'refund_amount':money_text(row.refund_amount),'currency':row.currency,
        'refund_method':row.refund_method,'cash_movement_id':row.cash_movement_id,'accounting':vouchers,'lines':lines}


def state(ident,db,actor):
    company,branch,scope,_=authority(db,actor,write=False)
    row=query(db,PharmaReturn,company,branch,scope).filter_by(id=ident).one_or_none()
    if row is None:fail('Medicine return not found',404)
    return result(row,db,scope)


def recovery(key,db,actor):
    company,branch,scope,_=authority(db,actor,write=False)
    row=query(db,PharmaReturn,company,branch,scope).filter_by(request_key=str(key),created_by=actor.id).one_or_none()
    if row is None:fail('Medicine return request not found',404)
    return {'state':row.state,'result':result(row,db,scope)}


def create(data,db,actor,request,*,commit=True):
    try:return _create(data,db,actor,request,commit=commit)
    except BaseException:
        if commit:db.rollback()
        else:db.expire_all()
        raise


def _create(data,db,actor,request,*,commit=True):
    from .models import PharmaBatchAllocation
    from app.apps.srm.services.commercial import lock_tenant,money
    from app.apps.srm.service_checkout import _collection_register
    from app.apps.srm.service_checkout_register import group_register_cash
    from app.business_packs.retail.valuation import allocate_return
    from app.business_packs.retail.posting_plan import build
    from app.business_packs.retail.accounting import post
    from .return_stock import quarantine_operation,create_batch,receive
    from app.apps.srm.services.commercial_numbering import reserve_number
    data=PharmaReturnInput.model_validate(data.model_dump())
    company,branch,scope,epoch=authority(db,actor)
    lock_tenant(db,actor)
    if authority(db,actor)!=(company,branch,scope,epoch):fail('Medicine refund authority changed while waiting',403)
    digest=sha256(json.dumps(data.model_dump(mode='json'),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    previous=query(db,PharmaReturn,company,branch,scope).filter_by(request_key=str(data.request_key)).one_or_none()
    if previous:
        if previous.created_by!=actor.id or previous.request_sha256!=digest:fail('Return request key was used for another command')
        return result(previous,db,scope)
    with db.begin_nested():
        checkout=_scope(db.query(POSServiceCheckout),POSServiceCheckout,company,branch,scope).filter_by(id=data.checkout_id).with_for_update().one_or_none()
        if checkout is None:fail('Original Pharma checkout not found',404)
        if checkout.state!='committed' or checkout.revision!=data.expected_checkout_revision:fail('Original checkout changed; review the medicine sale')
        _validate_group_sources(checkout,db,scope)
        invoice=db.get(SRMInvoice,checkout.invoice_id)
        if invoice is None or invoice.status in ('draft','pending_approval','cancelled') or invoice.balance_amount!=0 or invoice.total_amount!=invoice.paid_amount or invoice.total_amount<=0:
            fail('This medicine refund requires a fully paid issued original sale')
        register=_collection_register(db,actor,company,branch,scope,data.refund.session_id,cash=data.refund.method=='cash',currency=checkout.currency)
        if register is None:fail('An open authorized refund register is required')
        source_lines={line.sales_order_line_id:line for line in db.query(POSCheckoutLine).filter_by(checkout_id=checkout.id,line_kind='product')}
        from .fefo import sale_allocations
        sale_allocations(db,scope,checkout,list(source_lines.values()))
        allocations=query(db,PharmaBatchAllocation,company,branch,scope).filter(PharmaBatchAllocation.sales_order_line_id.in_(source_lines)).order_by(PharmaBatchAllocation.id).with_for_update().all()
        prior_lots=db.query(PharmaReturnLot).join(PharmaReturn,PharmaReturn.id==PharmaReturnLot.return_id).filter(PharmaReturn.checkout_id==checkout.id,PharmaReturn.state=='committed').all()
        source=tuple(SoldLot(row.id,row.batch_id,Decimal(row.quantity),sum((p.quantity for p in prior_lots if p.allocation_id==row.id),Decimal(0))) for row in allocations)
        try:planned=plan_return(source,{line.allocation_id:line.quantity for line in data.lots})
        except ValueError as error:fail(str(error))
        by_id={row.id:row for row in allocations};grouped={}
        for item in planned:
            allocation=by_id[item.allocation_id];_source_scope(db,scope,company,branch,PharmaBatchAllocation,allocation.id)
            line=source_lines[allocation.sales_order_line_id]
            grouped.setdefault(line.id,[line,[]])[1].append((allocation,item.quantity))
        selected=[]
        for line,items in grouped.values():
            prior=db.query(PharmaReturnLine).join(PharmaReturn,PharmaReturn.id==PharmaReturnLine.return_id).filter(PharmaReturn.checkout_id==checkout.id,PharmaReturn.state=='committed',PharmaReturnLine.checkout_line_id==line.id).all()
            try:charge=allocate_return(sold_quantity=line.quantity,issued_gross=line.line_total,issued_tax=line.tax_amount,
                prior_quantity=sum((p.quantity for p in prior),Decimal(0)),prior_gross=sum((p.gross_amount for p in prior),Decimal(0)),
                prior_tax=sum((p.tax_amount for p in prior),Decimal(0)),requested_quantity=sum((q for _,q in items),Decimal(0)))
            except ValueError as error:fail(str(error))
            selected.append((line,items,charge))
        total=sum((charge.gross for _,_,charge in selected),Decimal(0))
        if total<=0:fail('The selected original lots have no refundable issued charge')
        if data.expected_refund_amount is not None and data.expected_refund_amount!=total:fail('Original remaining refund changed; review the lots before continuing')
        if data.refund.method=='cash':
            cash=group_register_cash(db,register,[])
            if cash['unattributed_cash_count']:fail('Reconcile the actual register before a cash refund')
            def cash_total(kind):return Decimal(db.query(func.coalesce(func.sum(SRMPOSCashMovement.amount),0)).filter_by(organization_id=company,session_id=register.id,movement_type=kind).scalar())
            capacity=Decimal(register.opening_cash or 0)+cash['cash_received']+cash_total('cash_in')-cash_total('cash_out')
            if total>capacity:fail('The actual refund register has insufficient cash')
        root=PharmaReturn(organization_id=company,branch_id=branch,pack_context_id=scope.context_id,
            checkout_id=checkout.id,request_key=str(data.request_key),request_sha256=digest,created_by=actor.id,
            sales_order_id=checkout.sales_order_id,invoice_id=checkout.invoice_id,collection_session_id=register.id,
            refund_method=data.refund.method,payment_reference=data.refund.reference,currency=checkout.currency,reason=data.reason,
            net_amount=sum((c.net for _,_,c in selected),Decimal(0)),tax_amount=sum((c.tax for _,_,c in selected),Decimal(0)),refund_amount=total,state='draft')
        db.add(root);db.flush();plan=build(db,actor,scope,root,checkout,native_epoch=epoch)
        native=SRMPOSReturn(organization_id=company,return_number=reserve_number(db,SRMPOSReturn,'RET','return_number',company,actor=actor),
            sales_order_id=checkout.sales_order_id,session_id=register.id,customer_id=checkout.customer_id,status='completed',refund_method=data.refund.method,
            refund_status='pending',subtotal=root.net_amount,tax_amount=root.tax_amount,refund_amount=total,reason=data.reason,created_by=actor.id)
        db.add(native);db.flush();root.native_return_id=native.id;db.flush()
        with quarantine_operation(db,actor,scope,root,native_epoch=epoch) as quarantine:
            for line,items,charge in selected:
                warehouses={allocation.warehouse_id for allocation,_ in items}
                if len(warehouses)!=1:fail('Original medicine line warehouse requires reconciliation')
                native_line=SRMPOSReturnLine(return_id=native.id,sales_order_line_id=line.sales_order_line_id,product_id=line.product_id,
                    warehouse_id=next(iter(warehouses)),description='Original medicine lots to quarantine',quantity=charge.quantity,
                    unit_price=money(charge.net/charge.quantity),tax_amount=charge.tax,line_total=charge.gross,condition='quarantine',restock=False)
                db.add(native_line);db.flush()
                mapped=PharmaReturnLine(return_id=root.id,checkout_id=checkout.id,organization_id=company,branch_id=branch,pack_context_id=scope.context_id,
                    checkout_line_id=line.id,product_id=line.product_id,sales_order_line_id=line.sales_order_line_id,invoice_line_id=line.invoice_line_id,
                    native_return_line_id=native_line.id,quantity=charge.quantity,net_amount=charge.net,tax_amount=charge.tax,gross_amount=charge.gross)
                db.add(mapped);db.flush()
                for allocation,quantity in items:
                    batch_id=create_batch(quarantine,mapped,allocation,quantity)
                    lot=PharmaReturnLot(return_line_id=mapped.id,return_id=root.id,checkout_id=checkout.id,checkout_line_id=line.id,
                        organization_id=company,branch_id=branch,pack_context_id=scope.context_id,product_id=line.product_id,
                        sales_order_line_id=line.sales_order_line_id,warehouse_id=allocation.warehouse_id,allocation_id=allocation.id,
                        original_batch_id=allocation.batch_id,quarantine_batch_id=batch_id,original_batch_number=allocation.batch_number,
                        original_expiry_date=allocation.expiry_date,quantity=quantity,disposition='quarantine')
                    db.add(lot);db.flush();receive(quarantine,lot)
        root.credit_voucher_id,root.refund_voucher_id=post(plan,db,actor,request,scope)
        if data.refund.method=='cash':
            movement=SRMPOSCashMovement(organization_id=company,session_id=register.id,movement_type='cash_out',amount=total,
                reason='Original medicine refund '+native.return_number,created_by=actor.id)
            db.add(movement);db.flush();root.cash_movement_id=movement.id
        native.refund_status='refunded';db.flush()
        root.state='committed';root.committed_at=datetime.now(timezone.utc);db.flush()
        output=result(root,db,scope)
    if commit:db.commit()
    return output
