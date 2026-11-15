from uuid import uuid4
from decimal import Decimal
import pytest
from sqlalchemy import select, func
from app.apps.srm.models import SRMInvoice, SRMInvoiceDraft, SRMInvoiceLine, SRMReceipt
from app.business_packs.accounting_firm.models import AccountsCommand
from tests.test_accounts_periods import accounts, scenario, catalog, directory_identity, create, prepared, revision, send, body
from tests.test_accounts_actual_time import delivery


def approved(client, case):
    row = prepared(client, case, create(client, case))
    return send(client, case['reviewer']['headers'], f"/{row['id']}/approve",
        revision(row) | {'expected_work_revision': row['work_revision']})


def billing(client, case, row, payload=None, status=201):
    return send(client, case['headers'], f"/{row['id']}/invoice", payload or
        revision(row) | {'expected_work_revision': row['work_revision'], 'amount': '1500.00'}, status=status)


def test_approved_period_creates_one_native_invoice_and_retry(client, db, accounts):
    row = approved(client, accounts)
    payload = revision(row) | {'expected_work_revision': row['work_revision'], 'amount': '1500.00'}
    result = billing(client, accounts, row, payload)
    assert billing(client, accounts, row, payload) == result
    billing(client, accounts, row, payload | {'request_key': str(uuid4())}, status=409)
    assert db.query(SRMInvoice).count() == db.query(SRMInvoiceDraft).count() == db.query(SRMInvoiceLine).count() == 1
    invoice = db.query(SRMInvoice).one()
    assert invoice.engagement_id == accounts['engagement'] and invoice.customer_id == 101
    assert invoice.total_amount == invoice.balance_amount == Decimal('1500.00')
    assert db.query(SRMInvoiceLine).one().source_type == 'accounts_period'


@pytest.mark.parametrize('fault', ['unapproved', 'stale', 'preparer', 'changed_review'])
def test_native_billing_denials_do_not_create_financial_records(client, db, accounts, fault):
    row = approved(client, accounts) if fault != 'unapproved' else create(client, accounts)
    payload = revision(row) | {'expected_work_revision': max(row['work_revision'], 1), 'amount': '1500.00'}
    headers = accounts['headers']
    status = 409
    if fault == 'stale': payload['expected_revision'] = 999
    if fault == 'preparer': headers = accounts['preparer']['headers']; status = 403
    if fault == 'changed_review':
        send(client, accounts['preparer']['headers'], f"/{row['id']}/work",
            revision(row) | {'summary': 'Changed after independent review'}, method='put')
    send(client, headers, f"/{row['id']}/invoice", payload, status=status)
    assert db.query(SRMInvoice).count() == db.query(SRMInvoiceDraft).count() == 0


def test_billing_late_failure_rolls_back_invoice_and_can_retry(client, db, accounts, monkeypatch):
    from app.apps.srm.api import router
    row = approved(client, accounts)
    payload = revision(row) | {'expected_work_revision': row['work_revision'], 'amount': '1500.00'}
    original = router._create_invoice_from_amount
    def fail_after_native(*args, **kwargs):
        original(*args, **kwargs)
        from fastapi import HTTPException
        raise HTTPException(409, 'Injected late native failure')
    monkeypatch.setattr(router, '_create_invoice_from_amount', fail_after_native)
    billing(client, accounts, row, payload, status=409)
    assert db.query(SRMInvoice).count() == db.query(SRMInvoiceDraft).count() == 0
    assert db.query(AccountsCommand).filter_by(action='invoice').count() == 0
    monkeypatch.setattr(router, '_create_invoice_from_amount', original)
    billing(client, accounts, row, payload)
    assert db.query(SRMInvoice).count() == 1


def test_native_issue_partial_and_final_collection_use_existing_receipt_ledger(client, db, accounts):
    from tests.test_business_pack_http_integration import native_actor, grant
    from app.business_packs.models import PackContext
    row = approved(client, accounts)
    result = billing(client, accounts, row)
    invoice_id = result['invoice_id']
    response = client.post(f'/api/v1/srm/invoices/{invoice_id}/approve', headers=accounts['headers'])
    assert response.status_code == 200, response.text
    headers, officer = native_actor(db, accounts['branch'])
    grant(db, officer, accounts['branch'], 'accounting_firm', 'billing_officer', db.get(PackContext, accounts['context']))
    headers = headers | {'X-Suite-Pack-Context': str(accounts['context'])}
    path = f"/api/v1/srm/accounts/periods/{row['id']}/payments"
    payment = {'request_id': str(uuid4()), 'amount': '500.00', 'payment_method': 'bank_transfer'}
    paid = client.post(path, headers=headers, json=payment)
    assert paid.status_code == 201, paid.text
    assert client.post(path, headers=headers, json=payment).json()['receipt_id'] == paid.json()['receipt_id']
    balance_path = f"/api/v1/srm/accounts/periods/{row['id']}/billing"
    balance = client.get(balance_path, headers=headers)
    assert balance.status_code == 200, balance.text
    assert Decimal(balance.json()['invoice']['balance_amount']) == Decimal('1000.00')
    final = client.post(path, headers=headers, json=payment | {'request_id': str(uuid4()), 'amount': '1000.00'})
    assert final.status_code == 201, final.text
    assert Decimal(client.get(balance_path, headers=headers).json()['invoice']['balance_amount']) == 0
    assert db.query(SRMReceipt).count() == 2


def test_project_linked_service_uses_native_period_invoice_without_source_bypass(client, db, accounts, delivery):
    row = approved(client, accounts)
    result = billing(client, accounts, row)
    assert db.get(SRMInvoice, result['invoice_id']).engagement_id == accounts['engagement']
    assert result['project_id'] == delivery


def test_native_existing_invoice_cannot_be_adopted_as_another_period_birth(client, db, accounts, monkeypatch):
    from app.apps.srm.api import router
    first = billing(client, accounts, approved(client, accounts))
    row = send(client, accounts['headers'], '', body(accounts) | {'starts_on': '2026-03-01',
        'ends_on': '2026-03-31', 'due_on': '2026-04-10'}, status=201)
    row = prepared(client, accounts, row)
    row = send(client, accounts['reviewer']['headers'], f"/{row['id']}/approve", revision(row) | {
        'expected_work_revision': row['work_revision']})
    monkeypatch.setattr(router, '_create_invoice_from_amount', lambda *args, **kwargs: db.get(SRMInvoice, first['invoice_id']))
    billing(client, accounts, row, status=409)
    assert db.query(SRMInvoice).count() == 1
    assert db.query(AccountsCommand).filter_by(action='invoice').count() == 1
