from datetime import date, datetime, timezone
from decimal import Decimal

from app.db.init_db import init_db
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.payroll import EmployeeSalary, PayrollComponent, Reimbursement
from tests.payroll_test_utils import ensure_payroll_ready


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_attendance_for_weekdays(db, employee_id: int, month: int, year: int):
    for day in range(1, 32):
        try:
            work_date = date(year, month, day)
        except ValueError:
            continue
        if work_date.weekday() >= 5:
            continue
        db.add(Attendance(
            employee_id=employee_id,
            attendance_date=work_date,
            check_in=datetime(year, month, day, 9, 0, tzinfo=timezone.utc),
            check_out=datetime(year, month, day, 18, 0, tzinfo=timezone.utc),
            status="Present",
        ))
    db.commit()


def test_payroll_run_persists_component_lines_and_rich_payslip(client, db):
    init_db(db)
    admin_headers = _login(client, "admin@aihrms.com", "Admin@123456")
    employee_headers = _login(client, "employee@aihrms.com", "Employee@123456")
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()

    db.add(EmployeeSalary(
        employee_id=employee.id,
        ctc=Decimal("600000"),
        basic=Decimal("20000"),
        hra=Decimal("10000"),
        effective_from=date(2026, 5, 1),
        is_active=True,
    ))
    db.add(Reimbursement(
        employee_id=employee.id,
        category="Travel",
        amount=Decimal("1250"),
        date=date(2026, 5, 10),
        description="Client visit",
        status="Approved",
    ))
    db.commit()
    _seed_attendance_for_weekdays(db, employee.id, 5, 2026)
    ensure_payroll_ready(db, 5, 2026)

    run = client.post("/api/v1/payroll/run", json={"month": 5, "year": 2026}, headers=admin_headers)
    assert run.status_code == 201
    run_id = run.json()["id"]

    records = client.get(f"/api/v1/payroll/runs/{run_id}/records", headers=admin_headers)
    assert records.status_code == 200
    record = next(item for item in records.json() if item["employee_id"] == employee.id)

    lines = db.query(PayrollComponent).filter(PayrollComponent.record_id == record["id"]).all()
    names = {line.component_name for line in lines}
    assert {"Basic", "House Rent Allowance", "PF Employee", "PF Employer", "Approved Reimbursements"}.issubset(names)

    payslip = client.get("/api/v1/payroll/payslip?month=5&year=2026", headers=employee_headers)
    assert payslip.status_code == 200
    data = payslip.json()
    assert data["month"] == 5
    assert data["year"] == 2026
    assert data["employee"]["employee_id"] == "DEMO-EMP-001"
    assert any(item["component_name"] == "Basic" for item in data["earnings"])
    assert any(item["component_name"] == "PF Employee" for item in data["deductions"])
    assert any(item["component_name"] == "PF Employer" for item in data["employer_contributions"])
    assert any(item["component_name"] == "Approved Reimbursements" for item in data["reimbursements"])
    assert Decimal(str(data["ytd"]["net_salary"])) == Decimal(str(data["net_salary"]))
