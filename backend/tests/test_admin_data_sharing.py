from admin_security_test_utils import auth_headers


def test_data_sharing_rules(client, db):
    headers = auth_headers(client, db)
    response = client.post("/api/v1/admin/data-sharing-rules", headers=headers, json={"module_name": "deals", "name": "Branch read", "rule_json": {"branch": "south"}, "access_level": "read"})
    assert response.status_code == 201
    listing = client.get("/api/v1/admin/data-sharing-rules", headers=headers)
    assert listing.json()["total"] == 1
