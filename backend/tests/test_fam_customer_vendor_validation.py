from tests.fam_test_utils import fam_admin_headers, party_payload


def test_fam_invalid_party_type_is_rejected(client, db):
    headers = fam_admin_headers(client, db)
    payload = party_payload("customer", "BAD-100", "Bad Party")
    payload["party_type"] = "prospect"

    response = client.post("/api/v1/fam/parties", headers=headers, json=payload)

    assert response.status_code == 422
    assert "Invalid party type" in response.json()["detail"]


def test_fam_invalid_gstin_is_rejected(client, db):
    headers = fam_admin_headers(client, db)
    payload = party_payload("customer", "GST-100", "GST Bad")
    payload["gstin"] = "BADGST"

    response = client.post("/api/v1/fam/parties", headers=headers, json=payload)

    assert response.status_code == 422
    assert "GSTIN" in response.json()["detail"]


def test_fam_party_opening_balance_cannot_be_both_dr_and_cr(client, db):
    headers = fam_admin_headers(client, db)
    payload = party_payload("vendor", "OPEN-100", "Opening Balance Vendor")
    payload["opening_balance_dr"] = 100
    payload["opening_balance_cr"] = 50

    response = client.post("/api/v1/fam/parties", headers=headers, json=payload)

    assert response.status_code == 422
    assert "opening balance" in response.json()["detail"]

