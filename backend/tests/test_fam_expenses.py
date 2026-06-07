from tests.fam_test_utils import fam_admin_headers, ledger_by_nature


def test_fam_expense_claim_create_and_post(client, db):
    headers = fam_admin_headers(client, db)
    expense = ledger_by_nature(client, headers, "expense")
    liability = ledger_by_nature(client, headers, "liability")
    created = client.post("/api/v1/fam/expenses", headers=headers, json={"claim_number": "EXP-001", "claimant_name": "Employee", "claim_date": "2026-06-06", "payable_ledger_id": liability["id"], "lines": [{"expense_ledger_id": expense["id"], "description": "Travel", "taxable_value": 500, "gst_amount": 90}]} )
    assert created.status_code == 201, created.text
    posted = client.post(f"/api/v1/fam/expenses/{created.json()['id']}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    assert posted.json()["status"] == "posted"
