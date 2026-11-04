from tests.rich_text_test_utils import organization_context
from datetime import date
from app.db.init_db import init_db
from app.models.attendance import Attendance
from app.models.audit import AuditLog
from app.models.employee import Employee


def _login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_attendance_checkin_handles_existing_partial_record(client, db):
    init_db(db)
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    db.add(Attendance(
        employee_id=employee.id,
        attendance_date=date.today(),
        status="Absent",
        source=None,
        is_regularized=None,
        overtime_hours=None,
        late_minutes=None,
        early_exit_minutes=None,
        short_minutes=None,
    ))
    db.commit()

    response = client.post("/api/v1/attendance/check-in", json={"source": "Web"}, headers=employee_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["check_in"] is not None
    assert payload["source"] == "Web"
    assert payload["is_regularized"] is False
    assert payload["overtime_hours"] == "0.00"


def test_admin_can_view_and_analyze_audit_logs(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    db.add_all([
        AuditLog(method="POST", endpoint="/api/v1/attendance/check-in", status_code=500, duration_ms=120, action="ERROR", description="error=boom"),
        AuditLog(method="GET", endpoint="/api/v1/attendance/today", status_code=200, duration_ms=20, action="GET"),
        AuditLog(method="POST", endpoint="/api/v1/leave/requests", status_code=400, duration_ms=60, action="POST", description="bad request"),
    ])
    db.commit()

    errors = client.get("/api/v1/logs/errors?endpoint=attendance", headers=admin_headers)
    assert errors.status_code == 200
    assert len(errors.json()) == 1
    assert errors.json()[0]["endpoint"] == "/api/v1/attendance/check-in"

    analysis = client.get("/api/v1/logs/analysis?endpoint=attendance", headers=admin_headers)
    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["total_requests"] == 2
    assert payload["error_count"] == 1
    assert payload["server_error_count"] == 1
    assert any(item["endpoint"] == "/api/v1/attendance/check-in" for item in payload["top_errors"])
