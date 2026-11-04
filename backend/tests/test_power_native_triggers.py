"""Provider-authenticated native setup, inbox, renewal and cleanup regressions."""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest
from app.core.config import settings
from app.apps.power_apps.integrations import (
    adapters,
    native_runtime as native,
    native_subscriptions as subscriptions,
    native_events,
    native_sources,
)
from app.apps.power_apps.integrations.models import NativeDelivery
from app.apps.power_apps.integrations.transport import Response, EgressPolicy
from app.apps.power_apps.integrations.contracts import IntegrationFailure
from app.apps.power_apps.runtime import now
from app.apps.power_apps.runtime_models import AutomationTrigger as Trigger
from app.apps.power_apps.models import PowerExecution
from tests.test_power_runtime import db, actors, publish, definition, ROOT, drain
from tests.test_power_automation_catalog import connect


@pytest.fixture
def https_backend(monkeypatch):
    monkeypatch.setattr(settings, "BACKEND_PUBLIC_URL", "https://native.example.test")


def enable(client, headers, mid, setup, secrets=None):
    row = publish(
        client,
        headers,
        definition("integration_trigger_" + mid, setup=setup),
        policy={"identity": "owner", "delegated_owner": True},
    )
    response = client.put(
        f"{ROOT}/{row['id']}/triggers/connector",
        headers=headers,
        json={"enabled": True, "config": {}, "provider_secrets": secrets or {}},
    )
    assert response.status_code == 200, response.text
    return row, response.json()


def test_github_native_setup_verified_inbox_dedup_and_cleanup(
    client, db, actors, monkeypatch, https_backend
):
    calls = []
    hooks = []

    class Transport:
        def __init__(self, policy):
            assert policy.allowed_hosts == {"api.github.com"}

        def request(self, method, url, **kw):
            calls.append((method, url, kw))
            if method == "GET":
                value = hooks
            elif method == "POST":
                payload = json.loads(kw["body"])
                assert payload["events"] == ["issues"] and payload["config"][
                    "url"
                ].startswith(
                    "https://native.example.test/api/v1/power-apps/native-hooks/"
                )
                hooks.append({"id": 77, "config": payload["config"]})
                value = hooks[-1]
            else:
                assert method == "DELETE" and url.endswith("/hooks/77")
                value = {}
                hooks.clear()
            return Response(200, {}, json.dumps(value).encode(), 1)

    monkeypatch.setattr(adapters, "HTTP_FACTORY", Transport)
    conn = connect(client, actors[0], "github")
    row, result = enable(
        client,
        actors[0],
        "github",
        {
            "connection_id": conn,
            "event": "issue_opened",
            "owner": "owner",
            "repository": "repo",
        },
    )
    trigger = db.get(Trigger, result["id"])
    assert result["secret"] is None
    native.tick(db)
    assert trigger.config["native"]["phase"] == "active", trigger.config
    assert sum(method == "POST" for method, _, _ in calls) == 1
    private = native.read_private(trigger)
    body = json.dumps(
        {
            "action": "opened",
            "issue": {"id": 8, "number": 2},
            "repository": {"name": "repo", "owner": {"login": "owner"}},
        }
    ).encode()
    signature = (
        "sha256="
        + hmac.new(
            private["secrets"]["verification"].encode(), body, hashlib.sha256
        ).hexdigest()
    )
    url = "/api/v1/power-apps/native-hooks/" + trigger.endpoint
    assert (
        client.post(
            url, content=body, headers={"X-Hub-Signature-256": "invalid"}
        ).status_code
        == 401
    )
    for delivery in ("first-delivery", "altered-unsigned-delivery-header"):
        response = client.post(
            url,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
                "X-GitHub-Delivery": delivery,
                "X-GitHub-Event": "issues",
            },
        )
        assert response.status_code == 200, response.text
    assert db.query(NativeDelivery).count() == 1
    native.tick(db)
    drain(db)
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 1
    assert db.query(NativeDelivery).one().encrypted_payload is None
    listing = client.get(f"{ROOT}/{row['id']}/triggers", headers=actors[0]).text
    assert private["secrets"]["verification"] not in listing
    response = client.put(
        f"{ROOT}/{row['id']}/triggers/connector",
        headers=actors[0],
        json={"enabled": False, "config": {}},
    )
    assert response.status_code == 200, response.text
    native.tick(db)
    assert trigger.config["native"]["phase"] == "disabled" and hooks == []


def test_disable_during_registration_preserves_owned_hook_for_cleanup(
    client, db, actors, monkeypatch, https_backend
):
    hooks = []
    resource = []

    class Transport:
        def __init__(self, policy):
            pass

        def request(self, method, url, **kw):
            if method == "GET":
                value = hooks
            elif method == "POST":
                body = json.loads(kw["body"])
                hooks.append({"id": 3, "config": body["config"]})
                disabled = client.put(
                    f"{ROOT}/{resource[0]}/triggers/connector",
                    headers=actors[0],
                    json={"enabled": False, "config": {}},
                )
                assert disabled.status_code == 200, disabled.text
                value = hooks[-1]
            else:
                hooks.clear()
                value = {}
            return Response(200, {}, json.dumps(value).encode(), 1)

    monkeypatch.setattr(adapters, "HTTP_FACTORY", Transport)
    conn = connect(client, actors[0], "github")
    row, result = enable(
        client,
        actors[0],
        "github",
        {
            "connection_id": conn,
            "event": "push",
            "owner": "owner",
            "repository": "repo",
        },
    )
    resource.append(row["id"])
    native.tick(db)
    trigger = db.get(Trigger, result["id"])
    assert not trigger.enabled and native.read_private(trigger)["state"]["id"] == "3"
    native.tick(db)
    assert hooks == [] and trigger.config["native"]["phase"] == "disabled"
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 0


def test_graph_challenge_pending_registration_and_invalid_client_state(
    client, db, actors, monkeypatch, https_backend
):
    subs = []

    class Transport:
        def __init__(self, policy):
            pass

        def request(self, method, url, **kw):
            if method == "GET":
                value = {"value": subs}
            else:
                body = json.loads(kw["body"])
                challenge = client.post(
                    body["notificationUrl"] + "?validationToken=provider%2Bchallenge"
                )
                assert (
                    challenge.status_code == 200
                    and challenge.text == "provider+challenge"
                )
                value = {**body, "id": "subscription"}
                subs.append(value)
            return Response(200, {}, json.dumps(value).encode(), 1)

    monkeypatch.setattr(adapters, "HTTP_FACTORY", Transport)
    conn = connect(client, actors[0], "outlook", ["Mail.Read"])
    row, result = enable(
        client,
        actors[0],
        "outlook",
        {"connection_id": conn, "event": "email_received", "folder_id": "inbox"},
    )
    native.tick(db)
    trigger = db.get(Trigger, result["id"])
    assert trigger.config["native"]["phase"] == "active", trigger.config
    callback = "/api/v1/power-apps/native-hooks/" + trigger.endpoint
    value = {
        "value": [
            {
                "subscriptionId": "subscription",
                "clientState": "wrong",
                "changeType": "created",
                "resourceData": {"id": "message"},
            }
        ]
    }
    assert client.post(callback, json=value).status_code == 401
    assert db.query(NativeDelivery).count() == 0


def test_dropbox_uses_native_cursor_without_webhook_or_relay(
    client, db, actors, monkeypatch
):
    changed = False

    class Transport:
        def __init__(self, policy):
            pass

        def request(self, method, url, **kw):
            assert method == "POST" and "api.dropboxapi.com/2/files/list_folder" in url
            rows = [
                {"id": "id:file", ".tag": "file", "path_lower": "/a.txt", "rev": "1"}
            ]
            if url.endswith("continue"):
                rows = [{**rows[0], "rev": "2"}] if changed else []
            return Response(
                200,
                {},
                json.dumps(
                    {"entries": rows, "cursor": "cursor", "has_more": False}
                ).encode(),
                1,
            )

    monkeypatch.setattr(adapters, "HTTP_FACTORY", Transport)
    conn = connect(client, actors[0], "dropbox")
    row, result = enable(
        client, actors[0], "dropbox", {"connection_id": conn, "event": "file_updated"}
    )
    native.tick(db)
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 0
    changed = True
    trigger = db.get(Trigger, result["id"])
    trigger.next_at = now()
    db.commit()
    native.tick(db)
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 1


@pytest.mark.parametrize(
    "module,key,header",
    [
        ("github", "verification", "x-hub-signature-256"),
        ("whatsapp_business", "app_secret", "x-hub-signature-256"),
        ("clickup", "webhook_secret", "x-signature"),
        ("airtable", "mac_secret", "x-airtable-content-mac"),
    ],
)
def test_native_hmac_protocols_require_provider_format_and_bound_identity(
    module, key, header
):
    data = {"webhook_id": "id", "webhook": {"id": "id"}}
    body = json.dumps(data).encode()
    secret = b"provider-secret"
    auth = {
        key: (
            base64.b64encode(secret).decode()
            if key == "mac_secret"
            else secret.decode()
        )
    }
    private = {"secrets": auth, "state": {"id": "id"}}
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    signature = (
        "hmac-sha256="
        if module == "airtable"
        else "sha256=" if module in {"github", "whatsapp_business"} else ""
    ) + signature
    native_events.verify(module, private, {header: signature}, body, data)
    with pytest.raises(HTTPException):
        native_events.verify(module, private, {header: signature}, body + b" ", data)


def test_pubsub_setup_preserves_iam_and_history_on_renewal(monkeypatch):
    monkeypatch.setattr(subscriptions, "cloud_token", lambda *args: "cloud-token")
    calls = []

    class Client:
        conn = NS(id=7)

        def request(self, method, path, body=None, **kw):
            calls.append((method, path, body, kw))
            if path.endswith(":getIamPolicy"):
                return {
                    "etag": "etag",
                    "bindings": [
                        {"role": "roles/viewer", "members": ["user:admin@example.test"]}
                    ],
                }
            if path.endswith("/watch"):
                return {
                    "historyId": "history-1",
                    "expiration": str(int((time.time() + 86400) * 1000)),
                }
            return {}

    private = {"epoch": "epoch", "secrets": {}, "state": {}}
    subscriptions.ensure(
        Client(),
        "gmail",
        {"cloud_project_id": "project-example"},
        private,
        "",
        lambda: None,
    )
    iam = next(
        body["policy"] for _, path, body, _ in calls if path.endswith(":setIamPolicy")
    )
    assert iam["etag"] == "etag" and iam["bindings"][0]["role"] == "roles/viewer"
    assert any(
        "serviceAccount:gmail-api-push@system.gserviceaccount.com" in b["members"]
        for b in iam["bindings"]
    )
    assert private["state"]["history_id"] == "history-1"
    private["state"]["history_id"] = "later-history"
    private["state"]["expires_at"] = datetime.now(timezone.utc).isoformat()
    subscriptions.ensure(
        Client(),
        "gmail",
        {"cloud_project_id": "project-example"},
        private,
        "",
        lambda: None,
    )
    assert private["state"]["history_id"] == "later-history"


from fastapi import HTTPException
