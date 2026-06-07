from admin_security_test_utils import auth_headers


def test_compliance_backup_and_retention_settings(client, db):
    headers = auth_headers(client, db)
    compliance = client.post("/api/v1/admin/compliance", headers=headers, json={"setting_key": "consent_link", "setting_value_json": {"communication_module": True}})
    assert compliance.status_code == 201
    retention = client.post("/api/v1/admin/data-retention", headers=headers, json={"module_name": "leads", "retention_days": 365, "action": "archive"})
    assert retention.status_code == 201
    backup = client.post("/api/v1/admin/backups/request", headers=headers, json={"scope": "crm"})
    assert backup.status_code == 201
    assert backup.json()["detail_json"]["destructive"] is False
