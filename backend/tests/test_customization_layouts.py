from tests.customization_test_utils import customization_headers, create_module, create_text_field


def test_layout_sections_and_field_reorder(client, db):
    headers = customization_headers(client, db)
    create_module(client, headers)
    field = create_text_field(client, headers)
    layout = client.post("/api/v1/customization/layouts", headers=headers, json={"module_name": "partner_projects", "name": "Default Detail", "layout_type": "detail", "is_default": True})
    assert layout.status_code == 201, layout.text
    section = client.post(f"/api/v1/customization/layouts/{layout.json()['id']}/sections", headers=headers, json={"title": "General", "order_index": 1})
    assert section.status_code == 201, section.text
    response = client.post(f"/api/v1/customization/layouts/{layout.json()['id']}/fields/reorder", headers=headers, json={"fields": [{"field_id": field["id"], "section_id": section.json()["id"], "order_index": 1, "readonly": False, "hidden": False}]})
    assert response.status_code == 200
    assert response.json()["count"] == 1

