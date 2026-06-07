from admin_security_test_utils import auth_headers, create_profile


def test_audit_log_viewer_and_export(client, db):
    headers = auth_headers(client, db)
    create_profile(client, headers, "Audit Profile")
    logs = client.get("/api/v1/admin/audit-logs", headers=headers)
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1
    export = client.get("/api/v1/admin/audit-logs/export", headers=headers)
    assert export.status_code == 200
    assert "event_type" in export.text
