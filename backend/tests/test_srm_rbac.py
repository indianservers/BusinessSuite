from tests.srm_test_utils import auth_headers_for


def test_srm_role_without_permission_is_api_blocked(client, db):
    headers = auth_headers_for(client, db, "viewer-without-perms@srm.example.com", "srm_viewer")
    response = client.get("/api/v1/srm/module-info", headers=headers)
    assert response.status_code == 403
