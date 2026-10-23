from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_ai_operator import setup_operator, mock_provider, plan_for, preview, isolate_generic_http_audit  # noqa: F401
from app.ai_operator.models import OperatorRun, OperatorJob, OperatorStep, OperatorEvent, OperatorApiLog
from app.ai_operator.jobs import claim, process_claim, process_batch, now_utc
from app.apps.project_management.models import PMSTask, PMSChecklistItem, PMSTaskDependency


def queued_plan(client, db, monkeypatch, *, execution_mode="checkpointed"):
    headers, user, project, task = setup_operator(client, db)
    calls = mock_provider(monkeypatch, plan_for(task))
    response = preview(client, headers, project, task, background=True, execution_mode=execution_mode)
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "queued_planning" and len(calls) == 0
    assert process_batch(db, limit=1) == {"processed": 1}
    run = client.get(f"/api/v1/ai-operator/runs/{run['id']}", headers=headers).json()
    assert run["status"] == "awaiting_approval", run
    return headers, user, project, task, run, calls


def approve(client, headers, run):
    response = client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve", headers=headers, json={"plan_hash": run["plan_hash"]})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"


@pytest.mark.parametrize("execution_mode", ["atomic", "checkpointed"])
def test_background_work_uses_durable_queue_and_after_commit_events(client, db, monkeypatch, execution_mode):
    headers, _, _, task, run, calls = queued_plan(client, db, monkeypatch, execution_mode=execution_mode)
    approve(client, headers, run)
    approve(client, headers, run)  # Duplicate human approval queues just one job.
    assert db.query(OperatorJob).filter_by(run_id=run["id"], kind="execute").count() == 1
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0
    process_batch(db, limit=5)
    db.expire_all()
    assert db.get(OperatorRun, run["id"]).status == "succeeded"
    assert db.get(PMSTask, task).priority == "High"
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 1
    assert len(calls) == 1
    steps = client.get(f"/api/v1/ai-operator/runs/{run['id']}/steps", headers=headers).json()["items"]
    assert len(steps) == 2 and all(s["status"] == "succeeded" for s in steps)
    assert steps[1]["depends_on"] == [1]
    events = client.get(f"/api/v1/ai-operator/runs/{run['id']}/events?limit=2", headers=headers).json()
    assert events["has_more"]
    later = client.get(f"/api/v1/ai-operator/runs/{run['id']}/events?after_id={events['next_cursor']}", headers=headers).json()
    assert all(e["id"] > events["next_cursor"] for e in later["items"])
    assert later["items"][-1]["type"] == "run.succeeded"


def test_expired_lease_resumes_without_duplicate_completed_step(client, db, monkeypatch):
    headers, _, _, task, run, _ = queued_plan(client, db, monkeypatch)
    approve(client, headers, run)
    process_batch(db, limit=1)  # First step committed; second pending.
    held = claim(db)
    assert held
    assert claim(db) is None  # Cannot claim a live lease.
    job = db.get(OperatorJob, held[0])
    job.lease_until = now_utc() - timedelta(seconds=1)
    db.commit()
    replacement = claim(db)
    assert replacement and replacement[1] != held[1]
    assert process_claim(db, *held) == "lost_lease"
    assert process_claim(db, *replacement) == "processed"
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 1
    assert db.query(OperatorStep).filter_by(run_id=run["id"], status="succeeded").count() == 2


def test_failed_checkpoint_preserves_completed_effects_and_resumes(client, db, monkeypatch):
    headers, _, _, task, run, _ = queued_plan(client, db, monkeypatch)
    approve(client, headers, run)
    process_batch(db, limit=1)
    from app.apps.project_management.api import router as pms
    original = pms.create_task_checklist_operation
    def fail(*args, **kwargs):
        raise HTTPException(422, "Validation changed")
    monkeypatch.setattr(pms, "create_task_checklist_operation", fail)
    process_batch(db, limit=1)
    db.expire_all()
    row = db.get(OperatorRun, run["id"])
    assert row.status == "paused" and len(row.result["receipts"]) == 1
    assert db.get(PMSTask, task).priority == "High"
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0
    monkeypatch.setattr(pms, "create_task_checklist_operation", original)
    resumed = client.post(f"/api/v1/ai-operator/runs/{row.id}/resume", headers=headers, json={"plan_hash": row.plan_hash})
    assert resumed.status_code == 200, resumed.text
    process_batch(db, limit=3)
    db.expire_all()
    assert db.get(OperatorRun, row.id).status == "succeeded"
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 1


def test_checkpoint_cancel_keeps_receipts_and_prevents_future_writes(client, db, monkeypatch):
    headers, _, _, task, run, _ = queued_plan(client, db, monkeypatch)
    approve(client, headers, run)
    process_batch(db, limit=1)
    cancelled = client.post(f"/api/v1/ai-operator/runs/{run['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert len(cancelled.json()["result"]["receipts"]) == 1
    process_batch(db)
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0
    assert client.post(f"/api/v1/ai-operator/runs/{run['id']}/resume", headers=headers, json={"plan_hash": run["plan_hash"]}).status_code == 409


def test_revision_invalidates_old_approval_and_preserves_context(client, db, monkeypatch):
    headers, _, _, task, run, calls = queued_plan(client, db, monkeypatch)
    body = {"command": "Only change the priority to High", "request_key": str(uuid4()), "plan_hash": run["plan_hash"]}
    child = client.post(f"/api/v1/ai-operator/runs/{run['id']}/revise", headers=headers, json=body)
    assert child.status_code == 200, child.text
    assert child.json()["parent_run_id"] == run["id"] and child.json()["revision"] == 2
    assert client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve", headers=headers, json={"plan_hash": run["plan_hash"]}).status_code == 409
    duplicate = client.post(f"/api/v1/ai-operator/runs/{run['id']}/revise", headers=headers, json=body)
    assert duplicate.status_code == 200 and duplicate.json()["id"] == child.json()["id"]
    process_batch(db, limit=1)
    assert len(calls) == 2
    import json
    request = json.loads(calls[-1].content)
    context = json.loads(request["input"])
    assert context["prior_turns_newest_first"][0]["command"] == run["command"]
    assert context["authorized_context"]["tasks"][0]["id"] == task
    assert db.get(OperatorRun, run["id"]).status == "superseded"


def test_stale_task_between_checkpoints_cannot_be_resumed(client, db, monkeypatch):
    headers, _, _, task, run, _ = queued_plan(client, db, monkeypatch)
    approve(client, headers, run)
    process_batch(db, limit=1)
    client.patch(f"/api/v1/project-management/tasks/{task}", headers=headers, json={"title": "Changed by another user"})
    process_batch(db, limit=1)
    row = db.get(OperatorRun, run["id"])
    assert row.status == "paused" and row.error_code == "STALE_PLAN"
    assert client.post(f"/api/v1/ai-operator/runs/{row.id}/resume", headers=headers, json={"plan_hash": row.plan_hash}).status_code == 409
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0


def test_provider_retry_budget_and_failed_attempt_telemetry(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    calls = mock_provider(monkeypatch, None, status=503)
    run = preview(client, headers, project, task, background=True).json()
    for _ in range(3):
        process_batch(db, limit=1)
        job = db.query(OperatorJob).filter_by(run_id=run["id"]).one()
        job.available_at = now_utc() - timedelta(seconds=1)
        db.commit()
    assert len(calls) == 3
    assert db.get(OperatorRun, run["id"]).status == "failed"
    assert db.query(OperatorApiLog).filter_by(run_id=run["id"], status="failed").count() == 3


def test_schedule_and_dependency_tools_and_cycle_validation(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    other = client.post(f"/api/v1/project-management/projects/{project}/tasks", headers=headers, json={"title": "QA", "task_key": "OP-2"}).json()["id"]
    plan = {"summary": "Schedule delivery then QA", "steps": [
        {"tool": "schedule_task", "task_id": task, "start_date": "2026-10-26", "due_date": "2026-10-27"},
        {"tool": "schedule_task", "task_id": other, "start_date": "2026-10-28", "due_date": "2026-10-29", "depends_on": [1]},
        {"tool": "add_dependency", "task_id": other, "source_task_id": task, "depends_on": [1, 2]}]}
    mock_provider(monkeypatch, plan)
    run = preview(client, headers, project, task, task_ids=[task, other], background=True).json()
    process_batch(db, limit=1)
    row = db.get(OperatorRun, run["id"])
    assert row.status == "awaiting_approval", row.error_code
    approve(client, headers, {"id": row.id, "plan_hash": row.plan_hash})
    process_batch(db, limit=2)
    assert db.get(OperatorRun, row.id).status == "succeeded"
    assert str(db.get(PMSTask, task).due_date) == "2026-10-27"
    assert db.query(PMSTaskDependency).filter_by(task_id=other, depends_on_task_id=task).count() == 1


def test_revoked_permissions_pause_worker_and_events_are_private(client, db, monkeypatch):
    headers, user, _, task, run, _ = queued_plan(client, db, monkeypatch)
    approve(client, headers, run)
    user.role.permissions = [p for p in user.role.permissions if p.name != "ai_assistant" and p.name != "settings_manage"]
    db.commit()
    process_batch(db, limit=1)
    assert db.get(OperatorRun, run["id"]).status == "paused"
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0
    assert client.get(f"/api/v1/ai-operator/runs/{run['id']}/events", headers=headers).status_code == 403


def test_cancel_queued_planning_never_calls_provider(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    calls = mock_provider(monkeypatch, plan_for(task))
    run = preview(client, headers, project, task, background=True).json()
    client.post(f"/api/v1/ai-operator/runs/{run['id']}/cancel", headers=headers)
    process_batch(db)
    assert not calls
    assert db.get(OperatorRun, run["id"]).status == "cancelled"


@pytest.mark.parametrize("include_source", [True, False])
def test_cycle_and_out_of_selection_dependencies_cannot_be_approved(client, db, monkeypatch, include_source):
    headers, _, project, task = setup_operator(client, db)
    other = client.post(f"/api/v1/project-management/projects/{project}/tasks", headers=headers, json={"title": "QA", "task_key": "OP-2"}).json()["id"]
    plan = {"summary": "Cycle", "steps": [{"tool": "add_dependency", "task_id": task, "source_task_id": other},
        {"tool": "add_dependency", "task_id": other, "source_task_id": task}]}
    mock_provider(monkeypatch, plan)
    run = preview(client, headers, project, task, task_ids=[task, other] if include_source else [task], background=True).json()
    process_batch(db, limit=1)
    row = db.get(OperatorRun, run["id"])
    assert row.status == "failed" and row.approval_id is None
    assert db.query(PMSTaskDependency).count() == 0


def test_permanent_provider_error_does_not_retry(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    calls = mock_provider(monkeypatch, None, status=401)
    run = preview(client, headers, project, task, background=True).json()
    process_batch(db, limit=3)
    assert len(calls) == 1
    assert db.get(OperatorRun, run["id"]).status == "failed"


def test_checkpoint_rechecks_dates_of_linked_tasks_outside_selection(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    other = client.post(f"/api/v1/project-management/projects/{project}/tasks", headers=headers, json={"title": "Blocker", "task_key": "OP-2"}).json()["id"]
    dependency = client.post("/api/v1/project-management/task-dependencies", headers=headers,
        json={"source_task_id": other, "target_task_id": task})
    assert dependency.status_code == 201
    mock_provider(monkeypatch, plan_for(task))
    run = preview(client, headers, project, task, background=True, execution_mode="checkpointed").json()
    process_batch(db, limit=1)
    row = db.get(OperatorRun, run["id"])
    approve(client, headers, {"id": row.id, "plan_hash": row.plan_hash})
    process_batch(db, limit=1)
    assert client.patch(f"/api/v1/project-management/tasks/{other}/schedule", headers=headers,
        json={"due_date": "2026-11-12"}).status_code == 200
    process_batch(db, limit=1)
    db.expire_all()
    assert db.get(OperatorRun, run["id"]).error_code == "STALE_PLAN"
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0


def test_job_events_and_revisions_deny_other_users(client, db, monkeypatch):
    from ai_test_utils import auth_headers
    headers, _, _, _, run, _ = queued_plan(client, db, monkeypatch)
    other, _ = auth_headers(client, db, email="other-job-user@example.com", permissions=["ai_assistant", "pms_manage_tasks"])
    for suffix in ("events", "steps"):
        assert client.get(f"/api/v1/ai-operator/runs/{run['id']}/{suffix}", headers=other).status_code == 404
    assert client.post(f"/api/v1/ai-operator/runs/{run['id']}/revise", headers=other,
        json={"command": "Assign to me", "request_key": str(uuid4()), "plan_hash": run["plan_hash"]}).status_code == 404


def test_background_job_migration_preserves_old_runs_and_is_repeatable():
    import importlib.util
    from pathlib import Path
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    folder = Path(__file__).resolve().parents[1] / "alembic_postgresql/versions"
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        for name in ("users", "pms_projects", "ai_action_approvals"):
            connection.exec_driver_sql(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)")
        migrations = []
        for name in ("pg_20261023_009_ai_operator.py", "pg_20261024_001_operator_jobs.py"):
            spec = importlib.util.spec_from_file_location(name, folder / name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            migrations.append(module)
        with Operations.context(MigrationContext.configure(connection)):
            migrations[0].upgrade()
            connection.exec_driver_sql("INSERT INTO ai_operator_runs (id, scope_key, user_id, project_id, request_key, request_hash, command, input_mode, provider, status, selection, snapshots) VALUES (42, 'user:1', 1, 1, 'key', 'hash', 'Command', 'text', 'openai', 'planning', '[]', '{}')")
            migrations[1].upgrade()
            migrations[1].upgrade()
        assert connection.exec_driver_sql("SELECT revision, execution_mode, background FROM ai_operator_runs WHERE id=42").one() == (1, "atomic", 0)
        assert sa.inspect(connection).has_table("ai_operator_steps")
    engine.dispose()
