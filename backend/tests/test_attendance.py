from datetime import date, datetime, time, timezone
from decimal import Decimal


def _create_employee(db):
    from app.models.employee import Employee

    emp = Employee(
        employee_id=f"ATT{id(db)}",
        first_name="Attendance",
        last_name="Tester",
        date_of_joining=date(2024, 1, 1),
    )
    db.add(emp)
    db.commit()
    return emp


def test_attendance_compute_late_early_and_short_hours(client, superuser_headers, db):
    from app.models.attendance import Attendance

    emp = _create_employee(db)
    shift_resp = client.post("/api/v1/attendance/shifts", json={
        "name": "General",
        "code": "GEN",
        "start_time": "09:00:00",
        "end_time": "17:00:00",
        "grace_minutes": 10,
        "working_hours": "8.0",
    }, headers=superuser_headers)
    assert shift_resp.status_code == 201
    shift_id = shift_resp.json()["id"]

    work_date = date(2026, 5, 4)
    roster = client.post("/api/v1/attendance/roster", json={
        "employee_id": emp.id,
        "shift_id": shift_id,
        "work_date": work_date.isoformat(),
    }, headers=superuser_headers)
    assert roster.status_code == 201

    attendance = Attendance(
        employee_id=emp.id,
        attendance_date=work_date,
        check_in=datetime(2026, 5, 4, 9, 20, tzinfo=timezone.utc),
        check_out=datetime(2026, 5, 4, 16, 30, tzinfo=timezone.utc),
        status="Present",
    )
    db.add(attendance)
    db.commit()

    computed = client.post(
        f"/api/v1/attendance/compute/{emp.id}/{work_date.isoformat()}",
        headers=superuser_headers,
    )
    assert computed.status_code == 200
    data = computed.json()
    assert data["shift_id"] == shift_id
    assert data["is_late"] is True
    assert data["late_minutes"] == 20
    assert data["is_early_exit"] is True
    assert data["early_exit_minutes"] == 30
    assert data["is_short_hours"] is True
    assert data["short_minutes"] == 50
    assert data["status"] == "Present"


def test_attendance_compute_weekly_off(client, superuser_headers, db):
    emp = _create_employee(db)
    shift_resp = client.post("/api/v1/attendance/shifts", json={
        "name": "Sunday Off Shift",
        "code": "SUN",
        "start_time": "09:00:00",
        "end_time": "17:00:00",
        "grace_minutes": 10,
        "working_hours": "8.0",
    }, headers=superuser_headers)
    assert shift_resp.status_code == 201
    shift_id = shift_resp.json()["id"]

    weekly_off = client.post("/api/v1/attendance/weekly-offs", json={
        "shift_id": shift_id,
        "weekday": 6,
        "week_pattern": "all",
    }, headers=superuser_headers)
    assert weekly_off.status_code == 201

    work_date = date(2026, 5, 3)
    roster = client.post("/api/v1/attendance/roster", json={
        "employee_id": emp.id,
        "shift_id": shift_id,
        "work_date": work_date.isoformat(),
    }, headers=superuser_headers)
    assert roster.status_code == 201

    computed = client.post(
        f"/api/v1/attendance/compute/{emp.id}/{work_date.isoformat()}",
        headers=superuser_headers,
    )
    assert computed.status_code == 200
    assert computed.json()["status"] == "Weekend"


def test_attendance_compute_on_time_full_day(client, superuser_headers, db):
    from app.models.attendance import Attendance

    emp = _create_employee(db)
    shift_resp = client.post("/api/v1/attendance/shifts", json={
        "name": "On Time",
        "code": "ONT",
        "start_time": "09:00:00",
        "end_time": "17:00:00",
        "grace_minutes": 10,
        "working_hours": "8.0",
    }, headers=superuser_headers)
    assert shift_resp.status_code == 201
    shift_id = shift_resp.json()["id"]

    work_date = date(2026, 5, 5)
    roster = client.post("/api/v1/attendance/roster", json={
        "employee_id": emp.id,
        "shift_id": shift_id,
        "work_date": work_date.isoformat(),
    }, headers=superuser_headers)
    assert roster.status_code == 201

    db.add(Attendance(
        employee_id=emp.id,
        attendance_date=work_date,
        check_in=datetime(2026, 5, 5, 9, 0, tzinfo=timezone.utc),
        check_out=datetime(2026, 5, 5, 17, 0, tzinfo=timezone.utc),
        status="Present",
    ))
    db.commit()

    computed = client.post(
        f"/api/v1/attendance/compute/{emp.id}/{work_date.isoformat()}",
        headers=superuser_headers,
    )
    assert computed.status_code == 200
    data = computed.json()
    assert data["total_hours"] == "8.00"
    assert data["is_late"] is False
    assert data["late_minutes"] == 0
    assert data["is_early_exit"] is False
    assert data["early_exit_minutes"] == 0
    assert data["is_short_hours"] is False
    assert data["short_minutes"] == 0
    assert data["status"] == "Present"


def test_attendance_raw_punches_use_same_break_aware_computation(client, superuser_headers, db):
    emp = _create_employee(db)
    shift_resp = client.post("/api/v1/attendance/shifts", json={
        "name": "Break Aware",
        "code": "BRK",
        "start_time": "09:00:00",
        "end_time": "17:00:00",
        "grace_minutes": 10,
        "working_hours": "7.5",
    }, headers=superuser_headers)
    assert shift_resp.status_code == 201
    shift_id = shift_resp.json()["id"]

    work_date = date(2026, 5, 6)
    roster = client.post("/api/v1/attendance/roster", json={
        "employee_id": emp.id,
        "shift_id": shift_id,
        "work_date": work_date.isoformat(),
    }, headers=superuser_headers)
    assert roster.status_code == 201

    for punch_type, punch_time in [
        ("IN", datetime(2026, 5, 6, 9, 0, tzinfo=timezone.utc)),
        ("BREAK_OUT", datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)),
        ("BREAK_IN", datetime(2026, 5, 6, 12, 30, tzinfo=timezone.utc)),
        ("OUT", datetime(2026, 5, 6, 17, 0, tzinfo=timezone.utc)),
    ]:
        punch = client.post("/api/v1/attendance/punches", json={
            "employee_id": emp.id,
            "punch_type": punch_type,
            "punch_time": punch_time.isoformat(),
            "source": "Biometric",
        }, headers=superuser_headers)
        assert punch.status_code == 201, punch.text

    computed = client.post(
        f"/api/v1/attendance/compute/{emp.id}/{work_date.isoformat()}",
        headers=superuser_headers,
    )
    assert computed.status_code == 200
    data = computed.json()
    assert data["total_hours"] == "7.50"
    assert data["is_short_hours"] is False
    assert data["short_minutes"] == 0
    assert data["status"] == "Present"


def test_attendance_compute_overnight_shift(client, superuser_headers, db):
    from app.models.attendance import Attendance

    emp = _create_employee(db)
    shift_resp = client.post("/api/v1/attendance/shifts", json={
        "name": "Night",
        "code": "NGT",
        "start_time": "22:00:00",
        "end_time": "06:00:00",
        "grace_minutes": 0,
        "working_hours": "8.0",
        "is_night_shift": True,
    }, headers=superuser_headers)
    assert shift_resp.status_code == 201
    shift_id = shift_resp.json()["id"]

    work_date = date(2026, 5, 7)
    roster = client.post("/api/v1/attendance/roster", json={
        "employee_id": emp.id,
        "shift_id": shift_id,
        "work_date": work_date.isoformat(),
    }, headers=superuser_headers)
    assert roster.status_code == 201

    db.add(Attendance(
        employee_id=emp.id,
        attendance_date=work_date,
        check_in=datetime(2026, 5, 7, 22, 15, tzinfo=timezone.utc),
        check_out=datetime(2026, 5, 8, 5, 30, tzinfo=timezone.utc),
        status="Present",
    ))
    db.commit()

    computed = client.post(
        f"/api/v1/attendance/compute/{emp.id}/{work_date.isoformat()}",
        headers=superuser_headers,
    )
    assert computed.status_code == 200
    data = computed.json()
    assert data["is_late"] is True
    assert data["late_minutes"] == 15
    assert data["is_early_exit"] is True
    assert data["early_exit_minutes"] == 30
    assert data["is_short_hours"] is True
    assert data["short_minutes"] == 45
    assert data["total_hours"] == "7.25"
