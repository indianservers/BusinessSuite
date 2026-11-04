from tests.rich_text_test_utils import organization_context
from datetime import date
from decimal import Decimal

from app.models.employee import Employee
from app.models.exit import ExitChecklistItem, ExitRecord
from app.models.leave import LeaveBalance, LeaveType
from app.models.payroll import EmployeeLoan, EmployeeSalary, Reimbursement


def test_fnf_settlement_generation_and_approval_flow(client, superuser_headers, db):
    employee = Employee(
        employee_id="FNF001",
        first_name="Final",
        last_name="Tester",
        date_of_joining=date(2018, 1, 1),
    )
    db.add(employee)
    db.flush()

    db.add(
        EmployeeSalary(
            employee_id=employee.id,
            ctc=Decimal("1200000"),
            basic=Decimal("40000"),
            hra=Decimal("20000"),
            effective_from=date(2024, 1, 1),
            is_active=True,
        )
    )
    leave_type = LeaveType(
        name="Earned Leave",
        code="ELFNF",
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
            year=2026,
            allocated=Decimal("10"),
            used=Decimal("2"),
            pending=Decimal("0"),
            carried_forward=Decimal("1"),
        )
    )
    db.add(
        EmployeeLoan(
            employee_id=employee.id,
            principal_amount=Decimal("50000"),
            total_payable=Decimal("50000"),
            emi_amount=Decimal("5000"),
            start_month=1,
            start_year=2026,
            tenure_months=10,
            balance_amount=Decimal("15000"),
            status="Active",
        )
    )
    db.add(
        Reimbursement(
            employee_id=employee.id,
            category="Travel",
            amount=Decimal("2500"),
            date=date(2026, 4, 30),
            status="Approved",
        )
    )
    exit_record = ExitRecord(
        employee_id=employee.id,
        exit_type="Resignation",
        resignation_date=date(2026, 5, 1),
        last_working_date=date(2026, 5, 20),
        notice_period_days=30,
        notice_waived=False,
        reason="Personal",
        status="Initiated",
    )
    db.add(exit_record)
    db.flush()
    db.add(ExitChecklistItem(exit_record_id=exit_record.id, task_name="Laptop return", is_completed=True))
    db.commit()

    generated = client.post(
        "/api/v1/hrms/fnf-settlements/generate",
        json={
            "employee_id": employee.id,
            "exit_id": exit_record.id,
            "last_working_date": "2026-05-20",
            "exit_reason": "Personal",
        },
        headers=superuser_headers,
    )
    assert generated.status_code == 200, generated.text
    settlement = generated.json()
    assert settlement["settlementStatus"] == "draft"
    assert settlement["unpaidSalary"] > 0
    assert settlement["leaveEncashment"] > 0
    assert settlement["loanRecovery"] == 15000
    assert settlement["reimbursementPayable"] == 2500
    assert settlement["clearanceStatus"]["status"] == "cleared"

    settlement_id = settlement["id"]
    submitted = client.post(f"/api/v1/hrms/fnf-settlements/{settlement_id}/submit", headers=superuser_headers)
    assert submitted.status_code == 200
    assert submitted.json()["settlementStatus"] == "pending_approval"

    approved = client.post(f"/api/v1/hrms/fnf-settlements/{settlement_id}/approve", json={"remarks": "Approved"}, headers=superuser_headers)
    assert approved.status_code == 200
    assert approved.json()["settlementStatus"] == "approved"

    pdf = client.get(f"/api/v1/hrms/fnf-settlements/{settlement_id}/pdf", headers=superuser_headers)
    assert pdf.status_code == 200
    assert "application/pdf" in pdf.headers["content-type"]

    paid = client.post(f"/api/v1/hrms/fnf-settlements/{settlement_id}/mark-paid", headers=superuser_headers)
    assert paid.status_code == 200
    assert paid.json()["settlementStatus"] == "paid"
