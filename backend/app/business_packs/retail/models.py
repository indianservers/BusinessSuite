"""Typed return provenance; balances remain in native stock and company books."""
from sqlalchemy import (Column, Integer, String, Text, Numeric, DateTime, ForeignKey,
    ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Boolean, event, inspect, func)
from app.db.base_class import Base


class RetailSaleStockSource(Base):
    __tablename__ = 'business_retail_sale_stock_sources'
    __table_args__ = (
        ForeignKeyConstraint(['pack_context_id','organization_id','branch_id'],
            ['business_pack_contexts.id','business_pack_contexts.company_id','business_pack_contexts.branch_id'],
            ondelete='RESTRICT',name='fk_retail_sale_stock_context'),
        CheckConstraint('pack_context_id > 0 AND quantity > 0',name='ck_retail_sale_stock_quantity'),
    )
    id = Column(Integer,primary_key=True)
    organization_id = Column(Integer,nullable=False)
    branch_id = Column(Integer,nullable=False)
    pack_context_id = Column(Integer,nullable=False)
    sales_order_line_id = Column(Integer,ForeignKey('srm_sales_order_lines.id',ondelete='RESTRICT'),nullable=False,unique=True)
    movement_id = Column(Integer,ForeignKey('srm_inventory_movements.id',ondelete='RESTRICT'),nullable=False,unique=True)
    product_id = Column(Integer,ForeignKey('srm_products.id',ondelete='RESTRICT'),nullable=False)
    warehouse_id = Column(Integer,ForeignKey('srm_warehouses.id',ondelete='RESTRICT'),nullable=False)
    quantity = Column(Numeric(24,10),nullable=False)
    created_by = Column(Integer,ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    created_at = Column(DateTime(timezone=True),server_default=func.now(),nullable=False)


class RetailReturn(Base):
    __tablename__ = 'business_retail_returns'
    __table_args__ = (
        ForeignKeyConstraint(['checkout_id','organization_id','branch_id','pack_context_id'],
            ['srm_pos_service_checkouts.id','srm_pos_service_checkouts.organization_id',
             'srm_pos_service_checkouts.branch_id','srm_pos_service_checkouts.scope_context_key'],
            ondelete='RESTRICT', name='fk_retail_return_checkout_scope'),
        UniqueConstraint('organization_id','branch_id','pack_context_id','request_key', name='uq_retail_return_request'),
        UniqueConstraint('id','checkout_id','organization_id','branch_id','pack_context_id',name='uq_retail_return_scope'),
        CheckConstraint('pack_context_id > 0 AND revision > 0',name='ck_retail_return_scope'),
        CheckConstraint("state IN ('draft','committed')",name='ck_retail_return_state'),
        CheckConstraint('length(request_key)=36 AND length(request_sha256)=64',name='ck_retail_return_request'),
        CheckConstraint("refund_method IN ('cash','card') AND length(currency)=3",name='ck_retail_return_payment'),
        CheckConstraint('net_amount >= 0 AND tax_amount >= 0 AND refund_amount > 0 AND net_amount+tax_amount=refund_amount',name='ck_retail_return_money'),
        CheckConstraint("state != 'committed' OR (native_return_id IS NOT NULL AND credit_voucher_id IS NOT NULL AND refund_voucher_id IS NOT NULL AND committed_at IS NOT NULL)",name='ck_retail_return_committed'),
        CheckConstraint("refund_method != 'cash' OR state != 'committed' OR cash_movement_id IS NOT NULL",name='ck_retail_return_cash'),
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


class RetailReturnLine(Base):
    __tablename__ = 'business_retail_return_lines'
    __table_args__ = (
        ForeignKeyConstraint(['return_id','checkout_id','organization_id','branch_id','pack_context_id'],
            ['business_retail_returns.id','business_retail_returns.checkout_id','business_retail_returns.organization_id',
             'business_retail_returns.branch_id','business_retail_returns.pack_context_id'],ondelete='RESTRICT',name='fk_retail_return_line_root'),
        ForeignKeyConstraint(['checkout_line_id','checkout_id','organization_id','branch_id','pack_context_id','product_id'],
            ['srm_pos_checkout_lines.id','srm_pos_checkout_lines.checkout_id','srm_pos_checkout_lines.organization_id',
             'srm_pos_checkout_lines.branch_id','srm_pos_checkout_lines.scope_context_key','srm_pos_checkout_lines.product_id'],
            ondelete='RESTRICT',name='fk_retail_return_line_source'),
        UniqueConstraint('return_id','checkout_line_id',name='uq_retail_return_source_line'),
        CheckConstraint('quantity > 0 AND net_amount >= 0 AND tax_amount >= 0 AND gross_amount >= 0 AND net_amount+tax_amount=gross_amount',name='ck_retail_return_line_money'),
        CheckConstraint('restock = false OR stock_movement_id IS NOT NULL',name='ck_retail_return_line_stock'),
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
    stock_movement_id = Column(Integer,ForeignKey('srm_inventory_movements.id',ondelete='RESTRICT'),unique=True)
    quantity = Column(Numeric(24,10),nullable=False)
    net_amount = Column(Numeric(14,2),nullable=False)
    tax_amount = Column(Numeric(14,2),nullable=False)
    gross_amount = Column(Numeric(14,2),nullable=False)
    restock = Column(Boolean,nullable=False)


@event.listens_for(RetailReturn,'before_update')
def _immutable_return(mapper,connection,row):
    state=inspect(row)
    bind_once={'native_return_id','credit_voucher_id','refund_voucher_id','cash_movement_id','committed_at'}
    for attr in state.mapper.column_attrs:
        history=state.attrs[attr.key].history
        if not history.has_changes() or attr.key=='revision':continue
        if attr.key in bind_once and getattr(row,attr.key) is not None:
            from sqlalchemy import select
            original=history.deleted[0] if history.deleted else connection.execute(select(
                RetailReturn.__table__.c[attr.key]).where(RetailReturn.id==state.identity[0])).scalar_one()
            if original is None:continue
        if attr.key=='state' and tuple(history.deleted)==('draft',) and row.state=='committed':continue
        raise ValueError('Issued return source and charges are immutable: '+attr.key)


@event.listens_for(RetailReturnLine,'before_update')
@event.listens_for(RetailReturnLine,'before_delete')
@event.listens_for(RetailReturn,'before_delete')
@event.listens_for(RetailSaleStockSource,'before_update')
@event.listens_for(RetailSaleStockSource,'before_delete')
def _immutable_return_history(mapper,connection,row):
    raise ValueError('Native return history is immutable')


@event.listens_for(RetailSaleStockSource,'before_insert')
def _sale_stock_source(mapper,connection,row):
    from sqlalchemy import select
    from app.apps.srm.models import SRMSalesOrder,SRMSalesOrderLine,SRMInventoryMovement
    from app.business_packs.models import PackRecordOwnership
    from app.branches.models import BranchOwnership
    line=connection.execute(select(SRMSalesOrderLine.__table__).where(SRMSalesOrderLine.id==row.sales_order_line_id)).mappings().first()
    movement=connection.execute(select(SRMInventoryMovement.__table__).where(SRMInventoryMovement.id==row.movement_id)).mappings().first()
    order=connection.execute(select(SRMSalesOrder.__table__).where(SRMSalesOrder.id==line['sales_order_id'])).mappings().first() if line else None
    if not line or not movement or not order or (order['organization_id'],order['created_by'],line['product_id'],line['quantity'])!=(row.organization_id,row.created_by,row.product_id,row.quantity):
        raise ValueError('Sale stock provenance requires its actual issued native sale line')
    if (movement['organization_id'],movement['created_by'],movement['product_id'],movement['warehouse_id'],movement['quantity_out'],movement['quantity_in'],movement['movement_type'])!=(row.organization_id,row.created_by,row.product_id,row.warehouse_id,row.quantity,0,'pos_sale'):
        raise ValueError('Sale stock provenance differs from the actual native movement')
    for model,ident in ((SRMSalesOrder,order['id']),(SRMSalesOrderLine,line['id']),(SRMInventoryMovement,movement['id'])):
        private=connection.execute(select(PackRecordOwnership.__table__.c.id).where(
            PackRecordOwnership.resource_table==model.__tablename__,PackRecordOwnership.resource_key==str(ident),
            PackRecordOwnership.company_id==row.organization_id,PackRecordOwnership.branch_id==row.branch_id,PackRecordOwnership.context_id==row.pack_context_id)).first()
        native=connection.execute(select(BranchOwnership.__table__.c.resource_key).where(
            BranchOwnership.resource_table==model.__tablename__,BranchOwnership.resource_key==str(ident),
            BranchOwnership.company_id==row.organization_id,BranchOwnership.branch_id==row.branch_id)).first()
        if private is None or native is None:raise ValueError('Sale stock provenance requires both exact native and private source ownership')


MODELS=(RetailSaleStockSource,RetailReturn,RetailReturnLine)
