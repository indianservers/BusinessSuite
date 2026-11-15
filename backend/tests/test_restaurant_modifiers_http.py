"""Canonical catalog modifier configuration and actual Restaurant HTTP source."""
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.apps.srm.models import SRMProduct, SRMSalesOrderLine
from app.business_packs.models import PackMasterAvailability
from tests.test_restaurant_tabs import unpaid, scenario, catalog, directory_identity, data, BASE, stock
from tests.test_restaurant_kitchen import post


@pytest.fixture
def menu(client, db, unpaid, scenario):
    case = unpaid
    native_catalog = scenario[2]
    option = native_catalog[2][2]
    db.add(PackMasterAvailability(company_id=1, branch_id=case['branch'], context_id=case['context'],
        resource_table='srm_products', resource_key=str(option), active=True))
    db.commit()
    definition = {'version': 1, 'groups': [{'key':'extras', 'label':'Extras', 'min_choices':1,
        'max_choices':2, 'options':[{'product_id': option, 'max_quantity':2}]}]}
    response = client.put(f"/api/v1/catalog/items/product/{case['product']}?source=srm", headers=case['headers'],
        json={'kind':'product','name':'QA-STOCK','code':'QA-STOCK','price':'100','tax':'18','version':0,'restaurant_modifiers':definition})
    assert response.status_code == 200, response.text
    body = data(case)
    body['lines'][0]['modifiers'] = [{'group':'extras', 'product_id':option, 'quantity':2}]
    return case, option, body, native_catalog


def test_native_additive_modifiers_issue_exact_independent_stock_and_replay_frozen_catalog(client, db, menu):
    case, option, body, native_catalog = menu
    before = stock(db, case)
    order = post(client, case['headers'], '/tabs', body)
    assert Decimal(order['total']) == 354 and len(order['items']) == 2
    assert stock(db, case) == before
    assert len(order['modifier_sources']) == 2
    original = client.get(BASE+f"/orders/{order['id']}", headers=case['headers'])
    assert original.status_code == 200, original.text
    changed = client.put(f"/api/v1/catalog/items/product/{case['product']}?source=srm", headers=case['headers'],
        json={'kind':'product','name':'QA-STOCK','code':'QA-STOCK','price':'200','tax':'18','version':1,'restaurant_modifiers':{'groups':[]}})
    assert changed.status_code == 200, changed.text
    assert post(client, case['headers'], '/tabs', body) == order
    current = client.get(BASE+f"/orders/{order['id']}", headers=case['headers'])
    assert current.status_code == 200 and Decimal(current.json()['total']) == 354
    ticket = post(client, case['headers'], f"/orders/{order['id']}/tickets", {
        'request_key': str(uuid4()), 'service_order_id':order['id'], 'expected_revision':order['revision'],
        'lines':[{'sales_order_line_id':item['sales_order_line_id'], 'quantity':item['quantity']} for item in order['items']]})
    assert ticket['id'] and stock(db, case) == before-1
    assert db.get(SRMProduct, option).current_quantity == Decimal('3')


@pytest.mark.parametrize('fault', ['missing', 'unavailable', 'corrupt_source'])
def test_modifier_selection_native_visibility_and_issued_provenance_fail_closed(client, db, menu, fault):
    case, option, body, _ = menu
    if fault == 'missing':
        body['lines'][0]['modifiers'] = []
    elif fault == 'unavailable':
        item = db.query(PackMasterAvailability).filter_by(context_id=case['context'], resource_table='srm_products', resource_key=str(option)).one()
        item.active = False
        db.commit()
    else:
        order = post(client, case['headers'], '/tabs', body)
        line = SRMSalesOrderLine.__table__
        ident = order['items'][1]['sales_order_line_id']
        metadata = db.connection().scalar(select(line.c.metadata_json).where(line.c.id == ident))
        metadata['restaurant_modifier']['per_base_quantity'] = 1
        db.connection().execute(line.update().where(line.c.id == ident).values(metadata_json=metadata))
        db.commit()
        response = client.get(BASE+f"/orders/{order['id']}", headers=case['headers'])
        assert response.status_code == 409, response.text
        return
    response = client.post(BASE+'/tabs', headers=case['headers'], json=body)
    assert response.status_code == (422 if fault == 'missing' else 404), response.text


@pytest.mark.parametrize('fault', ['omitted', 'stale_version', 'unavailable_option', 'chef', 'stale_option_price'])
def test_modifier_config_version_omission_and_native_role_boundaries(client, db, menu, fault):
    case, option, body, _ = menu
    path = f"/api/v1/catalog/items/product/{case['product']}?source=srm"
    update = {'kind':'product','name':'QA-STOCK','code':'QA-STOCK','price':'100','tax':'18','version':1}
    if fault == 'stale_option_price':
        body['lines'][0]['modifiers'][0]['expected_unit_price'] = '1'
        response = client.post(BASE+'/tabs', headers=case['headers'], json=body)
        assert response.status_code == 409, response.text
        return
    if fault == 'stale_version':
        update['version'] = 0
    elif fault == 'unavailable_option':
        update['restaurant_modifiers'] = {'groups':[{'key':'extras','label':'Extras','options':[{'product_id':99999999}]}]}
    headers = case['headers']
    if fault == 'chef':
        from tests.test_restaurant_kitchen import staff
        headers, _ = staff(db, case, 'chef')
    response = client.put(path, headers=headers, json=update)
    expected = {'omitted':200, 'stale_version':409, 'unavailable_option':404, 'chef':403}[fault]
    assert response.status_code == expected, response.text
    current = client.get(path, headers=case['headers'])
    assert current.status_code == 200, current.text
    assert current.json()['restaurant_modifiers']['groups'][0]['options'][0]['product_id'] == option
    if fault == 'omitted':
        menu_response = client.get(BASE+'/menu', headers=case['headers'])
        assert menu_response.status_code == 200, menu_response.text
        item = next(item for item in menu_response.json()['items'] if item['id'] == case['product'])
        assert item['modifier_groups'][0]['options'][0]['price'] == '100.00'



def test_catalog_modifier_read_never_discloses_options_after_context_availability_revoked(client, db, menu):
    case, option, body, _ = menu
    enrolled = db.query(PackMasterAvailability).filter_by(context_id=case['context'], resource_table='srm_products', resource_key=str(option)).one()
    enrolled.active = False
    db.commit()
    response = client.get(f"/api/v1/catalog/items/product/{case['product']}?source=srm", headers=case['headers'])
    assert response.status_code == 409, response.text
    assert str(option) not in response.text and 'product_id' not in response.text.lower()



def test_modifier_additions_are_new_immutable_lines_and_replay_does_not_duplicate(client, db, menu):
    case, option, body, _ = menu
    order = post(client, case['headers'], '/tabs', body)
    addition = {'request_key':str(uuid4()), 'expected_revision':order['revision'], 'lines':body['lines']}
    added = post(client, case['headers'], f"/tabs/{order['id']}/items", addition)
    assert len(added['items']) == 4 and Decimal(added['total']) == 708
    assert len(added['modifier_sources']) == 2
    assert post(client, case['headers'], f"/tabs/{order['id']}/items", addition) == added
    current = client.get(BASE+f"/orders/{order['id']}", headers=case['headers'])
    assert current.status_code == 200 and len(current.json()['items']) == 4
    assert stock(db, case) == 5
