"""Immutable original-sale medicine returns; native stock and books stay canonical."""
from sqlalchemy import (Column,Integer,String,Text,Numeric,Date,DateTime,ForeignKey,
    ForeignKeyConstraint,UniqueConstraint,CheckConstraint,event,inspect,func)
from app.db.base_class import Base


class PharmaReturn(Base):
    __tablename__ = 'business_pharma_returns'
    __table_args__ = (
        ForeignKeyConstraint(['checkout_id','organization_id','branch_id','pack_context_id'],
            ['srm_pos_service_checkouts.id','srm_pos_service_checkouts.organization_id',
             'srm_pos_service_checkouts.branch_id','srm_pos_service_checkouts.scope_context_key'],
            ondelete='RESTRICT', name='fk_pharma_return_checkout_scope'),
        UniqueConstraint('organization_id','branch_id','pack_context_id','request_key', name='uq_pharma_return_request'),
        UniqueConstraint('id','checkout_id','organization_id','branch_id','pack_context_id',name='uq_pharma_return_scope'),
        CheckConstraint('pack_context_id > 0 AND revision > 0',name='ck_pharma_return_scope'),
        CheckConstraint("state IN ('draft','committed')",name='ck_pharma_return_state'),
        CheckConstraint('length(request_key)=36 AND length(request_sha256)=64',name='ck_pharma_return_request'),
        CheckConstraint("refund_method IN ('cash','card') AND length(currency)=3",name='ck_pharma_return_payment'),
        CheckConstraint('net_amount >= 0 AND tax_amount >= 0 AND refund_amount > 0 AND round(net_amount+tax_amount,2)=refund_amount',name='ck_pharma_return_money'),
        CheckConstraint("state != 'committed' OR (native_return_id IS NOT NULL AND credit_voucher_id IS NOT NULL AND refund_voucher_id IS NOT NULL AND committed_at IS NOT NULL)",name='ck_pharma_return_committed'),
        CheckConstraint("refund_method != 'cash' OR state != 'committed' OR cash_movement_id IS NOT NULL",name='ck_pharma_return_cash'),
    )
    id = Column(Integer,primary_key=True)
    organization_id = Column(Integer,nullable=False,index=True)
    branch_id = Column(Integer,ForeignKey('branches.id',ondelete='RESTRICT'),nullable=False)
    pack_context_id = Column(Integer,ForeignKey('business_pack_contexts.id',ondelete='RESTRICT'),nullable=False)
    checkout_id = Column(Integer,nullable=False)
    request_key = Column(String(36),nullable=False)
    request_sha256 = Column(String(64),nullable=False)
    created_by = Column(Integer,ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    sales_order_id = Column(Integer,ForeignKey('srm_sales_orders.id',ondelete='RESTRICT'),nullable=False)
    invoice_id = Column(Integer,ForeignKey('srm_invoices.id',ondelete='RESTRICT'),nullable=False)
    collection_session_id = Column(Integer,ForeignKey('srm_pos_sessions.id',ondelete='RESTRICT'),nullable=False)
    native_return_id = Column(Integer,ForeignKey('srm_pos_returns.id',ondelete='RESTRICT'),unique=True)
    credit_voucher_id = Column(Integer,ForeignKey('fam_vouchers.id',ondelete='RESTRICT'),unique=True)
    refund_voucher_id = Column(Integer,ForeignKey('fam_vouchers.id',ondelete='RESTRICT'),unique=True)
    cash_movement_id = Column(Integer,ForeignKey('srm_pos_cash_movements.id',ondelete='RESTRICT'),unique=True)
    refund_method = Column(String(12),nullable=False)
    payment_reference = Column(String(200),nullable=False,default='')
    currency = Column(String(3),nullable=False)
    reason = Column(Text,nullable=False)
    net_amount = Column(Numeric(14,2),nullable=False)
    tax_amount = Column(Numeric(14,2),nullable=False)
    refund_amount = Column(Numeric(14,2),nullable=False)
    state = Column(String(12),nullable=False,default='draft')
    revision = Column(Integer,nullable=False,default=1)
    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    committed_at = Column(DateTime(timezone=True))
    __mapper_args__ = {'version_id_col':revision}


class PharmaReturnLine(Base):
    __tablename__ = 'business_pharma_return_lines'
    __table_args__ = (
        ForeignKeyConstraint(['return_id','checkout_id','organization_id','branch_id','pack_context_id'],
            ['business_pharma_returns.id','business_pharma_returns.checkout_id','business_pharma_returns.organization_id',
             'business_pharma_returns.branch_id','business_pharma_returns.pack_context_id'],ondelete='RESTRICT',name='fk_pharma_return_line_root'),
        ForeignKeyConstraint(['checkout_line_id','checkout_id','organization_id','branch_id','pack_context_id','product_id'],
            ['srm_pos_checkout_lines.id','srm_pos_checkout_lines.checkout_id','srm_pos_checkout_lines.organization_id',
             'srm_pos_checkout_lines.branch_id','srm_pos_checkout_lines.scope_context_key','srm_pos_checkout_lines.product_id'],
            ondelete='RESTRICT',name='fk_pharma_return_line_source'),
        UniqueConstraint('return_id','checkout_line_id',name='uq_pharma_return_source_line'),
        UniqueConstraint('id','return_id','checkout_id','checkout_line_id','organization_id','branch_id','pack_context_id','product_id','sales_order_line_id',name='uq_pharma_return_line_scope'),
        CheckConstraint('quantity > 0 AND net_amount >= 0 AND tax_amount >= 0 AND gross_amount >= 0 AND round(net_amount+tax_amount,2)=gross_amount',name='ck_pharma_return_line_money'),
    )
    id = Column(Integer,primary_key=True)
    return_id = Column(Integer,nullable=False)
    checkout_id = Column(Integer,nullable=False)
    organization_id = Column(Integer,nullable=False)
    branch_id = Column(Integer,nullable=False)
    pack_context_id = Column(Integer,nullable=False)
    checkout_line_id = Column(Integer,nullable=False)
    product_id = Column(Integer,nullable=False)
    sales_order_line_id = Column(Integer,ForeignKey('srm_sales_order_lines.id',ondelete='RESTRICT'),nullable=False)
    invoice_line_id = Column(Integer,ForeignKey('srm_invoice_lines.id',ondelete='RESTRICT'),nullable=False)
    native_return_line_id = Column(Integer,ForeignKey('srm_pos_return_lines.id',ondelete='RESTRICT'),nullable=False,unique=True)
    quantity = Column(Numeric(14,3),nullable=False)
    net_amount = Column(Numeric(14,2),nullable=False)
    tax_amount = Column(Numeric(14,2),nullable=False)
    gross_amount = Column(Numeric(14,2),nullable=False)


@event.listens_for(PharmaReturn,'before_update')
def _immutable_return(mapper,connection,row):
    state=inspect(row)
    bind_once={'native_return_id','credit_voucher_id','refund_voucher_id','cash_movement_id','committed_at'}
    for attr in state.mapper.column_attrs:
        history=state.attrs[attr.key].history
        if not history.has_changes() or attr.key=='revision':continue
        if attr.key in bind_once and getattr(row,attr.key) is not None:
            from sqlalchemy import select
            original=history.deleted[0] if history.deleted else connection.execute(select(
                PharmaReturn.__table__.c[attr.key]).where(PharmaReturn.id==state.identity[0])).scalar_one()
            if original is None:continue
        if attr.key=='state' and tuple(history.deleted)==('draft',) and row.state=='committed':
            _complete_return(connection,row)
            continue
        raise ValueError('Issued return source and charges are immutable: '+attr.key)


@event.listens_for(PharmaReturnLine,'before_update')
@event.listens_for(PharmaReturnLine,'before_delete')
@event.listens_for(PharmaReturn,'before_delete')
def _immutable_return_history(mapper,connection,row):
    raise ValueError('Native return history is immutable')


class PharmaReturnLot(Base):
    __tablename__ = 'business_pharma_return_lots'
    __table_args__ = (
        ForeignKeyConstraint(['return_line_id','return_id','checkout_id','checkout_line_id',
            'organization_id','branch_id','pack_context_id','product_id','sales_order_line_id'],
            ['business_pharma_return_lines.'+name for name in ('id','return_id','checkout_id',
             'checkout_line_id','organization_id','branch_id','pack_context_id','product_id','sales_order_line_id')],
            ondelete='RESTRICT',name='fk_pharma_return_lot_line'),
        ForeignKeyConstraint(['allocation_id','organization_id','branch_id','pack_context_id',
            'sales_order_line_id','product_id','warehouse_id','original_batch_id'],
            ['business_pharma_batch_allocations.'+name for name in ('id','organization_id','branch_id',
             'pack_context_id','sales_order_line_id','product_id','warehouse_id','batch_id')],
            ondelete='RESTRICT',name='fk_pharma_return_lot_allocation'),
        UniqueConstraint('return_id','allocation_id',name='uq_pharma_return_original_allocation'),
        CheckConstraint("quantity > 0 AND disposition='quarantine' AND original_batch_id != quarantine_batch_id",
                        name='ck_pharma_return_lot_quarantine'),
    )
    id = Column(Integer,primary_key=True)
    return_line_id = Column(Integer,nullable=False)
    return_id = Column(Integer,nullable=False)
    checkout_id = Column(Integer,nullable=False)
    checkout_line_id = Column(Integer,nullable=False)
    organization_id = Column(Integer,nullable=False)
    branch_id = Column(Integer,nullable=False)
    pack_context_id = Column(Integer,nullable=False)
    product_id = Column(Integer,nullable=False)
    sales_order_line_id = Column(Integer,nullable=False)
    warehouse_id = Column(Integer,nullable=False)
    allocation_id = Column(Integer,nullable=False)
    original_batch_id = Column(Integer,nullable=False)
    quarantine_batch_id = Column(Integer,ForeignKey('srm_inventory_batches.id',ondelete='RESTRICT'),nullable=False,unique=True)
    stock_movement_id = Column(Integer,ForeignKey('srm_inventory_movements.id',ondelete='RESTRICT'),unique=True)
    original_batch_number = Column(String(120),nullable=False)
    original_expiry_date = Column(Date,nullable=False)
    quantity = Column(Numeric(14,3),nullable=False)
    disposition = Column(String(20),nullable=False,default='quarantine')
    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)


@event.listens_for(PharmaReturnLot,'before_update')
def _lot_movement_bind_once(mapper,connection,row):
    from sqlalchemy import select
    state = inspect(row)
    for attr in state.mapper.column_attrs:
        if not state.attrs[attr.key].history.has_changes():
            continue
        if attr.key == 'stock_movement_id' and row.stock_movement_id is not None:
            original = connection.scalar(select(PharmaReturnLot.stock_movement_id).where(PharmaReturnLot.id == state.identity[0]))
            if original is None:
                from app.apps.srm.models import SRMInventoryMovement
                movement=connection.execute(select(SRMInventoryMovement.__table__).where(SRMInventoryMovement.id==row.stock_movement_id)).mappings().first()
                root=connection.execute(select(PharmaReturn.state,PharmaReturn.created_by).where(PharmaReturn.id==row.return_id)).first()
                if (root is None or root.state!='draft' or movement is None or
                        (movement['organization_id'],movement['product_id'],movement['warehouse_id'],movement['quantity_in'],movement['quantity_out'],movement['movement_type'],movement['created_by'])
                        !=(row.organization_id,row.product_id,row.warehouse_id,row.quantity,0,'pharma_return_quarantine',root.created_by)):
                    raise ValueError('Quarantine movement must match its actual original-lot return')
                _owned(connection,SRMInventoryMovement,row.stock_movement_id,row)
                continue
        raise ValueError('Original medicine return lot provenance is immutable')


event.listen(PharmaReturnLot,'before_delete',_immutable_return_history)
MODELS = (PharmaReturn,PharmaReturnLine,PharmaReturnLot)


def _owned(connection, model, ident, row):
    from sqlalchemy import select
    from app.business_packs.models import PackRecordOwnership
    from app.branches.models import BranchOwnership
    for owner, extra in ((PackRecordOwnership.__table__, True), (BranchOwnership.__table__, False)):
        conditions = [owner.c.resource_table == model.__tablename__, owner.c.resource_key == str(ident),
                      owner.c.company_id == row.organization_id, owner.c.branch_id == row.branch_id]
        if extra:conditions.append(owner.c.context_id == row.pack_context_id)
        if not connection.scalar(select(owner.c.resource_key).where(*conditions)):
            raise ValueError('Original medicine return source ownership differs')


@event.listens_for(PharmaReturn,'before_insert')
def _original_checkout(mapper,connection,row):
    from sqlalchemy import select
    from app.apps.srm.service_checkout_models import POSServiceCheckout
    from app.apps.srm.models import SRMInvoice,SRMPOSSession
    from app.business_packs.models import PackContext
    if row.state not in (None,'draft'):
        raise ValueError('A medicine return must start as an uncommitted command')
    if connection.scalar(select(PackContext.pack_key).where(PackContext.id==row.pack_context_id))!='pharma':
        raise ValueError('Medicine return requires an actual Pharma source context')
    source=connection.execute(select(POSServiceCheckout.__table__).where(POSServiceCheckout.id==row.checkout_id)).mappings().first()
    if (not source or source['state']!='committed' or (source['organization_id'],source['branch_id'],source['pack_context_id'],source['sales_order_id'],source['invoice_id'],source['currency'])
            !=(row.organization_id,row.branch_id,row.pack_context_id,row.sales_order_id,row.invoice_id,row.currency)):
        raise ValueError('Original Pharma return checkout source differs')
    _owned(connection,POSServiceCheckout,row.checkout_id,row)
    _owned(connection,SRMInvoice,row.invoice_id,row)
    _owned(connection,SRMPOSSession,row.collection_session_id,row)
    invoice=connection.execute(select(SRMInvoice.total_amount,SRMInvoice.paid_amount,SRMInvoice.balance_amount,SRMInvoice.status).where(SRMInvoice.id==row.invoice_id)).first()
    if (invoice is None or invoice.status in ('draft','pending_approval','cancelled')
            or invoice.balance_amount!=0 or invoice.total_amount!=invoice.paid_amount
            or row.refund_amount<=0 or row.refund_amount>invoice.paid_amount):
        raise ValueError('Original medicine refund requires a fully paid issued sale')


@event.listens_for(PharmaReturnLine,'before_insert')
def _original_line(mapper,connection,row):
    from sqlalchemy import select
    from decimal import Decimal
    from app.apps.srm.service_checkout_models import POSCheckoutLine
    from app.apps.srm.models import SRMPOSReturnLine
    from .models import PharmaBatchAllocation
    source=connection.execute(select(POSCheckoutLine.__table__).where(POSCheckoutLine.id==row.checkout_line_id)).mappings().first()
    root=connection.execute(select(PharmaReturn.__table__).where(PharmaReturn.id==row.return_id)).mappings().first()
    if (not root or not source or source['line_kind']!='product' or root['state']!='draft'
            or (source['checkout_id'],source['organization_id'],source['branch_id'],source['scope_context_key'],source['product_id'],source['sales_order_line_id'],source['invoice_line_id'])
            !=(row.checkout_id,row.organization_id,row.branch_id,row.pack_context_id,row.product_id,row.sales_order_line_id,row.invoice_line_id)
            or (root['checkout_id'],root['organization_id'],root['branch_id'],root['pack_context_id'])
            !=(row.checkout_id,row.organization_id,row.branch_id,row.pack_context_id)):
        raise ValueError('Original medicine return line source differs')
    quantity=Decimal(row.quantity)
    if not quantity.is_finite() or quantity<=0 or quantity!=quantity.quantize(Decimal('.001')) or quantity>source['quantity']:
        raise ValueError('Medicine return quantity must retain exact original precision')
    native=connection.execute(select(SRMPOSReturnLine.__table__).where(SRMPOSReturnLine.id==row.native_return_line_id)).mappings().first()
    warehouses=set(connection.execute(select(PharmaBatchAllocation.warehouse_id).where(
        PharmaBatchAllocation.sales_order_line_id==row.sales_order_line_id,
        PharmaBatchAllocation.organization_id==row.organization_id,
        PharmaBatchAllocation.branch_id==row.branch_id,
        PharmaBatchAllocation.pack_context_id==row.pack_context_id)).scalars())
    if (not native or (native['return_id'],native['sales_order_line_id'],native['product_id'],native['quantity'],native['tax_amount'],native['line_total'])
            !=(root['native_return_id'],row.sales_order_line_id,row.product_id,quantity,row.tax_amount,row.gross_amount)
            or native['restock'] is not False or len(warehouses)!=1 or native['warehouse_id'] not in warehouses):
        raise ValueError('Native medicine return line differs from quarantine charges')
    _owned(connection,POSCheckoutLine,row.checkout_line_id,row)


@event.listens_for(PharmaReturnLot,'before_insert')
def _original_allocation(mapper,connection,row):
    from sqlalchemy import select
    from decimal import Decimal
    from .models import PharmaBatchAllocation
    from app.apps.srm.models import SRMInventoryBatch
    if row.stock_movement_id is not None:
        raise ValueError('Quarantine movement must bind after its actual lot source is persisted')
    source=connection.execute(select(PharmaBatchAllocation.__table__).where(PharmaBatchAllocation.id==row.allocation_id)).mappings().first()
    line=connection.execute(select(PharmaReturnLine.__table__).where(PharmaReturnLine.id==row.return_line_id)).mappings().first()
    if (not source or not line or
            tuple(source[key] for key in ('organization_id','branch_id','pack_context_id','sales_order_line_id','product_id','warehouse_id','batch_id','batch_number','expiry_date'))
            !=(row.organization_id,row.branch_id,row.pack_context_id,row.sales_order_line_id,row.product_id,row.warehouse_id,row.original_batch_id,row.original_batch_number,row.original_expiry_date)
            or tuple(line[key] for key in ('return_id','checkout_id','checkout_line_id','organization_id','branch_id','pack_context_id','product_id','sales_order_line_id'))
            !=(row.return_id,row.checkout_id,row.checkout_line_id,row.organization_id,row.branch_id,row.pack_context_id,row.product_id,row.sales_order_line_id)):
        raise ValueError('Original medicine allocation source differs')
    quantity=Decimal(row.quantity)
    if not quantity.is_finite() or quantity<=0 or quantity!=quantity.quantize(Decimal('.001')) or quantity>source['quantity']:
        raise ValueError('Original medicine lot return quantity differs')
    batch=connection.execute(select(SRMInventoryBatch.__table__).where(SRMInventoryBatch.id==row.quarantine_batch_id)).mappings().first()
    original=connection.execute(select(SRMInventoryBatch.__table__).where(SRMInventoryBatch.id==row.original_batch_id)).mappings().first()
    if (not batch or row.quarantine_batch_id==row.original_batch_id or
            (batch['organization_id'],batch['product_id'],batch['warehouse_id'],batch['expiry_date'],batch['quantity'],batch['available_quantity'],batch['status'])
            !=(row.organization_id,row.product_id,row.warehouse_id,row.original_expiry_date,quantity,0,'quarantined')
            or not original or batch['unit_cost']!=original['unit_cost'] or batch['manufacture_date']!=original['manufacture_date']):
        raise ValueError('Returned medicine must enter a separate unavailable quarantine lot')
    _owned(connection,PharmaBatchAllocation,row.allocation_id,row)


def _complete_return(connection,row):
    """No financial pointer alone can certify a completed stock return."""
    from sqlalchemy import select
    from decimal import Decimal
    from app.apps.srm.models import SRMPOSReturn,SRMPOSReturnLine,SRMInventoryBatch,SRMInventoryMovement,SRMPOSCashMovement
    from app.apps.srm.service_checkout_models import POSServiceCheckout
    from app.apps.fam.models import FAMVoucher,FAMVoucherType
    def failed():raise ValueError('Medicine return requires complete native quarantine and refund sources')
    lines=connection.execute(select(PharmaReturnLine.__table__).where(PharmaReturnLine.return_id==row.id)).mappings().all()
    native=connection.execute(select(SRMPOSReturn.__table__).where(SRMPOSReturn.id==row.native_return_id)).mappings().first()
    customer=connection.scalar(select(POSServiceCheckout.customer_id).where(POSServiceCheckout.id==row.checkout_id))
    if (not lines or not native or native['organization_id']!=row.organization_id
            or native['sales_order_id']!=row.sales_order_id or native['session_id']!=row.collection_session_id
            or native['created_by']!=row.created_by or native['refund_amount']!=row.refund_amount
            or native['customer_id']!=customer or native['subtotal']!=row.net_amount or native['tax_amount']!=row.tax_amount
            or native['refund_method']!=row.refund_method or native['refund_status']!='refunded'):failed()
    native_ids=set(connection.execute(select(SRMPOSReturnLine.id).where(SRMPOSReturnLine.return_id==row.native_return_id)).scalars())
    if native_ids!={line['native_return_line_id'] for line in lines}:failed()
    if tuple(sum((line[key] for line in lines),Decimal(0)) for key in ('net_amount','tax_amount','gross_amount'))!=(row.net_amount,row.tax_amount,row.refund_amount):failed()
    for line in lines:
        native_line=connection.execute(select(SRMPOSReturnLine.__table__).where(SRMPOSReturnLine.id==line['native_return_line_id'])).mappings().first()
        lots=connection.execute(select(PharmaReturnLot.__table__).where(PharmaReturnLot.return_line_id==line['id'])).mappings().all()
        if (not native_line or native_line['return_id']!=row.native_return_id or not lots
                or (native_line['quantity'],native_line['tax_amount'],native_line['line_total'])
                !=(line['quantity'],line['tax_amount'],line['gross_amount'])
                or native_line['product_id']!=line['product_id'] or native_line['sales_order_line_id']!=line['sales_order_line_id']
                or native_line['restock'] is not False or any(lot['warehouse_id']!=native_line['warehouse_id'] for lot in lots)
                or sum((lot['quantity'] for lot in lots),Decimal(0))!=line['quantity']):failed()
        for lot in lots:
            batch=connection.execute(select(SRMInventoryBatch.__table__).where(SRMInventoryBatch.id==lot['quarantine_batch_id'])).mappings().first()
            movement=connection.execute(select(SRMInventoryMovement.__table__).where(SRMInventoryMovement.id==lot['stock_movement_id'])).mappings().first()
            if (not batch or not movement or
                    (batch['organization_id'],batch['product_id'],batch['warehouse_id'],batch['quantity'],batch['available_quantity'],batch['status'])
                    !=(row.organization_id,lot['product_id'],lot['warehouse_id'],lot['quantity'],0,'quarantined')
                    or (movement['organization_id'],movement['product_id'],movement['warehouse_id'],movement['quantity_in'],movement['quantity_out'],movement['movement_type'],movement['created_by'])
                    !=(row.organization_id,lot['product_id'],lot['warehouse_id'],lot['quantity'],0,'pharma_return_quarantine',row.created_by)):failed()
    for ident,code in ((row.credit_voucher_id,'CN'),(row.refund_voucher_id,'PV')):
        voucher=connection.execute(select(FAMVoucher.__table__).where(FAMVoucher.id==ident)).mappings().first()
        kind=connection.execute(select(FAMVoucherType.__table__).where(FAMVoucherType.id==voucher['voucher_type_id'])).mappings().first() if voucher else None
        if (not voucher or not kind or kind['company_id']!=row.organization_id or kind['voucher_type_code']!=code
                or voucher['company_id']!=row.organization_id or voucher['status']!='posted'
                or voucher['source_module']!='srm' or voucher['source_record_type']!='pharma_return'
                or voucher['source_record_id']!=str(row.id)
                or voucher['total_debit']!=row.refund_amount or voucher['total_credit']!=row.refund_amount):failed()
    if row.refund_method=='cash':
        cash=connection.execute(select(SRMPOSCashMovement.__table__).where(SRMPOSCashMovement.id==row.cash_movement_id)).mappings().first()
        if not cash or (cash['organization_id'],cash['session_id'],cash['movement_type'],cash['amount'],cash['created_by'])!=(row.organization_id,row.collection_session_id,'cash_out',row.refund_amount,row.created_by):failed()
    elif row.cash_movement_id is not None:failed()


