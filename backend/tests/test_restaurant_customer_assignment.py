from decimal import Decimal
from uuid import uuid4
import pytest
from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMSalesOrder, SRMPOSSession, SRMInvoice, SRMReceipt
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantCommand
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_restaurant_tabs import unpaid, scenario, catalog, directory_identity, data, stock, BASE
from tests.test_restaurant_kitchen import post, staff
from tests.test_srm_native_transaction_operations import native_writer


@pytest.fixture
def walkin(client, db, unpaid):
    case = unpaid
    db.get(CRMCompany, 101).account_type = 'Customer'
    db.commit()
    with native_writer(db, case['manager'], case['branch']):
        scope = resolve_context(db, case['manager'], db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            register = SRMPOSSession(organization_id=1, session_number='WALKIN-'+uuid4().hex,
                status='open', cashier_user_id=case['manager'].id, created_by=case['manager'].id)
            db.add(register); db.commit()
            register_id = register.id
        finally:
            cleanup()
    order = post(client, case['headers'], '/tabs', data(case))
    return {**case, 'order': order, 'register': register_id}


def assignment(case, **changes):
    return {'request_key': str(uuid4()), 'expected_revision': case['order']['revision'], 'customer_id': 101, **changes}


def test_independent_server_assigns_walkin_once_then_same_native_order_adds_bills_and_collects(client, db, walkin):
    case = walkin
    server, _ = staff(db, case, 'server')
    original = db.query(RestaurantServiceOrder).one().source_sha256
    before = stock(db, case)
    payload = assignment(case)
    path = f"/tabs/{case['order']['id']}"
    answer = post(client, server, path+'/customer', payload, status=200)
    assert post(client, server, path+'/customer', payload, status=200) == answer
    order = client.get(BASE+f"/orders/{answer['id']}", headers=server).json()
    assert order['customer_assigned'] is True
    order = post(client, server, path+'/items', {'request_key': str(uuid4()), 'expected_revision': order['revision'], 'lines': data(case)['lines']})
    post(client, server, f"/orders/{order['id']}/tickets", {'request_key': str(uuid4()),
        'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': line['sales_order_line_id'], 'quantity': '1'} for line in order['items']]})
    order = client.get(BASE+f"/orders/{order['id']}", headers=case['headers']).json()
    billed = post(client, case['headers'], path+'/bill', {'request_key': str(uuid4()),
        'expected_revision': order['revision'], 'expected_total': '236', 'pos_session_id': case['register']})
    paid = post(client, case['headers'], path+'/payments', {'request_key': str(uuid4()),
        'expected_revision': billed['checkout']['revision'], 'pos_session_id': case['register'],
        'payment': {'payment_key': str(uuid4()), 'method': 'card', 'amount': '236'}})
    assert Decimal(paid['checkout']['invoice']['balance']) == 0
    assert db.query(SRMSalesOrder).count() == db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 1
    assert db.query(SRMSalesOrder).one().customer_id == 101
    assert db.query(RestaurantServiceOrder).one().source_sha256 == original
    assert db.query(RestaurantCommand).filter_by(action='tab.assign_customer').count() == 1
    assert stock(db, case) == before-2
    response = client.post(BASE+path+'/customer', headers=server, json=assignment(case, expected_revision=order['revision']))
    assert response.status_code == 409, response.text


@pytest.mark.parametrize('fault', ['stale', 'foreign_company', 'unassigned', 'supplier', 'forged_fields'])
def test_assignment_denials_preserve_actual_native_null_customer(client, db, walkin, fault):
    case = walkin
    payload = assignment(case)
    if fault == 'stale':
        payload['expected_revision'] = 999
    elif fault in ('foreign_company', 'unassigned', 'supplier'):
        row = CRMCompany(organization_id=2 if fault == 'foreign_company' else 1,
            name='Unavailable named customer', account_type='Supplier' if fault == 'supplier' else 'Customer')
        db.add(row); db.commit()
        payload['customer_id'] = row.id
        if fault != 'unassigned':
            from app.business_packs.models import PackMasterAvailability
            db.add(PackMasterAvailability(company_id=1, branch_id=case['branch'], context_id=case['context'],
                resource_table='crm_companies', resource_key=str(row.id), active=True))
            db.commit()
    else:
        payload['total_amount'] = '1'
    response = client.post(BASE+f"/tabs/{case['order']['id']}/customer", headers=case['headers'], json=payload)
    assert response.status_code == (409 if fault == 'stale' else 422 if fault == 'forged_fields' else 404), response.text
    assert db.query(SRMSalesOrder).one().customer_id is None
    assert db.query(RestaurantCommand).filter_by(action='tab.assign_customer').count() == 0


def test_uncommanded_customer_change_and_corrupted_transition_fail_source_proof(client, db, walkin):
    case = walkin
    source = db.query(SRMSalesOrder).one()
    db.connection().execute(SRMSalesOrder.__table__.update().where(SRMSalesOrder.id == source.id).values(customer_id=101))
    db.commit()
    response = client.get(BASE+f"/orders/{case['order']['id']}", headers=case['headers'])
    assert response.status_code == 409, response.text


def test_assignment_requires_both_restaurant_role_and_native_order_authority(client, db, walkin):
    from app.access.models import AccessPolicy
    from tests.test_restaurant_settlement import finance_actor
    case = walkin
    cashier, _ = finance_actor(db, case)
    chef, _ = staff(db, case, 'chef')
    for headers in (cashier, chef):
        response = client.post(BASE+f"/tabs/{case['order']['id']}/customer", headers=headers, json=assignment(case))
        assert response.status_code == 403, response.text
    server, actor = staff(db, case, 'server')
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {'srm': {'enabled': True, 'permissions': ['srm_collection_create'], 'actions': ['view','create'], 'scope': 'organization'}}
    db.commit()
    response = client.post(BASE+f"/tabs/{case['order']['id']}/customer", headers=server, json=assignment(case))
    assert response.status_code == 403, response.text
    assert db.query(SRMSalesOrder).one().customer_id is None


@pytest.mark.parametrize('fault', ['money', 'terms', 'assignee', 'line'])
def test_customer_binding_lease_cannot_edit_other_source_fields(client, db, walkin, monkeypatch, fault):
    from contextlib import contextmanager
    from app.business_packs.restaurant import references
    case = walkin
    original = references.customer_update
    @contextmanager
    def poisoned(db, actor, scope, epoch, native, order, selected):
        with original(db, actor, scope, epoch, native, order, selected):
            if fault == 'money':
                native.total_amount = 1
            elif fault == 'terms':
                native.terms = 'Forged unrelated source edit'
            elif fault == 'assignee':
                native.assigned_user_id = 999999
            else:
                native.lines[0].quantity = 2
            yield
    monkeypatch.setattr(references, 'customer_update', poisoned)
    response = client.post(BASE+f"/tabs/{case['order']['id']}/customer", headers=case['headers'], json=assignment(case))
    assert response.status_code == 403, response.text
    source = db.query(SRMSalesOrder).one()
    assert source.customer_id is None and source.total_amount == Decimal('118')
    assert db.query(RestaurantCommand).filter_by(action='tab.assign_customer').count() == 0 and not references._leases


def test_transition_command_and_customer_reference_cannot_be_rewritten(client, db, walkin):
    case = walkin
    post(client, case['headers'], f"/tabs/{case['order']['id']}/customer", assignment(case), status=200)
    command = db.query(RestaurantCommand).filter_by(action='tab.assign_customer').one()
    db.connection().execute(RestaurantCommand.__table__.update().where(RestaurantCommand.id == command.id).values(
        result={**command.result, 'previous_customer_id': 101}))
    db.commit()
    response = client.get(BASE+f"/orders/{case['order']['id']}", headers=case['headers'])
    assert response.status_code == 409, response.text


def test_register_picker_uses_real_labels_and_excludes_other_cashier_closed_sessions(client, db, walkin):
    case = walkin
    other, actor = staff(db, case, 'server')
    actor_id = actor.id
    with native_writer(db, actor, case['branch']):
        scope = resolve_context(db, actor, db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            db.add(SRMPOSSession(organization_id=1, session_number='OTHER-'+uuid4().hex,
                status='open', cashier_user_id=actor_id, created_by=actor_id))
            db.commit()
        finally:
            cleanup()
    with native_writer(db, case['manager'], case['branch']):
        scope = resolve_context(db, case['manager'], db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            db.add(SRMPOSSession(organization_id=1, session_number='CLOSED-'+uuid4().hex,
                status='closed', cashier_user_id=case['manager'].id, created_by=case['manager'].id))
            db.commit()
        finally:
            cleanup()
    response = client.get(BASE+'/registers', headers=case['headers'])
    assert response.status_code == 200, response.text
    assert response.json()['items'] == [{'id': case['register'], 'label': db.get(SRMPOSSession, case['register']).session_number+' · My register'}]
    assert all(key not in response.text for key in ('opening_cash','closing_cash','cash_received','cashier_user_id'))
    chef, _ = staff(db, case, 'chef')
    assert client.get(BASE+'/registers', headers=chef).status_code == 403
