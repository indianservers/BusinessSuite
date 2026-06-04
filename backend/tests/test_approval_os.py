from datetime import datetime, timedelta, timezone

from app.core.security import get_password_hash
from app.models.approval_os import ApprovalHistory
from app.models.notification import Notification
from app.models.user import Role, User
from app.models.workflow_engine import WorkflowDefinition, WorkflowInstance, WorkflowStepDefinition, WorkflowTask


def _login(client, email: str, password: str = "Password@123") -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _user(db, email: str, role_name: str) -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=role_name, is_system=True)
        db.add(role)
        db.flush()
    user = User(
        email=email,
        hashed_password=get_password_hash("Password@123"),
        is_active=True,
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_approval_os_create_inbox_decide_history_and_notification(client, db, superuser_headers):
    approver = _user(db, "manager-approval-os@test.com", "manager")

    due_at = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    created = client.post(
        "/api/v1/approval-os/requests",
        headers=superuser_headers,
        json={
            "source_module": "crm",
            "approval_type": "Quote Approval",
            "entity_type": "quote",
            "entity_id": 42,
            "title": "Approve BrightPath quote",
            "description": "Discount and margin review",
            "assigned_role": "manager",
            "priority": "High",
            "sla_due_at": due_at,
            "ai_summary": "AI summary: margin is acceptable but discount is above policy.",
            "context_json": {"amount": 250000, "discount": 12},
        },
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert db.query(Notification).filter_by(event_type="approval_os_pending").count() == 0

    manager_headers = _login(client, approver.email)
    inbox = client.get("/api/v1/approval-os/inbox", headers=manager_headers)
    assert inbox.status_code == 200, inbox.text
    assert inbox.json()["summary"]["pending"] == 1
    assert inbox.json()["summary"]["high_priority"] == 1
    item = inbox.json()["items"][0]
    assert item["id"] == f"approval:{request_id}"
    assert item["can_decide"] is True
    assert item["ai_summary"].startswith("AI summary")

    approved = client.put(
        f"/api/v1/approval-os/requests/{request_id}/approve",
        headers=manager_headers,
        json={"reason": "Margin accepted"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "Approved"
    assert approved.json()["decision_reason"] == "Margin accepted"

    history = client.get(f"/api/v1/approval-os/requests/{request_id}/history", headers=manager_headers)
    assert history.status_code == 200
    events = [row["event_type"] for row in history.json()]
    assert events == ["created", "approved"]
    assert db.query(ApprovalHistory).filter_by(request_id=request_id).count() == 2


def test_approval_os_aggregates_workflow_engine_tasks(client, db, superuser_headers):
    approver = _user(db, "workflow-approval-os@test.com", "manager")
    definition = WorkflowDefinition(name="Timesheet workflow", module="pms", trigger_event="timesheet_submitted", created_by=approver.id)
    db.add(definition)
    db.flush()
    instance = WorkflowInstance(
        workflow_id=definition.id,
        module="pms",
        entity_type="timesheet",
        entity_id=77,
        requester_user_id=approver.id,
        context_json={
            "title": "Timesheet approval for Sprint 24",
            "description": "Review billable delivery hours",
            "priority": "Normal",
            "ai_summary": "Hours match sprint allocation.",
        },
    )
    db.add(instance)
    db.flush()
    step = WorkflowStepDefinition(workflow_id=definition.id, step_order=1, step_type="Timesheet Approval", approver_type="Role", approver_value="manager")
    db.add(step)
    db.flush()
    db.add(WorkflowTask(instance_id=instance.id, step_definition_id=step.id, assigned_role="manager"))
    db.commit()

    manager_headers = _login(client, approver.email)
    inbox = client.get("/api/v1/approval-os/inbox", headers=manager_headers)
    assert inbox.status_code == 200, inbox.text
    items = inbox.json()["items"]
    assert any(item["id"].startswith("workflow:") and item["source_module"] == "pms" for item in items)
    workflow_item = next(item for item in items if item["id"].startswith("workflow:"))
    assert workflow_item["title"] == "Timesheet approval for Sprint 24"
    assert workflow_item["can_decide"] is True
