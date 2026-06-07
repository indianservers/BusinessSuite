from tests.customization_test_utils import customization_headers, create_module, create_text_field


def test_dynamic_custom_module_record_crud(client, db):
    headers = customization_headers(client, db)
    create_module(client, headers)
    create_text_field(client, headers)
    created = client.post("/api/v1/custom/partner_projects", headers=headers, json={"values": {"project_name": "Project A"}})
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]
    assert client.get("/api/v1/custom/partner_projects", headers=headers).json()["total"] == 1
    assert client.get(f"/api/v1/custom/partner_projects/{record_id}", headers=headers).json()["values_json"]["project_name"] == "Project A"
    updated = client.put(f"/api/v1/custom/partner_projects/{record_id}", headers=headers, json={"values": {"project_name": "Project B"}})
    assert updated.status_code == 200
    assert updated.json()["values_json"]["project_name"] == "Project B"
    assert client.delete(f"/api/v1/custom/partner_projects/{record_id}", headers=headers).status_code == 204

