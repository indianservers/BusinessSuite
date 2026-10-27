"""Isolated connector foundation checks. No live provider credentials or calls."""

import json
import socket
from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from app.apps.power_apps.integrations import adapters, vault, service
from app.apps.power_apps.integrations.contracts import (
    HTTPInput,
    ConnectionCreate,
    IntegrationFailure,
)
from app.apps.power_apps.integrations.registry import REGISTRY, INPUTS, catalog, NATIVE
from app.apps.power_apps.integrations.transport import (
    EgressPolicy,
    HttpTransport,
    PinnedHTTPS,
    Response,
    encode_request,
    scrub,
)
from app.apps.power_apps.integrations.models import Operation, RequestLog, Credential
from app.models.user import User
from tests.test_power_runtime import db
from tests.test_power_apps import actors


def resolver(host, port, **kwargs):
    addresses = {
        "public.example": ["8.8.8.8"],
        "mixed.example": ["8.8.8.8", "10.0.0.1"],
        "private.example": ["10.0.0.5"],
        "alias.example": ["9.9.9.9"],
        "app.example": ["9.9.9.9"],
    }.get(host, ["127.0.0.1"])
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in addresses]


def test_manifest_contracts_and_truthful_candidates():
    assert len(REGISTRY) >= 40
    assert len(REGISTRY["ai_gateway"].actions) == 15
    for manifest in REGISTRY.values():
        assert manifest.availability == "Requires Configuration"
        assert manifest.live_verification == "Pending authorized credentials"
        for action in manifest.actions:
            assert (manifest.id, action.id) in INPUTS
    candidates = [x for x in catalog(True) if x["id"].startswith("candidate_")]
    assert all(
        x["availability"] == "In Development" and x["actions"] == [] for x in candidates
    )
    assert all(not contract["active"] for contract in NATIVE.values())


@pytest.mark.parametrize(
    "url",
    [
        "http://public.example",
        "https://public.example:8443",
        "https://localhost",
        "https://127.0.0.1",
        "https://169.254.169.254",
        "https://mixed.example",
        "https://public.example/#fragment",
        "https://user:password@public.example",
        "https://public.example/?api_key=secret",
        "https://public.example/\r\nHost:evil",
    ],
)
def test_egress_denies_unsafe_urls_and_mixed_dns(url):
    policy = EgressPolicy(
        [
            "public.example",
            "mixed.example",
            "localhost",
            "127.0.0.1",
            "169.254.169.254",
        ],
        resolver=resolver,
    )
    with pytest.raises(IntegrationFailure):
        policy.resolve(url)


def test_exact_private_grants_and_application_alias(monkeypatch):
    policy = EgressPolicy(
        ["private.example"], {("private.example", 443): ["10.0.0.5"]}, resolver=resolver
    )
    assert policy.resolve("https://private.example").address == "10.0.0.5"
    with pytest.raises(IntegrationFailure):
        EgressPolicy(["private.example"], resolver=resolver).resolve(
            "https://private.example"
        )
    from app.core.config import settings

    monkeypatch.setattr(settings, "BACKEND_PUBLIC_URL", "https://app.example")
    with pytest.raises(IntegrationFailure):
        EgressPolicy(["alias.example"], resolver=resolver).resolve(
            "https://alias.example"
        )


def test_socket_is_pinned_and_original_hostname_is_tls_sni(monkeypatch):
    target = EgressPolicy(["public.example"], resolver=resolver).resolve(
        "https://public.example"
    )
    calls = []

    class Raw:
        def close(self):
            pass

    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda address, timeout: (calls.append(address) or Raw()),
    )
    conn = PinnedHTTPS(target, 5)
    conn._context = NS(
        wrap_socket=lambda raw, server_hostname: (calls.append(server_hostname) or raw)
    )
    conn.connect()
    assert calls == [("8.8.8.8", 443), "public.example"]


@pytest.mark.parametrize(
    "method,uncertain,retryable", [("GET", False, True), ("POST", True, False)]
)
def test_post_dispatch_network_failure_classification(method, uncertain, retryable):
    class Broken:
        def __init__(self, *args):
            pass

        def connect(self):
            pass

        def request(self, *args, **kwargs):
            raise OSError("isolated failure")

        def close(self):
            pass

    with pytest.raises(IntegrationFailure) as failure:
        HttpTransport(
            EgressPolicy(["public.example"], resolver=resolver), Broken
        ).request(method, "https://public.example")
    assert failure.value.uncertain == uncertain and failure.value.retryable == retryable


def test_redirects_cannot_forward_credentials_to_another_origin():
    class Redirect:
        def __init__(self, *args):
            pass

        def connect(self):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return NS(
                status=302,
                read=lambda n: b"",
                getheaders=lambda: [("Location", "https://mixed.example")],
            )

        def close(self):
            pass

    with pytest.raises(IntegrationFailure):
        HttpTransport(
            EgressPolicy(["public.example", "mixed.example"], resolver=resolver),
            Redirect,
        ).request("GET", "https://public.example", redirects=1)


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "Bearer unsafe"},
        {"Host": "evil"},
        {"X-Test": "a\r\nb"},
        {"Content-Length": "1"},
    ],
)
def test_authentication_and_request_smuggling_headers_rejected(headers):
    with pytest.raises(IntegrationFailure):
        encode_request(HTTPInput(url="https://public.example", headers=headers))


def test_scrub_removes_secret_properties_and_exact_values():
    assert scrub(
        {
            "api_key": "private",
            "nested": {
                "authorization": "secret",
                "safe": "prefix isolated-value suffix",
            },
            "__proto__": {},
            "token": "never",
        },
        ["isolated-value"],
    ) == {"nested": {"safe": "prefix [REDACTED] suffix"}}


def test_mutation_pagination_is_rejected_before_transport():
    with pytest.raises(IntegrationFailure):
        adapters.http_action(
            NS(writes_enabled=True),
            HTTPInput(
                url="https://public.example",
                method="POST",
                max_pages=2,
                page_parameter="page",
            ),
            None,
            {},
            {},
            "isolated",
        )


def test_status_errors_obey_retry_after_and_uncertain_write_rules():
    with pytest.raises(IntegrationFailure) as failure:
        adapters.status_error(Response(429, {"retry-after": "17"}, b"", 1))
    assert failure.value.retry_after == 17 and failure.value.retryable
    with pytest.raises(IntegrationFailure) as failure:
        adapters.status_error(Response(503, {}, b"", 1), True)
    assert failure.value.uncertain and not failure.value.retryable


def setup_connection(db):
    user = db.query(User).filter_by(email="power-0@example.com").one()
    user.organization_id = 1
    data = ConnectionCreate(
        connector_id="http",
        name="Isolated fixture",
        auth_type="bearer",
        secrets={"access_token": "fixture-local-only-value"},
        config={"hosts": ["public.example"]},
        writes_enabled=True,
    )
    conn = vault.create(db, user, "development", data)
    db.commit()
    return user, conn


def test_encrypted_vault_write_opt_in_and_tenant_binding(db, actors):
    user, conn = setup_connection(db)
    credential = db.get(Credential, conn.credential_id)
    assert "fixture-local-only-value" not in credential.encrypted_value
    assert (
        vault.CredentialVault.decrypt(credential)["access_token"]
        == "fixture-local-only-value"
    )
    assert "encrypted_value" not in vault.public_connection(conn)
    foreign = db.query(User).filter_by(email="power-1@example.com").one()
    foreign.organization_id = 2
    with pytest.raises(HTTPException):
        vault.connection(db, foreign, "development", conn.id)
    with pytest.raises(IntegrationFailure):
        service.typed_action(
            conn, "request", {"url": "https://public.example", "method": "POST"}, False
        )


def test_operation_journal_reuses_success_and_blocks_uncertain_redelivery(
    db, actors, monkeypatch
):
    user, conn = setup_connection(db)
    calls = []

    class FixtureTransport:
        def __init__(self, policy):
            pass

        def request(self, method, url, *args, **kwargs):
            calls.append(method)
            assert db.query(Operation).filter_by(status="dispatched").count() >= 1
            if method == "POST":
                raise IntegrationFailure(
                    "network", "Fixture interrupted after dispatch", uncertain=True
                )
            return Response(
                200, {}, b'{"answer":42,"token":"fixture-local-only-value"}', 1
            )

    monkeypatch.setattr(adapters, "HTTP_FACTORY", FixtureTransport)
    result = service.invoke(
        db, user, conn, "request", {"url": "https://public.example"}, key="fixture-read"
    )
    assert result["body"] == {"answer": 42}
    assert (
        service.invoke(
            db,
            user,
            conn,
            "request",
            {"url": "https://public.example"},
            key="fixture-read",
        )
        == result
    )
    assert calls == ["GET"]
    for _ in range(2):
        with pytest.raises(IntegrationFailure) as failure:
            service.invoke(
                db,
                user,
                conn,
                "request",
                {"url": "https://public.example", "method": "POST"},
                confirmed=True,
                key="fixture-write",
            )
        assert failure.value.uncertain
    assert calls == ["GET", "POST"]
    assert db.query(RequestLog).count() == 2
    assert db.query(Operation).filter_by(status="uncertain").count() == 1


def test_oauth_exact_callback_and_encrypted_single_use_state(db, actors, monkeypatch):
    from urllib.parse import urlsplit, parse_qs
    from app.core.config import settings
    from app.apps.power_apps.integrations import oauth
    from app.apps.power_apps.integrations.models import OAuthState
    from app.apps.power_apps.runtime import now

    user = db.query(User).filter_by(email="power-0@example.com").one()
    user.organization_id = 1
    conn = vault.create(
        db,
        user,
        "development",
        ConnectionCreate(
            connector_id="google_sheets",
            name="OAuth fixture",
            auth_type="oauth2",
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        ),
    )
    db.commit()
    monkeypatch.setattr(settings, "POWER_GOOGLE_CLIENT_ID", "isolated-client")
    monkeypatch.setattr(
        settings, "POWER_GOOGLE_CLIENT_SECRET", "isolated-server-secret"
    )
    monkeypatch.setattr(
        settings,
        "POWER_OAUTH_REDIRECT_URI",
        settings.BACKEND_PUBLIC_URL.rstrip("/")
        + "/api/v1/power-apps/integrations/oauth/callback",
    )
    url = oauth.start(db, conn, user, list(conn.scopes))
    query = parse_qs(urlsplit(url).query)
    assert query["code_challenge_method"] == ["S256"]
    state = db.query(OAuthState).one()
    assert query["state"][0] not in state.state_hash
    assert "verifier" not in state.encrypted_verifier
    assert oauth.callback
    state.consumed_at = now()
    db.commit()
    with pytest.raises(HTTPException):
        oauth.callback(db, query["state"][0], "isolated-code")
    monkeypatch.setattr(
        settings, "POWER_OAUTH_REDIRECT_URI", "https://evil.example/callback"
    )
    with pytest.raises(HTTPException):
        oauth.app_config(conn.connector_id)


def test_oauth_refresh_rotates_and_rejects_concurrent_revocation(
    db, actors, monkeypatch
):
    from datetime import timedelta
    from app.apps.power_apps.integrations import oauth
    from app.apps.power_apps.runtime import now

    user = db.query(User).filter_by(email="power-0@example.com").one()
    user.organization_id = 1
    conn = vault.create(
        db,
        user,
        "development",
        ConnectionCreate(
            connector_id="google_sheets",
            name="Refresh fixture",
            auth_type="oauth2",
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        ),
    )
    credential = db.get(Credential, conn.credential_id)
    credential.encrypted_value = vault.CredentialVault.encrypt(
        {"access_token": "old-fixture-value", "refresh_token": "refresh-fixture-value"}
    )
    conn.expires_at = now() - timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr(
        oauth,
        "app_config",
        lambda id: {
            "token": "https://fixture.invalid/token",
            "client_id": "fixture",
            "secret": "fixture",
        },
    )
    requests = []

    def token_request(url, fields):
        requests.append(fields)
        return {
            "access_token": "new-fixture-value",
            "refresh_token": "rotated-fixture-value",
            "expires_in": 3600,
        }

    monkeypatch.setattr(oauth, "token_request", token_request)
    values = oauth.access_values(
        db, conn, credential, vault.CredentialVault.decrypt(credential)
    )
    assert values["refresh_token"] == "rotated-fixture-value"
    assert credential.version == 2 and len(requests) == 1
    conn.expires_at = now() - timedelta(seconds=1)
    db.commit()

    def revoked_request(url, fields):
        credential.version += 1
        credential.revoked_at = now()
        conn.enabled = False
        db.commit()
        return {"access_token": "must-not-save", "expires_in": 3600}

    monkeypatch.setattr(oauth, "token_request", revoked_request)
    with pytest.raises(IntegrationFailure):
        oauth.access_values(db, conn, credential, values)
    assert "must-not-save" not in str(vault.CredentialVault.decrypt(credential))
