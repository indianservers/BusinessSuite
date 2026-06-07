from tests.customization_test_utils import customization_headers


def test_kanban_view_create(client, db):
    headers = customization_headers(client, db)
    response = client.post("/api/v1/customization/kanban", headers=headers, json={"module_name": "partner_projects", "name": "Status Board", "group_by_field": "status", "card_fields_json": ["project_name"], "transition_validation_json": {"allow_drag": True}})
    assert response.status_code == 201, response.text
    assert response.json()["group_by_field"] == "status"

