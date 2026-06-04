from datetime import date
from decimal import Decimal

from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveRequest, LeaveType
from app.models.payroll import EmployeeSalary, LeaveEncashmentRequest, PayrollLWPEntry, PayrollPeriod, PayrollRecord
from tests.payroll_test_utils import ensure_payroll_ready


def _employee(db, code: str = "LP-001") -> Employee:
    employee = Employee(
        employee_id=code,
        first_name="Leave",
        last_name="Payroll",
        date_of_joining=date(2024, 1, 1),
        status="Active",
    )
    db.add(employee)
    db.flush()
    db.add(
        EmployeeSalary(
            employee_id=employee.id,
            ctc=Decimal("312000"),
            basic=Decimal("13000"),
            hra=Decimal("6500"),
            effective_from=date(2024, 1, 1),
            is_active=True,
        )
    )
    return employee


def test_leave_encashment_request_approval_feeds_payroll(client, db, superuser_headers):
    employee = _employee(db)
    leave_type = LeaveType(
        name="Earned Leave Payroll",
        code="EL-PAY",
        days_allowed=Decimal("24"),
        encashable=True,
        is_active=True,
    )
    db.add(leave_type)
    db.flush()
    db.add(
        LeaveBalance(
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            year=date.today().year,
            allocated=Decimal("12"),
            used=Decimal("2"),
            pending=Decimal("0"),
            carried_forward=Decimal("0"),
        )
    )
    db.commit()

    create = client.post(
        "/api/v1/hrms/leave-encashment/request",
        json={"employeeId": employee.id, "leaveTypeId": leave_type.id, "daysToEncash": 2, "remarks": "Year-end encashment"},
        headers=superuser_headers,
    )
    assert create.status_code == 201, create.text
    request_id = create.json()["id"]
    assert create.json()["amount"] > 0

    approve = client.post(
        f"/api/v1/hrms/leave-encashment/{request_id}/approve",
        json={"remarks": "Approved for payroll"},
        headers=superuser_headers,
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    today = date.today()
    ensure_payroll_ready(db, today.month, today.year, employees=[employee])
    run = client.post("/api/v1/payroll/run", json={"month": today.month, "year": today.year}, headers=superuser_headers)
    assert run.status_code == 201, run.text

    stored = db.query(LeaveEncashmentRequest).filter_by(id=request_id).first()
    assert stored.status == "paid"
    assert stored.payroll_run_id == run.json()["id"]
    record = db.query(PayrollRecord).filter_by(payroll_run_id=run.json()["id"], employee_id=employee.id).first()
    assert Decimal(str(record.gross_salary)) > Decimal("26000")


def test_lwp_feed_sync_creates_payroll_deduction_input(client, db, superuser_headers):
    employee = _employee(db, "LP-002")
    leave_type = LeaveType(
        name="Leave Without Pay",
        code="LWP-PAY",
        days_allowed=Decimal("30"),
        encashable=False,
        is_active=True,
    )
    db.add(leave_type)
    db.flush()
    today = date.today()
    db.add(
        LeaveRequest(
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            from_date=today,
            to_date=today,
            days_count=Decimal("1"),
            reason="Unpaid leave",
            status="Approved",
        )
    )
    db.commit()
    month = f"{today.year:04d}-{today.month:02d}"

    feed = client.get("/api/v1/hrms/payroll/lwp-feed", params={"month": month}, headers=superuser_headers)
    assert feed.status_code == 200, feed.text
    assert any(row["employeeId"] == employee.id and row["lwpDays"] >= 1 for row in feed.json()["preview"])

    sync = client.post("/api/v1/hrms/payroll/lwp-sync", json={"month": month}, headers=superuser_headers)
    assert sync.status_code == 200, sync.text
    assert sync.json()["synced"] >= 1
    period = db.query(PayrollPeriod).filter_by(month=today.month, year=today.year).first()
    assert period is not None
    ensure_payroll_ready(db, today.month, today.year, employees=[employee])

    run = client.post("/api/v1/payroll/run", json={"month": today.month, "year": today.year}, headers=superuser_headers)
    assert run.status_code == 201, run.text
    entry = db.query(PayrollLWPEntry).filter_by(employee_id=employee.id, payroll_month=month).first()
    assert entry.payroll_run_id == run.json()["id"]
    assert Decimal(str(entry.amount_deducted)) > 0
