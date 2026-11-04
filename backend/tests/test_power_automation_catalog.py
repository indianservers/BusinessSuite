"""Offline provider contracts and real connector-trigger queue regressions."""

import base64
import hashlib
import hmac
import json
from types import SimpleNamespace as NS
from urllib.parse import urlsplit

import pytest
from app.apps.power_apps.integrations import automation_catalog as catalog
from app.apps.power_apps.integrations import automation_triggers as triggers, adapters
from app.apps.power_apps.integrations.contracts import IntegrationFailure
from app.apps.power_apps.integrations.registry import REGISTRY, INPUTS
from app.apps.power_apps.integrations.transport import Response
from app.apps.power_apps.runtime import now
from app.apps.power_apps.runtime_models import AutomationTrigger as Trigger
from app.apps.power_apps.models import PowerExecution
from tests.test_power_runtime import db, actors, publish, definition, ROOT, drain


def sample(model):
    result = {}
    for key, field in model.model_fields.items():
        if not field.is_required():
            continue
        typ = field.annotation
        result[key] = (
            {}
            if typ is dict
            else (
                []
                if typ is list
                else 1 if typ is int else False if typ is bool else "resource"
            )
        )
    result.update(
        {
            k: v
            for k, v in {
                "to": "a@example.test",
                "subject": "Subject",
                "text": "Body",
                "content_base64": base64.b64encode(b"hello").decode(),
                "mime_type": "text/plain",
                "start_index": 0,
                "end_index": 2,
                "file_path": "folder/file.txt",
                "range": "Sheet1!A1:Z1000",
            }.items()
            if k in result
        }
    )
    return result


@pytest.mark.parametrize("key", sorted(catalog.INSTALLED))
def test_new_operation_dispatch_has_bounded_origin_and_structured_payload(
    key, monkeypatch
):
    mid, aid = key
    calls = []

    class Transport:
        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            host = urlsplit(url).hostname
            assert host in {
                catalog.MODULES[mid]["host"],
                catalog.OPERATIONS[key]["host"],
                "tenant.my.salesforce.com",
                "tenant.atlassian.net",
                "www.zohoapis.com",
                "files.slack.com",
            }
            if kwargs.get("headers", {}).get("Content-Type") == "application/json":
                assert isinstance(json.loads(kwargs["body"]), dict)
            if "files.getUploadURLExternal" in url:
                return Response(
                    200,
                    {},
                    b'{"ok":true,"file_id":"file","upload_url":"https://files.slack.com/upload/fixture"}',
                    1,
                )
            if aid in {"find_rows", "upsert_row"} and method == "GET":
                if mid == "google_sheets":
                    result = {"values": [["resource"], ["resource"]]}
                elif url.endswith("/columns"):
                    result = {"value": [{"index": 0, "name": "resource"}]}
                else:
                    result = {"value": [{"index": 0, "values": [["resource"]]}]}
                return Response(200, {}, json.dumps(result).encode(), 1)
            return Response(
                200,
                {"content-type": "text/plain"},
                b'{"ok":true,"id":"external-id"}',
                1,
            )

    hosts = {
        "salesforce": "tenant.my.salesforce.com",
        "jira": "tenant.atlassian.net",
        "zoho_crm": "www.zohoapis.com",
    }
    conn = NS(connector_id=mid, config={"provider_host": hosts.get(mid, "")})
    if (mid, aid) == ("slack", "upload_file"):
        monkeypatch.setattr(
            "app.apps.power_apps.integrations.transport.HttpTransport",
            lambda policy: Transport(),
        )
    output = catalog.execute(
        conn,
        aid,
        INPUTS[key].model_validate(sample(INPUTS[key])),
        Transport(),
        {"Authorization": "Bearer credential"},
        {"access_token": "123:fixture"},
        "request-key",
    )
    assert (
        len(calls)
        == (
            3
            if (mid, aid) == ("slack", "upload_file")
            else (
                (1 if mid == "google_sheets" else 2) + (1 if aid == "upsert_row" else 0)
                if aid in {"find_rows", "upsert_row"}
                else 1
            )
        )
        and output["http_status"] == 200
    )


def test_sheet_upsert_preserves_unmapped_columns_and_uses_physical_row():
    calls = []

    class Transport:
        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            if method == "GET":
                return Response(
                    200,
                    {},
                    b'{"values":[["ID","Status","Owner"],["a","New","Alex"]]}',
                    1,
                )
            return Response(200, {}, b'{"updatedRows":1}', 1)

    key = ("google_sheets", "upsert_row")
    parsed = INPUTS[key].model_validate(
        {
            "spreadsheet_id": "sheet",
            "range": "Sheet1!A5:C100",
            "key_column": "ID",
            "key_value": "a",
            "record": {"Status": "Done"},
        }
    )
    catalog.execute(
        NS(connector_id="google_sheets", config={}),
        key[1],
        parsed,
        Transport(),
        {},
        {"access_token": "fixture"},
        "key",
    )
    assert calls[1][0] == "PUT" and "A6%3AC6" in calls[1][1]
    assert json.loads(calls[1][2]["body"])["values"] == [["a", "Done", "Alex"]]


def test_telegram_poll_reads_are_not_misclassified_as_external_writes():
    assert not next(
        a for a in REGISTRY["telegram"].actions if a.id == "get_updates"
    ).mutates
    assert not next(
        a for a in REGISTRY["dropbox"].actions if a.id == "list_files"
    ).mutates
    assert next(a for a in REGISTRY["telegram"].actions if a.id == "send_text").mutates


def test_google_folder_and_mime_email_payloads():
    calls = []

    class Transport:
        def request(self, method, url, **kw):
            calls.append(json.loads(kw["body"]))
            return Response(200, {}, b"{}", 1)

    def execute(mid, aid, data):
        return catalog.execute(
            NS(connector_id=mid, config={}),
            aid,
            INPUTS[mid, aid].model_validate(data),
            Transport(),
            {},
            {"access_token": "fixture"},
            "request-key",
        )

    execute("google_drive", "create_folder", {"name": "Reports", "parent_id": "parent"})
    assert calls[-1] == {
        "name": "Reports",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": ["parent"],
    }
    execute(
        "gmail",
        "reply",
        {
            "to": "a@example.test",
            "subject": "Re: Report",
            "text": "Received",
            "thread_id": "thread",
            "in_reply_to": "<id@example.test>",
            "attachments": [
                {
                    "name": "report.txt",
                    "mime_type": "text/plain",
                    "content_base64": "aGVsbG8=",
                }
            ],
        },
    )
    from email import policy
    from email.parser import BytesParser

    email = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(calls[-1]["raw"])
    )
    assert (
        email["In-Reply-To"] == "<id@example.test>"
        and calls[-1]["threadId"] == "thread"
    )
    assert next(email.iter_attachments()).get_payload(decode=True) == b"hello"


def test_row_changes_use_keys_not_position_and_detect_deletions():
    old = triggers.rows_snapshot(["ID", "Status"], [["a", "New"], ["b", "New"]], "ID")
    reordered = triggers.rows_snapshot(
        ["ID", "Status"], [["b", "New"], ["a", "New"]], "ID"
    )
    assert triggers.row_events(old, reordered, {"event": "row_updated"}) == []
    current = triggers.rows_snapshot(
        ["ID", "Status"], [["a", "Done"], ["c", "New"]], "ID"
    )
    changed = triggers.row_events(
        old, current, {"event": "row_updated", "watched_columns": ["Status"]}
    )
    assert changed == [
        {
            "event": "row_updated",
            "row_key": "a",
            "previous": {"ID": "a", "Status": "New"},
            "current": {"ID": "a", "Status": "Done"},
            "changed_columns": ["Status"],
        }
    ]
    assert (
        triggers.row_events(old, current, {"event": "row_deleted"})[0]["row_key"] == "b"
    )
    assert (
        triggers.row_events(old, current, {"event": "row_added"})[0]["row_key"] == "c"
    )
    assert triggers.row_events(None, current, {"event": "row_added"}) == []
    assert (
        len(
            triggers.row_events(
                None, current, {"event": "row_added", "emit_initial": True}
            )
        )
        == 2
    )
    assert (
        len(
            triggers.row_events(
                old,
                current,
                {"event": "condition_matched", "condition": {"Status": "Done"}},
            )
        )
        == 1
    )
    assert (
        triggers.row_events(
            current,
            current,
            {"event": "condition_matched", "condition": {"Status": "Done"}},
        )
        == []
    )


@pytest.mark.parametrize("rows", [[["a"], ["a"]], [[""]], [[]], [["a", "extra"]]])
def test_invalid_nonunique_or_misaligned_sheet_snapshots_fail_closed(rows):
    if rows in ([[""]], [[]]):
        assert triggers.rows_snapshot(["ID"], rows, "ID") == {}
    else:
        with pytest.raises(ValueError):
            triggers.rows_snapshot(["ID"], rows, "ID")


def test_telegram_incoming_media_callbacks_channels_and_cursor():
    updates = [
        {
            "update_id": 1,
            "message": {
                "date": 100,
                "chat": {"id": 42},
                "photo": [{"file_id": "photo"}],
                "caption": "Photo",
            },
        },
        {
            "update_id": 2,
            "callback_query": {
                "id": "callback",
                "data": "confirm",
                "message": {"chat": {"id": 42}},
            },
        },
        {
            "update_id": 3,
            "channel_post": {"date": 100, "chat": {"id": -42}, "text": "Post"},
        },
    ]
    events, offset = triggers.telegram_events(
        updates, {"event": "message_received"}, 0, 100
    )
    assert (
        offset == 4 and events[0]["text"] == "Photo" and events[0]["message"]["photo"]
    )
    assert (
        triggers.telegram_events(updates, {"event": "callback_query"})[0][0]["update"][
            "callback_query"
        ]["data"]
        == "confirm"
    )
    assert (
        triggers.telegram_events(updates, {"event": "channel_post", "chat_id": "-42"})[
            0
        ][0]["text"]
        == "Post"
    )
    assert (
        triggers.telegram_events(updates, {"event": "message_received"}, offset)[0]
        == []
    )


def test_provider_resource_setup_is_applied_to_signed_events():
    setup = {
        "connection_id": 1,
        "event": "email_received",
        "label_id": "INBOX",
        "sender": "a@example.test",
        "subject_contains": "Invoice",
        "has_attachments": True,
    }
    triggers.validate_setup("gmail", setup)
    trigger = NS(config={"module_id": "gmail", "setup": setup})
    event = {
        "event": "email_received",
        "event_id": "1",
        "data": {
            "label_ids": ["INBOX"],
            "sender": "a@example.test",
            "subject": "Invoice 123",
            "has_attachments": True,
        },
    }
    assert triggers.relay_payload(trigger, event)["event_id"] == "1"
    event["data"]["sender"] = "other@example.test"
    with pytest.raises(ValueError, match="selected provider resource"):
        triggers.relay_payload(trigger, event)


def test_new_callback_and_edit_on_old_telegram_message_are_received():
    updates = [
        {
            "update_id": 1,
            "callback_query": {
                "id": "callback",
                "message": {"date": 1, "chat": {"id": 42}},
            },
        },
        {
            "update_id": 2,
            "edited_message": {
                "date": 1,
                "edit_date": 101,
                "chat": {"id": 42},
                "text": "Edited",
            },
        },
    ]
    assert (
        len(
            triggers.telegram_events(
                updates, {"event": "callback_query"}, started_at=100
            )[0]
        )
        == 1
    )
    assert (
        len(
            triggers.telegram_events(
                updates, {"event": "edited_message"}, started_at=100
            )[0]
        )
        == 1
    )


def connect(client, headers, mid, scopes=None):
    response = client.post(
        "/api/v1/power-apps/integrations/connections",
        headers=headers,
        json={
            "connector_id": mid,
            "name": "Trigger fixture",
            "auth_type": "bearer",
            "secrets": {"access_token": "123:fixture"},
            "scopes": scopes or [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def configure(client, headers, mid, setup):
    row = publish(
        client,
        headers,
        definition("integration_trigger_" + mid, setup=setup),
        policy={"identity": "owner", "delegated_owner": True},
    )
    response = client.put(
        f"{ROOT}/{row['id']}/triggers/connector",
        headers=headers,
        json={"enabled": True, "config": {}},
    )
    assert response.status_code == 200, response.text
    return row, response.json()


def test_google_sheet_row_polling_reaches_durable_queue_once(
    client, db, actors, monkeypatch
):
    values = [["ID", "Status"], ["a", "New"]]

    class Transport:
        def __init__(self, policy):
            pass

        def request(self, method, url, **kwargs):
            assert "sheets.googleapis.com/v4/spreadsheets/sheet/values/" in url
            return Response(200, {}, json.dumps({"values": values}).encode(), 1)

    monkeypatch.setattr(adapters, "HTTP_FACTORY", Transport)
    conn = connect(
        client, actors[0], "google_sheets", [catalog.G + "spreadsheets.readonly"]
    )
    row, _ = configure(
        client,
        actors[0],
        "google_sheets",
        {
            "connection_id": conn,
            "event": "row_updated",
            "spreadsheet_id": "sheet",
            "range": "Sheet1!A1:B100",
            "key_column": "ID",
        },
    )
    triggers.poll_tick(db)
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 0
    values[1][1] = "Done"
    trigger = db.query(Trigger).filter_by(resource_id=row["id"], kind="connector").one()
    trigger.next_at = now()
    db.commit()
    triggers.poll_tick(db)
    runs = db.query(PowerExecution).filter_by(resource_id=row["id"]).all()
    assert len(runs) == 1
    drain(db)
    assert runs[0].status == "completed"
    assert "Done" not in trigger.config["snapshot"]
    trigger.next_at = now()
    db.commit()
    triggers.poll_tick(db)
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 1


def test_signed_relay_deduplicates_provider_event_and_rejects_bad_signature(
    client, db, actors
):
    conn = connect(client, actors[0], "slack")
    row, configured = configure(
        client, actors[0], "slack", {"connection_id": conn, "event": "mention_received"}
    )
    body = json.dumps(
        {"event": "mention_received", "event_id": "external-1", "data": {"text": "Hi"}}
    ).encode()
    endpoint = configured["endpoint"]
    secret = configured["secret"]
    timestamp = str(int(now().timestamp()))

    def deliver(nonce, signature=None):
        digest = hmac.new(
            secret.encode(),
            timestamp.encode() + b"." + nonce.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        return client.post(
            endpoint,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Power-Timestamp": timestamp,
                "X-Power-Nonce": nonce,
                "X-Power-Signature": signature or digest,
            },
        )

    assert deliver("bad-signature", "invalid").status_code == 401
    assert deliver("nonce-000001").status_code == 202
    assert deliver("nonce-000002").status_code == 202
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 1


def test_telegram_receive_only_listener_enqueues_media_once(
    client, db, actors, monkeypatch
):
    updates = []

    class Transport:
        def __init__(self, policy):
            pass

        def request(self, method, url, **kwargs):
            if url.endswith("/getMe"):
                result = {"id": 123, "is_bot": True, "username": "fixture"}
            elif url.endswith("/getWebhookInfo"):
                result = {"url": ""}
            else:
                assert url.endswith("/getUpdates")
                result = updates
            return Response(
                200, {}, json.dumps({"ok": True, "result": result}).encode(), 1
            )

    monkeypatch.setattr(adapters, "HTTP_FACTORY", Transport)
    conn = connect(client, actors[0], "telegram")
    row, _ = configure(
        client,
        actors[0],
        "telegram",
        {"connection_id": conn, "event": "message_received"},
    )
    trigger = db.query(Trigger).filter_by(resource_id=row["id"], kind="connector").one()
    updates[:] = [
        {
            "update_id": 9,
            "message": {
                "date": trigger.config["started_at"] + 1,
                "chat": {"id": 42},
                "voice": {"file_id": "voice-file"},
                "caption": "Enquiry",
            },
        }
    ]
    triggers.poll_tick(db)
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 1
    assert trigger.config["offset"] == 10
    drain(db)
    trigger.next_at = now()
    db.commit()
    triggers.poll_tick(db)
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 1


def test_excel_row_update_uses_table_column_names(client, db, actors, monkeypatch):
    values = [["a", "New"]]

    class Transport:
        def __init__(self, policy):
            pass

        def request(self, method, url, **kwargs):
            if url.endswith("/columns"):
                result = {
                    "value": [
                        {"index": 0, "name": "ID"},
                        {"index": 1, "name": "Status"},
                    ]
                }
            else:
                assert url.endswith("/rows")
                result = {
                    "value": [{"index": i, "values": [r]} for i, r in enumerate(values)]
                }
            return Response(200, {}, json.dumps(result).encode(), 1)

    monkeypatch.setattr(adapters, "HTTP_FACTORY", Transport)
    conn = connect(client, actors[0], "excel_online", ["Files.ReadWrite"])
    row, _ = configure(
        client,
        actors[0],
        "excel_online",
        {
            "connection_id": conn,
            "event": "row_updated",
            "drive_id": "drive",
            "workbook_id": "workbook",
            "table_id": "table",
            "key_column": "ID",
        },
    )
    triggers.poll_tick(db)
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 0
    values[0][1] = "Done"
    trigger = db.query(Trigger).filter_by(resource_id=row["id"], kind="connector").one()
    trigger.next_at = now()
    db.commit()
    triggers.poll_tick(db)
    assert db.query(PowerExecution).filter_by(resource_id=row["id"]).count() == 1


def test_download_redirect_strips_credentials_and_rejects_other_hosts(monkeypatch):
    class Origin:
        location = "https://tenant.sharepoint.com/download/file"

        def request(self, *args, **kwargs):
            return Response(302, {"location": self.location}, b"", 1)

    class Download:
        def __init__(self, policy):
            assert policy.allowed_hosts == {"tenant.sharepoint.com"}

        def request(self, method, url, **kwargs):
            assert "Authorization" not in kwargs["headers"]
            return Response(200, {"content-type": "text/plain"}, b"private file", 1)

    monkeypatch.setattr(
        "app.apps.power_apps.integrations.transport.HttpTransport", Download
    )
    key = ("onedrive", "download_file")
    parsed = INPUTS[key].model_validate({"drive_id": "drive", "file_id": "file"})
    origin = Origin()
    result = catalog.execute(
        NS(connector_id="onedrive", config={}),
        key[1],
        parsed,
        origin,
        {"Authorization": "Bearer secret"},
        {"access_token": "secret"},
        "key",
    )
    assert base64.b64decode(result["data"]["content_base64"]) == b"private file"
    origin.location = "https://attacker.example/steal"
    with pytest.raises(IntegrationFailure, match="approved content hosts"):
        catalog.execute(
            NS(connector_id="onedrive", config={}),
            key[1],
            parsed,
            origin,
            {"Authorization": "Bearer secret"},
            {"access_token": "secret"},
            "key",
        )
