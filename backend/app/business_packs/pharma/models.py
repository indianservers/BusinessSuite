"""Typed private provenance for canonical lot resources."""
from sqlalchemy import Column,Integer,String,Date,DateTime,Numeric,Boolean,ForeignKey,ForeignKeyConstraint,UniqueConstraint,CheckConstraint,Index,event,inspect,func
from app.db.base_class import Base


class PackBatchAvailability(Base):
    __tablename__='business_pharma_batch_availability'
    __table_args__=(
        ForeignKeyConstraint(['pack_context_id','organization_id','branch_id'],['business_pack_contexts.id','business_pack_contexts.company_id','business_pack_contexts.branch_id'],ondelete='RESTRICT',name='fk_pharma_batch_context'),
        UniqueConstraint('pack_context_id','batch_id',name='uq_pharma_batch_available'),
    )
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False)
    branch_id=Column(Integer,nullable=False)
    pack_context_id=Column(Integer,nullable=False)
    batch_id=Column(Integer,ForeignKey('srm_inventory_batches.id',ondelete='RESTRICT'),nullable=False)
    active=Column(Boolean,nullable=False,default=True)


class PharmaBatchReceipt(Base):
    __tablename__='business_pharma_batch_receipts'
    __table_args__=(
        ForeignKeyConstraint(['pack_context_id','organization_id','branch_id'],['business_pack_contexts.id','business_pack_contexts.company_id','business_pack_contexts.branch_id'],ondelete='RESTRICT',name='fk_pharma_receipt_context'),
        UniqueConstraint('organization_id','branch_id','pack_context_id','request_key',name='uq_pharma_receipt_request'),
        CheckConstraint('quantity > 0 AND unit_cost >= 0',name='ck_pharma_receipt_quantity'),
        CheckConstraint('length(request_key)=36 AND length(request_sha256)=64',name='ck_pharma_receipt_request'),
    )
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    branch_id=Column(Integer,nullable=False)
    pack_context_id=Column(Integer,nullable=False)
    request_key=Column(String(36),nullable=False)
    request_sha256=Column(String(64),nullable=False)
    created_by=Column(Integer,ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    product_id=Column(Integer,ForeignKey('srm_products.id',ondelete='RESTRICT'),nullable=False)
    warehouse_id=Column(Integer,ForeignKey('srm_warehouses.id',ondelete='RESTRICT'),nullable=False)
    batch_id=Column(Integer,ForeignKey('srm_inventory_batches.id',ondelete='RESTRICT'),nullable=False)
    movement_id=Column(Integer,ForeignKey('srm_inventory_movements.id',ondelete='RESTRICT'),unique=True)
    quantity=Column(Numeric(14,3),nullable=False)
    unit_cost=Column(Numeric(14,4),nullable=False)
    batch_number=Column(String(120),nullable=False)
    manufacture_date=Column(Date)
    expiry_date=Column(Date,nullable=False)
    received_date=Column(Date,nullable=False)
    created_at=Column(DateTime(timezone=True),server_default=func.now(),nullable=False)


class PharmaBatchAllocation(Base):
    __tablename__='business_pharma_batch_allocations'
    __table_args__=(
        ForeignKeyConstraint(['pack_context_id','organization_id','branch_id'],['business_pack_contexts.id','business_pack_contexts.company_id','business_pack_contexts.branch_id'],ondelete='RESTRICT',name='fk_pharma_allocation_context'),
        UniqueConstraint('sales_order_line_id','batch_id',name='uq_pharma_line_batch'),
        Index('uq_pharma_allocation_return_source','id','organization_id','branch_id','pack_context_id',
              'sales_order_line_id','product_id','warehouse_id','batch_id',unique=True),
        CheckConstraint('quantity > 0',name='ck_pharma_allocation_quantity'),
    )
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,nullable=False,index=True)
    branch_id=Column(Integer,nullable=False)
    pack_context_id=Column(Integer,nullable=False)
    sales_order_line_id=Column(Integer,ForeignKey('srm_sales_order_lines.id',ondelete='RESTRICT'),nullable=False)
    batch_id=Column(Integer,ForeignKey('srm_inventory_batches.id',ondelete='RESTRICT'),nullable=False)
    movement_id=Column(Integer,ForeignKey('srm_inventory_movements.id',ondelete='RESTRICT'),nullable=False)
    product_id=Column(Integer,ForeignKey('srm_products.id',ondelete='RESTRICT'),nullable=False)
    warehouse_id=Column(Integer,ForeignKey('srm_warehouses.id',ondelete='RESTRICT'),nullable=False)
    quantity=Column(Numeric(14,3),nullable=False)
    batch_number=Column(String(120),nullable=False)
    expiry_date=Column(Date,nullable=False)
    created_by=Column(Integer,ForeignKey('users.id',ondelete='RESTRICT'),nullable=False)
    created_at=Column(DateTime(timezone=True),server_default=func.now(),nullable=False)


@event.listens_for(PharmaBatchReceipt,'before_update')
def receipt_immutable(mapper,connection,row):
    state=inspect(row)
    for attr in state.mapper.column_attrs:
        history=state.attrs[attr.key].history
        if not history.has_changes():continue
        if attr.key=='movement_id' and row.movement_id is not None:
            from sqlalchemy import select
            original=history.deleted[0] if history.deleted else connection.scalar(select(PharmaBatchReceipt.__table__.c.movement_id).where(PharmaBatchReceipt.id==state.identity[0]))
            if original is None:continue
        raise ValueError('Pharma receipt provenance is immutable')


@event.listens_for(PharmaBatchReceipt,'before_delete')
@event.listens_for(PharmaBatchAllocation,'before_update')
@event.listens_for(PharmaBatchAllocation,'before_delete')
def history_immutable(mapper,connection,row):
    raise ValueError('Pharma stock provenance is immutable')


MODELS=(PackBatchAvailability,PharmaBatchReceipt,PharmaBatchAllocation)


@event.listens_for(PharmaBatchAllocation,'before_insert')
def allocation_source(mapper,connection,row):
    from sqlalchemy import select
    from app.apps.srm.models import SRMSalesOrder,SRMSalesOrderLine,SRMInventoryMovement,SRMInventoryBatch
    from app.business_packs.models import PackRecordOwnership
    line=connection.execute(select(SRMSalesOrderLine.__table__).where(SRMSalesOrderLine.id==row.sales_order_line_id)).mappings().first()
    order=connection.execute(select(SRMSalesOrder.__table__).where(SRMSalesOrder.id==line['sales_order_id'])).mappings().first() if line else None
    movement=connection.execute(select(SRMInventoryMovement.__table__).where(SRMInventoryMovement.id==row.movement_id)).mappings().first()
    batch=connection.execute(select(SRMInventoryBatch.__table__).where(SRMInventoryBatch.id==row.batch_id)).mappings().first()
    if not line or not order or not movement or not batch or (order['organization_id'],order['created_by'],line['product_id'])!=(row.organization_id,row.created_by,row.product_id):raise ValueError('Allocation native source differs')
    if (movement['organization_id'],movement['created_by'],movement['product_id'],movement['warehouse_id'],movement['quantity_in'],movement['movement_type'],movement['reference_number'])!=(row.organization_id,row.created_by,row.product_id,row.warehouse_id,0,'pos_sale',order['order_number']) or movement['quantity_out']!=line['quantity'] or row.quantity>line['quantity']:raise ValueError('Allocation stock movement differs')
    previous=connection.scalar(select(func.coalesce(func.sum(PharmaBatchAllocation.quantity),0)).where(PharmaBatchAllocation.sales_order_line_id==row.sales_order_line_id))
    if previous+row.quantity>line['quantity']:raise ValueError('Allocation total exceeds the native sale quantity')
    if (batch['organization_id'],batch['product_id'],batch['warehouse_id'],batch['batch_number'],batch['expiry_date'])!=(row.organization_id,row.product_id,row.warehouse_id,row.batch_number,row.expiry_date):raise ValueError('Allocation canonical lot differs')
    owner=PackRecordOwnership.__table__
    for model,ident in ((SRMSalesOrder,order['id']),(SRMSalesOrderLine,line['id']),(SRMInventoryMovement,movement['id'])):
        if not connection.scalar(select(owner.c.id).where(owner.c.resource_table==model.__tablename__,owner.c.resource_key==str(ident),owner.c.company_id==row.organization_id,owner.c.branch_id==row.branch_id,owner.c.context_id==row.pack_context_id)):raise ValueError('Allocation private source ownership differs')
