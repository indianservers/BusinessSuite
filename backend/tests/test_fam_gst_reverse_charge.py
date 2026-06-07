from tests.fam_test_utils import fam_admin_headers


def test_fam_gst_reverse_charge_and_exempt_classification(client, db):
    headers = fam_admin_headers(client, db)
    rcm = client.post("/api/v1/fam/gst/calculate", headers=headers, json={"taxable_value": 500, "company_state_code": "29", "place_of_supply_state": "29", "cgst_rate": 9, "sgst_rate": 9, "igst_rate": 18, "transaction_type": "rcm", "reverse_charge": True, "itc_eligible": True})
    exempt = client.post("/api/v1/fam/gst/calculate", headers=headers, json={"taxable_value": 500, "company_state_code": "29", "place_of_supply_state": "29", "cgst_rate": 9, "sgst_rate": 9, "igst_rate": 18, "exempt_type": "nil"})
    assert rcm.status_code == 200
    assert rcm.json()["reverse_charge"] is True
    assert exempt.status_code == 200
    assert exempt.json()["total_tax"] == 0
