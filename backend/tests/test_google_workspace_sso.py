from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
import base64
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import jwt
from app.models.sso import SSOProvider, SSOSession
from app.services.sso_service import validate_google_identity
from tests.test_pms_workspaces import account, middleware_database


@pytest.fixture(scope="module")
def signing_key():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    def enc(number):
        return base64.urlsafe_b64encode(number.to_bytes((number.bit_length() + 7) // 8, 'big')).rstrip(b'=').decode()
    key = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return key, {"keys": [{"kty": "RSA", "kid": "audit", "use": "sig", "n": enc(numbers.n), "e": enc(numbers.e)}]}


@pytest.mark.parametrize("changed", [{}, {"email_verified": False}, {"hd": "another.example"}, {"nonce": "replayed"}, {"aud": "another-client"}, {"iss": "https://attacker.example"}, {"exp": 1}, {"azp": "another-client"}])
def test_google_signature_and_workspace_claims(signing_key, changed):
    key, jwks = signing_key
    claims = {"iss": "https://accounts.google.com", "aud": "our-client", "sub": "google-user", "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(minutes=5), "nonce": "our-nonce", "hd": "workspace.example", "email": "member@workspace.example", "email_verified": True}
    claims.update(changed)
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "audit"})
    provider = SSOProvider(client_id="our-client", domain_hint="workspace.example", provider_type="google")
    if not changed:
        assert validate_google_identity(token, jwks, provider, "our-nonce")["sub"] == "google-user"
    else:
        with pytest.raises((ValueError, jwt.PyJWTError)):
            validate_google_identity(token, jwks, provider, "our-nonce")


@pytest.mark.parametrize("mode", ["normal", "disabled", "mfa", "expired", "totp"])
def test_google_callback_creates_revocable_session_and_rejects_replay(client, db, monkeypatch, mode):
    from app.models.company import Company
    if not db.get(Company, 1):
        db.add(Company(id=1, name="SSO test company", is_active=True))
        db.flush()
    user, _ = account(db, "sso-member@workspace.example")
    if mode == "totp":
        monkeypatch.setattr("app.api.v1.auth._active_totp", lambda *args: object())
    user.is_active = mode != "disabled"
    provider = SSOProvider(name="Workspace", provider_type="google", client_id="our-client", client_secret="test-only", domain_hint="workspace.example", is_active=True, auto_provision=False)
    provider.force_mfa = mode == "mfa"
    db.add(provider); db.commit()
    session = SSOSession(provider_id=provider.id, state="audit-state", nonce="audit-nonce", code_verifier="verifier", relay_state="/pms/workspaces", expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
    db.add(session); db.commit()
    async def exchange(*args, **kwargs):
        assert kwargs["nonce"] == "audit-nonce"
        return {"email": user.email}
    monkeypatch.setattr("app.api.v1.sso.exchange_oidc_code", exchange)
    callback = f"/api/v1/auth/sso/callback/oidc/{provider.id}?state=audit-state&code=audit-code"
    denied = client.get(callback, follow_redirects=False)
    assert "invalid_state" in denied.headers["location"]
    client.cookies.set(f"sso_state_{provider.id}", "audit-state", path="/api/v1/auth/sso")
    response = client.get(callback, follow_redirects=False)
    if mode in {"disabled", "mfa", "totp"}:
        assert ("account_disabled" if mode == "disabled" else "mfa_required") in response.headers["location"]
        return
    assert "sso_code=" in response.headers["location"], response.headers
    assert "access_token" not in response.headers["location"]
    params = parse_qs(urlparse(response.headers["location"]).fragment)
    complete = f"/api/v1/auth/sso/complete/{provider.id}"
    code = params["sso_code"][0]
    if mode == "expired":
        db.refresh(session)
        session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        assert client.post(complete, json={"code": code}).status_code == 401
        return
    client.cookies.clear()
    assert client.post(complete, json={"code": code}).status_code == 401
    client.cookies.set(f"sso_state_{provider.id}", "audit-state", path="/api/v1/auth/sso")
    assert client.post(complete, json={"code": "wrong-handoff-code-123456"}).status_code == 401
    exchanged = client.post(complete, json={"code": code})
    assert exchanged.status_code == 200, exchanged.text
    token = exchanged.json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    client.cookies.set(f"sso_state_{provider.id}", "audit-state", path="/api/v1/auth/sso")
    assert client.post(complete, json={"code": code}).status_code == 401
    assert "invalid_state" in client.get(callback, follow_redirects=False).headers["location"]


def test_google_provider_requires_workspace_and_official_endpoints():
    from app.api.v1.sso import _validate_provider_config
    from fastapi import HTTPException
    config = {"provider_type": "google", "domain_hint": "workspace.example", "client_id": "client", "client_secret": "test-only"}
    _validate_provider_config(config)
    assert config["token_url"] == "https://oauth2.googleapis.com/token"
    with pytest.raises(HTTPException):
        _validate_provider_config({**config, "domain_hint": ""})
    with pytest.raises(HTTPException):
        _validate_provider_config({**config, "token_url": "https://attacker.example/token"})
