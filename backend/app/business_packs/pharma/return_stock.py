"""Private original-allocation quarantine command; no sellable stock restoration."""
from contextlib import contextmanager
from dataclasses import dataclass,field
from datetime import date
from decimal import Decimal
from uuid import uuid4
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import select,func,inspect

_ACTIVE=WeakKeyDictionary()


def fail(message='Original medicine quarantine source is unavailable',status=409):
    raise HTTPException(status,message)


@dataclass
class _Lease:
    db:object
    actor:object
    scope:object
    root:object
    batches:dict=field(default_factory=dict)


def _current(lease):
    from app.apps.srm.service_checkout import _authority,_source_scope
    from .return_models import PharmaReturn
    db,actor,scope,root=lease.db,lease.actor,lease.scope,lease.root
    if _ACTIVE.get(db) is not lease or db.info.get('business_pack_scope') is not scope:
        fail(status=403)
    company,branch,fresh=_authority(db,actor,payments=True)
    if fresh!=scope or (company,branch)!=(scope.company_id,scope.branch_id) or scope.pack_key!='pharma':fail(status=403)
    if not {'pharma.returns.approve','pharma.payments.record'}<=scope.capabilities:fail(status=403)
    state=inspect(root,raiseerr=False)
    if (type(root) is not PharmaReturn or state.session is not db or not state.persistent or root in db.deleted
            or root.state!='draft' or state.identity!=(root.id,)
            or (root.organization_id,root.branch_id,root.pack_context_id,root.created_by)!=(company,branch,scope.context_id,actor.id)):
        fail(status=403)
    _source_scope(db,scope,company,branch,PharmaReturn,root.id)
    return db.connection()


@contextmanager
def quarantine_operation(db,actor,scope,root):
    if db in _ACTIVE:fail('Quarantine commands cannot nest',403)
    lease=_Lease(db,actor,scope,root)
    _ACTIVE[db]=lease
    try:
        _current(lease)
        from app.apps.srm.services.commercial import lock_tenant
        lock_tenant(db,actor);_current(lease)
        yield lease
    finally:
        if _ACTIVE.get(db) is lease:del _ACTIVE[db]


def create_batch(lease,line,allocation,quantity):
    """Create one opaque unavailable batch from an actual issued allocation."""
    from .return_models import PharmaReturnLine,_owned
    from .models import PharmaBatchAllocation
    from app.apps.srm.models import SRMProduct,SRMWarehouse,SRMInventoryBatch,SRMInventoryBalance
    from app.branches.models import BranchOwnership
    db,scope=lease.db,lease.scope
    connection=_current(lease)
    for item,model in ((line,PharmaReturnLine),(allocation,PharmaBatchAllocation)):
        state=inspect(item,raiseerr=False)
        if type(item) is not model or state.session is not db or not state.persistent or state.modified or item in db.deleted:fail(status=403)
        _owned(connection,model,item.id,lease.root)
    if (line.return_id!=lease.root.id or
            (allocation.organization_id,allocation.branch_id,allocation.pack_context_id,allocation.sales_order_line_id,allocation.product_id)
            !=(scope.company_id,scope.branch_id,scope.context_id,line.sales_order_line_id,line.product_id)):
        fail(status=403)
    quantity=Decimal(quantity)
    if not quantity.is_finite() or quantity<=0 or quantity!=quantity.quantize(Decimal('.001')) or quantity>allocation.quantity:fail('Invalid original lot return quantity',422)
    if allocation.id in lease.batches:fail('An original allocation can be received only once per command')
    reserved=sum((entry['quantity'] for entry in lease.batches.values() if entry['line'] is line),Decimal(0))
    if reserved+quantity>line.quantity:fail('Quarantine quantities exceed the certified native return line')
    p,w,b,stock=(model.__table__ for model in (SRMProduct,SRMWarehouse,SRMInventoryBatch,SRMInventoryBalance))
    if connection.scalar(select(p.c.id).where(p.c.id==line.product_id,p.c.organization_id==scope.company_id).with_for_update()) is None:fail()
    if connection.scalar(select(w.c.id).where(w.c.id==allocation.warehouse_id,w.c.organization_id==scope.company_id).with_for_update()) is None:fail()
    balance=connection.execute(select(stock.c.id,stock.c.quantity).where(stock.c.organization_id==scope.company_id,
        stock.c.product_id==line.product_id,stock.c.warehouse_id==allocation.warehouse_id).with_for_update()).first()
    if balance is None:fail('Original warehouse stock needs reconciliation')
    available=connection.scalar(select(func.coalesce(func.sum(b.c.available_quantity),0)).where(
        b.c.organization_id==scope.company_id,b.c.product_id==line.product_id,b.c.warehouse_id==allocation.warehouse_id))
    if Decimal(balance.quantity)<Decimal(available):fail('Canonical lot stock needs reconciliation before accepting a return')
    original=connection.execute(select(b).where(b.c.id==allocation.batch_id,b.c.organization_id==scope.company_id,
        b.c.product_id==line.product_id,b.c.warehouse_id==allocation.warehouse_id).with_for_update()).mappings().first()
    if (not original or original['batch_number']!=allocation.batch_number or original['expiry_date']!=allocation.expiry_date):fail()
    # Current recall/expiry/sellability deliberately does not reject a historical
    # original sale being returned into quarantine. Nothing is made available.
    number='PQR-'+str(lease.root.id)+'-'+uuid4().hex
    batch_id=connection.execute(b.insert().values(organization_id=scope.company_id,product_id=line.product_id,
        warehouse_id=allocation.warehouse_id,batch_number=number,manufacture_date=original['manufacture_date'],
        expiry_date=allocation.expiry_date,received_date=date.today(),quantity=quantity,available_quantity=0,
        unit_cost=original['unit_cost'],status='quarantined',created_by=lease.actor.id).returning(b.c.id)).scalar_one()
    native=BranchOwnership.__table__
    connection.execute(native.insert().values(resource_table=b.name,resource_key=str(batch_id),
        company_id=scope.company_id,branch_id=scope.branch_id,source='pharma-return-new-quarantine'))
    lease.batches[allocation.id]={'line':line,'allocation':allocation,'quantity':quantity,'batch_id':batch_id,
                                  'batch_number':number,'balance_id':balance.id}
    return batch_id


def receive(lease,lot):
    from .return_models import PharmaReturnLot,_owned
    from app.apps.srm.models import SRMInventoryBalance,SRMInventoryMovement,SRMSalesOrderLine,SRMSalesOrder
    from app.apps.srm.services.commercial_numbering import reserve_number
    from app.apps.srm.stock_resource import _write_quantity_cache
    db,scope=lease.db,lease.scope
    connection=_current(lease)
    state=inspect(lot,raiseerr=False)
    if type(lot) is not PharmaReturnLot or state.session is not db or not state.persistent or state.modified or lot.stock_movement_id is not None:fail(status=403)
    _owned(connection,PharmaReturnLot,lot.id,lease.root)
    certificate=lease.batches.get(lot.allocation_id)
    if (not certificate or certificate.get('received') or lot.return_id!=lease.root.id
            or lot.return_line_id!=certificate['line'].id or lot.quarantine_batch_id!=certificate['batch_id']
            or lot.quantity!=certificate['quantity']):fail(status=403)
    allocation=certificate['allocation']
    movement=connection.execute(select(SRMInventoryMovement.__table__).where(SRMInventoryMovement.id==allocation.movement_id)).mappings().first()
    line=connection.execute(select(SRMSalesOrderLine.__table__).where(SRMSalesOrderLine.id==allocation.sales_order_line_id)).mappings().first()
    order=connection.execute(select(SRMSalesOrder.__table__).where(SRMSalesOrder.id==lease.root.sales_order_id)).mappings().first()
    if (not movement or not line or not order or line['sales_order_id']!=order['id']
            or (movement['organization_id'],movement['product_id'],movement['warehouse_id'],movement['quantity_in'],movement['quantity_out'],movement['movement_type'],movement['reference_number'])
            !=(scope.company_id,lot.product_id,lot.warehouse_id,0,line['quantity'],'pos_sale',order['order_number'])):fail()
    _owned(connection,SRMInventoryMovement,allocation.movement_id,lease.root)
    table=SRMInventoryBalance.__table__
    balance=connection.execute(select(table.c.quantity).where(table.c.id==certificate['balance_id']).with_for_update()).scalar_one()
    changed=connection.execute(table.update().where(table.c.id==certificate['balance_id'],table.c.quantity==balance)
        .values(quantity=Decimal(balance)+lot.quantity))
    if changed.rowcount!=1:fail('Canonical quarantine stock changed; retry')
    returned=SRMInventoryMovement(organization_id=scope.company_id,
        movement_number=reserve_number(db,SRMInventoryMovement,'INV','movement_number',scope.company_id,actor=lease.actor),
        movement_type='pharma_return_quarantine',movement_date=date.today(),product_id=lot.product_id,
        warehouse_id=lot.warehouse_id,quantity_in=lot.quantity,quantity_out=0,rate=movement['rate'],
        value=lot.quantity*Decimal(movement['rate']),reference_number='PHARMA-RETURN-'+str(lease.root.id),
        notes='Original medicine lot returned to quarantine',created_by=lease.actor.id)
    returned._suite_source_record=lot
    db.add(returned);db.flush()
    lot.stock_movement_id=returned.id;db.flush()
    _write_quantity_cache(db,lot.product_id,scope.company_id)
    certificate['received']=True
    return returned
