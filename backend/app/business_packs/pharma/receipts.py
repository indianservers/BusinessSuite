"""Atomic creation-only receipt into canonical batch and warehouse stock.

No existing lot adoption, manual available quantity, generic SQL or master edit
permission is exposed. Existing native SRM uses server date.today for stock dates;
this command follows that convention, explicitly blocking expiry on that date.
"""
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from fastapi import HTTPException
from sqlalchemy import select,inspect
from app.apps.srm.models import SRMProduct,SRMWarehouse,SRMInventoryBatch,SRMInventoryBalance,SRMInventoryMovement
from app.apps.srm.service_checkout import _authority,_source_scope
from app.apps.srm.stock_resource import _native_branch,_write_quantity_cache
from app.business_packs.models import PackRecordOwnership
from .models import MODELS,PackBatchAvailability,PharmaBatchReceipt
from .schemas import ReceiptInput


def fail(message,code=403):raise HTTPException(code,message)


def authority(db,actor,capability='batches.receive',*,write=True):
    # Reject an unrelated selected pack before probing Pharma/native schemas.
    # The native authority check below still independently verifies permissions.
    installed=db.info.get('business_pack_scope')
    if installed is None or installed.pack_key!='pharma' or 'pharma.'+capability not in installed.capabilities:
        fail('Select an authorized Pharma context for this operation')
    if not write:
        from app.apps.srm.services.commercial import require
        require(actor,'srm_view','srm_manage','srm_admin')
    company,branch,scope=_authority(db,actor,order=write,write=write)
    if scope is None or scope.pack_key!='pharma' or 'pharma.'+capability not in scope.capabilities:
        fail('Select an authorized Pharma context for this operation')
    installed=db.info.get('business_pack_scope')
    if installed is None or installed!=scope:fail('Verified Pharma request scope changed')
    scope=installed
    from app.business_packs.native_policy import native_srm_policy
    if db.info.get('business_pack_policy')!=native_srm_policy('pharma').policy:fail('Audited Pharma isolation adapter is not installed',503)
    inspector=inspect(db.connection())
    if not all(inspector.has_table(model.__tablename__) for model in MODELS):fail('Install the Pharma stock extension first',503)
    return company,branch,scope


def _resources(db,scope,product_id,warehouse_id):
    company,branch=scope.company_id,scope.branch_id
    p=SRMProduct.__table__;w=SRMWarehouse.__table__
    product=db.connection().execute(select(p.c.id,p.c.active,p.c.deleted_at,p.c.product_type,p.c.track_inventory,
        p.c.batch_tracking,p.c.serial_tracking,p.c.expiry_tracking,p.c.metadata_json).where(p.c.id==product_id,p.c.organization_id==company).with_for_update()).mappings().first()
    if product is None:fail('Eligible medicine is unavailable',404)
    _source_scope(db,scope,company,branch,SRMProduct,product_id,master=True)
    from .reads import workspace_bound
    if db.connection().scalar(select(workspace_bound(db,company,product_id))):fail('Workspace offerings are not available for Pharma lot receipts',409)
    from app.shared.catalog_branches import is_available
    from types import SimpleNamespace
    if not product['active'] or product['deleted_at'] is not None or not is_available(SimpleNamespace(metadata_json=product['metadata_json']),branch):fail('Medicine is unavailable in this branch',409)
    if (product['product_type'] or '').lower() in {'service','services'} or not product['track_inventory'] or not product['batch_tracking'] or not product['expiry_tracking'] or product['serial_tracking']:
        fail('Configure a physical batch-and-expiry tracked medicine; serial tracking is unsupported',409)
    warehouse=db.connection().execute(select(w.c.id).where(w.c.id==warehouse_id,w.c.organization_id==company,w.c.active.is_(True)).with_for_update()).first()
    if warehouse is None:fail('Eligible warehouse is unavailable',404)
    _source_scope(db,scope,company,branch,SRMWarehouse,warehouse_id,master=True)
    _native_branch(db,w.name,warehouse_id,company,branch)
    return product


def _result(row,db,scope):
    _source_scope(db,scope,row.organization_id,row.branch_id,PharmaBatchReceipt,row.id)
    if row.movement_id is None:fail('Receipt has not completed',409)
    movement=db.get(SRMInventoryMovement,row.movement_id)
    if movement is None:fail('Receipt stock movement is unavailable',409)
    _source_scope(db,scope,row.organization_id,row.branch_id,SRMInventoryMovement,movement.id)
    if (movement.organization_id,movement.product_id,movement.warehouse_id,movement.quantity_in,movement.quantity_out,movement.created_by,movement.movement_type)!=(
        row.organization_id,row.product_id,row.warehouse_id,row.quantity,0,row.created_by,'pharma_receipt'):fail('Receipt stock provenance differs',409)
    if movement.reference_number!='PHARMA-'+str(row.id) or movement.movement_date!=row.received_date or movement.rate!=row.unit_cost:
        fail('Receipt stock source reference differs',409)
    return {'id':row.id,'batch_id':row.batch_id,'movement_id':row.movement_id,'batch_number':row.batch_number,
        'product_id':row.product_id,'warehouse_id':row.warehouse_id,'quantity':str(row.quantity),'expiry_date':row.expiry_date.isoformat(),'state':'committed'}


def create(data,db,actor,*,commit=True):
    data=ReceiptInput.model_validate(data.model_dump())
    company,branch,scope=authority(db,actor)
    from app.apps.srm.services.commercial import lock_tenant
    lock_tenant(db,actor)
    if authority(db,actor)!=(company,branch,scope):fail('Pharma receipt authorization changed')
    fingerprint=sha256(json.dumps(data.model_dump(mode='json'),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    prior=db.query(PharmaBatchReceipt).filter_by(organization_id=company,branch_id=branch,pack_context_id=scope.context_id,request_key=str(data.request_key)).one_or_none()
    if prior is not None:
        if prior.created_by!=actor.id or prior.request_sha256!=fingerprint:fail('Receipt request key was already used for another command',409)
        return _result(prior,db,scope)
    with db.begin_nested():
        if data.received_date>date.today() or data.expiry_date<=date.today():fail('Receipt date cannot be future and expiry must follow the current stock date',422)
        _resources(db,scope,data.product_id,data.warehouse_id)
        batch=SRMInventoryBatch.__table__;balance=SRMInventoryBalance.__table__
        # Batch uniqueness is company/product/number in the native schema. A
        # duplicate remains a generic conflict even if its private context differs.
        if db.connection().scalar(select(batch.c.id).where(batch.c.organization_id==company,batch.c.product_id==data.product_id,batch.c.batch_number==data.batch_number)):
            fail('Batch number already exists for this product; this command cannot adopt or top up an existing lot',409)
        current=db.connection().execute(select(balance.c.id,balance.c.quantity,balance.c.average_cost).where(balance.c.organization_id==company,
            balance.c.product_id==data.product_id,balance.c.warehouse_id==data.warehouse_id).with_for_update()).first()
        if current is not None:
            anchor=PackRecordOwnership.__table__
            if db.connection().scalar(select(anchor.c.id).where(anchor.c.resource_table==balance.name,anchor.c.resource_key==str(current.id))):fail('Canonical stock cannot adopt a privately owned balance')
        batch_id=db.connection().execute(batch.insert().values(organization_id=company,product_id=data.product_id,warehouse_id=data.warehouse_id,
            batch_number=data.batch_number,manufacture_date=data.manufacture_date,expiry_date=data.expiry_date,received_date=data.received_date,
            quantity=data.quantity,available_quantity=data.quantity,unit_cost=data.unit_cost,status='available',created_by=actor.id)).inserted_primary_key[0]
        # This row was created here after the canonical warehouse branch proof;
        # native FK guards require its own creation-only ownership anchor too.
        from app.branches.models import BranchOwnership
        native=BranchOwnership.__table__
        db.connection().execute(native.insert().values(company_id=company,branch_id=branch,resource_table=batch.name,
            resource_key=str(batch_id),source='pharma-batch-created'))
        availability=PackBatchAvailability.__table__
        db.connection().execute(availability.insert().values(organization_id=company,branch_id=branch,pack_context_id=scope.context_id,batch_id=batch_id,active=True))
        row=PharmaBatchReceipt(organization_id=company,branch_id=branch,pack_context_id=scope.context_id,request_key=str(data.request_key),request_sha256=fingerprint,
            created_by=actor.id,product_id=data.product_id,warehouse_id=data.warehouse_id,batch_id=batch_id,quantity=data.quantity,unit_cost=data.unit_cost,
            batch_number=data.batch_number,manufacture_date=data.manufacture_date,expiry_date=data.expiry_date,received_date=data.received_date)
        from .references import creation_plan
        with creation_plan(db,scope,row):
            db.add(row);db.flush()
            old_quantity=Decimal(current.quantity or 0) if current else Decimal(0)
            if old_quantity<0:fail('Canonical stock requires reconciliation before receipt',409)
            new_quantity=old_quantity+data.quantity
            if new_quantity>=Decimal('100000000000'):fail('Receipt exceeds native stock quantity capacity',422)
            average=((old_quantity*Decimal(current.average_cost or 0) if current else Decimal(0))+data.quantity*data.unit_cost)/new_quantity
            if current:
                changed=db.connection().execute(balance.update().where(balance.c.id==current.id,balance.c.quantity==current.quantity).values(quantity=new_quantity,average_cost=average))
                if changed.rowcount!=1:fail('Canonical stock changed; retry receipt',409)
            else:db.connection().execute(balance.insert().values(organization_id=company,product_id=data.product_id,warehouse_id=data.warehouse_id,quantity=new_quantity,average_cost=average))
            from app.apps.srm.services.commercial_numbering import reserve_number
            movement=SRMInventoryMovement(organization_id=company,movement_number=reserve_number(db,SRMInventoryMovement,'INV','movement_number',company,actor=actor),
                movement_type='pharma_receipt',movement_date=data.received_date,product_id=data.product_id,warehouse_id=data.warehouse_id,
                quantity_in=data.quantity,quantity_out=Decimal(0),rate=data.unit_cost,value=data.quantity*data.unit_cost,reference_number='PHARMA-'+str(row.id),
                notes='Pharma batch receipt',created_by=actor.id)
            movement._suite_source_record=row
            db.add(movement);db.flush();row.movement_id=movement.id;db.flush()
            _write_quantity_cache(db,data.product_id,company)
            result=_result(row,db,scope)
    if commit:db.commit()
    return result
