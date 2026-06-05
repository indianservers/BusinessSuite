from app.core.security import get_password_hash
from app.models.user import Permission, Role, User


def auth_headers_for(client, db, email: str, role_name: str, password: str = "Password@123", permissions: list[str] | None = None):
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=role_name, is_system=True)
        db.add(role)
        db.flush()
    if permissions is not None:
        role.permissions = []
        for name in permissions:
            permission = db.query(Permission).filter(Permission.name == name).first()
            if not permission:
                permission = Permission(name=name, description=name, module="srm")
                db.add(permission)
                db.flush()
            role.permissions.append(permission)
    user = User(email=email, hashed_password=get_password_hash(password), is_active=True, is_superuser=False, role_id=role.id)
    db.add(user)
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password, "module": "srm"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_sales_order(client, headers, title: str = "Enterprise onboarding"):
    response = client.post("/api/v1/srm/sales-orders", headers=headers, json={
        "title": title,
        "customer_id": 101,
        "currency": "INR",
        "lines": [
            {
                "description": title,
                "quantity": 1,
                "unit_price": 125000,
                "tax_amount": 22500,
                "line_total": 147500,
            }
        ],
    })
    assert response.status_code == 201, response.text
    return response.json()


def create_engagement_via_confirm(client, headers):
    order = create_sales_order(client, headers)
    response = client.post(f"/api/v1/srm/sales-orders/{order['id']}/submit", headers=headers)
    assert response.status_code == 200, response.text
    response = client.post(f"/api/v1/srm/sales-orders/{order['id']}/confirm", headers=headers)
    if response.status_code == 400:
        client.post(f"/api/v1/srm/sales-orders/{order['id']}/approve", headers=headers)
        response = client.post(f"/api/v1/srm/sales-orders/{order['id']}/confirm", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["engagement"], order
