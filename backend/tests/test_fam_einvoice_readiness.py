from tests.fam_test_utils import create_balanced_voucher, fam_admin_headers


def test_fam_einvoice_readiness_does_not_fake_irn(client, db):
    headers = fam_admin_headers(client, db)
    voucher = create_balanced_voucher(client, headers)
    response = client.post(f"/api/v1/fam/gst/einvoice/generate/{voucher['id']}", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "not_configured"
    assert data["irn"] is None
    assert "not configured" in data["message"].lower()
