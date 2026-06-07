from tests.fam_test_utils import fam_admin_headers


def test_fam_tds_calculation_uses_threshold(client, db):
    headers = fam_admin_headers(client, db)
    section = client.post("/api/v1/fam/tds/sections", headers=headers, json={"section_code": "194C", "description": "Contractor", "default_rate": 2, "threshold_amount": 1000, "effective_from": "2026-04-01"}).json()
    below = client.post("/api/v1/fam/tds/calculate", headers=headers, json={"section_id": section["id"], "taxable_amount": 500})
    above = client.post("/api/v1/fam/tds/calculate", headers=headers, json={"section_id": section["id"], "taxable_amount": 2000})
    assert below.json()["tds_amount"] == 0
    assert above.json()["tds_amount"] == 40
