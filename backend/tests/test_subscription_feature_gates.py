from phase10_test_utils import auth_headers


def test_subscription_feature_gate_blocks_disabled_feature_and_allows_admin_override(client, db):
    headers = auth_headers(client, db, permissions=["tenant_view", "tenant_admin"])
    client.put("/api/v1/admin/feature-flags", json={"feature_key": "marketplace", "enabled": False, "upgrade_message": "Upgrade required"}, headers=headers)
    blocked = client.get("/api/v1/admin/feature-gates/marketplace", headers=headers)
    assert blocked.status_code == 200
    assert blocked.json()["allowed"] is False

    enable = client.put("/api/v1/admin/feature-flags", json={"feature_key": "marketplace", "enabled": True}, headers=headers)
    assert enable.status_code == 200, enable.text
    update = client.put("/api/v1/admin/subscription", json={"edition": "starter", "status": "active", "admin_override": False}, headers=headers)
    assert update.status_code == 200, update.text
    starter = client.get("/api/v1/admin/feature-gates/marketplace", headers=headers)
    assert starter.json()["allowed"] is False

    override = client.put("/api/v1/admin/subscription", json={"edition": "starter", "status": "active", "admin_override": True}, headers=headers)
    assert override.status_code == 200, override.text
    assert override.json()["admin_override"] is True
    allowed = client.get("/api/v1/admin/feature-gates/marketplace", headers=headers)
    assert allowed.json()["allowed"] is True
