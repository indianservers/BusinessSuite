from decimal import Decimal
import os
from uuid import uuid4
import pytest
from app.access.models import AccessPolicy
from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine
from app.business_packs.restaurant.models import RestaurantTabLine
from tests.test_restaurant_tabs import unpaid, scenario, catalog, directory_identity, data, BASE, stock, send_items
from tests.test_restaurant_kitchen import post, staff


def enable_delete(db, case):
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=case['manager'].id).one()
    policy.grants = {**policy.grants, 'srm': {**policy.grants['srm'], 'actions': ['view', 'create', 'edit', 'approve', 'delete']}}
    db.commit()


def body(order, ids):
    return {'request_key': str(uuid4()), 'expected_revision': order['revision'], 'sales_order_line_ids': ids, 'reason': 'Guest changed selection'}


def test_native_delete_retains_immutable_original_snapshot_and_exact_retry(client, db, unpaid):
    enable_delete(db, unpaid)
    order = post(client, unpaid['headers'], '/tabs', data(unpaid, lines=data(unpaid)['lines'] * 2))
    before = stock(db, unpaid)
    request = body(order, [order['items'][0]['sales_order_line_id']])
    result = post(client, unpaid['headers'], f"/tabs/{order['id']}/remove-items", request, 200)
    assert len(result['items']) == 1 and Decimal(result['total']) == 118
    assert result['sales_order_id'] == order['sales_order_id'] and result['revision'] == order['revision'] + 1
    assert stock(db, unpaid) == before and db.query(SRMSalesOrder).count() == 1
    assert db.get(SRMSalesOrderLine, request['sales_order_line_ids'][0]) is None
    frozen = db.query(RestaurantTabLine).filter_by(original_sales_order_line_id=request['sales_order_line_ids'][0]).one()
    assert frozen.sales_order_line_id is None and frozen.quantity == 1 and frozen.line_total == 118
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackRecordOwnership
    for model in (BranchOwnership, PackRecordOwnership):
        anchor = db.query(model).filter_by(resource_table='srm_sales_order_lines', resource_key=str(request['sales_order_line_ids'][0])).one()
        assert anchor.company_id == 1 and anchor.branch_id == unpaid['branch']
    assert post(client, unpaid['headers'], f"/tabs/{order['id']}/remove-items", request, 200) == result
    send_items(client, unpaid, result)
    assert stock(db, unpaid) == before - 1
    current = client.get(BASE + f"/orders/{order['id']}", headers=unpaid['headers']).json()
    added = post(client, unpaid['headers'], f"/tabs/{order['id']}/items", {'request_key': str(uuid4()), 'expected_revision': current['revision'], 'lines': data(unpaid)['lines']})
    assert len(added['items']) == 2 and Decimal(added['total']) == 236
    assert request['sales_order_line_ids'][0] not in {item['sales_order_line_id'] for item in added['items']}



@pytest.mark.parametrize('fault', ['stale', 'issued', 'all', 'unknown', 'chef', 'native_delete'])
def test_remove_rejects_without_changing_native_charges(client, db, unpaid, fault):
    if fault != 'native_delete': enable_delete(db, unpaid)
    order = post(client, unpaid['headers'], '/tabs', data(unpaid, lines=data(unpaid)['lines'] * 2))
    ids = [order['items'][-1]['sales_order_line_id']]
    if fault == 'issued':
        send_items(client, unpaid, order)
        order = client.get(BASE + f"/orders/{order['id']}", headers=unpaid['headers']).json()
    request = body(order, ids)
    headers = unpaid['headers']
    if fault == 'stale': request['expected_revision'] += 1
    if fault == 'all': request['sales_order_line_ids'] = [i['sales_order_line_id'] for i in order['items']]
    if fault == 'unknown': request['sales_order_line_ids'] = [999999]
    if fault == 'chef': headers, _ = staff(db, unpaid, 'chef')
    before = client.get(BASE + f"/orders/{order['id']}", headers=unpaid['headers']).json()
    post(client, headers, f"/tabs/{order['id']}/remove-items", request, 403 if fault in ('chef', 'native_delete') else 409)
    assert client.get(BASE + f"/orders/{order['id']}", headers=unpaid['headers']).json() == before


def test_removal_failure_rolls_back_and_same_command_can_retry(client, db, unpaid, monkeypatch):
    from fastapi import HTTPException
    from app.business_packs.restaurant import service
    enable_delete(db, unpaid)
    order = post(client, unpaid['headers'], '/tabs', data(unpaid, lines=data(unpaid)['lines'] * 2))
    request = body(order, [order['items'][0]['sales_order_line_id']])
    original = service.save_command
    def reject(*args, **kwargs):
        if args[3] == 'tab.remove': raise HTTPException(409, 'Injected command persistence failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(service, 'save_command', reject)
    post(client, unpaid['headers'], f"/tabs/{order['id']}/remove-items", request, 409)
    assert client.get(BASE + f"/orders/{order['id']}", headers=unpaid['headers']).json() == order
    assert all(row.sales_order_line_id is not None for row in db.query(RestaurantTabLine))
    monkeypatch.setattr(service, 'save_command', original)
    post(client, unpaid['headers'], f"/tabs/{order['id']}/remove-items", request, 200)


from tests.test_restaurant_modifiers_http import menu


def test_complete_modifier_group_removal_keeps_exact_native_remaining_charge(client, db, menu):
    case, option, payload, _ = menu
    enable_delete(db, case)
    payload['lines'].append({'product_id': option, 'quantity': '1', 'expected_unit_price': '100'})
    order = post(client, case['headers'], '/tabs', payload)
    post(client, case['headers'], f"/tabs/{order['id']}/remove-items", body(order, [order['items'][0]['sales_order_line_id']]), 409)
    request = body(order, [item['sales_order_line_id'] for item in order['items'][:2]])
    removed = post(client, case['headers'], f"/tabs/{order['id']}/remove-items", request, 200)
    assert len(removed['items']) == 1 and Decimal(removed['total']) == 118
    assert len(removed['removed_sources']) == 2
    current = client.get(BASE + f"/orders/{order['id']}", headers=case['headers'])
    assert current.status_code == 200, current.text
    added = post(client, case['headers'], f"/tabs/{order['id']}/items", {'request_key': str(uuid4()), 'expected_revision': removed['revision'], 'lines': payload['lines'][:1]})
    assert Decimal(added['total']) == 472 and len(added['items']) == 3


from tests.test_restaurant_settlement import settlement, bill_input


def test_cancellation_then_native_invoice_and_paid_restriction(client, db, settlement):
    case = settlement
    enable_delete(db, case)
    order = post(client, case['headers'], f"/tabs/{case['order']['id']}/items", {'request_key': str(uuid4()), 'expected_revision': case['order']['revision'], 'lines': data(case)['lines']})
    removed = post(client, case['headers'], f"/tabs/{order['id']}/remove-items", body(order, [order['items'][-1]['sales_order_line_id']]), 200)
    billed = post(client, case['headers'], f"/tabs/{order['id']}/bill", {**bill_input(case), 'expected_revision': removed['revision']})
    assert Decimal(billed['checkout']['invoice']['total']) == 118
    post(client, case['headers'], f"/tabs/{order['id']}/remove-items", body({**removed, 'revision': billed['order_revision']}, [removed['items'][0]['sales_order_line_id']]), 409)


from tests.test_restaurant_anonymous import anonymous, walkin, full


def test_anonymous_settlement_after_removal_preserves_full_tender_rollback_and_retry(client, db, anonymous, monkeypatch):
    from fastapi import HTTPException
    from app.apps.srm.api import router as native
    from app.apps.srm.models import SRMInvoice, SRMReceipt
    from sqlalchemy.orm import sessionmaker
    from app.main import app
    from app.core.deps import get_db
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, join_transaction_mode='create_savepoint')
    def request(path, payload, status=201):
        # Production opens a new identity map for each HTTP request. Keep the
        # fixture's outer transaction, not its reused ORM identity map.
        with factory() as fresh, monkeypatch.context() as request_patch:
            def dependency():
                try:
                    yield fresh
                except BaseException:
                    fresh.rollback()
                    raise
            request_patch.setitem(app.dependency_overrides, get_db, dependency)
            request_patch.setattr(app.state, 'business_os_session_factory', lambda: fresh)
            request_patch.setattr(app.state, 'business_os_close_session', False)
            request_patch.setattr(app.state, 'audit_session_factory', lambda: fresh)
            request_patch.setattr(app.state, 'audit_close_session', False)
            request_patch.setattr(app.state, 'audit_commit', False)
            return post(client, case['headers'], path, payload, status)
    case = anonymous
    enable_delete(db, case)
    order = request(f"/tabs/{case['order']['id']}/items", {'request_key': str(uuid4()), 'expected_revision': case['order']['revision'], 'lines': data(case)['lines']})
    removed = request(f"/tabs/{order['id']}/remove-items", body(order, [order['items'][-1]['sales_order_line_id']]), 200)
    case = {**case, 'order': removed}
    payload = full(case)
    path = f"/tabs/{removed['id']}/anonymous-settlement"
    short = {**payload, 'payments': payload['payments'][:1]}
    request(path, short, 422)
    original = native.allocate_receipt_operation
    calls = []
    def reject_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2: raise HTTPException(409, 'Injected second allocation failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(native, 'allocate_receipt_operation', reject_second)
    before = stock(db, case)
    request(path, payload, 409)
    assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 0
    assert db.get(SRMSalesOrder, removed['sales_order_id']).customer_id is None
    assert stock(db, case) == before
    assert client.get(BASE + f"/orders/{removed['id']}", headers=case['headers']).status_code == 200
    monkeypatch.setattr(native, 'allocate_receipt_operation', original)
    result = request(path, payload)
    assert Decimal(result['checkout']['invoice']['balance']) == 0
    assert request(path, payload) == result
    assert stock(db, case) == before and db.query(SRMSalesOrder).count() == 1


def test_retention_callback_cannot_use_flags_forged_dict_or_unissued_lease(db, unpaid, monkeypatch):
    from fastapi import HTTPException
    from app.business_packs.restaurant import removals
    from app.apps.srm.models import SRMInvoice
    line = SRMSalesOrderLine(id=999, sales_order_id=999)
    db.info['restaurant_cancel_authorized'] = True
    assert removals.retain_deleted_branch_source(db, line) is False
    assert removals.retain_deleted_branch_source(db, SRMInvoice()) is False
    with monkeypatch.context() as patch:
        patch.setitem(removals._plans, db, {'authorized': True})
        with pytest.raises(HTTPException) as error: removals.retain_deleted_branch_source(db, line)
        assert error.value.status_code == 403
    forged = removals._Cancellation(actor=unpaid['manager'], scope=object(), epoch='', order=object(), lines={}, sources=[], snapshots={}, native_values={})
    with monkeypatch.context() as patch:
        patch.setitem(removals._plans, db, forged)
        with pytest.raises(HTTPException) as error: removals.retain_deleted_branch_source(db, line)
        assert error.value.status_code == 403
    db.info.pop('restaurant_cancel_authorized', None)


def test_authentic_retention_refuses_wrong_line_and_cannot_adopt_deleted_native_identity(client, db, unpaid, monkeypatch):
    from fastapi import HTTPException
    from sqlalchemy import select
    from app.apps.srm.api import router as native
    from app.business_packs.restaurant import removals
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from tests.test_srm_native_transaction_operations import native_writer
    enable_delete(db, unpaid)
    order = post(client, unpaid['headers'], '/tabs', data(unpaid, lines=data(unpaid)['lines'] * 2))
    selected, other = [item['sales_order_line_id'] for item in order['items']]
    actual = native.delete_sales_order_line_operation
    def observed(ident, line_id, session, actor, **kwargs):
        wrong = session.get(SRMSalesOrderLine, other)
        with pytest.raises(HTTPException) as error: removals.retain_deleted_branch_source(session, wrong)
        assert error.value.status_code == 403
        return actual(ident, line_id, session, actor, **kwargs)
    monkeypatch.setattr(native, 'delete_sales_order_line_operation', observed)
    post(client, unpaid['headers'], f"/tabs/{order['id']}/remove-items", body(order, [selected]), 200)
    table = SRMSalesOrderLine.__table__
    original = dict(db.connection().execute(select(table).where(table.c.id == other)).mappings().one())
    original['id'] = selected
    with native_writer(db, unpaid['manager'], unpaid['branch']):
        scope = resolve_context(db, unpaid['manager'], db.info['branch_context'], unpaid['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            with pytest.raises(HTTPException) as error, db.begin_nested():
                db.add(SRMSalesOrderLine(**original))
                db.flush()
            assert error.value.status_code == 403
        finally:
            cleanup()
    assert db.connection().scalar(select(table.c.id).where(table.c.id == selected)) is None
    assert client.get(BASE + f"/orders/{order['id']}", headers=unpaid['headers']).status_code == 200


def test_default_public_native_delete_still_cleans_unowned_legacy_branch_metadata(client, db, scenario):
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackRecordOwnership
    headers = scenario[2][0]
    created = client.post('/api/v1/srm/sales-orders', headers=headers, json={'title': 'Legacy draft deletion parity', 'customer_id': 101,
        'lines': [{'description': 'Legacy draft charge', 'quantity': '1', 'unit_price': '100'}]})
    assert created.status_code == 201, created.text
    order = created.json()
    line_id = order['lines'][0]['id']
    key = {'resource_table': 'srm_sales_order_lines', 'resource_key': str(line_id)}
    assert db.query(BranchOwnership).filter_by(**key).one()
    assert db.query(PackRecordOwnership).filter_by(**key).count() == 0
    deleted = client.delete(f"/api/v1/srm/sales-orders/{order['id']}/lines/{line_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {'deleted': True, 'id': line_id}
    assert db.query(SRMSalesOrderLine).filter_by(id=line_id).count() == 0
    assert db.query(BranchOwnership).filter_by(**key).count() == 0


@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='Requires non-recycling PostgreSQL native sequence')
def test_postgres_removing_highest_native_line_then_adding_uses_fresh_identity(client, db, unpaid):
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackRecordOwnership
    assert db.bind.dialect.name == 'postgresql'
    enable_delete(db, unpaid)
    order = post(client, unpaid['headers'], '/tabs', data(unpaid, lines=data(unpaid)['lines'] * 2))
    original_ids = {item['sales_order_line_id'] for item in order['items']}
    removed_id = max(original_ids)
    removed = post(client, unpaid['headers'], f"/tabs/{order['id']}/remove-items", body(order, [removed_id]), 200)
    added = post(client, unpaid['headers'], f"/tabs/{order['id']}/items", {'request_key': str(uuid4()), 'expected_revision': removed['revision'], 'lines': data(unpaid)['lines']})
    assert len(added['items']) == 2 and Decimal(added['total']) == 236
    assert len({item['sales_order_line_id'] for item in added['items']} - original_ids) == 1
    assert removed_id not in {item['sales_order_line_id'] for item in added['items']}
    for model in (BranchOwnership, PackRecordOwnership):
        row = db.query(model).filter_by(resource_table='srm_sales_order_lines', resource_key=str(removed_id)).one()
        assert row.company_id == 1 and row.branch_id == unpaid['branch']
