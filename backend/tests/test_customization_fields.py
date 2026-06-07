from app.apps.customization.models import CustomizationField
from tests.customization_test_utils import customization_headers, create_module, create_text_field


def test_customization_field_create_update_validate(client, db):
    headers = customization_headers(client, db)
    create_module(client, headers)
    field = create_text_field(client, headers)
    assert db.query(CustomizationField).count() == 1

    response = client.post(f"/api/v1/customization/fields/{field['id']}/validate", headers=headers, json={"value": "Project A"})
    assert response.status_code == 200
    assert response.json()["valid"] is True

    response = client.put(f"/api/v1/customization/fields/{field['id']}", headers=headers, json={**field, "field_label": "Project"})
    assert response.status_code == 200
    assert response.json()["field_label"] == "Project"

