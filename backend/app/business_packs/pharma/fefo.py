"""Closed lot allocation command inside the existing native sale transaction."""
from datetime import date
from decimal import Decimal
from sqlalchemy import select,String
from app.apps.srm.models import SRMInventoryBatch,SRMSalesOrderLine
from app.branches.models import BranchOwnership
from .models import PackBatchAvailability,PharmaBatchAllocation
from .receipts import fail

MAX_ALLOCATIONS=200


def supported(scope,product):
    def value(key):return product[key] if hasattr(product,'keys') else getattr(product,key)
    return bool(scope is not None and scope.pack_key=='pharma' and value('track_inventory') and value('batch_tracking')
        and value('expiry_tracking') and not value('serial_tracking') and (value('product_type') or '').lower() not in {'service','services'})


def split(rows,requested,stock_date):
    """Pure deterministic FEFO, with the current stock date excluded."""
    remaining=Decimal(requested);result=[]
    if not remaining.is_finite() or remaining<=0:raise ValueError('Lot demand must be positive and finite')
    for row in sorted(rows,key=lambda item:(item['expiry_date'] or date.max,item['received_date'] or date.max,item['id'])):
        if row['status']!='available' or row['expiry_date'] is None or row['expiry_date']<=stock_date:continue
        available=Decimal(row['available_quantity'] or 0)
        if not available.is_finite() or available<0:raise ValueError('Lot stock requires reconciliation')
        take=min(remaining,available)
        if take>0:result.append((row,take));remaining-=take
        if remaining==0:break
    if remaining:raise ValueError('Insufficient eligible unexpired batch stock for this cart')
    return result


def plan(db,scope,selected,*,consume=False):
    """Called only after native company/product/balance locks and authority proof."""
    tracked=[item for item in selected if supported(scope,item[2])]
    if not tracked:return {}
    if db.info.get('business_pack_scope')!=scope:fail('Pharma lot request scope changed')
    from .models import MODELS
    from sqlalchemy import inspect
    if not all(inspect(db.connection()).has_table(m.__tablename__) for m in MODELS):fail('Install the Pharma stock extension first',503)
    b=SRMInventoryBatch.__table__;a=PackBatchAvailability.__table__;native=BranchOwnership.__table__
    by_key={}
    for line,key,product,quantity in tracked:
        if quantity!=quantity.quantize(Decimal('.001')):fail('Lot quantities support at most three decimal places',422)
        by_key.setdefault(key,[]).append((line,quantity))
    result={}
    for (product,warehouse),lines in sorted(by_key.items()):
        # Lock IDs deterministically, then sort the actual locked snapshots FEFO.
        rows=db.connection().execute(select(b).join(a,a.c.batch_id==b.c.id).join(native,
            (native.c.resource_table==b.name)&(native.c.resource_key==b.c.id.cast(String)))
            .where(b.c.organization_id==scope.company_id,b.c.product_id==product,b.c.warehouse_id==warehouse,
                a.c.organization_id==scope.company_id,a.c.branch_id==scope.branch_id,a.c.pack_context_id==scope.context_id,a.c.active.is_(True),
                native.c.company_id==scope.company_id,native.c.branch_id==scope.branch_id,b.c.status=='available',b.c.expiry_date>date.today(),b.c.available_quantity>0)
            .order_by(b.c.id).limit(MAX_ALLOCATIONS+1).with_for_update(of=b)).mappings().all()
        if len(rows)>MAX_ALLOCATIONS:fail('This medicine exceeds the supported eligible batch allocation capacity; reconcile stock before checkout',409)
        remaining={row['id']:dict(row) for row in rows}
        for line,quantity in lines:
            try:allocations=split(remaining.values(),quantity,date.today())
            except ValueError as error:fail(str(error),409)
            result[id(line)]=[(dict(row),take) for row,take in allocations]
            if sum(len(items) for items in result.values())>MAX_ALLOCATIONS:fail('This cart exceeds the supported batch allocation capacity; split the sale',409)
            for row,take in allocations:remaining[row['id']]['available_quantity']=Decimal(row['available_quantity'])-take
        if consume:
            for row in rows:
                new=remaining[row['id']]['available_quantity']
                if new==row['available_quantity']:continue
                changed=db.connection().execute(b.update().where(b.c.id==row['id'],b.c.organization_id==scope.company_id,
                    b.c.available_quantity==row['available_quantity'],b.c.status=='available').values(available_quantity=new))
                if changed.rowcount!=1:fail('Batch stock changed; retry checkout',409)
    return result


def persist(db,scope,actor,line,movement,allocations):
    if not allocations:return
    from app.apps.srm.stock_resource import _private_source
    _private_source(db,scope,scope.company_id,scope.branch_id,line,SRMSalesOrderLine)
    if sum((quantity for _,quantity in allocations),Decimal(0))!=Decimal(line.quantity):fail('Lot allocation differs from the issued native sale quantity',409)
    from .references import creation_plan
    for batch,quantity in allocations:
        row=PharmaBatchAllocation(organization_id=scope.company_id,branch_id=scope.branch_id,pack_context_id=scope.context_id,
            sales_order_line_id=line.id,batch_id=batch['id'],movement_id=movement.id,product_id=line.product_id,
            warehouse_id=movement.warehouse_id,quantity=quantity,batch_number=batch['batch_number'],expiry_date=batch['expiry_date'],created_by=actor.id)
        with creation_plan(db,db.info['business_pack_scope'],row):
            db.add(row);db.flush()
    line.metadata_json={**(line.metadata_json or {}),'pharma_lot_count':len(allocations)}
    db.flush()


def sale_allocations(db,scope,root,lines):
    """Immutable issued snapshots only, source-proven to each actual invoice line."""
    if scope is None or scope.pack_key!='pharma':return {}
    from app.apps.srm.service_checkout import _source_scope
    from app.apps.srm.models import SRMInvoiceLine
    if (root.organization_id,root.branch_id,root.pack_context_id)!=(scope.company_id,scope.branch_id,scope.context_id):fail('Batch result checkout source differs',409)
    by_source={line.sales_order_line_id:line for line in lines}
    rows=db.query(PharmaBatchAllocation).filter(PharmaBatchAllocation.organization_id==scope.company_id,
        PharmaBatchAllocation.branch_id==scope.branch_id,PharmaBatchAllocation.pack_context_id==scope.context_id,
        PharmaBatchAllocation.sales_order_line_id.in_(list(by_source))).order_by(PharmaBatchAllocation.id).limit(MAX_ALLOCATIONS+1).all() if by_source else []
    if len(rows)>MAX_ALLOCATIONS:fail('Issued sale exceeds the supported batch result capacity',409)
    result={line.id:[] for line in lines}
    for row in rows:
        _source_scope(db,scope,scope.company_id,scope.branch_id,PharmaBatchAllocation,row.id)
        line=by_source[row.sales_order_line_id]
        source=db.get(SRMSalesOrderLine,row.sales_order_line_id);invoice=db.get(SRMInvoiceLine,line.invoice_line_id)
        if source is None or invoice is None or source.sales_order_id!=root.sales_order_id or invoice.invoice_id!=root.invoice_id or invoice.source_id!=source.id or row.product_id!=line.product_id:fail('Issued batch sale/invoice source differs',409)
        result[line.id].append({'batch_id':row.batch_id,'batch_number':row.batch_number,'expiry_date':row.expiry_date.isoformat(),'quantity':str(row.quantity),'movement_id':row.movement_id})
    for line in lines:
        source=db.get(SRMSalesOrderLine,line.sales_order_line_id)
        expected=(source.metadata_json or {}).get('pharma_lot_count',0) if source else 0
        if type(expected) is not int or expected!=len(result[line.id]) or (expected and sum((Decimal(item['quantity']) for item in result[line.id]),Decimal(0))!=line.quantity):fail('Issued batch allocation snapshot is incomplete',409)
    return result
