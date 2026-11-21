"""Minimal batch/resource projections; no canonical batch ORM grant."""
from datetime import date
from decimal import Decimal
from sqlalchemy import select,func,exists,String,literal,inspect
from app.apps.srm.models import SRMProduct,SRMWarehouse,SRMInventoryBatch,SRMInventoryBalance
from app.business_packs.models import PackMasterAvailability
from app.branches.models import BranchOwnership
from .models import PackBatchAvailability
from .receipts import authority


def workspace_bound(db,company,product_id):
    from app.shared.catalog_models import CatalogDetails
    d=CatalogDetails.__table__
    return exists(select(d.c.id).where(d.c.organization_id==company,d.c.product_id==product_id,d.c.service_id.is_(None),d.c.workspace_id.is_not(None)))


def eligible_quantity(db,scope,product_id,warehouse_id):
    b=SRMInventoryBatch.__table__;a=PackBatchAvailability.__table__;n=BranchOwnership.__table__
    value=db.connection().scalar(select(func.coalesce(func.sum(b.c.available_quantity),0)).select_from(b.join(a,a.c.batch_id==b.c.id).join(n,
        (n.c.resource_table==b.name)&(n.c.resource_key==b.c.id.cast(String)))).where(
        b.c.organization_id==scope.company_id,b.c.product_id==product_id,b.c.warehouse_id==warehouse_id,b.c.status=='available',
        b.c.expiry_date>date.today(),b.c.available_quantity>0,a.c.organization_id==scope.company_id,a.c.branch_id==scope.branch_id,
        a.c.pack_context_id==scope.context_id,a.c.active.is_(True),n.c.company_id==scope.company_id,n.c.branch_id==scope.branch_id))
    return Decimal(value or 0)


def _available(table,scope):
    a=PackMasterAvailability.__table__
    return exists(select(a.c.id).where(a.c.company_id==scope.company_id,a.c.branch_id==scope.branch_id,a.c.context_id==scope.context_id,
        a.c.resource_table==table.name,a.c.resource_key==table.c.id.cast(String),a.c.active.is_(True)))


def options(db,actor,*,search='',after=0,limit=30):
    company,branch,scope=authority(db,actor,'batches.view',write=False)
    from app.shared.catalog_branches import availability_clause
    p=SRMProduct.__table__;w=SRMWarehouse.__table__;n=BranchOwnership.__table__
    query=select(p.c.id,p.c.item_name,p.c.sku).where(p.c.organization_id==company,p.c.id>after,p.c.active.is_(True),p.c.deleted_at.is_(None),
        p.c.product_type.not_in(['service','services']),p.c.track_inventory.is_(True),p.c.batch_tracking.is_(True),p.c.expiry_tracking.is_(True),p.c.serial_tracking.is_(False),
        _available(p,scope),availability_clause(SRMProduct,branch),~workspace_bound(db,company,p.c.id))
    if search:query=query.where(p.c.item_name.contains(search,autoescape=True)|p.c.sku.contains(search,autoescape=True))
    products=db.connection().execute(query.order_by(p.c.id).limit(limit+1)).mappings().all()
    warehouses=db.connection().execute(select(w.c.id,w.c.warehouse_name).join(n,(n.c.resource_table==w.name)&(n.c.resource_key==w.c.id.cast(String))).where(
        w.c.organization_id==company,w.c.active.is_(True),_available(w,scope),n.c.company_id==company,n.c.branch_id==branch).order_by(w.c.id).limit(201)).mappings().all()
    # The finite warehouse chooser must not silently hide valid destinations.
    from .receipts import fail
    if len(warehouses)>200:fail('This branch exceeds the supported warehouse chooser capacity',409)
    return {'products':[dict(row) for row in products[:limit]],'has_more':len(products)>limit,'next':products[limit-1]['id'] if len(products)>limit else None,
        'warehouses':[dict(row) for row in warehouses],'can_receive':scope.writable and 'pharma.batches.receive' in scope.capabilities,
        'can_recall':scope.writable and 'pharma.recalls.manage' in scope.capabilities and _recall_ready(db)}


def _recall_ready(db):
    from .recall_models import MODELS
    return all(inspect(db.connection()).has_table(model.__tablename__) for model in MODELS)


def batches(db,actor,*,search='',after=0,limit=30):
    company,branch,scope=authority(db,actor,'batches.view',write=False)
    b=SRMInventoryBatch.__table__;a=PackBatchAvailability.__table__;p=SRMProduct.__table__;w=SRMWarehouse.__table__;n=BranchOwnership.__table__
    from app.shared.catalog_branches import availability_clause
    from .recall_models import PharmaBatchControl
    control=PharmaBatchControl.__table__
    revision=func.coalesce(select(control.c.revision).where(control.c.organization_id==company,control.c.batch_id==b.c.id).scalar_subquery(),0) if _recall_ready(db) else literal(0)
    query=select(b.c.id,b.c.batch_number,b.c.product_id,b.c.warehouse_id,b.c.manufacture_date,b.c.expiry_date,b.c.received_date,b.c.quantity,b.c.available_quantity,b.c.status,b.c.selling_price,
        p.c.item_name,w.c.warehouse_name,revision.label('state_revision')).select_from(b.join(a,a.c.batch_id==b.c.id).join(p,p.c.id==b.c.product_id).join(w,w.c.id==b.c.warehouse_id).join(n,
        (n.c.resource_table==b.name)&(n.c.resource_key==b.c.id.cast(String)))).where(b.c.organization_id==company,b.c.id>after,a.c.organization_id==company,
        a.c.branch_id==branch,a.c.pack_context_id==scope.context_id,a.c.active.is_(True),p.c.organization_id==company,w.c.organization_id==company,
        n.c.company_id==company,n.c.branch_id==branch,_available(p,scope),_available(w,scope),availability_clause(SRMProduct,branch),~workspace_bound(db,company,p.c.id))
    if search:query=query.where(b.c.batch_number.contains(search,autoescape=True)|p.c.item_name.contains(search,autoescape=True))
    rows=db.connection().execute(query.order_by(b.c.id).limit(limit+1)).mappings().all()
    return {'items':[{**dict(row),'quantity':str(row['quantity']),'available_quantity':str(row['available_quantity']),
        'fefo_eligible':row['status']=='available' and row['expiry_date'] is not None and row['expiry_date']>date.today() and row['available_quantity']>0} for row in rows[:limit]],
        'has_more':len(rows)>limit,'next':rows[limit-1]['id'] if len(rows)>limit else None}
