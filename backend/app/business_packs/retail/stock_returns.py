"""Restore only stock proven to have left through this original sale line."""
from datetime import date
from decimal import Decimal
from sqlalchemy import select,inspect
from app.apps.srm.models import (SRMInventoryBalance,SRMInventoryMovement,SRMProduct,
    SRMWarehouse,SRMPOSReturnLine)
from app.apps.srm.stock_resource import _product,_native_branch,_write_quantity_cache
from app.apps.srm.service_checkout import _source_scope
from app.business_packs.models import PackRecordOwnership
from .accounting import authority,fail
from .models import RetailSaleStockSource


def original(db,scope,checkout_line):
    proof=db.query(RetailSaleStockSource).filter_by(organization_id=scope.company_id,branch_id=scope.branch_id,
        pack_context_id=scope.context_id,sales_order_line_id=checkout_line.sales_order_line_id).one_or_none()
    if proof is None:fail('This sale predates durable Retail stock provenance and cannot be returned through this workflow',409)
    _source_scope(db,scope,scope.company_id,scope.branch_id,RetailSaleStockSource,proof.id)
    movement=db.get(SRMInventoryMovement,proof.movement_id)
    if movement is None:fail('Original stock issuance is unavailable',409)
    _source_scope(db,scope,scope.company_id,scope.branch_id,SRMInventoryMovement,movement.id)
    _native_branch(db,SRMInventoryMovement.__tablename__,movement.id,scope.company_id,scope.branch_id)
    if (proof.product_id,proof.quantity,movement.product_id,movement.warehouse_id,movement.quantity_out,
            movement.quantity_in,movement.movement_type,movement.organization_id)!=(
            checkout_line.product_id,checkout_line.quantity,proof.product_id,proof.warehouse_id,proof.quantity,
            0,'pos_sale',scope.company_id):fail('Original stock issuance differs from its durable sale provenance',409)
    return proof


def restore(db,actor,scope,native_line,proof,currency):
    authority(db,actor,scope)
    state=inspect(native_line)
    if type(native_line) is not SRMPOSReturnLine or state.session is not db or not state.persistent:fail()
    _source_scope(db,scope,scope.company_id,scope.branch_id,SRMPOSReturnLine,native_line.id)
    _native_branch(db,SRMPOSReturnLine.__tablename__,native_line.id,scope.company_id,scope.branch_id)
    if (native_line.sales_order_line_id,native_line.product_id,native_line.warehouse_id)!=(
            proof.sales_order_line_id,proof.product_id,proof.warehouse_id):fail()
    quantity=Decimal(native_line.quantity)
    if quantity<=0 or quantity!=quantity.quantize(Decimal('.01')):fail('Native physical return quantity supports at most two decimal places',422)
    product,physical=_product(db,proof.product_id,scope.company_id,scope.branch_id,scope,currency)
    if not physical:fail('The original item is no longer configured as supported physical stock',409)
    warehouse=SRMWarehouse.__table__
    found=db.connection().execute(select(warehouse.c.id).where(warehouse.c.id==proof.warehouse_id,
        warehouse.c.organization_id==scope.company_id,warehouse.c.active.is_(True)).with_for_update()).first()
    if found is None:fail('The original stock warehouse is inactive or unavailable',409)
    _source_scope(db,scope,scope.company_id,scope.branch_id,SRMWarehouse,proof.warehouse_id,master=True)
    _native_branch(db,warehouse.name,proof.warehouse_id,scope.company_id,scope.branch_id)
    balance=SRMInventoryBalance.__table__
    current=db.connection().execute(select(balance.c.id,balance.c.quantity).where(
        balance.c.organization_id==scope.company_id,balance.c.product_id==proof.product_id,
        balance.c.warehouse_id==proof.warehouse_id).with_for_update()).first()
    if current is None:fail('Original canonical stock balance is unavailable',409)
    anchor=PackRecordOwnership.__table__
    if db.connection().scalar(select(anchor.c.id).where(anchor.c.resource_table==balance.name,anchor.c.resource_key==str(current.id))):fail()
    changed=db.connection().execute(balance.update().where(balance.c.id==current.id,balance.c.quantity==current.quantity).values(quantity=Decimal(current.quantity)+quantity))
    if changed.rowcount!=1:fail('Original warehouse stock changed; retry the return',409)
    from app.apps.srm.services.commercial_numbering import reserve_number
    issued=db.get(SRMInventoryMovement,proof.movement_id)
    if issued is None:fail('Original issued stock movement is unavailable',409)
    movement=SRMInventoryMovement(organization_id=scope.company_id,
        movement_number=reserve_number(db,SRMInventoryMovement,'INV','movement_number',scope.company_id,actor=actor),
        movement_type='pos_return',movement_date=date.today(),product_id=proof.product_id,warehouse_id=proof.warehouse_id,
        quantity_in=quantity,quantity_out=Decimal(0),rate=issued.rate,value=quantity*Decimal(issued.rate),
        reference_number='RETURN-'+str(native_line.return_id),notes='Original-sale Retail stock return',created_by=actor.id)
    movement._suite_source_record=native_line
    db.add(movement);db.flush()
    _write_quantity_cache(db,proof.product_id,scope.company_id)
    return movement
