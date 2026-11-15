from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException

from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine, SRMInvoice, SRMReceipt, SRMPOSCashierClosing, SRMReceiptAllocation
from app.apps.srm.service_checkout_models import POSServiceCheckout
from app.business_packs.restaurant.split_models import RestaurantBillGroup, RestaurantBillLine, RestaurantBillIssue, RestaurantBillReceipt
from tests.test_restaurant_settlement import settlement, bill_input, unpaid, scenario, catalog, directory_identity
from tests.test_restaurant_kitchen import post
from tests.test_restaurant_tabs import BASE, stock
from tests.test_restaurant_customer_assignment import walkin


@pytest.fixture(autouse=True)
def split_sql_guards(db):
    if db.bind.dialect.name != 'sqlite':
        return
    from tests.test_restaurant_split_migration import migration
    if not db.connection().exec_driver_sql("SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='rest_split_0_insert'").first():
        migration().install_guards(db.connection())


def body(case, quantity='.5', total='59'):
    return {'request_key': str(uuid4()), 'expected_revision': case['order']['revision'], 'expected_total': total,
        'lines': [{'sales_order_line_id': case['order']['items'][0]['sales_order_line_id'], 'quantity': quantity}]}


def test_two_quantity_bills_share_original_order_and_keep_independent_native_balances(client, db, settlement):
    case = settlement
    initial_stock = stock(db, case)
    path = f"/tabs/{case['order']['id']}"
    payload = body(case)
    first = post(client, case['headers'], path+'/bills', payload)
    assert post(client, case['headers'], path+'/bills', payload) == first
    case['order']['revision'] = first['order_revision']
    second = post(client, case['headers'], path+'/bills', body(case))
    assert first['invoice_id'] != second['invoice_id']
    assert db.query(SRMSalesOrder).count() == 1 and db.query(SRMSalesOrderLine).one().quantity == 1
    assert db.query(SRMInvoice).count() == 2 and db.query(POSServiceCheckout).count() == 0
    assert sum(row.total_amount for row in db.query(SRMInvoice)) == Decimal('118')
    listed = client.get(BASE+path+'/bills', headers=case['headers'])
    assert listed.status_code == 200, listed.text
    assert [Decimal(row['balance']) for row in listed.json()['bills']] == [59, 59]
    assert stock(db, case) == initial_stock
    whole = client.post(BASE+path+'/bill', headers=case['headers'], json={**bill_input(case), 'expected_revision': second['order_revision']})
    assert whole.status_code == 409, whole.text
    payment = {'request_key': str(uuid4()), 'expected_revision': second['order_revision'], 'expected_balance': '59',
        'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '20'}}
    paid = post(client, case['headers'], path+f"/bills/{first['bill_id']}/payments", payment)
    assert post(client, case['headers'], path+f"/bills/{first['bill_id']}/payments", payment) == paid
    assert Decimal(paid['bill']['balance']) == 39 and db.query(SRMReceipt).count() == 1
    listed = client.get(BASE+path+'/bills', headers=case['headers']).json()
    assert [Decimal(row['balance']) for row in listed['bills']] == [39, 59]
    for bill, method, amount in [(first, 'card', '39'), (second, 'cash', '59')]:
        payment = {'request_key': str(uuid4()), 'expected_revision': listed['order_revision'], 'expected_balance': amount,
            'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': method, 'amount': amount}}
        result = post(client, case['headers'], path+f"/bills/{bill['bill_id']}/payments", payment)
        assert Decimal(result['bill']['balance']) == 0
        listed = client.get(BASE+path+'/bills', headers=case['headers']).json()
    assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 3
    closed = client.post('/api/v1/srm/pos/cashier-closing', headers=case['headers'], json={'session_id': case['register'], 'counted_cash': '79'})
    assert closed.status_code == 201, closed.text
    assert Decimal(str(closed.json()['closing']['cash_sales'])) == 79
    assert Decimal(str(closed.json()['closing']['variance'])) == 0
    assert db.query(SRMPOSCashierClosing).count() == 1 and stock(db, case) == initial_stock
    historical = client.get(BASE+path+'/bills', headers=case['headers'])
    assert historical.status_code == 200, historical.text
    assert [Decimal(row['balance']) for row in historical.json()['bills']] == [0, 0]


@pytest.mark.parametrize('fault', ['revision', 'total', 'quantity', 'foreign_line'])
def test_split_failure_preserves_original_graph(client, db, settlement, fault):
    case = settlement
    payload = body(case)
    if fault == 'revision': payload['expected_revision'] += 1
    if fault == 'total': payload['expected_total'] = '58.99'
    if fault == 'quantity': payload['lines'][0]['quantity'] = '1.01'
    if fault == 'foreign_line': payload['lines'][0]['sales_order_line_id'] += 9999
    response = client.post(BASE+f"/tabs/{case['order']['id']}/bills", headers=case['headers'], json=payload)
    assert response.status_code == 409, response.text
    assert db.query(RestaurantBillGroup).count() == db.query(RestaurantBillLine).count() == db.query(SRMInvoice).count() == 0
    assert db.query(SRMSalesOrderLine).one().quantity == 1


def test_existing_whole_invoice_rejects_split_without_new_native_sources(client, db, settlement):
    case = settlement
    whole = post(client, case['headers'], f"/tabs/{case['order']['id']}/bill", bill_input(case))
    case['order']['revision'] = whole['order_revision']
    response = client.post(BASE+f"/tabs/{case['order']['id']}/bills", headers=case['headers'], json=body(case))
    assert response.status_code == 409, response.text
    assert db.query(SRMInvoice).count() == 1 and db.query(RestaurantBillGroup).count() == 0


def test_split_uuid_conflict_overbilling_and_frozen_source_edits_are_rejected(client, db, settlement):
    from tests.test_restaurant_tabs import data
    case = settlement
    path = f"/tabs/{case['order']['id']}"
    payload = body(case)
    first = post(client, case['headers'], path+'/bills', payload)
    changed = {**payload, 'expected_total': '118', 'lines': [{**payload['lines'][0], 'quantity': '1'}]}
    assert client.post(BASE+path+'/bills', headers=case['headers'], json=changed).status_code == 409
    case['order']['revision'] = first['order_revision']
    excess = client.post(BASE+path+'/bills', headers=case['headers'], json=body(case, '.51', '60.18'))
    assert excess.status_code == 409, excess.text
    added = client.post(BASE+path+'/items', headers=case['headers'], json={
        'request_key': str(uuid4()), 'expected_revision': first['order_revision'], 'lines': data(case)['lines']})
    assert added.status_code == 409, added.text
    table = post(client, case['headers'], '/tables', {'request_key': str(uuid4()), 'name': 'Allocated transfer denied', 'capacity': 2})
    moved = client.post(BASE+path+'/transfer', headers=case['headers'], json={
        'request_key': str(uuid4()), 'expected_revision': first['order_revision'], 'destination_table_id': table['id'],
        'expected_destination_revision': table['revision']})
    assert moved.status_code == 409, moved.text
    assert db.query(SRMInvoice).count() == 1 and db.query(SRMSalesOrderLine).one().quantity == 1


def test_chef_cannot_borrow_hospital_financial_assignment_for_split_bills(client, db, settlement):
    from tests.test_business_pack_http_integration import grant
    from app.business_packs.models import PackUserGrant
    case = settlement
    first = post(client, case['headers'], f"/tabs/{case['order']['id']}/bills", body(case))
    grant(db, case['manager'], case['branch'], 'hospital', 'hospital_manager')
    own = db.query(PackUserGrant).filter_by(context_id=case['context'], user_id=case['manager'].id).one()
    own.role = 'chef'; db.commit()
    path = BASE+f"/tabs/{case['order']['id']}/bills"
    assert client.get(path, headers=case['headers']).status_code == 403
    assert client.get(path+f"/{first['bill_id']}", headers=case['headers']).status_code == 403
    assert client.post(path, headers=case['headers'], json=body(case)).status_code == 403
    response = client.post(path+f"/{first['bill_id']}/payments", headers=case['headers'], json={
        'request_key': str(uuid4()), 'expected_revision': first['order_revision'], 'expected_balance': '59',
        'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '59'}})
    assert response.status_code == 403, response.text
    assert db.query(SRMReceipt).count() == 0


@pytest.fixture
def fresh_http(client, db, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app.main import app
    from app.core.deps import get_db
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, join_transaction_mode='create_savepoint')
    def request(method, path, headers, payload=None):
        with factory() as fresh, monkeypatch.context() as patch:
            def dependency():
                try:
                    yield fresh
                except BaseException:
                    fresh.rollback()
                    raise
            patch.setitem(app.dependency_overrides, get_db, dependency)
            for name, value in {'business_os_session_factory': lambda: fresh, 'business_os_close_session': False,
                    'audit_session_factory': lambda: fresh, 'audit_close_session': False, 'audit_commit': False}.items():
                patch.setattr(app.state, name, value)
            return client.request(method, BASE+path, headers=headers, json=payload)
    return request


def test_late_invoice_failure_rolls_back_all_allocations_and_same_uuid_retries(client, db, settlement, monkeypatch, fresh_http):
    from app.apps.srm.api import router as native
    case = settlement
    payload = body(case)
    path = f"/tabs/{case['order']['id']}/bills"
    original = native.approve_invoice_operation
    def reject(*args, **kwargs): raise HTTPException(409, 'Injected native approval failure')
    monkeypatch.setattr(native, 'approve_invoice_operation', reject)
    failed = fresh_http('POST', path, case['headers'], payload)
    assert failed.status_code == 409, failed.text
    assert db.query(SRMInvoice).count() == db.query(RestaurantBillGroup).count() == db.query(RestaurantBillLine).count() == 0
    monkeypatch.setattr(native, 'approve_invoice_operation', original)
    success = fresh_http('POST', path, case['headers'], payload)
    assert success.status_code == 201, success.text
    assert fresh_http('POST', path, case['headers'], payload).json() == success.json()
    assert db.query(SRMInvoice).count() == db.query(RestaurantBillGroup).count() == 1


def test_native_allocation_failure_rolls_back_receipt_and_same_payment_uuid_retries(client, db, settlement, monkeypatch, fresh_http):
    from app.apps.srm.api import router as native
    case = settlement
    path = f"/tabs/{case['order']['id']}/bills"
    first = fresh_http('POST', path, case['headers'], body(case))
    assert first.status_code == 201, first.text
    first = first.json()
    payload = {'request_key': str(uuid4()), 'expected_revision': first['order_revision'], 'expected_balance': '59',
        'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '20'}}
    path += f"/{first['bill_id']}/payments"
    original = native.allocate_receipt_operation
    def reject(*args, **kwargs): raise HTTPException(409, 'Injected native allocation failure')
    monkeypatch.setattr(native, 'allocate_receipt_operation', reject)
    failed = fresh_http('POST', path, case['headers'], payload)
    assert failed.status_code == 409, failed.text
    assert db.query(SRMReceipt).count() == db.query(RestaurantBillReceipt).count() == 0
    db.expire_all()
    assert db.get(SRMInvoice, first['invoice_id']).paid_amount == 0
    monkeypatch.setattr(native, 'allocate_receipt_operation', original)
    success = fresh_http('POST', path, case['headers'], payload)
    assert success.status_code == 201, success.text
    assert fresh_http('POST', path, case['headers'], payload).json() == success.json()
    assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == db.query(RestaurantBillReceipt).count() == 1


def test_split_native_sources_cannot_be_authorized_by_flags_or_forged_certificates(db, unpaid, monkeypatch):
    from app.business_packs.restaurant import split_bills as split
    db.info['restaurant_split_authorized'] = True
    for fake in (None, {'authorized': True}, object()):
        if fake is not None: monkeypatch.setitem(split._active, db, fake)
        with pytest.raises(HTTPException) as error: split.source_reserved(db, 'restaurant_bill', 1)
        assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error: split._current_collection(db, {'authorized': True})
    assert error.value.status_code == 403


from contextlib import contextmanager


@contextmanager
def selected(db, case):
    from tests.test_srm_native_transaction_operations import native_writer
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    with native_writer(db, case['manager'], case['branch']):
        scope = resolve_context(db, case['manager'], db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try: yield scope
        finally: cleanup()


def test_failed_composed_split_does_not_rollback_callers_existing_writes(db, settlement, monkeypatch):
    from app.business_packs.restaurant.split_bills import issue
    from app.business_packs.restaurant.split_schemas import SplitBill
    from app.business_packs.restaurant.models import RestaurantTable
    from app.business_packs.restaurant.service import fields
    from app.apps.srm.api import router as native
    case = settlement
    with selected(db, case) as scope:
        own = RestaurantTable(**fields(scope, case['manager']), name='Caller transaction survives', capacity=2)
        db.add(own); db.flush()
        ident = own.id
        def reject(*args, **kwargs): raise HTTPException(409, 'Injected composed native failure')
        monkeypatch.setattr(native, 'approve_invoice_operation', reject)
        with pytest.raises(HTTPException) as error:
            issue(case['order']['id'], SplitBill.model_validate(body(case)), db, case['manager'], commit=False)
        assert error.value.status_code == 409
        assert db.query(SRMInvoice).count() == db.query(RestaurantBillGroup).count() == 0
        assert db.get(RestaurantTable, ident).name == 'Caller transaction survives'
        db.commit()
        assert db.get(RestaurantTable, ident).name == 'Caller transaction survives'


@pytest.mark.parametrize('fault', ['permission', 'source', 'early_close'])
def test_composed_success_is_reverified_at_outer_commit(db, settlement, fault):
    from sqlalchemy import select
    from app.access.models import AccessPolicy
    from app.business_packs.restaurant.split_bills import issue
    from app.business_packs.restaurant.split_schemas import SplitBill
    case = settlement
    with selected(db, case):
        issue(case['order']['id'], SplitBill.model_validate(body(case)), db, case['manager'], commit=False)
        if fault == 'permission':
            policy = AccessPolicy.__table__
            grants = db.connection().execute(select(policy.c.grants).where(policy.c.user_id == case['manager'].id, policy.c.company_id == 1)).scalar_one()
            grants = {**grants, 'srm': {**grants['srm'], 'actions': ['view']}}
            db.connection().execute(policy.update().where(policy.c.user_id == case['manager'].id, policy.c.company_id == 1).values(grants=grants))
        elif fault == 'source':
            db.connection().execute(SRMSalesOrderLine.__table__.update().where(SRMSalesOrderLine.sales_order_id == case['order']['sales_order_id']).values(unit_price=99))
        else:
            from app.business_packs.restaurant.models import RestaurantServiceOrder
            db.connection().execute(RestaurantServiceOrder.__table__.update().where(RestaurantServiceOrder.id == case['order']['id']).values(state='served'))
        with pytest.raises(HTTPException) as error: db.commit()
        assert error.value.status_code == (403 if fault == 'permission' else 409)
        db.rollback()


def test_inert_pending_group_cannot_commit_without_native_issuance(db, settlement):
    from app.business_packs.restaurant.service import fields
    case = settlement
    with selected(db, case) as scope:
        pending = RestaurantBillGroup(**fields(scope, case['manager']), service_order_id=case['order']['id'], request_key=str(uuid4()), request_sha256='a'*64)
        db.add(pending)
        with pytest.raises(HTTPException) as error: db.commit()
        assert error.value.status_code == 403
        db.rollback()


def test_sql_sources_cannot_be_edited_or_extended_after_native_bill_issuance(client, db, settlement):
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    case = settlement
    first = post(client, case['headers'], f"/tabs/{case['order']['id']}/bills", body(case))
    line = db.connection().execute(select(RestaurantBillLine.__table__)).mappings().one()
    for model in (RestaurantBillGroup, RestaurantBillLine, RestaurantBillIssue):
        with pytest.raises(IntegrityError), db.begin_nested():
            db.connection().execute(model.__table__.update().values(created_by=case['manager'].id))
    with pytest.raises(IntegrityError), db.begin_nested():
        copied = dict(line); copied.pop('id'); copied['quantity'] = Decimal('.01')
        db.connection().execute(RestaurantBillLine.__table__.insert().values(**copied))
    response = client.get(BASE+f"/tabs/{case['order']['id']}/bills/{first['bill_id']}", headers=case['headers'])
    assert response.status_code == 200, response.text
    assert Decimal(response.json()['bills'][0]['total']) == 59


def test_anonymous_split_is_rejected_without_implicit_counter_customer_or_invoice(client, db, walkin):
    from app.apps.crm.models import CRMCompany
    before = db.query(CRMCompany).count()
    response = client.post(BASE+f"/tabs/{walkin['order']['id']}/bills", headers=walkin['headers'], json=body(walkin))
    assert response.status_code == 409 and 'anonymous split is unsupported' in response.text, response.text
    assert db.query(SRMInvoice).count() == db.query(RestaurantBillGroup).count() == db.query(SRMReceipt).count() == 0
    assert db.get(SRMSalesOrder, walkin['order']['sales_order_id']).customer_id is None
    assert db.query(CRMCompany).count() == before


def test_mismatched_cash_currency_and_overpayment_never_write_a_receipt(client, db, settlement):
    from app.apps.srm.models import SRMPOSSession
    case = settlement
    first = post(client, case['headers'], f"/tabs/{case['order']['id']}/bills", body(case))
    with selected(db, case):
        other = SRMPOSSession(organization_id=1, session_number='USD-'+uuid4().hex, status='open',
            cashier_user_id=None, created_by=case['manager'].id, metadata_json={'cash_currency': 'USD'})
        db.add(other); db.commit(); register = other.id
    path = BASE+f"/tabs/{case['order']['id']}/bills/{first['bill_id']}/payments"
    payload = {'request_key': str(uuid4()), 'expected_revision': first['order_revision'], 'expected_balance': '59',
        'pos_session_id': register, 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '59'}}
    wrong = client.post(path, headers=case['headers'], json=payload)
    assert wrong.status_code == 409 and 'currency' in wrong.text, wrong.text
    payload['payment']['amount'] = '59.01'; payload['pos_session_id'] = case['register']
    too_much = client.post(path, headers=case['headers'], json=payload)
    assert too_much.status_code == 422, too_much.text
    assert db.query(SRMReceipt).count() == db.query(RestaurantBillReceipt).count() == 0


def test_whole_item_bills_keep_both_original_native_lines_without_new_stock(client, db, settlement):
    from tests.test_restaurant_tabs import data
    case = settlement
    path = f"/tabs/{case['order']['id']}"
    order = post(client, case['headers'], path+'/items', {'request_key': str(uuid4()),
        'expected_revision': case['order']['revision'], 'lines': data(case)['lines']})
    post(client, case['headers'], f"/orders/{order['id']}/tickets", {'request_key': str(uuid4()),
        'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][-1]['sales_order_line_id'], 'quantity': '1'}]})
    order = client.get(BASE+f"/orders/{order['id']}", headers=case['headers']).json()
    case['order'] = order
    before = stock(db, case)
    first = post(client, case['headers'], path+'/bills', body(case, '1', '118'))
    second = body(case, '1', '118'); second['expected_revision'] = first['order_revision']
    second['lines'][0]['sales_order_line_id'] = order['items'][-1]['sales_order_line_id']
    post(client, case['headers'], path+'/bills', second)
    assert db.query(SRMSalesOrder).count() == 1 and db.query(SRMInvoice).count() == 2
    assert [row.quantity for row in db.query(SRMSalesOrderLine).order_by(SRMSalesOrderLine.id)] == [1, 1]
    assert stock(db, case) == before


def test_retained_genuine_issue_certificate_cannot_be_reused_after_its_command(client, db, settlement, monkeypatch):
    from dataclasses import FrozenInstanceError
    from app.apps.srm.api import router as native
    from app.business_packs.restaurant import split_bills as split
    actual = native._create_invoice_from_lines
    retained = []
    def observed(session, actor, kind, ident, *args, **kwargs):
        retained.append(split._active.get(session))
        with pytest.raises(HTTPException) as error: split.source_reserved(session, kind, ident+999)
        assert error.value.status_code == 403
        return actual(session, actor, kind, ident, *args, **kwargs)
    monkeypatch.setattr(native, '_create_invoice_from_lines', observed)
    case = settlement
    post(client, case['headers'], f"/tabs/{case['order']['id']}/bills", body(case))
    plan = retained[0]
    with pytest.raises(FrozenInstanceError): plan.native_order_id = 0
    monkeypatch.setitem(split._active, db, plan)
    with pytest.raises(HTTPException) as error: split.source_reserved(db, 'restaurant_bill', plan.group.id)
    assert error.value.status_code == 403


def test_native_approve_permission_is_required_independently_of_restaurant_billing_role(client, db, settlement):
    from app.access.models import AccessPolicy
    case = settlement
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=case['manager'].id).one()
    policy.grants = {**policy.grants, 'srm': {**policy.grants['srm'], 'actions': ['view', 'create']}}
    db.commit()
    response = client.post(BASE+f"/tabs/{case['order']['id']}/bills", headers=case['headers'], json=body(case))
    assert response.status_code == 403, response.text
    assert db.query(SRMInvoice).count() == db.query(RestaurantBillGroup).count() == 0


def test_native_finance_only_cashier_can_split_and_collect_without_order_mutation_rights(client, db, settlement):
    from tests.test_restaurant_settlement import finance_actor
    case = settlement
    headers, _ = finance_actor(db, case)
    issued = post(client, headers, f"/tabs/{case['order']['id']}/bills", body(case))
    paid = post(client, headers, f"/tabs/{case['order']['id']}/bills/{issued['bill_id']}/payments", {
        'request_key': str(uuid4()), 'expected_revision': issued['order_revision'], 'expected_balance': '59',
        'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': 'card', 'amount': '59'}})
    assert Decimal(paid['bill']['balance']) == 0
    assert db.query(SRMSalesOrderLine).one().quantity == 1 and db.query(SRMInvoice).count() == 1


def test_empty_split_projection_leaves_unrelated_selected_register_behavior_unchanged(db):
    from types import SimpleNamespace
    from app.business_packs.restaurant.split_bills import register_cash
    db.info['business_pack_scope'] = SimpleNamespace(pack_key='restaurant')
    try:
        assert register_cash(db, SimpleNamespace(id=987654321)) == {
            'cash_received': Decimal(0), 'cash_by_currency': {}, 'receipt_ids': set(), 'collection_count': 0}
    finally:
        db.info.pop('business_pack_scope', None)


@pytest.mark.parametrize('fault', ['close', 'reassign', 'delete', 'currency', 'shared'])
def test_composed_payment_rechecks_register_through_outer_commit(client, db, settlement, fault):
    from sqlalchemy.exc import IntegrityError
    from app.apps.srm.models import SRMPOSSession
    from tests.test_restaurant_kitchen import staff
    from app.business_packs.restaurant.split_bills import pay
    from app.business_packs.restaurant.split_schemas import SplitPayment
    case = settlement
    _, other = staff(db, case, 'server')
    other_id = other.id
    path = f"/tabs/{case['order']['id']}"
    billed = post(client, case['headers'], path+'/bills', body(case))
    initial = post(client, case['headers'], path+f"/bills/{billed['bill_id']}/payments", {
        'request_key': str(uuid4()), 'expected_revision': billed['order_revision'], 'expected_balance': '59',
        'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '10'}})
    payload = SplitPayment.model_validate({'request_key': str(uuid4()), 'expected_revision': initial['order_revision'], 'expected_balance': '49',
        'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '20'}})
    with selected(db, case):
        pay(case['order']['id'], billed['bill_id'], payload, db, case['manager'], commit=False)
        register = SRMPOSSession.__table__
        with pytest.raises((HTTPException, IntegrityError)):
            if fault == 'delete':
                db.connection().execute(register.delete().where(register.c.id == case['register']))
            elif fault == 'close':
                db.connection().execute(register.update().where(register.c.id == case['register']).values(status='closed'))
            elif fault == 'currency':
                db.connection().execute(register.update().where(register.c.id == case['register']).values(metadata_json={'cash_currency': 'USD'}))
            elif fault == 'shared':
                db.connection().execute(register.update().where(register.c.id == case['register']).values(cashier_user_id=None))
            else:
                db.connection().execute(register.update().where(register.c.id == case['register']).values(cashier_user_id=other_id))
            db.commit()
        db.rollback()
    assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == db.query(RestaurantBillReceipt).count() == 1
    assert db.get(SRMInvoice, billed['invoice_id']).paid_amount == 10
    response = client.get('/api/v1/srm/pos/sessions', headers=case['headers'])
    assert response.status_code == 200, response.text
    summary = next(row for row in response.json() if row['session']['id'] == case['register'])
    assert summary['session']['status'] == 'open' and Decimal(str(summary['cash_sales'])) == 10


def test_card_only_unbound_split_collection_does_not_count_as_empty_drawer_or_bind_on_read(client, db, settlement):
    from app.apps.srm.models import SRMPOSSession
    case = settlement
    first = post(client, case['headers'], f"/tabs/{case['order']['id']}/bills", body(case))
    post(client, case['headers'], f"/tabs/{case['order']['id']}/bills/{first['bill_id']}/payments", {
        'request_key': str(uuid4()), 'expected_revision': first['order_revision'], 'expected_balance': '59',
        'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': 'card', 'amount': '59'}})
    db.expire_all()
    assert db.get(SRMPOSSession, case['register']).metadata_json is None
    read = client.get('/api/v1/srm/pos/sessions', headers=case['headers'])
    assert read.status_code == 200, read.text
    db.expire_all()
    assert db.get(SRMPOSSession, case['register']).metadata_json is None
    close = client.post('/api/v1/srm/pos/cashier-closing', headers=case['headers'], json={'session_id': case['register'], 'counted_cash': '0'})
    assert close.status_code == 409 and 'currency' in close.text, close.text
    assert db.query(SRMPOSCashierClosing).count() == 0 and db.query(SRMReceipt).count() == 1
