from datetime import date, timedelta

from app.core.security import get_password_hash
from app.models.attendance import Attendance, Holiday
from app.models.employee import Employee
from app.models.user import Role, User


def _login(client, email: str, password: str = "User@123456") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _employee_user(db, email: str, code: str, *, branch_id: int | None = None):
    role = Role(name=f"holiday-role-{code}", description="Holiday test role")
    db.add(role)
    db.flush()
    user = User(
        email=email,
        hashed_password=get_password_hash("User@123456"),
        is_active=True,
        role_id=role.id,
    )
    db.add(user)
    db.flush()
    employee = Employee(
        employee_id=code,
        user_id=user.id,
        first_name="Holiday",
        last_name="Reader",
        date_of_joining=date.today(),
        branch_id=branch_id,
        status="Active",
    )
    db.add(employee)
    db.commit()
    return user, employee


def test_holiday_calendar_crud_filters_and_attendance_sync(client, db, superuser_headers):
    branch_one = 101
    branch_two = 202
    _, employee_one = _employee_user(db, "holiday.branch1@test.com", "HOL-001", branch_id=branch_one)
    _, employee_two = _employee_user(db, "holiday.branch2@test.com", "HOL-002", branch_id=branch_two)
    holiday_date = date.today() + timedelta(days=7)
    db.add_all([
        Attendance(employee_id=employee_one.id, attendance_date=holiday_date, status="Absent"),
        Attendance(employee_id=employee_two.id, attendance_date=holiday_date, status="Absent"),
    ])
    db.commit()

    create = client.post(
        "/api/v1/holidays",
        json={
            "name": "Regional Foundation Day",
            "holiday_date": str(holiday_date),
            "holiday_type": "Regional",
            "description": "Branch specific holiday",
            "applicable_branches": [branch_one],
        },
        headers=superuser_headers,
    )
    assert create.status_code == 201
    payload = create.json()
    assert payload["applicable_branches"] == [branch_one]
    assert db.query(Attendance).filter_by(employee_id=employee_one.id, attendance_date=holiday_date).first().status == "Holiday"
    assert db.query(Attendance).filter_by(employee_id=employee_two.id, attendance_date=holiday_date).first().status == "Absent"

    branch_one_list = client.get(
        "/api/v1/holidays",
        params={"year": holiday_date.year, "branch_id": branch_one, "holiday_type": "Regional"},
        headers=superuser_headers,
    )
    assert branch_one_list.status_code == 200
    assert [item["name"] for item in branch_one_list.json()] == ["Regional Foundation Day"]

    branch_two_list = client.get(
        "/api/v1/holidays",
        params={"year": holiday_date.year, "branch_id": branch_two},
        headers=superuser_headers,
    )
    assert branch_two_list.status_code == 200
    assert branch_two_list.json() == []

    update = client.put(
        f"/api/v1/holidays/{payload['id']}",
        json={"description": "Updated", "applicable_branches": [branch_one, branch_two]},
        headers=superuser_headers,
    )
    assert update.status_code == 200
    assert update.json()["applicable_branches"] == [branch_one, branch_two]
    assert db.query(Attendance).filter_by(employee_id=employee_two.id, attendance_date=holiday_date).first().status == "Holiday"

    upcoming = client.get("/api/v1/holidays/upcoming", headers=superuser_headers)
    assert upcoming.status_code == 200
    assert len(upcoming.json()) <= 5
    assert any(item["id"] == payload["id"] for item in upcoming.json())

    delete = client.delete(f"/api/v1/holidays/{payload['id']}", headers=superuser_headers)
    assert delete.status_code == 200
    assert db.query(Holiday).filter_by(id=payload["id"]).first().is_active is False


def test_holiday_bulk_create_and_write_permissions(client, db, superuser_headers):
    _, _ = _employee_user(db, "holiday.reader@test.com", "HOL-READ")
    reader_headers = _login(client, "holiday.reader@test.com")
    holiday_date = date.today() + timedelta(days=10)

    blocked = client.post(
        "/api/v1/holidays",
        json={"name": "Blocked Holiday", "holiday_date": str(holiday_date), "holiday_type": "National"},
        headers=reader_headers,
    )
    assert blocked.status_code == 403

    bulk = client.post(
        "/api/v1/holidays/bulk",
        json=[
            {"name": "Holiday One", "holiday_date": str(holiday_date), "holiday_type": "National"},
            {"name": "Holiday Two", "holiday_date": str(holiday_date + timedelta(days=1)), "holiday_type": "Optional"},
        ],
        headers=superuser_headers,
    )
    assert bulk.status_code == 201
    assert [item["name"] for item in bulk.json()] == ["Holiday One", "Holiday Two"]

    read = client.get("/api/v1/holidays", params={"year": holiday_date.year}, headers=reader_headers)
    assert read.status_code == 200
    assert {"Holiday One", "Holiday Two"}.issubset({item["name"] for item in read.json()})
