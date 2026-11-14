from uuid import uuid4
from tests.test_industry_operations import business, stylist, booking, post, state, ROOT
from tests.test_contact_directory import directory_identity


def test_advance_partial_payments_and_native_invoice_allocation(client, db, business):
    from app.apps.srm.models import SRMReceipt, SRMReceiptAllocation, SRMInvoice
    h, buyer, _, service = business
    provider = stylist(client, h)
    row = post(client, h, '/appointments', booking(client, h, buyer, service, provider))
    base = ROOT + f'/appointments/{row["id"]}'
    payment = {'request_id': str(uuid4()), 'expected_revision': row['revision'], 'amount': '100.00', 'payment_method': 'cash'}
    paid = client.post(base + '/payments', headers=h, json=payment)
    assert paid.status_code == 201, paid.text
    panel = paid.json()
    assert float(panel['total']) == 590 and float(panel['advance']) == 100 and float(panel['balance']) == 490
    assert panel['visit_status'] == 'booked' and panel['invoice'] is None
    retry = client.post(base + '/payments', headers=h, json={**payment, 'amount': '100'})
    assert retry.status_code == 201, retry.text
    assert db.query(SRMReceipt).count() == 1
    assert client.post(base + '/payments', headers=h, json={**payment, 'amount': '101'}).status_code == 409
    assert client.post(base + '/payments', headers=h, json={**payment, 'request_id': str(uuid4()), 'expected_revision': panel['revision'], 'amount': '500'}).status_code == 422
    assert db.query(SRMReceipt).count() == 1
    row = {**row, 'revision': panel['revision']}
    for status in ['checked_in', 'in_service', 'completed']:
        row = state(client, h, row, status)
    invoice = post(client, h, f'/records/{row["id"]}/invoice', {'expected_revision': row['revision']})
    before = client.get(base + '/billing', headers=h).json()
    assert client.post(base + '/apply-advances', headers=h, json={'expected_revision': before['revision']}).status_code == 409
    assert client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve', headers=h).status_code == 200
    applied = client.post(base + '/apply-advances', headers=h, json={'expected_revision': before['revision']})
    assert applied.status_code == 200, applied.text
    panel = applied.json()
    assert float(panel['advance']) == 0 and float(panel['paid']) == 100 and float(panel['balance']) == 490
    final = client.post(base + '/payments', headers=h, json={'request_id': str(uuid4()), 'expected_revision': panel['revision'], 'amount': '490', 'payment_method': 'upi', 'reference_number': 'UTR-EXAMPLE'})
    assert final.status_code == 201, final.text
    assert float(final.json()['balance']) == 0 and final.json()['invoice']['status'] == 'paid'
    assert db.query(SRMReceipt).count() == 2 and db.query(SRMReceiptAllocation).count() == 2
    assert float(db.get(SRMInvoice, invoice['id']).paid_amount) == 590


def test_cancellation_retains_advance_and_does_not_collect_more(client, business):
    h, buyer, _, service = business
    provider = stylist(client, h)
    row = post(client, h, '/appointments', booking(client, h, buyer, service, provider))
    base = ROOT + f'/appointments/{row["id"]}'
    paid = client.post(base + '/payments', headers=h, json={'request_id': str(uuid4()), 'expected_revision': row['revision'], 'amount': '50'})
    assert paid.status_code == 201, paid.text
    row = state(client, h, {**row, 'revision': paid.json()['revision']}, 'cancelled', reason='Customer requested')
    panel = client.get(base + '/billing', headers=h)
    assert panel.status_code == 200, panel.text
    assert float(panel.json()['advance']) == 50
    assert client.post(base + '/payments', headers=h, json={'request_id': str(uuid4()), 'expected_revision': row['revision'], 'amount': '50'}).status_code == 409


def test_failed_allocation_rolls_back_receipt_and_appointment_changes(client, db, business, monkeypatch):
    from fastapi import HTTPException
    from app.apps.srm.api import router as native
    from app.apps.srm.models import SRMReceipt, SRMReceiptAllocation, SRMInvoice
    from app.apps.srm.industry_models import IndustryRecord
    h, buyer, _, service = business
    row = post(client, h, '/appointments', booking(client, h, buyer, service, stylist(client, h)))
    for status in ['checked_in', 'in_service', 'completed']:
        row = state(client, h, row, status)
    invoice = post(client, h, f'/records/{row["id"]}/invoice', {'expected_revision': row['revision']})
    assert client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve', headers=h).status_code == 200
    base = ROOT + f'/appointments/{row["id"]}'
    current = client.get(base + '/billing', headers=h).json()
    def reject(*args, **kwargs):
        raise HTTPException(409, 'Allocation changed concurrently')
    monkeypatch.setattr(native, 'allocate_receipt_operation', reject)
    response = client.post(base + '/payments', headers=h, json={'request_id': str(uuid4()), 'expected_revision': current['revision'], 'amount': '100'})
    assert response.status_code == 409, response.text
    assert db.query(SRMReceipt).count() == 0 and db.query(SRMReceiptAllocation).count() == 0
    assert float(db.get(SRMInvoice, invoice['id']).paid_amount) == 0
    assert not db.get(IndustryRecord, row['id']).data.get('_payment_requests')


def test_billing_access_requires_finance_permission_and_current_branch(client, db, business):
    from app.models.company import Branch
    from app.apps.srm.models import SRMReceipt
    from tests.test_settings_hub import actor
    from test_identity_utils import attach_workflow_branch
    h, buyer, _, service = business
    row = post(client, h, '/appointments', booking(client, h, buyer, service, stylist(client, h)))
    base = ROOT + f'/appointments/{row["id"]}'
    reader, user = actor(db, 'appointment-non-finance-reader', permissions=['srm_view'])
    branch = attach_workflow_branch(db, user); db.commit()
    reader = {**reader, 'X-Suite-Branch': str(branch.id)}
    assert client.get(base + '/billing', headers=reader).status_code == 403
    assert client.post(base + '/payments', headers=reader, json={'request_id': str(uuid4()), 'expected_revision': row['revision'], 'amount': '100'}).status_code == 403
    foreign = Branch(company_id=1, name='Other visit branch', is_active=True)
    db.add(foreign); db.commit()
    other = {**h, 'X-Suite-Branch': str(foreign.id)}
    assert client.get(base + '/billing', headers=other).status_code == 404
    assert db.query(SRMReceipt).count() == 0
