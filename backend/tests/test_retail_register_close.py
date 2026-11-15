"""Selected Retail closing uses actual receipts and never another pack's till."""
from decimal import Decimal
from uuid import uuid4

import pytest

from app.apps.srm.models import SRMPOSSession, SRMPOSCashierClosing, SRMReceipt
from tests.test_retail_return_http import retail_setup, scenario, catalog, directory_identity


def test_selected_retail_split_collection_cash_movements_and_close_once(client, db, retail_setup):
    headers, actor, branch, context, register, product, warehouse = retail_setup
    sale = client.post('/api/v1/srm/service-checkout', headers=headers, json={
        'request_id': str(uuid4()), 'customer_id': 101, 'pos_session_id': register,
        'lines': [{'client_line_key': str(uuid4()), 'line_kind': 'product', 'product_id': product, 'quantity': 2}],
        'payments': [{'payment_key': str(uuid4()), 'method': 'cash', 'amount': '100'},
                     {'payment_key': str(uuid4()), 'method': 'card', 'amount': '136', 'reference': 'Actual terminal'}]})
    assert sale.status_code == 201, sale.text
    for kind, amount in [('cash_in', '20'), ('cash_out', '10')]:
        moved = client.post('/api/v1/srm/pos/cash-movements', headers=headers,
                            json={'session_id': register, 'movement_type': kind, 'amount': amount, 'reason': 'Actual drawer movement'})
        assert moved.status_code == 201, moved.text
    response = client.get('/api/v1/srm/pos/sessions', headers=headers)
    assert response.status_code == 200, response.text
    summary = next(row for row in response.json() if row['session']['id'] == register)
    assert Decimal(str(summary['cash_sales'])) == 100
    assert Decimal(str(summary['expected_cash'])) == 110
    assert not summary['reconciliation_required']
    payload = {'session_id': register, 'counted_cash': '110'}
    closed = client.post('/api/v1/srm/pos/cashier-closing', headers=headers, json=payload)
    assert closed.status_code == 201, closed.text
    assert Decimal(str(closed.json()['closing']['variance'])) == 0
    repeat = client.post('/api/v1/srm/pos/cashier-closing', headers=headers, json=payload)
    assert repeat.status_code == 201, repeat.text
    assert db.query(SRMPOSCashierClosing).filter_by(session_id=register).count() == 1
    assert db.query(SRMReceipt).count() == 2
    db.expire_all()
    assert db.get(SRMPOSSession, register).status == 'closed'
    late = client.post('/api/v1/srm/pos/cash-movements', headers=headers,
                       json={'session_id': register, 'movement_type': 'cash_in', 'amount': '1', 'reason': 'Late entry'})
    assert late.status_code == 400, late.text
    assert db.query(SRMPOSCashierClosing).filter_by(session_id=register).count() == 1


@pytest.mark.parametrize('pack,role,status', [
    ('hospital', 'doctor', 403), ('restaurant', 'chef', 403),
    ('construction', 'site_engineer', 403),
    ('hospital', 'hospital_manager', 404), ('restaurant', 'restaurant_manager', 404),
    ('construction', 'project_manager', 404),
])
def test_other_pack_cannot_close_retail_register(client, db, retail_setup, pack, role, status):
    from tests.test_business_pack_http_integration import grant
    headers, actor, branch, context, register, _, _ = retail_setup
    other, _ = grant(db, actor, branch, pack, role)
    response = client.post('/api/v1/srm/pos/cashier-closing',
        headers={**headers, 'X-Suite-Pack-Context': str(other.id)},
        json={'session_id': register, 'counted_cash': '0'})
    assert response.status_code == status, response.text
    db.expire_all()
    assert db.get(SRMPOSSession, register).status == 'open'
    assert db.query(SRMPOSCashierClosing).count() == 0


def test_retail_cashier_role_cannot_inherit_store_manager_closing(client, db, retail_setup):
    from app.business_packs.models import PackUserGrant
    headers, actor, branch, context, register, _, _ = retail_setup
    assert not actor.is_superuser
    role = db.query(PackUserGrant).filter_by(context_id=context, user_id=actor.id).one()
    role.role = 'cashier'
    db.commit()
    response = client.post('/api/v1/srm/pos/cashier-closing', headers=headers,
                           json={'session_id': register, 'counted_cash': '0'})
    assert response.status_code == 403, response.text
    db.expire_all()
    assert db.get(SRMPOSSession, register).status == 'open'
    assert db.query(SRMPOSCashierClosing).count() == 0
