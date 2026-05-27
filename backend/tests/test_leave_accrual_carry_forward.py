from datetime import date
from decimal import Decimal

from app.crud.crud_leave import get_leave_balance, run_leave_carry_forward, run_scheduled_leave_accruals
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveBalanceLedger, LeaveType


def test_scheduled_leave_accrual_is_idempotent(db):
    employee = Employee(
        employee_id="EMP-ACCRUAL",
        first_name="Accrual",
        last_name="User",
        date_of_joining=date(2025, 1, 1),
        status="Active",
    )
    leave_type = LeaveType(
        name="Earned Leave",
        code="EL-ACCRUAL",
        days_allowed=Decimal("12"),
        accrual_frequency="monthly",
        carry_forward=True,
        carry_forward_limit=Decimal("6"),
    )
    db.add_all([employee, leave_type])
    db.commit()

    first = run_scheduled_leave_accruals(db, run_date=date(2026, 5, 23), created_by=1)
    second = run_scheduled_leave_accruals(db, run_date=date(2026, 5, 23), created_by=1)

    balance = get_leave_balance(db, employee.id, leave_type.id, 2026)
    assert first["credited"] == 1
    assert second["credited"] == 0
    assert balance.allocated == Decimal("1.0")
    assert db.query(LeaveBalanceLedger).filter_by(transaction_type="scheduled_accrual").count() == 1


def test_leave_carry_forward_respects_limit_and_is_idempotent(db):
    employee = Employee(
        employee_id="EMP-CARRY",
        first_name="Carry",
        last_name="User",
        date_of_joining=date(2025, 1, 1),
        status="Active",
    )
    leave_type = LeaveType(
        name="Carry Leave",
        code="CL-CARRY",
        days_allowed=Decimal("12"),
        accrual_frequency="annual",
        carry_forward=True,
        carry_forward_limit=Decimal("5"),
    )
    db.add_all([employee, leave_type])
    db.flush()
    db.add(
        LeaveBalance(
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            year=2025,
            allocated=Decimal("10"),
            used=Decimal("2"),
            pending=Decimal("0"),
            carried_forward=Decimal("0"),
        )
    )
    db.commit()

    first = run_leave_carry_forward(db, from_year=2025, to_year=2026, created_by=1)
    second = run_leave_carry_forward(db, from_year=2025, to_year=2026, created_by=1)

    balance = get_leave_balance(db, employee.id, leave_type.id, 2026)
    assert first["carried"] == 1
    assert second["carried"] == 0
    assert balance.carried_forward == Decimal("5.0")
    assert db.query(LeaveBalanceLedger).filter_by(transaction_type="carry_forward").count() == 1
