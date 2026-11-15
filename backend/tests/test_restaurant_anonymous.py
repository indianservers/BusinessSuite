from decimal import Decimal
from uuid import uuid4
import pytest
from app.apps.srm.models import SRMSalesOrder, SRMInvoice, SRMReceipt
from app.apps.srm.service_checkout_models import POSServiceCheckout
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantCommand
from app.apps.srm.anonymous_cash import configure, _KEY
from app.apps.srm.anonymous_cash_schemas import CashAccountSetup
from app.business_packs.models import PackContext
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_business_pack_http_integration import grant
from tests.test_restaurant_customer_assignment import walkin, unpaid, scenario, catalog, directory_identity
from tests.test_restaurant_tabs import stock, BASE
from tests.test_restaurant_kitchen import post, staff
from tests.test_srm_native_transaction_operations import native_writer


def configure_counter(db, case, admin, *, client=None, headers=None):
    grant(db, admin, case['branch'], 'restaurant', 'business_owner', db.get(PackContext, case['context']))
    if client is not None:
        from app.core.security import create_access_token
        identity = headers or {'Authorization': 'Bearer '+create_access_token(admin.id)}
        response = client.put('/api/v1/srm/anonymous-cash/configuration', headers={**identity,
            'X-Suite-Organization': '1', 'X-Suite-Branch': str(case['branch']),
            'X-Suite-Pack-Context': str(case['context'])}, json={
                'action':'create','label':'Restaurant counter control','jurisdiction_country':'IN',
                'reason':'Explicit native Restaurant counter setup'})
        assert response.status_code == 200, response.text
        return response.json()
    with native_writer(db, admin, case['branch']):
        scope = resolve_context(db, admin, db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            from sqlalchemy import event
            from sqlalchemy.orm import Session
            from app.business_packs import anonymous_definitions
            def models_only(session, *args):
                if anonymous_definitions._leases.get(session) is not None:
                    print('anonymous-config pending model classes:', sorted({type(row).__name__ for row in session.new | session.dirty | session.deleted}))
            event.listen(Session, 'before_flush', models_only)
            try:
                account = configure(CashAccountSetup(action='create', label='Restaurant counter control',
                    jurisdiction_country='IN', reason='Explicit native Restaurant counter setup'), db, admin)
            finally:
                event.remove(Session, 'before_flush', models_only)
        finally:
            cleanup()
    return account


@pytest.fixture
def anonymous(client, db, walkin, scenario, monkeypatch):
    case = walkin
    from app.business_packs import common_queries
    import traceback
    actual_exception = common_queries.HTTPException
    def static_denial(*args, **kwargs):
        if (args[1] if len(args) > 1 else kwargs.get('detail')) == 'An ORM source is outside the registered native purpose':
            print('anonymous configuration static source frames:', ''.join(traceback.format_stack(limit=18)))
        return actual_exception(*args, **kwargs)
    monkeypatch.setattr(common_queries, 'HTTPException', static_denial)
    from tests.test_business_pack_http_integration import native_actor
    admin_headers, admin = native_actor(db, case['branch'], actions=('view','create','edit','approve','configure'), admin=True)
    assert not admin.is_superuser
    account = configure_counter(db, case, admin, client=client, headers=admin_headers)
    order = case['order']
    ticket = post(client, case['headers'], f"/orders/{order['id']}/tickets", {'request_key': str(uuid4()),
        'service_order_id': order['id'], 'expected_revision': order['revision'],
        'lines': [{'sales_order_line_id': order['items'][0]['sales_order_line_id'], 'quantity': '1'}]})
    order = client.get(BASE+f"/orders/{order['id']}", headers=case['headers']).json()
    return {**case, 'order': order, 'ticket': ticket, 'account': account}


def full(case):
    return {'request_key': str(uuid4()), 'expected_revision': case['order']['revision'],
        'pos_session_id': case['register'], 'expected_total': '118', 'payments': [
            {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '50'},
            {'payment_key': str(uuid4()), 'method': 'card', 'amount': '68'}]}


def test_atomic_anonymous_split_uses_existing_so_and_no_additional_stock(client, db, anonymous):
    from app.business_packs.restaurant.anonymous import _leases
    case = anonymous
    original = db.query(RestaurantServiceOrder).one().source_sha256
    before = stock(db, case)
    payload = full(case)
    path = f"/tabs/{case['order']['id']}/anonymous-settlement"
    result = post(client, case['headers'], path, payload)
    assert post(client, case['headers'], path, payload) == result
    assert db.query(SRMSalesOrder).count() == db.query(SRMInvoice).count() == db.query(POSServiceCheckout).count() == 1
    assert db.query(SRMReceipt).count() == 2 and db.query(SRMInvoice).one().balance_amount == 0
    assert db.query(SRMSalesOrder).one().customer_id == case['account']['customer_id']
    assert db.query(RestaurantServiceOrder).one().source_sha256 == original
    assert db.query(RestaurantCommand).filter_by(action='tab.assign_anonymous').count() == 1
    assert db.query(RestaurantCommand).filter_by(action='tab.settle_anonymous').count() == 1
    assert stock(db, case) == before and not _leases and _KEY not in db.connection().info
    chef, _ = staff(db, case, 'chef')
    response = client.get(BASE+'/kitchen', headers=chef)
    assert response.status_code == 200 and all(key not in response.text for key in ('invoice','customer','amount','receipt')), response.text


@pytest.mark.parametrize('fault', ['partial','overpay','duplicate_keys','customer_override','empty','currency_override'])
def test_strict_anonymous_request_never_enters_partial_or_caller_control_mode(client, db, walkin, fault):
    body = full(walkin)
    if fault == 'partial':
        body['payments'][1]['amount'] = '1'
    elif fault == 'overpay':
        body['payments'][1]['amount'] = '69'
    elif fault == 'duplicate_keys':
        body['payments'][1]['payment_key'] = body['payments'][0]['payment_key']
    elif fault == 'customer_override':
        body['customer_id'] = 101
    elif fault == 'empty':
        body['payments'] = []
    else:
        body['currency'] = 'USD'
    response = client.post(BASE+f"/tabs/{walkin['order']['id']}/anonymous-settlement", headers=walkin['headers'], json=body)
    assert response.status_code == 422, response.text
    assert db.query(SRMSalesOrder).one().customer_id is None
    assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 0


@pytest.mark.parametrize('role', ['cashier','server','chef'])
def test_anonymous_full_settlement_requires_all_pack_and_native_purposes(client, db, walkin, role):
    from tests.test_restaurant_settlement import finance_actor
    headers, _ = finance_actor(db, walkin) if role == 'cashier' else staff(db, walkin, role)
    response = client.post(BASE+f"/tabs/{walkin['order']['id']}/anonymous-settlement", headers=headers, json=full(walkin))
    assert response.status_code == 403, response.text
    assert db.query(SRMSalesOrder).one().customer_id is None
    assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 0


@pytest.mark.parametrize('definition_company', [1,2])
def test_real_hidden_required_company_definition_is_enforced_and_foreign_definition_excluded(db, walkin, scenario, monkeypatch, definition_company):
    from fastapi import HTTPException
    from app.apps.crm.models import CRMCustomField, CRMCompany, CRMContact
    from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
    from app.apps.crm import custom_field_config
    db.add(CRMCustomField(organization_id=definition_company, entity='companies', field_key='counter_internal_key',
        label='Counter internal key', field_type='text', is_required=True, is_visible=False, is_active=True))
    db.commit()
    before = db.query(CRMCompany).count(), db.query(CRMContact).count()
    if definition_company == 2:
        original = custom_field_config.validate_values
        def validated_before_any_birth(*args, **kwargs):
            original(*args, **kwargs)
            raise HTTPException(409, 'Stopped after genuine canonical required-definition validation')
        monkeypatch.setattr(custom_field_config, 'validate_values', validated_before_any_birth)
    with pytest.raises(HTTPException) as denied:
        configure_counter(db, walkin, scenario[0])
    assert denied.value.status_code == (422 if definition_company == 1 else 409)
    assert ('Counter internal key' in str(denied.value.detail)) if definition_company == 1 else ('genuine canonical' in str(denied.value.detail))
    assert (db.query(CRMCompany).count(), db.query(CRMContact).count()) == before
    assert db.query(AnonymousCashAccount).count() == 0


@pytest.mark.parametrize('fault', ['second_tender','incomplete_commit','counterfeit_permit'])
def test_anonymous_late_failure_and_commit_guard_roll_back_entire_binding_money_transaction(client, db, anonymous, monkeypatch, fault):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.apps.srm.api import router as native_router
    from app.business_packs.restaurant import anonymous as operation
    case = anonymous
    before = stock(db, case)
    if fault == 'counterfeit_permit':
        @contextmanager
        def fake(db, actor, account, scope):
            db.connection().info[_KEY] = (object(), SimpleNamespace(financial_ready=False))
            try:
                yield SimpleNamespace(financial_ready=False)
            finally:
                db.connection().info.pop(_KEY, None)
        monkeypatch.setattr(operation, 'checkout_permit', fake)
    else:
        original, calls = native_router.create_receipt_operation, []
        def fail_at_payment(*args, **kwargs):
            calls.append(1)
            if fault == 'incomplete_commit':
                args[1].commit()  # Must never commit the anonymous identity/invoice without full allocations.
            if len(calls) == 2:
                raise HTTPException(409, 'Second native tender failed')
            return original(*args, **kwargs)
        monkeypatch.setattr(native_router, 'create_receipt_operation', fail_at_payment)
    response = client.post(BASE+f"/tabs/{case['order']['id']}/anonymous-settlement", headers=case['headers'], json=full(case))
    assert response.status_code == (403 if fault == 'counterfeit_permit' else 409), response.text
    assert db.query(SRMSalesOrder).one().customer_id is None
    assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == db.query(POSServiceCheckout).count() == 0
    assert db.query(RestaurantCommand).filter(RestaurantCommand.action.in_(('tab.assign_anonymous','tab.bill','tab.settle_anonymous'))).count() == 0
    assert stock(db, case) == before and not operation._leases and _KEY not in db.connection().info


def test_anonymous_key_replay_rejects_changed_plan_without_collecting_again(client, db, anonymous):
    case = anonymous
    body = full(case)
    path = f"/tabs/{case['order']['id']}/anonymous-settlement"
    post(client, case['headers'], path, body)
    body['payments'][0]['amount'], body['payments'][1]['amount'] = '51', '67'
    response = client.post(BASE+path, headers=case['headers'], json=body)
    assert response.status_code == 409, response.text
    assert db.query(SRMReceipt).count() == 2 and db.query(SRMInvoice).one().paid_amount == 118


@pytest.mark.parametrize('fault', ['missing_final','forged_paid_snapshot'])
def test_anonymous_identity_is_not_readable_without_actual_durable_full_settlement(client, db, anonymous, fault):
    case = anonymous
    post(client, case['headers'], f"/tabs/{case['order']['id']}/anonymous-settlement", full(case))
    command = db.query(RestaurantCommand).filter_by(action='tab.settle_anonymous').one()
    if fault == 'missing_final':
        db.connection().execute(RestaurantCommand.__table__.delete().where(RestaurantCommand.id == command.id))
    else:
        from copy import deepcopy
        changed = deepcopy(command.result)
        changed['checkout']['invoice']['paid'] = '1'
        db.connection().execute(RestaurantCommand.__table__.update().where(RestaurantCommand.id == command.id).values(result=changed))
    db.commit()
    response = client.get(BASE+f"/orders/{case['order']['id']}", headers=case['headers'])
    assert response.status_code == 409, response.text


def test_anonymous_full_payment_cannot_use_another_native_cashier_register(client, db, anonymous):
    from app.apps.srm.models import SRMPOSSession
    case = anonymous
    _, actor = staff(db, case, 'restaurant_manager')
    with native_writer(db, actor, case['branch']):
        scope = resolve_context(db, actor, db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            other = SRMPOSSession(organization_id=1, session_number='OTHER-ANON-'+uuid4().hex,
                status='open', cashier_user_id=actor.id, created_by=actor.id)
            db.add(other); db.commit()
            other_id = other.id
        finally:
            cleanup()
    body = full(case)
    body['pos_session_id'] = other_id
    response = client.post(BASE+f"/tabs/{case['order']['id']}/anonymous-settlement", headers=case['headers'], json=body)
    assert response.status_code in {403,404}, response.text
    assert db.query(SRMSalesOrder).one().customer_id is None
    assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 0
