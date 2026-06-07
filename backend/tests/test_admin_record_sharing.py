from app.apps.admin_security.models import AdminManualRecordShare
from admin_security_test_utils import auth_headers


def test_record_sharing_rule_and_manual_share_unshare(client, db):
    headers = auth_headers(client, db)
    rule = client.post("/api/v1/admin/record-sharing-rules", headers=headers, json={"module_name": "leads", "rule_name": "Team share", "condition_json": {"source": "Partner"}, "share_with_type": "role", "share_with_id": 1, "access_level": "read"})
    assert rule.status_code == 201
    share = client.post("/api/v1/admin/records/share", headers=headers, json={"module_name": "leads", "record_id": 10, "share_with_type": "user", "share_with_id": 2, "access_level": "edit"})
    assert share.status_code == 201
    assert db.query(AdminManualRecordShare).first().active is True
    unshare = client.post("/api/v1/admin/records/unshare", headers=headers, json={"module_name": "leads", "record_id": 10, "share_with_type": "user", "share_with_id": 2, "access_level": "edit"})
    assert unshare.status_code == 200
    assert db.query(AdminManualRecordShare).first().active is False
