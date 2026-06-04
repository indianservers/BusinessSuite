from datetime import date

from app.db.init_db import init_db
from app.models.audit import AuditLog
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveType
from app.models.payroll import EmployeeLoan, FullFinalSettlement, Reimbursement


def _login(client, email: str, password: str):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_employee_ess_summary_includes_attendance_leave_and_claims(client, db):
    init_db(db)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee

    leave_type = LeaveType(name="Casual Leave UAT", code="CL-UAT", days_allowed=12, accrual_frequency="annual")
    db.add(leave_type)
    db.flush()
    db.add(LeaveBalance(
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        year=date.today().year,
        allocated=12,
        used=2,
        pending=1,
        carried_forward=1,
    ))
    db.add(Attendance(employee_id=employee.id, attendance_date=date.today(), status="Half-day", total_hours=4))
    db.add(Reimbursement(employee_id=employee.id, category="Travel", amount=750, date=date.today(), status="Pending"))
    db.commit()

    headers = _login(client, "employee@aihrms.com", "Employee@123456")
    response = client.get("/api/v1/reports/ess-summary", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["employee"]["id"] == employee.id
    assert data["attendance"]["summary"]["present"] == 0.5
    assert data["leave_balances"][0]["available"] == 10
    assert data["claims"][0]["status"] == "Pending"


def test_hrms_named_operational_reports(client, db, superuser_headers):
    init_db(db)
    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    assert employee
    db.add(Reimbursement(employee_id=employee.id, category="Medical", amount=500, date=date.today(), status="Approved"))
    db.add(EmployeeLoan(
        employee_id=employee.id,
        loan_type="Employee Loan",
        principal_amount=10000,
        total_payable=10000,
        emi_amount=1000,
        start_month=date.today().month,
        start_year=date.today().year,
        tenure_months=10,
        balance_amount=9000,
        status="Active",
    ))
    db.add(FullFinalSettlement(
        employee_id=employee.id,
        settlement_date=date.today(),
        last_working_date=date.today(),
        status="Draft",
        net_payable=2500,
    ))
    db.add(AuditLog(method="PUT", endpoint="/api/v1/employees/1", status_code=200, entity_type="Employee", entity_id=employee.id, action="UPDATE"))
    db.commit()

    for path in [
        "/api/v1/reports/employee-report",
        "/api/v1/reports/reimbursement-report",
        "/api/v1/reports/loan-outstanding-report",
        "/api/v1/reports/fnf-report",
        "/api/v1/reports/audit-log-report",
    ]:
        response = client.get(path, headers=superuser_headers)
        assert response.status_code == 200, path
        assert "items" in response.json()
