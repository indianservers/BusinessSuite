"""Cash denomination guards use actual native checkout sources, never FX sums."""
import json
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.apps.srm.models import SRMPOSSession, SRMProduct, SRMReceipt, SRMPOSCashMovement
from app.apps.srm.register_currency import evidence, require_cash_currency
from app.apps.srm.service_checkout_register import group_register_cash
from tests.test_retail_return_http import retail_setup, scenario, catalog, directory_identity, retail_http, command, post_original


def sale(client,db,case,currency='INR',method='cash',amount='118'):
    product=db.get(SRMProduct,case[5])
    product.metadata_json={**(product.metadata_json or {}),'currency':currency};db.commit()
    return client.post('/api/v1/srm/service-checkout',headers=case[0],json={
        'request_id':str(uuid4()),'customer_id':101,'pos_session_id':case[4],'currency':currency,
        'lines':[{'client_line_key':str(uuid4()),'line_kind':'product','product_id':case[5],'quantity':1}],
        'payments':[{'payment_key':str(uuid4()),'method':method,'amount':amount}] if amount else []})


def test_actual_cash_currency_mismatch_is_atomic_and_card_stays_native(client,db,retail_setup):
    first=sale(client,db,retail_setup);assert first.status_code==201,first.text
    receipts=db.query(SRMReceipt).count()
    rejected=sale(client,db,retail_setup,'USD');assert rejected.status_code==409,rejected.text
    assert db.query(SRMReceipt).count()==receipts
    card=sale(client,db,retail_setup,'USD','card');assert card.status_code==201,card.text
    summary=client.get('/api/v1/srm/pos/sessions/active',headers=retail_setup[0]).json()
    assert summary['cash_sales']==summary['expected_cash']==118
    assert summary['cash_currency']=='INR' and not summary['reconciliation_required']
    closed=client.post('/api/v1/srm/pos/cashier-closing',headers=retail_setup[0],json={'session_id':retail_setup[4],'counted_cash':'118'})
    assert closed.status_code==201,closed.text


def test_actual_append_cash_mismatch_has_no_receipt(client,db,retail_setup):
    assert sale(client,db,retail_setup).status_code==201
    credit=sale(client,db,retail_setup,'USD',amount=None);assert credit.status_code==201,credit.text
    count=db.query(SRMReceipt).count();data=credit.json()
    response=client.post(f"/api/v1/srm/service-checkout/{data['id']}/payments",headers=retail_setup[0],json={
        'expected_revision':data['revision'],'pos_session_id':retail_setup[4],
        'payment':{'payment_key':str(uuid4()),'method':'cash','amount':'118'}})
    assert response.status_code==409,response.text
    assert db.query(SRMReceipt).count()==count


def test_legacy_untyped_opening_is_readonly_and_blocks_close_and_movement(client,db,retail_setup):
    register=db.get(SRMPOSSession,retail_setup[4]);register.opening_cash=20;db.commit()
    metadata=register.metadata_json
    summary=client.get('/api/v1/srm/pos/sessions/active',headers=retail_setup[0]);assert summary.status_code==200,summary.text
    assert summary.json()['reconciliation_required'] and summary.json()['expected_cash'] is None
    assert db.get(SRMPOSSession,register.id).metadata_json==metadata
    response=client.post('/api/v1/srm/pos/cashier-closing',headers=retail_setup[0],json={'session_id':register.id,'counted_cash':'20'})
    assert response.status_code==409,response.text
    movement=client.post('/api/v1/srm/pos/cash-movements',headers=retail_setup[0],json={'session_id':register.id,'movement_type':'cash_in','amount':'10'})
    assert movement.status_code==409,movement.text
    assert db.query(SRMPOSCashMovement).count()==0


def test_new_register_currency_is_server_managed(client,db,retail_setup):
    old=db.get(SRMPOSSession,retail_setup[4]);old.status='closed';db.commit()
    forged=client.post('/api/v1/srm/pos/sessions',headers=retail_setup[0],json={'opening_cash':'0','metadata_json':{'cash_currency':'USD'}})
    assert forged.status_code==422,forged.text
    opened=client.post('/api/v1/srm/pos/sessions',headers=retail_setup[0],json={'opening_cash':'25'})
    assert opened.status_code==201,opened.text
    assert opened.json()['session']['metadata_json']['cash_currency']=='INR'
    assert opened.json()['expected_cash']==25


def test_actual_refund_currency_mismatch_rolls_back(client,db,retail_http):
    post_original(db,retail_http)
    # Open a genuinely different-currency drawer; issued INR sources stay untouched.
    from app.models.company import Company
    register=db.get(SRMPOSSession,retail_http[5]);register.status='closed'
    db.get(Company,1).default_currency='USD';db.commit()
    opened=client.post('/api/v1/srm/pos/sessions',headers=retail_http[0],json={'opening_cash':'1000'})
    assert opened.status_code==201,opened.text
    payload=command(retail_http);payload['refund']['session_id']=opened.json()['session']['id']
    before=db.query(SRMPOSCashMovement).count()
    response=client.post('/api/v1/srm/retail/returns',headers=retail_http[0],json=payload)
    assert response.status_code==409,response.text
    assert db.query(SRMPOSCashMovement).count()==before


def test_historical_mixed_cash_is_never_scalar_and_get_does_not_bind(client,db,retail_setup,monkeypatch):
    import app.apps.srm.register_currency as currencies
    with monkeypatch.context() as setup:
        # Recreate valid pre-fix cash receipts through the native API.
        setup.setattr(currencies,'require_cash_currency',lambda *args,**kwargs:None)
        assert sale(client,db,retail_setup).status_code==201
        assert sale(client,db,retail_setup,'USD').status_code==201
    register=db.get(SRMPOSSession,retail_setup[4]);before=register.metadata_json
    response=client.get('/api/v1/srm/pos/sessions/active',headers=retail_setup[0]);assert response.status_code==200,response.text
    summary=response.json()
    assert summary['cash_sales'] is None and summary['expected_cash'] is None
    assert summary['reconciliation_required'] and summary['cash_by_currency']=={'INR':118,'USD':118}
    assert db.get(SRMPOSSession,register.id).metadata_json==before
    from tests.test_srm_native_transaction_operations import native_writer
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    with native_writer(db,retail_setup[1],retail_setup[2]):
        scope=resolve_context(db,retail_setup[1],db.info['branch_context'],retail_setup[3])
        cleanup=install(db,scope,policy=native_srm_policy('retail').policy)
        try:
            with pytest.raises(HTTPException) as denied:
                group_register_cash(db,register,[])
            assert denied.value.status_code==409
        finally:
            cleanup()
    close=client.post('/api/v1/srm/pos/cashier-closing',headers=retail_setup[0],json={'session_id':register.id,'counted_cash':'236'})
    assert close.status_code==409,close.text
    assert db.get(SRMPOSSession,register.id).status=='open'


def test_failed_cash_checkout_does_not_bind_and_success_replay_does_not_collect_twice(client,db,retail_setup):
    register=db.get(SRMPOSSession,retail_setup[4]);before=register.metadata_json
    invalid=sale(client,db,retail_setup,amount='999');assert invalid.status_code in (400,409,422),invalid.text
    assert db.get(SRMPOSSession,register.id).metadata_json==before
    response=sale(client,db,retail_setup);assert response.status_code==201,response.text
    assert db.get(SRMPOSSession,register.id).metadata_json['cash_currency']=='INR'
    receipts=db.query(SRMReceipt).count()
    replay=client.post('/api/v1/srm/service-checkout',headers=retail_setup[0],json=json.loads(response.request.content))
    assert replay.status_code==201 and replay.json()==response.json(),replay.text
    assert client.get('/api/v1/srm/pos/sessions/active',headers=retail_setup[0]).json()['cash_sales']==118
    assert db.query(SRMReceipt).count()==receipts


def test_empty_legacy_drawer_can_close_zero_without_binding_currency(client,db,retail_setup):
    register=db.get(SRMPOSSession,retail_setup[4]);before=register.metadata_json
    response=client.post('/api/v1/srm/pos/cashier-closing',headers=retail_setup[0],json={'session_id':register.id,'counted_cash':'0'})
    assert response.status_code==201,response.text
    assert response.json()['closing']['expected_cash']==response.json()['closing']['variance']==0
    assert db.get(SRMPOSSession,register.id).metadata_json==before
    assert response.json()['cash_currency'] is None


def test_empty_legacy_drawer_cannot_close_nonzero_or_accept_untyped_movement(client,db,retail_setup):
    register=db.get(SRMPOSSession,retail_setup[4]);before=register.metadata_json
    response=client.post('/api/v1/srm/pos/cashier-closing',headers=retail_setup[0],json={'session_id':register.id,'counted_cash':'1'})
    assert response.status_code==409,response.text
    assert db.get(SRMPOSSession,register.id).status=='open'
    movement=client.post('/api/v1/srm/pos/cash-movements',headers=retail_setup[0],json={'session_id':register.id,'movement_type':'cash_in','amount':'1'})
    assert movement.status_code==409,movement.text
    assert db.get(SRMPOSSession,register.id).metadata_json==before
