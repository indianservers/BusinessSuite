from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
from sqlalchemy import select
from tests.test_pms_workflow_postgresql import live, race
from tests.test_restaurant_concurrency import configured
from app.apps.srm.models import SRMSalesOrder, SRMInvoice
from app.business_packs.restaurant.models import RestaurantCommand, RestaurantServiceOrder
from app.access.models import AccessPolicy

BASE = '/api/v1/srm/restaurant'


def test_competing_customer_assignment_is_one_immutable_transition(live):
    headers, order = configured(live, unpaid=True)
    body = {'request_key': str(uuid4()), 'expected_revision': order['revision'], 'customer_id': 101}
    results = race(lambda: live.client.post(BASE+f"/tabs/{order['id']}/customer", headers=headers, json=body),
        lambda: live.client.post(BASE+f"/tabs/{order['id']}/customer", headers=headers, json={**body, 'request_key': str(uuid4())}))
    assert sorted(row.status_code for row in results) == [200,409], [row.text for row in results]
    with live.factory() as db:
        assert db.query(RestaurantCommand).filter_by(action='tab.assign_customer').count() == 1
        assert db.query(SRMSalesOrder).one().customer_id == 101 and db.query(SRMInvoice).count() == 0


def test_same_customer_command_parallel_replay_returns_same_source(live):
    headers, order = configured(live, unpaid=True)
    body = {'request_key': str(uuid4()), 'expected_revision': order['revision'], 'customer_id': 101}
    call = lambda: live.client.post(BASE+f"/tabs/{order['id']}/customer", headers=headers, json=body)
    results = race(call, call)
    assert [row.status_code for row in results] == [200,200], [row.text for row in results]
    assert results[0].json() == results[1].json()
    with live.factory() as db:
        assert db.query(RestaurantCommand).filter_by(action='tab.assign_customer').count() == 1


def test_native_order_permission_revocation_while_waiting_denies_assignment(live, monkeypatch):
    from app.business_packs.restaurant import tabs
    from app.core.company_writer import lock_company_writer
    headers, order = configured(live, unpaid=True)
    with live.factory() as db:
        actor = db.get(RestaurantServiceOrder, order['id']).created_by
    original, waiting = tabs.lock_tenant, Event()
    def observed(db, actor):
        waiting.set()
        return original(db, actor)
    monkeypatch.setattr(tabs, 'lock_tenant', observed)
    with live.factory() as blocker:
        lock_company_writer(blocker, 1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda: live.client.post(BASE+f"/tabs/{order['id']}/customer", headers=headers, json={
                'request_key': str(uuid4()), 'expected_revision': order['revision'], 'customer_id': 101}))
            assert waiting.wait(timeout=20), 'Assignment did not reach actual company writer wait'
            table = AccessPolicy.__table__
            policy = blocker.connection().execute(select(table.c.id, table.c.grants).where(table.c.company_id == 1, table.c.user_id == actor)).mappings().one()
            grants = {**policy['grants'], 'srm': {**policy['grants']['srm'], 'actions': ['view']}}
            blocker.connection().execute(table.update().where(table.c.id == policy['id']).values(grants=grants, version=table.c.version+1))
            blocker.commit()
            response = future.result(timeout=40)
            assert response.status_code == 403, response.text
    with live.factory() as db:
        assert db.query(SRMSalesOrder).one().customer_id is None
        assert db.query(RestaurantCommand).filter_by(action='tab.assign_customer').count() == 0
