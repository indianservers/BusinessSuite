from tests.test_fam_bank_statement_matching import post_bank_voucher
from tests.fam_test_utils import create_bank_account, fam_admin_headers


def test_manual_match_and_reconcile_statement(client, db):
    headers = fam_admin_headers(client, db, "bank-reconcile@example.com")
    account = create_bank_account(client, headers)
    voucher = post_bank_voucher(client, headers)
    statement = client.post("/api/v1/fam/bank-statements/import", headers=headers, json={
        "bank_account_id": account["id"],
        "statement_period_start": "2026-06-01",
        "statement_period_end": "2026-06-30",
        "imported_file_name": "reconcile.csv",
        "lines": [{"transaction_date": "2026-06-06", "description": "Customer receipt REF-1", "reference_number": "REF-1", "debit_amount": 0, "credit_amount": 1000, "balance": 1000}],
    }).json()
    line_id = statement["lines"][0]["id"]

    matched = client.post(f"/api/v1/fam/bank-statements/{statement['id']}/match", headers=headers, json={"statement_line_id": line_id, "voucher_id": voucher["id"], "matched_amount": 1000})
    assert matched.status_code == 200, matched.text
    reconciled = client.post(f"/api/v1/fam/bank-statements/{statement['id']}/reconcile", headers=headers)
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["statement"]["status"] == "reconciled"

