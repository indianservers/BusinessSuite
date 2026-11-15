from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
from sqlalchemy import select
from tests.test_pms_workflow_postgresql import live, race
from tests.test_restaurant_concurrency import configured
from tests.test_restaurant_anonymous import configure_counter
from app.models.user import User
from app.business_packs.models import PackContext
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantCommand
from app.apps.srm.models import SRMSalesOrder, SRMInvoice, SRMReceipt, SRMPOSSession, SRMInventoryMovement
from app.access.models import AccessPolicy

BASE = '/api/v1/srm/restaurant'


def prepared(live):
    headers, order = configured(live, unpaid=True)
    with live.factory() as db:
        context = db.get(PackContext, int(headers['X-Suite-Pack-Context']))
        admin = db.query(User).filter_by(is_superuser=True).order_by(User.id).first()
        assert admin is not None
        configure_counter(db, {'branch': context.branch_id, 'context': context.id}, admin, client=live.client)
        register = db.query(SRMPOSSession).one().id
    response = live.client.post(BASE+f"/orders/{order['id']}/tickets", headers=headers, json={
        'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '1'}]})
    assert response.status_code == 201, response.text
    current = live.client.get(BASE+f"/orders/{order['id']}", headers=headers)
    assert current.status_code == 200, current.text
    data = {'request_key': str(uuid4()), 'expected_revision': current.json()['revision'], 'expected_total': '118',
        'pos_session_id': register, 'payments': [{'payment_key': str(uuid4()), 'method': 'cash', 'amount': '50'},
            {'payment_key': str(uuid4()), 'method': 'card', 'amount': '68'}]}
    return headers, order['id'], data


def test_competing_anonymous_settlements_cannot_bill_or_collect_twice(live):
    headers, ident, body = prepared(live)
    results = race(lambda: live.client.post(BASE+f'/tabs/{ident}/anonymous-settlement', headers=headers, json=body),
        lambda: live.client.post(BASE+f'/tabs/{ident}/anonymous-settlement', headers=headers, json={**body,'request_key':str(uuid4())}))
    assert sorted(row.status_code for row in results) == [201,409], [row.text for row in results]
    with live.factory() as db:
        assert db.query(SRMInvoice).count() == 1 and db.query(SRMReceipt).count() == 2
        assert db.query(RestaurantCommand).filter_by(action='tab.settle_anonymous').count() == 1
        assert db.query(SRMInventoryMovement).filter_by(movement_type='restaurant_kitchen').count() == 1


def test_parallel_exact_anonymous_replay_has_one_full_settlement(live):
    headers, ident, body = prepared(live)
    call = lambda: live.client.post(BASE+f'/tabs/{ident}/anonymous-settlement', headers=headers, json=body)
    results = race(call, call)
    assert [row.status_code for row in results] == [201,201], [row.text for row in results]
    assert results[0].json() == results[1].json()
    with live.factory() as db:
        assert db.query(SRMInvoice).count() == 1 and db.query(SRMReceipt).count() == 2


def test_full_native_permission_revocation_while_waiting_leaves_no_anonymous_binding(live, monkeypatch):
    from app.business_packs.restaurant import service
    from app.core.company_writer import lock_company_writer
    headers, ident, body = prepared(live)
    with live.factory() as db:
        actor = db.get(RestaurantServiceOrder, ident).created_by
    original, waiting = service.lock_tenant, Event()
    def observed(db, actor):
        waiting.set()
        return original(db, actor)
    monkeypatch.setattr(service, 'lock_tenant', observed)
    with live.factory() as blocker:
        lock_company_writer(blocker, 1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda: live.client.post(BASE+f'/tabs/{ident}/anonymous-settlement', headers=headers, json=body))
            assert waiting.wait(timeout=20), 'Anonymous settlement did not reach actual company writer wait'
            table = AccessPolicy.__table__
            row = blocker.connection().execute(select(table.c.id, table.c.grants).where(table.c.company_id == 1, table.c.user_id == actor)).mappings().one()
            names = ['srm_invoice_create','srm_invoice_approve','srm_collection_create','srm_collection_view']
            grants = {**row['grants'],'srm':{**row['grants']['srm'],'permissions':names}}
            blocker.connection().execute(table.update().where(table.c.id == row['id']).values(grants=grants, version=table.c.version+1))
            blocker.commit()
            response = future.result(timeout=40)
            assert response.status_code == 403, response.text
    with live.factory() as db:
        assert db.query(SRMSalesOrder).one().customer_id is None
        assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 0
