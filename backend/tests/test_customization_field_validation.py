from tests.customization_test_utils import customization_headers, create_module, create_text_field


def test_required_type_picklist_unique_and_unknown_field_validation(client, db):
    headers = customization_headers(client, db)
    create_module(client, headers)
    field = create_text_field(client, headers, unique=True)
    missing = client.post(f"/api/v1/customization/fields/{field['id']}/validate", headers=headers, json={"value": ""})
    assert missing.status_code == 400

    number = client.post("/api/v1/customization/fields", headers=headers, json={"module_name": "partner_projects", "field_api_name": "budget", "field_label": "Budget", "field_type": "number"})
    assert number.status_code == 201, number.text
    invalid_number = client.post(f"/api/v1/customization/fields/{number.json()['id']}/validate", headers=headers, json={"value": "abc"})
    assert invalid_number.status_code == 400

    picklist = client.post("/api/v1/customization/fields", headers=headers, json={"module_name": "partner_projects", "field_api_name": "status", "field_label": "Status", "field_type": "picklist", "options": [{"value": "open", "label": "Open"}]})
    assert picklist.status_code == 201, picklist.text
    invalid_picklist = client.post(f"/api/v1/customization/fields/{picklist.json()['id']}/validate", headers=headers, json={"value": "closed"})
    assert invalid_picklist.status_code == 400

    created = client.post("/api/v1/custom/partner_projects", headers=headers, json={"values": {"project_name": "A", "budget": 10, "status": "open"}})
    assert created.status_code == 201, created.text
    duplicate = client.post("/api/v1/custom/partner_projects", headers=headers, json={"values": {"project_name": "A", "budget": 20, "status": "open"}})
    assert duplicate.status_code == 400

