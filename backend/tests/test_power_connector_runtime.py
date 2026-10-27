"""Real queue/webhook/API checks with isolated provider responses."""

import copy
import hashlib
import hmac
import json
import pytest
from app.apps.power_apps.integrations import adapters
from app.apps.power_apps.integrations.models import Operation, Credential, Connection
from app.apps.power_apps.integrations.transport import Response
from app.apps.power_apps.models import PowerExecution
from app.apps.power_apps.runtime import now, process, claim
from tests.test_power_runtime import (
    db,
    actors,
    definition,
    publish,
    run,
    drain,
    history,
    node,
    edge,
    ROOT,
)

API = "/api/v1/power-apps/integrations"


def connect(client, headers, connector="groq", writes=True):
    response = client.post(
        API + "/connections",
        headers=headers,
        json={
            "connector_id": connector,
            "name": "Isolated fixture",
            "auth_type": "bearer",
            "secrets": {"access_token": "fixture-secret-not-live"},
            "writes_enabled": writes,
        },
    )
    assert response.status_code == 201, response.text
    assert (
        "fixture-secret-not-live" not in response.text
        and "encrypted_value" not in response.text
    )
    return response.json()


def external_node(connection, action="generate_text", **input):
    n = node(
        "provider", "connector_groq", action=action, input=input, confirm_write=True
    )
    n["credential_reference"] = str(connection["id"])
    return n


def fixture_transport(monkeypatch, callback=None):
    calls = []

    class Transport:
        def __init__(self, policy):
            pass

        def request(self, method, url, headers=None, body=None, **kwargs):
            kwargs.update(headers=headers, body=body)
            calls.append((method, url, kwargs))
            if callback:
                return callback(method, url, kwargs)
            return Response(
                200, {}, b'{"choices":[{"message":{"content":"fixture answer"}}]}', 1
            )

    monkeypatch.setattr(adapters, "HTTP_FACTORY", Transport)
    return calls


def test_connection_api_secrets_owner_and_tenant_boundaries(client, db, actors):
    connection = connect(client, actors[0])
    for other in actors[1:]:
        listing = client.get(API + "/connections", headers=other)
        assert listing.status_code in {200, 403}, listing.text
        if listing.status_code == 200:
            assert listing.json()["items"] == []
        response = client.post(
            API + "/execute",
            headers=other,
            json={
                "connection_id": connection["id"],
                "action_id": "list_models",
                "request_id": "fixture-request",
            },
        )
        assert response.status_code in {403, 404}, response.text
    credential = db.query(Credential).one()
    assert "fixture-secret-not-live" not in credential.encrypted_value


def test_action_probe_idempotency_and_write_opt_in(client, db, actors, monkeypatch):
    calls = fixture_transport(monkeypatch)
    connection = connect(client, actors[0])
    data = {
        "connection_id": connection["id"],
        "action_id": "generate_text",
        "input": {"model": "fixture-model", "prompt": "Hello"},
        "request_id": "same-probe-key",
        "confirm_side_effect": False,
    }
    assert (
        client.post(API + "/execute", headers=actors[0], json=data).status_code == 422
    )
    assert not calls
    data["confirm_side_effect"] = True
    for _ in range(2):
        response = client.post(API + "/execute", headers=actors[0], json=data)
        assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert db.query(Operation).one().status == "succeeded"


def test_signed_webhook_resolves_input_dispatches_provider_and_resumes_queue(
    client, db, actors, monkeypatch
):
    calls = fixture_transport(monkeypatch)
    connection = connect(client, actors[0])
    graph = definition(
        "webhook_trigger",
        nodes=[
            external_node(
                connection, model="fixture-model", prompt="{{trigger.input.message}}"
            ),
            node("done", "log_event", message="Completed"),
        ],
        edges=[edge("start", "provider"), edge("provider", "done")],
        event_name="provider-fixture",
    )
    row = publish(
        client, actors[0], graph, {"identity": "owner", "delegated_owner": True}
    )
    response = client.put(
        f"{ROOT}/{row['id']}/triggers/webhook",
        headers=actors[0],
        json={
            "enabled": True,
            "config": {
                "schema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                }
            },
        },
    )
    assert response.status_code == 200, response.text
    hook = response.json()
    body = b'{"message":"From webhook"}'
    stamp = str(int(now().timestamp()))
    nonce = "provider-event-001"
    signature = hmac.new(
        hook["secret"].encode(),
        stamp.encode() + b"." + nonce.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "x-power-timestamp": stamp,
        "x-power-nonce": nonce,
        "x-power-signature": signature,
        "content-type": "application/json",
    }
    received = client.post(hook["endpoint"], headers=headers, content=body)
    assert received.status_code == 202, received.text
    assert (
        client.post(hook["endpoint"], headers=headers, content=body).status_code == 409
    )
    drain(db)
    assert len(calls) == 1
    assert json.loads(calls[0][2]["body"])["messages"][0]["content"] == "From webhook"
    operation = db.query(Operation).one()
    assert operation.status == "succeeded" and operation.run_id and operation.step_id
    assert db.get(PowerExecution, operation.run_id).status == "completed"


def test_publish_rejects_disabled_or_unapproved_external_write(client, db, actors):
    connection = connect(client, actors[0], writes=False)
    graph = definition(
        nodes=[external_node(connection, model="fixture-model", prompt="Hello")],
        edges=[edge("start", "provider")],
    )
    from tests.test_power_studio import create

    row = create(client, actors[0], graph)
    body = {"expected_version": row["version"]}
    assert (
        client.post(
            f"{ROOT}/{row['id']}/runtime/validate", headers=actors[0], json=body
        ).status_code
        == 200
    )
    response = client.post(
        f"{ROOT}/{row['id']}/runtime/publish", headers=actors[0], json=body
    )
    assert response.status_code == 422, response.text


def test_uncertain_external_write_is_not_blindly_resent(
    client, db, actors, monkeypatch
):
    def timeout(*args):
        from app.apps.power_apps.integrations.contracts import IntegrationFailure

        raise IntegrationFailure(
            "timeout", "Provider response was lost", uncertain=True
        )

    calls = fixture_transport(monkeypatch, timeout)
    connection = connect(client, actors[0])
    data = {
        "connection_id": connection["id"],
        "action_id": "generate_text",
        "input": {"model": "fixture-model", "prompt": "Hello"},
        "request_id": "uncertain-probe-key",
        "confirm_side_effect": True,
    }
    for _ in range(2):
        assert (
            client.post(API + "/execute", headers=actors[0], json=data).status_code
            == 409
        )
    assert len(calls) == 1 and db.query(Operation).one().status == "uncertain"


def test_managed_own_scope_can_create_and_use_connection(
    client, db, actors, monkeypatch
):
    fixture_transport(monkeypatch)
    connection = connect(client, actors[3])
    listing = client.get(API + "/connections", headers=actors[3])
    assert listing.status_code == 200, listing.text
    assert [c["id"] for c in listing.json()["items"]] == [connection["id"]]
    response = client.post(
        API + "/execute",
        headers=actors[3],
        json={
            "connection_id": connection["id"],
            "action_id": "list_models",
            "request_id": "managed-read-request",
        },
    )
    assert response.status_code == 200, response.text


def test_readonly_connection_cannot_mutate_via_probe(client, db, actors, monkeypatch):
    calls = fixture_transport(monkeypatch)
    connection = connect(client, actors[0], writes=False)
    response = client.post(
        API + "/execute",
        headers=actors[0],
        json={
            "connection_id": connection["id"],
            "action_id": "generate_text",
            "input": {"model": "fixture-model", "prompt": "Hello"},
            "request_id": "read-only-write-attempt",
            "confirm_side_effect": True,
        },
    )
    assert response.status_code == 422, response.text
    assert not calls


from tests.test_smtp_email import smtp


def test_sheet_append_then_smtp_uses_queue_mapping_and_existing_mail_service(
    client, db, actors, monkeypatch, smtp
):
    calls = fixture_transport(
        monkeypatch,
        lambda *args: Response(200, {}, b'{"updates":{"updatedRows":1}}', 1),
    )
    sheet = client.post(
        API + "/connections",
        headers=actors[0],
        json={
            "connector_id": "google_sheets",
            "name": "Fixture spreadsheet",
            "auth_type": "bearer",
            "secrets": {"access_token": "fixture-google-token"},
            "scopes": ["https://www.googleapis.com/auth/spreadsheets"],
            "writes_enabled": True,
        },
    )
    mail = client.post(
        API + "/connections",
        headers=actors[0],
        json={
            "connector_id": "smtp",
            "name": "Fixture SMTP",
            "auth_type": "platform_smtp",
            "writes_enabled": True,
        },
    )
    assert sheet.status_code == 201, sheet.text
    assert mail.status_code == 201, mail.text
    sheets = node(
        "sheet",
        "connector_google_sheets",
        action="append_rows",
        input={
            "spreadsheet_id": "fixture_spreadsheet_123",
            "range": "Sheet1!A:B",
            "values": [["{{trigger.input.name}}", "{{trigger.input.email}}"]],
        },
        confirm_write=True,
    )
    sheets["credential_reference"] = str(sheet.json()["id"])
    email = node(
        "email",
        "connector_smtp",
        action="send",
        input={
            "recipient": "{{trigger.input.email}}",
            "subject": "Submission received",
            "text": "Hello {{trigger.input.name}}",
        },
        confirm_write=True,
    )
    email["credential_reference"] = str(mail.json()["id"])
    row = publish(
        client,
        actors[0],
        definition(
            nodes=[sheets, email],
            edges=[edge("start", "sheet"), edge("sheet", "email")],
        ),
    )
    run_id = run(
        client, actors[0], row, data={"name": "Asha", "email": "recipient@example.com"}
    )
    drain(db)
    assert db.get(PowerExecution, run_id).status == "completed", [
        (o.connector_id, o.status, o.error) for o in db.query(Operation).all()
    ] + [
        (step.node_id, step.status, step.error)
        for step in db.query(
            __import__(
                "app.apps.power_apps.runtime_models", fromlist=["AutomationStep"]
            ).AutomationStep
        ).all()
    ]
    assert len(calls) == 1
    assert json.loads(calls[0][2]["body"])["values"] == [
        ["Asha", "recipient@example.com"]
    ]
    smtp.starttls.assert_called_once()
    assert smtp.send_message.call_args.kwargs["to_addrs"] == ["recipient@example.com"]
    assert "Hello Asha" in smtp.send_message.call_args.args[0].get_content()
    assert db.query(Operation).filter_by(run_id=run_id, status="succeeded").count() == 2


def test_generic_http_post_requires_published_write_confirmation(client, db, actors):
    response = client.post(
        API + "/connections",
        headers=actors[0],
        json={
            "connector_id": "http",
            "name": "Fixture HTTP",
            "auth_type": "none",
            "config": {"hosts": ["public.example"]},
            "writes_enabled": True,
        },
    )
    assert response.status_code == 201, response.text
    external = node(
        "http",
        "connector_http",
        action="request",
        input={"url": "https://public.example/events", "method": "POST"},
        confirm_write=False,
    )
    external["credential_reference"] = str(response.json()["id"])
    from tests.test_power_studio import create

    row = create(
        client, actors[0], definition(nodes=[external], edges=[edge("start", "http")])
    )
    body = {"expected_version": row["version"]}
    assert (
        client.post(
            f"{ROOT}/{row['id']}/runtime/validate", headers=actors[0], json=body
        ).status_code
        == 200
    )
    denied = client.post(
        f"{ROOT}/{row['id']}/runtime/publish", headers=actors[0], json=body
    )
    assert denied.status_code == 422, denied.text


def test_outgoing_webhook_defaults_post_and_signs_exact_body(
    client, db, actors, monkeypatch
):
    calls = fixture_transport(
        monkeypatch, lambda *args: Response(200, {}, b'{"ok":true}', 1)
    )
    response = client.post(
        API + "/connections",
        headers=actors[0],
        json={
            "connector_id": "outgoing_webhook",
            "name": "Signed fixture",
            "auth_type": "signing",
            "secrets": {"signing_secret": "fixture-signing-value"},
            "config": {"hosts": ["public.example"]},
            "writes_enabled": True,
        },
    )
    assert response.status_code == 201, response.text
    executed = client.post(
        API + "/execute",
        headers=actors[0],
        json={
            "connection_id": response.json()["id"],
            "action_id": "deliver",
            "input": {
                "url": "https://public.example/events",
                "body": {"event": "fixture"},
            },
            "request_id": "signed-outgoing-fixture",
            "confirm_side_effect": True,
        },
    )
    assert executed.status_code == 200, executed.text
    method, url, kwargs = calls[0]
    headers = kwargs["headers"]
    assert method == "POST"
    signature = hmac.new(
        b"fixture-signing-value",
        headers["X-Power-Timestamp"].encode()
        + b"."
        + headers["X-Power-Nonce"].encode()
        + b"."
        + kwargs["body"],
        hashlib.sha256,
    ).hexdigest()
    assert hmac.compare_digest(signature, headers["X-Power-Signature"])
    assert json.loads(kwargs["body"]) == {"event": "fixture"}


def test_cancel_during_provider_request_fences_completion_but_keeps_journal(client,db,actors,monkeypatch):
    from app.apps.power_apps.runtime import finish
    from app.apps.power_apps.runtime_models import AutomationRun, AutomationStep
    holder={}
    def provider(*args):
        current=db.get(AutomationRun,holder["run_id"])
        finish(db,current,"cancelled");db.commit()
        return Response(200,{},b'{"choices":[{"message":{"content":"accepted before cancellation"}}]}',1)
    calls=fixture_transport(monkeypatch,provider)
    connection=connect(client,actors[0])
    graph=definition(nodes=[external_node(connection,model="fixture-model",prompt="Hello"),node("done","log_event",message="Must not run")],edges=[edge("start","provider"),edge("provider","done")])
    row=publish(client,actors[0],graph);holder["run_id"]=run(client,actors[0],row)
    drain(db)
    assert len(calls)==1
    assert db.get(PowerExecution,holder["run_id"]).status=="cancelled"
    assert db.query(Operation).filter_by(run_id=holder["run_id"]).one().status=="succeeded"
    assert db.query(AutomationStep).filter_by(run_id=holder["run_id"],node_id="done").one().status=="cancelled"
