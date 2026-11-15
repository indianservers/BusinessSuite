from app.db.init_db import init_db
from app.models.employee import Employee


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_employee_timesheet_submission_and_manager_approval(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    manager_headers = _login(client, "manager@aihrms.com", "Manager@123456")
    employee = db.query(Employee).filter(Employee.employee_id == 'DEMO-EMP-001').one()

    project_response = client.post(
        "/api/v1/timesheets/projects",
        json={
            "code": "TECH-001",
            "name": "Client ERP Implementation",
            "client_name": "Acme Services",
            "is_billable": True,
            "owner_employee_id": employee.id,
        },
        headers=admin_headers,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    duplicate_project = client.post(
        "/api/v1/timesheets/projects",
        json={"code": "TECH-001", "name": "Duplicate Project"},
        headers=admin_headers,
    )
    assert duplicate_project.status_code == 400

    timesheet_response = client.post(
        "/api/v1/timesheets/",
        json={
            "project_id": project_id,
            "period_start": "2026-05-04",
            "period_end": "2026-05-10",
        },
        headers=employee_headers,
    )
    assert timesheet_response.status_code == 201, timesheet_response.text
    sheet_id = timesheet_response.json()["id"]

    billable_entry = client.post(
        f"/api/v1/timesheets/{sheet_id}/entries",
        json={
            "work_date": "2026-05-04",
            "hours": "8.00",
            "is_billable": True,
            "task_name": "Implementation",
        },
        headers=employee_headers,
    )
    assert billable_entry.status_code == 201

    non_billable_entry = client.post(
        f"/api/v1/timesheets/{sheet_id}/entries",
        json={
            "work_date": "2026-05-05",
            "hours": "2.50",
            "is_billable": False,
            "task_name": "Internal planning",
        },
        headers=employee_headers,
    )
    assert non_billable_entry.status_code == 201

    submitted = client.put(f"/api/v1/timesheets/{sheet_id}/submit", headers=employee_headers)
    assert submitted.status_code == 200
    submitted_data = submitted.json()
    assert submitted_data["status"] == "Submitted"
    assert float(submitted_data["total_hours"]) == 10.5
    assert float(submitted_data["billable_hours"]) == 8.0
    assert float(submitted_data["non_billable_hours"]) == 2.5

    approved = client.put(
        f"/api/v1/timesheets/{sheet_id}/review",
        json={"status": "Approved", "review_remarks": "Approved for billing."},
        headers=manager_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "Approved"
    assert approved.json()["reviewed_by"] is not None


def test_timesheet_entry_validation_and_role_boundaries(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    hr_headers = _login(client, "hr@aihrms.com", "HR@123456")
    employee = db.query(Employee).filter(Employee.employee_id == 'DEMO-EMP-001').one()

    project = client.post(
        "/api/v1/timesheets/projects",
        json={"code": "TECH-002", "name": "Product Support", "owner_employee_id": employee.id},
        headers=admin_headers,
    )
    assert project.status_code == 201

    sheet = client.post(
        "/api/v1/timesheets/",
        json={
            "project_id": project.json()["id"],
            "period_start": "2026-05-04",
            "period_end": "2026-05-10",
        },
        headers=employee_headers,
    )
    assert sheet.status_code == 201, sheet.text
    sheet_id = sheet.json()["id"]

    outside_period = client.post(
        f"/api/v1/timesheets/{sheet_id}/entries",
        json={"work_date": "2026-05-11", "hours": "1.00", "is_billable": True},
        headers=employee_headers,
    )
    assert outside_period.status_code == 400

    too_many_hours = client.post(
        f"/api/v1/timesheets/{sheet_id}/entries",
        json={"work_date": "2026-05-04", "hours": "25.00", "is_billable": True},
        headers=employee_headers,
    )
    assert too_many_hours.status_code == 400

    hr_edit = client.post(
        f"/api/v1/timesheets/{sheet_id}/entries",
        json={"work_date": "2026-05-04", "hours": "1.00", "is_billable": True},
        headers=hr_headers,
    )
    assert hr_edit.status_code == 403
