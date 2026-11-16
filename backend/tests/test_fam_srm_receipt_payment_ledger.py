from decimal import Decimal

import pytest

from app.apps.fam.models import FAMLedger, FAMLedgerEntry
from tests.srm_test_utils import seed_invoice_parties


@pytest.mark.parametrize("method,expected_code", [
    ("cash", "CASH"),
    (" Cash ", "CASH"),
    ("bank_transfer", "BANK-DEFAULT"),
    ("card", "BANK-DEFAULT"),
    ("upi", "BANK-DEFAULT"),
])
def test_receipt_posts_to_payment_ledger_and_replay_creates_no_entries(
    client, db, superuser_headers, method, expected_code
):
    seed_invoice_parties(db, (702,))
    created = client.post("/api/v1/srm/receipts", headers=superuser_headers,
                          json={"customer_id": 702, "amount": 100, "payment_method": method})
    assert created.status_code == 201, created.text
    receipt_id = created.json()["id"]
    confirmed = client.post(f"/api/v1/srm/receipts/{receipt_id}/confirm", headers=superuser_headers)
    assert confirmed.status_code == 200, confirmed.text

    path = f"/api/v1/fam/integrations/srm/post-receipt/{receipt_id}"
    posted = client.post(path, headers=superuser_headers)
    assert posted.status_code == 200, posted.text
    voucher_id = posted.json()["voucher"]["id"]
    entries = db.query(FAMLedgerEntry).filter_by(voucher_id=voucher_id).all()
    assert len(entries) == 2
    debit = next(entry for entry in entries if entry.debit_amount > 0)
    credit = next(entry for entry in entries if entry.credit_amount > 0)
    assert db.get(FAMLedger, debit.ledger_id).ledger_code == expected_code
    assert debit.debit_amount == credit.credit_amount == Decimal("100")
    assert debit.credit_amount == credit.debit_amount == 0

    replay = client.post(path, headers=superuser_headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["idempotent"] is True
    assert replay.json()["voucher"]["id"] == voucher_id
    assert db.query(FAMLedgerEntry).filter_by(voucher_id=voucher_id).count() == 2
