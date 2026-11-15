"""Unpaid native tabs: append items, fire stock once, cook before payment."""
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from fastapi import HTTPException
from app.apps.srm.models import SRMProduct, SRMInventoryBalance, SRMInventoryMovement, SRMSalesOrder, SRMSalesOrderLine, SRMInvoice, SRMReceipt
from app.apps.srm.service_checkout_models import POSServiceCheckout
from app.business_packs.models import PackMasterAvailability, PackContext
from app.business_packs.restaurant.models import MODELS, RestaurantServiceOrder, RestaurantTabLine, RestaurantKitchenIssue
from app.business_packs.restaurant import tabs
from app.business_packs.restaurant.schemas import TabCreate, TabAdd
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_business_pack_http_integration import native_actor, grant
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer
from tests.test_restaurant_kitchen import post, counts, staff

BASE = '/api/v1/srm/restaurant'


@pytest.fixture
def unpaid(client, db, scenario):
    _, branch, catalog, _ = scenario
    for model in MODELS:
        model.__table__.create(db.bind, checkfirst=True)
    headers, actor = native_actor(db, branch)
    context, _ = grant(db, actor, branch, 'restaurant', 'restaurant_manager')
    for table, ident in [('srm_products', catalog[2][0]), ('srm_warehouses', catalog[1]), ('crm_companies', 101)]:
        db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context.id, resource_table=table, resource_key=str(ident), active=True))
    db.commit()
    return {'headers': {**headers, 'X-Suite-Pack-Context': str(context.id)}, 'manager': actor, 'context': context.id,
        'branch': branch, 'product': catalog[2][0], 'warehouse': catalog[1]}


def data(case, **changes):
    return {'request_key': str(uuid4()), 'lines': [{'product_id': case['product'], 'quantity': '1', 'expected_unit_price': '100'}], **changes}


def stock(db, case):
    table = SRMInventoryBalance.__table__
    return db.connection().scalar(select(table.c.quantity).where(table.c.product_id == case['product'], table.c.warehouse_id == case['warehouse']))


def nothing_billed(db):
    return tuple(db.connection().scalar(select(func.count()).select_from(model.__table__)) for model in (SRMInvoice, SRMReceipt, POSServiceCheckout))


def send_items(client, case, order, quantity='1'):
    return post(client, case['headers'], f"/orders/{order['id']}/tickets", {'request_key': str(uuid4()),
        'service_order_id': order['id'], 'expected_revision': order['revision'], 'lines': [
            {'sales_order_line_id': order['items'][-1]['sales_order_line_id'], 'quantity': quantity, 'instruction': 'No salt'}]})


def test_genuine_unpaid_tab_additions_kitchen_and_serving_keep_table_open_without_invoice(client, db, unpaid):
    case = unpaid
    table = post(client, case['headers'], '/tables', {'request_key': str(uuid4()), 'name': 'Before payment', 'capacity': 4})
    initial = data(case, table_id=table['id'], expected_table_revision=table['revision'])
    before = stock(db, case)
    order = post(client, case['headers'], '/tabs', initial)
    assert order['checkout_id'] is None and order['billing_state'] == 'unpaid_tab'
    assert Decimal(order['total']) == 118 and stock(db, case) == before
    assert nothing_billed(db) == (0, 0, 0)
    assert post(client, case['headers'], '/tabs', initial) == order
    add = {'request_key': str(uuid4()), 'expected_revision': order['revision'], 'lines': initial['lines']}
    added = post(client, case['headers'], f"/tabs/{order['id']}/items", add)
    assert Decimal(added['total']) == 236 and len(added['items']) == 2
    assert post(client, case['headers'], f"/tabs/{order['id']}/items", add) == added
    assert stock(db, case) == before and db.query(RestaurantTabLine).count() == 2
    queued = send_items(client, case, added)
    assert stock(db, case) == before-1 and db.query(RestaurantKitchenIssue).count() == 1
    chef, _ = staff(db, case, 'chef')
    waiter, _ = staff(db, case, 'server')
    preparing = post(client, chef, f"/tickets/{queued['id']}/prepare", {'request_key': str(uuid4()), 'expected_revision': 1}, 200)
    ready = post(client, chef, f"/tickets/{queued['id']}/ready", {'request_key': str(uuid4()), 'expected_revision': preparing['revision']}, 200)
    post(client, waiter, f"/tickets/{queued['id']}/serve", {'request_key': str(uuid4()), 'expected_revision': ready['revision']}, 200)
    current = client.get(BASE+f"/orders/{order['id']}", headers=case['headers'])
    assert current.status_code == 200, current.text
    assert current.json()['state'] == 'open' and current.json()['billing_state'] == 'unpaid_tab'
    tables = client.get(BASE+'/tables', headers=case['headers']).json()['items']
    assert tables[0]['occupied'] is True
    more = post(client, case['headers'], f"/tabs/{order['id']}/items", {
        'request_key': str(uuid4()), 'expected_revision': current.json()['revision'], 'lines': initial['lines']})
    assert len(more['items']) == 3 and Decimal(more['total']) == 354
    assert nothing_billed(db) == (0, 0, 0) and stock(db, case) == before-1
    assert db.query(SRMSalesOrder).count() == 1 and db.query(SRMSalesOrderLine).count() == 3


@pytest.mark.parametrize('fault', ['stale', 'price', 'unavailable', 'tracked', 'missing_warehouse', 'capacity'])
def test_unpaid_add_rejections_are_atomic(client, db, unpaid, fault):
    case = unpaid
    order = post(client, case['headers'], '/tabs', data(case))
    body = {'request_key': str(uuid4()), 'expected_revision': order['revision'], 'lines': data(case)['lines']}
    if fault == 'stale':
        body['expected_revision'] = 999
    elif fault == 'price':
        body['lines'][0]['expected_unit_price'] = '1'
    elif fault == 'unavailable':
        row = db.query(PackMasterAvailability).filter_by(context_id=case['context'], resource_table='srm_products').one()
        row.active = False
    elif fault == 'tracked':
        db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id == case['product']).values(batch_tracking=True))
    elif fault == 'missing_warehouse':
        db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id == case['product']).values(default_warehouse_id=None))
    else:
        body['lines'][0]['quantity'] = '1000000000'
        db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id == case['product']).values(sales_rate=Decimal('99999999999')))
        body['lines'][0]['expected_unit_price'] = '99999999999'
    db.commit()
    before = db.query(SRMSalesOrderLine).count(), db.query(RestaurantTabLine).count(), counts(db), stock(db, case)
    response = client.post(BASE+f"/tabs/{order['id']}/items", headers=case['headers'], json=body)
    expected = {'stale': 409, 'price': 409, 'unavailable': 404, 'tracked': 409, 'missing_warehouse': 422, 'capacity': 422}[fault]
    assert response.status_code == expected, response.text
    assert (db.query(SRMSalesOrderLine).count(), db.query(RestaurantTabLine).count(), counts(db), stock(db, case)) == before


def test_late_stock_failure_rolls_back_ticket_and_native_movement(client, db, unpaid, monkeypatch):
    case = unpaid
    order = post(client, case['headers'], '/tabs', data(case))
    import app.apps.srm.services.commercial_numbering as numbering
    def conflict(*args, **kwargs):
        raise HTTPException(409, 'Native movement numbering conflict')
    monkeypatch.setattr(numbering, 'reserve_number', conflict)
    before = counts(db), stock(db, case)
    response = client.post(BASE+f"/orders/{order['id']}/tickets", headers=case['headers'], json={
        'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '1'}]})
    assert response.status_code == 409, response.text
    assert (counts(db), stock(db, case)) == before and db.query(RestaurantKitchenIssue).count() == 0


@pytest.mark.parametrize('key,role', [('hospital', 'doctor'), ('construction', 'site_engineer'), ('restaurant', 'chef')])
def test_specialists_cannot_create_or_add_unpaid_tabs(client, db, unpaid, key, role):
    case = unpaid
    order = post(client, case['headers'], '/tabs', data(case))
    headers, actor = native_actor(db, case['branch'])
    context = db.get(PackContext, case['context']) if key == 'restaurant' else None
    context, _ = grant(db, actor, case['branch'], key, role, context)
    headers['X-Suite-Pack-Context'] = str(context.id)
    before = counts(db), db.query(SRMSalesOrderLine).count(), stock(db, case)
    for path, body in [('/tabs', data(case)), (f"/tabs/{order['id']}/items", {
        'request_key': str(uuid4()), 'expected_revision': order['revision'], 'lines': data(case)['lines']})]:
        response = client.post(BASE+path, headers=headers, json=body)
        assert response.status_code == 403, response.text
    assert (counts(db), db.query(SRMSalesOrderLine).count(), stock(db, case)) == before


def test_public_metadata_cannot_create_deferred_native_stock_authority(db, unpaid):
    from app.apps.srm.api.router import create_sales_order_operation
    from app.apps.srm.schemas import SRMSalesOrderCreate
    case = unpaid
    with native_writer(db, case['manager'], case['branch']):
        scope = resolve_context(db, case['manager'], db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            assert tabs.native_creation(db, case['manager'], SRMSalesOrderCreate(title='Forged')) is False
            with pytest.raises(HTTPException) as denied:
                create_sales_order_operation(SRMSalesOrderCreate(title='Forged public source', metadata_json={'source': 'restaurant_tab'},
                    lines=[{'product_id': case['product'], 'quantity': 1, 'unit_price': 1}]), db, case['manager'], commit=False)
            assert denied.value.status_code == 409
            assert db.query(SRMSalesOrder).count() == 0
        finally:
            cleanup()


@pytest.mark.parametrize('fault', ['copied_input', 'mutated_input', 'mutated_source', 'other_actor'])
def test_native_creation_lease_is_bound_to_exact_new_source_and_input(db, unpaid, fault):
    from app.apps.srm.schemas import SRMSalesOrderCreate
    case = unpaid
    with native_writer(db, case['manager'], case['branch']):
        scope = resolve_context(db, case['manager'], db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            scope, epoch = tabs.writer(db, case['manager'])
            row = RestaurantServiceOrder(organization_id=1, branch_id=case['branch'], pack_context_id=case['context'],
                created_by=case['manager'].id, source_kind='unpaid_tab', checkout_id=None, state='open', revision=1, source_sha256='0'*64)
            payload = SRMSalesOrderCreate(title='Certified tab', metadata_json={'source': 'restaurant_tab'})
            with tabs._creation(db, case['manager'], scope, epoch, row, payload):
                candidate, actor = payload, case['manager']
                if fault == 'copied_input':
                    candidate = payload.model_copy(deep=True)
                elif fault == 'mutated_input':
                    payload.title = 'Changed after certificate'
                elif fault == 'mutated_source':
                    row.branch_id = 999
                else:
                    from types import SimpleNamespace
                    actor = SimpleNamespace(id=case['manager'].id)
                with pytest.raises(HTTPException) as denied:
                    tabs.native_creation(db, actor, candidate)
                assert denied.value.status_code == 403
        finally:
            cleanup()


def test_fractional_native_prices_and_snapshot_tampering(client, db, unpaid):
    case = unpaid
    db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id == case['product']).values(sales_rate=Decimal('99.99')))
    db.commit()
    payload = data(case)
    payload['lines'][0] |= {'quantity': '1.25', 'expected_unit_price': '99.99'}
    order = post(client, case['headers'], '/tabs', payload)
    assert Decimal(order['total']) == Decimal('147.49')
    native_line = order['items'][0]['sales_order_line_id']
    db.connection().execute(SRMSalesOrderLine.__table__.update().where(SRMSalesOrderLine.id == native_line).values(unit_price=Decimal('1')))
    db.commit()
    response = client.get(BASE+f"/orders/{order['id']}", headers=case['headers'])
    assert response.status_code == 409, response.text


def test_empty_tab_cannot_change_occupied_table_or_create_native_sources(client, db, unpaid):
    case = unpaid
    table = post(client, case['headers'], '/tables', {'request_key': str(uuid4()), 'name': 'Occupied unpaid', 'capacity': 2})
    order = post(client, case['headers'], '/tabs', data(case, table_id=table['id'], expected_table_revision=table['revision']))
    before = counts(db), stock(db, case), db.query(SRMSalesOrder).count()
    response = client.post(BASE+'/tabs', headers=case['headers'], json={'request_key': str(uuid4()), 'lines': [],
        'table_id': table['id'], 'expected_table_revision': table['revision']})
    assert response.status_code == 422, response.text
    assert (counts(db), stock(db, case), db.query(SRMSalesOrder).count()) == before
    assert client.get(BASE+'/tables', headers=case['headers']).json()['items'][0]['occupied'] is True
    assert client.get(BASE+'/tabs', headers=case['headers']).json()['items'] == [
        {'id': order['id'], 'revision': order['revision'], 'table_id': table['id'], 'state': 'open'}]


def test_native_create_without_financial_approval_can_take_unpaid_orders(client, db, unpaid):
    from app.access.models import AccessPolicy
    case = unpaid
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=case['manager'].id).one()
    policy.grants = {'srm': {'enabled': True, 'permissions': ['srm_admin'], 'actions': ['view', 'create'], 'scope': 'organization'}}
    db.commit()
    order = post(client, case['headers'], '/tabs', data(case))
    assert order['billing_state'] == 'unpaid_tab' and nothing_billed(db) == (0, 0, 0)
    response = client.post('/api/v1/srm/service-checkout', headers=case['headers'], json={
        'request_id': str(uuid4()), 'customer_id': 101, 'pos_session_id': 999999,
        'lines': [{'client_line_key': str(uuid4()), 'line_kind': 'product', 'product_id': case['product'], 'quantity': '1'}],
        'payments': [{'payment_key': str(uuid4()), 'method': 'cash', 'amount': '118'}]})
    assert response.status_code == 403, response.text
    assert nothing_billed(db) == (0, 0, 0)


def test_collection_only_cashier_can_view_finite_tabs_without_manage_permission(client, db, unpaid):
    from app.access.models import AccessPolicy
    from app.models.user import Permission
    from app.branches.models import BranchGrant
    case = unpaid
    order = post(client, case['headers'], '/tabs', data(case))
    headers, actor = native_actor(db, case['branch'], actions=('view',))
    grant(db, actor, case['branch'], 'restaurant', 'cashier', db.get(PackContext, case['context']))
    permission = db.query(Permission).filter_by(name='srm_collection_view').one_or_none()
    if permission is None:
        from app.db.init_db import SYSTEM_PERMISSIONS
        definition = next(value for value in SYSTEM_PERMISSIONS if value[0] == 'srm_collection_view')
        permission = Permission(name=definition[0], description=definition[1], module=definition[2])
        db.add(permission)
    actor.role.permissions = [permission]
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {'srm': {'enabled': True, 'permissions': ['srm_collection_view'], 'actions': ['view'], 'scope': 'organization'}}
    branch = db.query(BranchGrant).filter_by(company_id=1, branch_id=case['branch'], user_id=actor.id).one()
    branch.can_write = False
    db.commit()
    headers['X-Suite-Pack-Context'] = str(case['context'])
    response = client.get(BASE+'/tabs', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['items'] == [{'id': order['id'], 'revision': order['revision'], 'table_id': None, 'state': 'open'}]
    assert all(key not in response.text for key in ('unit_price', 'tax', 'customer', 'cost', 'receipt'))
    response = client.get(BASE+'/capabilities', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['orders_view'] is True and response.json()['orders_create'] is False
    response = client.post(BASE+'/tabs', headers=headers, json=data(case))
    assert response.status_code == 403, response.text
