from tests.fam_test_utils import auth_headers_for, balanced_voucher_payload, fam_admin_headers


def test_voucher_backend_rbac_blocks_viewer_mutation(client, db):
    viewer = auth_headers_for(client, db, "fam-viewer-voucher@example.com", "fam_viewer", permissions=["fam_view", "fam_vouchers_view"])
    admin = fam_admin_headers(client, db)
    payload = balanced_voucher_payload(client, admin)
    response = client.post("/api/v1/fam/vouchers", headers=viewer, json=payload)
    assert response.status_code == 403
    assert client.get("/api/v1/fam/vouchers", headers=viewer).status_code == 200
