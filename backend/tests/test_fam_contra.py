from tests.fam_test_utils import fam_admin_headers, ledger_by_type


def test_contra_posts_between_bank_and_cash_ledgers(client, db):
    headers = fam_admin_headers(client, db, "contra@example.com")
    bank = ledger_by_type(client, headers, "bank")
    cash = ledger_by_type(client, headers, "cash")
    response = client.post("/api/v1/fam/contra/post", headers=headers, json={"from_ledger_id": cash["id"], "to_ledger_id": bank["id"], "amount": 1000, "contra_date": "2026-06-06", "reference_number": "CONTRA-1", "narration": "Cash deposit"})
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "posted"
    assert response.json()["source_record_type"] == "contra"

