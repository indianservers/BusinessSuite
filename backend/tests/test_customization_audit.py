from app.apps.customization.models import CustomizationAuditLog
from tests.customization_test_utils import customization_headers, create_module


def test_customization_audit_log_api(client, db):
    headers = customization_headers(client, db)
    create_module(client, headers)
    response = client.get("/api/v1/customization/audit-logs", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1
    assert db.query(CustomizationAuditLog).count() >= 1

