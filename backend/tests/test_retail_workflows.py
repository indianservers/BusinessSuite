"""Retail public commands: actual invoices, receipts and canonical stock."""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

import pytest

from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMSalesOrder, SRMInventoryBalance, SRMInventoryMovement
from app.apps.srm.service_checkout_models import POSServiceCheckout
from tests.test_retail_return_http import retail_setup, scenario, catalog, directory_identity


def cart(setup, method='cash', quantity=1):
    return {'request_id': str(uuid4()), 'customer_id': 101, 'pos_session_id': setup[4],
            'lines': [{'client_line_key': str(uuid4()), 'line_kind': 'product', 'product_id': setup[5], 'quantity': quantity}],
            'payments': [{'payment_key': str(uuid4()), 'method': method, 'amount': str(118 * quantity)}]}


def counts(db):
    return {model: db.query(model).count() for model in
            (SRMInvoice, SRMReceipt, SRMSalesOrder, SRMInventoryMovement, POSServiceCheckout)}


@pytest.fixture
def independent_request_sessions(client, db, retail_setup):
    """Keep fixture rollback while giving each HTTP request its native identity map."""
    from sqlalchemy.orm import sessionmaker
    from app.main import app
    from app.core.deps import get_db
    previous = app.dependency_overrides[get_db]
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False,
                           join_transaction_mode='create_savepoint')

    def request_db():
        with factory() as session:
            try:
                yield session
            except BaseException:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = request_db
    try:
        yield client
    finally:
        app.dependency_overrides[get_db] = previous


@pytest.mark.parametrize('method', ['cash', 'card', 'split'])
def test_retail_server_price_tax_payments_replay_and_changed_retry(client, db, retail_setup, method):
    data = cart(retail_setup, 'cash' if method == 'split' else method)
    if method == 'split':
        data['payments'][0]['amount'] = '40'
        data['payments'].append({'payment_key': str(uuid4()), 'method': 'card', 'amount': '78'})
    first = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=data)
    assert first.status_code == 201, first.text
    result = first.json()
    assert result['lines'][0]['unit_price'] == '100.00'
    assert result['lines'][0]['tax'] == '18.00'
    assert result['invoice']['paid'] == '118.00'
    assert result['invoice']['balance'] == '0.00'
    before = counts(db)
    replay = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=data)
    assert replay.status_code == 201, replay.text
    assert replay.json() == result
    changed = deepcopy(data)
    changed['lines'][0]['quantity'] = 2
    response = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=changed)
    assert response.status_code == 409, response.text
    assert counts(db) == before
    assert db.query(SRMInventoryBalance).filter_by(product_id=retail_setup[5], warehouse_id=retail_setup[6]).one().quantity == 4


@pytest.mark.parametrize('field', ['unit_price', 'discount_amount', 'bill_discount_amount'])
def test_cashier_cannot_inherit_manager_discount_permission(client, db, retail_setup, field):
    from app.business_packs.models import PackUserGrant
    grant = db.query(PackUserGrant).filter_by(context_id=retail_setup[3], user_id=retail_setup[1].id).one()
    grant.role = 'cashier'
    db.commit()
    data = cart(retail_setup)
    (data if field == 'bill_discount_amount' else data['lines'][0])[field] = '1'
    before = counts(db)
    response = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=data)
    assert response.status_code == 403, response.text
    assert counts(db) == before


def test_closed_register_and_insufficient_stock_leave_no_sale(client, db, retail_setup):
    before = counts(db)
    response = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=cart(retail_setup, quantity=6))
    assert response.status_code == 409, response.text
    assert counts(db) == before
    closed = client.post('/api/v1/srm/pos/cashier-closing', headers=retail_setup[0],
                         json={'session_id': retail_setup[4], 'counted_cash': '0'})
    assert closed.status_code == 201, closed.text
    response = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=cart(retail_setup))
    assert response.status_code == 409, response.text
    assert counts(db) == before


def test_second_receipt_failure_rolls_back_and_same_request_can_retry(independent_request_sessions, db, retail_setup, monkeypatch):
    client = independent_request_sessions
    from fastapi import HTTPException
    from app.apps.srm.api import router as native
    original = native.create_receipt_operation
    data = cart(retail_setup)
    data['payments'][0]['amount'] = '40'
    data['payments'].append({'payment_key': str(uuid4()), 'method': 'card', 'amount': '78'})
    calls = []
    def fail_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise HTTPException(409, 'Terminal refused second payment')
        return original(*args, **kwargs)
    before = counts(db)
    monkeypatch.setattr(native, 'create_receipt_operation', fail_second)
    failed = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=data)
    assert failed.status_code == 409, failed.text
    assert counts(db) == before
    assert db.query(SRMInventoryBalance).filter_by(product_id=retail_setup[5], warehouse_id=retail_setup[6]).one().quantity == 5
    monkeypatch.setattr(native, 'create_receipt_operation', original)
    retried = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=data)
    assert retried.status_code == 201, retried.text
    assert Decimal(retried.json()['invoice']['paid']) == 118
    assert db.query(SRMReceipt).count() == 2


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef'), ('construction', 'site_engineer')])
def test_same_user_other_assignment_cannot_use_retail_register(client, db, retail_setup, pack, role):
    from tests.test_business_pack_http_integration import grant
    context, _ = grant(db, retail_setup[1], retail_setup[2], pack, role)
    before = counts(db)
    response = client.post('/api/v1/srm/service-checkout',
                           headers={**retail_setup[0], 'X-Suite-Pack-Context': str(context.id)}, json=cart(retail_setup))
    assert response.status_code == 403, response.text
    assert counts(db) == before


def test_store_manager_discount_uses_native_server_tax_and_totals(client, db, retail_setup):
    data = cart(retail_setup, quantity=2)
    data['lines'][0]['discount_amount'] = '10'
    data['bill_discount_amount'] = '10'
    data['payments'][0]['amount'] = '212.40'
    data['expected_total'] = '212.40'
    response = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=data)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['lines'][0]['unit_price'] == '100.00'
    assert Decimal(result['lines'][0]['discount']) == 20
    assert Decimal(result['lines'][0]['tax']) == Decimal('32.40')
    assert Decimal(result['invoice']['total']) == Decimal('212.40')
    assert Decimal(result['invoice']['paid']) == Decimal('212.40')
    assert db.query(SRMReceipt).count() == 1
