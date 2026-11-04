from tests.rich_text_test_utils import organization_context
from datetime import date, time
from decimal import Decimal

from app.crud.crud_attendance import crud_attendance
from app.models.attendance import Shift, ShiftRoster, ShiftWeeklyOff
from app.models.employee import Employee


def _seed_employee_and_shifts(db):
    employee = Employee(
        employee_id="ROS001",
        first_name="Roster",
        last_name="Worker",
        date_of_joining=date(2026, 1, 1),
        status="Active",
    )
    day = Shift(
        name="General",
        code="GEN",
        start_time=time(9, 0),
        end_time=time(18, 0),
        grace_minutes=10,
        working_hours=Decimal("9.00"),
        is_active=True,
    )
    night = Shift(
        name="Night",
        code="NGT",
        start_time=time(21, 0),
        end_time=time(6, 0),
        grace_minutes=10,
        working_hours=Decimal("9.00"),
        is_night_shift=True,
        is_active=True,
    )
    db.add_all([employee, day, night])
    db.flush()
    db.add(ShiftWeeklyOff(shift_id=day.id, weekday=6, week_pattern="all", is_active=True))
    db.commit()
    return employee, day, night


def test_shift_roster_assign_copy_publish_and_attendance_shift(client, db, superuser_headers):
    employee, day, night = _seed_employee_and_shifts(db)

    assigned = client.post(
        "/api/v1/hrms/shift-roster/assign",
        json={"employeeId": employee.id, "shiftId": day.id, "rosterDate": "2026-05-11", "status": "draft"},
        headers=superuser_headers,
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "draft"
    assert assigned.json()["shift"]["code"] == "GEN"

    bulk = client.post(
        "/api/v1/hrms/shift-roster/bulk-assign",
        json={"employeeIds": [employee.id], "shiftId": day.id, "fromDate": "2026-05-11", "toDate": "2026-05-17"},
        headers=superuser_headers,
    )
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["assigned"] == 7
    assert any("Weekly roster exceeds 48 planned hours" in ";".join(item["messages"]) for item in bulk.json()["conflicts"])
    assert any("weekly off" in ";".join(item["messages"]).lower() for item in bulk.json()["conflicts"])

    published = client.post(
        "/api/v1/hrms/shift-roster/publish",
        json={"employeeIds": [employee.id], "fromDate": "2026-05-11", "toDate": "2026-05-17"},
        headers=superuser_headers,
    )
    assert published.status_code == 200
    assert published.json()["published"] == 7

    roster = client.get(
        "/api/v1/hrms/shift-roster?from=2026-05-11&to=2026-05-17",
        headers=superuser_headers,
    )
    assert roster.status_code == 200
    assert len(roster.json()["rosters"]) == 7

    copied = client.post(
        "/api/v1/hrms/shift-roster/copy-week",
        json={"employeeIds": [employee.id], "sourceWeekStart": "2026-05-11", "targetWeekStart": "2026-05-18"},
        headers=superuser_headers,
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["copied"] == 7

    # Published shift rosters should be the first source used by attendance computation.
    next_monday = db.query(ShiftRoster).filter_by(employee_id=employee.id, roster_date=date(2026, 5, 18)).first()
    next_monday.shift_id = night.id
    next_monday.status = "published"
    db.commit()
    shift = crud_attendance.get_shift_for_day(db, employee.id, date(2026, 5, 18))
    assert shift.id == night.id
