import pyotp

from app.db.init_db import init_db
from app.models.user import MFAMethod, UserSession


def _login(client, email="admin@aihrms.com", password="Admin@123456"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


def _create_policy(client, headers, **overrides):
    payload = {
        "name": "Strict Enterprise",
        "min_length": 10,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_number": True,
        "require_special": True,
        "lockout_attempts": 3,
        "lockout_duration_minutes": 15,
        "mfa_required": False,
        "is_default": True,
        "is_active": True,
    }
    payload.update(overrides)
    response = client.post("/api/v1/auth/password-policies", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _create_user(client, headers, email="secure.user@example.com", password="Str0ng!Pass99"):
    response = client.post("/api/v1/auth/users", json={"email": email, "password": password}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_password_policy_is_enforced_during_user_creation(client, db):
    init_db(db)
    headers, _ = _login(client)
    _create_policy(client, headers)

    response = client.post(
        "/api/v1/auth/users",
        json={"email": "weak@example.com", "password": "weakpass"},
        headers=headers,
    )

    assert response.status_code == 400
    assert "Password" in response.json()["detail"]


def test_login_attempt_lockout_blocks_after_threshold(client, db):
    init_db(db)
    headers, _ = _login(client)
    _create_policy(client, headers, lockout_attempts=2, lockout_duration_minutes=30)
    _create_user(client, headers, email="lockout@example.com")

    for _ in range(2):
        failed = client.post("/api/v1/auth/login", json={"email": "lockout@example.com", "password": "Wrong!Pass1"})
        assert failed.status_code == 401

    locked = client.post("/api/v1/auth/login", json={"email": "lockout@example.com", "password": "Str0ng!Pass99"})
    assert locked.status_code == 423
    assert "Account locked" in locked.json()["detail"]


def test_mfa_required_login_trusted_device_and_recovery_code(client, db):
    init_db(db)
    headers, _ = _login(client)
    _create_policy(client, headers)
    _create_user(client, headers, email="mfa.user@example.com")
    user_headers, _ = _login(client, "mfa.user@example.com", "Str0ng!Pass99")

    setup = client.post("/api/v1/auth/mfa/setup", headers=user_headers)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    recovery_code = setup.json()["recovery_codes"][0]
    method_id = setup.json()["method_id"]

    stored = db.query(MFAMethod).filter(MFAMethod.id == method_id).first()
    assert stored.secret is None
    assert stored.secret_ref != secret
    assert recovery_code not in str(stored.recovery_codes_json)

    code = pyotp.TOTP(secret).now()
    confirmed = client.post("/api/v1/auth/mfa/confirm", json={"method_id": method_id, "code": code}, headers=user_headers)
    assert confirmed.status_code == 200, confirmed.text

    phase_one = client.post("/api/v1/auth/login", json={"email": "mfa.user@example.com", "password": "Str0ng!Pass99"})
    assert phase_one.status_code == 200
    assert phase_one.json()["mfa_required"] is True

    verified = client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": phase_one.json()["mfa_token"], "method": "totp", "code": pyotp.TOTP(secret).now(), "trust_device": True, "device_name": "Test laptop"},
    )
    assert verified.status_code == 200, verified.text
    trusted_device_token = verified.json()["trusted_device_token"]

    bypass = client.post(
        "/api/v1/auth/login",
        json={"email": "mfa.user@example.com", "password": "Str0ng!Pass99", "trusted_device_token": trusted_device_token},
    )
    assert bypass.status_code == 200
    assert bypass.json()["access_token"]

    recovery_login = client.post("/api/v1/auth/login", json={"email": "mfa.user@example.com", "password": "Str0ng!Pass99"})
    recovery = client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": recovery_login.json()["mfa_token"], "method": "recovery", "code": recovery_code},
    )
    assert recovery.status_code == 200, recovery.text

    reuse = client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": recovery_login.json()["mfa_token"], "method": "recovery", "code": recovery_code},
    )
    assert reuse.status_code == 401


def test_session_listing_and_revoke_current_session(client, db):
    init_db(db)
    headers, _ = _login(client)
    _create_policy(client, headers)
    _create_user(client, headers, email="session.user@example.com")
    user_headers, body = _login(client, "session.user@example.com", "Str0ng!Pass99")

    sessions = client.get("/api/v1/auth/sessions/me", headers=user_headers)
    assert sessions.status_code == 200
    session_id = sessions.json()[0]["id"]

    revoked = client.put(f"/api/v1/auth/sessions/me/{session_id}/revoke", headers=user_headers)
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    denied = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert denied.status_code == 401


def test_sso_provider_config_validation(client, db):
    init_db(db)
    headers, _ = _login(client)

    invalid = client.post(
        "/api/v1/auth/sso/providers",
        json={"name": "Bad OIDC", "provider_type": "custom_oidc", "client_id": "abc", "domain_hint": "example.com"},
        headers=headers,
    )
    assert invalid.status_code == 400

    valid = client.post(
        "/api/v1/auth/sso/providers",
        json={
            "name": "Enterprise OIDC",
            "provider_type": "custom_oidc",
            "domain_hint": "example.com",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "authorization_url": "https://idp.example.com/auth",
            "token_url": "https://idp.example.com/token",
            "userinfo_url": "https://idp.example.com/userinfo",
            "scope": "openid email profile",
            "is_active": True,
            "is_default": True,
        },
        headers=headers,
    )
    assert valid.status_code == 201, valid.text
    assert valid.json()["client_secret"] == "***"


def test_ip_policy_blocklist_denies_login(client, db):
    init_db(db)
    headers, _ = _login(client)
    response = client.post(
        "/api/v1/auth/ip-policies",
        json={"cidr": "203.0.113.10/32", "action": "block", "description": "Block suspicious office IP"},
        headers=headers,
    )
    assert response.status_code == 201
    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@aihrms.com", "password": "Admin@123456"},
        headers={"X-Forwarded-For": "203.0.113.10"},
    )
    assert blocked.status_code == 403
    assert "blocked" in blocked.json()["detail"].lower()
