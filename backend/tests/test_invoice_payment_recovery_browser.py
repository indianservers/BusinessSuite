"""Ordinary invoice collection through the real App, including a lost committed reply."""
import json
import tempfile
from pathlib import Path
from decimal import Decimal
import pytest
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMReceiptAllocation
from tests.srm_test_utils import seed_invoice_parties


@pytest.mark.parametrize('width', [1440, 390])
def test_invoice_payment_reload_replays_original_receipt(client, db, superuser_headers, monkeypatch, width):
    headers = superuser_headers
    seed_invoice_parties(db)
    from app.models.company import Branch
    branch = db.query(Branch).filter_by(company_id=1).first()
    assert branch is not None
    headers = {**headers, 'X-Suite-Branch': str(branch.id)}
    response = client.post('/api/v1/srm/sales-orders', headers=headers, json={
        'title': 'Invoice recovery browser', 'customer_id': 101, 'currency': 'INR',
        'lines': [{'description': 'Recovery service', 'quantity': 1, 'unit_price': 100}]})
    assert response.status_code == 201, response.text
    response = client.post(f'/api/v1/srm/invoices/draft-from-sales-order/{response.json()["id"]}', headers=headers)
    assert response.status_code == 201, response.text
    invoice = response.json()
    response = client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve', headers=headers)
    assert response.status_code == 200, response.text
    identity = client.get('/api/v1/auth/me', headers=headers).json()
    access = client.get('/api/v1/access/me', headers=headers).json()
    role = identity['role'] if isinstance(identity['role'], str) else identity['role']['name']
    identity.update(role=role, primary_role=role, access=access)
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'construction-invoice-native.cjs')
    with tempfile.TemporaryDirectory(prefix='srm-invoice-recovery-') as folder:
        auth_file = Path(folder) / 'auth.json'
        auth_file.write_text(json.dumps({'token': headers['Authorization'].split(' ', 1)[1],
            'user': identity, 'branch': str(branch.id), 'context': '', 'width': width,
            'invoice': invoice['id'], 'invoice_number': invoice['invoice_number'],
            'first_amount': '40.00', 'final_amount': '60.00'}), encoding='utf-8')
        monkeypatch.setenv('SUITE_QA_AUTH_FILE', str(auth_file))
        from tests.test_control_browser import test_control_center_real_browser
        test_control_center_real_browser(client, db, None, headers)
    db.expire_all()
    row = db.get(SRMInvoice, invoice['id'])
    assert row.paid_amount == Decimal('100') and row.balance_amount == 0
    assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 2
