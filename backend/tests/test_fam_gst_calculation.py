from tests.fam_test_utils import fam_admin_headers


def test_fam_gst_calculation_persists_transaction_line(client, db):
    headers = fam_admin_headers(client, db)
    response = client.post("/api/v1/fam/gst/calculate", headers=headers, json={
        "taxable_value": 1000,
        "company_state_code": "29",
        "place_of_supply_state": "29",
        "cgst_rate": 9,
        "sgst_rate": 9,
        "igst_rate": 18,
        "supply_type": "b2b",
        "transaction_type": "outward",
        "persist": True,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["cgst_amount"] == 90
    assert data["sgst_amount"] == 90
    assert data["igst_amount"] == 0
    assert data["transaction_line"]["id"]
