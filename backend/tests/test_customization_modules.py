from app.apps.customization.models import CustomizationAuditLog, CustomizationModule
from tests.customization_test_utils import customization_headers, create_module


def test_customization_module_crud_and_audit(client, db):
    headers = customization_headers(client, db)
    module = create_module(client, headers)
    assert db.query(CustomizationModule).count() == 1
    assert db.query(CustomizationAuditLog).filter(CustomizationAuditLog.entity_type == "module").count() == 1

    response = client.get(f"/api/v1/customization/modules/{module['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["module_api_name"] == "partner_projects"

    response = client.put(f"/api/v1/customization/modules/{module['id']}", headers=headers, json={**module, "module_label": "Partner Delivery"})
    assert response.status_code == 200
    assert response.json()["module_label"] == "Partner Delivery"

