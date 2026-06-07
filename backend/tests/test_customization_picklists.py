from tests.customization_test_utils import customization_headers


def test_global_picklist_create(client, db):
    headers = customization_headers(client, db)
    response = client.post("/api/v1/customization/picklists", headers=headers, json={"api_name": "project_statuses", "label": "Project Statuses", "values": [{"value": "open", "label": "Open"}]})
    assert response.status_code == 201, response.text
    assert response.json()["api_name"] == "project_statuses"

