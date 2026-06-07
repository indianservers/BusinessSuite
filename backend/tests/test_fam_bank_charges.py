from tests.fam_test_utils import create_bank_account, fam_admin_headers, ledger_by_nature


def test_bank_charge_posts_payment_voucher(client, db):
    headers = fam_admin_headers(client, db, "bank-charge@example.com")
    account = create_bank_account(client, headers)
    expense = ledger_by_nature(client, headers, "expense")
    response = client.post("/api/v1/fam/bank-charges/post", headers=headers, json={"bank_account_id": account["id"], "expense_ledger_id": expense["id"], "amount": 250, "charge_date": "2026-06-06", "reference_number": "CHG-1", "narration": "Bank fee"})
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "posted"
    assert response.json()["total_debit"] == 250

