from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveType
from app.models.timesheet import Project, Timesheet


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_manager_workflow_inbox_shows_team_approvals(client, db):
    init_db(db)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    manager_headers = _login(client, "manager@aihrms.com", "Manager@123456")

    leave_type = LeaveType(name="Workflow Leave", code="WFL", days_allowed=Decimal("5"))
    db.add(leave_type)
    db.flush()
    from app.models.security_boundary import SecurityResourceOwnership
    db.add(SecurityResourceOwnership(resource_table="leave_types", resource_id=leave_type.id, company_id=employee.branch.company_id))
    db.add(
        LeaveRequest(
            company_id=employee.branch.company_id,
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            from_date=date(2026, 5, 12),
            to_date=date(2026, 5, 12),
            days_count=Decimal("1"),
            reason="Manager workflow test",
            status="Pending",
        )
    )

    project = Project(code="WF-001", name="Workflow Project", organization_id=employee.branch.company_id)
    db.add(project)
    db.flush()
    db.add(
        Timesheet(
            employee_id=employee.id,
            project_id=project.id,
            period_start=date(2026, 5, 4),
            period_end=date(2026, 5, 10),
            total_hours=Decimal("8.00"),
            billable_hours=Decimal("8.00"),
            status="Submitted",
        )
    )
    db.commit()

    response = client.get("/api/v1/workflow/inbox", headers=manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["pending_action"] == 2
    assert data["by_source"]["leave"] == 1
    assert data["by_source"]["timesheet"] == 1
    assert {item["role_scope"] for item in data["items"]} == {"manager"}


def test_employee_workflow_inbox_shows_own_submissions_only(client, db):
    init_db(db)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")

    leave_type = LeaveType(name="My Workflow Leave", code="MWFL", days_allowed=Decimal("5"))
    db.add(leave_type)
    db.flush()
    from app.models.security_boundary import SecurityResourceOwnership
    db.add(SecurityResourceOwnership(resource_table="leave_types", resource_id=leave_type.id, company_id=employee.branch.company_id))
    db.add(
        LeaveRequest(
            company_id=employee.branch.company_id,
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            from_date=date(2026, 6, 1),
            to_date=date(2026, 6, 2),
            days_count=Decimal("2"),
            reason="Employee workflow test",
            status="Pending",
        )
    )
    db.commit()

    response = client.get("/api/v1/workflow/inbox?mine=true", headers=employee_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["submitted_by_me"] >= 1
    assert data["by_source"]["leave"] == 1
    assert data["items"][0]["requester_employee_id"] == employee.id

    approval_view = client.get("/api/v1/workflow/inbox", headers=employee_headers)
    assert approval_view.status_code == 200
    assert approval_view.json()["total"] == 0
