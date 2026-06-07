from tests.fam_test_utils import auth_headers_for, fam_admin_headers


def test_fam_srm_posting_rbac_blocks_readonly_users_from_posting(client, db, superuser_headers):
    admin_headers = fam_admin_headers(client, db)
    viewer_headers = auth_headers_for(client, db, "fam-phase4-viewer@example.com", "fam_viewer", permissions=[
        "fam_view",
        "fam_srm_integration_view",
        "fam_accounting_status_view",
    ])

    status = client.get("/api/v1/fam/integrations/srm/status", headers=viewer_headers)
    assert status.status_code == 200

    blocked = client.post("/api/v1/fam/integrations/srm/post-invoice/999", headers=viewer_headers)
    assert blocked.status_code == 403

    missing = client.post("/api/v1/fam/integrations/srm/post-invoice/999", headers=admin_headers)
    assert missing.status_code == 404

