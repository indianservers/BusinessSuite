import json
from decimal import Decimal
from app.apps.srm.models import SRMSalesOrder
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantTable
from tests.test_restaurant_modifiers_http import menu, unpaid, scenario, catalog, directory_identity
from tests.test_restaurant_kitchen import staff


def test_modifier_transfer_summary_in_existing_desktop_and_phone_screen(client, db, menu, monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    from tests.test_restaurant_removals import enable_delete
    case, option, _, _ = menu
    enable_delete(db, case)
    chef, _ = staff(db, case, 'chef')
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'restaurant-extensions-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH', json.dumps({'branch': str(case['branch']), 'context': str(case['context']),
        'product': case['product'], 'option': option, 'manager': case['headers']['Authorization'].split(' ', 1)[1],
        'chef': chef['Authorization'].split(' ', 1)[1]}))
    test_control_center_real_browser(client, db, None, case['headers'])
    assert db.query(SRMSalesOrder).one().total_amount == Decimal('118')
    assert db.query(RestaurantServiceOrder).one().table_id == db.query(RestaurantTable).filter_by(name='Moved table').one().id

    from app.apps.srm.industry_models import IndustryRecord
    reservation = db.query(IndustryRecord).filter_by(kind='restaurant_reservation').one()
    assert reservation.customer_id == 101 and reservation.status == 'cancelled'
