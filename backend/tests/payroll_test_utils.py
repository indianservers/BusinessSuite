from datetime import date
from decimal import Decimal
import calendar
from sqlalchemy import cast, String

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
    if db.info.get("payroll_fixture_recorder"):
        commit_payroll_fixture(db)
    else:
        db.commit()
    return period


def init_payroll_test_db(db, **kwargs):
    """Seed valid company/module setup without satisfying period readiness."""
    from app.db.init_db import init_db
    from app.models.company import Company, Branch
    from app.models.payroll import SalaryComponent
    from app.branches.models import BranchOwnership
    from app.branches.migration import backfill

    init_db(db, **kwargs)
    if not db.info.get("payroll_fixture_recorder"):
        from sqlalchemy import event
        def remember_fixture_rows(session, *_):
            if session.info.get("branch_context") is None:
                session.info.setdefault("payroll_fixture_rows", set()).update(session.new)
        event.listen(db, "before_flush", remember_fixture_rows)
        db.info["payroll_fixture_recorder"] = True
    for company in db.query(Company).all():
        backfill(db.connection(), company.id, table_names={"branches", "departments", "designations", "employees"})
        company.email = company.email or f"payroll-{company.id}@example.com"
        company.country = company.country or "India"
        branch = db.query(Branch).filter_by(company_id=company.id, is_active=True).order_by(Branch.id).first()
        if branch is None:
            continue
        owned = db.query(SalaryComponent).join(BranchOwnership,
            (BranchOwnership.resource_table == SalaryComponent.__tablename__) &
            (BranchOwnership.resource_key == cast(SalaryComponent.id, String))
        ).filter(BranchOwnership.company_id == company.id, SalaryComponent.is_active.is_(True)).first()
        if owned is None:
            component = SalaryComponent(name="Payroll setup allowance", code=f"SETUP-{company.id}",
                                        component_type="Earning", amount=0, is_active=True)
            db.add(component)
            db.flush()
            db.add(BranchOwnership(resource_table=SalaryComponent.__tablename__, resource_key=str(component.id),
                                   company_id=company.id, branch_id=branch.id, source="payroll-test-setup"))
    commit_payroll_fixture(db)


def commit_payroll_fixture(db):
    """Give directly seeded test rows explicit, validated branch ownership."""
    from sqlalchemy import inspect, select
    from fastapi import HTTPException
    from app.models.company import Branch, Company
    from app.branches.models import BranchOwnership
    from app.branches.catalog import SHARED, resource_key
    from app.branches.boundary import branch_for_row
    from app.db.base_class import Base

    company = db.query(Company).filter_by(name="Demo Company").one()
    branch = db.query(Branch).filter_by(company_id=company.id, is_active=True).order_by(Branch.id).first()
    assert branch is not None
    assert db.info.get("branch_context") is None, "Fixture seeding must run outside API requests"
    candidates = set(db.new) | db.info.get("payroll_fixture_rows", set())
    for item in candidates:
        if inspect(item).deleted or item in db.deleted:
            continue
        table = inspect(item).mapper.local_table
        if table.name in SHARED:
            continue
        for field in ("company_id", "organization_id"):
            if field in table.c and getattr(item, field) is None:
                setattr(item, field, company.id)
        if "branch_id" in table.c and getattr(item, "branch_id") is None:
            if any(fk.column.table.name == "branches" for fk in table.c.branch_id.foreign_keys):
                item.branch_id = branch.id
    db.flush()
    candidates.update(db.info.pop("payroll_fixture_rows", set()))
    pending = []
    owner = BranchOwnership.__table__
    for item in candidates:
        if inspect(item).deleted or item in db.deleted:
            continue
        table = inspect(item).mapper.local_table
        if table.name in SHARED:
            continue
        key = resource_key(table, {c.name: getattr(item, c.name) for c in table.primary_key})
        if not db.connection().execute(select(owner.c.resource_key).where(
                owner.c.resource_table == table.name, owner.c.resource_key == key)).first():
            pending.append((item, table, key))
    while pending:
        deferred = []
        last_error = None
        for item, table, key in pending:
            values = {c.name: getattr(item, c.name) for c in table.c}
            try:
                branches = branch_for_row(db.connection(), table, values, company.id, Base.metadata.tables, branch.id)
            except HTTPException as error:
                last_error = error
                deferred.append((item, table, key))
                continue
            assert len(branches) <= 1, "Fixture links records from different branches"
            destination = next(iter(branches), branch.id)
            assert db.get(Branch, destination).company_id == company.id
            db.connection().execute(owner.insert().values(resource_table=table.name, resource_key=key,
                company_id=company.id, branch_id=destination, source="payroll-test-fixture"))
        if deferred and len(deferred) == len(pending):
            raise last_error
        pending = deferred
    db.commit()
