from admin_security_test_utils import auth_headers, create_profile


def test_admin_roles_and_hierarchy(client, db):
    headers = auth_headers(client, db)
    profile = create_profile(client, headers, "Manager Profile")
    parent = client.post("/api/v1/admin/roles", headers=headers, json={"name": "Country Manager", "profile_id": profile["id"]})
    child = client.post("/api/v1/admin/roles", headers=headers, json={"name": "Branch Manager", "profile_id": profile["id"]})
    assert parent.status_code == child.status_code == 201
    hierarchy = client.post("/api/v1/admin/roles/hierarchy", headers=headers, json={"parent_role_id": parent.json()["id"], "child_role_id": child.json()["id"]})
    assert hierarchy.status_code == 201
    invalid = client.post("/api/v1/admin/roles/hierarchy", headers=headers, json={"parent_role_id": parent.json()["id"], "child_role_id": parent.json()["id"]})
    assert invalid.status_code == 422
