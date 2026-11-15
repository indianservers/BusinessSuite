"""Prepared for the serialized native slot: real independent committed sessions."""
from uuid import uuid4
from decimal import Decimal

from tests.test_pms_workflow_postgresql import live, race
from tests.test_restaurant_settlement_concurrency import prepared
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMSalesOrder, SRMSalesOrderLine, SRMInventoryMovement
from app.apps.srm.service_checkout_models import POSServiceCheckout
from app.business_packs.restaurant.split_models import RestaurantBillGroup, RestaurantBillReceipt

BASE = '/api/v1/srm/restaurant'


def split_input(live, headers, order_id, original):
    order = live.client.get(BASE+f'/orders/{order_id}', headers=headers)
    assert order.status_code == 200, order.text
    return {'request_key': str(uuid4()), 'expected_revision': original['expected_revision'], 'expected_total': '59',
        'lines': [{'sales_order_line_id': order.json()['items'][0]['sales_order_line_id'], 'quantity': '.5'}]}


def test_split_and_whole_bill_race_reserve_original_source_once(live):
    headers, order, whole = prepared(live)
    payload = split_input(live, headers, order, whole)
    results = race(lambda: live.client.post(BASE+f'/tabs/{order}/bills', headers=headers, json=payload),
        lambda: live.client.post(BASE+f'/tabs/{order}/bill', headers=headers, json=whole))
    assert sorted(row.status_code for row in results) == [201, 409], [row.text for row in results]
    with live.factory() as db:
        assert db.query(SRMInvoice).count() == db.query(SRMSalesOrder).count() == 1
        assert db.query(RestaurantBillGroup).count() + db.query(POSServiceCheckout).count() == 1
        assert db.query(SRMSalesOrderLine).one().quantity == 1
        assert db.query(SRMInventoryMovement).filter_by(movement_type='restaurant_kitchen').count() == 1


def test_distinct_split_commands_compete_on_one_original_revision(live):
    headers, order, whole = prepared(live)
    payload = split_input(live, headers, order, whole)
    results = race(lambda: live.client.post(BASE+f'/tabs/{order}/bills', headers=headers, json=payload),
        lambda: live.client.post(BASE+f'/tabs/{order}/bills', headers=headers, json={**payload, 'request_key': str(uuid4())}))
    assert sorted(row.status_code for row in results) == [201, 409], [row.text for row in results]
    with live.factory() as db:
        assert db.query(SRMInvoice).count() == db.query(RestaurantBillGroup).count() == 1
        assert db.query(SRMInvoice).one().total_amount == 59


def test_duplicate_split_commands_replay_one_canonical_invoice(live):
    headers, order, whole = prepared(live)
    payload = split_input(live, headers, order, whole)
    call = lambda: live.client.post(BASE+f'/tabs/{order}/bills', headers=headers, json=payload)
    results = race(call, call)
    assert [row.status_code for row in results] == [201, 201], [row.text for row in results]
    assert results[0].json() == results[1].json()
    with live.factory() as db:
        assert db.query(SRMInvoice).count() == db.query(RestaurantBillGroup).count() == 1


def test_parallel_duplicate_split_payment_records_one_actual_native_receipt(live):
    headers, order, whole = prepared(live)
    billed = live.client.post(BASE+f'/tabs/{order}/bills', headers=headers, json=split_input(live, headers, order, whole))
    assert billed.status_code == 201, billed.text
    bill = billed.json()
    payment = {'request_key': str(uuid4()), 'expected_revision': bill['order_revision'], 'expected_balance': '59',
        'pos_session_id': whole['pos_session_id'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '59'}}
    call = lambda: live.client.post(BASE+f"/tabs/{order}/bills/{bill['bill_id']}/payments", headers=headers, json=payment)
    results = race(call, call)
    assert [row.status_code for row in results] == [201, 201], [row.text for row in results]
    assert results[0].json() == results[1].json()
    with live.factory() as db:
        assert db.query(SRMReceipt).count() == db.query(RestaurantBillReceipt).count() == 1
        assert db.query(SRMInvoice).one().paid_amount == Decimal('59')


def test_distinct_payment_commands_cannot_overcollect_one_split_bill_balance(live):
    headers, order, whole = prepared(live)
    billed = live.client.post(BASE+f'/tabs/{order}/bills', headers=headers, json=split_input(live, headers, order, whole))
    assert billed.status_code == 201, billed.text
    bill = billed.json()
    def call():
        return live.client.post(BASE+f"/tabs/{order}/bills/{bill['bill_id']}/payments", headers=headers, json={
            'request_key': str(uuid4()), 'expected_revision': bill['order_revision'], 'expected_balance': '59',
            'pos_session_id': whole['pos_session_id'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '59'}})
    results = race(call, call)
    assert sorted(row.status_code for row in results) == [201, 409], [row.text for row in results]
    with live.factory() as db:
        assert db.query(SRMReceipt).count() == db.query(RestaurantBillReceipt).count() == 1
        assert db.query(SRMInvoice).one().paid_amount == Decimal('59')
