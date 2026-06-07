from app.core.security import get_password_hash
from app.models.user import Permission, Role, User


ALL_CUSTOMIZATION_PERMISSIONS = [
    "customization_view",
    "customization_manage",
    "customization_modules_manage",
    "customization_fields_manage",
    "customization_layouts_manage",
    "customization_views_manage",
    "customization_validation_manage",
    "customization_buttons_manage",
]


def customization_headers(client, db, email: str = "customization-admin@example.com", permissions: list[str] | None = None):
    role = Role(name=f"role-{email}", description="Customization test role", is_system=False)
    db.add(role)
    db.flush()
    for name in (ALL_CUSTOMIZATION_PERMISSIONS if permissions is None else permissions):
        permission = db.query(Permission).filter(Permission.name == name).first()
        if not permission:
            permission = Permission(name=name, description=name, module="customization")
            db.add(permission)
            db.flush()
        role.permissions.append(permission)
    user = User(email=email, hashed_password=get_password_hash("Password@123"), is_active=True, role_id=role.id)
    db.add(user)
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Password@123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_module(client, headers, module_api_name: str = "partner_projects"):
    response = client.post("/api/v1/customization/modules", headers=headers, json={
        "module_api_name": module_api_name,
        "module_label": "Partner Project",
        "plural_label": "Partner Projects",
        "icon": "database",
        "description": "Partner delivery records",
        "enabled": True,
    })
    assert response.status_code == 201, response.text
    return response.json()


def create_text_field(client, headers, module_name: str = "partner_projects", field_api_name: str = "project_name", required: bool = True, unique: bool = False):
    response = client.post("/api/v1/customization/fields", headers=headers, json={
        "module_name": module_name,
        "field_api_name": field_api_name,
        "field_label": "Project Name",
        "field_type": "text",
        "required": required,
        "unique": unique,
        "visible": True,
        "editable": True,
    })
    assert response.status_code == 201, response.text
    return response.json()

