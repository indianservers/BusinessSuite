from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.payroll import (
    SalaryComponent, SalaryStructure, SalaryStructureComponent,
    EmployeeSalary, PayrollRun, PayrollRecord, PayrollComponent, Reimbursement,
    PayrollVarianceItem, PayrollPeriod, PayrollAttendanceInput,
    OvertimePayLine, LeaveEncashmentLine, LeaveEncashmentRequest, PayrollLWPEntry,
    EmployeeStatutoryProfile, PayrollStatutoryContributionLine,
    PFRule, ESIRule, ProfessionalTaxSlab, LWFSlab, SalaryAdvance, PayrollExchangeRate,
    PayrollCalculationSnapshot, PayrollPreRunCheck,
)
from app.models.expense import ExpenseClaim


PAYROLL_RUN_STATUS_DRAFT = "draft"
PAYROLL_RUN_STATUS_INPUTS_PENDING = "inputs_pending"
PAYROLL_RUN_STATUS_CALCULATED = "calculated"
PAYROLL_RUN_STATUS_APPROVED = "approved"
PAYROLL_RUN_STATUS_LOCKED = "locked"
PAYROLL_RUN_STATUS_PAID = "paid"

PAYROLL_RUN_STATUSES = (
    PAYROLL_RUN_STATUS_DRAFT,
    PAYROLL_RUN_STATUS_INPUTS_PENDING,
    PAYROLL_RUN_STATUS_CALCULATED,
    PAYROLL_RUN_STATUS_APPROVED,
    PAYROLL_RUN_STATUS_LOCKED,
    PAYROLL_RUN_STATUS_PAID,
)

PAYROLL_RUN_TRANSITIONS = {
    PAYROLL_RUN_STATUS_DRAFT: {PAYROLL_RUN_STATUS_INPUTS_PENDING},
    PAYROLL_RUN_STATUS_INPUTS_PENDING: {PAYROLL_RUN_STATUS_CALCULATED, PAYROLL_RUN_STATUS_DRAFT},
    PAYROLL_RUN_STATUS_CALCULATED: {PAYROLL_RUN_STATUS_APPROVED, PAYROLL_RUN_STATUS_INPUTS_PENDING},
    PAYROLL_RUN_STATUS_APPROVED: {PAYROLL_RUN_STATUS_LOCKED, PAYROLL_RUN_STATUS_CALCULATED},
    PAYROLL_RUN_STATUS_LOCKED: {PAYROLL_RUN_STATUS_PAID},
    PAYROLL_RUN_STATUS_PAID: set(),
}

LEGACY_PAYROLL_RUN_STATUS_MAP = {
    "draft": PAYROLL_RUN_STATUS_DRAFT,
    "processing": PAYROLL_RUN_STATUS_INPUTS_PENDING,
    "inputs pending": PAYROLL_RUN_STATUS_INPUTS_PENDING,
    "inputs_pending": PAYROLL_RUN_STATUS_INPUTS_PENDING,
    "completed": PAYROLL_RUN_STATUS_CALCULATED,
    "calculated": PAYROLL_RUN_STATUS_CALCULATED,
    "approved": PAYROLL_RUN_STATUS_APPROVED,
    "locked": PAYROLL_RUN_STATUS_LOCKED,
    "paid": PAYROLL_RUN_STATUS_PAID,
}


def normalize_payroll_run_status(status: str | None) -> str:
    normalized = (status or PAYROLL_RUN_STATUS_DRAFT).strip().lower()
    normalized = LEGACY_PAYROLL_RUN_STATUS_MAP.get(normalized, normalized)
    if normalized not in PAYROLL_RUN_STATUSES:
        raise ValueError(f"Invalid payroll run status '{status}'")
    return normalized


def validate_payroll_run_transition(current_status: str | None, next_status: str) -> tuple[str, str]:
    current = normalize_payroll_run_status(current_status)
    target = normalize_payroll_run_status(next_status)
    if current == target:
        return current, target
    if target not in PAYROLL_RUN_TRANSITIONS[current]:
        allowed = ", ".join(sorted(PAYROLL_RUN_TRANSITIONS[current])) or "no further status"
        raise ValueError(f"Invalid payroll run status transition: {current} -> {target}. Allowed next: {allowed}")
    return current, target


def transition_payroll_run_status(payroll_run: PayrollRun, next_status: str) -> PayrollRun:
    _, target = validate_payroll_run_transition(payroll_run.status, next_status)
    payroll_run.status = target
    return payroll_run


def coerce_payroll_run_status(payroll_run: PayrollRun) -> PayrollRun:
    payroll_run.status = normalize_payroll_run_status(payroll_run.status)
    return payroll_run


def _money(value: Decimal) -> Decimal:
    return (value or Decimal("0")).quantize(Decimal("0.01"))


def _rounded_money(value: Decimal, rule: str | None = "Nearest Rupee") -> Decimal:
    if rule == "No Rounding":
        return _money(value)
    return value.quantize(Decimal("1")).quantize(Decimal("0.01"))


def _active_rule(db: Session, model, on_date: date):
    return db.query(model).filter(
        model.is_active == True,
        model.effective_from <= on_date,
        or_(model.effective_to.is_(None), model.effective_to >= on_date),
    ).order_by(model.effective_from.desc(), model.id.desc()).first()


def _salary_in_slab(salary: Decimal, salary_from: Decimal, salary_to: Decimal | None) -> bool:
    if salary < Decimal(salary_from or 0):
        return False
    return salary_to is None or salary <= Decimal(salary_to)


def _calculate_statutory_amounts(
    db: Session,
    employee_id: int,
    month: int,
    calculation_date: date,
    basic: Decimal,
    gross: Decimal,
) -> tuple[dict[str, Decimal], list[PayrollStatutoryContributionLine]]:
    profile = db.query(EmployeeStatutoryProfile).filter(
        EmployeeStatutoryProfile.employee_id == employee_id,
    ).first()
    amounts = {
        "pf_employee": Decimal("0"),
        "pf_employer": Decimal("0"),
        "esi_employee": Decimal("0"),
        "esi_employer": Decimal("0"),
        "professional_tax": Decimal("0"),
        "lwf_employee": Decimal("0"),
        "lwf_employer": Decimal("0"),
    }
    lines: list[PayrollStatutoryContributionLine] = []

    if not profile or profile.pf_applicable:
        pf_rule = _active_rule(db, PFRule, calculation_date)
        pf_wage_ceiling = Decimal(pf_rule.wage_ceiling or 0) if pf_rule else Decimal("15000")
        pf_employee_rate = Decimal(pf_rule.employee_rate or 0) if pf_rule else Decimal("12")
        pf_employer_rate = Decimal(pf_rule.employer_rate or 0) if pf_rule else Decimal("12")
        pf_rounding_rule = pf_rule.rounding_rule if pf_rule else "Nearest Rupee"
        pf_wage = min(Decimal(basic or 0), pf_wage_ceiling)
        employee_pf = _rounded_money(pf_wage * pf_employee_rate / Decimal("100"), pf_rounding_rule)
        employer_pf = _rounded_money(pf_wage * pf_employer_rate / Decimal("100"), pf_rounding_rule)
        amounts["pf_employee"] = employee_pf
        amounts["pf_employer"] = employer_pf
        lines.append(PayrollStatutoryContributionLine(
            employee_id=employee_id,
            component="PF",
            wage_base=pf_wage,
            employee_amount=employee_pf,
            employer_amount=employer_pf,
            admin_charge=_rounded_money(pf_wage * Decimal(pf_rule.admin_charge_rate or 0) / Decimal("100"), pf_rounding_rule) if pf_rule else Decimal("0.00"),
            edli_amount=_rounded_money(pf_wage * Decimal(pf_rule.edli_rate or 0) / Decimal("100"), pf_rounding_rule) if pf_rule else Decimal("0.00"),
            rule_id=pf_rule.id if pf_rule else None,
            rule_type="PF",
        ))

    if not profile or profile.esi_applicable:
        esi_rule = _active_rule(db, ESIRule, calculation_date)
        esi_wage = Decimal(gross or 0)
        if esi_rule and esi_wage <= Decimal(esi_rule.wage_threshold or 0):
            employee_esi = _rounded_money(esi_wage * Decimal(esi_rule.employee_rate or 0) / Decimal("100"), esi_rule.rounding_rule)
            employer_esi = _rounded_money(esi_wage * Decimal(esi_rule.employer_rate or 0) / Decimal("100"), esi_rule.rounding_rule)
            amounts["esi_employee"] = employee_esi
            amounts["esi_employer"] = employer_esi
            lines.append(PayrollStatutoryContributionLine(
                employee_id=employee_id,
                component="ESI",
                wage_base=esi_wage,
                employee_amount=employee_esi,
                employer_amount=employer_esi,
                rule_id=esi_rule.id,
                rule_type="ESI",
            ))

    state = profile.pt_state if profile else None
    if state:
        pt_slabs = db.query(ProfessionalTaxSlab).filter(
            ProfessionalTaxSlab.is_active == True,
            ProfessionalTaxSlab.state == state,
            ProfessionalTaxSlab.effective_from <= calculation_date,
            or_(ProfessionalTaxSlab.effective_to.is_(None), ProfessionalTaxSlab.effective_to >= calculation_date),
        ).order_by(ProfessionalTaxSlab.salary_from.asc(), ProfessionalTaxSlab.id.asc()).all()
        for slab in pt_slabs:
            if slab.month and slab.month != month:
                continue
            if _salary_in_slab(Decimal(gross or 0), Decimal(slab.salary_from or 0), slab.salary_to):
                amounts["professional_tax"] = _money(Decimal(slab.employee_amount or 0))
                lines.append(PayrollStatutoryContributionLine(
                    employee_id=employee_id,
                    component="PT",
                    wage_base=gross,
                    employee_amount=amounts["professional_tax"],
                    employer_amount=Decimal("0"),
                    rule_id=slab.id,
                    rule_type="PT",
                ))
                break

    if profile and profile.lwf_applicable and state:
        lwf_slabs = db.query(LWFSlab).filter(
            LWFSlab.is_active == True,
            LWFSlab.state == state,
            LWFSlab.effective_from <= calculation_date,
            or_(LWFSlab.effective_to.is_(None), LWFSlab.effective_to >= calculation_date),
        ).order_by(LWFSlab.salary_from.asc(), LWFSlab.id.asc()).all()
        for slab in lwf_slabs:
            if slab.deduction_month and slab.deduction_month != month:
                continue
            if _salary_in_slab(Decimal(gross or 0), Decimal(slab.salary_from or 0), slab.salary_to):
                amounts["lwf_employee"] = _money(Decimal(slab.employee_amount or 0))
                amounts["lwf_employer"] = _money(Decimal(slab.employer_amount or 0))
                lines.append(PayrollStatutoryContributionLine(
                    employee_id=employee_id,
                    component="LWF",
                    wage_base=gross,
                    employee_amount=amounts["lwf_employee"],
                    employer_amount=amounts["lwf_employer"],
                    rule_id=slab.id,
                    rule_type="LWF",
                ))
                break

    return amounts, lines


def get_active_salary(db: Session, employee_id: int) -> Optional[EmployeeSalary]:
    return db.query(EmployeeSalary).filter(
        and_(EmployeeSalary.employee_id == employee_id, EmployeeSalary.is_active == True)
    ).order_by(
        EmployeeSalary.effective_from.desc(),
        EmployeeSalary.id.desc(),
    ).first()


def _salary_effective_from(salary: EmployeeSalary) -> date:
    return salary.effective_date or salary.effective_from


def get_prorated_salary_for_period(
    db: Session,
    employee_id: int,
    period_start: date,
    period_end: date,
) -> tuple[Decimal, Decimal, Decimal]:
    salaries = db.query(EmployeeSalary).filter(
        EmployeeSalary.employee_id == employee_id,
        EmployeeSalary.effective_from <= period_end,
        or_(EmployeeSalary.effective_to.is_(None), EmployeeSalary.effective_to >= period_start),
    ).order_by(
        EmployeeSalary.effective_from.asc(),
        EmployeeSalary.id.asc(),
    ).all()
    if not salaries:
        return Decimal("0"), Decimal("0"), Decimal("0")

    total_days = Decimal(str((period_end - period_start).days + 1))
    monthly_ctc = Decimal("0")
    basic = Decimal("0")
    hra = Decimal("0")

    for salary in salaries:
        segment_start = max(_salary_effective_from(salary), period_start)
        segment_end = min(salary.effective_to or period_end, period_end)
        if segment_end < segment_start:
            continue
        segment_days = Decimal(str((segment_end - segment_start).days + 1))
        weight = segment_days / total_days
        segment_monthly_ctc = Decimal(salary.ctc or 0) / Decimal("12")
        segment_basic = Decimal(salary.basic or 0) or (segment_monthly_ctc * Decimal("0.4"))
        segment_hra = Decimal(salary.hra or 0) or (segment_basic * Decimal("0.5"))
        monthly_ctc += segment_monthly_ctc * weight
        basic += segment_basic * weight
        hra += segment_hra * weight

    return _money(monthly_ctc), _money(basic), _money(hra)


def _find_exchange_rate(db: Session, from_currency: str, to_currency: str, on_date: date) -> Optional[PayrollExchangeRate]:
    return db.query(PayrollExchangeRate).filter(
        PayrollExchangeRate.from_currency == from_currency.upper(),
        PayrollExchangeRate.to_currency == to_currency.upper(),
        PayrollExchangeRate.effective_date <= on_date,
    ).order_by(PayrollExchangeRate.effective_date.desc(), PayrollExchangeRate.id.desc()).first()


def run_payroll(db: Session, month: int, year: int, run_by_user_id: int, force_run: bool = False) -> PayrollRun:
    from app.models.employee import Employee
    from app.models.attendance import Attendance
    import calendar

    period_start = date(year, month, 1)
    period_end = date(year, month, calendar.monthrange(year, month)[1])

    # Create or get existing run
    payroll_run = db.query(PayrollRun).filter(
        and_(PayrollRun.month == month, PayrollRun.year == year, PayrollRun.deleted_at.is_(None))
    ).first()

    if payroll_run:
        coerce_payroll_run_status(payroll_run)
        if payroll_run.status in {PAYROLL_RUN_STATUS_APPROVED, PAYROLL_RUN_STATUS_LOCKED, PAYROLL_RUN_STATUS_PAID}:
            raise ValueError(f"Payroll run cannot be recalculated from status '{payroll_run.status}'")

    if payroll_run:
        payroll_run.pay_period_start = payroll_run.pay_period_start or period_start
        payroll_run.pay_period_end = payroll_run.pay_period_end or period_end

    if not payroll_run:
        payroll_run = PayrollRun(
            month=month,
            year=year,
            pay_period_start=period_start,
            pay_period_end=period_end,
            run_date=date.today(),
            status=PAYROLL_RUN_STATUS_DRAFT,
        )
        db.add(payroll_run)
        db.flush()

    if payroll_run.status == PAYROLL_RUN_STATUS_DRAFT:
        transition_payroll_run_status(payroll_run, PAYROLL_RUN_STATUS_INPUTS_PENDING)

    # Get all employees who were employed for at least one day in this payroll period.
    employees = db.query(Employee).filter(
        Employee.date_of_joining <= period_end,
        or_(Employee.date_of_exit.is_(None), Employee.date_of_exit >= period_start),
        Employee.deleted_at.is_(None),
    ).all()
    total_working_days = sum(1 for d in range(1, calendar.monthrange(year, month)[1] + 1)
                             if date(year, month, d).weekday() < 5)  # Mon-Fri

    total_gross = Decimal("0")
    total_deductions = Decimal("0")
    total_net = Decimal("0")
    missing_exchange_employee_ids: set[int] = set()

    db.query(PayrollPreRunCheck).filter(
        PayrollPreRunCheck.payroll_run_id == payroll_run.id,
        PayrollPreRunCheck.check_type == "currency_exchange_rate",
    ).delete(synchronize_session=False)
    db.flush()

    for emp in employees:
        salary = get_active_salary(db, emp.id)
        salary_currency = (emp.salary_currency or "INR").upper()
        if not salary or salary_currency == "INR":
            continue
        if not _find_exchange_rate(db, salary_currency, "INR", period_start):
            missing_exchange_employee_ids.add(emp.id)
            action = "Employee will be skipped because force_run is enabled." if force_run else "Payroll run is blocked."
            db.add(PayrollPreRunCheck(
                payroll_run_id=payroll_run.id,
                check_type="currency_exchange_rate",
                status="Failed",
                severity="Critical",
                affected_employee_id=emp.id,
                message=(
                    f"Missing {salary_currency}->INR exchange rate effective on or before "
                    f"{period_start.isoformat()} for employee {getattr(emp, 'employee_id', emp.id)}. {action}"
                ),
            ))

    if missing_exchange_employee_ids and not force_run:
        db.commit()
        raise ValueError(
            "Missing exchange rate for non-INR salary employees. Configure exchange rates or rerun with force_run=true to skip affected employees."
        )

    for emp in employees:
        if emp.id in missing_exchange_employee_ids:
            continue

        salary = get_active_salary(db, emp.id)
        if not salary:
            continue

        # Count attendance
        attendance_input = db.query(PayrollAttendanceInput).join(PayrollPeriod).filter(
            PayrollPeriod.month == month,
            PayrollPeriod.year == year,
            PayrollAttendanceInput.employee_id == emp.id,
            PayrollAttendanceInput.source_status.in_(["Approved", "Locked"]),
        ).order_by(PayrollAttendanceInput.id.desc()).first()

        attendance_query = db.query(Attendance).filter(
            and_(
                Attendance.employee_id == emp.id,
                Attendance.attendance_date >= period_start,
                Attendance.attendance_date <= period_end,
            )
        )
        raw_attendance_days = attendance_query.count()
        raw_present_days = attendance_query.filter(Attendance.status.in_(["Present", "WFH", "Half-day"])).count()

        employment_start = max(emp.date_of_joining or period_start, period_start)
        employment_end = min(emp.date_of_exit or period_end, period_end)
        payable_calendar_days = max(0, (employment_end - employment_start).days + 1)
        period_calendar_days = max(1, (period_end - period_start).days + 1)
        employment_ratio = Decimal(str(payable_calendar_days)) / Decimal(str(period_calendar_days))
        if payable_calendar_days <= 0:
            continue

        if attendance_input:
            total_working_days = int(attendance_input.working_days or total_working_days)
            paid_days = Decimal(attendance_input.payable_days or 0)
            lop_days = Decimal(attendance_input.lop_days or 0)
            present_days = Decimal(attendance_input.present_days or 0)
        else:
            # If attendance has not been captured for the period, treat the employee as payable.
            # Once attendance rows exist, the present/WFH/Half-day count drives LOP.
            employable_working_days = sum(
                1 for d in range(employment_start.day, employment_end.day + 1)
                if date(year, month, d).weekday() < 5
            )
            present_days = Decimal(str(raw_present_days if raw_attendance_days else employable_working_days))
            paid_days = min(present_days, Decimal(str(employable_working_days)))
            lop_days = max(Decimal("0"), Decimal(str(employable_working_days)) - paid_days)

        salary_currency = (emp.salary_currency or "INR").upper()
        exchange_rate = Decimal("1")
        converted_currency = "INR"
        monthly_ctc, basic, hra = get_prorated_salary_for_period(db, emp.id, period_start, period_end)
        if monthly_ctc == Decimal("0"):
            ctc = salary.ctc
            monthly_ctc = ctc / Decimal("12")
            basic = salary.basic or (monthly_ctc * Decimal("0.4"))
            hra = salary.hra or (basic * Decimal("0.5"))
        original_monthly_ctc = _money(monthly_ctc)
        original_basic = _money(basic)
        original_hra = _money(hra)
        if salary_currency != "INR":
            rate = _find_exchange_rate(db, salary_currency, "INR", period_start)
            if not rate:
                continue
            exchange_rate = Decimal(rate.rate)
            monthly_ctc = _money(monthly_ctc * exchange_rate)
            basic = _money(basic * exchange_rate)
            hra = _money(hra * exchange_rate)
        monthly_ctc = _money(monthly_ctc * employment_ratio)
        basic = _money(basic * employment_ratio)
        hra = _money(hra * employment_ratio)
        other_allowances = monthly_ctc - basic - hra

        per_day_salary = monthly_ctc / Decimal(str(total_working_days or 1))
        lop_deduction = per_day_salary * lop_days

        gross = monthly_ctc - lop_deduction

        approved_reimbursements = db.query(Reimbursement).filter(
            and_(
                Reimbursement.employee_id == emp.id,
                Reimbursement.status == "Approved",
                Reimbursement.payroll_record_id.is_(None),
                Reimbursement.date >= period_start,
                Reimbursement.date <= period_end,
            )
        ).all()
        reimbursement_total = sum((item.amount or Decimal("0")) for item in approved_reimbursements)
        approved_advances = db.query(SalaryAdvance).filter(
            SalaryAdvance.employee_id == emp.id,
            SalaryAdvance.status == "Approved",
            SalaryAdvance.requested_deduction_month == month,
            SalaryAdvance.requested_deduction_year == year,
            SalaryAdvance.payroll_record_id.is_(None),
        ).all()
        salary_advance_total = sum((item.approved_amount or item.requested_amount or Decimal("0")) for item in approved_advances)
        period = attendance_input.period if attendance_input else db.query(PayrollPeriod).filter(
            PayrollPeriod.month == month,
            PayrollPeriod.year == year,
        ).order_by(PayrollPeriod.id.desc()).first()
        overtime_lines = []
        encashment_lines = []
        overtime_total = Decimal("0")
        encashment_total = Decimal("0")
        if period:
            overtime_lines = db.query(OvertimePayLine).filter(
                OvertimePayLine.period_id == period.id,
                OvertimePayLine.employee_id == emp.id,
                OvertimePayLine.status == "Approved",
                OvertimePayLine.payroll_record_id.is_(None),
            ).all()
            encashment_lines = db.query(LeaveEncashmentLine).filter(
                LeaveEncashmentLine.period_id == period.id,
                LeaveEncashmentLine.employee_id == emp.id,
                LeaveEncashmentLine.status == "Approved",
                LeaveEncashmentLine.payroll_record_id.is_(None),
            ).all()
            overtime_total = sum((item.amount or Decimal("0")) for item in overtime_lines)
            encashment_total = sum((item.amount or Decimal("0")) for item in encashment_lines)

        gross = gross + overtime_total + encashment_total
        statutory_amounts, statutory_lines = _calculate_statutory_amounts(
            db=db,
            employee_id=emp.id,
            month=month,
            calculation_date=period_start,
            basic=basic,
            gross=gross,
        )
        pf_employee = statutory_amounts["pf_employee"]
        pf_employer = statutory_amounts["pf_employer"]
        esi_employee = statutory_amounts["esi_employee"]
        esi_employer = statutory_amounts["esi_employer"]
        pt = statutory_amounts["professional_tax"]
        lwf_employee = statutory_amounts["lwf_employee"]
        lwf_employer = statutory_amounts["lwf_employer"]
        total_ded = pf_employee + esi_employee + pt + lwf_employee + salary_advance_total
        net = gross - total_ded + reimbursement_total

        # AI anomaly detection placeholder
        is_anomaly = False
        anomaly_reason = None
        if net < Decimal("0"):
            is_anomaly = True
            anomaly_reason = "Net salary is negative"

        # Remove existing record for this run
        existing = db.query(PayrollRecord).filter(
            and_(
                PayrollRecord.payroll_run_id == payroll_run.id,
                PayrollRecord.employee_id == emp.id,
            )
        ).first()
        if existing:
            db.query(PayrollStatutoryContributionLine).filter(
                PayrollStatutoryContributionLine.payroll_record_id == existing.id,
            ).delete(synchronize_session=False)
            db.delete(existing)
            db.flush()

        record = PayrollRecord(
            payroll_run_id=payroll_run.id,
            employee_id=emp.id,
            working_days=total_working_days,
            present_days=paid_days,
            lop_days=lop_days,
            paid_days=paid_days,
            basic=basic,
            hra=hra,
            da=Decimal("0"),
            ta=Decimal("0"),
            other_allowances=other_allowances,
            gross_salary=gross,
            pf_employee=pf_employee,
            pf_employer=pf_employer,
            esi_employee=esi_employee,
            esi_employer=esi_employer,
            professional_tax=pt,
            tds=Decimal("0"),
            other_deductions=lwf_employee + salary_advance_total,
            total_deductions=total_ded,
            reimbursements=reimbursement_total,
            net_salary=net,
            salary_currency=salary_currency,
            exchange_rate=exchange_rate,
            converted_currency=converted_currency,
            is_anomaly=is_anomaly,
            anomaly_reason=anomaly_reason,
        )
        db.add(record)
        db.flush()

        db.add(PayrollCalculationSnapshot(
            payroll_run_id=payroll_run.id,
            employee_id=emp.id,
            snapshot_type="PayrollRun",
            attendance_input_json={
                "attendance_input_id": attendance_input.id if attendance_input else None,
                "paid_days": str(paid_days),
                "lop_days": str(lop_days),
                "employment_ratio": str(employment_ratio),
            },
            result_json={
                "salary_currency": salary_currency,
                "exchange_rate": str(exchange_rate),
                "converted_currency": converted_currency,
                "original_monthly_ctc": str(original_monthly_ctc),
                "original_basic": str(original_basic),
                "original_hra": str(original_hra),
                "converted_monthly_ctc": str(monthly_ctc),
                "converted_basic": str(basic),
                "converted_hra": str(hra),
                "gross_salary": str(gross),
                "net_salary": str(net),
            },
            created_by=run_by_user_id,
        ))

        payroll_lines = [
            ("Basic", "Earning", basic),
            ("House Rent Allowance", "Earning", hra),
            ("Other Allowances", "Earning", other_allowances),
            ("LOP Deduction", "Deduction", lop_deduction),
            ("PF Employee", "Deduction", pf_employee),
            ("ESI Employee", "Deduction", esi_employee),
            ("Professional Tax", "Deduction", pt),
            ("Labour Welfare Fund", "Deduction", lwf_employee),
            ("Salary Advance Recovery", "Deduction", salary_advance_total),
            ("PF Employer", "Employer Contribution", pf_employer),
            ("ESI Employer", "Employer Contribution", esi_employer),
            ("LWF Employer", "Employer Contribution", lwf_employer),
        ]
        if overtime_total > 0:
            payroll_lines.append(("Overtime Pay", "Earning", overtime_total))
        if encashment_total > 0:
            payroll_lines.append(("Leave Encashment", "Earning", encashment_total))
        if reimbursement_total > 0:
            payroll_lines.append(("Approved Reimbursements", "Reimbursement", reimbursement_total))

        for order, (component_name, component_type, amount) in enumerate(payroll_lines, start=1):
            if amount and amount != Decimal("0"):
                db.add(PayrollComponent(
                    record_id=record.id,
                    component_name=component_name,
                    component_type=component_type,
                    amount=_money(amount),
                    source_type="payroll_engine",
                    taxable_amount=_money(amount) if component_type == "Earning" else Decimal("0"),
                    exempt_amount=Decimal("0"),
                    wage_base_flags={"pf": component_name == "Basic", "esi": component_type == "Earning"},
                    calculation_order=order,
                    formula_trace_json={
                        "engine": "legacy-run-v1",
                        "attendance_input_id": attendance_input.id if attendance_input else None,
                        "salary_proration": "calendar_days",
                        "period_start": period_start.isoformat(),
                        "period_end": period_end.isoformat(),
                    },
                ))

        for line in statutory_lines:
            line.payroll_record_id = record.id
            db.add(line)

        for reimbursement in approved_reimbursements:
            reimbursement.payroll_record_id = record.id
            reimbursement.status = "Paid"
            db.query(ExpenseClaim).filter(
                ExpenseClaim.payroll_reimbursement_id == reimbursement.id,
            ).update(
                {
                    "payroll_run_id": payroll_run.id,
                    "reimbursed_at": datetime.now(timezone.utc),
                    "status": "reimbursed",
                },
                synchronize_session=False,
            )
        for advance in approved_advances:
            advance.payroll_record_id = record.id
            advance.status = "Recovered"
        for line in overtime_lines:
            line.payroll_record_id = record.id
            line.status = "Paid"
        for line in encashment_lines:
            line.payroll_record_id = record.id
            line.status = "Paid"
            db.query(LeaveEncashmentRequest).filter(
                LeaveEncashmentRequest.leave_encashment_line_id == line.id,
            ).update(
                {
                    "status": "paid",
                    "payroll_run_id": payroll_run.id,
                },
                synchronize_session=False,
            )
        if attendance_input and lop_days > 0:
            payroll_month = f"{year:04d}-{month:02d}"
            db.query(PayrollLWPEntry).filter(
                PayrollLWPEntry.employee_id == emp.id,
                PayrollLWPEntry.payroll_month == payroll_month,
                PayrollLWPEntry.payroll_run_id.is_(None),
            ).update(
                {
                    "payroll_run_id": payroll_run.id,
                    "payroll_attendance_input_id": attendance_input.id,
                    "amount_deducted": _money(lop_deduction),
                },
                synchronize_session=False,
            )

        total_gross += gross
        total_deductions += total_ded
        total_net += net

    payroll_run.total_gross = total_gross
    payroll_run.total_deductions = total_deductions
    payroll_run.total_net = total_net
    transition_payroll_run_status(payroll_run, PAYROLL_RUN_STATUS_CALCULATED)
    db.commit()
    db.refresh(payroll_run)
    return payroll_run


def calculate_payroll_variance(db: Session, payroll_run_id: int) -> List[PayrollVarianceItem]:
    import calendar

    run = db.query(PayrollRun).filter(
        PayrollRun.id == payroll_run_id,
        PayrollRun.deleted_at.is_(None),
    ).first()
    if not run:
        raise ValueError("Payroll run not found")

    previous_month = 12 if run.month == 1 else run.month - 1
    previous_year = run.year - 1 if run.month == 1 else run.year
    previous_run = db.query(PayrollRun).filter(
        PayrollRun.month == previous_month,
        PayrollRun.year == previous_year,
        PayrollRun.deleted_at.is_(None),
    ).first()

    db.query(PayrollVarianceItem).filter(PayrollVarianceItem.payroll_run_id == payroll_run_id).delete()
    db.flush()

    items: List[PayrollVarianceItem] = []
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == payroll_run_id).all()
    for record in records:
        previous_record = None
        if previous_run:
            previous_record = db.query(PayrollRecord).filter(
                PayrollRecord.payroll_run_id == previous_run.id,
                PayrollRecord.employee_id == record.employee_id,
            ).first()

        previous_gross = previous_record.gross_salary if previous_record else Decimal("0")
        previous_net = previous_record.net_salary if previous_record else Decimal("0")
        current_gross = record.gross_salary or Decimal("0")
        current_net = record.net_salary or Decimal("0")
        gross_delta = current_gross - previous_gross
        net_delta = current_net - previous_net
        gross_delta_percent = (gross_delta / previous_gross * Decimal("100")) if previous_gross else Decimal("0")
        net_delta_percent = (net_delta / previous_net * Decimal("100")) if previous_net else Decimal("0")

        reasons = []
        severity = "Info"
        if not previous_record:
            reasons.append("No previous month payroll record")
        if current_net < 0:
            severity = "Critical"
            reasons.append("Net salary is negative")
        elif abs(gross_delta_percent) >= Decimal("25") or abs(net_delta_percent) >= Decimal("25"):
            severity = "High"
            reasons.append("Payroll changed by 25% or more")
        elif abs(gross_delta_percent) >= Decimal("10") or abs(net_delta_percent) >= Decimal("10"):
            severity = "Medium"
            reasons.append("Payroll changed by 10% or more")

        item = PayrollVarianceItem(
            payroll_run_id=payroll_run_id,
            employee_id=record.employee_id,
            previous_payroll_record_id=previous_record.id if previous_record else None,
            current_gross=current_gross,
            previous_gross=previous_gross,
            gross_delta=gross_delta,
            gross_delta_percent=gross_delta_percent,
            current_net=current_net,
            previous_net=previous_net,
            net_delta=net_delta,
            net_delta_percent=net_delta_percent,
            severity=severity,
            reason="; ".join(reasons) if reasons else "Within configured variance threshold",
        )
        db.add(item)
        items.append(item)

    db.commit()
    for item in items:
        db.refresh(item)
    return items


def get_payslip(db: Session, employee_id: int, month: int, year: int) -> Optional[PayrollRecord]:
    return db.query(PayrollRecord).join(PayrollRun).filter(
        and_(
            PayrollRecord.employee_id == employee_id,
            PayrollRun.month == month,
            PayrollRun.year == year,
            PayrollRun.deleted_at.is_(None),
        )
    ).first()


def _component_payload(component: PayrollComponent) -> dict:
    return {
        "component_name": component.component_name,
        "component_type": component.component_type,
        "amount": component.amount or Decimal("0"),
    }


def _fallback_components(record: PayrollRecord) -> list[PayrollComponent]:
    values = [
        ("Basic", "Earning", record.basic),
        ("House Rent Allowance", "Earning", record.hra),
        ("Other Allowances", "Earning", record.other_allowances),
        ("PF Employee", "Deduction", record.pf_employee),
        ("ESI Employee", "Deduction", record.esi_employee),
        ("Professional Tax", "Deduction", record.professional_tax),
        ("TDS", "Deduction", record.tds),
        ("Other Deductions", "Deduction", record.other_deductions),
        ("PF Employer", "Employer Contribution", record.pf_employer),
        ("ESI Employer", "Employer Contribution", record.esi_employer),
        ("Reimbursements", "Reimbursement", record.reimbursements),
    ]
    return [
        PayrollComponent(component_name=name, component_type=kind, amount=amount)
        for name, kind, amount in values
        if amount and amount != Decimal("0")
    ]


def build_payslip_payload(db: Session, record: PayrollRecord) -> dict:
    components = list(record.components) or _fallback_components(record)
    earnings = [_component_payload(c) for c in components if c.component_type == "Earning"]
    deductions = [_component_payload(c) for c in components if c.component_type == "Deduction"]
    employer_contributions = [
        _component_payload(c) for c in components if c.component_type == "Employer Contribution"
    ]
    reimbursements = [_component_payload(c) for c in components if c.component_type == "Reimbursement"]

    run = record.payroll_run
    ytd_records = db.query(PayrollRecord).join(PayrollRun).filter(
        PayrollRecord.employee_id == record.employee_id,
        PayrollRun.year == run.year,
        PayrollRun.month <= run.month,
        PayrollRun.deleted_at.is_(None),
    ).all()
    ytd = {
        "gross_salary": sum((item.gross_salary or Decimal("0")) for item in ytd_records),
        "total_deductions": sum((item.total_deductions or Decimal("0")) for item in ytd_records),
        "net_salary": sum((item.net_salary or Decimal("0")) for item in ytd_records),
        "reimbursements": sum((item.reimbursements or Decimal("0")) for item in ytd_records),
        "employer_contributions": sum(
            (item.pf_employer or Decimal("0")) + (item.esi_employer or Decimal("0"))
            for item in ytd_records
        ),
    }

    return {
        "id": record.id,
        "payroll_run_id": record.payroll_run_id,
        "employee_id": record.employee_id,
        "employee": record.employee,
        "month": run.month,
        "year": run.year,
        "working_days": record.working_days,
        "present_days": record.present_days,
        "lop_days": record.lop_days,
        "paid_days": record.paid_days,
        "gross_salary": record.gross_salary,
        "total_deductions": record.total_deductions,
        "net_salary": record.net_salary,
        "currency": record.converted_currency or "INR",
        "salary_currency": record.salary_currency or "INR",
        "exchange_rate": record.exchange_rate,
        "converted_currency": record.converted_currency or "INR",
        "currency_note": (
            f"Salary converted from {record.salary_currency} to {record.converted_currency or 'INR'} at {record.exchange_rate}"
            if (record.salary_currency or "INR") != (record.converted_currency or "INR")
            else "Salary processed in INR"
        ),
        "status": record.status,
        "is_anomaly": record.is_anomaly,
        "anomaly_reason": record.anomaly_reason,
        "earnings": earnings,
        "deductions": deductions,
        "employer_contributions": employer_contributions,
        "reimbursements": reimbursements,
        "ytd": ytd,
    }
