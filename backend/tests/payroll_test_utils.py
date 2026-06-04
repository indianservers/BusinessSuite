from datetime import date
from decimal import Decimal
import calendar

from app.models.employee import Employee
from app.models.payroll import EmployeeSalary, EmployeeStatutoryProfile, PayrollPayGroup, PayrollPeriod


def ensure_payroll_ready(db, month: int, year: int, employees: list[Employee] | None = None) -> PayrollPeriod:
    employees = employees or db.query(Employee).filter(
        Employee.deleted_at.is_(None),
        Employee.status.in_(["Active", "Probation", "Resigned"]),
    ).all()
    for index, employee in enumerate(employees, start=1):
        if not db.query(EmployeeSalary).filter(
            EmployeeSalary.employee_id == employee.id,
            EmployeeSalary.is_active == True,
        ).first():
            db.add(EmployeeSalary(
                employee_id=employee.id,
                ctc=Decimal("600000"),
                basic=Decimal("20000"),
                hra=Decimal("10000"),
                effective_from=date(year, month, 1),
                is_active=True,
            ))
        employee.bank_name = employee.bank_name or "HDFC Bank"
        employee.account_number = employee.account_number or f"123456789{index}"
        employee.ifsc_code = employee.ifsc_code or "HDFC0001234"
        employee.pan_number = employee.pan_number or f"ABCDE{1230 + index}F"
        employee.uan_number = employee.uan_number or f"{100200300400 + index:012d}"
        employee.esic_number = employee.esic_number or f"ESIC{12340 + index}"
        statutory_profile = db.query(EmployeeStatutoryProfile).filter(
            EmployeeStatutoryProfile.employee_id == employee.id,
        ).first()
        if not statutory_profile:
            statutory_profile = EmployeeStatutoryProfile(employee_id=employee.id)
            db.add(statutory_profile)
        statutory_profile.uan = statutory_profile.uan or employee.uan_number
        statutory_profile.pf_applicable = True
        statutory_profile.pension_applicable = True
        statutory_profile.esi_ip_number = statutory_profile.esi_ip_number or employee.esic_number
        statutory_profile.esi_applicable = True

    pay_group = db.query(PayrollPayGroup).filter(PayrollPayGroup.code == "TEST-PAY").first()
    if not pay_group:
        pay_group = PayrollPayGroup(name="Test Payroll", code="TEST-PAY", state="Telangana", is_default=True)
        db.add(pay_group)
        db.flush()

    period = db.query(PayrollPeriod).filter(
        PayrollPeriod.month == month,
        PayrollPeriod.year == year,
    ).order_by(PayrollPeriod.id.desc()).first()
    if not period:
        period_start = date(year, month, 1)
        period_end = date(year, month, calendar.monthrange(year, month)[1])
        period = PayrollPeriod(
            pay_group_id=pay_group.id,
            month=month,
            year=year,
            financial_year=f"{year}-{str(year + 1)[-2:]}",
            period_start=period_start,
            period_end=period_end,
            payroll_date=period_end,
        )
        db.add(period)
    period.status = "Locked"
    db.commit()
    return period
