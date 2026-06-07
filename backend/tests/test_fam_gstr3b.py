from tests.fam_test_utils import fam_admin_headers


def test_fam_gstr3b_prepare_framework(client, db):
    headers = fam_admin_headers(client, db)
    response = client.post("/api/v1/fam/gst/gstr3b/prepare", headers=headers, json={"period_month": 6, "period_year": 2026})
    assert response.status_code == 200, response.text
    assert response.json()["portal_status"] == "not_configured"
    assert len(response.json()["records"]) == 2
