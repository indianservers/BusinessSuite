from datetime import date
from decimal import Decimal

from app.db.init_db import init_db
from app.models.attendance import Attendance
from app.models.company import Department
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary, PayrollPayGroup, PayrollPeriod, PayrollRecord
from tests.payroll_test_utils import ensure_payroll_ready


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@aihrms.com", "password": "Admin@123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _pay_group_period(db, code: str, month: int, year: int, **pay_group_kwargs):
    pay_group = PayrollPayGroup(name=f"{code} Payroll", code=code, **pay_group_kwargs)
    db.add(pay_group)
    db.flush()
    period = PayrollPeriod(
        pay_group_id=pay_group.id,
        month=month,
        year=year,
        financial_year=f"{year}-{str(year + 1)[-2:]}",
        period_start=date(year, month, 1),
        period_end=date(year, month, 31),
        payroll_date=date(year, month, 31),
        status="Locked",
    )
    db.add(period)
    db.commit()
    return pay_group


def _salary(db, employee_id: int, *, ctc="600000", basic="20000", hra="10000", payroll_type="monthly_fixed", wage_rate="0", default_units="0", effective_from=date(2026, 5, 1)):
    db.add(EmployeeSalary(
        employee_id=employee_id,
        ctc=Decimal(ctc),
        basic=Decimal(basic) if basic is not None else None,
        hra=Decimal(hra) if hra is not None else None,
        payroll_type=payroll_type,
        wage_rate=Decimal(wage_rate),
        default_units=Decimal(default_units),
        effective_from=effective_from,
        is_active=True,
    ))
    db.commit()


def test_raw_half_day_attendance_counts_as_half_day(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    _salary(db, employee.id)
    ensure_payroll_ready(db, 5, 2026)

    for day in range(1, 30):
        work_date = date(2026, 5, day)
        if work_date.weekday() < 5:
            db.add(Attendance(employee_id=employee.id, attendance_date=work_date, status="Half-day" if day == 1 else "Present"))
    db.commit()

    response = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=headers)
    assert response.status_code == 201, response.json()
    record = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == response.json()["id"], PayrollRecord.employee_id == employee.id).first()
    assert record.working_days == 21
    assert record.present_days == Decimal("20.5")
    assert record.paid_days == Decimal("20.5")
    assert record.lop_days == Decimal("0.5")
    assert record.gross_salary == Decimal("48809.52")


def test_six_day_retail_calendar_does_not_leak_to_next_run(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    _salary(db, employee.id)
    retail_group = _pay_group_period(db, "RETAIL6", 5, 2026, branch_id=employee.branch_id, working_pattern="6_day", working_days_per_week=6)
    ensure_payroll_ready(db, 5, 2026)

    retail = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026, "pay_group_id": retail_group.id, "branch_id": employee.branch_id}, headers=headers)
    assert retail.status_code == 201, retail.json()
    retail_record = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == retail.json()["id"], PayrollRecord.employee_id == employee.id).first()
    assert retail_record.working_days == 26

    office = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=headers)
    assert office.status_code == 201, office.json()
    office_record = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == office.json()["id"], PayrollRecord.employee_id == employee.id).first()
    assert office_record.working_days == 21


def test_visiting_faculty_per_lecture_payroll(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    employee.employment_type = "Visiting"
    _salary(db, employee.id, ctc="0", basic=None, hra=None, payroll_type="per_lecture", wage_rate="1200", default_units="10")
    ensure_payroll_ready(db, 5, 2026, [employee])

    response = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026, "employee_category": "Visiting"}, headers=headers)
    assert response.status_code == 201, response.json()
    record = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == response.json()["id"], PayrollRecord.employee_id == employee.id).first()
    assert record.gross_salary == Decimal("12000.00")
    assert any(component.component_name == "Per Lecture Pay" and component.amount == Decimal("12000.00") for component in record.components)


def test_mid_month_joining_and_exit_are_prorated(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    employee.date_of_joining = date(2026, 5, 16)
    employee.date_of_exit = date(2026, 5, 25)
    employee.functional_area = "MidMonthQA"
    _salary(db, employee.id)
    ensure_payroll_ready(db, 5, 2026, [employee])

    response = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026, "employee_category": "MidMonthQA"}, headers=headers)
    assert response.status_code == 201, response.json()
    record = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == response.json()["id"], PayrollRecord.employee_id == employee.id).first()
    assert record.gross_salary == Decimal("16129.03")


def test_department_scoped_run_only_includes_department_employees(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    target_dept = Department(name="Scoped Teaching", code="SCTEA", branch_id=employee.branch_id)
    other_dept = Department(name="Scoped Finance", code="SCFIN", branch_id=employee.branch_id)
    db.add_all([target_dept, other_dept])
    db.flush()
    employee.department_id = target_dept.id
    other_employee = Employee(
        employee_id="SCOPE-OTHER",
        first_name="Scope",
        last_name="Other",
        date_of_joining=date(2024, 1, 1),
        branch_id=employee.branch_id,
        department_id=other_dept.id,
        status="Active",
    )
    db.add(other_employee)
    db.commit()
    _salary(db, employee.id)
    _salary(db, other_employee.id)
    ensure_payroll_ready(db, 5, 2026, [employee, other_employee])

    response = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026, "department_id": target_dept.id}, headers=headers)
    assert response.status_code == 201, response.json()
    employee_ids = {row.employee_id for row in db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == response.json()["id"]).all()}
    assert employee.id in employee_ids
    assert other_employee.id not in employee_ids


def test_locked_payroll_still_blocks_salary_mutation(client, db):
    init_db(db)
    headers = _login(client)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    locked = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026, "force_run": True}, headers=headers)
    assert locked.status_code == 201
    approved = client.put(f"/api/v1/payroll/runs/{locked.json()['id']}/approve", json={"action": "approve", "force_approve": True}, headers=headers)
    assert approved.status_code == 200
    lock = client.put(f"/api/v1/payroll/runs/{locked.json()['id']}/approve", json={"action": "lock"}, headers=headers)
    assert lock.status_code == 200

    blocked = client.post(
        "/api/v1/payroll/salary",
        json={"employee_id": employee.id, "ctc": "600000", "basic": "20000", "hra": "10000", "effective_from": "2026-05-01"},
        headers=headers,
    )
    assert blocked.status_code == 400
