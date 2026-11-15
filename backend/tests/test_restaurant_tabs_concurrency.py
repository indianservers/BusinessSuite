from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
from sqlalchemy import select
from tests.test_pms_workflow_postgresql import live, race
from tests.test_restaurant_concurrency import configured
from app.access.models import AccessPolicy
from app.apps.srm.models import SRMInventoryMovement, SRMInventoryBalance, SRMInvoice, SRMReceipt, SRMSalesOrder
from app.business_packs.restaurant.models import RestaurantKitchenIssue, RestaurantKitchenTicket, RestaurantServiceOrder

BASE = '/api/v1/srm/restaurant'


def body(order):
    return {'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '1'}]}


def proof(live):
    with live.factory() as db:
        assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 0
        assert db.query(RestaurantKitchenIssue).count() == db.query(RestaurantKitchenTicket).count() == 1
        assert db.query(SRMInventoryMovement).filter_by(movement_type='restaurant_kitchen').count() == 1
        assert db.query(SRMInventoryBalance).one().quantity == 0


def test_unpaid_last_unit_firing_is_atomic_in_competing_transactions(live):
    headers, order = configured(live, unpaid=True)
    call = lambda: live.client.post(BASE+f"/orders/{order['id']}/tickets", headers=headers, json=body(order))
    results = race(call, call)
    assert sorted(response.status_code for response in results) == [201, 409], [response.text for response in results]
    proof(live)


def test_unpaid_exact_replay_has_one_canonical_stock_issue(live):
    headers, order = configured(live, unpaid=True)
    data = body(order)
    call = lambda: live.client.post(BASE+f"/orders/{order['id']}/tickets", headers=headers, json=data)
    results = race(call, call)
    assert [response.status_code for response in results] == [201, 201], [response.text for response in results]
    assert results[0].json() == results[1].json()
    proof(live)


def test_unpaid_create_rechecks_native_rights_after_actual_company_wait(live, monkeypatch):
    from app.business_packs.restaurant import tabs
    from app.core.company_writer import lock_company_writer
    headers, order = configured(live, unpaid=True)
    with live.factory() as db:
        actor_id = db.get(RestaurantServiceOrder, order['id']).created_by
        source = db.query(SRMSalesOrder).one()
        from app.apps.srm.models import SRMSalesOrderLine
        product = db.query(SRMSalesOrderLine).filter_by(sales_order_id=source.id).one().product_id
    waiting = Event()
    original = tabs.lock_tenant
    def observed(db, actor):
        waiting.set()
        return original(db, actor)
    monkeypatch.setattr(tabs, 'lock_tenant', observed)
    with live.factory() as blocker:
        lock_company_writer(blocker, 1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda: live.client.post(BASE+'/tabs', headers=headers, json={
                'request_key': str(uuid4()), 'lines': [{'product_id': product, 'quantity': '1', 'expected_unit_price': '100'}]}))
            assert waiting.wait(timeout=20), 'Tab command did not reach the actual company writer wait'
            table = AccessPolicy.__table__
            policy = blocker.connection().execute(select(table.c.id, table.c.grants).where(table.c.company_id == 1, table.c.user_id == actor_id)).mappings().one()
            grants = {**policy['grants'], 'srm': {**policy['grants']['srm'], 'actions': ['view']}}
            blocker.connection().execute(table.update().where(table.c.id == policy['id']).values(grants=grants, version=table.c.version+1))
            blocker.commit()
            response = future.result(timeout=30)
            assert response.status_code == 403, response.text
    with live.factory() as db:
        assert db.query(SRMSalesOrder).count() == db.query(RestaurantServiceOrder).count() == 1
        assert db.query(SRMInventoryMovement).filter_by(movement_type='restaurant_kitchen').count() == 0
        assert db.query(SRMInventoryBalance).one().quantity == 1
        assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 0
