from app.core.security import get_password_hash
from app.models.user import Role, User


def test_crm_quote_and_product_apis_require_backend_permissions(client, db):
    role = Role(name="employee", description="No CRM permissions", is_system=False)
    db.add(role)
    db.flush()
    user = User(email="crm-no-access@example.com", hashed_password=get_password_hash("Password@123"), is_active=True, role_id=role.id)
    db.add(user)
    db.commit()

    login = client.post("/api/v1/auth/login", json={"email": "crm-no-access@example.com", "password": "Password@123"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    blocked = client.post("/api/v1/crm/products", headers=headers, json={"name": "Blocked Product"})
    assert blocked.status_code == 403
    blocked_quote = client.post("/api/v1/crm/quotes", headers=headers, json={"quoteNumber": "QT-BLOCK", "issueDate": "2026-06-01", "expiryDate": "2026-06-30"})
    assert blocked_quote.status_code == 403
