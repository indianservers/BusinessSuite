from admin_security_test_utils import auth_headers


def test_ip_restrictions_are_environment_safe(client, db):
    headers = auth_headers(client, db)
    blocked = client.post("/api/v1/admin/ip-restrictions", headers=headers, json={"cidr": "0.0.0.0/0", "action": "deny", "environment_safe": False})
    assert blocked.status_code == 422
    allowed = client.post("/api/v1/admin/ip-restrictions", headers=headers, json={"cidr": "10.0.0.0/8", "action": "allow"})
    assert allowed.status_code == 201
