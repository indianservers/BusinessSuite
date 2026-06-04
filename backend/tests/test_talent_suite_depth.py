from decimal import Decimal
from datetime import date

from app.db.init_db import init_db
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_calibration_one_on_one_nine_box_and_succession_workflows(client, db):
    init_db(db)
    admin = _login(client, "admin@aihrms.com", "Admin@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    manager = db.query(Employee).filter(Employee.employee_id == "DEMO-MGR-001").first()

    cycle = client.post("/api/v1/performance/cycles", json={
        "name": "FY27 Talent Review",
        "start_date": "2026-04-01",
        "end_date": "2027-03-31",
    }, headers=admin)
    assert cycle.status_code == 201

    calibration = client.post("/api/v1/performance/calibration/sessions", json={
        "cycle_id": cycle.json()["id"],
        "name": "Engineering calibration",
        "participants": [{
            "employee_id": employee.id,
            "proposed_rating": "3.5",
            "potential_rating": "4.5",
            "notes": "Manager proposed rating",
        }],
    }, headers=admin)
    assert calibration.status_code == 201
    assert calibration.json()["participants"][0]["proposed_rating"] == "3.5"

    updated = client.put(f"/api/v1/performance/calibration/sessions/{calibration.json()['id']}", json={
        "status": "Completed",
        "notes": "Panel finalized",
        "participants": [{
            "employee_id": employee.id,
            "proposed_rating": "3.5",
            "final_rating": "4.0",
            "potential_rating": "4.5",
            "notes": "Finalized after calibration",
        }],
    }, headers=admin)
    assert updated.status_code == 200
    assert updated.json()["participants"][0]["status"] == "Finalized"
    assert updated.json()["audit_json"]

    nine_box = client.get("/api/v1/performance/nine-box", params={"cycle_id": cycle.json()["id"]}, headers=admin)
    assert nine_box.status_code == 200
    assert nine_box.json()["items"][0]["box"] == "Star"

    one_on_one = client.post("/api/v1/performance/one-on-ones", json={
        "manager_id": manager.id,
        "employee_id": employee.id,
        "meeting_date": "2026-05-20",
        "talking_points_json": [{"text": "Career goals"}],
        "action_items_json": [{"owner": "manager", "action": "Find mentor"}],
    }, headers=admin)
    assert one_on_one.status_code == 201
    assert one_on_one.json()["manager_id"] == manager.id

    role = client.post("/api/v1/performance/succession/critical-roles", json={
        "role_name": "Payroll Platform Lead",
        "incumbent_employee_id": manager.id,
        "business_impact": "Critical",
        "vacancy_risk": "Medium",
    }, headers=admin)
    assert role.status_code == 201
    successor = client.post("/api/v1/performance/succession/candidates", json={
        "critical_role_id": role.json()["id"],
        "employee_id": employee.id,
        "readiness_level": "Ready in 6 months",
        "development_actions_json": [{"action": "Lead statutory release"}],
        "mentor_employee_id": manager.id,
    }, headers=admin)
    assert successor.status_code == 201
    roles = client.get("/api/v1/performance/succession/critical-roles", headers=admin)
    assert roles.status_code == 200
    assert roles.json()[0]["successors"][0]["readiness_level"] == "Ready in 6 months"


def test_lms_scorm_xapi_completion_callback_and_certification_renewal(client, db):
    init_db(db)
    admin = _login(client, "admin@aihrms.com", "Admin@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()

    course = client.post("/api/v1/lms/courses", json={
        "code": "SEC-SCORM-101",
        "title": "Security SCORM Basics",
        "content_standard": "SCORM",
        "scorm_package_url": "https://lms.example/scorm/sec.zip",
        "scorm_version": "2004",
        "xapi_activity_id": "urn:course:security-basics",
        "external_launch_url": "https://lms.example/launch/sec",
        "completion_callback_url": "https://hrms.example/api/v1/lms/callback",
        "metadata_json": {"provider": "external-lms"},
    }, headers=admin)
    assert course.status_code == 201
    assert course.json()["content_standard"] == "SCORM"

    assignment = client.post("/api/v1/lms/assignments", json={
        "course_id": course.json()["id"],
        "employee_id": employee.id,
        "due_date": "2026-06-30",
    }, headers=admin)
    assert assignment.status_code == 201
    callback = client.post(f"/api/v1/lms/assignments/{assignment.json()['id']}/completion-callback", json={
        "completion_status": "passed",
        "score": "92.5",
    })
    assert callback.status_code == 200
    assert callback.json()["completion_status"] == "Completed"

    cert = client.post("/api/v1/lms/certifications", json={
        "employee_id": employee.id,
        "course_id": course.json()["id"],
        "title": "Security Certification",
        "issued_on": "2026-05-01",
        "expires_on": "2026-06-15",
        "renewal_required": True,
        "reminder_days": 45,
    }, headers=admin)
    assert cert.status_code == 201
    assert cert.json()["renewal_status"] == "Due"
    renewals = client.get("/api/v1/lms/certification-renewals", params={"due_within_days": 90}, headers=admin)
    assert renewals.status_code == 200
    assert len(renewals.json()) == 1
    reminder = client.post("/api/v1/lms/certification-renewals/reminders", params={"due_within_days": 90}, headers=admin)
    assert reminder.status_code == 200
    assert reminder.json()["reminders_marked"] == 1


def test_compensation_worksheet_is_restricted_and_calculates_budget_impact(client, db):
    init_db(db)
    admin = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    db.add(EmployeeSalary(
        employee_id=employee.id,
        ctc=Decimal("800000"),
        basic=Decimal("320000"),
        hra=Decimal("160000"),
        effective_from=date(2026, 4, 1),
        is_active=True,
    ))
    db.commit()

    cycle = client.post("/api/v1/performance/compensation/cycles", json={
        "name": "FY27 Merit Worksheet",
        "financial_year": "2026-27",
        "budget_amount": "1000000",
    }, headers=admin)
    assert cycle.status_code == 201
    band = client.post("/api/v1/performance/compensation/pay-bands", json={
        "name": "P2 India",
        "min_ctc": "600000",
        "midpoint_ctc": "900000",
        "max_ctc": "1200000",
    }, headers=admin)
    assert band.status_code == 201
    row = client.post("/api/v1/performance/compensation/worksheet", json={
        "compensation_cycle_id": cycle.json()["id"],
        "employee_id": employee.id,
        "pay_band_id": band.json()["id"],
        "proposed_merit_percent": "10",
        "performance_rating": "4.0",
        "manager_notes": "Strong year",
    }, headers=admin)
    assert row.status_code == 201
    assert row.json()["current_ctc"] == "800000.00"
    assert row.json()["budget_impact"] == "80000.00"
    assert row.json()["proposed_ctc"] == "880000.00"

    approved = client.put(f"/api/v1/performance/compensation/worksheet/{row.json()['id']}", json={
        "approval_status": "Approved",
        "hr_notes": "Within budget",
    }, headers=admin)
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "Approved"

    blocked = client.get("/api/v1/performance/compensation/worksheet", headers=employee_headers)
    assert blocked.status_code == 403
