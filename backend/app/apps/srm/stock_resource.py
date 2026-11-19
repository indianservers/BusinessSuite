"""Fixed outbound sale command over canonical company stock resources.

Balances and cached product quantity remain canonical and unowned. This command
never grants master writes, exposes movement history, or supports adjustments,
returns, lots, expiry or serial allocations. Native/domain permissions remain
independent of explicit pack eligibility.
"""
from datetime import date,datetime,timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select,func,inspect,text,bindparam,cast,String
from sqlalchemy.orm.attributes import NO_VALUE,set_committed_value
from app.apps.srm.models import SRMProduct,SRMWarehouse,SRMInventoryBalance,SRMInventoryMovement,SRMSalesOrder,SRMSalesOrderLine
from app.branches.models import BranchOwnership

_FIELDS=('id','organization_id','active','deleted_at','product_type','track_inventory','batch_tracking','serial_tracking','expiry_tracking','default_warehouse_id','sales_rate','gst_rate','metadata_json','unit_code')


def fail(message,code=403):raise HTTPException(code,message)


def _authority(db,actor):
    from app.apps.srm.service_checkout import _authority as native_authority
    from app.apps.srm.services.commercial import lock_tenant
    company,branch,scope=native_authority(db,actor)
    if scope is None:fail('A freshly selected Business Pack is required for the sale stock command')
    if not any(scope.pack_key+'.'+name in scope.capabilities for name in ('checkout.create','billing.prepare')):
        fail('Assigned Business Pack role cannot issue sale stock')
    lock_tenant(db,actor)
    current=native_authority(db,actor)
    if current!=(company,branch,scope):fail('Sale stock authorization changed while waiting')
    return current


def _native_branch(db,table,ident,company,branch):
    owned=BranchOwnership.__table__
    row=db.connection().execute(select(owned.c.company_id,owned.c.branch_id).where(
        owned.c.resource_table==table,owned.c.resource_key==str(ident)).with_for_update()).first()
    if not row or (row.company_id,row.branch_id)!=(company,branch):fail('Stock resource is outside the writable native branch')


def _signature(values,branch):
    from app.shared.catalog_branches import is_available
    from types import SimpleNamespace
    metadata=values.get('metadata_json') or {}
    currency=metadata.get('currency','INR') if isinstance(metadata,dict) else None
    return tuple(values.get(name) for name in _FIELDS if name not in ('metadata_json',))+(
        metadata,currency,is_available(SimpleNamespace(metadata_json=metadata),branch))


def _product(db,ident,company,branch,scope,currency):
    from app.apps.srm.service_checkout import _source_scope
    table=SRMProduct.__table__
    row=db.connection().execute(select(*(table.c[name] for name in _FIELDS)).where(
        table.c.id==ident,table.c.organization_id==company).with_for_update()).mappings().first()
    if not row:fail('Eligible stock item is unavailable',404)
    _source_scope(db,scope,company,branch,SRMProduct,ident,master=True)
    if not row['active'] or row['deleted_at'] is not None:fail('Eligible stock item is inactive',409)
    if not _signature(row,branch)[-1]:fail('This offering is unavailable in the selected branch',422)
    metadata=row['metadata_json'] or {}
    if not isinstance(metadata,dict) or metadata.get('currency','INR')!=currency:fail('Stock item currency changed',409)
    # The native pricing operation may already hold this master in its identity
    # map. Do not silently price/classify from stale catalog data after locking.
    cached=db.identity_map.get((SRMProduct,(ident,),None))
    if cached is not None:
        state=inspect(cached)
        if all(state.attrs[name].loaded_value is not NO_VALUE for name in _FIELDS):
            old={name:state.attrs[name].loaded_value for name in _FIELDS}
            if _signature(old,branch)!=_signature(row,branch):fail('Catalog stock configuration changed; review the cart',409)
    service=(row['product_type'] or '').strip().lower() in {'service','services','membership','subscription','bundle'}
    from app.business_packs.pharma.eligibility import managed_product
    if managed_product(db,company,ident):
        from app.business_packs.pharma.fefo import supported
        if not supported(scope,row):fail('Managed batch stock requires the authorized Pharma lot workflow and unchanged stock classification',409)
    physical=bool(row['track_inventory'] and not service)
    if not service and any(row[name] for name in ('batch_tracking','serial_tracking','expiry_tracking')):
        from app.business_packs.pharma.fefo import supported
        if not supported(scope,row):fail('Tracked stock requires an explicit supported lot or serial allocation workflow',409)
    return row,physical


def _plan(db,actor,lines,currency):
    from app.apps.srm.service_checkout import _source_scope
    company,branch,scope=_authority(db,actor)
    products={}
    for ident in sorted({line.product_id for line in lines if line.product_id}):
        products[ident]=_product(db,ident,company,branch,scope,currency)
    selected=[];requirements={}
    for line in lines:
        if not line.product_id:continue
        product,physical=products[line.product_id]
        if not physical:continue
        warehouse=(line.metadata_json or {}).get('warehouse_id') or product['default_warehouse_id']
        if type(warehouse) is not int or warehouse<=0:fail('Choose an eligible stock warehouse',422)
        quantity=Decimal(line.quantity)
        if not quantity.is_finite() or quantity<=0:fail('Sale stock quantity must be positive and finite',422)
        key=(line.product_id,warehouse)
        requirements[key]=requirements.get(key,Decimal(0))+quantity
        selected.append((line,key,product,quantity))
    if requirements:
        from app.business_packs.native_policy import native_srm_policy
        if db.info.get('business_pack_policy')!=native_srm_policy(scope.pack_key).policy:
            fail('The audited physical sale isolation adapter is not installed',503)
    warehouses={key[1] for key in requirements}
    table=SRMWarehouse.__table__
    for ident in sorted(warehouses):
        row=db.connection().execute(select(table.c.id,table.c.organization_id,table.c.active).where(
            table.c.id==ident,table.c.organization_id==company).with_for_update()).first()
        if not row or not row.active:fail('Eligible stock warehouse is unavailable',404)
        _source_scope(db,scope,company,branch,SRMWarehouse,ident,master=True)
        _native_branch(db,table.name,ident,company,branch)
    balance=SRMInventoryBalance.__table__;balances={}
    for key,total in sorted(requirements.items()):
        row=db.connection().execute(select(balance.c.id,balance.c.quantity).where(
            balance.c.organization_id==company,balance.c.product_id==key[0],balance.c.warehouse_id==key[1]).with_for_update()).first()
        if not row or Decimal(row.quantity or 0)<total:fail('Insufficient eligible stock for this cart',409)
        # A canonical resource must never be adopted from a private balance row.
        from app.business_packs.models import PackRecordOwnership
        anchor=PackRecordOwnership.__table__
        if db.connection().scalar(select(anchor.c.id).where(anchor.c.resource_table==balance.name,anchor.c.resource_key==str(row.id))):
            fail('Canonical stock balance has an unsupported private ownership marker')
        balances[key]=(row.id,Decimal(row.quantity or 0),total)
    if _authority(db,actor)!=(company,branch,scope):fail('Sale stock authority changed')
    if scope.pack_key=='pharma':
        from app.business_packs.pharma.fefo import plan
        plan(db,scope,selected)
    return company,branch,scope,selected,balances


def preflight(data,db,actor):
    if (data.metadata_json or {}).get('source')!='pos':fail('Selected-pack stock requires the supported POS sale workflow',409)
    _plan(db,actor,list(data.lines),data.currency)


def _private_source(db,scope,company,branch,row,model):
    from app.apps.srm.service_checkout import _source_scope
    state=inspect(row)
    if type(row) is not model or state.session is not db or not state.persistent or not state.identity or state.identity!=(row.id,):
        fail('Sale stock requires a live persisted private native source')
    fields=('id','organization_id','created_by','metadata_json') if model is SRMSalesOrder else ('id','sales_order_id','product_id','quantity','unit_price','metadata_json')
    if any(state.attrs[name].history.has_changes() for name in fields):
        fail('Sale stock source identity or charge snapshot changed')
    table=model.__table__
    actual=db.connection().execute(select(*(table.c[name] for name in fields)).where(table.c.id==state.identity[0]).with_for_update()).mappings().first()
    if actual is None or any(actual[name]!=getattr(row,name) for name in fields):
        fail('Sale stock source differs from the persisted native snapshot')
    _source_scope(db,scope,company,branch,model,row.id)
    _native_branch(db,model.__tablename__,row.id,company,branch)


def issue_for_order(order,db,actor):
    lines=list(order.lines)
    company,branch,scope,selected,balances=_plan(db,actor,lines,order.currency)
    if not selected:return []
    _private_source(db,scope,company,branch,order,SRMSalesOrder)
    if order.organization_id!=company or order.created_by!=actor.id or (order.metadata_json or {}).get('source')!='pos':
        fail('Sale stock source does not match the native checkout actor')
    if (order.metadata_json or {}).get('inventory_issued_at'):
        fail('Sale stock is already issued; replay the original checkout request',409)
    for line in lines:
        _private_source(db,scope,company,branch,line,SRMSalesOrderLine)
        if line.sales_order_id!=order.id:fail('Sale stock line belongs to another native source')
    lot_plan={}
    if scope.pack_key=='pharma':
        from app.business_packs.pharma.fefo import plan
        lot_plan=plan(db,scope,selected,consume=True)
    balance=SRMInventoryBalance.__table__
    for key,(ident,available,total) in balances.items():
        result=db.connection().execute(balance.update().where(balance.c.id==ident,balance.c.organization_id==company,
            balance.c.product_id==key[0],balance.c.warehouse_id==key[1],balance.c.quantity==available).values(quantity=available-total))
        if result.rowcount!=1:fail('Canonical stock changed; retry the cart',409)
    movements=[]
    from app.apps.srm.services.commercial_numbering import reserve_number
    for line,key,product,quantity in selected:
        rate=Decimal(line.unit_price or product['sales_rate'] or 0)
        movement=SRMInventoryMovement(organization_id=company,
            movement_number=reserve_number(db,SRMInventoryMovement,'INV','movement_number',company,actor=actor),
            movement_type='pos_sale',movement_date=date.today(),product_id=key[0],warehouse_id=key[1],
            quantity_in=Decimal(0),quantity_out=quantity,rate=rate,value=quantity*rate,
            reference_number=order.order_number,notes='POS sale '+order.order_number,created_by=actor.id)
        movement._suite_source_record=line
        db.add(movement);db.flush();movements.append(movement)
        if scope.pack_key=='pharma':
            from app.business_packs.pharma.fefo import persist
            persist(db,scope,actor,line,movement,lot_plan.get(id(line),[]))
        if scope.pack_key=='retail':
            from app.business_packs.retail.models import RetailSaleStockSource
            from sqlalchemy import inspect as schema_inspect
            if not schema_inspect(db.connection()).has_table(RetailSaleStockSource.__tablename__):
                fail('Install the Retail stock-source extension before issuing selected Retail stock',503)
            db.add(RetailSaleStockSource(organization_id=company,branch_id=branch,pack_context_id=scope.context_id,
                sales_order_line_id=line.id,movement_id=movement.id,product_id=key[0],warehouse_id=key[1],
                quantity=quantity,created_by=actor.id))
            db.flush()
    # No generic ORM master mutation is enabled by a sale.
    for ident in sorted({key[0] for key in balances}):
        _write_quantity_cache(db,ident,company)
    if movements:order.metadata_json={**(order.metadata_json or {}),'inventory_issued_at':datetime.now(timezone.utc).isoformat(),'inventory_issue_movement_ids':[row.id for row in movements]}
    return movements



def _write_quantity_cache(db,product_id,raw_company):
    """Private fixed derived write, invoked only after validated stock purpose."""
    balance=SRMInventoryBalance.__table__
    company_guard=balance.c.organization_id.is_(None) if raw_company is None else balance.c.organization_id==raw_company
    from app.business_packs.models import PackRecordOwnership
    anchor=PackRecordOwnership.__table__
    if inspect(db.connection()).has_table(anchor.name):
        private=db.connection().execute(select(anchor.c.id).select_from(balance.join(anchor,
            (anchor.c.resource_table==balance.name)&(anchor.c.resource_key==cast(balance.c.id,String)))).where(
            company_guard,balance.c.product_id==product_id)).first()
        if private:fail('Canonical stock resource has unsupported private ownership')
    total=Decimal(db.connection().scalar(select(func.coalesce(func.sum(balance.c.quantity),0)).where(company_guard,balance.c.product_id==product_id)))
    # Fixed text intentionally avoids ORM/Core onupdate defaults: this command
    # changes exactly current_quantity, not metadata, prices, costs or timestamps.
    statement=text('UPDATE srm_products SET current_quantity=:quantity WHERE id=:product_id AND organization_id IS NULL' if raw_company is None else
                   'UPDATE srm_products SET current_quantity=:quantity WHERE id=:product_id AND organization_id=:company_id').bindparams(
                       bindparam('quantity',type_=SRMProduct.__table__.c.current_quantity.type))
    result=db.connection().execute(statement,{'quantity':total,'product_id':product_id,'company_id':raw_company})
    if result.rowcount!=1:fail('Canonical product quantity source changed',409)
    cached=db.identity_map.get((SRMProduct,(product_id,),None))
    if cached is not None:set_committed_value(cached,'current_quantity',total)


def refresh_legacy_quantity(db,product,actor,source_movement):
    """Existing native stock flows retain a canonical company-wide cache.

    This is not a stock adjustment or a master management permission. It cannot
    be borrowed by a selected pack or an unrelated CommonCore request binding.
    """
    if (db.info.get('business_pack_scope') is not None or db.info.get('business_pack_request_binding') is not None
            or db.info.get('business_common_core_scope') is not None):
        fail('Legacy stock cache requires a genuine native stock operation')
    from app.apps.srm.services.commercial import require,tenant,lock_tenant
    from app.access.service import check_background_access
    from app.apps.srm.services.commercial_numbering import _authority as writer_authority
    require(actor,'srm_manage','srm_admin');check_background_access(db,actor,'srm','create')
    company=tenant(actor);writer_authority(db,actor,company);lock_tenant(db,actor);writer_authority(db,actor,company)
    branch=getattr(db.info.get('branch_context'),'branch_id',None)
    if not branch or branch not in db.info['branch_context'].writable:fail('A writable native stock branch is required')
    for row,model in ((product,SRMProduct),(source_movement,SRMInventoryMovement)):
        state=inspect(row,raiseerr=False)
        if (type(row) is not model or state is None or state.session is not db or not state.persistent
                or row in db.deleted or state.identity!=(row.id,)
                or any(state.attrs[name].history.has_changes() for name in ('id','organization_id') if name in state.attrs)):
            fail('Native stock cache requires persisted source identities')
    p,m=SRMProduct.__table__,SRMInventoryMovement.__table__
    actual_product=db.connection().execute(select(p.c.id,p.c.organization_id).where(p.c.id==product.id).with_for_update()).first()
    actual=db.connection().execute(select(m.c.organization_id,m.c.product_id,m.c.created_by,m.c.warehouse_id).where(m.c.id==source_movement.id)).first()
    if (not actual_product or (actual_product.organization_id if actual_product.organization_id is not None else 1)!=company
            or not actual or actual.organization_id!=actual_product.organization_id or actual.product_id!=product.id
            or actual.created_by!=actor.id or source_movement.product_id!=actual.product_id
            or source_movement.created_by!=actual.created_by or source_movement.organization_id!=actual.organization_id):
        fail('Native stock cache source company, product or actor differs')
    from app.apps.srm.service_checkout import _source_scope
    _source_scope(db,None,company,branch,SRMInventoryMovement,source_movement.id)
    _source_scope(db,None,company,branch,SRMProduct,product.id)
    _native_branch(db,m.name,source_movement.id,company,branch)
    warehouse=SRMWarehouse.__table__
    if not db.connection().execute(select(warehouse.c.id).where(warehouse.c.id==actual.warehouse_id,
            func.coalesce(warehouse.c.organization_id,1)==company)).first():fail('Native stock warehouse belongs to another company')
    _native_branch(db,warehouse.name,actual.warehouse_id,company,branch)
    _write_quantity_cache(db,product.id,actual_product.organization_id)
