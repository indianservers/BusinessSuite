from app.core.security import get_password_hash
from app.models.user import Permission, Role, User


AI_PERMISSIONS = [
    "ai_view",
    "ai_use",
    "ai_manage_settings",
    "ai_manage_prompts",
    "ai_agent_actions",
    "ai_action_log_view",
    "crm_view",
    "crm_manage",
    "srm_view",
    "srm_collection_view",
    "srm_collection_create",
    "analytics_view",
    "automation_manage",
]


def auth_headers(client, db, email: str = "ai-admin@example.com", permissions: list[str] | None = None, role_name: str | None = None):
    role = Role(name=role_name or f"role-{email}", description="AI test role", is_system=False)
    db.add(role)
    db.flush()
    for name in (AI_PERMISSIONS if permissions is None else permissions):
        permission = db.query(Permission).filter(Permission.name == name).first()
        if not permission:
            permission = Permission(name=name, description=name, module=name.split("_", 1)[0])
            db.add(permission)
            db.flush()
        role.permissions.append(permission)
    user = User(email=email, hashed_password=get_password_hash("Password@123"), is_active=True, role_id=role.id)
    db.add(user)
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Password@123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, user


def create_mock_provider(client, headers):
    response = client.post(
        "/api/v1/ai/provider-settings",
        headers=headers,
        json={
            "provider_name": "mock",
            "model_name": "mock-business-suite",
            "enabled": True,
            "masked_api_key_reference": "mock-test-only",
            "data_sharing_allowed": True,
            "max_tokens": 1200,
            "temperature": 0.2,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()

