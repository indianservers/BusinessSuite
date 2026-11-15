"""Competing kitchen commands use actual independent committed PG transactions."""
from uuid import uuid4
from sqlalchemy import event
from tests.test_pms_workflow_postgresql import live, race
from tests.test_business_suite_pos_concurrency import seed
from tests.test_business_pack_http_integration import native_actor, grant
from tests.test_srm_native_transaction_operations import native_writer
from tests.srm_test_utils import seed_invoice_parties
from app.apps.srm.models import SRMProduct, SRMPOSSession, SRMInventoryMovement, SRMInvoice, SRMReceipt
from app.branches.models import BranchOwnership
from app.business_packs.models import PackMasterAvailability
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from app.business_packs.restaurant.models import RestaurantKitchenTicket, RestaurantKitchenLine

BASE = '/api/v1/srm/restaurant'


def configured(live, *, unpaid=False, customer=None):
    @event.listens_for(live.engine, 'checkout')
    def test_budget(connection, record, proxy):
        cursor = connection.cursor()
        try:
            cursor.execute("SET lock_timeout='20000ms'")
            cursor.execute("SET statement_timeout='30000ms'")
        finally:
            cursor.close()
    product = seed(live)
    with live.factory() as db:
        warehouse = db.get(SRMProduct, product).default_warehouse_id
        branch = db.query(BranchOwnership).filter_by(company_id=1, resource_table='srm_warehouses', resource_key=str(warehouse)).one().branch_id
        seed_invoice_parties(db)
        headers, actor = native_actor(db, branch)
        context, _ = grant(db, actor, branch, 'restaurant', 'restaurant_manager')
        for table, ident in [('srm_products', product), ('srm_warehouses', warehouse), ('crm_companies', 101)]:
            db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context.id, resource_table=table, resource_key=str(ident), active=True))
        db.commit()
        with native_writer(db, actor, branch):
            scope = resolve_context(db, actor, db.info['branch_context'], context.id)
            cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
            try:
                register = SRMPOSSession(organization_id=1, session_number='KITCHEN-RACE-'+uuid4().hex, status='open', cashier_user_id=actor.id, created_by=actor.id)
                db.add(register)
                db.commit()
                register_id = register.id
            finally:
                cleanup()
        headers = {**headers, 'X-Suite-Pack-Context': str(context.id)}
    if unpaid:
        response = live.client.post(BASE+'/tabs', headers=headers, json={'request_key': str(uuid4()),
            **({'customer_id': customer} if customer is not None else {}),
            'lines': [{'product_id': product, 'quantity': '1', 'expected_unit_price': '100'}]})
        assert response.status_code == 201, response.text
        return headers, response.json()
    response = live.client.post('/api/v1/srm/service-checkout', headers=headers, json={
        'request_id': str(uuid4()), 'customer_id': 101, 'pos_session_id': register_id,
        'lines': [{'client_line_key': str(uuid4()), 'line_kind': 'product', 'product_id': product, 'quantity': '1'}],
        'payments': [{'payment_key': str(uuid4()), 'method': 'cash', 'amount': '118'}]})
    assert response.status_code == 201, response.text
    checkout = response.json()
    response = live.client.post(BASE+'/paid-orders', headers=headers, json={'request_key': str(uuid4()),
        'checkout_id': checkout['id'], 'expected_checkout_revision': checkout['revision']})
    assert response.status_code == 201, response.text
    return headers, response.json()


def test_concurrent_kitchen_send_cannot_fire_the_last_item_twice(live):
    headers, order = configured(live)
    def call():
        return live.client.post(BASE+f"/orders/{order['id']}/tickets", headers=headers, json={
            'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
            'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '1'}]})
    results = race(call, call)
    assert sorted(response.status_code for response in results) == [201, 409], [response.text for response in results]
    with live.factory() as db:
        assert db.query(RestaurantKitchenTicket).count() == db.query(RestaurantKitchenLine).count() == 1
        assert db.query(RestaurantKitchenLine).one().quantity == 1
        assert db.query(SRMInventoryMovement).filter_by(movement_type='pos_sale').count() == 1
        assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 1


def test_concurrent_exact_kitchen_replay_returns_one_ticket(live):
    headers, order = configured(live)
    body = {'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '1'}]}
    call = lambda: live.client.post(BASE+f"/orders/{order['id']}/tickets", headers=headers, json=body)
    results = race(call, call)
    assert [response.status_code for response in results] == [201, 201], [response.text for response in results]
    assert results[0].json() == results[1].json()
    with live.factory() as db:
        assert db.query(RestaurantKitchenTicket).count() == db.query(RestaurantKitchenLine).count() == 1
