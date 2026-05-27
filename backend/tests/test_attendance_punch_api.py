from datetime import date, datetime, time, timezone

from app.core.security import get_password_hash
from app.models.attendance import Attendance, AttendancePunch, AttendanceRegularization, Shift
from app.models.employee import Employee
from app.models.notification import Notification
from app.models.user import Role, User


def _login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _user_employee(db, email, code, first_name, *, manager_id=None, is_superuser=False):
    role = Role(name=f"role-{code}", description="Test role")
    db.add(role)
    db.flush()
    user = User(
        email=email,
        hashed_password=get_password_hash("User@123456"),
        is_active=True,
        is_superuser=is_superuser,
        role_id=role.id,
    )
    db.add(user)
    db.flush()
    employee = Employee(
        employee_id=code,
        user_id=user.id,
        first_name=first_name,
        last_name="Tester",
        date_of_joining=date.today(),
        reporting_manager_id=manager_id,
        status="Active",
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return user, employee


def test_employee_can_punch_and_today_returns_summary_with_punches(client, db):
    shift = Shift(name="General", code="GEN", start_time=time(9, 0), end_time=time(18, 0), grace_minutes=10, working_hours=8)
    db.add(shift)
    db.commit()

    _, employee = _user_employee(db, "punch.employee@test.com", "PUNCH-001", "Punch")
    employee.shift_id = shift.id
    db.commit()
    headers = _login(client, "punch.employee@test.com", "User@123456")

    punch_in = client.post("/api/v1/attendance/punch", json={"punch_type": "IN", "source": "web"}, headers=headers)
    assert punch_in.status_code == 201
    assert punch_in.json()["punch"]["punch_type"] == "IN"
    assert punch_in.json()["attendance"]["check_in"] is not None

    punch_out = client.post("/api/v1/attendance/punch", json={"punch_type": "OUT", "source": "web"}, headers=headers)
    assert punch_out.status_code == 201
    assert punch_out.json()["attendance"]["check_out"] is not None

    today = client.get("/api/v1/attendance/today", headers=headers)
    assert today.status_code == 200
    payload = today.json()
    assert payload["check_in"] is not None
    assert payload["check_out"] is not None
    assert [item["punch_type"] for item in payload["punches"]] == ["IN", "OUT"]

    paginated = client.get(
        "/api/v1/attendance/my",
        params={"from_date": str(date.today()), "to_date": str(date.today()), "page": 1, "page_size": 10},
        headers=headers,
    )
    assert paginated.status_code == 200
    assert paginated.json()["total"] == 1


def test_manager_can_view_reportee_team_attendance_and_regularization_notifies_manager(client, db):
    _, manager = _user_employee(db, "manager.attendance@test.com", "MGR-ATT-001", "Manager")
    _, reportee = _user_employee(db, "reportee.attendance@test.com", "REP-ATT-001", "Reportee", manager_id=manager.id)
    _, outsider = _user_employee(db, "outsider.attendance@test.com", "OUT-ATT-001", "Outsider")
    manager_headers = _login(client, "manager.attendance@test.com", "User@123456")
    reportee_headers = _login(client, "reportee.attendance@test.com", "User@123456")

    attendance = Attendance(employee_id=reportee.id, attendance_date=date.today(), status="Present")
    db.add(attendance)
    db.add(AttendancePunch(employee_id=reportee.id, punch_time=datetime.now(timezone.utc), punch_type="IN", source="Web"))
    db.commit()

    view_reportee = client.get(
        f"/api/v1/attendance/{reportee.id}",
        params={"from_date": str(date.today()), "to_date": str(date.today())},
        headers=manager_headers,
    )
    assert view_reportee.status_code == 200

    blocked = client.get(
        f"/api/v1/attendance/{outsider.id}",
        params={"from_date": str(date.today()), "to_date": str(date.today())},
        headers=manager_headers,
    )
    assert blocked.status_code == 403

    team = client.get("/api/v1/attendance/team", params={"from_date": str(date.today())}, headers=manager_headers)
    assert team.status_code == 200
    assert {item["employee_id"] for item in team.json()["items"]} == {reportee.id}

    regularize = client.post(
        "/api/v1/attendance/regularize",
        json={
            "date": str(date.today()),
            "reason": "Forgot checkout",
            "expected_check_in": datetime.combine(date.today(), time(9, 0), tzinfo=timezone.utc).isoformat(),
            "expected_check_out": datetime.combine(date.today(), time(18, 0), tzinfo=timezone.utc).isoformat(),
        },
        headers=reportee_headers,
    )
    assert regularize.status_code == 201
    assert db.query(AttendanceRegularization).filter_by(employee_id=reportee.id).count() == 1
    assert db.query(Notification).filter_by(user_id=manager.user_id, event_type="attendance_regularization_requested").count() == 1
