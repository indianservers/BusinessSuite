"""Real API, separate manager/Chef/Server browser identities; existing UI controls."""
import json
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantKitchenTicket
from tests.test_restaurant_kitchen import restaurant, staff, counts, scenario, catalog, directory_identity


def test_paid_order_prepared_by_chef_and_served_by_server_in_original_controls(client, db, restaurant, monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    chef, _ = staff(db, restaurant, 'chef')
    server, _ = staff(db, restaurant, 'server')
    before = counts(db)[:3]
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'restaurant-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH', json.dumps({'branch': str(restaurant['branch']), 'context': str(restaurant['context']),
        'checkout': restaurant['checkout']['id'], 'manager': restaurant['headers']['Authorization'].split(' ', 1)[1],
        'chef': chef['Authorization'].split(' ', 1)[1], 'server': server['Authorization'].split(' ', 1)[1]}))
    test_control_center_real_browser(client, db, None, restaurant['headers'])
    assert db.query(RestaurantServiceOrder).one().state == 'served'
    assert db.query(RestaurantKitchenTicket).one().state == 'served'
    assert counts(db)[:3] == before
