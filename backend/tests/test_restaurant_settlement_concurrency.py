from uuid import uuid4
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from sqlalchemy import select
from tests.test_pms_workflow_postgresql import live, race
from tests.test_restaurant_concurrency import configured
from app.apps.srm.models import SRMPOSSession, SRMInvoice, SRMReceipt, SRMInventoryMovement
from app.apps.srm.service_checkout_models import POSServiceCheckout

BASE = '/api/v1/srm/restaurant'


def prepared(live):
    headers, order = configured(live, unpaid=True, customer=101)
    response = live.client.post(BASE+f"/orders/{order['id']}/tickets", headers=headers, json={
        'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '1'}]})
    assert response.status_code == 201, response.text
    response = live.client.get(BASE+f"/orders/{order['id']}", headers=headers)
    assert response.status_code == 200, response.text
    with live.factory() as db:
        register = db.query(SRMPOSSession).one().id
    payload = {'request_key': str(uuid4()), 'expected_revision': response.json()['revision'],
        'pos_session_id': register, 'expected_total': '118'}
    return headers, order['id'], payload


def test_competing_bill_commands_issue_one_native_invoice(live):
    headers, order, payload = prepared(live)
    results = race(lambda: live.client.post(BASE+f'/tabs/{order}/bill', headers=headers, json=payload),
        lambda: live.client.post(BASE+f'/tabs/{order}/bill', headers=headers, json={**payload, 'request_key': str(uuid4())}))
    assert sorted(response.status_code for response in results) == [201, 409], [response.text for response in results]
    with live.factory() as db:
        assert db.query(SRMInvoice).count() == db.query(POSServiceCheckout).count() == 1
        assert db.query(SRMReceipt).count() == 0
        assert db.query(SRMInventoryMovement).filter_by(movement_type='restaurant_kitchen').count() == 1


def test_exact_bill_replay_is_one_invoice_under_parallel_sessions(live):
    headers, order, payload = prepared(live)
    call = lambda: live.client.post(BASE+f'/tabs/{order}/bill', headers=headers, json=payload)
    results = race(call, call)
    assert [response.status_code for response in results] == [201, 201], [response.text for response in results]
    assert results[0].json() == results[1].json()
    with live.factory() as db:
        assert db.query(SRMInvoice).count() == db.query(POSServiceCheckout).count() == 1


def test_competing_full_balance_payments_cannot_overcollect(live):
    headers, order, payload = prepared(live)
    billed = live.client.post(BASE+f'/tabs/{order}/bill', headers=headers, json=payload)
    assert billed.status_code == 201, billed.text
    def call():
        return live.client.post(BASE+f'/tabs/{order}/payments', headers=headers, json={
            'request_key': str(uuid4()), 'expected_revision': billed.json()['checkout']['revision'],
            'pos_session_id': payload['pos_session_id'],
            'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '118'}})
    results = race(call, call)
    assert sorted(response.status_code for response in results) == [201, 409], [response.text for response in results]
    with live.factory() as db:
        assert db.query(SRMReceipt).count() == 1 and db.query(SRMInvoice).one().paid_amount == Decimal('118')
        assert db.query(SRMInventoryMovement).filter_by(movement_type='restaurant_kitchen').count() == 1


def test_native_invoice_approve_revocation_during_actual_writer_wait_denies_bill(live, monkeypatch):
    from app.business_packs.restaurant import settlement
    from app.business_packs.restaurant.models import RestaurantServiceOrder
    from app.access.models import AccessPolicy
    from app.core.company_writer import lock_company_writer
    headers, order, payload = prepared(live)
    with live.factory() as db:
        actor = db.get(RestaurantServiceOrder, order).created_by
    waiting, original = Event(), settlement.lock_tenant
    def observed(db, actor):
        waiting.set()
        return original(db, actor)
    monkeypatch.setattr(settlement, 'lock_tenant', observed)
    with live.factory() as blocker:
        lock_company_writer(blocker, 1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda: live.client.post(BASE+f'/tabs/{order}/bill', headers=headers, json=payload))
            assert waiting.wait(timeout=20), 'Bill command did not reach actual company writer wait'
            table = AccessPolicy.__table__
            policy = blocker.connection().execute(select(table.c.id, table.c.grants).where(table.c.company_id == 1, table.c.user_id == actor)).mappings().one()
            grants = {**policy['grants'], 'srm': {**policy['grants']['srm'], 'actions': ['view','create']}}
            blocker.connection().execute(table.update().where(table.c.id == policy['id']).values(grants=grants, version=table.c.version+1))
            blocker.commit()
            response = future.result(timeout=40)
            assert response.status_code == 403, response.text
    with live.factory() as db:
        assert db.query(SRMInvoice).count() == db.query(POSServiceCheckout).count() == db.query(SRMReceipt).count() == 0
