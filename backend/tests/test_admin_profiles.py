from app.apps.admin_security.models import AdminAuditLog, AdminProfilePermission
from admin_security_test_utils import auth_headers, create_profile


def test_admin_profiles_crud_permissions_and_audit(client, db):
    headers = auth_headers(client, db)
    profile = create_profile(client, headers, "Sales Profile")
    assert profile["active"] is True
    perms = client.post(f"/api/v1/admin/profiles/{profile['id']}/permissions", headers=headers, json={"permissions": ["crm_view", "crm_manage"]})
    assert perms.status_code == 201
    assert db.query(AdminProfilePermission).count() == 2
    update = client.put(f"/api/v1/admin/profiles/{profile['id']}", headers=headers, json={"name": "Sales Profile", "description": "Updated", "active": True})
    assert update.status_code == 200
    delete = client.delete(f"/api/v1/admin/profiles/{profile['id']}", headers=headers)
    assert delete.status_code == 204
    assert db.query(AdminAuditLog).filter(AdminAuditLog.event_type == "admin_profile_created").count() == 1
