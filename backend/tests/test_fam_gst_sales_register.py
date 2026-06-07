from tests.fam_test_utils import fam_admin_headers


def test_fam_gst_sales_register_reads_outward_lines(client, db):
    headers = fam_admin_headers(client, db)
    client.post("/api/v1/fam/gst/calculate", headers=headers, json={"taxable_value": 1000, "company_state_code": "29", "place_of_supply_state": "29", "cgst_rate": 9, "sgst_rate": 9, "igst_rate": 18, "transaction_type": "outward", "persist": True})
    response = client.get("/api/v1/fam/gst/sales-register", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
