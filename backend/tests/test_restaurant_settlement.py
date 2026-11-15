from decimal import Decimal
from uuid import uuid4
import pytest
from app.apps.srm.models import SRMPOSSession, SRMSalesOrder, SRMInvoice, SRMReceipt
from app.apps.srm.service_checkout_models import POSServiceCheckout
from app.business_packs.boundary import install
from app.business_packs.access import resolve_context
from app.business_packs.native_policy import native_srm_policy
from tests.test_restaurant_tabs import unpaid, scenario, catalog, directory_identity, data, stock, BASE
from tests.test_restaurant_kitchen import post, staff
from tests.test_srm_native_transaction_operations import native_writer


@pytest.fixture
def settlement(client, db, unpaid):
    case = unpaid
    with native_writer(db, case['manager'], case['branch']):
        scope = resolve_context(db, case['manager'], db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            register = SRMPOSSession(organization_id=1, session_number='TAB-'+uuid4().hex,
                status='open', cashier_user_id=case['manager'].id, created_by=case['manager'].id)
            db.add(register); db.commit()
            register_id = register.id
        finally:
            cleanup()
    table = post(client, case['headers'], '/tables', {'request_key': str(uuid4()), 'name': 'Settle', 'capacity': 2})
    order = post(client, case['headers'], '/tabs', data(case, customer_id=101,
        table_id=table['id'], expected_table_revision=table['revision']))
    ticket = post(client, case['headers'], f"/orders/{order['id']}/tickets", {
        'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '1'}]})
    order = client.get(BASE+f"/orders/{order['id']}", headers=case['headers']).json()
    return {**case, 'order': order, 'ticket': ticket, 'register': register_id}


def bill_input(case):
    return {'request_key': str(uuid4()), 'expected_revision': case['order']['revision'],
        'expected_total': '118', 'pos_session_id': case['register']}


def test_named_tab_native_invoice_partial_split_payment_and_no_second_stock(client, db, settlement):
    case = settlement
    before = stock(db, case)
    payload = bill_input(case)
    path = f"/tabs/{case['order']['id']}"
    result = post(client, case['headers'], path+'/bill', payload)
    assert post(client, case['headers'], path+'/bill', payload) == result
    assert db.query(SRMSalesOrder).count() == db.query(SRMInvoice).count() == db.query(POSServiceCheckout).count() == 1
    assert Decimal(result['checkout']['invoice']['balance']) == 118 and db.query(SRMReceipt).count() == 0
    for method, amount in [('cash', '50'), ('card', '68')]:
        payment = {'request_key': str(uuid4()), 'expected_revision': result['checkout']['revision'],
            'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': method, 'amount': amount}}
        result = post(client, case['headers'], path+'/payments', payment)
        assert post(client, case['headers'], path+'/payments', payment) == result
        assert client.get(BASE+'/tables', headers=case['headers']).json()['items'][0]['occupied'] is True
        denied = client.post(BASE+path+'/items', headers=case['headers'], json={
            'request_key': str(uuid4()), 'expected_revision': result['order_revision'], 'lines': data(case)['lines']})
        assert denied.status_code == 409, denied.text
    assert db.query(SRMReceipt).count() == 2 and Decimal(result['checkout']['invoice']['balance']) == 0
    ticket = case['ticket']
    for action in ('prepare', 'ready', 'serve'):
        ticket = post(client, case['headers'], f"/tickets/{ticket['id']}/{action}", {
            'request_key': str(uuid4()), 'expected_revision': ticket['revision']}, status=200)
    assert client.get(BASE+'/tables', headers=case['headers']).json()['items'][0]['occupied'] is False
    assert stock(db, case) == before
    response = client.post(BASE+path+'/items', headers=case['headers'], json={
        'request_key': str(uuid4()), 'expected_revision': result['order_revision'], 'lines': data(case)['lines']})
    assert response.status_code == 409, response.text


@pytest.mark.parametrize('fault', ['stale', 'total', 'closed_register', 'approve_revoke', 'unfired'])
def test_bill_failure_does_not_leave_group_invoice_or_second_stock(client, db, settlement, fault):
    from app.access.models import AccessPolicy
    case = settlement
    payload = bill_input(case)
    if fault == 'stale':
        payload['expected_revision'] = 999
    elif fault == 'total':
        payload['expected_total'] = '117.99'
    elif fault == 'closed_register':
        db.connection().execute(SRMPOSSession.__table__.update().where(SRMPOSSession.id == case['register']).values(status='closed'))
        db.commit()
    elif fault == 'approve_revoke':
        policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=case['manager'].id).one()
        policy.grants = {'srm': {'enabled': True, 'permissions': ['srm_admin'], 'actions': ['view', 'create'], 'scope': 'organization'}}
        db.commit()
    else:
        new = post(client, case['headers'], f"/tabs/{case['order']['id']}/items", {
            'request_key': str(uuid4()), 'expected_revision': case['order']['revision'], 'lines': data(case)['lines']})
        payload['expected_revision'], payload['expected_total'] = new['revision'], '236'
    before = stock(db, case)
    response = client.post(BASE+f"/tabs/{case['order']['id']}/bill", headers=case['headers'], json=payload)
    assert response.status_code == (403 if fault == 'approve_revoke' else 409), response.text
    assert db.query(SRMInvoice).count() == db.query(POSServiceCheckout).count() == db.query(SRMReceipt).count() == 0
    assert stock(db, case) == before


def test_late_native_allocation_failure_and_overpay_are_atomic(client, db, settlement, monkeypatch):
    from fastapi import HTTPException
    from app.apps.srm.api import router as native
    case = settlement
    path = f"/tabs/{case['order']['id']}"
    result = post(client, case['headers'], path+'/bill', bill_input(case))
    payload = {'request_key': str(uuid4()), 'expected_revision': result['checkout']['revision'],
        'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '119'}}
    response = client.post(BASE+path+'/payments', headers=case['headers'], json=payload)
    assert response.status_code == 422, response.text
    payload['payment']['amount'] = '50'
    def denied(*args, **kwargs):
        raise HTTPException(409, 'Actual allocation conflict')
    monkeypatch.setattr(native, 'allocate_receipt_operation', denied)
    response = client.post(BASE+path+'/payments', headers=case['headers'], json=payload)
    assert response.status_code == 409, response.text
    assert db.query(SRMReceipt).count() == 0
    assert db.query(SRMInvoice).one().paid_amount == 0


def test_chef_server_and_foreign_pack_cannot_read_or_mutate_tab_finances(client, db, settlement):
    from tests.test_business_pack_http_integration import native_actor, grant
    case = settlement
    for role in ('chef', 'server'):
        headers, _ = staff(db, case, role)
        for method, path, payload in [('GET', '/billing', None), ('POST', '/bill', bill_input(case)),
                ('POST', '/payments', {'request_key': str(uuid4()), 'expected_revision': 1,
                    'payment': {'payment_key': str(uuid4()), 'method': 'card', 'amount': '10'}})]:
            response = client.request(method, BASE+f"/tabs/{case['order']['id']}"+path, headers=headers, json=payload)
            assert response.status_code == 403, response.text
    headers, actor = native_actor(db, case['branch'])
    context, _ = grant(db, actor, case['branch'], 'hospital', 'doctor')
    headers['X-Suite-Pack-Context'] = str(context.id)
    assert client.get(BASE+f"/tabs/{case['order']['id']}/billing", headers=headers).status_code == 403


def test_walk_in_tab_requires_explicit_identity_reconciliation(client, db, unpaid):
    case = unpaid
    order = post(client, case['headers'], '/tabs', data(case))
    ticket = post(client, case['headers'], f"/orders/{order['id']}/tickets", {
        'request_key': str(uuid4()), 'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '1'}]})
    order = client.get(BASE+f"/orders/{order['id']}", headers=case['headers']).json()
    response = client.post(BASE+f"/tabs/{order['id']}/bill", headers=case['headers'], json={
        'request_key': str(uuid4()), 'expected_revision': order['revision'], 'expected_total': '118', 'pos_session_id': 999})
    assert response.status_code == 409 and 'identity assignment' in response.text, response.text
    assert db.query(SRMInvoice).count() == db.query(POSServiceCheckout).count() == 0


def test_actual_customer_picker_is_finite_scoped_and_denied_to_chef(client, db, unpaid):
    from app.apps.crm.models import CRMCompany
    from app.business_packs.models import PackMasterAvailability
    case = unpaid
    row = db.get(CRMCompany, 101)
    row.account_type = 'Customer'
    db.add(CRMCompany(organization_id=2, name='Foreign buyer', account_type='Customer'))
    db.add(CRMCompany(organization_id=1, name='Unassigned buyer', account_type='Customer'))
    db.commit()
    response = client.get(BASE+'/customers', headers=case['headers'])
    assert response.status_code == 200, response.text
    assert response.json()['items'] == [{'id': 101, 'name': row.name}]
    assert client.get(BASE+'/customers?search=%25', headers=case['headers']).json()['items'] == []
    chef, _ = staff(db, case, 'chef')
    assert client.get(BASE+'/customers', headers=chef).status_code == 403
    db.query(PackMasterAvailability).filter_by(context_id=case['context'], resource_table='crm_companies', resource_key='101').one().active = False
    db.commit()
    assert client.get(BASE+'/customers', headers=case['headers']).json()['items'] == []


def finance_actor(db, case):
    from tests.test_business_pack_http_integration import native_actor, grant
    from app.business_packs.models import PackContext
    from app.access.models import AccessPolicy
    from app.models.user import Permission
    from app.db.init_db import SYSTEM_PERMISSIONS
    headers, actor = native_actor(db, case['branch'])
    grant(db, actor, case['branch'], 'restaurant', 'cashier', db.get(PackContext, case['context']))
    names = ['srm_invoice_create', 'srm_invoice_approve', 'srm_collection_create', 'srm_collection_view']
    permissions = []
    for name in names:
        permission = db.query(Permission).filter_by(name=name).one_or_none()
        if permission is None:
            definition = next(value for value in SYSTEM_PERMISSIONS if value[0] == name)
            permission = Permission(name=name, description=definition[1], module=definition[2])
            db.add(permission)
        permissions.append(permission)
    actor.role.permissions = permissions
    db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one().grants = {
        'srm': {'enabled': True, 'permissions': names, 'actions': ['view','create','approve'], 'scope': 'organization'}}
    db.connection().execute(SRMPOSSession.__table__.update().where(SRMPOSSession.id == case['register']).values(cashier_user_id=None))
    db.commit()
    headers['X-Suite-Pack-Context'] = str(case['context'])
    return headers, actor


def test_independent_native_finance_cashier_without_order_manage_can_bill_and_collect(client, db, settlement):
    case = settlement
    headers, actor = finance_actor(db, case)
    response = client.get(BASE+'/capabilities', headers=headers)
    assert response.status_code == 200 and response.json()['billing_prepare'] is True and response.json()['orders_create'] is False, response.text
    path = f"/tabs/{case['order']['id']}"
    answer = post(client, headers, path+'/bill', bill_input(case))
    answer = post(client, headers, path+'/payments', {'request_key': str(uuid4()),
        'expected_revision': answer['checkout']['revision'], 'pos_session_id': case['register'],
        'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '118'}})
    assert Decimal(answer['checkout']['invoice']['balance']) == 0
    assert db.query(SRMReceipt).count() == 1


def test_billing_preserves_original_catalog_tax_and_detects_mapping_corruption(client, db, settlement):
    from app.apps.srm.models import SRMProduct
    from app.apps.srm.service_checkout_models import POSCheckoutLine
    from app.business_packs.restaurant.models import RestaurantTabLine
    case = settlement
    snapshot = db.query(RestaurantTabLine).one().catalog_tax_snapshot
    db.connection().execute(SRMProduct.__table__.update().where(SRMProduct.id == case['product']).values(sales_rate=Decimal('1')))
    db.commit()
    path = f"/tabs/{case['order']['id']}"
    result = post(client, case['headers'], path+'/bill', bill_input(case))
    assert Decimal(result['checkout']['invoice']['total']) == 118
    assert db.query(POSCheckoutLine).one().catalog_tax_snapshot == snapshot
    db.connection().execute(POSCheckoutLine.__table__.update().values(catalog_tax_snapshot={'forged': True}))
    db.commit()
    response = client.get(BASE+path+'/billing', headers=case['headers'])
    assert response.status_code == 409, response.text
