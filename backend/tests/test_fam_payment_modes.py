from tests.fam_test_utils import fam_admin_headers, ledger_by_type


def test_payment_mode_create_and_validation(client, db):
    headers = fam_admin_headers(client, db, "payment-mode@example.com")
    ledger = ledger_by_type(client, headers, "bank")
    response = client.post("/api/v1/fam/payment-modes", headers=headers, json={"name": "UPI", "type": "upi", "default_ledger_id": ledger["id"], "active": True})
    assert response.status_code == 201, response.text
    assert response.json()["type"] == "upi"

    invalid = client.post("/api/v1/fam/payment-modes", headers=headers, json={"name": "Bad", "type": "crypto"})
    assert invalid.status_code == 422
