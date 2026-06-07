from app.core.security import get_password_hash
from app.models.user import Permission, Role, User


def automation_headers(client, db, email: str = "automation-admin@example.com", permissions: list[str] | None = None):
    role = Role(name=f"role-{email}", description="Automation test role", is_system=False)
    db.add(role)
    db.flush()
    effective_permissions = ["automation_view", "automation_manage", "automation_execute", "automation_logs_view", "automation_approval_view", "automation_approval_manage", "automation_approval_decide", "automation_webhook_manage"] if permissions is None else permissions
    for name in effective_permissions:
        permission = db.query(Permission).filter(Permission.name == name).first()
        if not permission:
            permission = Permission(name=name, description=name, module="automation")
            db.add(permission)
            db.flush()
        role.permissions.append(permission)
    user = User(email=email, hashed_password=get_password_hash("Password@123"), is_active=True, role_id=role.id)
    db.add(user)
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Password@123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_workflow(client, headers, name: str = "Quote discount approval"):
    response = client.post("/api/v1/automation/workflows", headers=headers, json={
        "name": name,
        "module_name": "crm",
        "record_type": "quote",
        "trigger_type": "quote_submitted",
        "conditions": [{"field": "discount_percent", "operator": "greater_or_equal", "value": 15}],
        "actions": [{"type": "send_notification", "title": "Approval needed", "message": "Discount review"}],
        "is_active": True,
    })
    assert response.status_code == 201, response.text
    return response.json()
