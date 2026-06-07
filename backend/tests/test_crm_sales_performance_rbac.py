from app.core.security import get_password_hash
from app.models.user import Permission, Role, User


def _headers_for_permissions(client, db, email: str, permissions: list[str]):
    role = Role(name=f"role_{email}", description=email, is_system=False)
    db.add(role)
    db.flush()
    for name in permissions:
        permission = db.query(Permission).filter(Permission.name == name).first()
        if not permission:
            permission = Permission(name=name, module="crm", description=name)
            db.add(permission)
            db.flush()
        role.permissions.append(permission)
    user = User(email=email, hashed_password=get_password_hash("Sales@123456"), is_active=True, role_id=role.id)
    db.add(user)
    db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Sales@123456"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_crm_phase_2_sales_performance_backend_rbac(client, db):
    allowed = _headers_for_permissions(client, db, "sales-performance@example.com", ["crm_sales_performance_view"])
    assert client.get("/api/v1/crm/sales-performance", headers=allowed).status_code == 200

    blocked = _headers_for_permissions(client, db, "no-crm-phase2@example.com", [])
    assert client.get("/api/v1/crm/sales-performance", headers=blocked).status_code == 403
