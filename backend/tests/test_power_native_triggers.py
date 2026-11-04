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
from app.apps.power_apps.integrations.models import NativeDelivery, ConnectorGate
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
    assert not db.query(ConnectorGate).one().leases, (
        db.query(ConnectorGate).one().leases
    )
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
    db.refresh(trigger)
    assert trigger.next_at.replace(tzinfo=timezone.utc) <= now(), (
        trigger.next_at,
        now(),
        trigger.config,
    )
    native.tick(db)
    drain(db)
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 1, (
        trigger.config["native"],
        native.read_private(trigger)["state"],
        db.query(ConnectorGate).one().leases,
        [(d.status, d.attempts) for d in db.query(NativeDelivery).all()],
    )
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

SETUPS = {
    "gmail": {"cloud_project_id": "project-example"},
    "google_forms": {"cloud_project_id": "project-example", "form_id": "form"},
    "google_drive": {},
    "google_calendar": {"calendar_id": "calendar"},
    "outlook": {},
    "onedrive": {"drive_id": "drive"},
    "sharepoint": {"site_id": "site", "list_id": "list"},
    "microsoft_calendar": {},
    "microsoft_teams": {"team_id": "team", "channel_id": "channel"},
    "github": {"owner": "owner", "repository": "repo", "event": "push"},
    "clickup": {"team_id": "team", "event": "task_created"},
    "box": {"folder_id": "folder", "event": "file_uploaded"},
    "airtable": {"base_id": "base", "table_id": "table"},
    "zoho_crm": {"module": "Leads"},
    "jira": {},
    "slack": {"app_id": "app", "event": "mention_received"},
    "whatsapp_business": {
        "app_id": "app",
        "business_account_id": "business",
        "api_version": "v26.0",
    },
    "dropbox": {},
    "notion": {},
    "hubspot": {"object_type": "contacts"},
    "salesforce": {"event": "platform_event"},
    "http": {},
}


@pytest.mark.parametrize("mid", sorted(SETUPS))
def test_every_remaining_module_automatically_configures_its_native_source(
    mid, monkeypatch
):
    from app.apps.power_apps.integrations import native_hubspot

    monkeypatch.setattr(subscriptions, "cloud_token", lambda *args: "cloud-token")
    monkeypatch.setattr(native_hubspot, "token", lambda *args: "journal-token")
    calls = []

    class Client:
        conn = NS(id=1)

        def collection(self, path, *args, **kw):
            calls.append(("GET", path, None))
            return [], {}

        def request(self, method, path, body=None, **kw):
            calls.append((method, path, body))
            if path.endswith(":getIamPolicy"):
                return {"bindings": []}
            if path.endswith("/startPageToken"):
                return {"startPageToken": "cursor"}
            if path.endswith("/auth.test"):
                return {"team_id": "workspace"}
            if path.endswith("/apps.manifest.export"):
                return {
                    "manifest": {
                        "display_information": {"name": "Existing app"},
                        "settings": {},
                    }
                }
            if path.endswith("/apps.manifest.update"):
                manifest = json.loads(body["manifest"])
                assert manifest["display_information"]["name"] == "Existing app"
                assert (
                    manifest["settings"]["event_subscriptions"]["request_url"]
                    == "https://callback.example/native"
                )
                return {"ok": True}
            if path.endswith("/account-info/v3/details"):
                return {"portalId": 7}
            if path.endswith("/latest"):
                return {"_status": 404}
            if method == "GET":
                if mid in {"github", "jira"}:
                    return []
                return {
                    "webhooks": [],
                    "entries": [],
                    "data": [],
                    "watches": [],
                    "results": [],
                }
            if mid == "gmail" and path.endswith("/watch"):
                return {
                    "historyId": "1",
                    "expiration": str(int((time.time() + 86400) * 1000)),
                }
            if mid == "google_forms" and "/forms/" in path:
                return {
                    "id": "watch",
                    "expireTime": (
                        datetime.now(timezone.utc) + timedelta(days=7)
                    ).isoformat(),
                }
            if mid in {"google_drive", "google_calendar"} and path.endswith("/watch"):
                return {
                    "id": body["id"],
                    "resourceId": "resource",
                    "expiration": str(int((time.time() + 86400) * 1000)),
                }
            if mid == "clickup":
                return {"webhook": {"id": "hook", "secret": "provider-hook-secret"}}
            if mid == "airtable":
                return {
                    "id": "hook",
                    "macSecretBase64": base64.b64encode(b"mac").decode(),
                    "expirationTime": (
                        datetime.now(timezone.utc) + timedelta(days=7)
                    ).isoformat(),
                }
            if mid in subscriptions.GRAPH:
                return {"id": "hook", "expirationDateTime": body["expirationDateTime"]}
            return {"id": "hook", "watch": [{"status": "success"}], "success": True}

    private = {
        "epoch": "epoch",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "secrets": {
            "verification": "verify",
            "primary_signature_key": "box-key",
            "configuration_token": "config-token",
            "app_secret": "meta-secret",
        },
        "state": {},
    }
    subscriptions.ensure(
        Client(),
        mid,
        {"event": "record_updated", **SETUPS[mid]},
        private,
        "https://callback.example/native",
        lambda: None,
    )
    assert private["state"].get("id") or private["state"].get("registered_at")
    if mid not in {"dropbox", "notion", "salesforce", "http"}:
        assert any(method in {"POST", "PUT"} for method, _, _ in calls)


def test_graph_expiring_subscription_is_renewed_without_duplicate_creation():
    calls = []

    class Client:
        def request(self, method, path, body=None, **kwargs):
            calls.append((method, path, body))
            return {"expirationDateTime": body["expirationDateTime"]}

    private = {
        "epoch": "epoch",
        "secrets": {},
        "state": {
            "id": "subscription",
            "expires_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    subscriptions.ensure(
        Client(), "outlook", {}, private, "https://callback", lambda: None
    )
    assert (
        len(calls) == 1
        and calls[0][0] == "PATCH"
        and calls[0][1].endswith("/subscription")
    )


def test_salesforce_native_stream_uses_wrapped_bayeux_and_replay_cursor():
    calls = []

    class Client:
        def request(self, method, path, body=None, **kw):
            calls.append(body)
            assert isinstance(body, list)
            if body[0]["channel"] == "/meta/handshake":
                return [
                    {
                        "channel": "/meta/handshake",
                        "successful": True,
                        "clientId": "client",
                    }
                ]
            if body[0]["channel"] == "/meta/subscribe":
                assert body[0]["ext"]["replay"]["/event/Order__e"] == 5
                return [{"successful": True}]
            return [
                {
                    "channel": "/event/Order__e",
                    "data": {"event": {"replayId": 6}, "payload": {"Order": "order"}},
                }
            ]

    private = {"state": {"replay_id": 5}}
    result = native_sources.poll_stream(
        Client(), {"api_version": "v68.0", "stream_channel": "/event/Order__e"}, private
    )
    assert (
        len(result) == 1
        and result[0]["event"] == "platform_event"
        and private["state"]["replay_id"] == 6
    )


def test_hubspot_journal_binds_portal_and_does_not_forward_bearer_to_s3(monkeypatch):
    from app.apps.power_apps.integrations import native_hubspot

    monkeypatch.setattr(native_hubspot, "token", lambda *args: "app-token")

    class Client:
        def request(self, method, path, **kw):
            assert kw["bearer"] == "app-token"
            return {
                "currentOffset": "next",
                "url": "https://s3.amazonaws.com/bucket/journal.json?X-Amz-Signature=signed",
            }

    rows = [
        {
            "type": "crmObject",
            "portalId": 7,
            "objectTypeId": "0-1",
            "objectId": 1,
            "occurredAt": "2026-11-04T01:00:00Z",
            "action": "CREATE",
        },
        {
            "type": "crmObject",
            "portalId": 99,
            "objectTypeId": "0-1",
            "objectId": 2,
            "occurredAt": "2026-11-04T01:00:00Z",
            "action": "CREATE",
        },
    ]

    class Transport:
        def __init__(self, policy):
            assert policy.allowed_hosts == {"s3.amazonaws.com"}

        def request(self, method, url, **kw):
            assert "Authorization" not in kw["headers"]
            return Response(
                200,
                {},
                json.dumps({"offset": "next", "journalEvents": rows}).encode(),
                1,
            )

    monkeypatch.setattr(adapters, "HTTP_FACTORY", Transport)
    private = {
        "started_at": "2026-11-04T00:00:00+00:00",
        "secrets": {},
        "state": {
            "portal_id": 7,
            "object_type_id": "0-1",
            "journal_offset": "previous",
        },
    }
    result = native_hubspot.poll(
        Client(), {"object_type": "contacts", "event": "record_created"}, private
    )
    assert (
        len(result) == 1
        and result[0]["data"]["id"] == "1"
        and private["state"]["journal_offset"] == "next"
    )


def test_native_inbox_migration_is_idempotent_and_indexed():
    from sqlalchemy import create_engine, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.apps.power_apps.integrations import native_schema

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        for table in ("companies", "users", "power_automation_triggers"):
            conn.exec_driver_sql(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
        op = Operations(MigrationContext.configure(conn))
        native_schema.upgrade(op)
        native_schema.upgrade(op)
        assert "power_native_deliveries" in inspect(conn).get_table_names()
        assert {
            i["name"] for i in inspect(conn).get_indexes("power_native_deliveries")
        } == {"ix_power_native_delivery_due"}
        native_schema.downgrade(op)
        assert "power_native_deliveries" not in inspect(conn).get_table_names()


@pytest.mark.parametrize("subtype", ["message_changed", "message_deleted"])
def test_slack_edits_do_not_fire_incoming_message_trigger(subtype):
    from app.apps.power_apps.integrations.native_events import normalize

    assert (
        normalize(
            None,
            "slack",
            {"app_id": "A1"},
            {"state": {"account_id": "T1"}},
            {
                "body": {
                    "type": "event_callback",
                    "team_id": "T1",
                    "api_app_id": "A1",
                    "event_id": "E1",
                    "event": {"type": "message", "subtype": subtype},
                }
            },
        )
        == []
    )


def test_graph_calendar_callback_reads_only_selected_calendar():
    from app.apps.power_apps.integrations.native_events import normalize

    class Client:
        def request(self, method, path, **kwargs):
            assert path == "/v1.0/me/calendars/selected/events/event1"
            return {"_status": 404}

    assert (
        normalize(
            Client(),
            "microsoft_calendar",
            {"calendar_id": "selected"},
            {"state": {}},
            {
                "body": {
                    "value": [
                        {"resourceData": {"id": "event1"}, "changeType": "created"}
                    ]
                }
            },
        )
        == []
    )


def test_teams_deleted_messages_do_not_fire_incoming_trigger():
    from app.apps.power_apps.integrations.native_events import normalize

    assert (
        normalize(
            None,
            "microsoft_teams",
            {},
            {"state": {}},
            {
                "body": {
                    "value": [
                        {"resourceData": {"id": "deleted"}, "changeType": "deleted"}
                    ]
                }
            },
        )
        == []
    )
