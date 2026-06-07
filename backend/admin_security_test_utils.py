from app.core.security import get_password_hash
from app.models.user import Permission, Role, User


ADMIN_PERMISSIONS = [
    "admin_security_view",
    "admin_security_manage",
    "admin_profiles_manage",
    "admin_roles_manage",
    "admin_field_security_manage",
    "admin_record_sharing_manage",
    "admin_import_manage",
    "admin_duplicates_manage",
    "admin_audit_view",
    "admin_export_control_manage",
    "admin_compliance_manage",
    "crm_view",
    "crm_manage",
]


def auth_headers(client, db, email="phase8-admin@example.com", role_name="crm_super_admin", permissions=None, superuser=False):
    role = Role(name=role_name, description="Phase 8 role", is_system=True)
    db.add(role)
    db.flush()
    role.permissions = []
    for name in (permissions if permissions is not None else ADMIN_PERMISSIONS):
        perm = db.query(Permission).filter(Permission.name == name).first()
        if not perm:
            perm = Permission(name=name, description=name, module="admin_security")
            db.add(perm)
            db.flush()
        role.permissions.append(perm)
    user = User(email=email, hashed_password=get_password_hash("Admin@123456"), is_active=True, is_superuser=superuser, role_id=role.id)
    db.add(user)
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Admin@123456"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_profile(client, headers, name="crm_sales_executive"):
    response = client.post("/api/v1/admin/profiles", headers=headers, json={"name": name, "description": "Test profile"})
    assert response.status_code == 201, response.text
    return response.json()
