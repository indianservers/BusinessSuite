"""Actual native shift-close proof; split tender is not item split billing."""
from decimal import Decimal
from uuid import uuid4

import pytest

from app.apps.srm.models import SRMPOSCashierClosing, SRMPOSSession, SRMInvoice, SRMReceipt
from app.business_packs.models import PackUserGrant
from tests.test_restaurant_settlement import settlement, bill_input, unpaid, scenario, catalog, directory_identity
from tests.test_restaurant_kitchen import post
from tests.test_restaurant_tabs import BASE


def test_restaurant_shift_close_counts_actual_cash_only_and_retries_once(client, db, settlement):
    case = settlement
    path = f"/tabs/{case['order']['id']}"
    billed = post(client, case['headers'], path + '/bill', bill_input(case))
    for method, amount in [('cash', '50'), ('card', '68')]:
        billed = post(client, case['headers'], path + '/payments', {
            'request_key': str(uuid4()), 'expected_revision': billed['checkout']['revision'],
            'pos_session_id': case['register'], 'payment': {'payment_key': str(uuid4()), 'method': method, 'amount': amount}})
    payload = {'session_id': case['register'], 'counted_cash': '50'}
    for _ in range(2):
        response = client.post('/api/v1/srm/pos/cashier-closing', headers=case['headers'], json=payload)
        assert response.status_code == 201, response.text
        assert Decimal(str(response.json()['closing']['cash_sales'])) == 50
        assert Decimal(str(response.json()['closing']['variance'])) == 0
    assert db.query(SRMPOSCashierClosing).filter_by(session_id=case['register']).count() == 1
    assert db.query(SRMInvoice).count() == 1 and db.query(SRMReceipt).count() == 2


@pytest.mark.parametrize('role', ['chef', 'cashier'])
def test_restaurant_specialist_cannot_inherit_other_pack_shift_close(client, db, settlement, role):
    from tests.test_business_pack_http_integration import grant
    case = settlement
    grant(db, case['manager'], case['branch'], 'hospital', 'hospital_manager')
    own = db.query(PackUserGrant).filter_by(context_id=case['context'], user_id=case['manager'].id).one()
    own.role = role
    db.commit()
    response = client.post('/api/v1/srm/pos/cashier-closing', headers=case['headers'],
        json={'session_id': case['register'], 'counted_cash': '0'})
    assert response.status_code == 403, response.text
    db.expire_all()
    assert db.get(SRMPOSSession, case['register']).status == 'open'
    assert db.query(SRMPOSCashierClosing).count() == 0


def test_current_bill_route_rejects_item_quantity_selection_without_an_invoice(client, db, settlement):
    case = settlement
    response = client.post(BASE + f"/tabs/{case['order']['id']}/bill", headers=case['headers'],
        json={**bill_input(case), 'lines': [{'sales_order_line_id': case['order']['items'][0]['sales_order_line_id'], 'quantity': '.5'}]})
    assert response.status_code == 422, response.text
    assert db.query(SRMInvoice).count() == 0
