import pytest
from datetime import date, timedelta
from decimal import Decimal


def _create_employee_with_leave(db, client, headers):
    """Helper to create an employee with leave balance."""
    from app.models.employee import Employee
    from app.models.leave import LeaveType, LeaveBalance
    from app.models.user import User, Role
    from app.core.security import get_password_hash

    role = Role(name=f"emp_role_{id(db)}", description="Employee", is_system=False)
    db.add(role)
    db.flush()

    user = User(
        email=f"leavetest_{id(db)}@test.com",
        hashed_password=get_password_hash("Test@123"),
        is_active=True,
        role_id=role.id,
    )
    db.add(user)
    db.flush()

    emp = Employee(
        employee_id=f"LEAVEEMP{id(db)}",
        first_name="Leave",
        last_name="Tester",
        date_of_joining=date(2023, 1, 1),
        user_id=user.id,
    )
    db.add(emp)
    db.flush()

    lt = LeaveType(
        name="Annual Leave",
        code=f"AL{id(db)}",
        days_allowed=Decimal("21"),
        carry_forward=False,
    )
    db.add(lt)
    db.flush()

    balance = LeaveBalance(
        employee_id=emp.id,
        leave_type_id=lt.id,
        year=date.today().year,
        allocated=Decimal("21"),
        used=Decimal("0"),
        pending=Decimal("0"),
    )
    db.add(balance)
    db.commit()

    return emp, lt, user


def test_list_leave_types(client, superuser_headers):
    response = client.get("/api/v1/leave/types", headers=superuser_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_leave_type(client, superuser_headers):
    response = client.post("/api/v1/leave/types", json={
        "name": "Sick Leave",
        "code": "SL001",
        "days_allowed": 10,
        "accrual_frequency": "monthly",
        "carry_forward": False,
    }, headers=superuser_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Sick Leave"
    assert data["code"] == "SL001"
    assert data["accrual_frequency"] == "monthly"


def test_scheduled_leave_accruals_are_idempotent(db):
    from app.crud.crud_leave import run_scheduled_leave_accruals
    from app.models.employee import Employee
    from app.models.leave import LeaveBalance, LeaveBalanceLedger, LeaveType

    employee = Employee(
        employee_id=f"ACCRUAL{id(db)}",
        first_name="Accrual",
        last_name="Tester",
        date_of_joining=date(2025, 1, 1),
        status="Active",
    )
    leave_type = LeaveType(
        name="Monthly Earned",
        code=f"ME{id(db)}",
        days_allowed=Decimal("12"),
        accrual_frequency="monthly",
        carry_forward=True,
    )
    db.add_all([employee, leave_type])
    db.commit()

    result = run_scheduled_leave_accruals(db, date(2026, 5, 1))
    assert result["credited"] == 1

    balance = db.query(LeaveBalance).filter_by(employee_id=employee.id, leave_type_id=leave_type.id, year=2026).first()
    assert balance.allocated == Decimal("1.0")
    assert db.query(LeaveBalanceLedger).filter_by(leave_balance_id=balance.id, transaction_type="scheduled_accrual").count() == 1

    rerun = run_scheduled_leave_accruals(db, date(2026, 5, 1))
    db.refresh(balance)
    assert rerun["credited"] == 0
    assert balance.allocated == Decimal("1.0")


def test_leave_accrual_celery_beat_is_registered():
    from app.worker import celery_app

    schedule = celery_app.conf.beat_schedule["credit-scheduled-leave-accruals-daily"]
    assert schedule["task"] == "app.worker.credit_scheduled_leave_accruals"


def test_leave_balance_check(client, db):
    from app.models.user import User
    from app.core.security import get_password_hash

    emp, lt, user = _create_employee_with_leave(db, client, {})

    login_response = client.post("/api/v1/auth/login", json={
        "email": user.email,
        "password": "Test@123",
    })
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/leave/balance", headers=headers)
    assert response.status_code == 200
    balances = response.json()
    assert len(balances) > 0


def test_leave_request_workflow(client, db):
    """Test apply → approve flow."""
    from app.models.user import User, Role
    from app.core.security import get_password_hash

    emp, lt, user = _create_employee_with_leave(db, client, {})

    login_resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Test@123"})
    emp_token = login_resp.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # Apply for leave
    from_date = (date.today() + timedelta(days=7)).isoformat()
    to_date = (date.today() + timedelta(days=9)).isoformat()
    apply_resp = client.post("/api/v1/leave/apply", json={
        "leave_type_id": lt.id,
        "from_date": from_date,
        "to_date": to_date,
        "reason": "Family vacation",
    }, headers=emp_headers)
    assert apply_resp.status_code == 201
    request_id = apply_resp.json()["id"]
    assert apply_resp.json()["status"] == "Pending"


def test_hr_can_review_leave_with_reason(client, db, superuser_headers):
    """HR/Admin approval flow records the decision reason and exposes employee details."""
    from app.models.leave import LeaveRequest
    from app.models.notification import Notification

    emp, lt, user = _create_employee_with_leave(db, client, {})

    login_resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Test@123"})
    emp_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    apply_resp = client.post("/api/v1/leave/apply", json={
        "leave_type_id": lt.id,
        "from_date": (date.today() + timedelta(days=14)).isoformat(),
        "to_date": (date.today() + timedelta(days=15)).isoformat(),
        "reason": "Family function",
    }, headers=emp_headers)
    assert apply_resp.status_code == 201
    request_id = apply_resp.json()["id"]

    pending = client.get("/api/v1/leave/requests", params={"status": "Pending"}, headers=superuser_headers)
    assert pending.status_code == 200
    item = next(row for row in pending.json() if row["id"] == request_id)
    assert item["employee"]["employee_id"] == emp.employee_id
    assert item["days_count"] == "2.0"

    review = client.put(
        f"/api/v1/leave/requests/{request_id}/approve",
        json={"status": "Rejected", "review_remarks": "Project handover is incomplete"},
        headers=superuser_headers,
    )
    assert review.status_code == 200

    stored = db.query(LeaveRequest).filter_by(id=request_id).first()
    assert stored.status == "Rejected"
    assert stored.review_remarks == "Project handover is incomplete"

    notification = db.query(Notification).filter_by(
        user_id=user.id,
        related_entity_type="leave_request",
        related_entity_id=request_id,
        event_type="leave_rejected",
    ).first()
    assert notification is not None
    assert notification.title == "Leave Rejected"
    assert "Project handover is incomplete" in notification.message


def test_leave_calendar_scopes_manager_team_and_holidays(client, db):
    from app.core.security import get_password_hash
    from app.models.attendance import Holiday
    from app.models.employee import Employee
    from app.models.leave import LeaveRequest
    from app.models.user import Role, User

    manager_role = Role(name="manager", description="Manager")
    db.add(manager_role)
    db.flush()
    manager_user = User(
        email=f"calendar_manager_{id(db)}@test.com",
        hashed_password=get_password_hash("Test@123"),
        is_active=True,
        role_id=manager_role.id,
    )
    db.add(manager_user)
    db.flush()
    manager_emp = Employee(
        employee_id=f"CALMGR{id(db)}",
        first_name="Calendar",
        last_name="Manager",
        date_of_joining=date(2023, 1, 1),
        user_id=manager_user.id,
    )
    db.add(manager_emp)
    db.flush()

    report_emp, leave_type, _ = _create_employee_with_leave(db, client, {})
    report_emp.reporting_manager_id = manager_emp.id
    outsider_user = User(
        email=f"calendar_outsider_{id(db)}@test.com",
        hashed_password=get_password_hash("Test@123"),
        is_active=True,
        role_id=manager_role.id,
    )
    db.add(outsider_user)
    db.flush()
    outsider_emp = Employee(
        employee_id=f"CALOUT{id(db)}",
        first_name="Outside",
        last_name="Team",
        date_of_joining=date(2023, 1, 1),
        user_id=outsider_user.id,
    )
    db.add(outsider_emp)
    db.flush()
    start = date.today() + timedelta(days=30)
    db.add(LeaveRequest(
        employee_id=report_emp.id,
        leave_type_id=leave_type.id,
        from_date=start,
        to_date=start + timedelta(days=1),
        days_count=Decimal("2"),
        status="Approved",
        reason="Team leave",
    ))
    db.add(LeaveRequest(
        employee_id=outsider_emp.id,
        leave_type_id=leave_type.id,
        from_date=start,
        to_date=start,
        days_count=Decimal("1"),
        status="Approved",
        reason="Outside team",
    ))
    db.add(Holiday(name="Calendar Holiday", holiday_date=start, holiday_type="National", is_active=True))
    db.commit()

    login = client.post("/api/v1/auth/login", json={"email": manager_user.email, "password": "Test@123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/v1/leave/calendar", params={
        "from_date": start.isoformat(),
        "to_date": (start + timedelta(days=2)).isoformat(),
        "scope": "team",
    }, headers=headers)

    assert response.status_code == 200
    data = response.json()
    first_day = data["days"][0]
    assert first_day["leave_count"] == 1
    assert first_day["approved_count"] == 1
    assert first_day["holidays"][0]["name"] == "Calendar Holiday"
    assert first_day["employees_on_leave"][0]["employee"]["employee_id"] == report_emp.employee_id


def test_team_leave_calendar_scopes_manager_employee_and_hr(client, db, superuser_headers):
    from app.core.security import get_password_hash
    from app.models.company import Branch, Company, Department
    from app.models.employee import Employee
    from app.models.leave import LeaveRequest, LeaveType
    from app.models.user import Role, User

    suffix = id(db)
    company = Company(name=f"Calendar Co {suffix}")
    db.add(company)
    db.flush()
    branch = Branch(name=f"Calendar Branch {suffix}", code=f"CB{suffix}", company_id=company.id)
    db.add(branch)
    db.flush()
    department = Department(name=f"Engineering {suffix}", code=f"ENG{suffix}", branch_id=branch.id)
    other_department = Department(name=f"Finance {suffix}", code=f"FIN{suffix}", branch_id=branch.id)
    db.add_all([department, other_department])
    db.flush()

    role = Role(name=f"leave_calendar_role_{suffix}", description="Leave calendar role")
    db.add(role)
    db.flush()

    def make_user_employee(email, code, first, department_id, manager_id=None):
        user = User(
            email=email,
            hashed_password=get_password_hash("Test@123"),
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()
        employee = Employee(
            employee_id=code,
            first_name=first,
            last_name="Calendar",
            date_of_joining=date(2023, 1, 1),
            user_id=user.id,
            branch_id=branch.id,
            department_id=department_id,
            reporting_manager_id=manager_id,
            profile_photo_url=f"https://example.test/{code}.png",
        )
        db.add(employee)
        db.flush()
        return user, employee

    manager_user, manager_emp = make_user_employee(
        f"team_calendar_manager_{suffix}@test.com", f"TCM{suffix}", "Manager", department.id
    )
    _, reportee_emp = make_user_employee(
        f"team_calendar_reportee_{suffix}@test.com", f"TCR{suffix}", "Reportee", department.id, manager_emp.id
    )
    employee_user, employee_emp = make_user_employee(
        f"team_calendar_employee_{suffix}@test.com", f"TCE{suffix}", "Employee", department.id
    )
    _, teammate_emp = make_user_employee(
        f"team_calendar_teammate_{suffix}@test.com", f"TCT{suffix}", "Teammate", department.id
    )
    _, outsider_emp = make_user_employee(
        f"team_calendar_outsider_{suffix}@test.com", f"TCO{suffix}", "Outsider", other_department.id
    )
    leave_type = LeaveType(name=f"Casual Leave {suffix}", code=f"CL{suffix}", days_allowed=Decimal("12"))
    db.add(leave_type)
    db.flush()
    leave_day = date.today().replace(day=1)
    db.add_all([
        LeaveRequest(employee_id=reportee_emp.id, leave_type_id=leave_type.id, from_date=leave_day, to_date=leave_day, days_count=Decimal("1"), status="Approved"),
        LeaveRequest(employee_id=teammate_emp.id, leave_type_id=leave_type.id, from_date=leave_day, to_date=leave_day + timedelta(days=1), days_count=Decimal("2"), status="Approved", is_half_day=False),
        LeaveRequest(employee_id=outsider_emp.id, leave_type_id=leave_type.id, from_date=leave_day, to_date=leave_day, days_count=Decimal("1"), status="Approved"),
    ])
    db.commit()

    manager_login = client.post("/api/v1/auth/login", json={"email": manager_user.email, "password": "Test@123"})
    manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}
    manager_response = client.get(
        "/api/v1/leave/team-calendar",
        params={"year": leave_day.year, "month": leave_day.month},
        headers=manager_headers,
    )
    assert manager_response.status_code == 200
    assert [item["employee_id"] for item in manager_response.json()] == [reportee_emp.id]
    assert manager_response.json()[0]["department_name"] == department.name
    assert manager_response.json()[0]["leaves"][0]["leave_type_name"] == leave_type.name

    employee_login = client.post("/api/v1/auth/login", json={"email": employee_user.email, "password": "Test@123"})
    employee_headers = {"Authorization": f"Bearer {employee_login.json()['access_token']}"}
    employee_response = client.get(
        "/api/v1/leave/team-calendar",
        params={"year": leave_day.year, "month": leave_day.month},
        headers=employee_headers,
    )
    assert employee_response.status_code == 200
    assert {item["employee_id"] for item in employee_response.json()} == {reportee_emp.id, teammate_emp.id}

    hr_response = client.get(
        "/api/v1/leave/team-calendar",
        params={"year": leave_day.year, "month": leave_day.month, "department_id": str(other_department.id)},
        headers=superuser_headers,
    )
    assert hr_response.status_code == 200
    assert [item["employee_id"] for item in hr_response.json()] == [outsider_emp.id]


def test_department_calendar_and_today_absences(client, db):
    from app.core.security import get_password_hash
    from app.models.company import Branch, Company, Department
    from app.models.employee import Employee
    from app.models.leave import LeaveRequest, LeaveType
    from app.models.user import Role, User

    suffix = id(db)
    company = Company(name=f"Absence Co {suffix}")
    db.add(company)
    db.flush()
    branch = Branch(name=f"Absence Branch {suffix}", code=f"AB{suffix}", company_id=company.id)
    db.add(branch)
    db.flush()
    department = Department(name=f"Operations {suffix}", code=f"OPS{suffix}", branch_id=branch.id)
    db.add(department)
    db.flush()
    role = Role(name=f"absence_role_{suffix}", description="Absence role")
    db.add(role)
    db.flush()

    user = User(email=f"absence_employee_{suffix}@test.com", hashed_password=get_password_hash("Test@123"), is_active=True, role_id=role.id)
    teammate_user = User(email=f"absence_teammate_{suffix}@test.com", hashed_password=get_password_hash("Test@123"), is_active=True, role_id=role.id)
    db.add_all([user, teammate_user])
    db.flush()
    employee = Employee(employee_id=f"ABSE{suffix}", first_name="Absence", last_name="Employee", date_of_joining=date(2023, 1, 1), user_id=user.id, branch_id=branch.id, department_id=department.id)
    teammate = Employee(employee_id=f"ABST{suffix}", first_name="Absent", last_name="Teammate", date_of_joining=date(2023, 1, 1), user_id=teammate_user.id, branch_id=branch.id, department_id=department.id)
    db.add_all([employee, teammate])
    db.flush()
    leave_type = LeaveType(name=f"Sick Leave {suffix}", code=f"SL{suffix}", days_allowed=Decimal("10"))
    db.add(leave_type)
    db.flush()
    db.add(LeaveRequest(employee_id=teammate.id, leave_type_id=leave_type.id, from_date=date.today(), to_date=date.today(), days_count=Decimal("1"), status="Approved", is_half_day=True))
    db.commit()

    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Test@123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    department_response = client.get(
        "/api/v1/leave/department-calendar",
        params={"department_id": str(department.id), "from_date": str(date.today()), "to_date": str(date.today())},
        headers=headers,
    )
    assert department_response.status_code == 200
    assert department_response.json()[0]["employee_id"] == teammate.id
    assert department_response.json()[0]["leaves"][0]["is_half_day"] is True

    today_response = client.get("/api/v1/leave/today-absences", headers=headers)
    assert today_response.status_code == 200
    assert [item["employee_id"] for item in today_response.json()] == [teammate.id]


def test_leave_request_blocks_overlap(client, db):
    emp, lt, user = _create_employee_with_leave(db, client, {})

    login_resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Test@123"})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    first_from = (date.today() + timedelta(days=10)).isoformat()
    first_to = (date.today() + timedelta(days=12)).isoformat()
    first = client.post("/api/v1/leave/apply", json={
        "leave_type_id": lt.id,
        "from_date": first_from,
        "to_date": first_to,
        "reason": "Planned leave",
    }, headers=headers)
    assert first.status_code == 201

    overlap = client.post("/api/v1/leave/apply", json={
        "leave_type_id": lt.id,
        "from_date": (date.today() + timedelta(days=11)).isoformat(),
        "to_date": (date.today() + timedelta(days=13)).isoformat(),
        "reason": "Overlapping leave",
    }, headers=headers)
    assert overlap.status_code == 400
    assert "overlap" in overlap.json()["detail"].lower()


def test_leave_request_requires_allocated_balance(client, db):
    from app.models.employee import Employee
    from app.models.leave import LeaveType
    from app.models.user import Role, User
    from app.core.security import get_password_hash

    role = Role(name=f"no_balance_role_{id(db)}", description="Employee", is_system=False)
    db.add(role)
    db.flush()
    user = User(
        email=f"nobalance_{id(db)}@test.com",
        hashed_password=get_password_hash("Test@123"),
        is_active=True,
        role_id=role.id,
    )
    db.add(user)
    db.flush()
    emp = Employee(
        employee_id=f"NOBAL{id(db)}",
        first_name="No",
        last_name="Balance",
        date_of_joining=date(2023, 1, 1),
        user_id=user.id,
    )
    db.add(emp)
    db.flush()
    lt = LeaveType(name="Privilege Leave", code=f"PL{id(db)}", days_allowed=Decimal("12"))
    db.add(lt)
    db.commit()

    login_resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Test@123"})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    response = client.post("/api/v1/leave/apply", json={
        "leave_type_id": lt.id,
        "from_date": (date.today() + timedelta(days=5)).isoformat(),
        "to_date": (date.today() + timedelta(days=5)).isoformat(),
        "reason": "No balance",
    }, headers=headers)
    assert response.status_code == 400
    assert "no leave balance" in response.json()["detail"].lower()


def test_leave_ledger_tracks_apply_and_cancel(client, db):
    from app.models.leave import LeaveBalance

    emp, lt, user = _create_employee_with_leave(db, client, {})

    login_resp = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Test@123"})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    apply_resp = client.post("/api/v1/leave/apply", json={
        "leave_type_id": lt.id,
        "from_date": (date.today() + timedelta(days=20)).isoformat(),
        "to_date": (date.today() + timedelta(days=21)).isoformat(),
        "reason": "Track ledger",
    }, headers=headers)
    assert apply_resp.status_code == 201
    request_id = apply_resp.json()["id"]

    ledger = client.get("/api/v1/leave/ledger", headers=headers)
    assert ledger.status_code == 200
    assert ledger.json()[0]["transaction_type"] == "request_pending"
    assert ledger.json()[0]["amount"] == "-2.0"
    assert ledger.json()[0]["balance_after"] == "19.0"

    cancel = client.put(f"/api/v1/leave/requests/{request_id}/cancel", headers=headers)
    assert cancel.status_code == 200

    ledger_after_cancel = client.get("/api/v1/leave/ledger", headers=headers)
    assert ledger_after_cancel.status_code == 200
    assert ledger_after_cancel.json()[0]["transaction_type"] == "request_cancelled"
    assert ledger_after_cancel.json()[0]["balance_after"] == "21.0"

    balance = db.query(LeaveBalance).filter_by(employee_id=emp.id, leave_type_id=lt.id).first()
    assert balance.pending == Decimal("0")
