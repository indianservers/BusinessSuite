from tests.fam_test_utils import fam_admin_headers


def test_fam_gstr1_prepare_framework(client, db):
    headers = fam_admin_headers(client, db)
    client.post("/api/v1/fam/gst/calculate", headers=headers, json={"taxable_value": 1000, "company_state_code": "29", "place_of_supply_state": "29", "cgst_rate": 9, "sgst_rate": 9, "igst_rate": 18, "transaction_type": "outward", "persist": True})
    response = client.post("/api/v1/fam/gst/gstr1/prepare", headers=headers, json={"period_month": 6, "period_year": 2026})
    assert response.status_code == 200, response.text
    assert response.json()["portal_status"] == "not_configured"
    assert response.json()["records"][0]["record_count"] == 1
