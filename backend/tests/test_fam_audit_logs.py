from app.apps.fam.models import FAMAuditLog
from tests.fam_test_utils import fam_admin_headers


def test_fam_audit_logs_capture_foundation_mutation(client, db):
    headers = fam_admin_headers(client, db)
    response = client.post("/api/v1/fam/cost-centers", headers=headers, json={"code": "OPS", "name": "Operations"})
    assert response.status_code == 201, response.text

    response = client.get("/api/v1/fam/audit-logs", headers=headers)
    assert response.status_code == 200
    assert any(item["record_type"] == "cost_center" and item["action"] == "CREATE" for item in response.json()["items"])
    assert db.query(FAMAuditLog).filter_by(record_type="cost_center", action="CREATE").first()
