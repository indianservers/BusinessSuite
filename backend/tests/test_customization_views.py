from tests.customization_test_utils import customization_headers


def test_list_view_create_update_delete(client, db):
    headers = customization_headers(client, db)
    response = client.post("/api/v1/customization/views", headers=headers, json={"module_name": "partner_projects", "name": "Open Projects", "filters_json": {"status": "open"}, "columns_json": ["project_name"], "shared": True})
    assert response.status_code == 201, response.text
    view_id = response.json()["id"]
    response = client.put(f"/api/v1/customization/views/{view_id}", headers=headers, json={"module_name": "partner_projects", "name": "All Projects", "columns_json": ["project_name"], "shared": True})
    assert response.status_code == 200
    assert response.json()["name"] == "All Projects"
    assert client.delete(f"/api/v1/customization/views/{view_id}", headers=headers).status_code == 204

