from app.core.security import get_password_hash
from app.models.user import Permission, Role, User


ALL_COMMUNICATION_PERMISSIONS = [
    "communication_view",
    "communication_email_send",
    "communication_templates_manage",
    "communication_webforms_manage",
    "communication_campaigns_view",
    "communication_campaigns_manage",
    "communication_campaigns_send",
    "communication_consents_manage",
    "communication_logs_view",
]


def communication_headers(client, db, email: str = "communication-admin@example.com", permissions: list[str] | None = None):
    role = Role(name=f"role-{email}", description="Communication test role", is_system=False)
    db.add(role)
    db.flush()
    for name in (ALL_COMMUNICATION_PERMISSIONS if permissions is None else permissions):
        permission = db.query(Permission).filter(Permission.name == name).first()
        if not permission:
            permission = Permission(name=name, description=name, module="communication")
            db.add(permission)
            db.flush()
        role.permissions.append(permission)
    user = User(email=email, hashed_password=get_password_hash("Password@123"), is_active=True, role_id=role.id)
    db.add(user)
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Password@123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_template(client, headers):
    response = client.post(
        "/api/v1/communication/email-templates",
        headers=headers,
        json={"name": "Welcome", "subject": "Hello {{name}}", "body_text": "Hi {{name}}", "module_name": "lead", "active": True},
    )
    assert response.status_code == 201, response.text
    return response.json()

