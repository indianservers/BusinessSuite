from datetime import datetime, timedelta, timezone
from uuid import uuid4
from tests.test_pms_workflow_postgresql import live, race
from tests.test_restaurant_concurrency import configured
from app.access.models import AccessPolicy
from app.apps.srm.models import SRMSalesOrderLine
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantCommand, RestaurantTabLine

BASE = '/api/v1/srm/restaurant'


def test_parallel_reservations_cannot_double_book_same_table(live):
    headers, _ = configured(live, unpaid=True)
    response = live.client.post(BASE + '/tables', headers=headers, json={'request_key': str(uuid4()), 'name': 'Concurrent reservation', 'capacity': 4})
    assert response.status_code == 201, response.text
    table = response.json()
    body = {'table_id': table['id'], 'expected_table_revision': table['revision'], 'party_size': 3,
        'starts_at': (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(), 'duration_minutes': 60}
    calls = [lambda: live.client.post(BASE + '/reservations', headers=headers, json={**body, 'request_key': str(uuid4())}) for _ in range(2)]
    results = race(*calls)
    assert sorted(row.status_code for row in results) == [201, 409], [row.text for row in results]
    assert live.client.get(BASE + '/reservations', headers=headers).json()['items'].__len__() == 1


def removable(live):
    headers, order = configured(live, unpaid=True)
    with live.factory() as db:
        actor = db.get(RestaurantServiceOrder, order['id']).created_by
        policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor).one()
        policy.grants = {**policy.grants, 'srm': {**policy.grants['srm'], 'actions': ['view', 'create', 'edit', 'approve', 'delete']}}
        product = db.query(SRMSalesOrderLine).filter_by(sales_order_id=order['sales_order_id']).one().product_id
        db.commit()
    response = live.client.post(BASE + f"/tabs/{order['id']}/items", headers=headers, json={'request_key': str(uuid4()),
        'expected_revision': order['revision'], 'lines': [{'product_id': product, 'quantity': '1', 'expected_unit_price': '100'}]})
    assert response.status_code == 201, response.text
    order = response.json()
    payload = {'request_key': str(uuid4()), 'expected_revision': order['revision'],
        'sales_order_line_ids': [order['items'][-1]['sales_order_line_id']], 'reason': 'Guest changed selection'}
    return headers, order, payload


def test_parallel_duplicate_removal_has_one_immutable_cancellation(live):
    headers, order, payload = removable(live)
    call = lambda: live.client.post(BASE + f"/tabs/{order['id']}/remove-items", headers=headers, json=payload)
    results = race(call, call)
    assert [row.status_code for row in results] == [200, 200], [row.text for row in results]
    assert results[0].json() == results[1].json()
    with live.factory() as db:
        assert db.query(RestaurantCommand).filter_by(action='tab.remove').count() == 1
        assert db.query(RestaurantTabLine).filter(RestaurantTabLine.sales_order_line_id.is_(None)).count() == 1


def test_removal_and_kitchen_firing_compete_on_same_revision(live):
    headers, order, payload = removable(live)
    remove = lambda: live.client.post(BASE + f"/tabs/{order['id']}/remove-items", headers=headers, json=payload)
    fire = lambda: live.client.post(BASE + f"/orders/{order['id']}/tickets", headers=headers, json={'request_key': str(uuid4()),
        'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': payload['sales_order_line_ids'][0], 'quantity': '1'}]})
    results = race(remove, fire)
    assert sorted(row.status_code for row in results) in ([200,409], [201,409]), [row.text for row in results]
    current = live.client.get(BASE + f"/orders/{order['id']}", headers=headers)
    assert current.status_code == 200, current.text
