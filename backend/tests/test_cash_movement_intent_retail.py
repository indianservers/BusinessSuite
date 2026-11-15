"""Keyed cash remains the actual native drawer inside a selected Retail context."""
from uuid import uuid4
from app.apps.srm.models import SRMPOSCashMovement
from tests.test_retail_return_http import retail_setup, scenario, catalog, directory_identity


def test_selected_retail_cash_retry_and_other_pack_denial(client, db, retail_setup):
    headers, actor, branch, context_id, old_register, *_ = retail_setup
    closed = client.post('/api/v1/srm/pos/cashier-closing', headers=headers,
        json={'session_id': old_register, 'counted_cash': '0'})
    assert closed.status_code == 201, closed.text
    opened = client.post('/api/v1/srm/pos/sessions', headers=headers,
        json={'opening_cash': '20', 'register_name': 'Durable Retail till'})
    assert opened.status_code == 201, opened.text
    register = opened.json()['session']['id']
    body = {'session_id': register, 'request_key': str(uuid4()),
        'movement_type': 'cash_out', 'amount': '2.50', 'reason': 'Verified petty cash'}
    first = client.post('/api/v1/srm/pos/cash-movements', headers=headers, json=body)
    assert first.status_code == 201, first.text
    replay = client.post('/api/v1/srm/pos/cash-movements', headers=headers, json=body)
    assert replay.status_code == 201, replay.text
    assert replay.json()['movement_id'] == first.json()['movement_id']
    assert replay.json()['expected_cash'] == 17.5
    item = db.query(SRMPOSCashMovement).filter_by(request_key=body['request_key']).one()
    assert (item.request_context_id, item.request_branch_id, item.request_currency) == (context_id, branch, 'INR')
    from tests.test_business_pack_http_integration import grant
    other, _ = grant(db, actor, branch, 'hospital', 'hospital_manager')
    denied = client.post('/api/v1/srm/pos/cash-movements',
        headers={**headers, 'X-Suite-Pack-Context': str(other.id)}, json=body)
    assert denied.status_code in (403, 404), denied.text
    assert 'movement_id' not in denied.json()
    assert db.query(SRMPOSCashMovement).count() == 1
