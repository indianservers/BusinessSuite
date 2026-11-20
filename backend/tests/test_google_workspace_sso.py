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


@pytest.mark.asyncio
async def test_oidc_exchange_uses_bounded_pinned_transport(monkeypatch):
    from app.apps.power_apps.integrations.transport import Response
    from app.services import sso_service

    requests = []

    class Transport:
        def __init__(self, policy):
            self.policy = policy

        def request(self, method, url, headers, body, **options):
            assert self.policy.allowed_hosts == {"identity.example.test"}
            assert options["return_redirect"] is False
            assert options["max_response_bytes"] == 256 * 1024
            requests.append((method, url, headers, body))
            response = b'{"access_token":"fixture-token"}' if method == "POST" else b'{"email":"person@example.test"}'
            return Response(200, {}, response, 1)

    monkeypatch.setattr(sso_service, "HttpTransport", Transport)
    provider = SSOProvider(provider_type="custom_oidc", client_id="fixture-client", client_secret="fixture-secret",
                           token_url="https://identity.example.test/token", userinfo_url="https://identity.example.test/me")
    result = await sso_service.exchange_oidc_code(provider, "fixture-code", "state", "fixture-verifier")
    assert result == {"email": "person@example.test"}
    assert requests[0][0] == "POST"
    assert requests[0][2]["Content-Type"] == "application/x-www-form-urlencoded"
    assert parse_qs(requests[0][3].decode())["code"] == ["fixture-code"]
    assert requests[1][0] == "GET"
    assert requests[1][2] == {"Authorization": "Bearer fixture-token"}


@pytest.mark.parametrize("claims", [
    {"email": "member@example.test"},
    {"email": "member@example.test", "email_verified": False},
    {"email": "member@example.test", "email_verified": "true"},
    {"preferred_username": "member@example.test", "email_verified": True},
])
def test_custom_oidc_requires_verified_standard_email(claims):
    from app.services.sso_service import extract_user_attributes

    provider = SSOProvider(provider_type="custom_oidc", attr_email="preferred_username")
    with pytest.raises(ValueError):
        extract_user_attributes(claims, provider)


def test_custom_oidc_allows_verified_claim_with_matching_legacy_mapping():
    from app.services.sso_service import extract_user_attributes

    provider = SSOProvider(provider_type="custom_oidc", attr_email="preferred_username")
    claims = {"email": "member@example.test", "email_verified": True, "preferred_username": "member@example.test"}
    assert extract_user_attributes(claims, provider)["email"] == "member@example.test"
