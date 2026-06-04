from app.db.init_db import init_db
from app.core.security import get_password_hash
from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveType
from app.models.user import Role, User
from datetime import date, datetime, timedelta, timezone


def _login(client, email="admin@aihrms.com", password="Admin@123456"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_workflow_conditions_escalations_and_reminders(client, db):
    init_db(db)
    admin_headers = _login(client)
    hr_user = db.query(User).filter(User.email == "hr@aihrms.com").first()

    definition = client.post(
        "/api/v1/workflow-engine/definitions",
        json={
            "name": "High Value Payroll Approval",
            "module": "payroll",
            "trigger_event": "submitted",
            "steps": [
                {
                    "step_order": 1,
                    "approver_type": "Role",
                    "approver_value": "super_admin",
                    "condition_expression": "amount >= 100000",
                    "timeout_hours": -1,
                    "escalation_user_id": hr_user.id,
                },
                {
                    "step_order": 2,
                    "approver_type": "Role",
                    "approver_value": "hr_manager",
                    "condition_expression": "requires_hr == true",
                },
            ],
        },
        headers=admin_headers,
    )
    assert definition.status_code == 201

    skipped = client.post(
        "/api/v1/workflow-engine/instances",
        json={
            "workflow_id": definition.json()["id"],
            "module": "payroll",
            "entity_type": "payroll_run",
            "entity_id": 1,
            "context_json": {"amount": 50000, "requires_hr": "false"},
        },
        headers=admin_headers,
    )
    assert skipped.status_code == 201
    assert skipped.json()["status"] == "Approved"

    instance = client.post(
        "/api/v1/workflow-engine/instances",
        json={
            "workflow_id": definition.json()["id"],
            "module": "payroll",
            "entity_type": "payroll_run",
            "entity_id": 2,
            "context_json": {"amount": 150000, "requires_hr": "true"},
        },
        headers=admin_headers,
    )
    assert instance.status_code == 201
    assert instance.json()["status"] == "Pending"

    reminders = client.post("/api/v1/workflow-engine/tasks/send-reminders", headers=admin_headers)
    assert reminders.status_code == 200
    assert reminders.json()[0]["reminder_sent_at"] is not None

    escalated = client.post("/api/v1/workflow-engine/tasks/process-escalations", headers=admin_headers)
    assert escalated.status_code == 200
    assert escalated.json()[0]["escalated_to_user_id"] == hr_user.id

    hr_headers = _login(client, "hr@aihrms.com", "HR@123456")
    first_tasks = client.get("/api/v1/workflow-engine/tasks", headers=hr_headers)
    assert first_tasks.status_code == 200
    assert any(item["instance_id"] == instance.json()["id"] for item in first_tasks.json())

    first_task_id = next(item["id"] for item in first_tasks.json() if item["instance_id"] == instance.json()["id"])
    decided = client.put(
        f"/api/v1/workflow-engine/tasks/{first_task_id}/decision",
        json={"decision": "approve", "reason": "Amount verified"},
        headers=hr_headers,
    )
    assert decided.status_code == 200

    second_tasks = client.get("/api/v1/workflow-engine/tasks", headers=hr_headers)
    assert second_tasks.status_code == 200
    assert any(item["instance_id"] == instance.json()["id"] for item in second_tasks.json())


def _ensure_role(db, name: str) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        role = Role(name=name, description=name, is_system=False)
        db.add(role)
        db.flush()
    return role


def _ensure_user(db, email: str, role_name: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    role = _ensure_role(db, role_name)
    user = User(
        email=email,
        hashed_password=get_password_hash("User@123456"),
        is_active=True,
        role_id=role.id,
    )
    db.add(user)
    db.flush()
    return user


def _ensure_leave_request(db) -> LeaveRequest:
    employee = db.query(Employee).first()
    if not employee:
        employee = Employee(employee_id="WF-EMP-001", first_name="Workflow", last_name="Employee", date_of_joining=date(2024, 1, 1))
        db.add(employee)
        db.flush()
    leave_type = db.query(LeaveType).first()
    if not leave_type:
        leave_type = LeaveType(name="Workflow Test Leave", code="WFT", days_allowed=10)
        db.add(leave_type)
        db.flush()
    leave = LeaveRequest(
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 2),
        days_count=2,
        status="Pending",
        reason="Workflow action test",
    )
    db.add(leave)
    db.flush()
    return leave


def test_workflow_sequential_conditional_delegated_action_and_audit(client, db):
    init_db(db)
    admin_headers = _login(client)
    approver = _ensure_user(db, "workflow.approver@example.com", "workflow_approver")
    delegate = _ensure_user(db, "workflow.delegate@example.com", "workflow_delegate")
    leave = _ensure_leave_request(db)
    db.commit()

    starts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    ends = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    definition = client.post(
        "/api/v1/workflow-engine/definitions",
        json={
            "name": "Delegated Leave Approval",
            "module": "leave",
            "trigger_event": "submitted",
            "steps": [
                {
                    "step_order": 1,
                    "step_type": "approval",
                    "approver_type": "User",
                    "approver_value": str(approver.id),
                    "condition_expression": "leave_days >= 2 and department == 'Engineering'",
                    "delegation_type": "User",
                    "delegation_value": str(delegate.id),
                    "delegation_starts_at": starts,
                    "delegation_ends_at": ends,
                },
                {
                    "step_order": 2,
                    "step_type": "action",
                    "action_type": "field_update",
                    "action_config": {"target_module": "leave", "fields": {"status": "Approved", "review_remarks": "Workflow approved"}},
                },
            ],
        },
        headers=admin_headers,
    )
    assert definition.status_code == 201, definition.text

    instance = client.post(
        "/api/v1/workflow-engine/instances",
        json={
            "workflow_id": definition.json()["id"],
            "module": "leave",
            "entity_type": "leave_request",
            "entity_id": leave.id,
            "context_json": {"leave_days": 2, "department": "Engineering"},
        },
        headers=admin_headers,
    )
    assert instance.status_code == 201

    delegate_headers = _login(client, "workflow.delegate@example.com", "User@123456")
    tasks = client.get("/api/v1/workflow-engine/tasks", headers=delegate_headers)
    assert tasks.status_code == 200
    task = next(item for item in tasks.json() if item["instance_id"] == instance.json()["id"])
    assert task["assigned_to_user_id"] == delegate.id
    assert task["original_assigned_to_user_id"] == approver.id

    decision = client.put(
        f"/api/v1/workflow-engine/tasks/{task['id']}/decision",
        json={"decision": "approve", "reason": "Delegated approval"},
        headers=delegate_headers,
    )
    assert decision.status_code == 200
    db.refresh(leave)
    assert leave.status == "Approved"
    assert leave.review_remarks == "Workflow approved"

    audit = client.get(f"/api/v1/workflow-engine/instances/{instance.json()['id']}/audit", headers=admin_headers)
    assert audit.status_code == 200
    event_types = {event["event_type"] for event in audit.json()}
    assert {"instance_started", "task_created", "task_approved", "action_applied", "instance_completed"} <= event_types


def test_workflow_parallel_waits_for_all_approvals_and_escalates(client, db):
    init_db(db)
    admin_headers = _login(client)
    approver_one = _ensure_user(db, "workflow.parallel.one@example.com", "parallel_one")
    approver_two = _ensure_user(db, "workflow.parallel.two@example.com", "parallel_two")
    escalation = db.query(User).filter(User.email == "hr@aihrms.com").first()
    db.commit()

    definition = client.post(
        "/api/v1/workflow-engine/definitions",
        json={
            "name": "Parallel Expense Approval",
            "module": "expense",
            "trigger_event": "submitted",
            "steps": [
                {"step_order": 1, "step_type": "parallel", "approver_type": "User", "approver_value": str(approver_one.id), "timeout_hours": -1, "escalation_user_id": escalation.id},
                {"step_order": 1, "step_type": "parallel", "approver_type": "User", "approver_value": str(approver_two.id), "timeout_hours": -1, "escalation_user_id": escalation.id},
                {"step_order": 2, "step_type": "approval", "approver_type": "Role", "approver_value": "hr_manager"},
            ],
        },
        headers=admin_headers,
    )
    assert definition.status_code == 201
    instance = client.post(
        "/api/v1/workflow-engine/instances",
        json={"workflow_id": definition.json()["id"], "module": "expense", "entity_type": "expense_claim", "entity_id": 99, "context_json": {"amount": 2000}},
        headers=admin_headers,
    )
    assert instance.status_code == 201

    escalated = client.post("/api/v1/workflow-engine/tasks/process-escalations", headers=admin_headers)
    assert escalated.status_code == 200
    assert len([task for task in escalated.json() if task["instance_id"] == instance.json()["id"]]) == 2

    hr_headers = _login(client, "hr@aihrms.com", "HR@123456")
    hr_tasks = [task for task in client.get("/api/v1/workflow-engine/tasks", headers=hr_headers).json() if task["instance_id"] == instance.json()["id"]]
    assert len(hr_tasks) >= 2
    first = client.put(f"/api/v1/workflow-engine/tasks/{hr_tasks[0]['id']}/decision", json={"decision": "approve"}, headers=hr_headers)
    assert first.status_code == 200
    assert len([task for task in client.get("/api/v1/workflow-engine/tasks", headers=hr_headers).json() if task["instance_id"] == instance.json()["id"]]) >= 1
    second = client.put(f"/api/v1/workflow-engine/tasks/{hr_tasks[1]['id']}/decision", json={"decision": "approve"}, headers=hr_headers)
    assert second.status_code == 200
    next_tasks = client.get("/api/v1/workflow-engine/tasks", headers=hr_headers)
    assert any(task["instance_id"] == instance.json()["id"] and task["assigned_role"] == "hr_manager" for task in next_tasks.json())


def test_workflow_rejects_unsafe_condition_and_action_fields(client, db):
    init_db(db)
    admin_headers = _login(client)
    response = client.post(
        "/api/v1/workflow-engine/definitions",
        json={
            "name": "Unsafe Workflow",
            "module": "leave",
            "trigger_event": "submitted",
            "steps": [{"step_order": 1, "condition_expression": "__import__ == 'os'", "approver_type": "Role", "approver_value": "hr_manager"}],
        },
        headers=admin_headers,
    )
    assert response.status_code == 400

    action = client.post(
        "/api/v1/workflow-engine/definitions",
        json={
            "name": "Unsafe Action",
            "module": "leave",
            "trigger_event": "submitted",
            "steps": [{"step_order": 1, "step_type": "action", "action_type": "field_update", "action_config": {"target_module": "leave", "fields": {"hashed_password": "oops"}}}],
        },
        headers=admin_headers,
    )
    assert action.status_code == 400
