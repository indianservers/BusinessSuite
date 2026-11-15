"""Real native-auth paid POS -> server -> chef -> server fulfillment proof."""
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.apps.srm.models import SRMPOSSession, SRMInvoice, SRMReceipt, SRMInventoryMovement, SRMSalesOrderLine
from app.business_packs.restaurant.models import MODELS, RestaurantCommand, RestaurantKitchenTicket, RestaurantKitchenLine
from app.business_packs.models import PackMasterAvailability, PackContext, PackUserGrant
from app.business_packs.boundary import install
from app.business_packs.access import resolve_context
from app.business_packs.native_policy import native_srm_policy
from tests.test_business_pack_http_integration import native_actor, grant
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer

BASE = '/api/v1/srm/restaurant'


@pytest.fixture
def restaurant(client, db, scenario):
    _, branch, catalog, _ = scenario
    for model in MODELS:
        model.__table__.create(db.bind, checkfirst=True)
    headers, manager = native_actor(db, branch)
    context, role = grant(db, manager, branch, 'restaurant', 'restaurant_manager')
    product, warehouse = catalog[2][0], catalog[1]
    for table, ident in [('srm_products', product), ('srm_warehouses', warehouse), ('crm_companies', 101)]:
        db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context.id, resource_table=table, resource_key=str(ident), active=True))
    db.commit()
    with native_writer(db, manager, branch):
        scope = resolve_context(db, manager, db.info['branch_context'], context.id)
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            register = SRMPOSSession(organization_id=1, session_number='DINING-'+uuid4().hex, status='open', cashier_user_id=manager.id, created_by=manager.id)
            db.add(register)
            db.commit()
            register_id = register.id
        finally:
            cleanup()
    headers = {**headers, 'X-Suite-Pack-Context': str(context.id)}
    payload = {'request_id': str(uuid4()), 'customer_id': 101, 'pos_session_id': register_id,
        'lines': [{'client_line_key': str(uuid4()), 'line_kind': 'product', 'product_id': product, 'quantity': '2'}],
        'payments': [{'payment_key': str(uuid4()), 'method': 'cash', 'amount': '236'}]}
    response = client.post('/api/v1/srm/service-checkout', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return {'headers': headers, 'manager': manager, 'role_id': role.id, 'context': context.id, 'branch': branch,
            'checkout': response.json(), 'payload': payload}


def post(client, headers, path, body, status=201):
    response = client.post(BASE+path, headers=headers, json=body)
    assert response.status_code == status, response.text
    return response.json()


def setup_order(client, case, table=True):
    body = {'request_key': str(uuid4()), 'checkout_id': case['checkout']['id'], 'expected_checkout_revision': case['checkout']['revision']}
    if table:
        created = post(client, case['headers'], '/tables', {'request_key': str(uuid4()), 'name': 'Table 1', 'capacity': 4})
        body |= {'table_id': created['id'], 'expected_table_revision': created['revision']}
    order = post(client, case['headers'], '/paid-orders', body)
    assert order['billing_state'] == 'paid_pos'
    assert post(client, case['headers'], '/paid-orders', body) == order
    return order


def ticket(client, case, order, quantity='2'):
    body = {'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': quantity, 'instruction': 'No salt'}]}
    result = post(client, case['headers'], f"/orders/{order['id']}/tickets", body)
    assert post(client, case['headers'], f"/orders/{order['id']}/tickets", body) == result
    return result


def counts(db):
    return tuple(db.connection().scalar(select(func.count()).select_from(model.__table__))
        for model in (SRMInvoice, SRMReceipt, SRMInventoryMovement, RestaurantCommand, RestaurantKitchenTicket, RestaurantKitchenLine))


def staff(db, case, role):
    headers, actor = native_actor(db, case['branch'])
    grant(db, actor, case['branch'], 'restaurant', role, db.get(PackContext, case['context']))
    return {**headers, 'X-Suite-Pack-Context': str(case['context'])}, actor


def test_paid_pos_kitchen_flow_distinct_chef_server_and_no_duplicate_money_stock(client, db, restaurant):
    case = restaurant
    order = setup_order(client, case)
    queued = ticket(client, case, order)
    chef, _ = staff(db, case, 'chef')
    server, _ = staff(db, case, 'server')
    before = counts(db)
    response = client.get(BASE+'/kitchen', headers=chef)
    assert response.status_code == 200, response.text
    assert response.json()['items'] == [queued]
    text = response.text
    for field in ('customer_id', 'invoice_id', 'sales_order_id', 'total', 'paid_amount', 'unit_price', 'receipt', 'tax'):
        assert field not in text
    preparing = post(client, chef, f"/tickets/{queued['id']}/prepare", {'request_key': str(uuid4()), 'expected_revision': 1}, 200)
    assert preparing['state'] == 'preparing'
    ready_body = {'request_key': str(uuid4()), 'expected_revision': preparing['revision']}
    ready = post(client, chef, f"/tickets/{queued['id']}/ready", ready_body, 200)
    assert post(client, chef, f"/tickets/{queued['id']}/ready", ready_body, 200) == ready
    served = post(client, server, f"/tickets/{queued['id']}/serve", {'request_key': str(uuid4()), 'expected_revision': ready['revision']}, 200)
    assert served['state'] == 'served'
    assert counts(db)[:3] == before[:3]
    response = client.get(BASE+f"/orders/{order['id']}", headers=server)
    assert response.status_code == 200, response.text
    assert response.json()['state'] == 'served'
    assert client.get(BASE+'/kitchen', headers=chef).json()['items'] == []


@pytest.mark.parametrize('fault', ['overquantity', 'foreignline', 'stale', 'changed_key'])
def test_invalid_kitchen_commands_have_no_partial_ticket(client, db, restaurant, fault):
    order = setup_order(client, restaurant)
    body = {'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '2'}]}
    if fault == 'overquantity':
        body['lines'][0]['quantity'] = '3'
    elif fault == 'foreignline':
        body['lines'][0]['sales_order_line_id'] = 9999999
    elif fault == 'stale':
        body['expected_revision'] = 999
    else:
        post(client, restaurant['headers'], f"/orders/{order['id']}/tickets", body)
        body['lines'][0]['quantity'] = '1'
    before = counts(db)
    response = client.post(BASE+f"/orders/{order['id']}/tickets", headers=restaurant['headers'], json=body)
    assert response.status_code == 409, response.text
    assert counts(db) == before


def test_cumulative_sent_quantity_and_illegal_backwards_transition(client, db, restaurant):
    case = restaurant
    order = setup_order(client, case)
    first = ticket(client, case, order, '1')
    order = client.get(BASE+f"/orders/{order['id']}", headers=case['headers']).json()
    ticket(client, case, order, '1')
    order = client.get(BASE+f"/orders/{order['id']}", headers=case['headers']).json()
    before = counts(db)
    body = {'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '0.01'}]}
    response = client.post(BASE+f"/orders/{order['id']}/tickets", headers=case['headers'], json=body)
    assert response.status_code == 409, response.text
    response = client.post(BASE+f"/tickets/{first['id']}/ready", headers=case['headers'], json={'request_key': str(uuid4()), 'expected_revision': 1})
    assert response.status_code == 409, response.text
    assert counts(db) == before


@pytest.mark.parametrize('other', [('hospital', 'doctor'), ('construction', 'site_engineer'), ('restaurant', 'cashier')])
def test_specialists_cannot_read_or_prepare_restaurant_kitchen(client, db, restaurant, other):
    order = setup_order(client, restaurant)
    queued = ticket(client, restaurant, order)
    headers, actor = native_actor(db, restaurant['branch'])
    context = db.get(PackContext, restaurant['context']) if other[0] == 'restaurant' else None
    context, _ = grant(db, actor, restaurant['branch'], *other, context)
    headers['X-Suite-Pack-Context'] = str(context.id)
    before = counts(db)
    for method, path, body in [('get', '/kitchen', None), ('post', f"/tickets/{queued['id']}/prepare", {'request_key': str(uuid4()), 'expected_revision': 1})]:
        response = getattr(client, method)(BASE+path, headers=headers, **({'json': body} if body else {}))
        assert response.status_code == 403, response.text
        assert 'No salt' not in response.text
    assert counts(db) == before


def test_chef_cannot_serve_or_read_financial_order_body(client, db, restaurant):
    order = setup_order(client, restaurant)
    queued = ticket(client, restaurant, order)
    headers, _ = staff(db, restaurant, 'chef')
    assert client.get(BASE+f"/orders/{order['id']}", headers=headers).status_code == 403
    response = client.post(BASE+f"/tickets/{queued['id']}/serve", headers=headers, json={'request_key': str(uuid4()), 'expected_revision': 1})
    assert response.status_code == 403, response.text


@pytest.mark.parametrize('fault', ['invoice_unpaid', 'receipt_reversed', 'source_changed'])
def test_native_paid_source_changes_block_kitchen_without_side_effect(client, db, restaurant, fault):
    order = setup_order(client, restaurant)
    queued = ticket(client, restaurant, order)
    if fault == 'invoice_unpaid':
        db.connection().execute(SRMInvoice.__table__.update().where(SRMInvoice.id == restaurant['checkout']['invoice']['id']).values(paid_amount=0, balance_amount=236))
    elif fault == 'receipt_reversed':
        db.connection().execute(SRMReceipt.__table__.update().where(SRMReceipt.id == restaurant['checkout']['receipts'][0]['id']).values(status='reversed'))
    else:
        db.connection().execute(SRMSalesOrderLine.__table__.update().where(SRMSalesOrderLine.id == order['items'][0]['sales_order_line_id']).values(description='Changed item source'))
    db.commit()
    before = counts(db)
    response = client.post(BASE+f"/tickets/{queued['id']}/prepare", headers=restaurant['headers'], json={'request_key': str(uuid4()), 'expected_revision': 1})
    assert response.status_code == 409, response.text
    assert counts(db) == before


def test_native_module_revocation_still_blocks_pack_manager(client, db, restaurant):
    from app.access.models import AccessPolicy
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=restaurant['manager'].id).one()
    policy.grants = {'srm': {'enabled': False}}
    db.commit()
    before = counts(db)
    response = client.post(BASE+'/tables', headers=restaurant['headers'], json={'request_key': str(uuid4()), 'name': 'Denied', 'capacity': 2})
    assert response.status_code == 403, response.text
    assert counts(db) == before


def test_fresh_capabilities_do_not_grant_chef_money_or_server_kitchen_actions(client, db, restaurant):
    chef, _ = staff(db, restaurant, 'chef')
    server, _ = staff(db, restaurant, 'server')
    for headers, expected in [(chef, {'kitchen_view', 'kitchen_prepare', 'kitchen_ready'}),
                              (server, {'tables_view', 'orders_view', 'orders_create', 'orders_serve'})]:
        response = client.get(BASE+'/capabilities', headers=headers)
        assert response.status_code == 200, response.text
        assert {key for key, value in response.json().items() if value is True} == expected
    source = client.get(BASE+f"/paid-orders/{restaurant['checkout']['id']}/source", headers=server)
    assert source.status_code == 200, source.text
    assert set(source.json()) == {'checkout_id', 'checkout_revision', 'sales_order_id', 'lines'}
    for key in ('customer', 'invoice', 'receipt', 'unit_price', 'tax', 'total', 'paid_amount'):
        assert key not in source.text
    assert client.get(BASE+f"/paid-orders/{restaurant['checkout']['id']}/source", headers=chef).status_code == 403
    assert client.get('/api/v1/srm/invoices/'+str(restaurant['checkout']['invoice']['id']), headers=chef).status_code == 403


def test_native_own_record_scope_is_not_widened_for_kitchen_role(client, db, restaurant):
    from app.access.models import AccessPolicy
    order = setup_order(client, restaurant)
    queued = ticket(client, restaurant, order)
    chef, actor = staff(db, restaurant, 'chef')
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {'srm': {'enabled': True, 'permissions': ['srm_admin'], 'actions': ['view', 'create', 'edit'], 'scope': 'own'}}
    db.commit()
    response = client.get(BASE+'/kitchen', headers=chef)
    assert response.status_code == 200, response.text
    assert response.json()['items'] == []
    before = counts(db)
    response = client.post(BASE+f"/tickets/{queued['id']}/prepare", headers=chef, json={'request_key': str(uuid4()), 'expected_revision': 1})
    assert response.status_code in (403, 404), response.text
    assert counts(db) == before


def test_native_read_only_chef_has_no_preparation_write_permission(client, db, restaurant):
    from app.access.models import AccessPolicy
    order = setup_order(client, restaurant)
    queued = ticket(client, restaurant, order)
    chef, actor = staff(db, restaurant, 'chef')
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {'srm': {'enabled': True, 'permissions': ['srm_admin'], 'actions': ['view'], 'scope': 'organization'}}
    db.commit()
    response = client.get(BASE+'/capabilities', headers=chef)
    assert response.status_code == 200, response.text
    assert response.json()['kitchen_view'] and not response.json()['kitchen_prepare'] and not response.json()['kitchen_ready']
    before = counts(db)
    response = client.post(BASE+f"/tickets/{queued['id']}/prepare", headers=chef, json={'request_key': str(uuid4()), 'expected_revision': 1})
    assert response.status_code == 403, response.text
    assert counts(db) == before


def test_same_actor_other_pack_business_owner_cannot_reinterpret_restaurant_ids(client, db, restaurant):
    order = setup_order(client, restaurant)
    queued = ticket(client, restaurant, order)
    context, _ = grant(db, restaurant['manager'], restaurant['branch'], 'hospital', 'business_owner')
    headers = {**restaurant['headers'], 'X-Suite-Pack-Context': str(context.id)}
    before = counts(db)
    for path in ['/kitchen', f"/orders/{order['id']}", f"/paid-orders/{restaurant['checkout']['id']}/source"]:
        response = client.get(BASE+path, headers=headers)
        assert response.status_code == 403, response.text
        assert 'No salt' not in response.text
    response = client.post(BASE+f"/tickets/{queued['id']}/prepare", headers=headers, json={'request_key': str(uuid4()), 'expected_revision': 1})
    assert response.status_code == 403, response.text
    assert counts(db) == before


def own_policy(db, actor):
    from app.access.models import AccessPolicy
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {'srm': {'enabled': True, 'permissions': ['srm_admin'], 'actions': ['view', 'create', 'edit', 'approve'], 'scope': 'own'}}
    db.commit()


def test_native_own_scope_cannot_hide_other_servers_already_sent_quantity(client, db, restaurant):
    order = setup_order(client, restaurant, table=False)
    other_headers, _ = staff(db, restaurant, 'restaurant_manager')
    other = {**restaurant, 'headers': other_headers}
    ticket(client, other, order, '1')
    own_policy(db, restaurant['manager'])
    response = client.get(BASE+f"/orders/{order['id']}", headers=restaurant['headers'])
    assert response.status_code == 200, response.text
    current = response.json()
    assert Decimal(current['items'][0]['sent_quantity']) == 1
    assert current['tickets'] == []  # No other server's private ticket body.
    before = counts(db)
    response = client.post(BASE+f"/orders/{order['id']}/tickets", headers=restaurant['headers'], json={
        'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': current['revision'],
        'lines': [{'sales_order_line_id': current['items'][0]['sales_order_line_id'], 'quantity': '2'}]})
    assert response.status_code == 409, response.text
    assert counts(db) == before


def test_native_own_scope_cannot_deactivate_table_occupied_by_hidden_order(client, db, restaurant):
    table = post(client, restaurant['headers'], '/tables', {'request_key': str(uuid4()), 'name': 'Shared dining table', 'capacity': 4})
    other_headers, _ = staff(db, restaurant, 'restaurant_manager')
    post(client, other_headers, '/paid-orders', {'request_key': str(uuid4()), 'checkout_id': restaurant['checkout']['id'],
        'expected_checkout_revision': restaurant['checkout']['revision'], 'table_id': table['id'], 'expected_table_revision': table['revision']})
    own_policy(db, restaurant['manager'])
    response = client.get(BASE+'/tables', headers=restaurant['headers'])
    assert response.status_code == 200, response.text
    current = response.json()['items'][0]
    assert current['occupied'] is True
    before = counts(db)
    response = client.put(BASE+f"/tables/{table['id']}", headers=restaurant['headers'], json={'request_key': str(uuid4()),
        'name': table['name'], 'capacity': 4, 'active': False, 'expected_revision': current['revision']})
    assert response.status_code == 409, response.text
    assert counts(db) == before
