from datetime import date,timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select
from fastapi import HTTPException
from app.apps.srm.models import SRMInventoryBatch,SRMPOSSession,SRMSalesOrder,SRMInvoice,SRMReceipt
from app.business_packs.pharma.models import PharmaBatchAllocation
from app.business_packs.pharma.fefo import split
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_pharma_receipts import pharma,command,balance,counts,BASE
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_srm_native_transaction_operations import native_writer


@pytest.fixture
def lots(client,db,pharma):
    from app.business_packs.models import PackUserGrant
    role=db.query(PackUserGrant).filter_by(context_id=pharma[3],user_id=pharma[1].id).one()
    role.role='business_owner';db.commit()
    results=[]
    for days,quantity in [(90,'2'),(30,'3')]:
        payload={**command(pharma),'quantity':quantity,'expiry_date':(date.today()+timedelta(days=days)).isoformat()}
        response=client.post(BASE,headers=pharma[0],json=payload);assert response.status_code==201,response.text
        results.append(response.json())
    with native_writer(db,pharma[1],pharma[2]):
        scope=resolve_context(db,pharma[1],db.info['branch_context'],pharma[3]);cleanup=install(db,scope,policy=native_srm_policy('pharma').policy)
        try:
            register=SRMPOSSession(organization_id=1,session_number='PHARMA-'+uuid4().hex,status='open',cashier_user_id=pharma[1].id,created_by=pharma[1].id)
            db.add(register);db.commit();register_id=register.id
        finally:cleanup()
    return pharma,results,register_id


def sale(lots,quantity='4',paid=False):
    case,_,register=lots
    return {'request_id':str(uuid4()),'customer_id':101,'pos_session_id':register,
        'lines':[{'client_line_key':str(uuid4()),'line_kind':'product','product_id':case[4],'quantity':quantity}],
        'payments':[{'payment_key':str(uuid4()),'method':'cash','amount':str(Decimal(quantity)*118)}] if paid else []}


def lot_quantities(db,lots):
    return [db.connection().scalar(select(SRMInventoryBatch.available_quantity).where(SRMInventoryBatch.id==item['batch_id'])) for item in lots[1]]


def test_actual_native_checkout_splits_fefo_and_replays_issued_lots(client,db,lots):
    case,receipts,_=lots;payload=sale(lots,paid=True);stock=balance(db,case)
    response=client.post('/api/v1/srm/service-checkout',headers=case[0],json=payload)
    assert response.status_code==201,response.text
    result=response.json()
    assert result['invoice']['paid']=='472.00' and result['invoice']['balance']=='0.00'
    assert lot_quantities(db,lots)==[Decimal('1'),Decimal('0')]
    assert balance(db,case)==stock-4
    allocations=db.query(PharmaBatchAllocation).order_by(PharmaBatchAllocation.id).all()
    assert [(r.batch_id,r.quantity) for r in allocations]==[(receipts[1]['batch_id'],Decimal('3')),(receipts[0]['batch_id'],Decimal('1'))]
    from app.apps.srm.service_checkout_models import POSCheckoutLine
    source=db.query(POSCheckoutLine).filter_by(checkout_id=result['id']).one()
    assert all(r.sales_order_line_id==source.sales_order_line_id for r in allocations)
    assert source.invoice_line_id is not None
    assert [(a['batch_id'],Decimal(a['quantity'])) for a in result['lines'][0]['batch_allocations']]==[(receipts[1]['batch_id'],Decimal('3')),(receipts[0]['batch_id'],Decimal('1'))]
    replay=client.post('/api/v1/srm/service-checkout',headers=case[0],json=payload)
    assert replay.status_code==201,replay.text
    assert replay.json()==result and lot_quantities(db,lots)==[Decimal('1'),Decimal('0')]
    assert db.query(PharmaBatchAllocation).count()==2


@pytest.mark.parametrize('state',['quarantined','recalled','expired','unavailable'])
def test_non_sellable_lots_cannot_be_replaced_by_unattributed_aggregate_stock(client,db,lots,state):
    from app.business_packs.pharma.models import PackBatchAvailability
    case=lots[0];first=lots[1][1]['batch_id']
    if state=='unavailable':db.connection().execute(PackBatchAvailability.__table__.update().where(PackBatchAvailability.batch_id==first).values(active=False))
    elif state=='expired':db.connection().execute(SRMInventoryBatch.__table__.update().where(SRMInventoryBatch.id==first).values(expiry_date=date.today()))
    else:db.connection().execute(SRMInventoryBatch.__table__.update().where(SRMInventoryBatch.id==first).values(status=state))
    db.commit();stock=balance(db,case);before=counts(db)
    response=client.post('/api/v1/srm/service-checkout',headers=case[0],json=sale(lots))
    assert response.status_code==409,response.text
    assert balance(db,case)==stock and counts(db)==before and db.query(PharmaBatchAllocation).count()==0


def test_payment_failure_rolls_back_lots_order_invoice_receipt_and_allocations(client,db,lots,monkeypatch):
    import app.apps.srm.api.router as native
    case=lots[0];stock=balance(db,case);before=counts(db)
    def fail(*args,**kwargs):raise HTTPException(409,'Late payment allocation conflict')
    monkeypatch.setattr(native,'allocate_receipt_operation',fail)
    response=client.post('/api/v1/srm/service-checkout',headers=case[0],json=sale(lots,paid=True))
    assert response.status_code==409,response.text
    assert balance(db,case)==stock and counts(db)==before and lot_quantities(db,lots)==[Decimal('2'),Decimal('3')]
    assert db.query(PharmaBatchAllocation).count()==0


def test_fefo_ties_and_current_day_expiry_are_deterministic():
    today=date(2030,1,1)
    def lot(id,expiry,received,status='available'):
        return {'id':id,'expiry_date':expiry,'received_date':received,'available_quantity':Decimal(1),'status':status}
    rows=[lot(3,today+timedelta(days=1),today),lot(2,today+timedelta(days=1),today),lot(1,today,today)]
    assert [r['id'] for r,_ in split(rows,2,today)]==[2,3]
    with pytest.raises(ValueError):split(rows,3,today)
