from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import HTTPException

from app.apps.crm import google_calendar as google


@pytest.fixture
def credentials(monkeypatch):
    monkeypatch.setattr(google.settings, "CRM_GOOGLE_CALENDAR_CLIENT_ID", "test-client")
    monkeypatch.setattr(google.settings, "CRM_GOOGLE_CALENDAR_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(google.settings, "CRM_GOOGLE_CALENDAR_REDIRECT_URI", "http://localhost:5173/crm/calendar-integrations")


def test_authorization_uses_offline_access_and_pkce(credentials):
    query = parse_qs(urlparse(google.authorize(1, 2)["url"]).query)
    assert query["scope"] == [google.SCOPE]
    assert query["access_type"] == ["offline"]
    assert query["code_challenge_method"] == ["S256"]
    assert "verifier" not in query["state"][0]


def test_exchange_rejects_other_users_tenants_and_tampering(credentials):
    state = google.authorize(1, 2)["state"]
    for value, user, org in [(state, 3, 2), (state, 1, 3), ("tampered", 1, 2)]:
        with pytest.raises(HTTPException) as error:
            google.exchange("code", value, user, org)
        assert error.value.status_code in (400, 403)


def test_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(google.settings, "CRM_GOOGLE_CALENDAR_CLIENT_ID", "")
    with pytest.raises(HTTPException) as error:
        google.authorize(1, 2)
    assert error.value.status_code == 503


def test_exchange_and_scope_validation(credentials, monkeypatch):
    state = google.authorize(1, 2)["state"]
    def token(data):
        assert data["code_verifier"]
        assert data["code"] == "code"
        return {"access_token": "secret", "scope": google.SCOPE}
    monkeypatch.setattr(google, "token_request", token)
    assert google.exchange("code", state, 1, 2)["access_token"] == "secret"
    monkeypatch.setattr(google, "token_request", lambda data: {"access_token": "secret", "scope": "openid"})
    with pytest.raises(HTTPException):
        google.exchange("code", state, 1, 2)


def test_refresh_and_retry_update_same_event(credentials, monkeypatch):
    integration = SimpleNamespace(id=4, organization_id=2, refresh_token_encrypted=None)
    google.store_tokens(integration, {"access_token": "old", "refresh_token": "refresh"})
    assert "refresh" != integration.refresh_token_encrypted
    integration.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    refreshes = []
    def refresh(data):
        refreshes.append(data)
        return {"access_token": "renewed", "expires_in": 3600}
    monkeypatch.setattr(google, "token_request", refresh)
    requests = []
    def handler(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer renewed"
        if request.method == "POST":
            return httpx.Response(409)
        return httpx.Response(200, json={"id": request.url.path.split("/")[-1]})
    real_client = httpx.Client
    monkeypatch.setattr(google.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    meeting = SimpleNamespace(id=5, title="Review", description="Agenda", location=None,
                              start_time=datetime(2026, 10, 24, 10), end_time=datetime(2026, 10, 24, 11), status="Scheduled")
    first = google.sync_meeting(integration, meeting)
    second = google.sync_meeting(integration, meeting)
    assert first == second
    assert len(refreshes) == 1
    assert refreshes[0]["refresh_token"] == "refresh"
    assert [r.method for r in requests] == ["POST", "PATCH", "POST", "PATCH"]


def test_api_blocks_fake_google_connections(client, superuser_headers):
    response = client.post("/api/v1/crm/calendar-integrations/connect", headers=superuser_headers,
                           json={"provider": "google", "mock": True})
    assert response.status_code == 422


def test_callback_stores_encrypted_credentials_and_disconnect_clears_them(client, db, superuser_headers, monkeypatch):
    from app.apps.crm.models import CRMCalendarIntegration
    monkeypatch.setattr(google, "exchange", lambda *args: {
        "access_token": "sensitive-access", "refresh_token": "sensitive-refresh", "expires_in": 3600,
    })
    response = client.post("/api/v1/crm/calendar-integrations/google/callback", headers=superuser_headers,
                           json={"code": "single-use-code", "state": "verified-by-exchange"})
    assert response.status_code == 200, response.text
    assert response.json()["connected"] is True
    assert "sensitive" not in response.text
    row = db.get(CRMCalendarIntegration, response.json()["id"])
    assert google.cipher().decrypt(row.access_token_encrypted.encode()).decode() == "sensitive-access"
    assert row.refresh_token_encrypted != "sensitive-refresh"
    disconnected = client.delete(f"/api/v1/crm/calendar-integrations/{row.id}", headers=superuser_headers)
    assert disconnected.status_code == 200
    db.refresh(row)
    assert row.access_token_encrypted is None
    assert row.refresh_token_encrypted is None


def test_expired_state_rejected(credentials):
    import json
    state = google.cipher().encrypt_at_time(json.dumps({"user": 1, "organization": 2,
                                                       "verifier": "expired"}).encode(), 1).decode()
    with pytest.raises(HTTPException) as error:
        google.exchange("code", state, 1, 2)
    assert error.value.status_code == 400


def test_provider_error_does_not_expose_response_body(credentials, monkeypatch):
    monkeypatch.setattr(google.httpx, "post", lambda *args, **kwargs:
                        httpx.Response(400, json={"error_description": "sensitive details"}))
    with pytest.raises(HTTPException) as error:
        google.token_request({"grant_type": "refresh_token", "refresh_token": "secret"})
    assert "sensitive" not in error.value.detail
