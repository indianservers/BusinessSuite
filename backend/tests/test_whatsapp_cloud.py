import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.v1.whatsapp_cloud import router, apply_statuses
from app.core.config import settings
from app.core.deps import get_db
from app.services.whatsapp import MetaWhatsAppProvider, WhatsAppGraph, MetaError


@pytest.mark.parametrize('path,budget,operation', [
    ('oauth/access_token', 45, 'authorization exchange'),
    ('debug_token', 20, 'token verification'),
    ('12345/phone_numbers', 20, 'sender verification'),
    ('12345/subscribed_apps', 20, 'webhook subscription'),
])
def test_transport_timeout_identifies_step_without_replaying_or_exposing_secrets(monkeypatch, path, budget, operation):
    calls = []
    def unavailable(url, **kwargs):
        calls.append(kwargs)
        raise httpx.ReadTimeout('provider exception with private values')
    monkeypatch.setattr(httpx, 'get', unavailable)
    with pytest.raises(MetaError) as error:
        WhatsAppGraph('private-token').request('GET', path, params={'code': 'private-code'})
    assert len(calls) == 1 and calls[0]['timeout'] == budget
    assert error.value.uncertain and operation in str(error.value)
    assert 'private' not in str(error.value)


@pytest.fixture
def configured(monkeypatch):
    for key, value in {
        "ACCESS_TOKEN": "test-token", "PHONE_NUMBER_ID": "12345",
        "BUSINESS_ACCOUNT_ID": "67890", "APP_SECRET": "test-secret",
        "VERIFY_TOKEN": "verify-me", "ORGANIZATION_ID": 42,
    }.items():
        monkeypatch.setattr(settings, "CRM_WHATSAPP_" + key, value)
    db = Mock()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app), db


def test_verification_is_plain_challenge_and_checks_token(configured):
    client, _ = configured
    response = client.get("/integrations/whatsapp/webhook", params={"hub.mode":"subscribe", "hub.verify_token":"verify-me", "hub.challenge":"1234"})
    assert response.status_code == 200 and response.text == "1234"
    assert client.get("/integrations/whatsapp/webhook", params={"hub.mode":"subscribe", "hub.verify_token":"bad"}).status_code == 403


def test_unsigned_webhook_rejected(configured):
    client, db = configured
    assert client.post("/integrations/whatsapp/webhook", json={}).status_code == 403
    db.commit.assert_not_called()


def test_signature_covers_exact_original_bytes(configured):
    client, db = configured
    body = b'{"object":"whatsapp_business_account"}'
    signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    response = client.post("/integrations/whatsapp/webhook", content=body + b' ', headers={"x-hub-signature-256":signature})
    assert response.status_code == 403
    db.commit.assert_not_called()


def test_signed_webhook_accepted(configured):
    client, db = configured
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    assert client.post("/integrations/whatsapp/webhook", content=body, headers={"x-hub-signature-256":signature}).status_code == 200
    db.commit.assert_called_once()


def test_status_does_not_regress_or_cross_sender(configured):
    _, db = configured
    row = SimpleNamespace(status="read", failure_reason=None)
    db.query.return_value.filter.return_value.with_for_update.return_value.all.return_value = [row]
    payload = {"object":"whatsapp_business_account","entry":[{"id":"67890","changes":[{"value":{"metadata":{"phone_number_id":"12345"},"statuses":[{"id":"wamid.1","status":"sent"}]}}]}]}
    assert apply_statuses(db, payload) == 1
    assert row.status == "read"
    payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "other"
    assert apply_statuses(db, payload) == 0


def test_transport_sends_template_and_returns_acceptance(configured, monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json={"messages":[{"id":"wamid.1"}]})
    monkeypatch.setattr("app.services.whatsapp.httpx.post", post)
    template = {"name":"hello_world","language":{"code":"en_US"}}
    assert MetaWhatsAppProvider().send(to="+91 9876543210", template=template) == ("accepted", "wamid.1")
    assert calls[0][1]["json"]["to"] == "919876543210"
    assert calls[0][1]["json"]["template"] == template
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-token"


def test_error_does_not_expose_provider_response(configured, monkeypatch):
    monkeypatch.setattr("app.services.whatsapp.httpx.post", lambda *a, **k: httpx.Response(400,json={"error":{"code":190,"message":"test-token secret"}}))
    with pytest.raises(RuntimeError) as error:
        MetaWhatsAppProvider().send(to="919876543210", body="hello")
    assert "190" in str(error.value) and "test-token" not in str(error.value)


def test_invalid_destination_never_calls_meta(configured, monkeypatch):
    post = Mock()
    monkeypatch.setattr("app.services.whatsapp.httpx.post", post)
    with pytest.raises(RuntimeError):
        MetaWhatsAppProvider().send(to="not a number", body="hello")
    post.assert_not_called()
