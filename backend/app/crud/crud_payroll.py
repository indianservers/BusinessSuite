from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional
import calendar
import re
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.payroll import (
    SalaryComponent, SalaryStructure, SalaryStructureComponent,
    EmployeeSalary, PayrollRun, PayrollRecord, PayrollComponent, Reimbursement,
    PayrollVarianceItem, PayrollPeriod, PayrollAttendanceInput,
    OvertimePayLine, LeaveEncashmentLine, LeaveEncashmentRequest, PayrollLWPEntry,
    EmployeeStatutoryProfile, PayrollStatutoryContributionLine,
    PFRule, ESIRule, ProfessionalTaxSlab, LWFSlab, SalaryAdvance, PayrollExchangeRate,
    PayrollCalculationSnapshot, PayrollPreRunCheck, PayrollRunAuditLog,
    PayrollPayGroup, PayrollManualInput, SalaryRevisionRequest,
    EmployeeTaxDeclaration,
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

PAYROLL_READINESS_CHECK_TYPES = {
    "missing_salary",
    "missing_bank",
    "invalid_bank",
    "missing_pan",
    "attendance_not_locked",
    "pending_salary_revisions",
    "pending_reimbursements",
    "negative_net_salary",
    "tax_declaration_readiness",
}


class PayrollReadinessError(ValueError):
    def __init__(self, summary: dict[str, Any]):
        super().__init__("Payroll readiness checks failed")
        self.summary = summary

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


def validate_employee_bank(employee, seen_accounts: dict[str, int]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    ifsc = (employee.ifsc_code or "").strip().upper()
    account = (employee.account_number or "").strip()
    if not ifsc or not re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", ifsc):
        errors.append({"code": "INVALID_IFSC", "message": "IFSC must match Indian bank IFSC format"})
    if not account or not re.match(r"^[0-9]{9,18}$", account):
        errors.append({"code": "INVALID_ACCOUNT", "message": "Bank account number must be 9 to 18 digits"})
    if account:
        if account in seen_accounts and seen_accounts[account] != employee.id:
            errors.append({"code": "DUPLICATE_ACCOUNT", "message": f"Account number duplicates employee_id={seen_accounts[account]}"})
        seen_accounts[account] = employee.id
    return errors


def _payroll_scope_filters(
    company_id: int | None = None,
    branch_id: int | None = None,
    department_id: int | None = None,
    pay_group_id: int | None = None,
    employee_category: str | None = None,
) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "branch_id": branch_id,
        "department_id": department_id,
        "pay_group_id": pay_group_id,
        "employee_category": employee_category,
    }


def _scoped_employee_query(db: Session, base_query, scope: dict[str, Any]):
    from app.models.company import Branch
    from app.models.employee import Employee

    pay_group_id = scope.get("pay_group_id")
    branch_id = scope.get("branch_id")
    if pay_group_id and not branch_id:
        pay_group = db.query(PayrollPayGroup).filter(PayrollPayGroup.id == pay_group_id).first()
        branch_id = pay_group.branch_id if pay_group else None

    if scope.get("company_id"):
        base_query = base_query.join(Employee.branch).filter(Branch.company_id == scope["company_id"])
    if branch_id:
        base_query = base_query.filter(Employee.branch_id == branch_id)
    if scope.get("department_id"):
        base_query = base_query.filter(Employee.department_id == scope["department_id"])
    if scope.get("employee_category"):
        category = scope["employee_category"]
        base_query = base_query.filter(or_(
            Employee.employment_type == category,
            Employee.worker_type == category,
            Employee.worker_category == category,
            Employee.functional_area == category,
        ))
    return base_query


def payroll_readiness_summary(
    db: Session,
    month: int,
    year: int,
    company_id: int | None = None,
    branch_id: int | None = None,
    department_id: int | None = None,
    pay_group_id: int | None = None,
    employee_category: str | None = None,
) -> dict[str, Any]:
    from app.models.employee import Employee

    scope = _payroll_scope_filters(company_id, branch_id, department_id, pay_group_id, employee_category)
    employee_query = db.query(Employee).filter(
        Employee.deleted_at.is_(None),
        Employee.status.in_(["Active", "Probation", "Resigned"]),
    )
    employees = _scoped_employee_query(db, employee_query, scope).all()
    employee_ids = [employee.id for employee in employees]
    salary_employee_ids = {row[0] for row in db.query(EmployeeSalary.employee_id).filter(EmployeeSalary.is_active == True).all()}
    seen_accounts: dict[str, int] = {}
    missing_salary: list[int] = []
    missing_bank: list[int] = []
    invalid_bank: list[dict[str, Any]] = []
    missing_pan: list[int] = []

    for employee in employees:
        if employee.id not in salary_employee_ids:
            missing_salary.append(employee.id)
        if not employee.account_number or not employee.ifsc_code:
            missing_bank.append(employee.id)
        errors = validate_employee_bank(employee, seen_accounts)
        if errors:
            invalid_bank.append({"employee_id": employee.id, "errors": errors})
        if not employee.pan_number:
            missing_pan.append(employee.id)

    period_query = db.query(PayrollPeriod).filter(PayrollPeriod.month == month, PayrollPeriod.year == year)
    if pay_group_id:
        period_query = period_query.filter(PayrollPeriod.pay_group_id == pay_group_id)
    period = period_query.order_by(PayrollPeriod.id.desc()).first()
    attendance_locked = bool(period and str(period.status).lower() in {"locked", "closed"})
    period_end = period.period_end if period and period.period_end else date(year, month, calendar.monthrange(year, month)[1])
    financial_year = f"{period_end.year}-{str(period_end.year + 1)[-2:]}" if period_end.month >= 4 else f"{period_end.year - 1}-{str(period_end.year)[-2:]}"

    pending_revision_ids = [
        row[0] for row in db.query(SalaryRevisionRequest.employee_id).filter(
            SalaryRevisionRequest.employee_id.in_(employee_ids or [0]),
            SalaryRevisionRequest.status.in_(["Pending", "Submitted"]),
            SalaryRevisionRequest.effective_from <= period_end,
        ).all()
    ]
    pending_reimbursement_rows = db.query(Reimbursement.employee_id, Reimbursement.id, Reimbursement.status).filter(
        Reimbursement.employee_id.in_(employee_ids or [0]),
        Reimbursement.payroll_record_id.is_(None),
        Reimbursement.status.in_(["Pending", "Submitted"]),
    ).all()
    negative_net_rows = db.query(PayrollRecord.employee_id, PayrollRecord.id, PayrollRecord.net_salary).join(
        PayrollRun, PayrollRun.id == PayrollRecord.payroll_run_id
    ).filter(
        PayrollRun.month == month,
        PayrollRun.year == year,
        PayrollRun.deleted_at.is_(None),
        PayrollRecord.employee_id.in_(employee_ids or [0]),
        PayrollRecord.net_salary < 0,
    ).all()
    declared_employee_ids = {
        row[0] for row in db.query(EmployeeTaxDeclaration.employee_id).filter(
            EmployeeTaxDeclaration.employee_id.in_(employee_ids or [0]),
            EmployeeTaxDeclaration.financial_year == financial_year,
            EmployeeTaxDeclaration.status.in_(["submitted", "approved", "verified", "Submitted", "Approved", "Verified"]),
        ).all()
    }
    tax_not_ready_ids = [employee_id for employee_id in employee_ids if employee_id not in declared_employee_ids]

    issues = {
        "missing_salary": {
            "count": len(missing_salary),
            "severity": "Critical",
            "employee_ids": missing_salary[:100],
        },
        "missing_bank": {
            "count": len(missing_bank),
            "severity": "Critical",
            "employee_ids": missing_bank[:100],
        },
        "invalid_bank": {
            "count": len(invalid_bank),
            "severity": "Critical",
            "items": invalid_bank[:100],
        },
        "missing_pan": {
            "count": len(missing_pan),
            "severity": "Warning",
            "employee_ids": missing_pan[:100],
        },
        "attendance_not_locked": {
            "count": 0 if attendance_locked else 1,
            "severity": "Critical",
            "message": "Attendance is locked" if attendance_locked else "Attendance period is not locked or no payroll period exists",
        },
        "pending_salary_revisions": {
            "count": len(set(pending_revision_ids)),
            "severity": "Critical",
            "employee_ids": sorted(set(pending_revision_ids))[:100],
            "message": "Salary revision requests effective for this period are still pending approval.",
        },
        "pending_reimbursements": {
            "count": len(pending_reimbursement_rows),
            "severity": "Critical",
            "items": [
                {"employee_id": row.employee_id, "reimbursement_id": row.id, "status": row.status}
                for row in pending_reimbursement_rows[:100]
            ],
            "message": "Reimbursements are pending approval for this period.",
        },
        "negative_net_salary": {
            "count": len(negative_net_rows),
            "severity": "Critical",
            "items": [
                {"employee_id": row.employee_id, "payroll_record_id": row.id, "net_salary": row.net_salary}
                for row in negative_net_rows[:100]
            ],
            "message": "One or more payroll records have negative net salary.",
        },
        "tax_declaration_readiness": {
            "count": len(tax_not_ready_ids),
            "severity": "Warning",
            "employee_ids": tax_not_ready_ids[:100],
            "financial_year": financial_year,
            "message": "Employee tax declaration is missing or not submitted/approved for the financial year.",
        },
    }
    critical_issue_count = sum(issue["count"] for issue in issues.values() if issue["severity"] == "Critical")
    warning_issue_count = sum(issue["count"] for issue in issues.values() if issue["severity"] == "Warning")
    return {
        "month": month,
        "year": year,
        "scope": scope,
        "total_employees": len(employees),
        "ready": critical_issue_count == 0,
        "attendance_locked": attendance_locked,
        "critical_issue_count": critical_issue_count,
        "warning_issue_count": warning_issue_count,
        "issues": issues,
    }


def persist_payroll_readiness_checks(
    db: Session,
    payroll_run: PayrollRun,
    summary: dict[str, Any],
    actor_user_id: int,
    force_run: bool = False,
) -> None:
    db.query(PayrollPreRunCheck).filter(
        PayrollPreRunCheck.payroll_run_id == payroll_run.id,
        PayrollPreRunCheck.check_type.in_(PAYROLL_READINESS_CHECK_TYPES),
    ).delete(synchronize_session=False)
    issues = summary.get("issues") or {}

    for employee_id in issues.get("missing_salary", {}).get("employee_ids", []):
        db.add(PayrollPreRunCheck(payroll_run_id=payroll_run.id, check_type="missing_salary", status="Failed", severity="Critical", affected_employee_id=employee_id, message="Employee has no active salary assignment."))
    for employee_id in issues.get("missing_bank", {}).get("employee_ids", []):
        db.add(PayrollPreRunCheck(payroll_run_id=payroll_run.id, check_type="missing_bank", status="Failed", severity="Critical", affected_employee_id=employee_id, message="Employee is missing bank account number or IFSC."))
    for item in issues.get("invalid_bank", {}).get("items", []):
        message = "; ".join(error.get("message", "") for error in item.get("errors", [])) or "Employee bank details failed validation."
        db.add(PayrollPreRunCheck(payroll_run_id=payroll_run.id, check_type="invalid_bank", status="Failed", severity="Critical", affected_employee_id=item.get("employee_id"), message=message))
    for employee_id in issues.get("missing_pan", {}).get("employee_ids", []):
        db.add(PayrollPreRunCheck(payroll_run_id=payroll_run.id, check_type="missing_pan", status="Warning", severity="Warning", affected_employee_id=employee_id, message="Employee PAN is missing; TDS/reporting may be affected."))
    if issues.get("attendance_not_locked", {}).get("count", 0):
        db.add(PayrollPreRunCheck(payroll_run_id=payroll_run.id, check_type="attendance_not_locked", status="Failed", severity="Critical", message="Attendance is not locked for this payroll month."))
    for employee_id in issues.get("pending_salary_revisions", {}).get("employee_ids", []):
        db.add(PayrollPreRunCheck(payroll_run_id=payroll_run.id, check_type="pending_salary_revisions", status="Failed", severity="Critical", affected_employee_id=employee_id, message="Salary revision effective for this period is pending approval."))
    for item in issues.get("pending_reimbursements", {}).get("items", []):
        db.add(PayrollPreRunCheck(payroll_run_id=payroll_run.id, check_type="pending_reimbursements", status="Failed", severity="Critical", affected_employee_id=item.get("employee_id"), message=f"Reimbursement #{item.get('reimbursement_id')} is {item.get('status')} and not included in payroll."))
    for item in issues.get("negative_net_salary", {}).get("items", []):
        db.add(PayrollPreRunCheck(payroll_run_id=payroll_run.id, check_type="negative_net_salary", status="Failed", severity="Critical", affected_employee_id=item.get("employee_id"), message=f"Payroll record #{item.get('payroll_record_id')} has negative net salary."))
    for employee_id in issues.get("tax_declaration_readiness", {}).get("employee_ids", []):
        db.add(PayrollPreRunCheck(payroll_run_id=payroll_run.id, check_type="tax_declaration_readiness", status="Warning", severity="Warning", affected_employee_id=employee_id, message="Employee tax declaration is missing or not submitted/approved for this financial year."))

    if force_run and (summary.get("critical_issue_count", 0) or summary.get("warning_issue_count", 0)):
        db.add(PayrollRunAuditLog(
            payroll_run_id=payroll_run.id,
            action="payroll_force_run_readiness_warnings",
            actor_user_id=actor_user_id,
            details=(
                f"Payroll force-run allowed with {summary.get('critical_issue_count', 0)} critical "
                f"and {summary.get('warning_issue_count', 0)} warning readiness issues."
            ),
        ))


def _active_pay_group(db: Session, pay_group_id: int | None, employee) -> PayrollPayGroup | None:
    if pay_group_id:
        return db.query(PayrollPayGroup).filter(PayrollPayGroup.id == pay_group_id).first()
    default = db.query(PayrollPayGroup).filter(
        PayrollPayGroup.is_default == True,
        PayrollPayGroup.is_active == True,
    ).order_by(PayrollPayGroup.id.desc()).first()
    if default:
        return default
    if employee.branch_id:
        scoped = db.query(PayrollPayGroup).filter(
            PayrollPayGroup.branch_id == employee.branch_id,
            PayrollPayGroup.is_active == True,
        ).order_by(PayrollPayGroup.is_default.desc(), PayrollPayGroup.id.desc()).first()
        if scoped:
            return scoped
    return None


def _week_of_month(value: date) -> int:
    return ((value.day - 1) // 7) + 1


def _holiday_dates_for_employee(db: Session, employee, period_start: date, period_end: date) -> set[date]:
    from app.models.attendance import Holiday

    rows = db.query(Holiday).filter(
        Holiday.is_active == True,
        Holiday.holiday_date >= period_start,
        Holiday.holiday_date <= period_end,
    ).all()
    dates: set[date] = set()
    branch_id = str(employee.branch_id or "")
    for row in rows:
        applicable = (row.applicable_branches or "").strip()
        if not applicable or branch_id in {item.strip() for item in applicable.split(",") if item.strip()}:
            dates.add(row.holiday_date)
    return dates


def _is_weekly_off(db: Session, employee, work_date: date, pay_group: PayrollPayGroup | None) -> bool:
    from app.models.attendance import ShiftRoster, ShiftWeeklyOff

    pattern = (pay_group.working_pattern if pay_group else None) or "company"
    if pattern == "shift_roster":
        return not db.query(ShiftRoster).filter(
            ShiftRoster.employee_id == employee.id,
            ShiftRoster.roster_date == work_date,
            ShiftRoster.status.in_(["published", "Published", "approved", "Approved"]),
        ).first()

    if pattern == "rotational_weekly_off" and employee.shift_id:
        week = str(_week_of_month(work_date))
        return bool(db.query(ShiftWeeklyOff).filter(
            ShiftWeeklyOff.shift_id == employee.shift_id,
            ShiftWeeklyOff.weekday == work_date.weekday(),
            ShiftWeeklyOff.is_active == True,
            ShiftWeeklyOff.week_pattern.in_(["all", week]),
        ).first())

    weekly_offs = pay_group.weekly_off_weekdays if pay_group and pay_group.weekly_off_weekdays else None
    if weekly_offs:
        return work_date.weekday() in {int(day) for day in weekly_offs}

    days_per_week = pay_group.working_days_per_week if pay_group and pay_group.working_days_per_week else None
    if days_per_week is None and pattern == "5_day":
        days_per_week = 5
    if days_per_week is None and pattern == "6_day":
        days_per_week = 6
    if days_per_week is None and employee.branch and employee.branch.company:
        days_per_week = employee.branch.company.working_days_per_week
    days_per_week = int(days_per_week or 5)

    if days_per_week >= 7:
        return False
    if days_per_week == 6:
        return work_date.weekday() == 6
    return work_date.weekday() >= 5


def _working_days_for_employee(
    db: Session,
    employee,
    period_start: date,
    period_end: date,
    pay_group: PayrollPayGroup | None,
) -> Decimal:
    holidays = _holiday_dates_for_employee(db, employee, period_start, period_end)
    days = Decimal("0")
    cursor = period_start
    while cursor <= period_end:
        if cursor not in holidays and not _is_weekly_off(db, employee, cursor, pay_group):
            days += Decimal("1")
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return days


def _attendance_day_value(status: str | None) -> Decimal:
    normalized = (status or "").strip().lower()
    if normalized in {"present", "wfh", "work from home", "remote"}:
        return Decimal("1")
    if normalized in {"half-day", "half day", "half_day"}:
        return Decimal("0.5")
    return Decimal("0")


def _non_monthly_base_pay(salary: EmployeeSalary, paid_days: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal, str | None]:
    payroll_type = (salary.payroll_type or "monthly_fixed").strip().lower()
    rate = Decimal(salary.wage_rate or 0)
    default_units = Decimal(salary.default_units or 0)
    unit_label = salary.unit_label
    if payroll_type == "daily":
        amount = rate * paid_days
        return _money(amount), _money(amount), Decimal("0"), Decimal("0"), "Daily Wage"
    if payroll_type in {"hourly", "per_lecture", "per_class", "per_delivery", "per_trip", "per_shift", "piece_rate", "unit_based"}:
        amount = rate * default_units
        labels = {
            "hourly": "Hourly Wage",
            "per_lecture": "Per Lecture Pay",
            "per_class": "Per Class Pay",
            "per_delivery": "Delivery Incentive",
            "per_trip": "Trip Allowance",
            "per_shift": "Shift Pay",
            "piece_rate": "Production Incentive",
            "unit_based": unit_label or "Unit Pay",
        }
        return _money(amount), _money(amount), Decimal("0"), Decimal("0"), labels.get(payroll_type)
    if payroll_type == "commission_based":
        amount = Decimal(salary.commission_base_amount or 0) * Decimal(salary.commission_rate_percent or 0) / Decimal("100")
        if amount == 0:
            amount = rate * default_units
        return _money(amount), Decimal("0"), Decimal("0"), _money(amount), "Commission"
    if payroll_type == "invoice_based":
        amount = Decimal(salary.invoice_amount or 0) or (rate * default_units)
        return _money(amount), Decimal("0"), Decimal("0"), _money(amount), "Consultant Invoice"
    return Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), None


def run_payroll(
    db: Session,
    month: int,
    year: int,
    run_by_user_id: int,
    force_run: bool = False,
    company_id: int | None = None,
    branch_id: int | None = None,
    department_id: int | None = None,
    pay_group_id: int | None = None,
    employee_category: str | None = None,
    pay_period_start: date | None = None,
    pay_period_end: date | None = None,
) -> PayrollRun:
    from app.models.employee import Employee
    from app.models.attendance import Attendance
    import calendar

    period_start = pay_period_start or date(year, month, 1)
    period_end = pay_period_end or date(year, month, calendar.monthrange(year, month)[1])
    scope = _payroll_scope_filters(company_id, branch_id, department_id, pay_group_id, employee_category)

    # Create or get existing run
    payroll_run = db.query(PayrollRun).filter(
        and_(
            PayrollRun.month == month,
            PayrollRun.year == year,
            PayrollRun.company_id == company_id,
            PayrollRun.branch_id == branch_id,
            PayrollRun.department_id == department_id,
            PayrollRun.pay_group_id == pay_group_id,
            PayrollRun.employee_category == employee_category,
            PayrollRun.deleted_at.is_(None),
        )
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
            company_id=company_id,
            branch_id=branch_id,
            department_id=department_id,
            pay_group_id=pay_group_id,
            employee_category=employee_category,
            pay_period_start=period_start,
            pay_period_end=period_end,
            run_date=date.today(),
            status=PAYROLL_RUN_STATUS_DRAFT,
        )
        db.add(payroll_run)
        db.flush()

    if payroll_run.status == PAYROLL_RUN_STATUS_DRAFT:
        transition_payroll_run_status(payroll_run, PAYROLL_RUN_STATUS_INPUTS_PENDING)

    readiness = payroll_readiness_summary(db, month, year, **scope)
    persist_payroll_readiness_checks(db, payroll_run, readiness, run_by_user_id, force_run=force_run)
    if readiness["critical_issue_count"] and not force_run:
        db.commit()
        raise PayrollReadinessError(readiness)

    # Get all employees who were employed for at least one day in this payroll period.
    employee_query = db.query(Employee).filter(
        Employee.date_of_joining <= period_end,
        or_(Employee.date_of_exit.is_(None), Employee.date_of_exit >= period_start),
        Employee.deleted_at.is_(None),
    )
    employees = _scoped_employee_query(db, employee_query, scope).all()

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

        pay_group = _active_pay_group(db, pay_group_id, emp)
        employee_working_days = _working_days_for_employee(db, emp, employment_start, employment_end, pay_group)

        if attendance_input:
            employee_working_days = Decimal(attendance_input.working_days or employee_working_days)
            paid_days = Decimal(attendance_input.payable_days or 0)
            lop_days = Decimal(attendance_input.lop_days or 0)
            present_days = Decimal(attendance_input.present_days or 0)
        else:
            # If attendance has not been captured for the period, treat the employee as payable.
            # Once attendance rows exist, raw status values drive payable days. Half-day is 0.5.
            if raw_attendance_days:
                present_days = sum(
                    (_attendance_day_value(row.status) for row in attendance_query.all()),
                    Decimal("0"),
                )
            else:
                present_days = employee_working_days
            paid_days = min(present_days, employee_working_days)
            lop_days = max(Decimal("0"), employee_working_days - paid_days)

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
        payroll_type = (salary.payroll_type or "monthly_fixed").strip().lower()
        unit_component_name = None
        if payroll_type in {"monthly_fixed", "mixed"}:
            monthly_ctc = _money(monthly_ctc * employment_ratio)
            basic = _money(basic * employment_ratio)
            hra = _money(hra * employment_ratio)
            other_allowances = monthly_ctc - basic - hra
            per_day_salary = monthly_ctc / Decimal(str(employee_working_days or 1))
            lop_deduction = per_day_salary * lop_days
            gross = monthly_ctc - lop_deduction
            if payroll_type == "mixed":
                unit_pay, _unit_basic, _unit_hra, unit_other, unit_component_name = _non_monthly_base_pay(salary, paid_days)
                gross += unit_pay
                other_allowances += unit_other
        else:
            unit_pay, basic, hra, other_allowances, unit_component_name = _non_monthly_base_pay(salary, paid_days)
            monthly_ctc = unit_pay
            lop_deduction = Decimal("0")
            gross = unit_pay

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

        approved_manual_inputs = db.query(PayrollManualInput).filter(
            PayrollManualInput.payroll_run_id == payroll_run.id,
            PayrollManualInput.employee_id == emp.id,
            PayrollManualInput.status == "Approved",
        ).all()
        manual_earning_inputs = [
            item for item in approved_manual_inputs
            if (item.input_type or "").strip().lower() not in {"deduction", "recovery", "loan", "advance"}
        ]
        manual_deduction_inputs = [
            item for item in approved_manual_inputs
            if (item.input_type or "").strip().lower() in {"deduction", "recovery", "loan", "advance"}
        ]
        manual_earning_total = sum((item.amount or Decimal("0")) for item in manual_earning_inputs)
        manual_deduction_total = sum((item.amount or Decimal("0")) for item in manual_deduction_inputs)

        gross = gross + overtime_total + encashment_total + manual_earning_total
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
        total_ded = pf_employee + esi_employee + pt + lwf_employee + salary_advance_total + manual_deduction_total
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
            working_days=int(employee_working_days),
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
            other_deductions=lwf_employee + salary_advance_total + manual_deduction_total,
            bonus=manual_earning_total,
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
                        "working_days": str(employee_working_days),
                        "working_pattern": (pay_group.working_pattern if pay_group else "company"),
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
        if unit_component_name and payroll_type != "monthly_fixed":
            payroll_lines.insert(0, (unit_component_name, "Earning", monthly_ctc if payroll_type != "mixed" else Decimal(salary.wage_rate or 0) * Decimal(salary.default_units or 0)))
        if overtime_total > 0:
            payroll_lines.append(("Overtime Pay", "Earning", overtime_total))
        if encashment_total > 0:
            payroll_lines.append(("Leave Encashment", "Earning", encashment_total))
        if reimbursement_total > 0:
            payroll_lines.append(("Approved Reimbursements", "Reimbursement", reimbursement_total))
        for item in manual_earning_inputs:
            payroll_lines.append((item.component_name, "Earning", item.amount or Decimal("0")))
        for item in manual_deduction_inputs:
            payroll_lines.append((item.component_name, "Deduction", item.amount or Decimal("0")))

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
