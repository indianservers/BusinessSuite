from decimal import Decimal
from uuid import uuid4
import pytest
from app.access.models import AccessPolicy
from app.models.user import Permission
from app.apps.srm.models import SRMInventoryBalance,SRMInventoryBatch,SRMInventoryMovement,SRMPOSCashMovement
from app.apps.fam.models import FAMVoucher
from app.business_packs.pharma.return_models import PharmaReturn,PharmaReturnLine,PharmaReturnLot
from tests.test_pharma_fefo import lots,sale,lot_quantities
from tests.test_pharma_receipts import pharma
from tests.test_service_checkout import scenario,catalog,directory_identity
from tests.test_retail_return_http import post_original

BASE='/api/v1/srm/pharma/returns'

@pytest.fixture
def original(client,db,lots,request):
    case=lots[0];actor=case[1]
    permission=db.query(Permission).filter_by(name='fam_admin').one_or_none()
    if permission is None:
        permission=Permission(name='fam_admin',description='Native Accounting administrator');db.add(permission);db.flush()
    actor.role.permissions.append(permission)
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=actor.id).one()
    policy.grants={**policy.grants,'fam':{'enabled':True,'permissions':['fam_admin'],'actions':['view','create','edit','approve'],'scope':'organization'}}
    db.commit()
    payload=sale(lots,paid=True)
    if getattr(request,'param','cash')=='card':
        payload['payments'][0].update(method='card',reference='ACTUAL-CARD-CAPTURE')
    response=client.post('/api/v1/srm/service-checkout',headers=case[0],json=payload)
    assert response.status_code==201,response.text
    checkout=response.json()
    discovered=client.get(BASE+f'/sales/{checkout["id"]}/lots',headers=case[0])
    assert discovered.status_code==200,discovered.text
    retail_compatible=(case[0],actor,case[2],case[3],checkout,lots[2],case[4],case[5])
    return lots,checkout,discovered.json()['lots'],retail_compatible

def command(original):
    lots,checkout,allocations,_=original
    return {'request_key':str(uuid4()),'checkout_id':checkout['id'],'expected_checkout_revision':checkout['revision'],
        'lots':[{'allocation_id':allocations[0]['allocation_id'],'quantity':'0.001'}],
        'refund':{'method':'cash','session_id':lots[2]},'reason':'Original medicine returned unopened for quarantine'}

def test_paid_original_lot_fraction_quarantines_and_posts_native_refund_once(client,db,original):
    lots,checkout,allocations,accounting=original
    post_original(db,accounting)
    before_lots=lot_quantities(db,lots)
    balance=db.query(SRMInventoryBalance).filter_by(product_id=lots[0][4],warehouse_id=lots[0][5]).one()
    physical=balance.quantity;vouchers=db.query(FAMVoucher).count()
    body=command(original)
    response=client.post(BASE,headers=lots[0][0],json=body)
    assert response.status_code==201,response.text
    result=response.json()
    assert Decimal(result['refund_amount'])==Decimal('.12')
    assert result['state']=='committed' and result['accounting']['credit_note']['status']=='posted'
    assert result['accounting']['refund']['status']=='posted'
    assert db.query(PharmaReturn).count()==db.query(PharmaReturnLine).count()==db.query(PharmaReturnLot).count()==1
    assert db.query(FAMVoucher).count()==vouchers+2
    returned=db.query(PharmaReturnLot).one();batch=db.get(SRMInventoryBatch,returned.quarantine_batch_id)
    assert batch.status=='quarantined' and batch.available_quantity==0 and batch.quantity==Decimal('.001')
    assert batch.id!=returned.original_batch_id
    db.expire(balance);assert balance.quantity==physical+Decimal('.001')
    assert lot_quantities(db,lots)==before_lots
    assert db.query(SRMInventoryMovement).filter_by(movement_type='pharma_return_quarantine').count()==1
    assert db.query(SRMPOSCashMovement).filter_by(movement_type='cash_out').count()==1
    replay=client.post(BASE,headers=lots[0][0],json=body)
    assert replay.status_code==201 and replay.json()==result,replay.text
    assert db.query(FAMVoucher).count()==vouchers+2
    read=client.get(BASE+'/'+str(result['id']),headers=lots[0][0])
    assert read.status_code==200 and read.json()==result,read.text
    recovered=client.get(BASE+'/requests/'+body['request_key'],headers=lots[0][0])
    assert recovered.status_code==200 and recovered.json()=={'state':'committed','result':result},recovered.text

def test_unposted_native_sale_has_no_return_or_quarantine_effect(client,db,original):
    before=db.query(SRMInventoryBatch).count(),db.query(SRMInventoryMovement).count()
    response=client.post(BASE,headers=original[0][0][0],json=command(original))
    assert response.status_code==409,response.text
    assert 'Accounting' in response.text
    assert db.query(PharmaReturn).count()==db.query(PharmaReturnLine).count()==db.query(PharmaReturnLot).count()==0
    assert (db.query(SRMInventoryBatch).count(),db.query(SRMInventoryMovement).count())==before

def test_partial_then_remaining_original_lots_preserves_last_cents_and_caps(client,db,original):
    post_original(db,original[3]);headers=original[0][0][0]
    first=client.post(BASE,headers=headers,json=command(original))
    assert first.status_code==201,first.text
    rest=command(original);rest['lots']=[{'allocation_id':row['allocation_id'],
        'quantity':str(Decimal(row['sold_quantity'])-(Decimal('.001') if index==0 else 0))} for index,row in enumerate(original[2])]
    second=client.post(BASE,headers=headers,json=rest)
    assert second.status_code==201,second.text
    assert Decimal(first.json()['refund_amount'])+Decimal(second.json()['refund_amount'])==472
    assert db.query(PharmaReturn).count()==2
    excess=client.post(BASE,headers=headers,json=command(original))
    assert excess.status_code==409,excess.text
    assert db.query(PharmaReturn).count()==2
    changed=client.post(BASE,headers=headers,json={**rest,'reason':'Another reason for the same request'})
    assert changed.status_code==409,changed.text

@pytest.mark.parametrize('failure',['second_lot','late_pv','after_cash','forged_running_balance'])
def test_late_stock_and_native_financial_failures_roll_back_every_source(client,db,original,monkeypatch,failure):
    from fastapi import HTTPException
    from app.apps.fam.models import FAMLedgerEntry,FAMLedger
    from app.apps.srm.models import SRMPOSReturn,SRMPOSReturnLine
    from app.business_packs.pharma import return_stock,returns
    from app.business_packs.retail import accounting
    from app.apps.fam.api import router as native
    post_original(db,original[3]);body=command(original)
    models=(PharmaReturn,PharmaReturnLine,PharmaReturnLot,SRMPOSReturn,SRMPOSReturnLine,
        SRMInventoryBatch,SRMInventoryMovement,SRMPOSCashMovement,FAMVoucher,FAMLedgerEntry)
    before={m:db.query(m).count() for m in models}
    balances={r.id:(r.current_balance_dr,r.current_balance_cr) for r in db.query(FAMLedger)}
    stock=db.query(SRMInventoryBalance).filter_by(product_id=original[0][0][4],warehouse_id=original[0][0][5]).one().quantity
    if failure=='second_lot':
        body['lots']=[{'allocation_id':row['allocation_id'],'quantity':row['sold_quantity']} for row in original[2]]
        previous=return_stock.receive;calls=[]
        def receive(*args):
            result=previous(*args);calls.append(1)
            if len(calls)==2:raise HTTPException(409,'Injected late second lot failure')
            return result
        monkeypatch.setattr(return_stock,'receive',receive)
    elif failure=='late_pv':
        previous=native.create_and_post_voucher
        def posted(*args,**kwargs):
            value=previous(*args,**kwargs)
            if args[4]=='PV':raise HTTPException(409,'Injected failure after native refund posting')
            return value
        monkeypatch.setattr(native,'create_and_post_voucher',posted)
    elif failure=='after_cash':
        previous=returns.result
        def completed(*args,**kwargs):
            previous(*args,**kwargs)
            raise HTTPException(409,'Injected failure after completed native sources')
        monkeypatch.setattr(returns,'result',completed)
    else:
        previous=native.apply_ledger_movement
        monkeypatch.setattr(native,'apply_ledger_movement',lambda *args:previous(*args)+1)
    response=client.post(BASE,headers=original[0][0][0],json=body)
    assert response.status_code in (403,409),response.text
    assert all(db.query(model).count()==count for model,count in before.items())
    db.expire_all()
    assert {r.id:(r.current_balance_dr,r.current_balance_cr) for r in db.query(FAMLedger)}==balances
    assert db.query(SRMInventoryBalance).filter_by(product_id=original[0][0][4],warehouse_id=original[0][0][5]).one().quantity==stock
    assert db not in return_stock._ACTIVE and db not in accounting._ACTIVE

@pytest.mark.parametrize('failure',['fam_denied','native_collection_denied','closed_register','canonical_balance_low'])
def test_current_authority_register_and_canonical_integrity_reject_before_refund(client,db,original,failure):
    from app.apps.srm.models import SRMPOSSession
    post_original(db,original[3]);case=original[0][0]
    from app.business_packs.models import PackUserGrant
    assigned=db.query(PackUserGrant).filter_by(context_id=case[3],user_id=case[1].id).one()
    assigned.role='pharmacy_manager';db.commit()
    if failure in ('fam_denied','native_collection_denied'):
        policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=case[1].id).one()
        if failure=='fam_denied':policy.grants={**policy.grants,'fam':{**policy.grants['fam'],'actions':['view']}}
        else:policy.grants={**policy.grants,'srm':{**policy.grants['srm'],'permissions':['srm_manage','srm_invoice_view']}}
    elif failure=='closed_register':
        db.connection().execute(SRMPOSSession.__table__.update().where(SRMPOSSession.id==original[0][2]).values(status='closed'))
    else:
        db.connection().execute(SRMInventoryBalance.__table__.update().where(SRMInventoryBalance.product_id==case[4],
            SRMInventoryBalance.warehouse_id==case[5]).values(quantity=0))
    db.commit()
    before=db.query(FAMVoucher).count(),db.query(SRMInventoryBatch).count(),db.query(SRMInventoryMovement).count()
    response=client.post(BASE,headers=case[0],json=command(original))
    assert response.status_code in (403,409),response.text
    assert db.query(PharmaReturn).count()==db.query(PharmaReturnLot).count()==0
    assert (db.query(FAMVoucher).count(),db.query(SRMInventoryBatch).count(),db.query(SRMInventoryMovement).count())==before

@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef'),('construction','site_engineer')])
def test_other_pack_specialists_cannot_refund_or_read_private_medicine_return(client,db,original,pack,role):
    from tests.test_business_pack_http_integration import grant
    case=original[0][0]
    context,_=grant(db,case[1],case[2],pack,role)
    response=client.post(BASE,headers={**case[0],'X-Suite-Pack-Context':str(context.id)},json=command(original))
    assert response.status_code==403,response.text
    assert 'refund_amount' not in response.text and 'batch_number' not in response.text
    assert db.query(PharmaReturn).count()==0

@pytest.mark.parametrize('original',['card'],indirect=True)
def test_original_card_refund_has_no_drawer_cash_out(client,db,original):
    post_original(db,original[3]);payload=command(original)
    payload['refund'].update(method='card',reference='ACTUAL-REFUND-REFERENCE')
    response=client.post(BASE,headers=original[0][0][0],json=payload)
    assert response.status_code==201,response.text
    assert response.json()['cash_movement_id'] is None
    assert db.query(SRMPOSCashMovement).filter_by(movement_type='cash_out').count()==0
    assert db.query(PharmaReturn).one().payment_reference=='ACTUAL-REFUND-REFERENCE'

@pytest.mark.parametrize('condition',['recalled','expired'])
def test_historical_original_lot_can_only_return_into_quarantine(client,db,original,monkeypatch,condition):
    from datetime import date,timedelta
    from app.business_packs.pharma import return_stock
    post_original(db,original[3]);allocation=original[2][0]
    if condition=='recalled':
        response=client.post('/api/v1/srm/pharma/recalls',headers=original[0][0][0],json={
            'request_key':str(uuid4()),'batch_id':allocation['batch_id'],'expected_batch_revision':0,
            'expected_batch_status':'available','action':'recall','reason':'Actual native original lot recall'})
        assert response.status_code==201,response.text
    else:
        expired_after=date.fromisoformat(allocation['expiry_date'])+timedelta(days=1)
        class StockDate(date):
            @classmethod
            def today(cls):return expired_after
        monkeypatch.setattr(return_stock,'date',StockDate)
    response=client.post(BASE,headers=original[0][0][0],json=command(original))
    assert response.status_code==201,response.text
    returned=db.query(PharmaReturnLot).one();batch=db.get(SRMInventoryBatch,returned.quarantine_batch_id)
    assert batch.status=='quarantined' and batch.available_quantity==0
    if condition=='expired':assert batch.expiry_date<return_stock.date.today()
    else:assert db.get(SRMInventoryBatch,allocation['batch_id']).status=='recalled'


def test_private_stock_certificate_cannot_be_fabricated(client,db,original,monkeypatch):
    from app.business_packs.pharma import return_stock
    post_original(db,original[3]);before=db.query(SRMInventoryBatch).count(),db.query(FAMVoucher).count()
    previous=return_stock.create_batch
    def forged(lease,*args):
        counterfeit=return_stock._Lease(lease.db,lease.actor,lease.scope,lease.root)
        return previous(counterfeit,*args)
    monkeypatch.setattr(return_stock,'create_batch',forged)
    response=client.post(BASE,headers=original[0][0][0],json=command(original))
    assert response.status_code==403,response.text
    assert db.query(PharmaReturn).count()==db.query(PharmaReturnLot).count()==0
    assert (db.query(SRMInventoryBatch).count(),db.query(FAMVoucher).count())==before


def test_pharmacy_manager_refunds_without_incoming_collection_capability(client,db,original):
    from app.business_packs.models import PackUserGrant
    from app.business_packs.registry import get_role
    post_original(db,original[3]);case=original[0][0]
    grant=db.query(PackUserGrant).filter_by(context_id=case[3],user_id=case[1].id).one()
    grant.role='pharmacy_manager';db.commit()
    capabilities=get_role('pharma','pharmacy_manager').capabilities
    assert 'pharma.returns.approve' in capabilities and 'pharma.payments.record' not in capabilities
    response=client.post(BASE,headers=case[0],json=command(original))
    assert response.status_code==201,response.text
    assert response.json()['state']=='committed' and response.json()['accounting']['refund']['status']=='posted'
    incoming=client.post('/api/v1/srm/service-checkout',headers=case[0],json=sale(original[0],quantity='1',paid=True))
    assert incoming.status_code==403,incoming.text
    assert 'Assigned Business Pack role cannot perform this operation' in incoming.text
    assert db.query(PharmaReturn).count()==1


def test_cashier_cannot_borrow_outgoing_refund_authority(client,db,original):
    from app.business_packs.models import PackUserGrant
    post_original(db,original[3]);case=original[0][0]
    grant=db.query(PackUserGrant).filter_by(context_id=case[3],user_id=case[1].id).one()
    grant.role='cashier';db.commit()
    before=db.query(FAMVoucher).count(),db.query(SRMInventoryMovement).count(),db.query(SRMInventoryBatch).count()
    response=client.post(BASE,headers=case[0],json=command(original))
    assert response.status_code==403,response.text
    assert db.query(PharmaReturn).count()==0
    assert (db.query(FAMVoucher).count(),db.query(SRMInventoryMovement).count(),db.query(SRMInventoryBatch).count())==before
