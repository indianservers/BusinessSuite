from tests.automation_test_utils import automation_headers


def test_automation_routes_require_backend_permissions(client, db):
    blocked = automation_headers(client, db, "automation-blocked@example.com", permissions=[])
    response = client.get("/api/v1/automation/workflows", headers=blocked)
    assert response.status_code == 403

    viewer = automation_headers(client, db, "automation-viewer@example.com", permissions=["automation_view"])
    assert client.get("/api/v1/automation/workflows", headers=viewer).status_code == 200
    response = client.post("/api/v1/automation/workflows", headers=viewer, json={"name": "Denied", "module_name": "crm", "record_type": "lead", "trigger_type": "created"})
    assert response.status_code == 403

