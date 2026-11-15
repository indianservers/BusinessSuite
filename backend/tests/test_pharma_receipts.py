"""Production Pharma receipt boundary and canonical inventory transaction."""
from datetime import date,timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from fastapi import HTTPException
from app.apps.srm.models import SRMProduct,SRMInventoryBatch,SRMInventoryBalance,SRMInventoryMovement
from app.business_packs.models import PackMasterAvailability
from app.business_packs.pharma.models import PharmaBatchReceipt,PackBatchAvailability
from app.business_packs.pharma.schemas import ReceiptInput
from app.business_packs.pharma.receipts import create
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_business_pack_http_integration import native_actor,grant
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_srm_native_transaction_operations import native_writer

BASE='/api/v1/srm/pharma/batch-receipts'


@pytest.fixture
def pharma(client,db,scenario):
    _,branch,catalog,_=scenario
    headers,actor=native_actor(db,branch)
    context,_=grant(db,actor,branch,'pharma','pharmacy_manager')
    product=catalog[2][0];warehouse=catalog[1]
    db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id==product).values(batch_tracking=True,expiry_tracking=True))
    for table,ident in [('srm_products',product),('srm_warehouses',warehouse),('crm_companies',101)]:
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context.id,resource_table=table,resource_key=str(ident),active=True))
    db.commit()
    return {**headers,'X-Suite-Pack-Context':str(context.id)},actor,branch,context.id,product,warehouse


def command(case):
    return {'request_key':str(uuid4()),'product_id':case[4],'warehouse_id':case[5],'batch_number':'LOT-'+uuid4().hex,
        'received_date':date.today().isoformat(),'expiry_date':(date.today()+timedelta(days=365)).isoformat(),
        'quantity':'2.500','unit_cost':'12.0000'}


def balance(db,case):
    t=SRMInventoryBalance.__table__
    return db.connection().scalar(select(t.c.quantity).where(t.c.organization_id==1,t.c.product_id==case[4],t.c.warehouse_id==case[5]))


def counts(db):
    return tuple(db.connection().scalar(select(func.count()).select_from(m.__table__)) for m in (PharmaBatchReceipt,SRMInventoryBatch,SRMInventoryMovement,PackBatchAvailability))


def test_actual_http_receipt_updates_batch_balance_movement_and_replays_once(client,db,pharma):
    data=command(pharma);before=balance(db,pharma)
    response=client.post(BASE,headers=pharma[0],json=data)
    assert response.status_code==201,response.text
    result=response.json();assert result['state']=='committed'
    assert balance(db,pharma)==before+Decimal('2.5')
    lot=db.get(SRMInventoryBatch,result['batch_id'])
    assert lot.available_quantity==lot.quantity==Decimal('2.5')
    movement=db.get(SRMInventoryMovement,result['movement_id'])
    assert movement.quantity_in==Decimal('2.5') and movement.quantity_out==0
    after=counts(db)
    replay=client.post(BASE,headers=pharma[0],json=data)
    assert replay.status_code==201,replay.text
    assert replay.json()==result and counts(db)==after
    changed=client.post(BASE,headers=pharma[0],json={**data,'quantity':'3'})
    assert changed.status_code==409,changed.text
    assert balance(db,pharma)==before+Decimal('2.5') and counts(db)==after


@pytest.mark.parametrize('fault',['expired','future_receipt','zero','nan','unknown','serial','unavailable_product','unavailable_warehouse'])
def test_receipt_invalid_resources_dates_and_amounts_have_no_side_effect(client,db,pharma,fault):
    data=command(pharma)
    if fault=='expired':data['expiry_date']=date.today().isoformat()
    elif fault=='future_receipt':data['received_date']=(date.today()+timedelta(days=1)).isoformat()
    elif fault=='zero':data['quantity']='0'
    elif fault=='nan':data['quantity']='NaN'
    elif fault=='unknown':data['metadata_json']={'adopt':True}
    elif fault=='serial':db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id==pharma[4]).values(serial_tracking=True));db.commit()
    else:
        table='srm_products' if fault=='unavailable_product' else 'srm_warehouses'
        row=db.query(PackMasterAvailability).filter_by(context_id=pharma[3],resource_table=table).one();row.active=False;db.commit()
    before=counts(db);stock=balance(db,pharma)
    response=client.post(BASE,headers=pharma[0],json=data)
    assert response.status_code in (403,409,422),response.text
    assert counts(db)==before and balance(db,pharma)==stock


def test_existing_lot_cannot_be_adopted_or_topped_up(client,db,pharma):
    data=command(pharma)
    first=client.post(BASE,headers=pharma[0],json=data);assert first.status_code==201,first.text
    before=counts(db)
    duplicate=client.post(BASE,headers=pharma[0],json={**data,'request_key':str(uuid4())})
    assert duplicate.status_code==409,duplicate.text
    assert counts(db)==before


def test_late_movement_failure_rolls_back_batch_availability_and_stock(client,db,pharma,monkeypatch):
    import app.apps.srm.services.commercial_numbering as numbering
    before=counts(db);stock=balance(db,pharma)
    def conflict(*args,**kwargs):raise HTTPException(409,'Native numbering conflict')
    monkeypatch.setattr(numbering,'reserve_number',conflict)
    response=client.post(BASE,headers=pharma[0],json=command(pharma))
    assert response.status_code==409,response.text
    assert counts(db)==before and balance(db,pharma)==stock


def test_outer_rollback_restores_receipt_resources(db,pharma):
    before=counts(db);stock=balance(db,pharma)
    with native_writer(db,pharma[1],pharma[2]):
        scope=resolve_context(db,pharma[1],db.info['branch_context'],pharma[3]);cleanup=install(db,scope,policy=native_srm_policy('pharma').policy)
        try:
            create(ReceiptInput.model_validate(command(pharma)),db,pharma[1],commit=False)
            assert balance(db,pharma)==stock+Decimal('2.5')
            db.rollback()
            assert balance(db,pharma)==stock and counts(db)==before
        finally:cleanup()


def test_cashier_does_not_gain_receiving_from_native_administrator_rights(client,db,pharma):
    from app.business_packs.models import PackUserGrant
    role=db.query(PackUserGrant).filter_by(context_id=pharma[3],user_id=pharma[1].id).one()
    role.role='cashier';db.commit()
    before=counts(db)
    response=client.post(BASE,headers=pharma[0],json=command(pharma))
    assert response.status_code==403,response.text
    assert counts(db)==before


def test_canonical_batch_mapper_is_not_shared_by_receipt_adapter(client,db,pharma):
    response=client.post(BASE,headers=pharma[0],json=command(pharma));assert response.status_code==201,response.text
    with native_writer(db,pharma[1],pharma[2]):
        scope=resolve_context(db,pharma[1],db.info['branch_context'],pharma[3]);cleanup=install(db,scope,policy=native_srm_policy('pharma').policy)
        try:
            with pytest.raises(HTTPException) as denied:db.query(SRMInventoryBatch).all()
            assert denied.value.status_code==403
            with pytest.raises(HTTPException):db.query(PackBatchAvailability).all()
        finally:cleanup()


def test_native_stock_numeric_capacity_is_rejected_without_partial_receipt(client,db,pharma):
    data=command(pharma);before=counts(db)
    response=client.post(BASE,headers=pharma[0],json={**data,'quantity':'99999999999.999','unit_cost':'9999999999.9999'})
    assert response.status_code==422,response.text
    assert counts(db)==before
    balance_table=SRMInventoryBalance.__table__
    db.connection().execute(balance_table.update().where(balance_table.c.product_id==pharma[4],balance_table.c.warehouse_id==pharma[5]).values(quantity=Decimal('99999999999.999')));db.commit()
    response=client.post(BASE,headers=pharma[0],json=data)
    assert response.status_code==422,response.text
    assert counts(db)==before and balance(db,pharma)==Decimal('99999999999.999')
