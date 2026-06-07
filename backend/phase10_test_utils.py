from app.core.security import get_password_hash
from app.models.user import Permission, Role, User


def auth_headers(client, db, email="phase10-admin@example.com", role_name="crm_super_admin", permissions=None, superuser=False):
    permissions = permissions or [
        "portal_manage",
        "developer_view",
        "developer_manage",
        "marketplace_view",
        "marketplace_manage",
        "sandbox_view",
        "sandbox_manage",
        "tenant_view",
        "tenant_admin",
        "crm_view",
        "crm_manage",
    ]
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description="Phase 10 test role", is_system=True)
        db.add(role)
        db.flush()
    role.permissions = []
    for name in permissions:
        perm = db.query(Permission).filter(Permission.name == name).first()
        if not perm:
            perm = Permission(name=name, description=name, module="phase10")
            db.add(perm)
            db.flush()
        role.permissions.append(perm)
    user = User(email=email, hashed_password=get_password_hash("Admin@123456"), is_active=True, is_superuser=superuser, role_id=role.id)
    db.add(user)
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Admin@123456"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def invite_portal(client, headers, portal_type="customer", email="customer@example.com", customer_id=100, partner_id=200):
    payload = {"email": email, "display_name": email.split("@")[0], "portal_type": portal_type}
    if portal_type == "customer":
        payload["customer_id"] = customer_id
    if portal_type == "partner":
        payload["partner_id"] = partner_id
    response = client.post("/api/v1/portals/invite", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()
