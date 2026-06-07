from tests.fam_test_utils import fam_admin_headers


def test_fam_gst_intra_and_inter_state_logic(client, db):
    headers = fam_admin_headers(client, db)
    intra = client.post("/api/v1/fam/gst/calculate", headers=headers, json={"taxable_value": 1000, "company_state_code": "29", "place_of_supply_state": "29", "cgst_rate": 9, "sgst_rate": 9, "igst_rate": 18})
    inter = client.post("/api/v1/fam/gst/calculate", headers=headers, json={"taxable_value": 1000, "company_state_code": "29", "place_of_supply_state": "27", "cgst_rate": 9, "sgst_rate": 9, "igst_rate": 18})
    assert intra.status_code == 200
    assert inter.status_code == 200
    assert intra.json()["intra_state"] is True
    assert inter.json()["inter_state"] is True
    assert inter.json()["igst_amount"] == 180
