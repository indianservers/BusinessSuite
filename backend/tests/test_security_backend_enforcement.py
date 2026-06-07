from admin_security_test_utils import auth_headers


def test_backend_security_permissions_are_enforced(client, db):
    viewer = auth_headers(client, db, email="phase8-viewer@example.com", role_name="crm_viewer", permissions=["crm_view"])
    denied = client.post("/api/v1/admin/profiles", headers=viewer, json={"name": "Blocked"})
    assert denied.status_code == 403

    admin = auth_headers(client, db, email="phase8-admin2@example.com", role_name="crm_super_admin")
    allowed = client.post("/api/v1/admin/profiles", headers=admin, json={"name": "Allowed"})
    assert allowed.status_code == 201
