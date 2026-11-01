from admin_security_test_utils import auth_headers
from app.models.user import MFAMethod, User


def test_mfa_method_listing_requires_superuser_and_redacts_secrets(client, db):
    admin = auth_headers(client, db, email="methods-admin@example.com", role_name="super_admin", superuser=True)
    member = auth_headers(client, db, email="methods-member@example.com", role_name="employee", permissions=[])
    actor = db.query(User).filter_by(email="methods-member@example.com").one()
    db.add(MFAMethod(user_id=actor.id, method_type="TOTP", secret="fixture-secret", secret_ref="fixture-ref", recovery_codes_json=["fixture-recovery"]))
    db.commit()
    response = client.get("/api/v1/auth/mfa-methods", headers=admin, params={"user_id": actor.id})
    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert response.json()[0]["user_id"] == actor.id
    assert all(key not in response.json()[0] for key in ("secret", "secret_ref", "recovery_codes_json"))
    assert client.get("/api/v1/auth/mfa-methods", headers=member).status_code == 403
    assert client.get("/api/v1/auth/mfa-methods", headers=admin, params={"limit": 301}).status_code == 422
