from tests.fam_test_utils import create_balanced_voucher, fam_admin_headers


def test_fam_ewaybill_readiness_does_not_fake_ewb_number(client, db):
    headers = fam_admin_headers(client, db)
    voucher = create_balanced_voucher(client, headers)
    response = client.post(f"/api/v1/fam/gst/ewaybill/generate/{voucher['id']}", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "not_configured"
    assert data["ewb_number"] is None
    assert "not configured" in data["message"].lower()
