"""Telegram uses the encrypted vault, governed dispatcher, and fixed API origin."""
import json
from urllib.parse import unquote
import pytest
from app.apps.power_apps.integrations import adapters, service, vault
from app.apps.power_apps.integrations.contracts import ConnectionCreate, IntegrationFailure
from app.apps.power_apps.integrations.models import Credential, Operation
from app.apps.power_apps.integrations.registry import INPUTS
from app.apps.power_apps.integrations.transport import Response
from app.apps.power_apps.node_registry import NODES
from app.models.user import User
from tests.test_power_runtime import db
from tests.test_power_apps import actors


def test_telegram_vault_verification_and_explicit_message_test(db, actors, monkeypatch):
    user = db.query(User).filter_by(email="power-0@example.com").one()
    user.organization_id = 1
    token = "123456789:fixture_telegram_credential_only"
    conn = vault.create(db, user, "development", ConnectionCreate(
        connector_id="telegram", name="Fixture bot", auth_type="bearer",
        secrets={"access_token": token}, writes_enabled=True,
    ))
    db.commit()
    assert token not in db.get(Credential, conn.credential_id).encrypted_value
    assert token not in json.dumps(vault.public_connection(conn), default=str)
    calls = []

    class Transport:
        def __init__(self, policy):
            assert policy.allowed_hosts == {"api.telegram.org"}

        def request(self, method, url, **kwargs):
            assert "Authorization" not in kwargs["headers"]
            calls.append((method, unquote(url), kwargs.get("body")))
            if method == "GET":
                assert unquote(url) == f"https://api.telegram.org/bot{token}/getMe"
                return Response(200, {}, b'{"ok":true,"result":{"id":123,"username":"fixture_bot","is_bot":true}}', 1)
            assert unquote(url) == f"https://api.telegram.org/bot{token}/sendMessage"
            assert json.loads(kwargs["body"]) == {"chat_id": "-1001234", "text": "Fixture test"}
            return Response(200, {}, b'{"ok":true,"result":{"message_id":42}}', 1)

    monkeypatch.setattr(adapters, "HTTP_FACTORY", Transport)
    result = service.invoke(db, user, conn, "test", {}, key="telegram-verify")
    assert result["data"]["result"]["username"] == "fixture_bot"
    assert calls[0][0] == "GET"
    payload = {"chat_id": "-1001234", "text": "Fixture test"}
    with pytest.raises(IntegrationFailure):
        service.invoke(db, user, conn, "send_message", payload, confirmed=False, key="telegram-unconfirmed")
    assert len(calls) == 1
    sent = service.invoke(db, user, conn, "send_message", payload, confirmed=True, key="telegram-send")
    assert sent["data"]["result"]["message_id"] == 42
    assert service.invoke(db, user, conn, "send_message", payload, confirmed=True, key="telegram-send") == sent
    assert len(calls) == 2
    for operation in db.query(Operation).all():
        assert token not in json.dumps(operation.output, default=str)


def test_telegram_module_defaults_and_message_limit():
    node = NODES["connector_telegram"]
    assert node["icon"] == "Send"
    assert node["fields"][0]["default"] == "send_message"
    assert node["requires_credential"] and node["executable"]
    with pytest.raises(ValueError):
        INPUTS["telegram", "send_message"].model_validate({"chat_id": "123", "text": "x" * 4097})
