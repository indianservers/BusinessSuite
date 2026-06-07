from tests.customization_test_utils import customization_headers


def test_customization_backend_rbac(client, db):
    blocked = customization_headers(client, db, "customization-blocked@example.com", permissions=[])
    assert client.get("/api/v1/customization/modules", headers=blocked).status_code == 403

    viewer = customization_headers(client, db, "customization-viewer@example.com", permissions=["customization_view"])
    assert client.get("/api/v1/customization/modules", headers=viewer).status_code == 200
    denied = client.post("/api/v1/customization/modules", headers=viewer, json={"module_api_name": "denied", "module_label": "Denied", "plural_label": "Denied"})
    assert denied.status_code == 403

