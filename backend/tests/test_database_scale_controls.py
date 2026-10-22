from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import inspect

from app.crud.crud_payroll import get_prorated_salary_for_period
from app.models.employee import Employee
from app.models.leave import LeaveRequest, LeaveType
from app.models.payroll import EmployeeSalary, PayrollRun, SalaryComponent


def test_database_scale_indexes_and_columns_exist(db_engine):
    inspector = inspect(db_engine)

    expected_indexes = {
        "attendances": "idx_attendance_employee_date",
        "leave_requests": "idx_leave_request_company_active_status",
        "payroll_runs": "idx_payroll_run_company_active_month",
        "notifications": "idx_notifications_company_user_unread",
        "audit_logs": "idx_audit_log_entity",
    }
    for table_name, index_name in expected_indexes.items():
        indexes = {item["name"] for item in inspector.get_indexes(table_name)}
        assert index_name in indexes

    employee_columns = {item["name"] for item in inspector.get_columns("employees")}
    assert {"salary_currency", "deleted_at", "deleted_by"}.issubset(employee_columns)

    leave_request_columns = {item["name"] for item in inspector.get_columns("leave_requests")}
    assert "company_id" in leave_request_columns

    payroll_run_columns = {item["name"] for item in inspector.get_columns("payroll_runs")}
    assert {"pay_period_start", "pay_period_end", "company_id", "deleted_at", "deleted_by"}.issubset(payroll_run_columns)

    notification_columns = {item["name"] for item in inspector.get_columns("notifications")}
    assert "company_id" in notification_columns

    audit_columns = {item["name"] for item in inspector.get_columns("audit_logs")}
    assert {"ip_address", "user_agent"}.issubset(audit_columns)


def test_soft_deleted_employee_leave_and_payroll_are_filtered(db):
    leave_type = LeaveType(name="Soft delete test leave", code="SOFT", days_allowed=12)
    db.add(leave_type)
    db.flush()
    employee = Employee(
        employee_id="SOFT-001",
        first_name="Soft",
        last_name="Deleted",
        date_of_joining=date(2026, 1, 1),
        deleted_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    db.add(employee)
    db.flush()
    db.add(LeaveRequest(
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        from_date=date(2026, 5, 4),
        to_date=date(2026, 5, 4),
        days_count=Decimal("1"),
        deleted_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    ))
    db.add(PayrollRun(month=5, year=2026, status="Completed", deleted_at=datetime(2026, 5, 1, tzinfo=timezone.utc)))
    db.commit()

    assert db.query(Employee).filter(Employee.deleted_at.is_(None), Employee.employee_id == "SOFT-001").first() is None
    assert db.query(LeaveRequest).filter(LeaveRequest.deleted_at.is_(None)).count() == 0
    assert db.query(PayrollRun).filter(PayrollRun.deleted_at.is_(None)).count() == 0


def test_salary_effective_date_prorates_mid_month(db):
    employee = Employee(
        employee_id="SAL-PRORATE-001",
        first_name="Salary",
        last_name="Prorate",
        date_of_joining=date(2026, 1, 1),
        salary_currency="USD",
    )
    db.add(employee)
    db.flush()
    db.add(EmployeeSalary(
        employee_id=employee.id,
        ctc=Decimal("600000"),
        basic=Decimal("20000"),
        hra=Decimal("10000"),
        effective_from=date(2026, 5, 1),
        effective_date=date(2026, 5, 1),
        effective_to=date(2026, 5, 14),
        is_active=False,
    ))
    db.add(EmployeeSalary(
        employee_id=employee.id,
        ctc=Decimal("1200000"),
        basic=Decimal("40000"),
        hra=Decimal("20000"),
        effective_from=date(2026, 5, 15),
        effective_date=date(2026, 5, 15),
        is_active=True,
    ))
    db.add(SalaryComponent(name="Global Allowance", code="GLB_ALLOW", component_type="Earning", is_currency_fixed=False))
    db.commit()

    monthly_ctc, basic, hra = get_prorated_salary_for_period(db, employee.id, date(2026, 5, 1), date(2026, 5, 31))

    assert monthly_ctc == Decimal("77419.35")
    assert basic == Decimal("30967.74")
    assert hra == Decimal("15483.87")
    assert db.query(Employee).filter_by(employee_id="SAL-PRORATE-001").first().salary_currency == "USD"
    assert db.query(SalaryComponent).filter_by(code="GLB_ALLOW").first().is_currency_fixed is False
