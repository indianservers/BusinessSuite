import json
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from ai_test_utils import auth_headers
from app.ai_operator.models import OperatorApiLog, OperatorProvider, OperatorRun
from app.ai_operator.providers import cipher
from app.apps.project_management.models import PMSChecklistItem, PMSTask


@pytest.fixture(autouse=True)
def isolate_generic_http_audit(monkeypatch):
    from app.ai_agents.services.rate_limit import AiRateLimitService
    AiRateLimitService._hits.clear()  # Fixture DBs reuse numeric user IDs across tests.
    # Generic HTTP audit opens a production SessionLocal instead of get_db.
    # Keep this suite entirely on its isolated fixture DB. Operator audit/API
    # telemetry still run normally and are asserted by these tests.
    from app.core.middleware.audit import AuditLogMiddleware
    async def isolated_log(*args, **kwargs):
        return None
    monkeypatch.setattr(AuditLogMiddleware, "_log_request", isolated_log)


def setup_operator(client, db, provider="openai"):
    headers, user = auth_headers(client, db, email=f"operator-{uuid4().hex}@example.com",
        permissions=["ai_assistant", "settings_manage", "pms_manage_projects", "pms_manage_tasks"])
    p = client.post("/api/v1/project-management/projects", headers=headers, json={"name": "Operator", "project_key": "OP"})
    assert p.status_code == 200, p.text
    project = p.json()["id"]
    t = client.post(f"/api/v1/project-management/projects/{project}/tasks", headers=headers, json={"title": "Review", "task_key": "OP-1"})
    assert t.status_code == 200, t.text
    config = client.put(f"/api/v1/ai-operator/providers/{provider}", headers=headers, json={"model": "test-model",
        "api_key": "unit-test-secret-key", "enabled": True, "data_sharing_allowed": True, "input_price": 1, "output_price": 2})
    assert config.status_code == 200, config.text
    assert "unit-test-secret-key" not in config.text and "encrypted_key" not in config.text
    return headers, user, project, t.json()["id"]


def plan_for(task):
    return {"summary": "Raise priority and add QA", "clarification": None, "steps": [
        {"tool": "update_task", "task_id": task, "changes": {"priority": "High"}},
        {"tool": "add_checklist", "task_id": task, "title": "QA review"}]}


def mock_provider(monkeypatch, plan, *, status=200):
    from app.ai_operator import providers
    original = httpx.Client
    calls = []
    def handle(request):
        calls.append(request)
        if status != 200:
            return httpx.Response(status, json={"error": "unit-test-secret-key business content"})
        if request.url.host == "api.openai.com":
            data = {"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps(plan)}]}],
                "usage": {"input_tokens": 100, "output_tokens": 50}}
        elif request.url.host == "api.anthropic.com":
            data = {"stop_reason": "tool_use", "content": [{"type": "tool_use", "name": "submit_plan", "input": plan}], "usage": {"input_tokens": 100, "output_tokens": 50}}
        else:
            data = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(plan)}]}}],
                "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50}}
        return httpx.Response(200, json=data, headers={"x-request-id": "provider-request-1"})
    monkeypatch.setattr(providers.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    return calls


def preview(client, headers, project, task, provider="openai", **extra):
    return client.post("/api/v1/ai-operator/commands", headers=headers, json={"project_id": project, "task_ids": [task],
        "command": "Set priority High and add a QA checklist item", "provider": provider, "request_key": str(uuid4()), **extra})


@pytest.mark.parametrize("provider", ["openai", "gemini", "claude"])
def test_three_providers_preview_execute_replay_and_usage(client, db, monkeypatch, provider):
    headers, user, project, task = setup_operator(client, db, provider)
    calls = mock_provider(monkeypatch, plan_for(task))
    response = preview(client, headers, project, task, provider, input_mode="voice")
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "awaiting_approval", response.text
    assert db.get(PMSTask, task).priority != "High"
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0
    endpoint = f"/api/v1/ai-operator/runs/{run['id']}/approve"
    wrong = client.post(endpoint, headers=headers, json={"plan_hash": "0" * 64})
    assert wrong.status_code == 409
    for _ in range(2):
        result = client.post(endpoint, headers=headers, json={"plan_hash": run["plan_hash"]})
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "succeeded", result.text
        assert len(result.json()["result"]["receipts"]) == 2
    db.expire_all()
    assert db.get(PMSTask, task).priority == "High"
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 1
    log = db.query(OperatorApiLog).filter_by(run_id=run["id"]).one()
    assert log.input_tokens == 100 and log.output_tokens == 50 and log.estimated_cost == Decimal("0.00020000")
    assert log.provider_request_id == "provider-request-1"
    assert len(calls) == 1
    analytics = client.get("/api/v1/ai-operator/analytics", headers=headers)
    assert analytics.status_code == 200 and analytics.json()["groups"][0]["requests"] == 1
    assert "unit-test-secret-key" not in analytics.text
    row = db.query(OperatorProvider).filter_by(updated_by=user.id).one()
    assert row.encrypted_key != "unit-test-secret-key" and cipher().decrypt(row.encrypted_key.encode()).decode() == "unit-test-secret-key"


def test_duplicate_command_reuses_plan_and_conflicting_key_fails(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    calls = mock_provider(monkeypatch, plan_for(task))
    key = str(uuid4())
    first = preview(client, headers, project, task, request_key=key)
    second = preview(client, headers, project, task, request_key=key)
    assert first.json()["id"] == second.json()["id"] and len(calls) == 1
    changed = preview(client, headers, project, task, request_key=key, command="Different command")
    assert changed.status_code == 409


def test_model_cannot_expand_frozen_selection(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, plan_for(task + 10000))
    result = preview(client, headers, project, task)
    assert result.json()["status"] == "failed" and result.json()["approval_id"] is None
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0


def test_stale_preview_commits_no_effects(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, plan_for(task))
    run = preview(client, headers, project, task).json()
    changed = client.patch(f"/api/v1/project-management/tasks/{task}", headers=headers, json={"priority": "Urgent"})
    assert changed.status_code == 200
    result = client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve", headers=headers, json={"plan_hash": run["plan_hash"]})
    assert result.status_code == 200, result.text
    assert result.json()["error_code"] == "STALE_PLAN"
    db.expire_all()
    assert db.get(PMSTask, task).priority == "Urgent" and db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0


def test_later_step_failure_rolls_back_earlier_task_change(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, plan_for(task))
    run = preview(client, headers, project, task).json()
    from app.apps.project_management.api import router as pms
    def fail(*args, **kwargs):
        raise HTTPException(422, "Injected failure after first task write")
    monkeypatch.setattr(pms, "create_task_checklist_operation", fail)
    result = client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve", headers=headers, json={"plan_hash": run["plan_hash"]})
    assert result.json()["status"] == "failed", result.text
    db.expire_all()
    assert db.get(PMSTask, task).priority != "High"
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0


def test_cancelled_run_cannot_execute(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, plan_for(task))
    run = preview(client, headers, project, task).json()
    assert client.post(f"/api/v1/ai-operator/runs/{run['id']}/cancel", headers=headers).json()["status"] == "cancelled"
    result = client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve", headers=headers, json={"plan_hash": run["plan_hash"]})
    assert result.status_code == 400
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0


def test_provider_failures_are_logged_without_sensitive_error_body(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, None, status=429)
    result = preview(client, headers, project, task)
    assert result.json()["status"] == "failed" and result.json()["error_code"] == "PROVIDER_HTTP_429"
    log = db.query(OperatorApiLog).filter_by(run_id=result.json()["id"]).one()
    assert log.status == "failed" and log.http_status == 429 and log.input_tokens is None
    analytics = client.get("/api/v1/ai-operator/analytics", headers=headers)
    assert "unit-test-secret-key" not in analytics.text and "business content" not in analytics.text


def test_permissions_and_private_scope_isolation(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, plan_for(task))
    run = preview(client, headers, project, task).json()
    other, _ = auth_headers(client, db, email="other-operator@example.com", permissions=["ai_assistant"])
    assert client.get("/api/v1/ai-operator/providers", headers=other).json()["items"] == []
    assert client.get(f"/api/v1/ai-operator/runs/{run['id']}", headers=other).status_code == 404
    assert client.get("/api/v1/ai-operator/analytics", headers=other).status_code == 403
    assert client.put("/api/v1/ai-operator/providers/openai", headers=other, json={"model": "x", "api_key": "secret"}).status_code == 403
    assert preview(client, other, project, task).status_code in {403, 404}


def test_clarification_never_creates_approval(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, {"summary": "Ambiguous collaborator", "clarification": "Which Arun? Provide the email.", "steps": []})
    result = preview(client, headers, project, task)
    assert result.json()["status"] == "needs_clarification" and result.json()["approval_id"] is None


def test_invalid_model_output_is_a_failed_api_call(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, {"summary": "Injected", "steps": [{"tool": "delete_all", "task_id": task}]})
    result = preview(client, headers, project, task)
    assert result.json()["error_code"] == "PROVIDER_INVALID_OUTPUT"
    assert db.query(OperatorApiLog).filter_by(run_id=result.json()["id"]).one().status == "failed"


def test_assignment_checklist_and_sprint_use_canonical_operations(client, db, monkeypatch):
    headers, user, project, task = setup_operator(client, db)
    response = client.post(f"/api/v1/project-management/projects/{project}/sprints", headers=headers,
        json={"name": "Sprint 4", "start_date": "2026-10-26", "end_date": "2026-11-06"})
    assert response.status_code == 200, response.text
    sprint = response.json()["id"]
    plan = plan_for(task)
    plan["steps"][0]["changes"] = {"priority": "High", "assignee_user_ids": [user.id]}
    plan["steps"].append({"tool": "move_to_sprint", "task_id": task, "sprint_id": sprint})
    mock_provider(monkeypatch, plan)
    run = preview(client, headers, project, task).json()
    assert run["status"] == "awaiting_approval", run
    result = client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve", headers=headers, json={"plan_hash": run["plan_hash"]})
    assert result.json()["status"] == "succeeded", result.text
    db.expire_all()
    record = db.get(PMSTask, task)
    assert record.assignee_user_ids == [user.id] and record.assignee_user_id == user.id and record.sprint_id == sprint


def test_provider_settings_scope_and_key_rotation(client, db):
    headers, user, _, _ = setup_operator(client, db)
    created = client.post("/api/v1/project-management/workspaces", headers=headers, json={"name": "Provider workspace"})
    assert created.status_code == 201, created.text
    workspace = created.json()["id"]
    endpoint = f"/api/v1/ai-operator/providers/claude?workspace_id={workspace}"
    saved = client.put(endpoint, headers=headers, json={"model": "configured-model", "api_key": "workspace-only-key"})
    assert saved.status_code == 200
    row = db.query(OperatorProvider).filter_by(scope_key=f"workspace:{workspace}", provider="claude").one()
    encrypted = row.encrypted_key
    assert client.put(endpoint, headers=headers, json={"model": "another-model"}).status_code == 200
    db.refresh(row)
    assert row.encrypted_key == encrypted
    assert client.put(endpoint, headers=headers, json={"model": "another-model", "api_key": "rotated-key"}).status_code == 200
    db.refresh(row)
    assert cipher().decrypt(row.encrypted_key.encode()).decode() == "rotated-key"
    outsider, _ = auth_headers(client, db, email="scope-outsider@example.com", permissions=["settings_manage", "ai_assistant"])
    assert client.get(f"/api/v1/ai-operator/providers?workspace_id={workspace}", headers=outsider).status_code == 404
    assert client.put(endpoint, headers=outsider, json={"model": "x", "api_key": "bad"}).status_code == 404


def test_emergency_disable_prevents_execution(client, db, monkeypatch):
    from app.ai_agents.models import AiSecuritySetting
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, plan_for(task))
    run = preview(client, headers, project, task).json()
    setting = db.query(AiSecuritySetting).filter_by(company_id=None).one()
    setting.pms_ai_enabled = False
    db.commit()
    response = client.post(f"/api/v1/ai-operator/runs/{run['id']}/approve", headers=headers, json={"plan_hash": run["plan_hash"]})
    assert response.status_code == 403
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 0


def test_shared_approval_rejection_checks_owner_and_cancels_run(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, plan_for(task))
    run = preview(client, headers, project, task).json()
    outsider, _ = auth_headers(client, db, email="approval-outsider@example.com", permissions=["ai_assistant"])
    endpoint = f"/api/v1/ai-agents/approvals/{run['approval_id']}/reject"
    assert client.post(endpoint, headers=outsider, json={"rejected_reason": "Declined"}).status_code == 403
    assert client.post(endpoint, headers=headers, json={"rejected_reason": "Declined"}).status_code == 200
    db.expire_all()
    assert db.get(OperatorRun, run["id"]).status == "cancelled"


def test_existing_approval_endpoint_executes_the_operator_plan(client, db, monkeypatch):
    headers, _, project, task = setup_operator(client, db)
    mock_provider(monkeypatch, plan_for(task))
    run = preview(client, headers, project, task).json()
    response = client.post(f"/api/v1/ai-agents/approvals/{run['approval_id']}/approve", headers=headers)
    assert response.status_code == 200 and response.json()["execution_status"] == "executed", response.text
    db.expire_all()
    assert db.get(OperatorRun, run["id"]).status == "succeeded"
    assert db.query(PMSChecklistItem).filter_by(task_id=task).count() == 1
