from __future__ import annotations

import calendar
import csv
import io
import os
import re
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.payroll import (
    _audit,
    _calculate_tax_from_slabs,
    _component_monthly_amount,
    _file_url_from_upload_path,
    _get_payroll_run_or_404,
    _has_permission,
    _active_rule,
    _ordered_structure_components,
    _rounded_money,
    _tax_with_rebate_surcharge_and_cess,
    _write_basic_pdf,
    compare_tax_regimes,
)
from app.core.config import settings
from app.core.deps import RequirePermission, get_current_user, get_db
from app.core.email import send_email
from app.core.messaging import MessagingResult, send_sms, send_whatsapp
from app.crud import crud_payroll
from app.models.company import CostCenter, Department
from app.models.employee import Employee
from app.models.expense import ExpenseClaim
from app.models.platform import IntegrationCredential
from app.models.payroll import (
    BonusPolicy,
    EmployeeSalary,
    Form12BARecord,
    GratuityAccrual,
    GratuityRule,
    ESIRule,
    EmployeeStatutoryProfile,
    OvertimePayLine,
    PFRule,
    PayrollArrearLine,
    PayrollArrearRun,
    PayrollBankFileValidation,
    PayrollBankValidation,
    PayrollBudget,
    PayrollExchangeRate,
    PayrollManualInput,
    PayrollPeriod,
    PayrollRecord,
    PayrollReportDefinition,
    PayrollRun,
    PayrollStatutoryContributionLine,
    PayrollVarianceItem,
    ProfessionalTaxSlab,
    PayslipDeliveryLog,
    PayslipPublishBatch,
    PayslipQuery,
    Reimbursement,
    SalaryAdvance,
    SalaryCertificate,
    SalaryRevisionBatch,
    SalaryRevisionBatchLine,
    SalaryRevisionRequest,
    SalaryStructure,
    TDS26ASReconciliation,
    PreviousEmploymentTaxDetail,
    TaxRegime,
    TaxSection,
    TaxSectionLimit,
    TaxSlab,
)
from app.models.statutory_compliance import PayrollLegalEntity, StatutoryPortalSubmission
from app.models.user import User
from app.services.bank_file_validators import validate_bank_file_rows

router = APIRouter(prefix="/payroll", tags=["Payroll Extensions"])


class PayrollSimulationRequest(BaseModel):
    ctc: Decimal = Field(gt=0)
    structure_id: int | None = None
    monthly_reimbursements: Decimal = Decimal("0")
    state: str | None = None
    currency: str = "INR"


class TaxOptimizerRequest(BaseModel):
    employee_id: int
    financial_year: str
    gross_taxable_income: Decimal = Field(ge=0)
    section_80c_declared: Decimal = Field(default=Decimal("0"), ge=0)
    section_80d_declared: Decimal = Field(default=Decimal("0"), ge=0)
    nps_80ccd_1b_declared: Decimal = Field(default=Decimal("0"), ge=0)
    home_loan_interest: Decimal = Field(default=Decimal("0"), ge=0)
    other_deductions: Decimal = Field(default=Decimal("0"), ge=0)
    hra_exemption: Decimal = Field(default=Decimal("0"), ge=0)
    hra_basic_salary: Decimal | None = Field(default=None, ge=0)
    hra_received: Decimal | None = Field(default=None, ge=0)
    rent_paid: Decimal | None = Field(default=None, ge=0)
    hra_is_metro: bool = False
    other_exemptions: Decimal = Field(default=Decimal("0"), ge=0)
    paid_tds: Decimal = Field(default=Decimal("0"), ge=0)
    remaining_months: int = Field(default=12, ge=1, le=12)
    previous_employment_income: Decimal | None = Field(default=None, ge=0)
    previous_employment_tds: Decimal | None = Field(default=None, ge=0)


class PayslipQueryCreate(BaseModel):
    payroll_record_id: int
    subject: str
    description: str
    priority: str = "Medium"


class PayslipQueryResolve(BaseModel):
    status: str = "Resolved"
    resolution: str | None = None
    assigned_to: int | None = None


class SalaryAdvanceCreate(BaseModel):
    employee_id: int | None = None
    requested_amount: Decimal = Field(gt=0)
    reason: str | None = None
    requested_deduction_month: int = Field(ge=1, le=12)
    requested_deduction_year: int


class SalaryAdvanceReview(BaseModel):
    action: str
    approved_amount: Decimal | None = None
    remarks: str | None = None


class SalaryRevisionBatchLinePayload(BaseModel):
    employee_id: int
    new_ctc: Decimal = Field(gt=0)
    structure_id: int | None = None


class SalaryRevisionBatchCreate(BaseModel):
    name: str
    effective_from: date
    lines: list[SalaryRevisionBatchLinePayload]


class BonusPolicyPayload(BaseModel):
    name: str
    bonus_type: str = "Festival"
    amount_type: str = "Fixed"
    amount_value: Decimal = Field(gt=0)
    applicable_month: int | None = Field(default=None, ge=1, le=12)
    department_id: int | None = None
    grade_band_id: int | None = None
    description: str | None = None


class BonusPolicyApplyRequest(BaseModel):
    payroll_run_id: int
    policy_id: int


class SalaryCertificateCreate(BaseModel):
    employee_id: int | None = None
    purpose: str
    period_from: date | None = None
    period_to: date | None = None


class PayrollBudgetCreate(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int
    budget_amount: Decimal = Field(gt=0)
    department_id: int | None = None
    cost_center_id: int | None = None
    currency: str = "INR"
    remarks: str | None = None


class TDS26ASReconciliationCreate(BaseModel):
    employee_id: int
    financial_year: str
    reported_26as_tds: Decimal = Decimal("0")
    remarks: str | None = None


class Form12BACreate(BaseModel):
    employee_id: int
    financial_year: str
    perquisites: list[dict[str, Any]] = []


class PayrollExchangeRateCreate(BaseModel):
    from_currency: str
    to_currency: str = "INR"
    rate: Decimal = Field(gt=0)
    effective_date: date
    source: str = "Manual"


class PayrollReportDefinitionCreate(BaseModel):
    name: str
    report_type: str
    filters_json: dict[str, Any] | None = None
    columns_json: list[str] | None = None


class PayrollReportDefinitionUpdate(BaseModel):
    name: str | None = None
    report_type: str | None = None
    filters_json: dict[str, Any] | None = None
    columns_json: list[str] | None = None


class StatutoryPortalSubmitRequest(BaseModel):
    portal: str = "EPFO"
    file_type: str
    file_url: str
    payroll_run_id: int | None = None
    legal_entity_id: int | None = None
    remarks: str | None = None


def _employee_or_404(db: Session, employee_id: int) -> Employee:
    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def _active_employee_salary(db: Session, employee_id: int) -> EmployeeSalary | None:
    return db.query(EmployeeSalary).filter(
        EmployeeSalary.employee_id == employee_id,
        EmployeeSalary.is_active == True,
    ).order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc()).first()


def _salary_breakup_for_ctc(db: Session, ctc: Decimal, structure_id: int | None = None) -> dict[str, Any]:
    monthly_ctc = (Decimal(ctc) / Decimal("12")).quantize(Decimal("0.01"))
    if not structure_id:
        basic = (monthly_ctc * Decimal("0.40")).quantize(Decimal("0.01"))
        hra = (basic * Decimal("0.50")).quantize(Decimal("0.01"))
        other = (monthly_ctc - basic - hra).quantize(Decimal("0.01"))
        return {
            "monthly_ctc": monthly_ctc,
            "gross": monthly_ctc,
            "lines": [
                {"component_name": "Basic", "component_code": "BASIC", "component_type": "Earning", "monthly_amount": basic, "annual_amount": basic * 12},
                {"component_name": "House Rent Allowance", "component_code": "HRA", "component_type": "Earning", "monthly_amount": hra, "annual_amount": hra * 12},
                {"component_name": "Other Allowances", "component_code": "OTHER", "component_type": "Earning", "monthly_amount": other, "annual_amount": other * 12},
            ],
            "warnings": ["No salary structure selected; used default 40/20/rest breakup"],
        }
    structure = db.query(SalaryStructure).filter(SalaryStructure.id == structure_id).first()
    if not structure:
        raise HTTPException(status_code=404, detail="Salary structure not found")
    variables = {"ctc_monthly": monthly_ctc, "ctc_annual": Decimal(ctc)}
    lines: list[dict[str, Any]] = []
    gross = Decimal("0")
    ordered, warnings = _ordered_structure_components(structure)
    for item in ordered:
        if not item.component:
            continue
        amount = _component_monthly_amount(item, monthly_ctc, variables)
        variables[item.component.code] = amount
        variables[item.component.code.lower()] = amount
        if item.component.component_type == "Earning":
            gross += amount
        lines.append({
            "component_id": item.component.id,
            "component_name": item.component.name,
            "component_code": item.component.code,
            "component_type": item.component.component_type,
            "monthly_amount": amount,
            "annual_amount": (amount * Decimal("12")).quantize(Decimal("0.01")),
        })
    return {"monthly_ctc": monthly_ctc, "gross": gross, "lines": lines, "warnings": warnings}


def _validate_employee_bank(employee: Employee, seen_accounts: dict[str, int]) -> list[dict[str, str]]:
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


def _can_access_employee(user: User, employee_id: int) -> bool:
    return _has_permission(user, "payroll_view") or bool(user.employee and user.employee.id == employee_id)


@router.get("/proration-preview")
def payroll_proration_preview(employee_id: int, month: int = Query(..., ge=1, le=12), year: int = Query(...), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    employee = _employee_or_404(db, employee_id)
    period_start = date(year, month, 1)
    period_end = date(year, month, calendar.monthrange(year, month)[1])
    employment_start = max(employee.date_of_joining or period_start, period_start)
    employment_end = min(employee.date_of_exit or period_end, period_end)
    payable_days = max(0, (employment_end - employment_start).days + 1)
    period_days = (period_end - period_start).days + 1
    monthly_ctc, basic, hra = crud_payroll.get_prorated_salary_for_period(db, employee_id, period_start, period_end)
    ratio = Decimal(str(payable_days)) / Decimal(str(period_days))
    return {
        "employee_id": employee_id,
        "period_start": period_start,
        "period_end": period_end,
        "employment_start": employment_start if payable_days else None,
        "employment_end": employment_end if payable_days else None,
        "period_days": period_days,
        "payable_days": payable_days,
        "proration_factor": ratio.quantize(Decimal("0.0001")),
        "monthly_ctc_before_join_exit_proration": monthly_ctc,
        "prorated_monthly_ctc": (monthly_ctc * ratio).quantize(Decimal("0.01")),
        "prorated_basic": (basic * ratio).quantize(Decimal("0.01")),
        "prorated_hra": (hra * ratio).quantize(Decimal("0.01")),
    }


@router.post("/simulate")
def simulate_take_home(data: PayrollSimulationRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    breakup = _salary_breakup_for_ctc(db, data.ctc, data.structure_id)
    gross = Decimal(breakup["gross"] or 0)
    basic = next((Decimal(row["monthly_amount"]) for row in breakup["lines"] if row.get("component_code") == "BASIC"), gross * Decimal("0.40"))
    pf = _rounded_money(min(basic, Decimal("15000")) * Decimal("0.12"))
    esi = _rounded_money(gross * Decimal("0.0075")) if gross <= Decimal("21000") else Decimal("0.00")
    pt = Decimal("200.00") if data.state else Decimal("0.00")
    deductions = pf + esi + pt
    take_home = (gross - deductions + Decimal(data.monthly_reimbursements or 0)).quantize(Decimal("0.01"))
    return {"annual_ctc": data.ctc, "monthly_ctc": breakup["monthly_ctc"], "gross_salary": gross, "deductions": {"pf_employee": pf, "esi_employee": esi, "professional_tax_estimate": pt}, "estimated_take_home": take_home, "components": breakup["lines"], "warnings": breakup["warnings"]}


@router.get("/health-dashboard")
def payroll_health_dashboard(month: int = Query(..., ge=1, le=12), year: int = Query(...), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    employees = db.query(Employee).filter(Employee.deleted_at.is_(None), Employee.status.in_(["Active", "Probation", "Resigned"])).all()
    salary_employee_ids = {row[0] for row in db.query(EmployeeSalary.employee_id).filter(EmployeeSalary.is_active == True).all()}
    seen_accounts: dict[str, int] = {}
    missing_salary, missing_bank, invalid_bank, missing_pan = [], [], [], []
    for employee in employees:
        if employee.id not in salary_employee_ids:
            missing_salary.append(employee.id)
        if not employee.account_number or not employee.ifsc_code:
            missing_bank.append(employee.id)
        errors = _validate_employee_bank(employee, seen_accounts)
        if errors:
            invalid_bank.append({"employee_id": employee.id, "errors": errors})
        if not employee.pan_number:
            missing_pan.append(employee.id)
    period = db.query(PayrollPeriod).filter(PayrollPeriod.month == month, PayrollPeriod.year == year).order_by(PayrollPeriod.id.desc()).first()
    attendance_locked = bool(period and str(period.status).lower() in {"locked", "closed"})
    return {"month": month, "year": year, "total_employees": len(employees), "ready": not missing_salary and not missing_bank and not invalid_bank and not missing_pan and attendance_locked, "attendance_locked": attendance_locked, "issues": {"missing_salary": {"count": len(missing_salary), "employee_ids": missing_salary[:100]}, "missing_bank": {"count": len(missing_bank), "employee_ids": missing_bank[:100]}, "invalid_bank": {"count": len(invalid_bank), "items": invalid_bank[:100]}, "missing_pan": {"count": len(missing_pan), "employee_ids": missing_pan[:100]}}}


@router.post("/runs/{run_id}/payslip-dispatch")
def dispatch_payslip_notifications(run_id: int, channels: list[str] = Query(default=["email"]), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    run = _get_payroll_run_or_404(db, run_id)
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run_id).all()
    allowed_channels = {"email", "whatsapp", "sms"}
    requested_channels = []
    for channel in channels or ["email"]:
        normalized = channel.strip().lower()
        if normalized and normalized not in requested_channels:
            requested_channels.append(normalized)

    counts = {"sent": 0, "failed": 0, "skipped": 0}
    by_channel = {
        channel: {"sent": 0, "failed": 0, "skipped": 0}
        for channel in requested_channels
    }

    def record_result(record: PayrollRecord, channel: str, destination: str | None, result: MessagingResult) -> None:
        normalized_status = result.status if result.status in {"Sent", "Failed", "Skipped"} else "Failed"
        status_key = normalized_status.lower()
        counts[status_key] += 1
        by_channel.setdefault(channel, {"sent": 0, "failed": 0, "skipped": 0})[status_key] += 1
        db.add(PayslipDeliveryLog(
            payroll_record_id=record.id,
            employee_id=record.employee_id,
            channel=channel,
            destination=destination,
            status=normalized_status,
            message=result.message,
            sent_at=datetime.now(timezone.utc) if normalized_status == "Sent" else None,
        ))

    for record in records:
        employee = record.employee
        if not employee:
            continue
        for channel in requested_channels:
            if channel not in allowed_channels:
                record_result(record, channel, None, MessagingResult(status="Skipped", message=f"Unsupported channel: {channel}"))
                continue
            destination = employee.work_email if channel == "email" else employee.phone_number
            message = f"Your payslip for {run.month}/{run.year} is ready."
            if not destination:
                record_result(record, channel, destination, MessagingResult(status="Skipped", message=f"{channel} destination missing"))
                continue
            try:
                if channel == "email":
                    send_email(destination, "Payslip published", message)
                    result = MessagingResult(status="Sent", message="Email queued")
                elif channel == "sms":
                    result = send_sms(destination, message)
                else:
                    result = send_whatsapp(destination, message)
            except Exception as exc:
                result = MessagingResult(status="Failed", message=str(exc))
            record_result(record, channel, destination, result)
    batch = db.query(PayslipPublishBatch).filter(PayslipPublishBatch.payroll_run_id == run_id).order_by(PayslipPublishBatch.id.desc()).first()
    if batch:
        batch.email_dispatch_status = (
            f"Sent {counts['sent']}, Failed {counts['failed']}, Skipped {counts['skipped']}"
            if counts["sent"] or counts["failed"] or counts["skipped"]
            else "No Recipients"
        )
    _audit(db, run_id, "payslip_notifications_dispatched", current_user.id, f"sent={counts['sent']}:failed={counts['failed']}:skipped={counts['skipped']}:channels={','.join(requested_channels)}")
    db.commit()
    return {
        "payroll_run_id": run_id,
        "notifications_sent": counts["sent"],
        "sent": counts["sent"],
        "failed": counts["failed"],
        "skipped": counts["skipped"],
        "by_channel": by_channel,
    }


@router.post("/payslip-queries", status_code=201)
def create_payslip_query(data: PayslipQueryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    record = db.query(PayrollRecord).filter(PayrollRecord.id == data.payroll_record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    if not _can_access_employee(current_user, record.employee_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    item = PayslipQuery(payroll_record_id=record.id, employee_id=record.employee_id, subject=data.subject, description=data.description, priority=data.priority, created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/payslip-queries")
def list_payslip_queries(status: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(PayslipQuery)
    if not _has_permission(current_user, "payroll_view"):
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        query = query.filter(PayslipQuery.employee_id == current_user.employee.id)
    if status:
        query = query.filter(PayslipQuery.status == status)
    return query.order_by(PayslipQuery.id.desc()).limit(200).all()


@router.put("/payslip-queries/{query_id}/resolve")
def resolve_payslip_query(query_id: int, data: PayslipQueryResolve, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = db.query(PayslipQuery).filter(PayslipQuery.id == query_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Payslip query not found")
    item.status = data.status
    item.resolution = data.resolution
    item.assigned_to = data.assigned_to
    item.resolved_by = current_user.id
    item.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/salary-advances", status_code=201)
def create_salary_advance(data: SalaryAdvanceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee_id = data.employee_id or (current_user.employee.id if current_user.employee else None)
    if not employee_id:
        raise HTTPException(status_code=400, detail="No employee profile")
    if data.employee_id and not _has_permission(current_user, "payroll_run"):
        raise HTTPException(status_code=403, detail="Not authorized")
    item = SalaryAdvance(**data.model_dump(exclude={"employee_id"}), employee_id=employee_id, created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/salary-advances")
def list_salary_advances(employee_id: Optional[int] = Query(None), status: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(SalaryAdvance)
    if _has_permission(current_user, "payroll_view"):
        if employee_id:
            query = query.filter(SalaryAdvance.employee_id == employee_id)
    else:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        query = query.filter(SalaryAdvance.employee_id == current_user.employee.id)
    if status:
        query = query.filter(SalaryAdvance.status == status)
    return query.order_by(SalaryAdvance.id.desc()).limit(200).all()


@router.put("/salary-advances/{advance_id}/review")
def review_salary_advance(advance_id: int, data: SalaryAdvanceReview, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_approve"))):
    item = db.query(SalaryAdvance).filter(SalaryAdvance.id == advance_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Salary advance not found")
    action = data.action.lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    item.status = "Approved" if action == "approve" else "Rejected"
    item.approved_amount = (data.approved_amount or item.requested_amount) if action == "approve" else Decimal("0")
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_remarks = data.remarks
    db.commit()
    db.refresh(item)
    return item


@router.post("/salary-revisions/bulk", status_code=201)
def create_bulk_salary_revision(data: SalaryRevisionBatchCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    batch = SalaryRevisionBatch(name=data.name, effective_from=data.effective_from, total_rows=len(data.lines), created_by=current_user.id)
    db.add(batch)
    db.flush()
    for line in data.lines:
        current_salary = _active_employee_salary(db, line.employee_id)
        db.add(SalaryRevisionBatchLine(batch_id=batch.id, employee_id=line.employee_id, current_ctc=current_salary.ctc if current_salary else Decimal("0"), new_ctc=line.new_ctc, structure_id=line.structure_id))
    db.commit()
    db.refresh(batch)
    return batch


@router.put("/salary-revisions/bulk/{batch_id}/apply")
def apply_bulk_salary_revision(batch_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_approve"))):
    batch = db.query(SalaryRevisionBatch).filter(SalaryRevisionBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Salary revision batch not found")
    applied = 0
    for line in batch.lines:
        existing = _active_employee_salary(db, line.employee_id)
        if existing:
            existing.is_active = False
            existing.effective_to = batch.effective_from - timedelta(days=1)
        db.add(EmployeeSalary(employee_id=line.employee_id, structure_id=line.structure_id, ctc=line.new_ctc, effective_from=batch.effective_from, effective_date=batch.effective_from, is_active=True))
        line.status = "Applied"
        applied += 1
    batch.status = "Applied"
    batch.applied_rows = applied
    batch.applied_by = current_user.id
    batch.applied_at = datetime.now(timezone.utc)
    db.commit()
    return {"batch_id": batch_id, "applied_rows": applied, "total_rows": batch.total_rows}


@router.post("/bank/validate")
def validate_bank_details(run_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    employees = db.query(Employee).filter(Employee.deleted_at.is_(None), Employee.status.in_(["Active", "Probation"])).all()
    if run_id:
        employee_ids = {row[0] for row in db.query(PayrollRecord.employee_id).filter(PayrollRecord.payroll_run_id == run_id).all()}
        employees = [employee for employee in employees if employee.id in employee_ids]
    db.query(PayrollBankValidation).filter(PayrollBankValidation.payroll_run_id == run_id).delete(synchronize_session=False)
    seen_accounts: dict[str, int] = {}
    results = []
    for employee in employees:
        errors = _validate_employee_bank(employee, seen_accounts)
        status_value = "Failed" if errors else "Passed"
        if errors:
            for error in errors:
                db.add(PayrollBankValidation(payroll_run_id=run_id, employee_id=employee.id, status=status_value, error_code=error["code"], message=error["message"]))
        else:
            db.add(PayrollBankValidation(payroll_run_id=run_id, employee_id=employee.id, status=status_value, message="Bank details valid"))
        results.append({"employee_id": employee.id, "status": status_value, "errors": errors})
    db.commit()
    return {"run_id": run_id, "total": len(results), "failed": sum(1 for row in results if row["status"] == "Failed"), "items": results}


def _tax_section_limit(db: Session, financial_year: str, section_code: str, fallback: Decimal) -> Decimal:
    section = db.query(TaxSection).filter(func.upper(TaxSection.section_code) == section_code.upper()).first()
    if not section:
        return fallback
    limit = (
        db.query(TaxSectionLimit)
        .filter(TaxSectionLimit.tax_section_id == section.id, TaxSectionLimit.financial_year == financial_year)
        .order_by(TaxSectionLimit.tax_regime_id.isnot(None), TaxSectionLimit.id.desc())
        .first()
    )
    return Decimal(limit.limit_amount or 0) if limit else fallback


def _capped(value: Decimal, limit: Decimal) -> Decimal:
    return min(Decimal(value or 0), Decimal(limit or 0)).quantize(Decimal("0.01"))


def _computed_hra_exemption(data: TaxOptimizerRequest) -> Decimal:
    if data.hra_basic_salary is None or data.hra_received is None or data.rent_paid is None:
        return Decimal(data.hra_exemption or 0).quantize(Decimal("0.01"))
    basic = Decimal(data.hra_basic_salary or 0)
    rent_minus_ten_percent_basic = max(Decimal("0"), Decimal(data.rent_paid or 0) - (basic * Decimal("0.10")))
    city_factor = Decimal("0.50") if data.hra_is_metro else Decimal("0.40")
    computed = min(Decimal(data.hra_received or 0), rent_minus_ten_percent_basic, basic * city_factor)
    return max(Decimal(data.hra_exemption or 0), computed).quantize(Decimal("0.01"))


def _previous_employment_totals(db: Session, data: TaxOptimizerRequest) -> tuple[Decimal, Decimal]:
    previous = db.query(PreviousEmploymentTaxDetail).filter(
        PreviousEmploymentTaxDetail.employee_id == data.employee_id,
        PreviousEmploymentTaxDetail.financial_year == data.financial_year,
    ).all()
    income = sum((item.taxable_income or Decimal("0")) for item in previous)
    tds = sum((item.tds_deducted or Decimal("0")) for item in previous)
    if data.previous_employment_income is not None:
        income = data.previous_employment_income
    if data.previous_employment_tds is not None:
        tds = data.previous_employment_tds
    return Decimal(income or 0), Decimal(tds or 0)


def _regime_kind(regime: TaxRegime) -> str:
    marker = f"{regime.regime_code or ''} {regime.name or ''}".upper()
    if "NEW" in marker:
        return "NEW"
    if "OLD" in marker:
        return "OLD"
    return (regime.regime_code or "").upper()


def _tax_optimizer_payload(data: TaxOptimizerRequest, db: Session) -> dict[str, Any]:
    limits = {
        "80C": _tax_section_limit(db, data.financial_year, "80C", Decimal("150000")),
        "80D": _tax_section_limit(db, data.financial_year, "80D", Decimal("100000")),
        "80CCD(1B)": _tax_section_limit(db, data.financial_year, "80CCD(1B)", Decimal("50000")),
        "HOME_LOAN_INTEREST": _tax_section_limit(db, data.financial_year, "HOME_LOAN_INTEREST", Decimal("200000")),
    }
    deductions_by_section = {
        "80C": _capped(data.section_80c_declared, limits["80C"]),
        "80D": _capped(data.section_80d_declared, limits["80D"]),
        "80CCD(1B)": _capped(data.nps_80ccd_1b_declared, limits["80CCD(1B)"]),
        "HOME_LOAN_INTEREST": _capped(data.home_loan_interest, limits["HOME_LOAN_INTEREST"]),
        "OTHER": Decimal(data.other_deductions or 0).quantize(Decimal("0.01")),
    }
    old_deductions = sum(deductions_by_section.values(), Decimal("0"))
    hra_exemption = _computed_hra_exemption(data)
    old_exemptions = (hra_exemption + Decimal(data.other_exemptions or 0)).quantize(Decimal("0.01"))
    previous_income, previous_tds = _previous_employment_totals(db, data)

    regimes = db.query(TaxRegime).filter(TaxRegime.financial_year == data.financial_year, TaxRegime.is_active == True).all()
    rows: list[dict[str, Any]] = []
    for regime in regimes:
        kind = _regime_kind(regime)
        allowed_deductions = old_deductions if kind == "OLD" else Decimal("0")
        allowed_exemptions = old_exemptions if kind == "OLD" else Decimal("0")
        taxable_income = max(
            Decimal("0"),
            Decimal(data.gross_taxable_income or 0) + previous_income - allowed_deductions - allowed_exemptions - Decimal(regime.standard_deduction_amount or 0),
        ).quantize(Decimal("0.01"))
        slabs = db.query(TaxSlab).filter(TaxSlab.tax_regime_id == regime.id).order_by(TaxSlab.sequence).all()
        base_tax = _calculate_tax_from_slabs(taxable_income, slabs)
        rebate, surcharge, cess, projected_tax = _tax_with_rebate_surcharge_and_cess(base_tax, taxable_income, regime)
        balance_tax = max(Decimal("0"), projected_tax - previous_tds - Decimal(data.paid_tds or 0)).quantize(Decimal("0.01"))
        rows.append({
            "tax_regime_id": regime.id,
            "regime_code": regime.regime_code,
            "regime_name": regime.name,
            "regime_kind": kind,
            "taxable_income": taxable_income,
            "standard_deduction": Decimal(regime.standard_deduction_amount or 0),
            "deductions_applied": allowed_deductions,
            "exemptions_applied": allowed_exemptions,
            "base_tax": base_tax,
            "rebate": rebate,
            "surcharge": surcharge,
            "cess": cess,
            "projected_tax": projected_tax,
            "balance_tax": balance_tax,
            "monthly_tds": (balance_tax / Decimal(data.remaining_months)).quantize(Decimal("0.01")),
        })

    rows.sort(key=lambda row: row["projected_tax"])
    old_row = next((row for row in rows if row["regime_kind"] == "OLD"), None)
    new_row = next((row for row in rows if row["regime_kind"] == "NEW"), None)
    recommended = rows[0] if rows else None
    if old_row and new_row:
        projected_savings = abs(Decimal(old_row["projected_tax"]) - Decimal(new_row["projected_tax"])).quantize(Decimal("0.01"))
    else:
        projected_savings = Decimal("0.00")

    recommendations = [
        {
            "section": "80C",
            "max_allowed": limits["80C"],
            "already_declared": data.section_80c_declared,
            "suggested_amount": max(Decimal("0"), limits["80C"] - Decimal(data.section_80c_declared or 0)).quantize(Decimal("0.01")),
            "reason": "Payroll estimate: remaining eligible 80C declaration capacity before the configured limit.",
        },
        {
            "section": "80D",
            "max_allowed": limits["80D"],
            "already_declared": data.section_80d_declared,
            "suggested_amount": max(Decimal("0"), limits["80D"] - Decimal(data.section_80d_declared or 0)).quantize(Decimal("0.01")),
            "reason": "Payroll estimate: health insurance declaration capacity before the configured limit.",
        },
        {
            "section": "80CCD(1B)",
            "max_allowed": limits["80CCD(1B)"],
            "already_declared": data.nps_80ccd_1b_declared,
            "suggested_amount": max(Decimal("0"), limits["80CCD(1B)"] - Decimal(data.nps_80ccd_1b_declared or 0)).quantize(Decimal("0.01")),
            "reason": "Payroll estimate: additional NPS declaration capacity before the configured limit.",
        },
        {
            "section": "HRA",
            "max_allowed": hra_exemption,
            "already_declared": data.hra_exemption,
            "suggested_amount": max(Decimal("0"), hra_exemption - Decimal(data.hra_exemption or 0)).quantize(Decimal("0.01")),
            "reason": "Payroll estimate: computed from basic salary, HRA received, rent paid, and city category when supplied.",
        },
        {
            "section": "HOME_LOAN_INTEREST",
            "max_allowed": limits["HOME_LOAN_INTEREST"],
            "already_declared": data.home_loan_interest,
            "suggested_amount": max(Decimal("0"), limits["HOME_LOAN_INTEREST"] - Decimal(data.home_loan_interest or 0)).quantize(Decimal("0.01")),
            "reason": "Payroll estimate: home loan interest declaration capacity before the configured limit.",
        },
        {
            "section": "STANDARD_DEDUCTION",
            "max_allowed": max((Decimal(row["standard_deduction"]) for row in rows), default=Decimal("0")),
            "already_declared": Decimal("0"),
            "suggested_amount": Decimal("0"),
            "reason": "Payroll estimate: applied automatically from the active tax regime configuration.",
        },
    ]

    return {
        "employee_id": data.employee_id,
        "financial_year": data.financial_year,
        "old_regime_tax": old_row["projected_tax"] if old_row else None,
        "new_regime_tax": new_row["projected_tax"] if new_row else None,
        "recommended_regime": recommended["regime_code"] if recommended else None,
        "recommended_regime_details": recommended,
        "projected_savings": projected_savings,
        "recommendations": recommendations,
        "regimes": rows,
        "inputs": {
            "gross_taxable_income": data.gross_taxable_income,
            "previous_employment_income": previous_income,
            "previous_employment_tds": previous_tds,
            "old_regime_deductions": old_deductions,
            "old_regime_exemptions": old_exemptions,
            "deductions_by_section": deductions_by_section,
        },
        "estimate_note": "Payroll estimate only; final tax depends on verified declarations, payroll records, and statutory configuration.",
    }


def _month_segments(start_date: date, end_date: date) -> list[tuple[date, date, Decimal]]:
    segments: list[tuple[date, date, Decimal]] = []
    cursor = start_date
    while cursor <= end_date:
        month_days = calendar.monthrange(cursor.year, cursor.month)[1]
        segment_end = min(end_date, date(cursor.year, cursor.month, month_days))
        covered_days = Decimal((segment_end - cursor).days + 1)
        factor = (covered_days / Decimal(month_days)).quantize(Decimal("0.0001"))
        segments.append((cursor, segment_end, factor))
        cursor = segment_end + timedelta(days=1)
    return segments


def _salary_component_snapshot(db: Session, ctc: Decimal, structure_id: int | None) -> list[dict[str, Any]]:
    monthly_ctc = (Decimal(ctc or 0) / Decimal("12")).quantize(Decimal("0.01"))
    if structure_id:
        structure = db.query(SalaryStructure).filter(SalaryStructure.id == structure_id).first()
        if structure:
            variables = {"ctc_monthly": monthly_ctc, "ctc_annual": Decimal(ctc or 0)}
            rows: list[dict[str, Any]] = []
            ordered, _warnings = _ordered_structure_components(structure)
            for item in ordered:
                component = item.component
                if not component:
                    continue
                amount = _component_monthly_amount(item, monthly_ctc, variables)
                variables[component.code] = amount
                variables[component.code.lower()] = amount
                rows.append({
                    "component_id": component.id,
                    "code": component.code or "",
                    "name": component.name or component.code or "Component",
                    "type": component.component_type or "Earning",
                    "amount": amount,
                    "pf_wage": bool(component.pf_wage_flag or component.is_pf_applicable),
                    "esi_wage": bool(component.esi_wage_flag or component.is_esi_applicable),
                })
            if rows:
                return rows

    basic = (monthly_ctc * Decimal("0.40")).quantize(Decimal("0.01"))
    hra = (basic * Decimal("0.50")).quantize(Decimal("0.01"))
    other = (monthly_ctc - basic - hra).quantize(Decimal("0.01"))
    return [
        {"component_id": None, "code": "BASIC", "name": "Basic", "type": "Earning", "amount": basic, "pf_wage": True, "esi_wage": True},
        {"component_id": None, "code": "HRA", "name": "House Rent Allowance", "type": "Earning", "amount": hra, "pf_wage": False, "esi_wage": True},
        {"component_id": None, "code": "OTHER", "name": "Other Earnings", "type": "Earning", "amount": other, "pf_wage": False, "esi_wage": True},
    ]


def _arrear_earning_buckets(rows: list[dict[str, Any]]) -> dict[str, Decimal]:
    buckets = {"Basic arrear": Decimal("0"), "HRA arrear": Decimal("0"), "Other earnings arrear": Decimal("0")}
    for row in rows:
        if (row.get("type") or "").lower() != "earning":
            continue
        code = (row.get("code") or "").upper()
        name = (row.get("name") or "").lower()
        amount = Decimal(row.get("amount") or 0)
        if code in {"BASIC", "BASIC_SALARY"} or "basic" in name:
            buckets["Basic arrear"] += amount
        elif code == "HRA" or "house rent" in name or "rent allowance" in name:
            buckets["HRA arrear"] += amount
        else:
            buckets["Other earnings arrear"] += amount
    return {key: value.quantize(Decimal("0.01")) for key, value in buckets.items()}


def _arrear_gross(rows: list[dict[str, Any]]) -> Decimal:
    return sum((Decimal(row.get("amount") or 0) for row in rows if (row.get("type") or "").lower() == "earning"), Decimal("0")).quantize(Decimal("0.01"))


def _arrear_wage(rows: list[dict[str, Any]], flag: str, fallback: Decimal) -> Decimal:
    wage = sum((Decimal(row.get("amount") or 0) for row in rows if row.get(flag)), Decimal("0"))
    return (wage if wage > 0 else fallback).quantize(Decimal("0.01"))


def _pt_amount_for_salary(db: Session, employee: Employee, salary: Decimal, on_date: date) -> Decimal:
    state = employee.present_state or employee.permanent_state
    if not state:
        return Decimal("0.00")
    slabs = db.query(ProfessionalTaxSlab).filter(
        ProfessionalTaxSlab.is_active == True,
        ProfessionalTaxSlab.state == state,
        ProfessionalTaxSlab.effective_from <= on_date,
    ).filter(
        (ProfessionalTaxSlab.effective_to == None) | (ProfessionalTaxSlab.effective_to >= on_date),
        (ProfessionalTaxSlab.month == None) | (ProfessionalTaxSlab.month == on_date.month),
    ).all()
    for slab in slabs:
        salary_from = Decimal(slab.salary_from or 0)
        salary_to = Decimal(slab.salary_to) if slab.salary_to is not None else None
        if salary >= salary_from and (salary_to is None or salary <= salary_to):
            return Decimal(slab.employee_amount or 0).quantize(Decimal("0.01"))
    return Decimal("0.00")


@router.get("/tax/optimizer")
def tax_saving_optimizer(
    employee_id: int,
    financial_year: str,
    gross_taxable_income: Decimal,
    declared_deductions: Decimal = Decimal("0"),
    hra_exemption: Decimal = Decimal("0"),
    paid_tds: Decimal = Decimal("0"),
    section_80d_declared: Decimal = Decimal("0"),
    nps_80ccd_1b_declared: Decimal = Decimal("0"),
    home_loan_interest: Decimal = Decimal("0"),
    other_deductions: Decimal = Decimal("0"),
    hra_basic_salary: Decimal | None = None,
    hra_received: Decimal | None = None,
    rent_paid: Decimal | None = None,
    hra_is_metro: bool = False,
    other_exemptions: Decimal = Decimal("0"),
    remaining_months: int = Query(12, ge=1, le=12),
    previous_employment_income: Decimal | None = None,
    previous_employment_tds: Decimal | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    data = TaxOptimizerRequest(
        employee_id=employee_id,
        financial_year=financial_year,
        gross_taxable_income=gross_taxable_income,
        section_80c_declared=declared_deductions,
        section_80d_declared=section_80d_declared,
        nps_80ccd_1b_declared=nps_80ccd_1b_declared,
        home_loan_interest=home_loan_interest,
        other_deductions=other_deductions,
        hra_exemption=hra_exemption,
        hra_basic_salary=hra_basic_salary,
        hra_received=hra_received,
        rent_paid=rent_paid,
        hra_is_metro=hra_is_metro,
        other_exemptions=other_exemptions,
        paid_tds=paid_tds,
        remaining_months=remaining_months,
        previous_employment_income=previous_employment_income,
        previous_employment_tds=previous_employment_tds,
    )
    return _tax_optimizer_payload(data, db)


@router.post("/tax/optimizer")
def tax_saving_optimizer_post(data: TaxOptimizerRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return _tax_optimizer_payload(data, db)


@router.post("/arrear-runs/auto-calculate", status_code=201)
def auto_calculate_arrears(payroll_run_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    run = _get_payroll_run_or_404(db, payroll_run_id)
    period_start = run.pay_period_start or date(run.year, run.month, 1)
    arrear_to_date = period_start - timedelta(days=1)
    revisions = db.query(SalaryRevisionRequest).filter(
        SalaryRevisionRequest.status == "Applied",
        SalaryRevisionRequest.effective_from < period_start,
    ).order_by(SalaryRevisionRequest.employee_id, SalaryRevisionRequest.effective_from).all()

    arrear_run = db.query(PayrollArrearRun).filter(
        PayrollArrearRun.payroll_run_id == run.id,
        PayrollArrearRun.name == f"Auto arrears {run.month}/{run.year}",
    ).first()
    if not arrear_run:
        arrear_run = PayrollArrearRun(
            payroll_run_id=run.id,
            name=f"Auto arrears {run.month}/{run.year}",
            reason="Auto calculated from applied backdated salary revisions",
            status="Draft",
            created_by=current_user.id,
        )
        db.add(arrear_run)
        db.flush()

    employees = {
        employee.id: employee
        for employee in db.query(Employee).filter(Employee.id.in_([revision.employee_id for revision in revisions])).all()
    } if revisions else {}
    old_salaries = {
        salary.id: salary
        for salary in db.query(EmployeeSalary).filter(EmployeeSalary.id.in_([revision.current_salary_id for revision in revisions if revision.current_salary_id])).all()
    }
    statutory_profiles = {
        profile.employee_id: profile
        for profile in db.query(EmployeeStatutoryProfile).filter(EmployeeStatutoryProfile.employee_id.in_(list(employees.keys()))).all()
    } if employees else {}

    employees_processed: set[int] = set()
    lines_created = 0
    gross_arrear = Decimal("0")
    deduction_arrear = Decimal("0")

    for revision in revisions:
        employee = employees.get(revision.employee_id)
        if not employee:
            continue
        duplicate = db.query(PayrollArrearLine.id).join(
            PayrollArrearRun, PayrollArrearLine.arrear_run_id == PayrollArrearRun.id,
        ).filter(
            PayrollArrearRun.payroll_run_id == run.id,
            PayrollArrearLine.employee_id == revision.employee_id,
            PayrollArrearLine.reason.ilike(f"%revision #{revision.id}%"),
        ).first()
        if duplicate:
            continue
        employees_processed.add(revision.employee_id)

        old_salary = old_salaries.get(revision.current_salary_id)
        old_structure_id = old_salary.structure_id if old_salary else revision.proposed_structure_id
        new_structure_id = revision.proposed_structure_id or old_structure_id
        old_rows = _salary_component_snapshot(db, Decimal(revision.current_ctc or 0), old_structure_id)
        new_rows = _salary_component_snapshot(db, Decimal(revision.proposed_ctc or 0), new_structure_id)
        old_buckets = _arrear_earning_buckets(old_rows)
        new_buckets = _arrear_earning_buckets(new_rows)
        component_totals: dict[tuple[str, str], Decimal] = {}

        for segment_start, segment_end, factor in _month_segments(revision.effective_from, arrear_to_date):
            segment_old_gross = _arrear_gross(old_rows)
            segment_new_gross = _arrear_gross(new_rows)
            for name in ("Basic arrear", "HRA arrear", "Other earnings arrear"):
                delta = ((new_buckets[name] - old_buckets[name]) * factor).quantize(Decimal("0.01"))
                if delta:
                    component_totals[(name, "Earning")] = component_totals.get((name, "Earning"), Decimal("0")) + delta

            pf_rule = _active_rule(db.query(PFRule), segment_end)
            profile = statutory_profiles.get(revision.employee_id)
            pf_applicable = bool(pf_rule and (profile is None or profile.pf_applicable))
            if pf_applicable:
                old_pf_wage = _arrear_wage(old_rows, "pf_wage", old_buckets["Basic arrear"])
                new_pf_wage = _arrear_wage(new_rows, "pf_wage", new_buckets["Basic arrear"])
                old_pf = _rounded_money(min(old_pf_wage, Decimal(pf_rule.wage_ceiling or old_pf_wage)) * Decimal(pf_rule.employee_rate or 0) / Decimal("100"), pf_rule.rounding_rule)
                new_pf = _rounded_money(min(new_pf_wage, Decimal(pf_rule.wage_ceiling or new_pf_wage)) * Decimal(pf_rule.employee_rate or 0) / Decimal("100"), pf_rule.rounding_rule)
                delta = ((new_pf - old_pf) * factor).quantize(Decimal("0.01"))
                if delta:
                    component_totals[("PF arrear", "Deduction")] = component_totals.get(("PF arrear", "Deduction"), Decimal("0")) + delta

            esi_rule = _active_rule(db.query(ESIRule), segment_end)
            esi_applicable = bool(esi_rule and ((profile and profile.esi_applicable) or employee.esic_number))
            if esi_applicable:
                old_esi_wage = _arrear_wage(old_rows, "esi_wage", segment_old_gross)
                new_esi_wage = _arrear_wage(new_rows, "esi_wage", segment_new_gross)
                old_esi = _rounded_money(old_esi_wage * Decimal(esi_rule.employee_rate or 0) / Decimal("100"), esi_rule.rounding_rule) if old_esi_wage <= Decimal(esi_rule.wage_threshold or 0) else Decimal("0.00")
                new_esi = _rounded_money(new_esi_wage * Decimal(esi_rule.employee_rate or 0) / Decimal("100"), esi_rule.rounding_rule) if new_esi_wage <= Decimal(esi_rule.wage_threshold or 0) else Decimal("0.00")
                delta = ((new_esi - old_esi) * factor).quantize(Decimal("0.01"))
                if delta:
                    component_totals[("ESI arrear", "Deduction")] = component_totals.get(("ESI arrear", "Deduction"), Decimal("0")) + delta

            old_pt = _pt_amount_for_salary(db, employee, segment_old_gross, segment_end)
            new_pt = _pt_amount_for_salary(db, employee, segment_new_gross, segment_end)
            delta = ((new_pt - old_pt) * factor).quantize(Decimal("0.01"))
            if delta:
                component_totals[("PT arrear", "Deduction")] = component_totals.get(("PT arrear", "Deduction"), Decimal("0")) + delta

        for (component_name, arrear_type), amount in component_totals.items():
            amount = amount.quantize(Decimal("0.01"))
            if amount == 0:
                continue
            db.add(PayrollArrearLine(
                arrear_run_id=arrear_run.id,
                employee_id=revision.employee_id,
                component_name=component_name,
                arrear_type=arrear_type,
                amount=amount,
                from_date=revision.effective_from,
                to_date=arrear_to_date,
                reason=f"Auto calculated from salary revision #{revision.id}",
                status="Pending",
            ))
            lines_created += 1
            if arrear_type == "Deduction":
                deduction_arrear += amount
            else:
                gross_arrear += amount

    db.commit()
    db.refresh(arrear_run)
    return {
        "arrear_run_id": arrear_run.id,
        "employees_processed": len(employees_processed),
        "lines_created": lines_created,
        "gross_arrear": gross_arrear.quantize(Decimal("0.01")),
        "deduction_arrear": deduction_arrear.quantize(Decimal("0.01")),
        "net_arrear": (gross_arrear - deduction_arrear).quantize(Decimal("0.01")),
    }


@router.post("/bonus-policies", status_code=201)
def create_bonus_policy(data: BonusPolicyPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = BonusPolicy(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/bonus-policies")
def list_bonus_policies(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(BonusPolicy).filter(BonusPolicy.is_active == True).order_by(BonusPolicy.id.desc()).all()


@router.post("/bonus-policies/apply")
def apply_bonus_policy(data: BonusPolicyApplyRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    run = _get_payroll_run_or_404(db, data.payroll_run_id)
    policy = db.query(BonusPolicy).filter(BonusPolicy.id == data.policy_id, BonusPolicy.is_active == True).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Bonus policy not found")
    employees = db.query(Employee).filter(Employee.deleted_at.is_(None), Employee.status.in_(["Active", "Probation"])).all()
    created = 0
    for employee in employees:
        if policy.department_id and employee.department_id != policy.department_id:
            continue
        if policy.grade_band_id and employee.grade_band_id != policy.grade_band_id:
            continue
        salary = _active_employee_salary(db, employee.id)
        if not salary:
            continue
        if policy.amount_type == "PercentageOfCTC":
            amount = (Decimal(salary.ctc or 0) / Decimal("12") * Decimal(policy.amount_value or 0) / Decimal("100")).quantize(Decimal("0.01"))
        elif policy.amount_type == "PercentageOfBasic":
            amount = (Decimal(salary.basic or 0) * Decimal(policy.amount_value or 0) / Decimal("100")).quantize(Decimal("0.01"))
        else:
            amount = Decimal(policy.amount_value or 0)
        db.add(PayrollManualInput(payroll_run_id=run.id, employee_id=employee.id, input_type="Bonus", component_name=policy.name, amount=amount, status="Approved", approved_by=current_user.id, approved_at=datetime.now(timezone.utc), created_by=current_user.id))
        created += 1
    db.commit()
    return {"payroll_run_id": run.id, "policy_id": policy.id, "bonus_inputs_created": created}


@router.post("/runs/{run_id}/gratuity-accruals")
def generate_gratuity_accruals(run_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    run = _get_payroll_run_or_404(db, run_id)
    calculation_date = run.pay_period_end or run.run_date or date(run.year, run.month, calendar.monthrange(run.year, run.month)[1])
    rule = _active_rule(db.query(GratuityRule), calculation_date)
    if not rule:
        raise HTTPException(status_code=400, detail=f"No active GratuityRule found for payroll date {calculation_date.isoformat()}")

    days_per_year = Decimal(rule.days_per_year or 0)
    wage_days_divisor = Decimal(rule.wage_days_divisor or 0)
    min_service_years = Decimal(rule.min_service_years or 0)
    if days_per_year <= 0:
        raise HTTPException(status_code=400, detail="Active GratuityRule has invalid days_per_year")
    if wage_days_divisor <= 0:
        raise HTTPException(status_code=400, detail="Active GratuityRule has invalid wage_days_divisor")

    db.query(GratuityAccrual).filter(GratuityAccrual.payroll_run_id == run_id).delete(synchronize_session=False)
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run_id).all()
    employees = {
        employee.id: employee
        for employee in db.query(Employee).filter(Employee.id.in_([record.employee_id for record in records])).all()
    } if records else {}
    total = Decimal("0")
    posted_count = 0
    ineligible_count = 0
    skipped_count = 0

    for record in records:
        employee = employees.get(record.employee_id)
        wage = Decimal(record.basic or 0)
        accrual = Decimal("0.00")
        status = "Posted"

        if not employee or not employee.date_of_joining or employee.date_of_joining > calculation_date:
            status = "Ineligible"
            ineligible_count += 1
        else:
            service_days = max(0, (calculation_date - employee.date_of_joining).days + 1)
            service_years = Decimal(service_days) / Decimal("365.2425")
            if service_years < min_service_years:
                status = "Ineligible"
                ineligible_count += 1
            elif wage <= 0:
                status = "Skipped"
                skipped_count += 1
            else:
                accrual = _rounded_money(wage * days_per_year / wage_days_divisor / Decimal("12"), rule.rounding_rule)
                total += accrual
                posted_count += 1

        db.add(GratuityAccrual(
            employee_id=record.employee_id,
            payroll_run_id=run_id,
            month=run.month,
            year=run.year,
            gratuity_wage=wage,
            accrual_amount=accrual,
            status=status,
        ))
    db.commit()
    return {
        "payroll_run_id": run_id,
        "total_employees": len(records),
        "accruals_created": posted_count,
        "ineligible_count": ineligible_count,
        "skipped_count": skipped_count,
        "total_accrual": total.quantize(Decimal("0.01")),
        "rule_id": rule.id,
    }


@router.post("/salary-certificates", status_code=201)
def generate_salary_certificate(data: SalaryCertificateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee_id = data.employee_id or (current_user.employee.id if current_user.employee else None)
    if not employee_id:
        raise HTTPException(status_code=400, detail="No employee profile")
    if data.employee_id and not _has_permission(current_user, "payroll_view"):
        raise HTTPException(status_code=403, detail="Not authorized")
    employee = _employee_or_404(db, employee_id)
    salary = _active_employee_salary(db, employee_id)
    annual_ctc = Decimal(salary.ctc or 0) if salary else Decimal("0")
    monthly_gross = (annual_ctc / Decimal("12")).quantize(Decimal("0.01")) if annual_ctc else Decimal("0")
    cert_dir = os.path.join(settings.UPLOAD_DIR, "salary_certificates")
    os.makedirs(cert_dir, exist_ok=True)
    file_name = f"salary_certificate_{employee_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
    file_path = os.path.join(cert_dir, file_name)
    _write_basic_pdf(file_path, ["Salary Certificate", f"Employee: {employee.employee_id} - {employee.first_name} {employee.last_name}", f"Purpose: {data.purpose}", f"Annual CTC: {annual_ctc}", f"Monthly Gross: {monthly_gross}"])
    item = SalaryCertificate(employee_id=employee_id, purpose=data.purpose, period_from=data.period_from, period_to=data.period_to, annual_ctc=annual_ctc, monthly_gross=monthly_gross, file_url=_file_url_from_upload_path(file_path), generated_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/budgets", status_code=201)
def create_payroll_budget(data: PayrollBudgetCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = PayrollBudget(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/budgets/variance")
def payroll_budget_variance(month: int, year: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    budgets = db.query(PayrollBudget).filter(PayrollBudget.month == month, PayrollBudget.year == year).all()
    run = db.query(PayrollRun).filter(PayrollRun.month == month, PayrollRun.year == year, PayrollRun.deleted_at.is_(None)).order_by(PayrollRun.id.desc()).first()
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run.id).all() if run else []
    rows = []
    for budget in budgets:
        employee_query = db.query(Employee.id)
        if budget.department_id:
            employee_query = employee_query.filter(Employee.department_id == budget.department_id)
        ids = {row[0] for row in employee_query.all()}
        actual = sum((record.gross_salary or Decimal("0")) for record in records if record.employee_id in ids)
        rows.append({"budget_id": budget.id, "department_id": budget.department_id, "cost_center_id": budget.cost_center_id, "budget_amount": budget.budget_amount, "actual_amount": actual, "variance": actual - Decimal(budget.budget_amount or 0)})
    return {"month": month, "year": year, "rows": rows}


@router.post("/bank-file/validate")
def validate_bank_file_format(run_id: int, bank_name: str, payment_mode: str = "NEFT", db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run_id).all()
    rows: list[dict[str, Any]] = []
    for record in records:
        employee = record.employee
        rows.append({
            "payroll_record_id": record.id,
            "employee_id": record.employee_id,
            "employee_code": employee.employee_id if employee else None,
            "employee_name": " ".join(part for part in [employee.first_name, employee.middle_name, employee.last_name] if part).strip() if employee else None,
            "account_holder_name": " ".join(part for part in [employee.first_name, employee.middle_name, employee.last_name] if part).strip() if employee else None,
            "account_number": employee.account_number if employee else None,
            "ifsc": employee.ifsc_code if employee else None,
            "net_payable": record.net_salary,
        })
    validation = validate_bank_file_rows(rows, bank_name=bank_name, payment_mode=payment_mode)
    item = PayrollBankFileValidation(
        payroll_run_id=run_id,
        bank_name=bank_name,
        status=validation["status"],
        error_count=len(validation["errors"]),
        errors_json=validation["errors"],
        warnings_json=validation["warnings"],
        created_by=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "payroll_run_id": run_id,
        "bank_name": bank_name,
        "payment_mode": validation["payment_mode"],
        "status": item.status,
        "checked_rows": validation["checked_rows"],
        "errors_json": item.errors_json,
        "warnings_json": item.warnings_json,
    }


@router.post("/tds-26as/reconcile", status_code=201)
def reconcile_tds_26as(data: TDS26ASReconciliationCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    company_tds = Decimal(db.query(func.coalesce(func.sum(PayrollRecord.tds), 0)).join(PayrollRun).filter(PayrollRecord.employee_id == data.employee_id, PayrollRun.year == int(data.financial_year[:4])).scalar() or 0)
    diff = company_tds - data.reported_26as_tds
    item = TDS26ASReconciliation(employee_id=data.employee_id, financial_year=data.financial_year, company_tds=company_tds, reported_26as_tds=data.reported_26as_tds, difference=diff, status="Matched" if abs(diff) <= Decimal("1") else "Mismatch", remarks=data.remarks, created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/form-12ba", status_code=201)
def generate_form_12ba(data: Form12BACreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    employee = _employee_or_404(db, data.employee_id)
    total = sum(Decimal(str(item.get("value", 0))) for item in data.perquisites)
    safe_financial_year = re.sub(r"[^A-Za-z0-9_-]", "_", data.financial_year)
    form_dir = os.path.join(settings.UPLOAD_DIR, "form_12ba", safe_financial_year)
    os.makedirs(form_dir, exist_ok=True)
    file_name = f"form_12ba_{employee.employee_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
    file_path = os.path.join(form_dir, file_name)
    lines = [
        "Form 12BA - Statement of Perquisites",
        f"Employee: {employee.employee_id} - {employee.first_name} {employee.last_name}",
        f"Financial Year: {data.financial_year}",
        f"Generated Date: {datetime.now(timezone.utc).date().isoformat()}",
        "Perquisites:",
    ]
    if data.perquisites:
        for index, perquisite in enumerate(data.perquisites, start=1):
            name = perquisite.get("name") or perquisite.get("type") or perquisite.get("description") or f"Perquisite {index}"
            value = Decimal(str(perquisite.get("value", 0))).quantize(Decimal("0.01"))
            lines.append(f"{index}. {name}: INR {value}")
    else:
        lines.append("No perquisites declared.")
    lines.append(f"Total Perquisite Value: INR {total.quantize(Decimal('0.01'))}")
    _write_basic_pdf(file_path, lines)
    item = Form12BARecord(employee_id=data.employee_id, financial_year=data.financial_year, perquisites_json=data.perquisites, total_perquisite_value=total, file_url=_file_url_from_upload_path(file_path), generated_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/form-12ba/{record_id}/download")
def download_form_12ba(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(Form12BARecord).filter(Form12BARecord.id == record_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Form 12BA record not found")
    if not _can_access_employee(current_user, item.employee_id):
        raise HTTPException(status_code=403, detail="Not authorized")
    if not item.file_url:
        raise HTTPException(status_code=404, detail="Form 12BA PDF has not been generated")
    file_path = os.path.join(settings.UPLOAD_DIR, item.file_url.replace("/uploads/", "").replace("/", os.sep))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Form 12BA PDF file not found")
    return FileResponse(file_path, media_type="application/pdf", filename=os.path.basename(file_path))


@router.post("/statutory/portal-submit")
def statutory_portal_submit(
    data: StatutoryPortalSubmitRequest | None = Body(default=None),
    portal: str | None = Query(default=None),
    file_type: str | None = Query(default=None),
    file_url: str | None = Query(default=None),
    payroll_run_id: int | None = Query(default=None),
    legal_entity_id: int | None = Query(default=None),
    remarks: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    payload = data.model_dump() if data else {}
    portal_value = (portal or payload.get("portal") or "EPFO").strip().upper()
    file_type_value = file_type or payload.get("file_type")
    file_url_value = file_url or payload.get("file_url")
    payroll_run_id_value = payroll_run_id or payload.get("payroll_run_id")
    legal_entity_id_value = legal_entity_id or payload.get("legal_entity_id")
    remarks_value = remarks or payload.get("remarks")

    allowed_portals = {"EPFO", "ESIC", "TRACES", "STATE_PT"}
    if portal_value not in allowed_portals:
        raise HTTPException(status_code=400, detail=f"portal must be one of {', '.join(sorted(allowed_portals))}")
    if not file_type_value or not file_url_value:
        raise HTTPException(status_code=400, detail="file_type and file_url are required")

    run = _get_payroll_run_or_404(db, int(payroll_run_id_value)) if payroll_run_id_value else None
    legal_entity = None
    if legal_entity_id_value:
        legal_entity = db.query(PayrollLegalEntity).filter(PayrollLegalEntity.id == int(legal_entity_id_value)).first()
    if not legal_entity:
        legal_entity = db.query(PayrollLegalEntity).filter(PayrollLegalEntity.is_default == True, PayrollLegalEntity.is_active == True).order_by(PayrollLegalEntity.id.desc()).first()
    if not legal_entity:
        legal_entity = db.query(PayrollLegalEntity).filter(PayrollLegalEntity.is_active == True).order_by(PayrollLegalEntity.id.desc()).first()
    if not legal_entity:
        raise HTTPException(status_code=400, detail="Configure a payroll legal entity before tracking statutory portal submissions")

    credential_providers = {
        portal_value,
        f"{portal_value}_PORTAL",
        f"STATUTORY_{portal_value}",
        "STATUTORY_PORTAL",
    }
    has_credentials = db.query(IntegrationCredential).filter(
        IntegrationCredential.provider.in_(credential_providers),
        IntegrationCredential.status == "Active",
    ).first() is not None
    connector_supported = portal_value in {"EPFO", "ESIC", "TRACES"}

    # TODO: Replace this status decision with a real portal connector once official
    # EPFO/ESIC/TRACES integration credentials and API contracts are configured.
    if not connector_supported:
        status = "ManualUploadRequired"
        next_action = "Upload this file manually on the state professional tax portal and record the acknowledgement."
    elif has_credentials:
        status = "Queued"
        next_action = "Connector credentials are configured; submit through the statutory connector worker when enabled."
    else:
        status = "PendingCredentials"
        next_action = f"Configure active integration credentials for {portal_value} before API submission; manual upload can continue."

    period_month = run.month if run else date.today().month
    period_year = run.year if run else date.today().year
    submission = StatutoryPortalSubmission(
        legal_entity_id=legal_entity.id,
        portal_type=portal_value,
        period_month=period_month,
        period_year=period_year,
        submission_type=file_type_value,
        status=status,
        upload_file_url=file_url_value,
        submitted_by=current_user.id,
        remarks=remarks_value or next_action,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    if run:
        _audit(db, run.id, "statutory_portal_submission_tracked", current_user.id, f"submission_id={submission.id}:portal={portal_value}:status={status}")
        db.commit()

    return {
        "submission_id": submission.id,
        "status": status,
        "portal": portal_value,
        "next_action": next_action,
        "file_type": file_type_value,
        "file_url": file_url_value,
        "payroll_run_id": run.id if run else None,
        "legal_entity_id": legal_entity.id,
    }


@router.post("/reimbursements/link-expense-claims")
def link_expense_claims_to_reimbursements(payroll_run_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    run = _get_payroll_run_or_404(db, payroll_run_id)
    period_start = run.pay_period_start or date(run.year, run.month, 1)
    period_end = run.pay_period_end or date(run.year, run.month, calendar.monthrange(run.year, run.month)[1])
    claims = db.query(ExpenseClaim).filter(
        ExpenseClaim.status.in_(["finance_approved", "approved", "Approved"]),
        ExpenseClaim.expense_date >= period_start,
        ExpenseClaim.expense_date <= period_end,
    ).all()
    created = 0
    skipped_duplicates = 0
    linked_claim_ids: list[int] = []
    for claim in claims:
        if claim.payroll_reimbursement_id:
            skipped_duplicates += 1
            continue
        reimbursement = Reimbursement(
            employee_id=claim.employee_id,
            category=claim.claim_type,
            amount=claim.approved_amount or claim.amount,
            date=claim.expense_date,
            description=claim.description,
            receipt_url=claim.receipt_url,
            status="Approved",
            approved_by=current_user.id,
        )
        db.add(reimbursement)
        db.flush()
        claim.payroll_reimbursement_id = reimbursement.id
        claim.payroll_run_id = payroll_run_id
        linked_claim_ids.append(claim.id)
        created += 1
    db.commit()
    return {
        "payroll_run_id": payroll_run_id,
        "claims_found": len(claims),
        "reimbursements_created": created,
        "skipped_duplicates": skipped_duplicates,
        "linked_claim_ids": linked_claim_ids,
    }


@router.post("/setup/periods/auto-generate", status_code=201)
def auto_generate_payroll_periods(pay_group_id: int, year: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    from app.models.payroll import PayrollPayGroup

    pay_group = db.query(PayrollPayGroup).filter(PayrollPayGroup.id == pay_group_id).first()
    if not pay_group:
        raise HTTPException(status_code=404, detail="Pay group not found")
    created = 0
    for month in range(1, 13):
        period_start = date(year, month, 1)
        period_end = date(year, month, calendar.monthrange(year, month)[1])
        existing = db.query(PayrollPeriod).filter(PayrollPeriod.pay_group_id == pay_group_id, PayrollPeriod.month == month, PayrollPeriod.year == year).first()
        if existing:
            continue
        payroll_date = date(year, month, min(calendar.monthrange(year, month)[1], max(1, pay_group.pay_cycle_day or calendar.monthrange(year, month)[1])))
        cutoff_day = min(calendar.monthrange(year, month)[1], pay_group.attendance_cutoff_day or 25)
        db.add(PayrollPeriod(pay_group_id=pay_group_id, month=month, year=year, financial_year=f"{year}-{str(year + 1)[-2:]}", period_start=period_start, period_end=period_end, payroll_date=payroll_date, attendance_cutoff_at=datetime(year, month, cutoff_day, tzinfo=timezone.utc)))
        created += 1
    db.commit()
    return {"pay_group_id": pay_group_id, "year": year, "created": created}


@router.post("/cutoff-reminders")
def send_payroll_cutoff_reminders(month: int, year: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    period = db.query(PayrollPeriod).filter(PayrollPeriod.month == month, PayrollPeriod.year == year).order_by(PayrollPeriod.id.desc()).first()
    cutoff = period.attendance_cutoff_at.date() if period and period.attendance_cutoff_at else None
    manager_ids = {row[0] for row in db.query(Employee.reporting_manager_id).filter(Employee.reporting_manager_id.isnot(None), Employee.deleted_at.is_(None)).all()}
    sent = 0
    for manager in db.query(Employee).filter(Employee.id.in_(manager_ids)).all():
        if manager.work_email:
            send_email(manager.work_email, "Payroll attendance cutoff reminder", f"Please lock attendance for {month}/{year} before {cutoff or 'the payroll cutoff date'}.")
            sent += 1
    return {"month": month, "year": year, "cutoff_date": cutoff, "manager_reminders_sent": sent}


@router.post("/exchange-rates", status_code=201)
def create_exchange_rate(data: PayrollExchangeRateCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    payload = data.model_dump()
    payload["from_currency"] = data.from_currency.upper()
    payload["to_currency"] = data.to_currency.upper()
    item = PayrollExchangeRate(**payload, created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/exchange-rates")
def list_exchange_rates(
    from_currency: str | None = None,
    to_currency: str | None = None,
    effective_date: date | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollExchangeRate)
    if from_currency:
        query = query.filter(PayrollExchangeRate.from_currency == from_currency.upper())
    if to_currency:
        query = query.filter(PayrollExchangeRate.to_currency == to_currency.upper())
    if effective_date:
        query = query.filter(PayrollExchangeRate.effective_date <= effective_date)
    return query.order_by(
        PayrollExchangeRate.effective_date.desc(),
        PayrollExchangeRate.from_currency.asc(),
        PayrollExchangeRate.to_currency.asc(),
        PayrollExchangeRate.id.desc(),
    ).all()


@router.get("/multi-currency/convert")
def convert_payroll_currency(amount: Decimal, from_currency: str, to_currency: str = "INR", on_date: date = Query(default_factory=date.today), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    if from_currency.upper() == to_currency.upper():
        return {"amount": amount, "converted_amount": amount, "rate": Decimal("1")}
    rate = db.query(PayrollExchangeRate).filter(PayrollExchangeRate.from_currency == from_currency.upper(), PayrollExchangeRate.to_currency == to_currency.upper(), PayrollExchangeRate.effective_date <= on_date).order_by(PayrollExchangeRate.effective_date.desc(), PayrollExchangeRate.id.desc()).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Exchange rate not configured")
    return {"amount": amount, "from_currency": from_currency.upper(), "to_currency": to_currency.upper(), "rate": rate.rate, "converted_amount": (amount * Decimal(rate.rate)).quantize(Decimal("0.01"))}


@router.get("/analytics")
def payroll_analytics(
    month: Optional[int] = None,
    year: Optional[int] = None,
    from_month: Optional[int] = Query(None, ge=1, le=12),
    from_year: Optional[int] = Query(None, ge=1900),
    to_month: Optional[int] = Query(None, ge=1, le=12),
    to_year: Optional[int] = Query(None, ge=1900),
    department_id: Optional[int] = None,
    cost_center_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    warnings: list[str] = []
    if month and year and not any([from_month, from_year, to_month, to_year]):
        from_month = to_month = month
        from_year = to_year = year
    today = date.today()
    from_month = from_month or 1
    from_year = from_year or today.year
    to_month = to_month or from_month
    to_year = to_year or from_year
    start_index = (from_year * 12) + from_month
    end_index = (to_year * 12) + to_month
    if start_index > end_index:
        raise HTTPException(status_code=400, detail="from period cannot be after to period")

    run_period = (PayrollRun.year * 12) + PayrollRun.month

    def scoped_records_query():
        query = (
            db.query(PayrollRecord)
            .join(PayrollRun, PayrollRecord.payroll_run_id == PayrollRun.id)
            .join(Employee, PayrollRecord.employee_id == Employee.id)
            .filter(PayrollRun.deleted_at.is_(None), run_period >= start_index, run_period <= end_index)
        )
        if department_id:
            query = query.filter(Employee.department_id == department_id)
        if cost_center_id:
            query = query.filter(Employee.cost_center_id == cost_center_id)
        return query

    def money(value: Any) -> Decimal:
        return Decimal(value or 0).quantize(Decimal("0.01"))

    gross_expr = func.coalesce(func.sum(PayrollRecord.gross_salary), 0)
    pf_employer_expr = func.coalesce(func.sum(PayrollRecord.pf_employer), 0)
    esi_employer_expr = func.coalesce(func.sum(PayrollRecord.esi_employer), 0)
    reimbursement_expr = func.coalesce(func.sum(PayrollRecord.reimbursements), 0)
    bonus_expr = func.coalesce(func.sum(PayrollRecord.bonus), 0)
    net_expr = func.coalesce(func.sum(PayrollRecord.net_salary), 0)
    deductions_expr = func.coalesce(func.sum(PayrollRecord.total_deductions), 0)
    headcount_expr = func.count(func.distinct(PayrollRecord.employee_id))
    record_count_expr = func.count(PayrollRecord.id)

    totals_row = scoped_records_query().with_entities(
        record_count_expr,
        headcount_expr,
        gross_expr,
        pf_employer_expr,
        esi_employer_expr,
        reimbursement_expr,
        bonus_expr,
        net_expr,
        deductions_expr,
    ).one()
    statutory_total = money(totals_row[3]) + money(totals_row[4])

    overtime_total = money(
        scoped_records_query()
        .join(OvertimePayLine, OvertimePayLine.payroll_record_id == PayrollRecord.id)
        .with_entities(func.coalesce(func.sum(OvertimePayLine.amount), 0))
        .scalar()
    )

    arrear_query = (
        db.query(PayrollArrearLine)
        .join(PayrollArrearRun, PayrollArrearLine.arrear_run_id == PayrollArrearRun.id)
        .join(PayrollRun, PayrollArrearRun.payroll_run_id == PayrollRun.id)
        .join(Employee, PayrollArrearLine.employee_id == Employee.id)
        .filter(PayrollRun.deleted_at.is_(None), run_period >= start_index, run_period <= end_index)
    )
    if department_id:
        arrear_query = arrear_query.filter(Employee.department_id == department_id)
    if cost_center_id:
        arrear_query = arrear_query.filter(Employee.cost_center_id == cost_center_id)
    arrear_total = money(arrear_query.with_entities(func.coalesce(func.sum(PayrollArrearLine.amount), 0)).scalar())

    total_payroll_cost = money(totals_row[2]) + statutory_total + money(totals_row[5]) + money(totals_row[6]) + overtime_total + arrear_total

    trend_rows = scoped_records_query().with_entities(
        PayrollRun.year,
        PayrollRun.month,
        record_count_expr,
        headcount_expr,
        gross_expr,
        pf_employer_expr,
        esi_employer_expr,
        reimbursement_expr,
        bonus_expr,
        net_expr,
    ).group_by(PayrollRun.year, PayrollRun.month).order_by(PayrollRun.year, PayrollRun.month).all()
    trends = []
    for row in trend_rows:
        employer_statutory = money(row[5]) + money(row[6])
        trends.append({
            "year": row[0],
            "month": row[1],
            "period": f"{row[0]}-{int(row[1]):02d}",
            "records": row[2],
            "headcount": row[3],
            "gross_salary": money(row[4]),
            "employer_statutory_cost": employer_statutory,
            "pf_employer": money(row[5]),
            "esi_employer": money(row[6]),
            "reimbursement_total": money(row[7]),
            "bonus_total": money(row[8]),
            "net_payout": money(row[9]),
            "total_payroll_cost": money(row[4]) + employer_statutory + money(row[7]) + money(row[8]),
        })

    department_rows = scoped_records_query().outerjoin(Department, Employee.department_id == Department.id).with_entities(
        Employee.department_id,
        Department.name,
        headcount_expr,
        gross_expr,
        pf_employer_expr,
        esi_employer_expr,
        reimbursement_expr,
        bonus_expr,
        net_expr,
    ).group_by(Employee.department_id, Department.name).order_by(gross_expr.desc()).all()
    department_breakdown = [
        {
            "department_id": row[0],
            "department_name": row[1] or "Unassigned",
            "headcount": row[2],
            "gross_salary": money(row[3]),
            "employer_statutory_cost": money(row[4]) + money(row[5]),
            "reimbursement_total": money(row[6]),
            "bonus_total": money(row[7]),
            "net_payout": money(row[8]),
        }
        for row in department_rows
    ]

    cost_center_rows = scoped_records_query().outerjoin(CostCenter, Employee.cost_center_id == CostCenter.id).with_entities(
        Employee.cost_center_id,
        CostCenter.name,
        headcount_expr,
        gross_expr,
        pf_employer_expr,
        esi_employer_expr,
        reimbursement_expr,
        bonus_expr,
        net_expr,
    ).group_by(Employee.cost_center_id, CostCenter.name).order_by(gross_expr.desc()).all()
    cost_center_breakdown = [
        {
            "cost_center_id": row[0],
            "cost_center_name": row[1] or "Unassigned",
            "headcount": row[2],
            "gross_salary": money(row[3]),
            "employer_statutory_cost": money(row[4]) + money(row[5]),
            "reimbursement_total": money(row[6]),
            "bonus_total": money(row[7]),
            "net_payout": money(row[8]),
        }
        for row in cost_center_rows
    ]

    active_salary_query = db.query(EmployeeSalary).join(Employee, EmployeeSalary.employee_id == Employee.id).filter(EmployeeSalary.is_active == True)
    if department_id:
        active_salary_query = active_salary_query.filter(Employee.department_id == department_id)
    if cost_center_id:
        active_salary_query = active_salary_query.filter(Employee.cost_center_id == cost_center_id)
    ctc_bands = [
        ("below_5l", None, Decimal("500000")),
        ("5l_to_10l", Decimal("500000"), Decimal("1000000")),
        ("10l_to_20l", Decimal("1000000"), Decimal("2000000")),
        ("above_20l", Decimal("2000000"), None),
    ]
    ctc_band_rows = []
    for label, lower, upper in ctc_bands:
        band_query = active_salary_query
        if lower is not None:
            band_query = band_query.filter(EmployeeSalary.ctc >= lower)
        if upper is not None:
            band_query = band_query.filter(EmployeeSalary.ctc < upper)
        count_value, ctc_total = band_query.with_entities(func.count(EmployeeSalary.id), func.coalesce(func.sum(EmployeeSalary.ctc), 0)).one()
        ctc_band_rows.append({"band": label, "headcount": count_value, "annual_ctc": money(ctc_total)})

    if not totals_row[0]:
        warnings.append("No payroll records found for the selected period and filters.")
    if not trend_rows:
        warnings.append("Trend data is empty; run payroll for this period to populate analytics.")

    return {
        "filters": {
            "from_month": from_month,
            "from_year": from_year,
            "to_month": to_month,
            "to_year": to_year,
            "department_id": department_id,
            "cost_center_id": cost_center_id,
        },
        "totals": {
            "records": totals_row[0],
            "headcount": totals_row[1],
            "gross_salary": money(totals_row[2]),
            "employer_statutory_cost": statutory_total,
            "pf_employer": money(totals_row[3]),
            "esi_employer": money(totals_row[4]),
            "reimbursement_total": money(totals_row[5]),
            "bonus_total": money(totals_row[6]),
            "net_payout": money(totals_row[7]),
            "total_deductions": money(totals_row[8]),
            "overtime_total": overtime_total,
            "arrear_total": arrear_total,
            "total_payroll_cost": total_payroll_cost,
        },
        "trends": {
            "payroll_cost": trends,
            "employer_statutory_cost": [{"period": row["period"], "amount": row["employer_statutory_cost"]} for row in trends],
            "net_payout": [{"period": row["period"], "amount": row["net_payout"]} for row in trends],
        },
        "breakdowns": {
            "department_salary_cost": department_breakdown,
            "cost_center_salary_cost": cost_center_breakdown,
            "headcount_cost_by_ctc_band": ctc_band_rows,
        },
        "warnings": warnings,
    }


SUPPORTED_PAYROLL_REPORT_TYPES = {
    "department_salary_cost",
    "month_over_month_cost",
    "ctc_band_distribution",
    "payroll_variance",
    "reimbursement_summary",
    "statutory_contribution_summary",
}


def _serialize_report_definition(item: PayrollReportDefinition) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "report_type": item.report_type,
        "filters_json": item.filters_json or {},
        "columns_json": item.columns_json or [],
        "created_by": item.created_by,
        "created_at": item.created_at,
    }


def _report_or_404(db: Session, report_id: int) -> PayrollReportDefinition:
    item = db.query(PayrollReportDefinition).filter(PayrollReportDefinition.id == report_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Payroll report definition not found")
    return item


def _validate_report_type(report_type: str) -> str:
    normalized = (report_type or "").strip()
    if normalized not in SUPPORTED_PAYROLL_REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported report_type. Allowed: {', '.join(sorted(SUPPORTED_PAYROLL_REPORT_TYPES))}")
    return normalized


def _coerce_int_filter(filters: dict[str, Any], key: str, default: int | None = None) -> int | None:
    value = filters.get(key, default)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{key} must be an integer")


def _payroll_report_filters(definition: PayrollReportDefinition, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = dict(definition.filters_json or {})
    for key, value in (overrides or {}).items():
        if value not in (None, ""):
            filters[key] = value

    month = _coerce_int_filter(filters, "month")
    year = _coerce_int_filter(filters, "year")
    from_month = _coerce_int_filter(filters, "from_month", month or 1)
    from_year = _coerce_int_filter(filters, "from_year", year or date.today().year)
    to_month = _coerce_int_filter(filters, "to_month", month or from_month)
    to_year = _coerce_int_filter(filters, "to_year", year or from_year)
    department_id = _coerce_int_filter(filters, "department_id")
    cost_center_id = _coerce_int_filter(filters, "cost_center_id")
    employee_id = _coerce_int_filter(filters, "employee_id")

    if not from_month or not to_month or not from_year or not to_year:
        raise HTTPException(status_code=400, detail="from_month/from_year/to_month/to_year are required")
    if not (1 <= from_month <= 12 and 1 <= to_month <= 12):
        raise HTTPException(status_code=400, detail="month values must be between 1 and 12")
    if (from_year * 12 + from_month) > (to_year * 12 + to_month):
        raise HTTPException(status_code=400, detail="from period cannot be after to period")

    return {
        "month": month,
        "year": year,
        "from_month": from_month,
        "from_year": from_year,
        "to_month": to_month,
        "to_year": to_year,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
        "employee_id": employee_id,
    }


def _money(value: Any) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def _scoped_payroll_record_query(db: Session, filters: dict[str, Any]):
    run_period = (PayrollRun.year * 12) + PayrollRun.month
    start_index = filters["from_year"] * 12 + filters["from_month"]
    end_index = filters["to_year"] * 12 + filters["to_month"]
    query = (
        db.query(PayrollRecord)
        .join(PayrollRun, PayrollRecord.payroll_run_id == PayrollRun.id)
        .join(Employee, PayrollRecord.employee_id == Employee.id)
        .filter(PayrollRun.deleted_at.is_(None), run_period >= start_index, run_period <= end_index)
    )
    if filters.get("department_id"):
        query = query.filter(Employee.department_id == filters["department_id"])
    if filters.get("cost_center_id"):
        query = query.filter(Employee.cost_center_id == filters["cost_center_id"])
    if filters.get("employee_id"):
        query = query.filter(PayrollRecord.employee_id == filters["employee_id"])
    return query


def _run_payroll_report(definition: PayrollReportDefinition, db: Session, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    report_type = _validate_report_type(definition.report_type)
    filters = _payroll_report_filters(definition, overrides)
    rows: list[dict[str, Any]] = []
    totals: dict[str, Any] = {}
    gross_expr = func.coalesce(func.sum(PayrollRecord.gross_salary), 0)
    net_expr = func.coalesce(func.sum(PayrollRecord.net_salary), 0)
    deduction_expr = func.coalesce(func.sum(PayrollRecord.total_deductions), 0)
    reimbursement_expr = func.coalesce(func.sum(PayrollRecord.reimbursements), 0)
    bonus_expr = func.coalesce(func.sum(PayrollRecord.bonus), 0)
    headcount_expr = func.count(func.distinct(PayrollRecord.employee_id))

    if report_type == "department_salary_cost":
        result_rows = _scoped_payroll_record_query(db, filters).outerjoin(Department, Employee.department_id == Department.id).with_entities(
            Employee.department_id,
            Department.name,
            headcount_expr,
            gross_expr,
            net_expr,
            deduction_expr,
            func.coalesce(func.sum(PayrollRecord.pf_employer + PayrollRecord.esi_employer), 0),
        ).group_by(Employee.department_id, Department.name).order_by(gross_expr.desc()).all()
        rows = [
            {"department_id": row[0], "department_name": row[1] or "Unassigned", "headcount": row[2], "gross_salary": _money(row[3]), "net_payout": _money(row[4]), "total_deductions": _money(row[5]), "employer_statutory_cost": _money(row[6])}
            for row in result_rows
        ]
        totals = {"gross_salary": sum((row["gross_salary"] for row in rows), Decimal("0")), "net_payout": sum((row["net_payout"] for row in rows), Decimal("0")), "headcount": sum(int(row["headcount"] or 0) for row in rows)}

    elif report_type == "month_over_month_cost":
        result_rows = _scoped_payroll_record_query(db, filters).with_entities(
            PayrollRun.year,
            PayrollRun.month,
            headcount_expr,
            gross_expr,
            net_expr,
            reimbursement_expr,
            bonus_expr,
            func.coalesce(func.sum(PayrollRecord.pf_employer + PayrollRecord.esi_employer), 0),
        ).group_by(PayrollRun.year, PayrollRun.month).order_by(PayrollRun.year, PayrollRun.month).all()
        rows = [
            {"year": row[0], "month": row[1], "period": f"{row[0]}-{int(row[1]):02d}", "headcount": row[2], "gross_salary": _money(row[3]), "net_payout": _money(row[4]), "reimbursements": _money(row[5]), "bonus": _money(row[6]), "employer_statutory_cost": _money(row[7]), "total_cost": _money(row[3]) + _money(row[5]) + _money(row[6]) + _money(row[7])}
            for row in result_rows
        ]
        totals = {"total_cost": sum((row["total_cost"] for row in rows), Decimal("0")), "gross_salary": sum((row["gross_salary"] for row in rows), Decimal("0")), "net_payout": sum((row["net_payout"] for row in rows), Decimal("0"))}

    elif report_type == "ctc_band_distribution":
        salary_query = db.query(EmployeeSalary).join(Employee, EmployeeSalary.employee_id == Employee.id).filter(EmployeeSalary.is_active == True)
        if filters.get("department_id"):
            salary_query = salary_query.filter(Employee.department_id == filters["department_id"])
        if filters.get("cost_center_id"):
            salary_query = salary_query.filter(Employee.cost_center_id == filters["cost_center_id"])
        if filters.get("employee_id"):
            salary_query = salary_query.filter(EmployeeSalary.employee_id == filters["employee_id"])
        for label, lower, upper in [("below_5l", None, Decimal("500000")), ("5l_to_10l", Decimal("500000"), Decimal("1000000")), ("10l_to_20l", Decimal("1000000"), Decimal("2000000")), ("above_20l", Decimal("2000000"), None)]:
            band_query = salary_query
            if lower is not None:
                band_query = band_query.filter(EmployeeSalary.ctc >= lower)
            if upper is not None:
                band_query = band_query.filter(EmployeeSalary.ctc < upper)
            count_value, ctc_total = band_query.with_entities(func.count(EmployeeSalary.id), func.coalesce(func.sum(EmployeeSalary.ctc), 0)).one()
            rows.append({"band": label, "headcount": count_value, "annual_ctc": _money(ctc_total)})
        totals = {"headcount": sum(int(row["headcount"] or 0) for row in rows), "annual_ctc": sum((row["annual_ctc"] for row in rows), Decimal("0"))}

    elif report_type == "payroll_variance":
        query = (
            db.query(PayrollVarianceItem)
            .join(PayrollRun, PayrollVarianceItem.payroll_run_id == PayrollRun.id)
            .join(Employee, PayrollVarianceItem.employee_id == Employee.id)
        )
        run_period = (PayrollRun.year * 12) + PayrollRun.month
        query = query.filter(run_period >= filters["from_year"] * 12 + filters["from_month"], run_period <= filters["to_year"] * 12 + filters["to_month"])
        if filters.get("department_id"):
            query = query.filter(Employee.department_id == filters["department_id"])
        if filters.get("cost_center_id"):
            query = query.filter(Employee.cost_center_id == filters["cost_center_id"])
        if filters.get("employee_id"):
            query = query.filter(PayrollVarianceItem.employee_id == filters["employee_id"])
        rows = [
            {"id": item.id, "payroll_run_id": item.payroll_run_id, "employee_id": item.employee_id, "current_gross": _money(item.current_gross), "previous_gross": _money(item.previous_gross), "gross_delta": _money(item.gross_delta), "gross_delta_percent": item.gross_delta_percent, "current_net": _money(item.current_net), "previous_net": _money(item.previous_net), "net_delta": _money(item.net_delta), "net_delta_percent": item.net_delta_percent, "severity": item.severity, "reason": item.reason}
            for item in query.order_by(PayrollVarianceItem.id.desc()).limit(1000).all()
        ]
        totals = {"items": len(rows), "gross_delta": sum((row["gross_delta"] for row in rows), Decimal("0")), "net_delta": sum((row["net_delta"] for row in rows), Decimal("0"))}

    elif report_type == "reimbursement_summary":
        start_date = date(filters["from_year"], filters["from_month"], 1)
        end_date = date(filters["to_year"], filters["to_month"], calendar.monthrange(filters["to_year"], filters["to_month"])[1])
        query = db.query(Reimbursement).join(Employee, Reimbursement.employee_id == Employee.id).filter(Reimbursement.date >= start_date, Reimbursement.date <= end_date)
        if filters.get("department_id"):
            query = query.filter(Employee.department_id == filters["department_id"])
        if filters.get("cost_center_id"):
            query = query.filter(Employee.cost_center_id == filters["cost_center_id"])
        if filters.get("employee_id"):
            query = query.filter(Reimbursement.employee_id == filters["employee_id"])
        result_rows = query.with_entities(Reimbursement.category, Reimbursement.status, func.count(Reimbursement.id), func.coalesce(func.sum(Reimbursement.amount), 0)).group_by(Reimbursement.category, Reimbursement.status).order_by(Reimbursement.category, Reimbursement.status).all()
        rows = [{"category": row[0] or "Uncategorized", "status": row[1], "count": row[2], "amount": _money(row[3])} for row in result_rows]
        totals = {"count": sum(int(row["count"] or 0) for row in rows), "amount": sum((row["amount"] for row in rows), Decimal("0"))}

    elif report_type == "statutory_contribution_summary":
        query = (
            db.query(PayrollStatutoryContributionLine)
            .join(PayrollRecord, PayrollStatutoryContributionLine.payroll_record_id == PayrollRecord.id)
            .join(PayrollRun, PayrollRecord.payroll_run_id == PayrollRun.id)
            .join(Employee, PayrollStatutoryContributionLine.employee_id == Employee.id)
        )
        run_period = (PayrollRun.year * 12) + PayrollRun.month
        query = query.filter(PayrollRun.deleted_at.is_(None), run_period >= filters["from_year"] * 12 + filters["from_month"], run_period <= filters["to_year"] * 12 + filters["to_month"])
        if filters.get("department_id"):
            query = query.filter(Employee.department_id == filters["department_id"])
        if filters.get("cost_center_id"):
            query = query.filter(Employee.cost_center_id == filters["cost_center_id"])
        if filters.get("employee_id"):
            query = query.filter(PayrollStatutoryContributionLine.employee_id == filters["employee_id"])
        result_rows = query.with_entities(
            PayrollStatutoryContributionLine.component,
            func.count(func.distinct(PayrollStatutoryContributionLine.employee_id)),
            func.coalesce(func.sum(PayrollStatutoryContributionLine.wage_base), 0),
            func.coalesce(func.sum(PayrollStatutoryContributionLine.employee_amount), 0),
            func.coalesce(func.sum(PayrollStatutoryContributionLine.employer_amount), 0),
            func.coalesce(func.sum(PayrollStatutoryContributionLine.admin_charge), 0),
            func.coalesce(func.sum(PayrollStatutoryContributionLine.edli_amount), 0),
        ).group_by(PayrollStatutoryContributionLine.component).order_by(PayrollStatutoryContributionLine.component).all()
        rows = [{"component": row[0], "employee_count": row[1], "wage_base": _money(row[2]), "employee_amount": _money(row[3]), "employer_amount": _money(row[4]), "admin_charge": _money(row[5]), "edli_amount": _money(row[6]), "total_amount": _money(row[3]) + _money(row[4]) + _money(row[5]) + _money(row[6])} for row in result_rows]
        totals = {"employee_amount": sum((row["employee_amount"] for row in rows), Decimal("0")), "employer_amount": sum((row["employer_amount"] for row in rows), Decimal("0")), "total_amount": sum((row["total_amount"] for row in rows), Decimal("0"))}

    return {"definition": _serialize_report_definition(definition), "filters": filters, "rows": rows, "totals": totals, "row_count": len(rows)}


@router.post("/reports", status_code=201)
def create_payroll_report_definition(data: PayrollReportDefinitionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    _validate_report_type(data.report_type)
    item = PayrollReportDefinition(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_report_definition(item)


@router.get("/reports")
def list_payroll_report_definitions(report_type: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    query = db.query(PayrollReportDefinition)
    if report_type:
        query = query.filter(PayrollReportDefinition.report_type == _validate_report_type(report_type))
    return [_serialize_report_definition(item) for item in query.order_by(PayrollReportDefinition.created_at.desc(), PayrollReportDefinition.id.desc()).all()]


@router.get("/reports/{report_id}")
def get_payroll_report_definition(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return _serialize_report_definition(_report_or_404(db, report_id))


@router.put("/reports/{report_id}")
def update_payroll_report_definition(report_id: int, data: PayrollReportDefinitionUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = _report_or_404(db, report_id)
    update_data = data.model_dump(exclude_unset=True)
    if "report_type" in update_data and update_data["report_type"] is not None:
        _validate_report_type(update_data["report_type"])
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return _serialize_report_definition(item)


@router.delete("/reports/{report_id}")
def delete_payroll_report_definition(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = _report_or_404(db, report_id)
    db.delete(item)
    db.commit()
    return {"deleted": True, "id": report_id}


@router.get("/reports/{report_id}/run")
def run_payroll_report_definition(
    report_id: int,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None),
    from_month: Optional[int] = Query(None, ge=1, le=12),
    from_year: Optional[int] = Query(None),
    to_month: Optional[int] = Query(None, ge=1, le=12),
    to_year: Optional[int] = Query(None),
    department_id: Optional[int] = None,
    cost_center_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    definition = _report_or_404(db, report_id)
    overrides = {"month": month, "year": year, "from_month": from_month, "from_year": from_year, "to_month": to_month, "to_year": to_year, "department_id": department_id, "cost_center_id": cost_center_id, "employee_id": employee_id}
    return _run_payroll_report(definition, db, overrides)


@router.post("/reports/{report_id}/run")
def run_payroll_report_definition_post(report_id: int, filters: dict[str, Any] = Body(default_factory=dict), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return _run_payroll_report(_report_or_404(db, report_id), db, filters)


@router.get("/reports/{report_id}/export")
def export_payroll_report_definition(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    result = _run_payroll_report(_report_or_404(db, report_id), db)
    buffer = io.StringIO()
    rows = result["rows"]
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["message"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    if rows:
        writer.writerows(rows)
    else:
        writer.writerow({"message": "No rows for selected report filters"})
    buffer.seek(0)
    filename = f"payroll_report_{report_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.csv"
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
