from tests.fam_test_utils import fam_admin_headers


def test_fam_tds_sections_and_rates_configurable(client, db):
    headers = fam_admin_headers(client, db)
    section = client.post("/api/v1/fam/tds/sections", headers=headers, json={"section_code": "194J", "description": "Professional fees", "default_rate": 10, "threshold_amount": 30000, "effective_from": "2026-04-01"})
    assert section.status_code == 201, section.text
    rate = client.post("/api/v1/fam/tds/rates", headers=headers, json={"section_id": section.json()["id"], "rate": 10, "threshold_amount": 30000, "effective_from": "2026-04-01"})
    assert rate.status_code == 201, rate.text
    assert client.get("/api/v1/fam/tds/sections", headers=headers).json()["total"] == 1
