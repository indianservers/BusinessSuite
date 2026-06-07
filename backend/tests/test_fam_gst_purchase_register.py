from tests.fam_test_utils import fam_admin_headers


def test_fam_gst_purchase_register_reads_inward_lines(client, db):
    headers = fam_admin_headers(client, db)
    client.post("/api/v1/fam/gst/calculate", headers=headers, json={"taxable_value": 1000, "company_state_code": "29", "place_of_supply_state": "27", "igst_rate": 18, "transaction_type": "inward", "itc_eligible": True, "persist": True})
    response = client.get("/api/v1/fam/gst/purchase-register", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
