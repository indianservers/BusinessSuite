from decimal import Decimal
from uuid import uuid4

import pytest

from app.apps.fam.models import FAMBillReference, FAMLedgerEntry, FAMVoucher
from app.apps.srm.models import SRMReceipt
from tests.srm_test_utils import create_sales_order, seed_invoice_parties


@pytest.mark.parametrize("post_invoice_before_payment", [True, False])
@pytest.mark.parametrize("payment_size", ["partial", "full"])
def test_audit_order_to_cash_reconciles_sales_finance_and_reports_regardless_of_posting_order(client, db, superuser_headers, monkeypatch, post_invoice_before_payment, payment_size):
    from app.shared import payment_requests
    monkeypatch.setattr(payment_requests, "gateway_for", lambda organization: None)
    seed_invoice_parties(db)
    headers = superuser_headers
    order = create_sales_order(client, headers)
    draft = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=headers)
    assert draft.status_code == 201, draft.text
    invoice_id = draft.json()["id"]
    approved = client.post(f"/api/v1/srm/invoices/{invoice_id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    total = Decimal(str(approved.json()["total_amount"]))
    amount = total if payment_size == "full" else Decimal("50000")
    invoice_path = f"/api/v1/fam/integrations/srm/post-invoice/{invoice_id}"
    invoice_posting = None
    if post_invoice_before_payment:
        response = client.post(invoice_path, headers=headers)
        assert response.status_code == 200, response.text
        invoice_posting = response.json()
    voucher_count, receipt_count = db.query(FAMVoucher).count(), db.query(SRMReceipt).count()
    requested = client.post("/api/v1/payment-requests", headers=headers, json={"source_type": "srm_invoice", "source_id": invoice_id, "amount": str(amount), "request_id": str(uuid4())})
    assert requested.status_code == 201, requested.text
    assert requested.json()["status"] == "awaiting_gateway"
    assert db.query(FAMVoucher).count() == voucher_count
    assert db.query(SRMReceipt).count() == receipt_count
    receipt = client.post("/api/v1/srm/receipts", headers=headers, json={"customer_id": 101, "amount": str(amount)})
    assert receipt.status_code == 201, receipt.text
    receipt_id = receipt.json()["id"]
    confirmed = client.post(f"/api/v1/srm/receipts/{receipt_id}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    allocated = client.post(f"/api/v1/srm/receipts/{receipt_id}/allocate", headers=headers, json={"invoice_id": invoice_id, "amount": str(amount)})
    assert allocated.status_code == 200, allocated.text
    allocation_id = allocated.json()["allocation"]["id"]
    expected = total - amount
    assert Decimal(str(allocated.json()["invoice"]["balance_amount"])) == expected
    if not post_invoice_before_payment:
        response = client.post(invoice_path, headers=headers)
        assert response.status_code == 200, response.text
        invoice_posting = response.json()
    posted_receipt = client.post(f"/api/v1/fam/integrations/srm/post-receipt/{receipt_id}", headers=headers)
    assert posted_receipt.status_code == 200, posted_receipt.text
    allocation_path = f"/api/v1/fam/integrations/srm/post-allocation/{allocation_id}"
    posted_allocation = client.post(allocation_path, headers=headers)
    assert posted_allocation.status_code == 200, posted_allocation.text
    bill = db.get(FAMBillReference, invoice_posting["billReference"]["id"])
    entries = db.query(FAMLedgerEntry).filter_by(ledger_id=bill.ledger_id).all()
    ledger_balance = sum((Decimal(entry.debit_amount or 0) - Decimal(entry.credit_amount or 0) for entry in entries), Decimal("0"))
    assert ledger_balance == expected
    assert Decimal(bill.outstanding_amount) == expected
    assert Decimal(str(client.get("/api/v1/fam/ar/outstanding", headers=headers).json()["totalOutstanding"])) == expected
    reports = client.get("/api/v1/srm/reports", headers=headers)
    assert reports.status_code == 200, reports.text
    assert Decimal(str(reports.json()["invoice_register"]["total"])) == total
    assert Decimal(str(reports.json()["customer_outstanding"]["total_outstanding"])) == expected
    assert Decimal(str(reports.json()["cash_margin_report"]["collected_total"])) == amount
    count = db.query(FAMVoucher).count()
    for path in [invoice_path, f"/api/v1/fam/integrations/srm/post-receipt/{receipt_id}", allocation_path]:
        repeated = client.post(path, headers=headers)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["idempotent"] is True
    assert db.query(FAMVoucher).count() == count
    db.refresh(bill)
    assert Decimal(bill.outstanding_amount) == expected
