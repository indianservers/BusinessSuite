import copy
import hashlib
import hmac
import json
from datetime import timedelta, datetime, timezone
import pytest
from fastapi import HTTPException
from app.apps.power_apps.models import PowerExecution, PowerResource, PowerVersion
from app.apps.power_apps.runtime_models import (
    AutomationRun as Run,
    AutomationStep as Step,
    AutomationJob as Job,
    AutomationWait as Wait,
    AutomationTrigger as Trigger,
    AutomationDeployment as Deployment,
)
from app.apps.power_apps.runtime import claim, process, tick, now, utc
from app.apps.power_apps.runtime_triggers import scheduler_tick
from app.apps.power_apps.runtime_schedule import next_occurrence
from tests.conftest import TestingSessionLocal


@pytest.fixture
def db(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("BEGIN")
    session = TestingSessionLocal(
        bind=connection, join_transaction_mode="create_savepoint"
    )
    yield session
    session.close()
    transaction.rollback()
    connection.close()


from tests.test_power_apps import actors
from tests.test_power_studio import node, edge, create, ROOT


def definition(kind="manual_trigger", nodes=None, edges=None, **config):
    return {
        "schema_version": 2,
        "nodes": [
            node("start", kind, **config),
            *(
                nodes
                or [
                    node("set", "set_variable", name="result", value=42),
                    node("log", "log_event", message="Done"),
                ]
            ),
        ],
        "edges": edges or [edge("start", "set"), edge("set", "log")],
    }


def publish(client, headers, value=None, policy=None):
    row = create(client, headers, value or definition())
    body = {"expected_version": row["version"]}
    if policy:
        body["policy"] = policy
    for action in ["validate", "publish", "activate"]:
        response = client.post(
            f"{ROOT}/{row['id']}/runtime/{action}", headers=headers, json=body
        )
        assert response.status_code == 200, response.text
    return row


def run(client, headers, row, key="test-request-0001", data=None):
    response = client.post(
        f"{ROOT}/{row['id']}/execute",
        headers=headers,
        json={"input": data or {}, "idempotency_key": key},
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def drain(db, limit=200):
    count = 0
    while count < limit:
        work = claim(db, "test-worker")
        if not work:
            break
        process(db, *work)
        count += 1
    return count


def history(client, headers, run_id):
    response = client.get(f"/api/v1/power-apps/executions/{run_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_success_persisted_history_idempotency_and_metrics(client, db, actors):
    row = publish(client, actors[0])
    run_id = run(client, actors[0], row)
    assert run(client, actors[0], row) == run_id
    assert db.get(PowerExecution, run_id).status == "queued"
    assert drain(db) == 3
    report = history(client, actors[0], run_id)
    assert report["execution"]["status"] == "completed"
    assert report["run"]["variables"]["result"] == 42
    assert [s["status"] for s in report["steps"]] == ["completed"] * 3
    assert any(e["kind"] == "structured_log" for e in report["events"])
    metrics = client.get("/api/v1/power-apps/executions", headers=actors[0]).json()
    assert (
        metrics["metrics"]["completed"] == 1 and metrics["metrics"]["queue_depth"] == 0
    )
    assert metrics["metrics"]["average_duration_seconds"] is not None


def test_b_conditional_skip(client, db, actors):
    value = definition(
        nodes=[
            node("check", "if_else", left=1, operator="equals", right=1),
            node("yes", "log_event", message="Yes"),
            node("no", "log_event", message="No"),
        ],
        edges=[
            edge("start", "check"),
            edge("check", "yes", "true"),
            edge("check", "no", "false"),
        ],
    )
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row)
    drain(db)
    steps = {s["node_id"]: s for s in history(client, actors[0], run_id)["steps"]}
    assert steps["yes"]["status"] == "completed" and steps["no"]["status"] == "skipped"


def test_c_schedule_duplicate_claims_and_explicit_delegation(client, db, actors):
    row = publish(
        client,
        actors[0],
        definition("scheduled_trigger", schedule="* * * * *", timezone="UTC"),
        {"identity": "owner", "delegated_owner": True},
    )
    response = client.put(
        f"{ROOT}/{row['id']}/triggers/scheduled",
        headers=actors[0],
        json={"enabled": True, "config": {"mode": "minutes", "every_minutes": 1}},
    )
    assert response.status_code == 200, response.text
    trigger = db.query(Trigger).one()
    trigger.next_at = now() - timedelta(seconds=1)
    db.commit()
    assert scheduler_tick(db) == 1
    assert scheduler_tick(db) == 0
    assert db.query(PowerExecution).count() == 1
    drain(db)
    assert db.query(PowerExecution).one().status == "completed"


def test_d_delay_release_and_new_session_resume(client, db, actors):
    value = definition(
        nodes=[
            node("wait", "delay", seconds=1),
            node("log", "log_event", message="Resumed"),
        ],
        edges=[edge("start", "wait"), edge("wait", "log")],
    )
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row)
    assert drain(db) == 2
    assert db.get(PowerExecution, run_id).status == "waiting"
    assert db.query(Job).filter_by(status="running").count() == 0
    wait = db.query(Wait).one()
    wait.wake_at = now() - timedelta(seconds=1)
    db.commit()
    db.expire_all()
    assert tick(db) == 1
    drain(db)
    assert db.get(PowerExecution, run_id).status == "completed"


def test_e_worker_crash_recovery_and_fencing(client, db, actors):
    row = publish(client, actors[0])
    run_id = run(client, actors[0], row)
    old = claim(db, "crashing-worker")
    assert old
    job = db.get(Job, old[0])
    job.lease_until = now() - timedelta(seconds=1)
    db.commit()
    replacement = claim(db, "replacement")
    assert replacement and replacement[0] == old[0] and replacement[1] != old[1]
    assert process(db, *old) == "lost_lease"
    assert process(db, *replacement) == "completed"
    drain(db)
    assert db.get(PowerExecution, run_id).status == "completed"
    assert db.query(Step).filter_by(run_id=run_id, node_id="start").one().attempt == 2


def test_f_bounded_retry_then_success_and_manual_retry(client, db, actors, monkeypatch):
    from app.apps.power_apps.runtime_executors import Executor

    original = Executor.execute
    calls = []

    def controlled(self, node, config, payload, previous):
        if node.id == "set" and not calls:
            calls.append(1)
            raise TimeoutError("Controlled transient failure")
        return original(self, node, config, payload, previous)

    monkeypatch.setattr(Executor, "execute", controlled)
    row = publish(client, actors[0])
    run_id = run(client, actors[0], row)
    drain(db)
    job = (
        db.query(Job)
        .join(Step, Step.id == Job.step_id)
        .filter(Step.node_id == "set")
        .one()
    )
    assert job.status == "queued" and utc(job.available_at) > now()
    job.available_at = now() - timedelta(seconds=1)
    db.commit()
    drain(db)
    assert db.get(PowerExecution, run_id).status == "completed"
    assert db.query(Step).filter_by(run_id=run_id, node_id="set").one().attempt == 2


@pytest.mark.parametrize("strategy", ["all", "first_completed", "first_successful"])
def test_g_parallel_join(client, db, actors, strategy):
    value = definition(
        nodes=[
            node("fork", "parallel_branch"),
            node("a", "set_variable", value="a"),
            node("b", "set_variable", value="b"),
            node("join", "merge", strategy=strategy),
            node("log", "log_event", message="Merged"),
        ],
        edges=[
            edge("start", "fork"),
            edge("fork", "a", "route_1"),
            edge("fork", "b", "route_2"),
            edge("a", "join", target="in_1") if False else edge("a", "join"),
            edge("b", "join"),
            edge("join", "log"),
        ],
    )
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row)
    drain(db)
    assert db.get(PowerExecution, run_id).status == "completed"
    assert db.query(Step).filter_by(run_id=run_id, node_id="join").one().attempt == 1


def test_h_permissions_tenants_and_revocation(client, db, actors):
    row = publish(client, actors[0])
    run_id = run(client, actors[0], row)
    assert (
        client.get(
            f"/api/v1/power-apps/executions/{run_id}", headers=actors[1]
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{ROOT}/{row['id']}/execute",
            headers=actors[2],
            json={"idempotency_key": "unauthorized"},
        ).status_code
        == 403
    )
    from app.models.user import User

    user = db.get(User, db.get(PowerExecution, run_id).actor_user_id)
    user.is_active = False
    db.commit()
    drain(db)
    assert db.get(PowerExecution, run_id).status == "failed"
    assert db.get(Run, run_id).error_type == "AuthorizationRevoked"


def test_i_concurrency_backpressure_cancel(client, db, actors):
    row = publish(client, actors[0], policy={"concurrency": 1})
    first = run(client, actors[0], row, "request-first")
    second = run(client, actors[0], row, "request-second")
    work = claim(db, "worker-a")
    assert work
    assert claim(db, "worker-b") is None
    assert (
        client.post(
            f"/api/v1/power-apps/executions/{first}/cancel", headers=actors[0]
        ).status_code
        == 200
    )
    assert process(db, *work) == "lost_lease"
    drain(db)
    assert db.get(PowerExecution, second).status == "completed"


def test_j_published_version_integrity(client, db, actors):
    row = publish(client, actors[0])
    run_id = run(client, actors[0], row)
    changed = copy.deepcopy(row["definition"])
    changed["nodes"][1]["config"]["value"] = 99
    response = client.put(
        f"{ROOT}/{row['id']}",
        headers=actors[0],
        json={
            "name": row["name"],
            "description": "Changed draft",
            "definition": changed,
            "expected_version": row["version"],
        },
    )
    assert response.status_code == 200, response.text
    drain(db)
    report = history(client, actors[0], run_id)
    assert report["execution"]["workflow_version"] == 1
    assert (
        next(s for s in report["steps"] if s["node_id"] == "set")["output"]["value"]
        == 42
    )
    assert (
        next(n for n in report["definition"]["nodes"] if n["id"] == "set")["config"][
            "value"
        ]
        == 42
    )


def test_signed_webhook_replay_rotation_and_schema(client, db, actors):
    row = publish(
        client,
        actors[0],
        definition("webhook_trigger", event_name="secure-ingress"),
        {"identity": "owner", "delegated_owner": True},
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
    data = response.json()
    body = b'{"message":"hello"}'
    stamp = str(int(now().timestamp()))
    nonce = "unique-event-0001"
    signature = hmac.new(
        data["secret"].encode(),
        stamp.encode() + b"." + nonce.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "x-power-timestamp": stamp,
        "x-power-nonce": nonce,
        "x-power-signature": signature,
        "content-type": "application/json",
    }
    unsigned = client.post(data["endpoint"], content=body)
    assert unsigned.status_code == 401, unsigned.text
    result = client.post(data["endpoint"], headers=headers, content=body)
    assert result.status_code == 202, result.text
    assert (
        client.post(data["endpoint"], headers=headers, content=body).status_code == 409
    )
    assert (
        client.post(
            f"{ROOT}/{row['id']}/triggers/webhook/rotate", headers=actors[0]
        ).status_code
        == 200
    )
    headers["x-power-nonce"] = "unique-event-0002"
    assert (
        client.post(data["endpoint"], headers=headers, content=body).status_code == 401
    )
    drain(db)
    assert db.query(PowerExecution).one().status == "completed"


def test_loop_materialized_durable_iterations(client, db, actors):
    value = definition(
        nodes=[
            node("loop", "for_each", items=[1, 2, 3], max_iterations=3),
            node("body", "set_variable", value="{{steps.loop.output.value}}"),
            node("done", "log_event", message="Done"),
        ],
        edges=[
            edge("start", "loop"),
            edge("loop", "body", "body"),
            edge("loop", "done", "done"),
        ],
    )
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row)
    drain(db)
    report = history(client, actors[0], run_id)
    assert report["execution"]["status"] == "completed", [
        (s["node_id"], s["status"], s["error"]) for s in report["steps"]
    ]
    bodies = [s for s in report["steps"] if s["original_node_id"] == "body"]
    assert len(bodies) == 3 and [s["output"]["value"] for s in bodies] == [1, 2, 3]
    assert (
        next(s for s in report["steps"] if s["node_id"] == "done")["status"]
        == "completed"
    )


def test_schedule_dst_and_numeric_cron():
    tz = timezone.utc
    gap = next_occurrence(
        {"mode": "daily", "hour": 2, "minute": 30, "timezone": "America/New_York"},
        datetime(2026, 3, 8, 6, tzinfo=tz),
    )
    assert gap == datetime(2026, 3, 9, 6, 30, tzinfo=tz)
    fold = next_occurrence(
        {"mode": "daily", "hour": 1, "minute": 30, "timezone": "America/New_York"},
        datetime(2026, 11, 1, 5, 31, tzinfo=tz),
    )
    assert fold == datetime(2026, 11, 2, 6, 30, tzinfo=tz)
    cron = next_occurrence(
        {"mode": "cron", "cron": "*/15 9-17 * * 1-5", "timezone": "UTC"},
        datetime(2026, 10, 27, 9, 1, tzinfo=tz),
    )
    assert cron == datetime(2026, 10, 27, 9, 15, tzinfo=tz)


# New hardening tests exercise actual server-owned executor dispatch, never connector stubs.
def test_manual_schema_unsupported_nodes_and_bad_transitions(client, db, actors):
    row = publish(
        client,
        actors[0],
        policy={
            "input_schema": {
                "type": "object",
                "properties": {"amount": {"type": "number"}},
                "required": ["amount"],
            }
        },
    )
    bad = client.post(
        f"{ROOT}/{row['id']}/execute",
        headers=actors[0],
        json={"input": {"amount": "12"}, "idempotency_key": "invalid-input"},
    )
    assert bad.status_code == 422
    assert (
        client.post(
            f"{ROOT}/{row['id']}/runtime/publish",
            headers=actors[0],
            json={"expected_version": 1},
        ).status_code
        == 409
    )
    bad_graph = definition(
        nodes=[
            node(
                "email",
                "send_email",
                recipient="test@example.invalid",
                subject="Hello",
                template="x",
            )
        ],
        edges=[edge("start", "email")],
    )
    bad_graph["nodes"][1]["credential_reference"] = "private-ref"
    draft = create(client, actors[0], bad_graph)
    result = client.post(
        f"{ROOT}/{draft['id']}/runtime/validate",
        headers=actors[0],
        json={"expected_version": 1},
    )
    assert result.status_code == 422 and "executor" in result.text
    assert db.query(PowerExecution).count() == 0


def test_permanent_failure_dead_letter_safe_retry_and_error_route(client, db, actors):
    value = definition(
        nodes=[
            node("parse", "parse_json", value="not JSON"),
            node("log", "log_event", message="Parsed"),
        ],
        edges=[edge("start", "parse"), edge("parse", "log")],
    )
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row)
    drain(db)
    from app.apps.power_apps.runtime_models import AutomationDeadLetter

    assert db.get(PowerExecution, run_id).status == "failed"
    assert db.query(AutomationDeadLetter).count() == 1
    assert (
        db.query(Step).filter_by(node_id="parse", run_id=run_id).one().status
        == "failed"
    )
    result = client.post(
        f"/api/v1/power-apps/executions/{run_id}/retry", headers=actors[0]
    )
    assert result.status_code == 200, result.text
    drain(db)
    assert db.get(PowerExecution, run_id).status == "failed"
    assert db.query(Step).filter_by(node_id="parse", run_id=run_id).one().attempt == 2
    value["nodes"][1]["advanced"] = {"error_strategy": "branch"}
    value["nodes"].append(node("error", "error_handler", message="Handled"))
    value["edges"].append(edge("parse", "error", "error"))
    second = publish(client, actors[0], value)
    handled = run(client, actors[0], second)
    drain(db)
    report = history(client, actors[0], handled)
    assert report["execution"]["status"] == "completed"
    assert (
        next(s for s in report["steps"] if s["node_id"] == "error")["status"]
        == "completed"
    )
    assert (
        next(s for s in report["steps"] if s["node_id"] == "log")["status"] == "skipped"
    )


def test_authorized_event_wait_resume_and_timeout(client, db, actors):
    future = (now() + timedelta(hours=1)).isoformat()
    value = definition(
        nodes=[
            node("wait", "wait_until", until=future, event_key="approval-contract-123"),
            node("log", "log_event", message="Resumed"),
        ],
        edges=[edge("start", "wait"), edge("wait", "log")],
    )
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row)
    drain(db)
    assert db.get(PowerExecution, run_id).status == "waiting"
    path = f"/api/v1/power-apps/executions/{run_id}/resume"
    assert (
        client.post(
            path, headers=actors[1], json={"event_key": "approval-contract-123"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            path, headers=actors[0], json={"event_key": "wrong-event-key"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            path, headers=actors[0], json={"event_key": "approval-contract-123"}
        ).status_code
        == 200
    )
    assert tick(db) == 1
    drain(db)
    assert db.get(PowerExecution, run_id).status == "completed"
    other = run(client, actors[0], row, "timeout-request-123")
    drain(db)
    wait = db.query(Wait).filter_by(run_id=other).one()
    wait.wake_at = now() - timedelta(seconds=1)
    db.commit()
    tick(db)
    assert (
        db.get(PowerExecution, other).status == "failed"
        and db.get(Run, other).error_type == "WaitEventTimeout"
    )


def test_nested_and_bounded_parallel_loops(client, db, actors):
    value = definition(
        nodes=[
            node(
                "outer",
                "for_each",
                items=[1, 2],
                max_iterations=2,
                mode="bounded_parallel",
                concurrency=2,
            ),
            node("inner", "loop", max_iterations=2),
            node("body", "set_variable", value="{{steps.inner.output.value}}"),
            node("inner_done", "log_event", message="Inner done"),
            node("done", "log_event", message="Done"),
        ],
        edges=[
            edge("start", "outer"),
            edge("outer", "inner", "body"),
            edge("inner", "body", "body"),
            edge("inner", "inner_done", "done"),
            edge("outer", "done", "done"),
        ],
    )
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row)
    drain(db)
    report = history(client, actors[0], run_id)
    assert report["execution"]["status"] == "completed", [
        (s["node_id"], s["status"], s["error"]) for s in report["steps"]
    ]
    assert len([s for s in report["steps"] if s["original_node_id"] == "body"]) == 4


def test_revoke_execute_permission_and_no_mutable_published_snapshot(
    client, db, actors
):
    row = publish(client, actors[0])
    run_id = run(client, actors[0], row)
    deployment = db.query(Deployment).one()
    version = db.get(PowerVersion, deployment.version_id)
    with pytest.raises(ValueError, match="immutable"):
        with db.begin_nested():
            version.snapshot = {**version.snapshot, "name": "Tampered"}
            db.flush()
    from app.models.user import User

    actor = db.get(User, db.get(PowerExecution, run_id).actor_user_id)
    actor.role.permissions = [
        p for p in actor.role.permissions if p.name != "power_apps_execute"
    ]
    db.commit()
    drain(db)
    assert db.get(PowerExecution, run_id).status == "failed"


def test_retention_sanitizes_payloads_without_deleting_history(client, db, actors):
    row = publish(client, actors[0])
    run_id = run(client, actors[0], row)
    drain(db)
    state = db.get(Run, run_id)
    state.finished_at = now() - timedelta(days=31)
    db.commit()
    from app.apps.power_apps.runtime_retention import purge_payloads

    assert purge_payloads(db) == 1
    assert (
        db.get(Run, run_id).input_payload == {}
        and db.get(Run, run_id).payloads_purged_at
    )
    assert all(s.output is None for s in db.query(Step).filter_by(run_id=run_id))
    assert history(client, actors[0], run_id)["execution"]["status"] == "completed"
    assert purge_payloads(db) == 0


def test_managed_service_identity_revalidates_current_policy(client, db, actors):
    from app.models.user import User, Role
    from app.common.models import CommonPerson
    from app.access.models import AccessPolicy

    owner = db.query(User).filter_by(email="power-0@example.com").one()
    role = Role(name="scoped_power_runtime_service", permissions=owner.role.permissions)
    db.add(role)
    db.flush()
    service = User(
        email="runtime-service@example.invalid",
        hashed_password="unused",
        is_active=True,
        role=role,
        person=CommonPerson(
            organization_id=1,
            primary_email="runtime-service@example.invalid",
            display_name="Runtime scoped service",
        ),
    )
    db.add(service)
    db.flush()
    policy = AccessPolicy(
        user_id=service.id,
        company_id=1,
        status="active",
        grants={
            "power_apps": {
                "enabled": True,
                "permissions": ["power_apps_view", "power_apps_execute"],
                "actions": ["view", "create"],
                "scope": "organization",
                "role": "service",
            }
        },
    )
    db.add(policy)
    db.commit()
    row = publish(
        client, actors[0], policy={"identity": "service", "service_user_id": service.id}
    )
    run_id = run(client, actors[0], row)
    drain(db)
    assert (
        db.get(PowerExecution, run_id).status == "completed"
        and db.get(Run, run_id).effective_user_id == service.id
    )
    other = run(client, actors[0], row, "service-revocation-123")
    policy.status = "suspended"
    db.commit()
    drain(db)
    assert (
        db.get(PowerExecution, other).status == "failed"
        and db.get(Run, other).error_type == "AuthorizationRevoked"
    )


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "properties": []},
        {"type": "array", "items": {"type": "string"}, "maxItems": "100"},
        {"type": "object", "required": ["missing"]},
        {"type": "object", "additionalProperties": {"$ref": "http://example.invalid"}},
        {"type": "string", "enum": "x"},
    ],
)
def test_input_schema_rejects_unsafe_and_malformed_contracts(schema):
    from app.apps.power_apps.runtime_triggers import validate_schema

    with pytest.raises(ValueError):
        validate_schema(schema)


def test_loop_deadline_and_expansion_guards(client, db, actors):
    value = definition(
        nodes=[
            node("loop", "loop", max_iterations=2),
            node("body", "delay", seconds=300),
            node("done", "log_event", message="Done"),
        ],
        edges=[
            edge("start", "loop"),
            edge("loop", "body", "body"),
            edge("loop", "done", "done"),
        ],
    )
    value["nodes"][1]["advanced"] = {"timeout_seconds": 10}
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row)
    drain(db)
    deadline = db.query(Wait).filter_by(run_id=run_id, kind="loop_timeout").one()
    deadline.wake_at = now() - timedelta(seconds=1)
    db.commit()
    tick(db)
    assert (
        db.get(PowerExecution, run_id).status == "failed"
        and db.get(Run, run_id).error_type == "LoopTimeout"
    )
    value["nodes"][1]["config"]["max_iterations"] = 1000
    for i in range(5):
        key = f"extra_{i}"
        value["nodes"].append(node(key, "set_variable", value=1))
        previous = "body" if i == 0 else f"extra_{i-1}"
        value["edges"].append(edge(previous, key))
    draft = create(client, actors[0], value)
    rejected = client.post(
        f"{ROOT}/{draft['id']}/runtime/validate",
        headers=actors[0],
        json={"expected_version": 1},
    )
    assert rejected.status_code == 422 and "5000" in rejected.text


def test_first_successful_join_tolerates_failed_sibling(client, db, actors):
    value = definition(
        nodes=[
            node("fork", "parallel_branch"),
            node("bad", "parse_json", value="broken JSON"),
            node("good", "set_variable", value=12),
            node("join", "merge", strategy="first_successful"),
        ],
        edges=[
            edge("start", "fork"),
            edge("fork", "bad", "route_1"),
            edge("fork", "good", "route_2"),
            edge("bad", "join"),
            edge("good", "join"),
        ],
    )
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row)
    drain(db)
    report = history(client, actors[0], run_id)
    assert report["execution"]["status"] == "completed"
    assert next(s for s in report["steps"] if s["node_id"] == "join")["output"][
        "value"
    ] == [{"value": 12}]


def test_webhook_policy_requires_explicit_delegation_and_provider_registration(
    client, db, actors
):
    row = publish(
        client, actors[0], definition("webhook_trigger", event_name="isolated")
    )
    response = client.put(
        f"{ROOT}/{row['id']}/triggers/webhook",
        headers=actors[0],
        json={
            "enabled": True,
            "config": {"schema": {"type": "object", "properties": {}}},
        },
    )
    assert response.status_code == 422
    # Internal providers cannot be created by client JSON.
    response = client.put(
        f"{ROOT}/{row['id']}/triggers/internal",
        headers=actors[0],
        json={
            "enabled": False,
            "config": {
                "provider": "pms",
                "event": "task.created",
                "schema": {"type": "object", "properties": {}},
            },
        },
    )
    assert response.status_code == 422


def test_worker_health_uses_actual_internal_liveness(client, db, actors):
    from app.apps.power_apps.runtime_models import AutomationWorker

    db.add(
        AutomationWorker(
            id="health-worker",
            status="running",
            heartbeat_at=now(),
            scheduler_at=now(),
            processed=0,
        )
    )
    db.commit()
    response = client.get("/api/v1/power-apps/runtime/health", headers=actors[0])
    assert response.status_code == 200, response.text
    assert (
        response.json()["workers_alive"] == 1 and response.json()["scheduler_last_at"]
    )
    worker = db.get(AutomationWorker, "health-worker")
    worker.status = "stopped"
    db.commit()
    assert (
        client.get("/api/v1/power-apps/runtime/health", headers=actors[0]).json()[
            "workers_alive"
        ]
        == 0
    )


def test_fair_dispatch_does_not_starve_another_tenant(client, db, actors):
    first = publish(client, actors[0])
    second = publish(client, actors[1])
    for i in range(3):
        run(client, actors[0], first, f"busy-tenant-{i:08}")
    other = run(client, actors[1], second, "other-tenant-0001")
    work_a = claim(db, "fair-worker-a")
    assert work_a
    work_b = claim(db, "fair-worker-b")
    assert work_b
    assert db.get(Job, work_b[0]).run_id == other
    process(db, *work_a)
    process(db, *work_b)
    drain(db)
    assert db.get(PowerExecution, other).status == "completed"


def test_secret_shaped_variables_cannot_enter_runtime_history(client, db, actors):
    value = definition()
    value["variables"] = {"sample": "sk-" + ("x" * 30)}
    row = create(client, actors[0], value)
    response = client.post(
        f"{ROOT}/{row['id']}/runtime/validate",
        headers=actors[0],
        json={"expected_version": 1},
    )
    assert response.status_code == 422 and "Secret" in response.text
    assert db.query(Run).count() == 0


@pytest.mark.parametrize(
    "data",
    [
        {"password": "no-inline-secrets"},
        {"value": "bad\x00text"},
        {"__proto__": {"polluted": True}},
    ],
)
def test_invalid_execution_input_is_rejected_without_a_server_error(
    client, db, actors, data
):
    row = publish(client, actors[0])
    response = client.post(
        f"{ROOT}/{row['id']}/execute",
        headers=actors[0],
        json={"input": data, "idempotency_key": "invalid-request-123"},
    )
    assert response.status_code == 422, response.text
    assert db.query(Run).count() == 0


def test_legacy_drafts_require_visual_save_before_runtime_validation(
    client, db, actors
):
    response = client.post(
        ROOT, headers=actors[0], json={"name": "Retained legacy draft"}
    )
    assert response.status_code == 201, response.text
    row = response.json()
    checked = client.post(
        f"{ROOT}/{row['id']}/runtime/validate",
        headers=actors[0],
        json={"expected_version": row["version"]},
    )
    assert checked.status_code == 422
    assert (
        client.get(f"{ROOT}/{row['id']}", headers=actors[0]).json()["definition"]
        == row["definition"]
    )


def test_export_requires_current_module_export_authority(client, db, actors):
    from app.models.user import User
    from app.access.models import AccessPolicy

    row = publish(client, actors[0])
    run_id = run(client, actors[0], row)
    drain(db)
    report = client.get(
        f"/api/v1/power-apps/executions/{run_id}/export", headers=actors[0]
    )
    assert report.status_code == 200, report.text
    assert report.json()["can_export"] is True
    user = db.get(User, db.get(PowerExecution, run_id).owner_user_id)
    from app.apps.power_apps.registry import PERMISSIONS

    db.add(
        AccessPolicy(
            user_id=user.id,
            company_id=1,
            status="active",
            grants={
                "power_apps": {
                    "enabled": True,
                    "permissions": list(PERMISSIONS),
                    "actions": ["view", "create", "configure"],
                    "scope": "own",
                    "role": "restricted_export",
                }
            },
        )
    )
    db.commit()
    current = history(client, actors[0], run_id)
    assert current["can_export"] is False
    assert (
        client.get(
            f"/api/v1/power-apps/executions/{run_id}/export", headers=actors[0]
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "path",
    [
        "/automations/1/runtime/publish",
        "/automations/1/runtime-limits",
        "/automations/1/triggers/scheduled",
        "/automations/1/triggers/webhook/rotate",
    ],
)
def test_runtime_configuration_actions_use_configuration_policy(path):
    from types import SimpleNamespace
    from app.access.catalog import action_for

    request = SimpleNamespace(
        url=SimpleNamespace(path="/api/v1/power-apps" + path),
        method="PUT" if path.endswith(("limits", "scheduled")) else "POST",
    )
    assert action_for(request) == "configure"


def test_variable_budget_rolls_back_failed_checkpoint(client, db, actors):
    value = definition(
        nodes=[
            node("first", "set_variable", name="alpha", value="x" * 30000),
            node("second", "set_variable", name="beta", value="x" * 30000),
            node("third", "set_variable", name="gamma", value="x" * 30000),
        ],
        edges=[
            edge("start", "first"),
            edge("first", "second"),
            edge("second", "third"),
        ],
    )
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row)
    drain(db)
    assert db.get(PowerExecution, run_id).status == "failed"
    assert set(db.get(Run, run_id).variables) == {"alpha", "beta"}
    assert db.query(Step).filter_by(run_id=run_id, node_id="third").one().output is None


def test_aggregate_output_budget_is_enforced_transactionally(
    client, db, actors, monkeypatch
):
    import app.apps.power_apps.runtime as runtime

    monkeypatch.setattr(runtime, "MAX_RUN_OUTPUT_BYTES", 80000)
    value = definition(
        nodes=[
            node("first", "set_variable", value="{{trigger.input.content}}"),
            node("second", "set_variable", value="{{trigger.input.content}}"),
            node("third", "set_variable", value="{{trigger.input.content}}"),
        ],
        edges=[
            edge("start", "first"),
            edge("first", "second"),
            edge("second", "third"),
        ],
    )
    row = publish(client, actors[0], value)
    run_id = run(client, actors[0], row, data={"content": "x" * 30000})
    drain(db)
    assert db.get(PowerExecution, run_id).status == "failed"
    assert (
        sum(
            len(json.dumps(s.output))
            for s in db.query(Step).filter_by(run_id=run_id)
            if s.output is not None
        )
        <= 80000
    )


def test_secret_shaped_idempotency_key_is_never_persisted(client, db, actors):
    row = publish(client, actors[0])
    response = client.post(
        f"{ROOT}/{row['id']}/execute",
        headers=actors[0],
        json={"input": {}, "idempotency_key": "sk-" + ("x" * 30)},
    )
    assert response.status_code == 422 and db.query(PowerExecution).count() == 0


def test_variable_names_are_literal_for_branch_race_validation(client, db, actors):
    value = definition()
    value["nodes"][1]["mappings"] = {
        "name": {"constant": "alpha", "target_type": "string"}
    }
    row = create(client, actors[0], value)
    response = client.post(
        f"{ROOT}/{row['id']}/runtime/validate",
        headers=actors[0],
        json={"expected_version": 1},
    )
    assert response.status_code == 422 and "literal" in response.text


def test_parallel_loop_shared_writes_require_sequential_mode():
    from app.apps.power_apps.runtime import validate_runtime

    value = definition(
        nodes=[
            node(
                "loop",
                "for_each",
                items=[1, 2],
                max_iterations=2,
                mode="bounded_parallel",
                concurrency=2,
            ),
            node("body", "set_variable", name="counter", value=1),
            node("done", "log_event", message="Done"),
        ],
        edges=[
            edge("start", "loop"),
            edge("loop", "body", "body"),
            edge("loop", "done", "done"),
        ],
    )
    with pytest.raises(HTTPException) as failure:
        validate_runtime(value)
    assert failure.value.status_code == 422 and "sequential mode" in str(
        failure.value.detail
    )
    value["nodes"][1]["config"]["mode"] = "sequential"
    assert validate_runtime(value)
