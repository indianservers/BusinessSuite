from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
import ast
import calendar
import csv
import os
import re
from app.core.deps import get_db, get_current_user, RequirePermission
from app.core.hr_audit import record_salary_field_changes
from app.core.config import settings
from app.core.email import send_email
from app.crud import crud_payroll
from app.models.user import User
from app.models.employee import Employee
from app.models.expense import ExpenseClaim
from app.models.payroll import (
    SalaryComponent, SalaryComponentCategory, SalaryComponentFormulaRule,
    SalaryStructure, PayrollRun, PayrollRecord, Reimbursement,
    PayrollExportBatch, PayrollRunAuditLog, SalaryStructureComponent,
    PayrollPayGroup, PayrollCalendar, PayrollStatutoryProfile, PayrollPeriod,
    PayrollComplianceRule, BankAdviceFormat,
    SalaryTemplate, SalaryTemplateComponent, EmployeeSalaryTemplateAssignment,
    EmployeeSalaryComponentOverride,
    SalaryRevisionRequest, SensitiveSalaryAuditLog,
    PayrollPreRunCheck, PayrollManualInput, PayrollUnlockRequest, PayslipPublishBatch,
    ReimbursementLedger, EmployeeLoan, EmployeeLoanInstallment, EmployeeLoanLedger,
    FullFinalSettlement, FullFinalSettlementLine,
    TaxRegime, TaxSlab, TaxSection, TaxSectionLimit, EmployeeTaxRegimeElection,
    EmployeeTaxWorksheet, EmployeeTaxWorksheetLine, PreviousEmploymentTaxDetail,
    PFRule, ESIRule, ProfessionalTaxSlab, LWFSlab, GratuityRule,
    EmployeeStatutoryProfile, PayrollStatutoryContributionLine,
    PayrollAttendanceInput,
    LOPAdjustment, OvertimePolicy, OvertimePayLine,
    LeaveEncashmentPolicy, LeaveEncashmentLine,
    PayrollRunEmployee, PayrollCalculationSnapshot,
    PayrollArrearRun, PayrollArrearLine, OffCyclePayrollRun,
    PayrollPaymentBatch, PayrollPaymentLine,
    AccountingLedger, PayrollGLMapping, PayrollJournalEntry, PayrollJournalLine,
    StatutoryFileValidation, StatutoryTemplateFile,
    StatutoryChallan, StatutoryReturnFile,
    TaxDeclarationCycle, TaxDeclaration, TaxDeclarationProof, EmployeeSalary,
    EmployeeTaxDeclaration, EmployeeTaxDeclarationItem,
    PayslipDeliveryLog, PayslipQuery, SalaryAdvance,
    SalaryRevisionBatch, SalaryRevisionBatchLine, BonusPolicy, GratuityAccrual,
    SalaryCertificate, PayrollBudget, PayrollBankValidation, PayrollBankFileValidation,
    TDS26ASReconciliation, Form12BARecord, PayrollExchangeRate, PayrollReportDefinition
)
from app.schemas.payroll import (
    SalaryComponentCreate, SalaryComponentSchema,
    SalaryComponentCategoryCreate, SalaryComponentCategorySchema,
    SalaryComponentFormulaRuleCreate, SalaryComponentFormulaRuleSchema,
    SalaryStructureCreate, SalaryStructureSchema, SalaryStructurePreviewRequest, SalaryStructurePreviewSchema,
    EmployeeSalaryCreate, EmployeeSalarySchema,
    PayrollRunCreate, PayrollRunApproval, PayrollRunSchema,
    PayrollRecordSchema, ReimbursementCreate, ReimbursementSchema,
    PayrollVarianceItemSchema, PayrollExportBatchSchema, PayrollRunAuditLogSchema,
    SalaryRevisionRequestCreate, SalaryRevisionReview, SalaryRevisionRequestSchema, SensitiveSalaryAuditLogSchema,
    PayrollPreRunCheckCreate, PayrollPreRunCheckSchema, PayrollManualInputCreate, PayrollManualInputReview,
    PayrollManualInputSchema, PayrollUnlockRequestCreate, PayrollUnlockReview, PayrollUnlockRequestSchema,
    PayslipPublishBatchCreate, PayslipPublishBatchSchema,
    ReimbursementReview, ReimbursementLedgerSchema, EmployeeLoanCreate, EmployeeLoanSchema,
    EmployeeLoanInstallmentSchema, EmployeeLoanLedgerSchema,
    FullFinalSettlementCreate, FullFinalSettlementSchema,
    PayrollPayGroupCreate, PayrollPayGroupSchema, PayrollCalendarCreate, PayrollCalendarSchema,
    PayrollStatutoryProfileCreate, PayrollStatutoryProfileSchema,
    PayrollPeriodCreate, PayrollPeriodSchema, PayrollPeriodGenerateRequest,
    SalaryTemplateCreate, SalaryTemplateSchema,
    EmployeeSalaryTemplateAssignmentCreate, EmployeeSalaryTemplateAssignmentSchema,
    EmployeeSalaryComponentOverrideCreate, EmployeeSalaryComponentOverrideSchema,
    PayrollComplianceRuleCreate, PayrollComplianceRuleSchema, BankAdviceFormatCreate, BankAdviceFormatSchema,
    TaxRegimeCreate, TaxRegimeSchema, TaxSlabCreate, TaxSlabSchema,
    TaxSectionCreate, TaxSectionSchema, TaxSectionLimitCreate, TaxSectionLimitSchema,
    EmployeeTaxRegimeElectionCreate, EmployeeTaxRegimeElectionSchema,
    PreviousEmploymentTaxDetailCreate, PreviousEmploymentTaxDetailSchema,
    TaxWorksheetProjectRequest, EmployeeTaxWorksheetSchema,
    PFRuleCreate, PFRuleSchema, ESIRuleCreate, ESIRuleSchema,
    ProfessionalTaxSlabCreate, ProfessionalTaxSlabSchema, LWFSlabCreate, LWFSlabSchema,
    GratuityRuleCreate, GratuityRuleSchema, EmployeeStatutoryProfileCreate,
    EmployeeStatutoryProfileSchema, StatutoryCalculationRequest, StatutoryCalculationSchema,
    PayrollStatutoryContributionLineSchema,
    PayrollAttendanceInputCreate, PayrollAttendanceInputSchema,
    LOPAdjustmentCreate, LOPAdjustmentReview, LOPAdjustmentSchema,
    OvertimePolicyCreate, OvertimePolicySchema, OvertimePayLineCreate, OvertimePayLineSchema,
    LeaveEncashmentPolicyCreate, LeaveEncashmentPolicySchema,
    LeaveEncashmentLineCreate, LeaveEncashmentLineSchema,
    PayrollAttendanceReconcileRequest, PayrollAttendanceReconcileSchema,
    PayrollRunEmployeeSchema, PayrollRunEmployeeAction, PayrollCalculationSnapshotSchema, PayrollWorksheetProcessSchema,
    PayrollArrearRunCreate, PayrollArrearRunSchema, OffCyclePayrollRunCreate, OffCyclePayrollRunSchema,
    PayrollPaymentBatchCreate, PayrollPaymentBatchSchema,
    PayrollPaymentStatusImportRequest, PayrollPaymentStatusImportSchema,
    AccountingLedgerCreate, AccountingLedgerSchema, PayrollGLMappingCreate, PayrollGLMappingSchema,
    PayrollJournalEntrySchema,
    StatutoryFileValidationRequest, StatutoryFileValidationSchema, StatutoryTemplateFileSchema,
    StatutoryChallanCreate, StatutoryChallanGenerateRequest, StatutoryChallanSchema,
    StatutoryReturnFileCreate, StatutoryReturnFileSchema,
    TaxDeclarationCycleCreate, TaxDeclarationCycleSchema, TaxDeclarationCreate, TaxDeclarationReview,
    TaxDeclarationSchema, TaxDeclarationProofCreate, TaxDeclarationProofReview, TaxDeclarationProofSchema,
)
from app.schemas.payroll import SalaryComponentCreate as SalaryComponentUpdate

router = APIRouter(prefix="/payroll", tags=["Payroll"])

EXPORT_TYPES = {"pf_ecr", "esi", "pt", "tds_24q", "form_16", "bank_advice", "pay_register", "accounting_journal"}


class PayrollSimulationRequest(BaseModel):
    ctc: Decimal = Field(gt=0)
    structure_id: int | None = None
    monthly_reimbursements: Decimal = Decimal("0")
    state: str | None = None
    currency: str = "INR"


class PayslipQueryCreate(BaseModel):
    payroll_record_id: int
    subject: str
    description: str
    priority: str = "Medium"


class PayslipQueryResolve(BaseModel):
    status: str = "Resolved"
    resolution: str | None = None
    assigned_to: int | None = None


def _payroll_export_readiness(db: Session, run: PayrollRun, export_type: str) -> dict:
    if export_type not in EXPORT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported payroll export type")
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run.id).all()
    issues = []
    warnings = []
    for record in records:
        employee = db.query(Employee).filter(Employee.id == record.employee_id).first()
        employee_code = employee.employee_id if employee else str(record.employee_id)
        if not employee:
            issues.append({"employee_id": record.employee_id, "employee_code": employee_code, "severity": "Critical", "message": "Employee master is missing"})
            continue
        if (record.net_salary or Decimal("0")) < 0:
            issues.append({"employee_id": employee.id, "employee_code": employee_code, "severity": "Critical", "message": "Net salary is negative"})
        if export_type == "pf_ecr" and (record.pf_employee or Decimal("0")) > 0 and not employee.uan_number:
            issues.append({"employee_id": employee.id, "employee_code": employee_code, "severity": "Critical", "message": "UAN is required for PF ECR"})
        if export_type == "esi" and (record.esi_employee or Decimal("0")) > 0 and not employee.esic_number:
            issues.append({"employee_id": employee.id, "employee_code": employee_code, "severity": "Critical", "message": "ESI IP number is required for ESI export"})
        if export_type in {"tds_24q", "form_16"} and (record.tds or Decimal("0")) > 0 and not employee.pan_number:
            issues.append({"employee_id": employee.id, "employee_code": employee_code, "severity": "Critical", "message": "PAN is required for TDS/Form 16 export"})
        if export_type == "bank_advice":
            missing_bank = [field for field, value in {
                "bank_name": employee.bank_name,
                "account_number": employee.account_number,
                "ifsc_code": employee.ifsc_code,
            }.items() if not value]
            if missing_bank:
                issues.append({"employee_id": employee.id, "employee_code": employee_code, "severity": "Critical", "message": f"Bank details missing: {', '.join(missing_bank)}"})
    if not records:
        issues.append({"employee_id": None, "employee_code": None, "severity": "Critical", "message": "Payroll run has no records"})
    if run.status not in {crud_payroll.PAYROLL_RUN_STATUS_APPROVED, crud_payroll.PAYROLL_RUN_STATUS_LOCKED, crud_payroll.PAYROLL_RUN_STATUS_PAID}:
        warnings.append({"severity": "Medium", "message": "Export is usually generated after payroll approval or lock"})
    return {
        "payroll_run_id": run.id,
        "export_type": export_type,
        "record_count": len(records),
        "scope": {
            "company_id": run.company_id,
            "branch_id": run.branch_id,
            "department_id": run.department_id,
            "pay_group_id": run.pay_group_id,
            "employee_category": run.employee_category,
        },
        "ready": not issues,
        "critical_issue_count": len(issues),
        "warning_count": len(warnings),
        "issues": issues,
        "warnings": warnings,
    }


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


def _pdf_escape(value: object) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_basic_pdf(file_path: str, lines: List[str]) -> None:
    """Small PDF fallback for environments where reportlab is not installed."""
    y = 800
    content_lines = ["BT", "/F1 11 Tf"]
    for line in lines:
        content_lines.append(f"50 {y} Td ({_pdf_escape(line)}) Tj")
        content_lines.append("0 -18 Td")
        y -= 18
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("ascii")
    )
    with open(file_path, "wb") as handle:
        handle.write(pdf)


def _has_permission(user: User, permission: str) -> bool:
    if user.is_superuser:
        return True
    return permission in {p.name for p in (user.role.permissions if user.role else [])}


def _can_view_other_payslips(user: User) -> bool:
    role_name = user.role.name if user.role else None
    return user.is_superuser or (role_name != "employee" and _has_permission(user, "payroll_view"))


def _current_company_id(user: User) -> Optional[int]:
    if user.employee and user.employee.branch:
        return user.employee.branch.company_id
    return None


def _locked_period(
    db: Session,
    month: int,
    year: int,
    company_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    department_id: Optional[int] = None,
    pay_group_id: Optional[int] = None,
    employee_category: Optional[str] = None,
) -> Optional[PayrollRun]:
    query = db.query(PayrollRun).filter(
        PayrollRun.month == month,
        PayrollRun.year == year,
        PayrollRun.status.in_([crud_payroll.PAYROLL_RUN_STATUS_LOCKED, crud_payroll.PAYROLL_RUN_STATUS_PAID, "Locked", "Paid"]),
        PayrollRun.deleted_at.is_(None),
    )
    if company_id is not None:
        query = query.filter(PayrollRun.company_id == company_id)
    if branch_id is not None:
        query = query.filter(PayrollRun.branch_id == branch_id)
    if department_id is not None:
        query = query.filter(PayrollRun.department_id == department_id)
    if pay_group_id is not None:
        query = query.filter(PayrollRun.pay_group_id == pay_group_id)
    if employee_category is not None:
        query = query.filter(PayrollRun.employee_category == employee_category)
    return query.first()


def _get_payroll_run_or_404(db: Session, run_id: int) -> PayrollRun:
    run = db.query(PayrollRun).filter(
        PayrollRun.id == run_id,
        PayrollRun.deleted_at.is_(None),
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    return run


def _ensure_not_locked_period(
    db: Session,
    month: int,
    year: int,
    action: str,
    company_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    department_id: Optional[int] = None,
    pay_group_id: Optional[int] = None,
    employee_category: Optional[str] = None,
) -> None:
    if _locked_period(db, month, year, company_id, branch_id, department_id, pay_group_id, employee_category):
        raise HTTPException(status_code=400, detail=f"Payroll is locked for this period; cannot {action}")


def _ensure_not_locked_for_date(db: Session, value: Optional[date], action: str) -> None:
    if not value:
        value = date.today()
    _ensure_not_locked_period(db, value.month, value.year, action)


def _ensure_no_locked_payroll_exists(db: Session, action: str) -> None:
    if db.query(PayrollRun).filter(
        PayrollRun.status.in_([crud_payroll.PAYROLL_RUN_STATUS_LOCKED, crud_payroll.PAYROLL_RUN_STATUS_PAID, "Locked", "Paid"]),
        PayrollRun.deleted_at.is_(None),
    ).first():
        raise HTTPException(
            status_code=400,
            detail=f"A payroll period is locked; clone/version setup before you {action}",
        )


def _audit(db: Session, run_id: Optional[int], action: str, user_id: Optional[int], details: Optional[str] = None) -> None:
    db.add(PayrollRunAuditLog(
        payroll_run_id=run_id,
        action=action,
        actor_user_id=user_id,
        details=details,
    ))


def _mask_money(value: Optional[Decimal]) -> str:
    if value is None:
        return "0.00"
    text = f"{Decimal(value):.2f}"
    return f"***{text[-6:]}" if len(text) > 6 else "***"


def _month_add(month: int, year: int, offset: int) -> tuple[int, int]:
    zero_based = (year * 12) + (month - 1) + offset
    return (zero_based % 12) + 1, zero_based // 12


def _structure_payload(structure: SalaryStructure) -> dict:
    ordered = sorted(structure.components, key=lambda item: item.order_sequence or 100)
    return {
        "id": structure.id,
        "name": structure.name,
        "description": structure.description,
        "version": structure.version,
        "parent_structure_id": structure.parent_structure_id,
        "effective_from": structure.effective_from,
        "is_active": structure.is_active,
        "components": [
            {
                "id": item.id,
                "component_id": item.component_id,
                "component_name": item.component.name if item.component else None,
                "component_code": item.component.code if item.component else None,
                "component_type": item.component.component_type if item.component else None,
                "payslip_group": item.component.payslip_group if item.component else None,
                "display_sequence": item.component.display_sequence if item.component else item.order_sequence,
                "amount": item.amount,
                "percentage": item.percentage,
                "order_sequence": item.order_sequence,
            }
            for item in ordered
        ],
    }


ALLOWED_FORMULA_FUNCS = {"min": min, "max": max, "round": round, "Decimal": Decimal}
ALLOWED_FORMULA_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.Call,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.UAdd, ast.USub,
)


def _safe_formula_value(expression: str, variables: dict[str, Decimal], component_code: str) -> Decimal:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid formula for {component_code}: {exc.msg}")

    allowed_names = set(variables) | set(ALLOWED_FORMULA_FUNCS)
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_FORMULA_NODES):
            raise HTTPException(status_code=400, detail=f"Invalid formula for {component_code}: unsupported expression")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise HTTPException(status_code=400, detail=f"Invalid formula for {component_code}: unknown name {node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FORMULA_FUNCS:
                raise HTTPException(status_code=400, detail=f"Invalid formula for {component_code}: unsupported function")
    try:
        value = eval(
            compile(tree, "<salary_formula>", "eval"),
            {"__builtins__": {}},
            {**ALLOWED_FORMULA_FUNCS, **variables},
        )
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid formula for {component_code}: {exc}")


def _formula_dependencies(expression: Optional[str]) -> set[str]:
    if not expression:
        return set()
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return set()
    return {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and node.id not in ALLOWED_FORMULA_FUNCS
        and node.id not in {"ctc_monthly", "ctc_annual", "gross", "basic"}
    }


def _active_formula_expression(component: SalaryComponent) -> Optional[str]:
    active_rules = [
        rule for rule in component.formula_rules
        if rule.validation_status in {"Active", "Approved"} and not rule.effective_to
    ]
    if active_rules:
        active_rules.sort(key=lambda rule: (rule.dependency_order or 100, rule.id), reverse=False)
        return active_rules[0].formula_expression
    return component.formula_expression


def _component_monthly_amount(item: SalaryStructureComponent, monthly_ctc: Decimal, extra_variables: Optional[dict[str, Decimal]] = None) -> Decimal:
    component = item.component
    variables = {
        "ctc_monthly": monthly_ctc,
        "ctc_annual": monthly_ctc * Decimal("12"),
    }
    if extra_variables:
        variables.update(extra_variables)
    item_expression = getattr(item, "formula_expression", None)
    if component and (component.calculation_type == "Formula" or item_expression):
        expression = item_expression or _active_formula_expression(component)
        if expression:
            value = _safe_formula_value(expression, variables, component.code)
            item_min = getattr(item, "min_amount", None)
            item_max = getattr(item, "max_amount", None)
            minimum = item_min if item_min is not None else component.min_amount
            maximum = item_max if item_max is not None else component.max_amount
            if minimum is not None:
                value = max(value, Decimal(minimum))
            if maximum is not None:
                value = min(value, Decimal(maximum))
            return value.quantize(Decimal("0.01"))
    if item.amount is not None and Decimal(item.amount) != Decimal("0"):
        return Decimal(item.amount)
    if item.percentage is not None:
        return (monthly_ctc * Decimal(item.percentage) / Decimal("100")).quantize(Decimal("0.01"))
    if component and component.calculation_type == "Percentage" and component.amount:
        return (monthly_ctc * Decimal(component.amount) / Decimal("100")).quantize(Decimal("0.01"))
    return Decimal(component.amount or 0) if component else Decimal("0")


def _ordered_structure_components(structure: SalaryStructure) -> tuple[list[SalaryStructureComponent], list[str]]:
    items = [item for item in structure.components if item.component]
    by_code = {item.component.code: item for item in items}
    dependencies = {
        item.component.code: {dep for dep in _formula_dependencies(getattr(item, "formula_expression", None) or _active_formula_expression(item.component)) if dep in by_code}
        for item in items
    }
    ordered: list[SalaryStructureComponent] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    warnings: list[str] = []

    def visit(code: str) -> None:
        if code in visited:
            return
        if code in visiting:
            raise HTTPException(status_code=400, detail=f"Circular salary formula dependency detected at {code}")
        visiting.add(code)
        for dependency in sorted(dependencies.get(code, set())):
            visit(dependency)
        visiting.remove(code)
        visited.add(code)
        ordered.append(by_code[code])

    for item in sorted(items, key=lambda row: (row.order_sequence or 100, row.component.display_sequence or 100, row.component.code)):
        visit(item.component.code)
    for code, deps in dependencies.items():
        if deps:
            warnings.append(f"{code} depends on {', '.join(sorted(deps))}")
    return ordered, warnings


def _calculate_tax_from_slabs(taxable_income: Decimal, slabs: List[TaxSlab]) -> Decimal:
    tax = Decimal("0")
    for slab in sorted(slabs, key=lambda item: item.sequence or 1):
        slab_min = Decimal(slab.min_income or 0)
        slab_max = Decimal(slab.max_income) if slab.max_income is not None else taxable_income
        if taxable_income <= slab_min:
            continue
        slab_income = min(taxable_income, slab_max) - slab_min
        if slab_income <= 0:
            continue
        tax += Decimal(slab.fixed_amount or 0)
        tax += (slab_income * Decimal(slab.rate_percent or 0) / Decimal("100")).quantize(Decimal("0.01"))
    return tax.quantize(Decimal("0.01"))


def _tax_with_rebate_surcharge_and_cess(base_tax: Decimal, taxable_income: Decimal, regime: TaxRegime) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    rebate = Decimal("0")
    for rule in (regime.rebate_rules_json or []):
        if taxable_income <= Decimal(str(rule.get("income_upto", 0))):
            rebate = min(base_tax, Decimal(str(rule.get("rebate_amount", 0))))
            break
    tax_after_rebate = max(Decimal("0"), base_tax - rebate)
    surcharge = Decimal("0")
    for rule in sorted((regime.surcharge_rules_json or []), key=lambda item: Decimal(str(item.get("income_above", 0)))):
        if taxable_income > Decimal(str(rule.get("income_above", 0))):
            surcharge = (tax_after_rebate * Decimal(str(rule.get("rate_percent", 0))) / Decimal("100")).quantize(Decimal("0.01"))
    cess = ((tax_after_rebate + surcharge) * Decimal(regime.cess_percent or 0) / Decimal("100")).quantize(Decimal("0.01"))
    return rebate, surcharge, cess, (tax_after_rebate + surcharge + cess).quantize(Decimal("0.01"))


def _rounded_money(value: Decimal, rule: Optional[str] = "Nearest Rupee") -> Decimal:
    if rule == "No Rounding":
        return value.quantize(Decimal("0.01"))
    return value.quantize(Decimal("1")).quantize(Decimal("0.01"))


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
    lines: list[dict[str, Any]] = []
    gross = Decimal("0")
    if structure_id:
        structure = db.query(SalaryStructure).filter(SalaryStructure.id == structure_id).first()
        if not structure:
            raise HTTPException(status_code=404, detail="Salary structure not found")
        variables = {"ctc_monthly": monthly_ctc, "ctc_annual": Decimal(ctc)}
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


def _payslip_password_for_employee(employee: Employee, policy: str) -> str | None:
    if policy == "none":
        return None
    if policy in {"aadhaar_last4", "dob_or_aadhaar"} and employee.aadhaar_number:
        digits = re.sub(r"\D", "", employee.aadhaar_number)
        if len(digits) >= 4:
            return digits[-4:]
    if employee.date_of_birth:
        return employee.date_of_birth.strftime("%d%m%Y")
    return None


def _active_rule(query, on_date: date):
    return query.filter(
        query.column_descriptions[0]["entity"].is_active == True,
        query.column_descriptions[0]["entity"].effective_from <= on_date,
    ).filter(
        (query.column_descriptions[0]["entity"].effective_to == None) |
        (query.column_descriptions[0]["entity"].effective_to >= on_date)
    ).order_by(query.column_descriptions[0]["entity"].effective_from.desc()).first()


def _salary_in_slab(salary: Decimal, salary_from: Decimal, salary_to: Optional[Decimal]) -> bool:
    if salary < Decimal(salary_from or 0):
        return False
    return salary_to is None or salary <= Decimal(salary_to)


def _period_bounds(period: PayrollPeriod) -> tuple[date, date]:
    return period.period_start, period.period_end


def _is_unpaid_leave_type(name: Optional[str], code: Optional[str]) -> bool:
    marker = f"{name or ''} {code or ''}".lower()
    return any(token in marker for token in ("lop", "loss of pay", "unpaid", "leave without pay", "lwp"))


def _inclusive_days(start: date, end: date) -> Decimal:
    return Decimal(str((end - start).days + 1))


def _active_overtime_policy(db: Session, period: PayrollPeriod) -> Optional[OvertimePolicy]:
    return db.query(OvertimePolicy).filter(
        OvertimePolicy.is_active == True,
        OvertimePolicy.effective_from <= period.period_end,
        (OvertimePolicy.effective_to == None) | (OvertimePolicy.effective_to >= period.period_start),
        (OvertimePolicy.pay_group_id == None) | (OvertimePolicy.pay_group_id == period.pay_group_id),
    ).order_by(OvertimePolicy.pay_group_id.desc(), OvertimePolicy.effective_from.desc()).first()


def _payroll_period_for_run(db: Session, run: PayrollRun) -> Optional[PayrollPeriod]:
    return db.query(PayrollPeriod).filter(
        PayrollPeriod.month == run.month,
        PayrollPeriod.year == run.year,
    ).order_by(PayrollPeriod.id.desc()).first()


def _payroll_input_blockers(db: Session, run: PayrollRun) -> List[str]:
    period = _payroll_period_for_run(db, run)
    if not period:
        return [f"No payroll period configured for {run.month}/{run.year}"]
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run.id).all()
    blockers: List[str] = []
    for record in records:
        item = db.query(PayrollAttendanceInput).filter(
            PayrollAttendanceInput.period_id == period.id,
            PayrollAttendanceInput.employee_id == record.employee_id,
        ).first()
        if not item:
            blockers.append(f"Employee {record.employee_id}: missing payroll attendance input")
        elif item.source_status not in {"Approved", "Locked"}:
            blockers.append(f"Employee {record.employee_id}: attendance input is {item.source_status}")
        elif item.source_status == "Approved" and not item.locked_at:
            blockers.append(f"Employee {record.employee_id}: attendance input is approved but not locked")
    return blockers


def _attendance_input_payload(item: Optional[PayrollAttendanceInput]) -> Optional[dict]:
    if not item:
        return None
    return {
        "id": item.id,
        "period_id": item.period_id,
        "working_days": str(item.working_days or 0),
        "payable_days": str(item.payable_days or 0),
        "present_days": str(item.present_days or 0),
        "paid_leave_days": str(item.paid_leave_days or 0),
        "unpaid_leave_days": str(item.unpaid_leave_days or 0),
        "lop_days": str(item.lop_days or 0),
        "holiday_days": str(item.holiday_days or 0),
        "weekly_off_days": str(item.weekly_off_days or 0),
        "ot_hours": str(item.ot_hours or 0),
        "source_status": item.source_status,
    }


def _ensure_default_ledgers(db: Session) -> dict[str, AccountingLedger]:
    defaults = {
        "SAL_EXP": ("Salary Expense", "Expense"),
        "SAL_PAY": ("Salary Payable", "Liability"),
        "DED_PAY": ("Statutory Deductions Payable", "Liability"),
        "BANK": ("Bank", "Asset"),
    }
    ledgers: dict[str, AccountingLedger] = {}
    for code, (name, ledger_type) in defaults.items():
        ledger = db.query(AccountingLedger).filter(AccountingLedger.code == code).first()
        if not ledger:
            ledger = AccountingLedger(name=name, code=code, ledger_type=ledger_type)
            db.add(ledger)
            db.flush()
        ledgers[code] = ledger
    return ledgers


def _write_rows_file(directory: str, filename: str, headers: List[str], rows: List[List[object]]) -> str:
    os.makedirs(directory, exist_ok=True)
    csv_path = os.path.join(directory, filename)
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    return csv_path


def _file_url_from_upload_path(file_path: str) -> str:
    rel_path = os.path.relpath(file_path, settings.UPLOAD_DIR).replace(os.sep, "/")
    return f"/uploads/{rel_path}"


# ── Salary Components ─────────────────────────────────────────────────────────

@router.get("/component-categories", response_model=List[SalaryComponentCategorySchema])
def list_component_categories(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(SalaryComponentCategory).filter(SalaryComponentCategory.is_active == True).order_by(SalaryComponentCategory.name).all()


@router.post("/component-categories", response_model=SalaryComponentCategorySchema, status_code=201)
def create_component_category(data: SalaryComponentCategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    category = SalaryComponentCategory(**data.model_dump())
    db.add(category)
    _audit(db, None, "component_category_created", current_user.id, data.code)
    db.commit()
    db.refresh(category)
    return category


@router.get("/setup/pay-groups", response_model=List[PayrollPayGroupSchema])
def list_pay_groups(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(PayrollPayGroup).filter(PayrollPayGroup.is_active == True).order_by(PayrollPayGroup.name).all()


@router.post("/setup/pay-groups", response_model=PayrollPayGroupSchema, status_code=201)
def create_pay_group(data: PayrollPayGroupCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = PayrollPayGroup(**data.model_dump())
    db.add(item)
    _audit(db, None, "pay_group_created", current_user.id, data.code)
    db.commit()
    db.refresh(item)
    return item


@router.get("/setup/statutory-profiles", response_model=List[PayrollStatutoryProfileSchema])
def list_statutory_profiles(
    legal_entity_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollStatutoryProfile).filter(PayrollStatutoryProfile.is_active == True)
    if legal_entity_id:
        query = query.filter(PayrollStatutoryProfile.legal_entity_id == legal_entity_id)
    return query.order_by(PayrollStatutoryProfile.effective_from.desc()).all()


@router.post("/setup/statutory-profiles", response_model=PayrollStatutoryProfileSchema, status_code=201)
def create_statutory_profile(
    data: PayrollStatutoryProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    item = PayrollStatutoryProfile(**data.model_dump())
    db.add(item)
    _audit(db, None, "statutory_profile_created", current_user.id, f"legal_entity_id={data.legal_entity_id}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/setup/periods", response_model=List[PayrollPeriodSchema])
def list_payroll_periods(
    year: Optional[int] = Query(None),
    pay_group_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollPeriod)
    if year:
        query = query.filter(PayrollPeriod.year == year)
    if pay_group_id:
        query = query.filter(PayrollPeriod.pay_group_id == pay_group_id)
    if status:
        query = query.filter(PayrollPeriod.status == status)
    return query.order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc()).all()


@router.post("/setup/periods", response_model=PayrollPeriodSchema, status_code=201)
def create_payroll_period(
    data: PayrollPeriodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    if data.period_end < data.period_start:
        raise HTTPException(status_code=400, detail="period_end cannot be before period_start")
    period = PayrollPeriod(**data.model_dump())
    db.add(period)
    _audit(db, None, "payroll_period_created", current_user.id, f"{data.month}/{data.year}")
    db.commit()
    db.refresh(period)
    return period


@router.post("/setup/periods/generate", response_model=List[PayrollPeriodSchema], status_code=201)
def generate_payroll_periods(
    data: PayrollPeriodGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    pay_group = db.query(PayrollPayGroup).filter(PayrollPayGroup.id == data.pay_group_id).first()
    if not pay_group:
        raise HTTPException(status_code=404, detail="Pay group not found")
    periods = []
    for month in range(1, 13):
        existing = db.query(PayrollPeriod).filter(
            PayrollPeriod.pay_group_id == data.pay_group_id,
            PayrollPeriod.month == month,
            PayrollPeriod.year == data.year,
        ).first()
        if existing:
            periods.append(existing)
            continue
        last_day = calendar.monthrange(data.year, month)[1]
        period_start = date(data.year, month, 1)
        period_end = date(data.year, month, last_day)
        payroll_day = min(pay_group.pay_cycle_day or last_day, last_day)
        payroll_date = date(data.year, month, payroll_day)
        cutoff_day = min(pay_group.attendance_cutoff_day or last_day, last_day)
        period = PayrollPeriod(
            pay_group_id=data.pay_group_id,
            month=month,
            year=data.year,
            financial_year=data.financial_year,
            period_start=period_start,
            period_end=period_end,
            attendance_cutoff_at=datetime(data.year, month, cutoff_day, 23, 59, 59),
            input_cutoff_at=datetime(data.year, month, min(pay_group.reimbursement_cutoff_day or cutoff_day, last_day), 23, 59, 59),
            payroll_date=payroll_date,
        )
        db.add(period)
        periods.append(period)
    _audit(db, None, "payroll_periods_generated", current_user.id, f"{data.pay_group_id}:{data.year}")
    db.commit()
    for period in periods:
        db.refresh(period)
    return periods


@router.put("/setup/periods/{period_id}/lock", response_model=PayrollPeriodSchema)
def lock_payroll_period(period_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_approve"))):
    period = db.query(PayrollPeriod).filter(PayrollPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    period.status = "Locked"
    period.locked_by = current_user.id
    period.locked_at = datetime.now(timezone.utc)
    _audit(db, None, "payroll_period_locked", current_user.id, f"id={period_id}")
    db.commit()
    db.refresh(period)
    return period


@router.put("/setup/periods/{period_id}/unlock", response_model=PayrollPeriodSchema)
def unlock_payroll_period(period_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_approve"))):
    period = db.query(PayrollPeriod).filter(PayrollPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    period.status = "Open"
    period.locked_by = None
    period.locked_at = None
    _audit(db, None, "payroll_period_unlocked", current_user.id, f"id={period_id}")
    db.commit()
    db.refresh(period)
    return period


@router.get("/setup/calendars", response_model=List[PayrollCalendarSchema])
def list_payroll_calendars(
    year: Optional[int] = Query(None),
    pay_group_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollCalendar)
    if year:
        query = query.filter(PayrollCalendar.year == year)
    if pay_group_id:
        query = query.filter(PayrollCalendar.pay_group_id == pay_group_id)
    return query.order_by(PayrollCalendar.year.desc(), PayrollCalendar.month.desc()).all()


@router.post("/setup/calendars", response_model=PayrollCalendarSchema, status_code=201)
def create_payroll_calendar(data: PayrollCalendarCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    if data.period_end < data.period_start:
        raise HTTPException(status_code=400, detail="period_end cannot be before period_start")
    item = PayrollCalendar(**data.model_dump())
    db.add(item)
    _audit(db, None, "payroll_calendar_created", current_user.id, f"{data.month}/{data.year}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/setup/compliance-rules", response_model=List[PayrollComplianceRuleSchema])
def list_compliance_rules(
    state: Optional[str] = Query(None),
    rule_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollComplianceRule).filter(PayrollComplianceRule.is_active == True)
    if state:
        query = query.filter(PayrollComplianceRule.state == state)
    if rule_type:
        query = query.filter(PayrollComplianceRule.rule_type == rule_type)
    return query.order_by(PayrollComplianceRule.state, PayrollComplianceRule.rule_type).all()


@router.post("/setup/compliance-rules", response_model=PayrollComplianceRuleSchema, status_code=201)
def create_compliance_rule(data: PayrollComplianceRuleCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = PayrollComplianceRule(**data.model_dump())
    db.add(item)
    _audit(db, None, "compliance_rule_created", current_user.id, f"{data.state}:{data.rule_type}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/statutory/pf-rules", response_model=List[PFRuleSchema])
def list_pf_rules(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(PFRule).filter(PFRule.is_active == True).order_by(PFRule.effective_from.desc()).all()


@router.post("/statutory/pf-rules", response_model=PFRuleSchema, status_code=201)
def create_pf_rule(data: PFRuleCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = PFRule(**data.model_dump())
    db.add(item)
    _audit(db, None, "pf_rule_created", current_user.id, data.name)
    db.commit()
    db.refresh(item)
    return item


@router.get("/statutory/esi-rules", response_model=List[ESIRuleSchema])
def list_esi_rules(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(ESIRule).filter(ESIRule.is_active == True).order_by(ESIRule.effective_from.desc()).all()


@router.post("/statutory/esi-rules", response_model=ESIRuleSchema, status_code=201)
def create_esi_rule(data: ESIRuleCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = ESIRule(**data.model_dump())
    db.add(item)
    _audit(db, None, "esi_rule_created", current_user.id, data.name)
    db.commit()
    db.refresh(item)
    return item


@router.get("/statutory/pt-slabs", response_model=List[ProfessionalTaxSlabSchema])
def list_pt_slabs(state: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    query = db.query(ProfessionalTaxSlab).filter(ProfessionalTaxSlab.is_active == True)
    if state:
        query = query.filter(ProfessionalTaxSlab.state == state)
    return query.order_by(ProfessionalTaxSlab.state, ProfessionalTaxSlab.salary_from).all()


@router.post("/statutory/pt-slabs", response_model=ProfessionalTaxSlabSchema, status_code=201)
def create_pt_slab(data: ProfessionalTaxSlabCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = ProfessionalTaxSlab(**data.model_dump())
    db.add(item)
    _audit(db, None, "pt_slab_created", current_user.id, data.state)
    db.commit()
    db.refresh(item)
    return item


@router.get("/statutory/lwf-slabs", response_model=List[LWFSlabSchema])
def list_lwf_slabs(state: Optional[str] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    query = db.query(LWFSlab).filter(LWFSlab.is_active == True)
    if state:
        query = query.filter(LWFSlab.state == state)
    return query.order_by(LWFSlab.state, LWFSlab.salary_from).all()


@router.post("/statutory/lwf-slabs", response_model=LWFSlabSchema, status_code=201)
def create_lwf_slab(data: LWFSlabCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = LWFSlab(**data.model_dump())
    db.add(item)
    _audit(db, None, "lwf_slab_created", current_user.id, data.state)
    db.commit()
    db.refresh(item)
    return item


@router.get("/statutory/gratuity-rules", response_model=List[GratuityRuleSchema])
def list_gratuity_rules(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(GratuityRule).filter(GratuityRule.is_active == True).order_by(GratuityRule.effective_from.desc()).all()


@router.post("/statutory/gratuity-rules", response_model=GratuityRuleSchema, status_code=201)
def create_gratuity_rule(data: GratuityRuleCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = GratuityRule(**data.model_dump())
    db.add(item)
    _audit(db, None, "gratuity_rule_created", current_user.id, data.name)
    db.commit()
    db.refresh(item)
    return item


@router.get("/statutory/employee-profiles", response_model=List[EmployeeStatutoryProfileSchema])
def list_employee_statutory_profiles(
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(EmployeeStatutoryProfile)
    if employee_id:
        query = query.filter(EmployeeStatutoryProfile.employee_id == employee_id)
    return query.order_by(EmployeeStatutoryProfile.id.desc()).limit(200).all()


@router.post("/statutory/employee-profiles", response_model=EmployeeStatutoryProfileSchema, status_code=201)
def upsert_employee_statutory_profile(
    data: EmployeeStatutoryProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    profile = db.query(EmployeeStatutoryProfile).filter(EmployeeStatutoryProfile.employee_id == data.employee_id).first()
    if not profile:
        profile = EmployeeStatutoryProfile(employee_id=data.employee_id)
        db.add(profile)
    for key, value in data.model_dump(exclude={"employee_id"}).items():
        setattr(profile, key, value)
    _audit(db, None, "employee_statutory_profile_upserted", current_user.id, f"employee_id={data.employee_id}")
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/statutory/calculate", response_model=StatutoryCalculationSchema, status_code=201)
def calculate_statutory_contributions(
    data: StatutoryCalculationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    calculation_date = date(data.year, data.month, 1)
    profile = db.query(EmployeeStatutoryProfile).filter(EmployeeStatutoryProfile.employee_id == data.employee_id).first()
    state = data.state or (profile.pt_state if profile else None)
    lines = []

    if not profile or profile.pf_applicable:
        pf_rule = _active_rule(db.query(PFRule), calculation_date)
        if pf_rule:
            pf_wage = min(Decimal(data.pf_wage or data.gross_salary), Decimal(pf_rule.wage_ceiling or 0))
            employee_pf = _rounded_money(pf_wage * Decimal(pf_rule.employee_rate or 0) / Decimal("100"), pf_rule.rounding_rule)
            employer_pf = _rounded_money(pf_wage * Decimal(pf_rule.employer_rate or 0) / Decimal("100"), pf_rule.rounding_rule)
            admin = _rounded_money(pf_wage * Decimal(pf_rule.admin_charge_rate or 0) / Decimal("100"), pf_rule.rounding_rule)
            edli = _rounded_money(pf_wage * Decimal(pf_rule.edli_rate or 0) / Decimal("100"), pf_rule.rounding_rule)
            lines.append(PayrollStatutoryContributionLine(
                payroll_record_id=data.payroll_record_id,
                employee_id=data.employee_id,
                component="PF",
                wage_base=pf_wage,
                employee_amount=employee_pf,
                employer_amount=employer_pf,
                admin_charge=admin,
                edli_amount=edli,
                rule_id=pf_rule.id,
                rule_type="PF",
            ))

    if profile and profile.esi_applicable:
        esi_rule = _active_rule(db.query(ESIRule), calculation_date)
        esi_wage = Decimal(data.esi_wage or data.gross_salary)
        if esi_rule and esi_wage <= Decimal(esi_rule.wage_threshold or 0):
            lines.append(PayrollStatutoryContributionLine(
                payroll_record_id=data.payroll_record_id,
                employee_id=data.employee_id,
                component="ESI",
                wage_base=esi_wage,
                employee_amount=_rounded_money(esi_wage * Decimal(esi_rule.employee_rate or 0) / Decimal("100"), esi_rule.rounding_rule),
                employer_amount=_rounded_money(esi_wage * Decimal(esi_rule.employer_rate or 0) / Decimal("100"), esi_rule.rounding_rule),
                rule_id=esi_rule.id,
                rule_type="ESI",
            ))

    if state:
        pt_slabs = db.query(ProfessionalTaxSlab).filter(
            ProfessionalTaxSlab.is_active == True,
            ProfessionalTaxSlab.state == state,
            ProfessionalTaxSlab.effective_from <= calculation_date,
        ).all()
        for slab in pt_slabs:
            if slab.month and slab.month != data.month:
                continue
            if _salary_in_slab(Decimal(data.gross_salary), Decimal(slab.salary_from or 0), slab.salary_to):
                lines.append(PayrollStatutoryContributionLine(
                    payroll_record_id=data.payroll_record_id,
                    employee_id=data.employee_id,
                    component="PT",
                    wage_base=data.gross_salary,
                    employee_amount=Decimal(slab.employee_amount or 0),
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
        ).all()
        for slab in lwf_slabs:
            if slab.deduction_month and slab.deduction_month != data.month:
                continue
            if _salary_in_slab(Decimal(data.gross_salary), Decimal(slab.salary_from or 0), slab.salary_to):
                lines.append(PayrollStatutoryContributionLine(
                    payroll_record_id=data.payroll_record_id,
                    employee_id=data.employee_id,
                    component="LWF",
                    wage_base=data.gross_salary,
                    employee_amount=Decimal(slab.employee_amount or 0),
                    employer_amount=Decimal(slab.employer_amount or 0),
                    rule_id=slab.id,
                    rule_type="LWF",
                ))
                break

    gratuity_rule = _active_rule(db.query(GratuityRule), calculation_date)
    if gratuity_rule and Decimal(data.service_years or 0) >= Decimal(gratuity_rule.min_service_years or 0):
        wage = Decimal(data.gratuity_wage or data.pf_wage or data.gross_salary)
        monthly_accrual = wage * Decimal(gratuity_rule.days_per_year or 0) / Decimal(gratuity_rule.wage_days_divisor or 1) / Decimal("12")
        lines.append(PayrollStatutoryContributionLine(
            payroll_record_id=data.payroll_record_id,
            employee_id=data.employee_id,
            component="GRATUITY",
            wage_base=wage,
            employee_amount=Decimal("0"),
            employer_amount=_rounded_money(monthly_accrual, gratuity_rule.rounding_rule),
            rule_id=gratuity_rule.id,
            rule_type="GRATUITY",
        ))

    for line in lines:
        db.add(line)
    _audit(db, None, "statutory_contributions_calculated", current_user.id, f"employee_id={data.employee_id}:{data.month}/{data.year}")
    db.commit()
    for line in lines:
        db.refresh(line)
    return {
        "employee_id": data.employee_id,
        "month": data.month,
        "year": data.year,
        "total_employee_amount": sum((line.employee_amount or Decimal("0")) for line in lines),
        "total_employer_amount": sum(((line.employer_amount or Decimal("0")) + (line.admin_charge or Decimal("0")) + (line.edli_amount or Decimal("0"))) for line in lines),
        "lines": lines,
    }


@router.get("/statutory/contribution-lines", response_model=List[PayrollStatutoryContributionLineSchema])
def list_statutory_contribution_lines(
    employee_id: Optional[int] = Query(None),
    component: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollStatutoryContributionLine)
    if employee_id:
        query = query.filter(PayrollStatutoryContributionLine.employee_id == employee_id)
    if component:
        query = query.filter(PayrollStatutoryContributionLine.component == component)
    return query.order_by(PayrollStatutoryContributionLine.id.desc()).limit(500).all()


@router.get("/inputs/attendance", response_model=List[PayrollAttendanceInputSchema])
def list_payroll_attendance_inputs(
    period_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    source_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollAttendanceInput)
    if period_id:
        query = query.filter(PayrollAttendanceInput.period_id == period_id)
    if employee_id:
        query = query.filter(PayrollAttendanceInput.employee_id == employee_id)
    if source_status:
        query = query.filter(PayrollAttendanceInput.source_status == source_status)
    return query.order_by(PayrollAttendanceInput.id.desc()).limit(500).all()


@router.post("/inputs/attendance", response_model=PayrollAttendanceInputSchema, status_code=201)
def upsert_payroll_attendance_input(
    data: PayrollAttendanceInputCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    period = db.query(PayrollPeriod).filter(PayrollPeriod.id == data.period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    if period.status == "Locked":
        raise HTTPException(status_code=400, detail="Payroll period is locked")
    item = db.query(PayrollAttendanceInput).filter(
        PayrollAttendanceInput.period_id == data.period_id,
        PayrollAttendanceInput.employee_id == data.employee_id,
    ).first()
    if not item:
        item = PayrollAttendanceInput(period_id=data.period_id, employee_id=data.employee_id)
        db.add(item)
    for key, value in data.model_dump(exclude={"period_id", "employee_id"}).items():
        setattr(item, key, value)
    if item.source_status in {"Approved", "Locked"} and not item.locked_at:
        item.locked_at = datetime.now(timezone.utc)
    _audit(db, None, "payroll_attendance_input_upserted", current_user.id, f"employee_id={data.employee_id}:period_id={data.period_id}")
    db.commit()
    db.refresh(item)
    return item


@router.post("/inputs/reconcile-attendance", response_model=PayrollAttendanceReconcileSchema, status_code=201)
def reconcile_payroll_attendance_inputs(
    data: PayrollAttendanceReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    from app.models.employee import Employee
    from app.models.attendance import Attendance, Holiday, OvertimeRequest
    from app.models.leave import LeaveRequest

    period = db.query(PayrollPeriod).filter(PayrollPeriod.id == data.period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    if period.status == "Locked":
        raise HTTPException(status_code=400, detail="Payroll period is locked")

    period_start, period_end = _period_bounds(period)
    employee_query = db.query(Employee).filter(Employee.status == "Active")
    if data.employee_ids:
        employee_query = employee_query.filter(Employee.id.in_(data.employee_ids))
    employees = employee_query.all()
    policy = _active_overtime_policy(db, period)
    working_days = Decimal(str(sum(1 for offset in range((period_end - period_start).days + 1) if (period_start + timedelta(days=offset)).weekday() < 5)))
    holiday_days = Decimal(str(db.query(Holiday).filter(
        Holiday.is_active == True,
        Holiday.holiday_date >= period_start,
        Holiday.holiday_date <= period_end,
    ).count()))
    calendar_days = _inclusive_days(period_start, period_end)
    weekly_off_days = max(Decimal("0"), calendar_days - working_days - holiday_days)
    inputs_created = 0
    overtime_created = 0
    exceptions = []

    for employee in employees:
        present_rows = db.query(Attendance).filter(
            Attendance.employee_id == employee.id,
            Attendance.attendance_date >= period_start,
            Attendance.attendance_date <= period_end,
            Attendance.status.in_(["Present", "WFH", "Half-day", "On Leave"]),
        ).all()
        present_days = Decimal("0")
        for row in present_rows:
            present_days += Decimal("0.5") if row.status == "Half-day" else Decimal("1")

        paid_leave_days = Decimal("0")
        unpaid_leave_days = Decimal("0")
        leaves = db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.status == "Approved",
            LeaveRequest.from_date <= period_end,
            LeaveRequest.to_date >= period_start,
        ).all()
        for leave in leaves:
            overlap_start = max(leave.from_date, period_start)
            overlap_end = min(leave.to_date, period_end)
            days = Decimal("0.5") if leave.is_half_day else _inclusive_days(overlap_start, overlap_end)
            if _is_unpaid_leave_type(leave.leave_type.name if leave.leave_type else None, leave.leave_type.code if leave.leave_type else None):
                unpaid_leave_days += days
            else:
                paid_leave_days += days

        approved_lop_adjustments = db.query(LOPAdjustment).filter(
            LOPAdjustment.period_id == period.id,
            LOPAdjustment.employee_id == employee.id,
            LOPAdjustment.status == "Approved",
        ).all()
        manual_lop_days = sum((item.adjustment_days or Decimal("0")) for item in approved_lop_adjustments)
        lop_days = max(Decimal("0"), unpaid_leave_days + Decimal(str(manual_lop_days)))
        payable_days = max(Decimal("0"), working_days - lop_days)

        item = db.query(PayrollAttendanceInput).filter(
            PayrollAttendanceInput.period_id == period.id,
            PayrollAttendanceInput.employee_id == employee.id,
        ).first()
        if not item:
            item = PayrollAttendanceInput(period_id=period.id, employee_id=employee.id)
            db.add(item)
            inputs_created += 1
        item.working_days = working_days
        item.present_days = present_days
        item.paid_leave_days = paid_leave_days
        item.unpaid_leave_days = unpaid_leave_days
        item.lop_days = lop_days
        item.payable_days = payable_days
        item.holiday_days = holiday_days
        item.weekly_off_days = weekly_off_days
        item.source_status = "Approved" if data.approve_inputs else "Draft"
        item.locked_at = datetime.now(timezone.utc) if data.approve_inputs else None

        approved_ot = db.query(OvertimeRequest).filter(
            OvertimeRequest.employee_id == employee.id,
            OvertimeRequest.status == "Approved",
            OvertimeRequest.date >= period_start,
            OvertimeRequest.date <= period_end,
        ).all()
        item.ot_hours = sum((row.hours or Decimal("0")) for row in approved_ot)
        for request in approved_ot:
            existing_line = db.query(OvertimePayLine).filter(
                OvertimePayLine.period_id == period.id,
                OvertimePayLine.approved_overtime_request_id == request.id,
            ).first()
            if existing_line:
                continue
            multiplier = policy.regular_multiplier if policy else Decimal("1")
            db.add(OvertimePayLine(
                period_id=period.id,
                employee_id=employee.id,
                policy_id=policy.id if policy else None,
                approved_overtime_request_id=request.id,
                ot_date=request.date,
                hours=request.hours,
                multiplier=multiplier,
                source="Reconciliation",
                status="Approved" if data.approve_inputs else "Pending",
                approved_by=current_user.id if data.approve_inputs else None,
                approved_at=datetime.now(timezone.utc) if data.approve_inputs else None,
            ))
            overtime_created += 1

        if present_days == 0 and paid_leave_days == 0 and unpaid_leave_days == 0:
            exceptions.append({"employee_id": employee.id, "issue": "No attendance or approved leave found in payroll period"})

    _audit(db, None, "payroll_attendance_reconciled", current_user.id, f"period_id={period.id}:employees={len(employees)}")
    db.commit()
    return {
        "period_id": period.id,
        "inputs_created": inputs_created,
        "overtime_lines_created": overtime_created,
        "exceptions": exceptions,
    }


@router.get("/inputs/lop-adjustments", response_model=List[LOPAdjustmentSchema])
def list_lop_adjustments(period_id: Optional[int] = Query(None), employee_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    query = db.query(LOPAdjustment)
    if period_id:
        query = query.filter(LOPAdjustment.period_id == period_id)
    if employee_id:
        query = query.filter(LOPAdjustment.employee_id == employee_id)
    return query.order_by(LOPAdjustment.id.desc()).limit(500).all()


@router.post("/inputs/lop-adjustments", response_model=LOPAdjustmentSchema, status_code=201)
def create_lop_adjustment(data: LOPAdjustmentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = LOPAdjustment(**data.model_dump(), created_by=current_user.id)
    if item.status == "Approved":
        item.approved_by = current_user.id
        item.approved_at = datetime.now(timezone.utc)
    db.add(item)
    _audit(db, None, "lop_adjustment_created", current_user.id, f"employee_id={data.employee_id}:period_id={data.period_id}")
    db.commit()
    db.refresh(item)
    return item


@router.put("/inputs/lop-adjustments/{adjustment_id}/review", response_model=LOPAdjustmentSchema)
def review_lop_adjustment(adjustment_id: int, data: LOPAdjustmentReview, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_approve"))):
    item = db.query(LOPAdjustment).filter(LOPAdjustment.id == adjustment_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="LOP adjustment not found")
    action = data.action.lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    item.status = "Approved" if action == "approve" else "Rejected"
    item.approved_by = current_user.id
    item.approved_at = datetime.now(timezone.utc)
    if data.remarks:
        item.reason = f"{item.reason or ''}\nReview: {data.remarks}".strip()
    db.commit()
    db.refresh(item)
    return item


@router.post("/inputs/overtime-policies", response_model=OvertimePolicySchema, status_code=201)
def create_overtime_policy(data: OvertimePolicyCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = OvertimePolicy(**data.model_dump())
    db.add(item)
    _audit(db, None, "overtime_policy_created", current_user.id, data.name)
    db.commit()
    db.refresh(item)
    return item


@router.get("/inputs/overtime-policies", response_model=List[OvertimePolicySchema])
def list_overtime_policies(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(OvertimePolicy).filter(OvertimePolicy.is_active == True).order_by(OvertimePolicy.name).all()


@router.post("/inputs/overtime-lines", response_model=OvertimePayLineSchema, status_code=201)
def create_overtime_line(data: OvertimePayLineCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    values = data.model_dump()
    if not values.get("amount") and values.get("hours") and values.get("hourly_rate"):
        values["amount"] = (Decimal(values["hours"]) * Decimal(values["hourly_rate"]) * Decimal(values["multiplier"])).quantize(Decimal("0.01"))
    item = OvertimePayLine(**values)
    if item.status == "Approved":
        item.approved_by = current_user.id
        item.approved_at = datetime.now(timezone.utc)
    db.add(item)
    _audit(db, None, "overtime_line_created", current_user.id, f"employee_id={data.employee_id}:period_id={data.period_id}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/inputs/overtime-lines", response_model=List[OvertimePayLineSchema])
def list_overtime_lines(period_id: Optional[int] = Query(None), employee_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    query = db.query(OvertimePayLine)
    if period_id:
        query = query.filter(OvertimePayLine.period_id == period_id)
    if employee_id:
        query = query.filter(OvertimePayLine.employee_id == employee_id)
    return query.order_by(OvertimePayLine.id.desc()).limit(500).all()


@router.post("/inputs/leave-encashment-policies", response_model=LeaveEncashmentPolicySchema, status_code=201)
def create_leave_encashment_policy(data: LeaveEncashmentPolicyCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = LeaveEncashmentPolicy(**data.model_dump())
    db.add(item)
    _audit(db, None, "leave_encashment_policy_created", current_user.id, data.name)
    db.commit()
    db.refresh(item)
    return item


@router.get("/inputs/leave-encashment-policies", response_model=List[LeaveEncashmentPolicySchema])
def list_leave_encashment_policies(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(LeaveEncashmentPolicy).filter(LeaveEncashmentPolicy.is_active == True).order_by(LeaveEncashmentPolicy.name).all()


@router.post("/inputs/leave-encashment-lines", response_model=LeaveEncashmentLineSchema, status_code=201)
def create_leave_encashment_line(data: LeaveEncashmentLineCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    values = data.model_dump()
    if not values.get("amount") and values.get("days") and values.get("rate_per_day"):
        values["amount"] = (Decimal(values["days"]) * Decimal(values["rate_per_day"])).quantize(Decimal("0.01"))
    item = LeaveEncashmentLine(**values)
    if item.status == "Approved":
        item.approved_by = current_user.id
        item.approved_at = datetime.now(timezone.utc)
    db.add(item)
    _audit(db, None, "leave_encashment_line_created", current_user.id, f"employee_id={data.employee_id}:period_id={data.period_id}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/inputs/leave-encashment-lines", response_model=List[LeaveEncashmentLineSchema])
def list_leave_encashment_lines(period_id: Optional[int] = Query(None), employee_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    query = db.query(LeaveEncashmentLine)
    if period_id:
        query = query.filter(LeaveEncashmentLine.period_id == period_id)
    if employee_id:
        query = query.filter(LeaveEncashmentLine.employee_id == employee_id)
    return query.order_by(LeaveEncashmentLine.id.desc()).limit(500).all()


@router.get("/statutory/challans", response_model=List[StatutoryChallanSchema])
def list_statutory_challans(
    challan_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(StatutoryChallan)
    if challan_type:
        query = query.filter(StatutoryChallan.challan_type == challan_type)
    return query.order_by(StatutoryChallan.due_date.desc()).limit(200).all()


@router.post("/statutory/challans", response_model=StatutoryChallanSchema, status_code=201)
def create_statutory_challan(data: StatutoryChallanCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    challan = StatutoryChallan(**data.model_dump())
    db.add(challan)
    _audit(db, None, "statutory_challan_created", current_user.id, data.challan_type)
    db.commit()
    db.refresh(challan)
    return challan


@router.post("/statutory/challans/generate", response_model=StatutoryChallanSchema, status_code=201)
def generate_statutory_challan(
    data: StatutoryChallanGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    components = {
        "PF": ["PF"],
        "ESI": ["ESI"],
        "PT": ["PT"],
        "LWF": ["LWF"],
        "GRATUITY": ["GRATUITY"],
    }.get(data.challan_type.upper(), [data.challan_type.upper()])
    lines = db.query(PayrollStatutoryContributionLine).filter(PayrollStatutoryContributionLine.component.in_(components)).all()
    amount = sum(
        (line.employee_amount or Decimal("0")) +
        (line.employer_amount or Decimal("0")) +
        (line.admin_charge or Decimal("0")) +
        (line.edli_amount or Decimal("0"))
        for line in lines
    )
    challan = StatutoryChallan(**data.model_dump(), amount=amount, status="Generated")
    db.add(challan)
    _audit(db, None, "statutory_challan_generated", current_user.id, f"{data.challan_type}:{amount}")
    db.commit()
    db.refresh(challan)
    return challan


@router.get("/statutory/return-files", response_model=List[StatutoryReturnFileSchema])
def list_statutory_return_files(
    challan_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(StatutoryReturnFile)
    if challan_id:
        query = query.filter(StatutoryReturnFile.challan_id == challan_id)
    return query.order_by(StatutoryReturnFile.id.desc()).limit(200).all()


@router.post("/statutory/return-files", response_model=StatutoryReturnFileSchema, status_code=201)
def create_statutory_return_file(
    data: StatutoryReturnFileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    challan = db.query(StatutoryChallan).filter(StatutoryChallan.id == data.challan_id).first()
    if not challan:
        raise HTTPException(status_code=404, detail="Statutory challan not found")
    errors = []
    if Decimal(challan.amount or 0) <= 0:
        errors.append({"field": "amount", "message": "Challan amount must be greater than zero"})
    if not data.file_url:
        errors.append({"field": "file_url", "message": "Return file URL is required before portal upload"})
    item = StatutoryReturnFile(
        **data.model_dump(),
        generated_by=current_user.id,
        validation_status="Failed" if errors else "Validated",
        validation_errors_json=errors,
    )
    db.add(item)
    _audit(db, None, "statutory_return_file_generated", current_user.id, f"challan_id={data.challan_id}:{item.validation_status}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/setup/bank-advice-formats", response_model=List[BankAdviceFormatSchema])
def list_bank_advice_formats(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(BankAdviceFormat).filter(BankAdviceFormat.is_active == True).order_by(BankAdviceFormat.bank_name).all()


@router.post("/setup/bank-advice-formats", response_model=BankAdviceFormatSchema, status_code=201)
def create_bank_advice_format(data: BankAdviceFormatCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = BankAdviceFormat(**data.model_dump())
    db.add(item)
    _audit(db, None, "bank_advice_format_created", current_user.id, f"{data.bank_name}:{data.name}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/components", response_model=List[SalaryComponentSchema])
def list_components(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    return db.query(SalaryComponent).filter(SalaryComponent.is_active == True).all()


@router.post("/components", response_model=SalaryComponentSchema, status_code=201)
def create_component(
    data: SalaryComponentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    _ensure_no_locked_payroll_exists(db, "change payroll component masters")
    comp = SalaryComponent(**data.model_dump())
    db.add(comp)
    _audit(db, None, "component_created", current_user.id, data.code)
    db.commit()
    db.refresh(comp)
    return comp


@router.put("/components/{component_id}", response_model=SalaryComponentSchema)
def update_component(
    component_id: int,
    data: SalaryComponentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    comp = db.query(SalaryComponent).filter(SalaryComponent.id == component_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Salary component not found")
    _ensure_no_locked_payroll_exists(db, "change payroll component masters")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(comp, k, v)
    _audit(db, None, "component_updated", current_user.id, comp.code)
    db.commit()
    db.refresh(comp)
    return comp


@router.delete("/components/{component_id}")
def delete_component(
    component_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    comp = db.query(SalaryComponent).filter(SalaryComponent.id == component_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Salary component not found")
    _ensure_no_locked_payroll_exists(db, "deactivate payroll component masters")
    comp.is_active = False
    _audit(db, None, "component_deactivated", current_user.id, comp.code)
    db.commit()
    return {"message": "Salary component deactivated"}


@router.get("/component-formula-rules", response_model=List[SalaryComponentFormulaRuleSchema])
def list_component_formula_rules(
    component_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(SalaryComponentFormulaRule)
    if component_id:
        query = query.filter(SalaryComponentFormulaRule.component_id == component_id)
    return query.order_by(SalaryComponentFormulaRule.dependency_order, SalaryComponentFormulaRule.id).all()


@router.post("/component-formula-rules", response_model=SalaryComponentFormulaRuleSchema, status_code=201)
def create_component_formula_rule(
    data: SalaryComponentFormulaRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    component = db.query(SalaryComponent).filter(SalaryComponent.id == data.component_id).first()
    if not component:
        raise HTTPException(status_code=404, detail="Salary component not found")
    _safe_formula_value(data.formula_expression, {"ctc_monthly": Decimal("100000"), "ctc_annual": Decimal("1200000")}, component.code)
    rule = SalaryComponentFormulaRule(**data.model_dump())
    db.add(rule)
    _audit(db, None, "component_formula_rule_created", current_user.id, component.code)
    db.commit()
    db.refresh(rule)
    return rule


# ── Salary Structures ─────────────────────────────────────────────────────────

@router.get("/structures", response_model=List[SalaryStructureSchema])
def list_structures(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    structures = db.query(SalaryStructure).filter(SalaryStructure.is_active == True).all()
    return [_structure_payload(structure) for structure in structures]


@router.post("/structures", response_model=SalaryStructureSchema, status_code=201)
def create_structure(
    data: SalaryStructureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    _ensure_no_locked_payroll_exists(db, "change salary structures")
    structure = SalaryStructure(
        name=data.name,
        description=data.description,
        version=data.version,
        parent_structure_id=data.parent_structure_id,
        effective_from=data.effective_from,
    )
    db.add(structure)
    db.flush()

    for comp_data in data.components:
        sc = SalaryStructureComponent(
            structure_id=structure.id,
            component_id=comp_data.component_id,
            amount=comp_data.amount,
            percentage=comp_data.percentage,
            order_sequence=comp_data.order_sequence,
        )
        db.add(sc)

    db.commit()
    db.refresh(structure)
    return _structure_payload(structure)


@router.post("/structures/{structure_id}/clone", response_model=SalaryStructureSchema, status_code=201)
def clone_structure(
    structure_id: int,
    version: str = Query(...),
    effective_from: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    _ensure_no_locked_payroll_exists(db, "version salary structures")
    source = db.query(SalaryStructure).filter(SalaryStructure.id == structure_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Salary structure not found")
    clone = SalaryStructure(
        name=source.name,
        description=source.description,
        version=version,
        parent_structure_id=source.id,
        effective_from=effective_from or source.effective_from,
    )
    db.add(clone)
    db.flush()
    for item in source.components:
        db.add(SalaryStructureComponent(
            structure_id=clone.id,
            component_id=item.component_id,
            amount=item.amount,
            percentage=item.percentage,
            order_sequence=item.order_sequence,
        ))
    _audit(db, None, "structure_version_created", current_user.id, f"{source.id}->{version}")
    db.commit()
    db.refresh(clone)
    return _structure_payload(clone)


@router.post("/structures/{structure_id}/preview", response_model=SalaryStructurePreviewSchema)
def preview_structure(
    structure_id: int,
    data: SalaryStructurePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    structure = db.query(SalaryStructure).filter(SalaryStructure.id == structure_id).first()
    if not structure:
        raise HTTPException(status_code=404, detail="Salary structure not found")
    monthly_ctc = (data.ctc / Decimal("12")).quantize(Decimal("0.01"))
    lines = []
    variables = {"ctc_monthly": monthly_ctc, "ctc_annual": data.ctc}
    ordered, warnings = _ordered_structure_components(structure)
    for item in ordered:
        component = item.component
        if not component:
            continue
        expression = getattr(item, "formula_expression", None) or _active_formula_expression(component)
        monthly = _component_monthly_amount(item, monthly_ctc, variables)
        variables[component.code] = monthly
        variables[component.code.lower()] = monthly
        lines.append({
            "component_id": component.id,
            "component_name": component.name,
            "component_code": component.code,
            "payslip_group": component.payslip_group,
            "display_sequence": component.display_sequence,
            "monthly_amount": monthly,
            "annual_amount": (monthly * Decimal("12")).quantize(Decimal("0.01")),
            "formula_expression": expression,
            "formula_trace": {
                "dependencies": sorted(_formula_dependencies(expression)),
                "min_amount": str(component.min_amount or getattr(item, "min_amount", None) or ""),
                "max_amount": str(component.max_amount or getattr(item, "max_amount", None) or ""),
            },
        })
    return {
        "structure_id": structure.id,
        "structure_name": structure.name,
        "version": structure.version,
        "monthly_ctc": monthly_ctc,
        "annual_ctc": data.ctc,
        "lines": lines,
        "formula_order": [item.component.code for item in ordered],
        "warnings": warnings,
    }


@router.get("/structures/{structure_id}/formula-graph")
def salary_structure_formula_graph(
    structure_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    structure = db.query(SalaryStructure).filter(SalaryStructure.id == structure_id).first()
    if not structure:
        raise HTTPException(status_code=404, detail="Salary structure not found")
    ordered, warnings = _ordered_structure_components(structure)
    return {
        "structure_id": structure.id,
        "formula_order": [item.component.code for item in ordered],
        "dependencies": [
            {
                "component_code": item.component.code,
                "depends_on": sorted(_formula_dependencies(getattr(item, "formula_expression", None) or _active_formula_expression(item.component))),
            }
            for item in ordered
        ],
        "warnings": warnings,
    }


# ── Employee Salary ───────────────────────────────────────────────────────────

@router.get("/salary-templates", response_model=List[SalaryTemplateSchema])
def list_salary_templates(
    pay_group_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(SalaryTemplate).filter(SalaryTemplate.is_active == True)
    if pay_group_id:
        query = query.filter(SalaryTemplate.pay_group_id == pay_group_id)
    return query.order_by(SalaryTemplate.name).all()


@router.post("/salary-templates", response_model=SalaryTemplateSchema, status_code=201)
def create_salary_template(
    data: SalaryTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    template = SalaryTemplate(
        name=data.name,
        code=data.code,
        pay_group_id=data.pay_group_id,
        grade=data.grade,
        location=data.location,
        description=data.description,
        residual_component_id=data.residual_component_id,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
    )
    db.add(template)
    db.flush()
    for component in data.components:
        db.add(SalaryTemplateComponent(template_id=template.id, **component.model_dump()))
    _audit(db, None, "salary_template_created", current_user.id, data.code)
    db.commit()
    db.refresh(template)
    return template


@router.post("/salary-template-assignments", response_model=EmployeeSalaryTemplateAssignmentSchema, status_code=201)
def assign_salary_template(
    data: EmployeeSalaryTemplateAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    assignment = EmployeeSalaryTemplateAssignment(
        **data.model_dump(),
        approved_by=current_user.id,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(assignment)
    _audit(db, None, "salary_template_assigned", current_user.id, f"employee_id={data.employee_id}")
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/salary-component-overrides", response_model=EmployeeSalaryComponentOverrideSchema, status_code=201)
def create_salary_component_override(
    data: EmployeeSalaryComponentOverrideCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    assignment = db.query(EmployeeSalaryTemplateAssignment).filter(EmployeeSalaryTemplateAssignment.id == data.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Salary template assignment not found")
    override = EmployeeSalaryComponentOverride(**data.model_dump(), approved_by=current_user.id)
    db.add(override)
    _audit(db, None, "salary_component_override_created", current_user.id, f"assignment_id={data.assignment_id}")
    db.commit()
    db.refresh(override)
    return override


@router.post("/salary", response_model=EmployeeSalarySchema, status_code=201)
def set_employee_salary(
    data: EmployeeSalaryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    from app.models.payroll import EmployeeSalary
    _ensure_not_locked_for_date(db, data.effective_from, "change salary assignment")

    # Deactivate existing salary
    existing = crud_payroll.get_active_salary(db, data.employee_id)
    if existing:
        record_salary_field_changes(
            db,
            employee_id=existing.employee_id,
            entity_type="employee_salary",
            entity_id=existing.id,
            old_values={"is_active": existing.is_active, "effective_to": existing.effective_to},
            new_values={"is_active": False, "effective_to": data.effective_from - timedelta(days=1)},
            actor_user_id=current_user.id,
            action="deactivated",
            reason="New salary assignment",
        )
        existing.is_active = False
        existing.effective_to = data.effective_from - timedelta(days=1)

    payload = data.model_dump()
    payload["effective_date"] = payload.get("effective_date") or payload["effective_from"]
    salary = EmployeeSalary(**payload)
    db.add(salary)
    db.flush()
    record_salary_field_changes(
        db,
        employee_id=data.employee_id,
        entity_type="employee_salary",
        entity_id=salary.id,
        old_values={},
        new_values=payload,
        actor_user_id=current_user.id,
        action="created",
        reason="Salary assignment",
    )
    _audit(db, None, "salary_assigned", current_user.id, f"employee_id={data.employee_id}")
    db.commit()
    db.refresh(salary)
    return salary


@router.get("/salary/{employee_id}", response_model=List[EmployeeSalarySchema])
def get_employee_salary_history(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    from app.models.payroll import EmployeeSalary
    return db.query(EmployeeSalary).filter(
        EmployeeSalary.employee_id == employee_id
    ).order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc()).all()


@router.post("/salary-revisions", response_model=SalaryRevisionRequestSchema, status_code=201)
def create_salary_revision_request(
    data: SalaryRevisionRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    _ensure_not_locked_for_date(db, data.effective_from, "request salary revision")
    current_salary = crud_payroll.get_active_salary(db, data.employee_id)
    request = SalaryRevisionRequest(
        employee_id=data.employee_id,
        current_salary_id=current_salary.id if current_salary else None,
        proposed_structure_id=data.proposed_structure_id,
        current_ctc=current_salary.ctc if current_salary else Decimal("0"),
        proposed_ctc=data.proposed_ctc,
        effective_from=data.effective_from,
        reason=data.reason,
        requested_by=current_user.id,
    )
    db.add(request)
    db.add(SensitiveSalaryAuditLog(
        employee_id=data.employee_id,
        entity_type="salary_revision_request",
        action="created",
        field_name="ctc",
        old_value_masked=_mask_money(current_salary.ctc if current_salary else None),
        new_value_masked=_mask_money(data.proposed_ctc),
        actor_user_id=current_user.id,
        reason=data.reason,
    ))
    db.commit()
    db.refresh(request)
    return request


@router.get("/salary-revisions", response_model=List[SalaryRevisionRequestSchema])
def list_salary_revision_requests(
    status: Optional[str] = Query(None),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(SalaryRevisionRequest)
    if status:
        query = query.filter(SalaryRevisionRequest.status == status)
    if employee_id:
        query = query.filter(SalaryRevisionRequest.employee_id == employee_id)
    return query.order_by(SalaryRevisionRequest.id.desc()).limit(200).all()


@router.put("/salary-revisions/{revision_id}/review", response_model=SalaryRevisionRequestSchema)
def review_salary_revision_request(
    revision_id: int,
    data: SalaryRevisionReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_approve")),
):
    request = db.query(SalaryRevisionRequest).filter(SalaryRevisionRequest.id == revision_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Salary revision request not found")
    if request.status != "Pending":
        raise HTTPException(status_code=400, detail="Salary revision request is already reviewed")
    action = data.action.lower()
    request.checked_by = current_user.id
    request.checked_at = datetime.now(timezone.utc)
    request.checker_remarks = data.remarks
    if action == "approve":
        existing = crud_payroll.get_active_salary(db, request.employee_id)
        if existing:
            record_salary_field_changes(
                db,
                employee_id=existing.employee_id,
                entity_type="employee_salary",
                entity_id=existing.id,
                old_values={"is_active": existing.is_active, "effective_to": existing.effective_to},
                new_values={"is_active": False, "effective_to": request.effective_from - timedelta(days=1)},
                actor_user_id=current_user.id,
                action="deactivated",
                reason=data.remarks or "Salary revision applied",
            )
            existing.is_active = False
            existing.effective_to = request.effective_from - timedelta(days=1)
        salary = EmployeeSalary(
            employee_id=request.employee_id,
            structure_id=request.proposed_structure_id,
            ctc=request.proposed_ctc,
            effective_from=request.effective_from,
            effective_date=request.effective_from,
            is_active=True,
        )
        db.add(salary)
        db.flush()
        record_salary_field_changes(
            db,
            employee_id=request.employee_id,
            entity_type="salary_revision_request",
            entity_id=request.id,
            old_values={"ctc": request.current_ctc},
            new_values={"ctc": request.proposed_ctc, "structure_id": request.proposed_structure_id, "effective_from": request.effective_from, "is_active": True},
            actor_user_id=current_user.id,
            action="approved_applied",
            reason=data.remarks,
        )
        request.status = "Applied"
        db.add(SensitiveSalaryAuditLog(
            employee_id=request.employee_id,
            entity_type="salary_revision_request",
            entity_id=request.id,
            action="approved_applied",
            field_name="ctc",
            old_value_masked=_mask_money(request.current_ctc),
            new_value_masked=_mask_money(request.proposed_ctc),
            actor_user_id=current_user.id,
            reason=data.remarks,
        ))
    elif action == "reject":
        request.status = "Rejected"
    else:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    db.commit()
    db.refresh(request)
    return request


@router.get("/salary-audit", response_model=List[SensitiveSalaryAuditLogSchema])
def list_sensitive_salary_audit(
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(SensitiveSalaryAuditLog)
    if employee_id:
        query = query.filter(SensitiveSalaryAuditLog.employee_id == employee_id)
    return query.order_by(SensitiveSalaryAuditLog.id.desc()).limit(200).all()


# ── Payroll Run ───────────────────────────────────────────────────────────────

@router.get("/runs", response_model=List[PayrollRunSchema])
def list_payroll_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollRun).filter(
        PayrollRun.deleted_at.is_(None)
    )
    company_id = None if current_user.is_superuser else _current_company_id(current_user)
    if company_id:
        query = query.filter(PayrollRun.company_id == company_id)
    return query.order_by(PayrollRun.year.desc(), PayrollRun.month.desc()).all()


@router.get("/last-run", response_model=PayrollRunSchema | None)
def get_last_payroll_run(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollRun).filter(PayrollRun.deleted_at.is_(None))
    company_id = None if current_user.is_superuser else _current_company_id(current_user)
    if company_id:
        query = query.filter(PayrollRun.company_id == company_id)
    return query.order_by(PayrollRun.year.desc(), PayrollRun.month.desc(), PayrollRun.id.desc()).first()


@router.post("/run", response_model=PayrollRunSchema, status_code=201)
def run_payroll(
    data: PayrollRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    effective_company_id = data.company_id if data.company_id is not None else _current_company_id(current_user)
    _ensure_not_locked_period(
        db,
        data.month,
        data.year,
        "rerun payroll",
        company_id=effective_company_id,
        branch_id=data.branch_id,
        department_id=data.department_id,
        pay_group_id=data.pay_group_id,
        employee_category=data.employee_category,
    )
    try:
        run = crud_payroll.run_payroll(
            db,
            data.month,
            data.year,
            current_user.id,
            force_run=data.force_run,
            company_id=effective_company_id,
            branch_id=data.branch_id,
            department_id=data.department_id,
            pay_group_id=data.pay_group_id,
            employee_category=data.employee_category,
            pay_period_start=data.pay_period_start,
            pay_period_end=data.pay_period_end,
        )
        db.commit()
        db.refresh(run)
        return run
    except crud_payroll.PayrollReadinessError as e:
        raise HTTPException(status_code=400, detail={"message": "Payroll readiness checks failed", "readiness": e.summary})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs/{run_id}", response_model=PayrollRunSchema)
def get_payroll_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    return _get_payroll_run_or_404(db, run_id)


@router.put("/runs/{run_id}/approve")
def approve_payroll(
    run_id: int,
    data: PayrollRunApproval,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_approve")),
):
    run = _get_payroll_run_or_404(db, run_id)
    try:
        crud_payroll.coerce_payroll_run_status(run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    action = data.action.lower()
    if action == "approve":
        blockers = _payroll_input_blockers(db, run)
        if blockers and not data.force_approve:
            raise HTTPException(status_code=400, detail={"message": "Payroll attendance inputs must be approved and locked before approval", "blockers": blockers})
        try:
            crud_payroll.transition_payroll_run_status(run, crud_payroll.PAYROLL_RUN_STATUS_APPROVED)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        run.approved_by = current_user.id
        run.approved_at = datetime.now(timezone.utc)
        audit_detail = data.remarks
        if blockers and data.force_approve:
            audit_detail = f"{data.remarks or 'Forced approval'} | overridden blockers: {'; '.join(blockers)}"
        _audit(db, run.id, "approved", current_user.id, audit_detail)
    elif action == "lock":
        try:
            crud_payroll.transition_payroll_run_status(run, crud_payroll.PAYROLL_RUN_STATUS_LOCKED)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        run.locked_by = current_user.id
        run.locked_at = datetime.now(timezone.utc)
        _audit(db, run.id, "locked", current_user.id, data.remarks)
    elif action in {"paid", "mark_paid"}:
        try:
            crud_payroll.transition_payroll_run_status(run, crud_payroll.PAYROLL_RUN_STATUS_PAID)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        _audit(db, run.id, "paid", current_user.id, data.remarks)
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    run.remarks = data.remarks
    db.commit()
    return {"message": f"Payroll {action} successfully", "status": run.status}


@router.get("/runs/{run_id}/variance", response_model=List[PayrollVarianceItemSchema])
def get_payroll_variance(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    try:
        return crud_payroll.calculate_payroll_variance(db, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/runs/{run_id}/exports/{export_type}/validate")
def validate_payroll_export(
    run_id: int,
    export_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    run = _get_payroll_run_or_404(db, run_id)
    return _payroll_export_readiness(db, run, export_type)


@router.post("/runs/{run_id}/exports/{export_type}", response_model=PayrollExportBatchSchema, status_code=201)
def create_payroll_export(
    run_id: int,
    export_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    if export_type not in EXPORT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported payroll export type")
    run = _get_payroll_run_or_404(db, run_id)
    readiness = _payroll_export_readiness(db, run, export_type)
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run_id).all()
    total_records = len(records)
    export_dir = os.path.join(settings.UPLOAD_DIR, "exports", "payroll", str(run_id))
    os.makedirs(export_dir, exist_ok=True)
    file_path = os.path.join(export_dir, f"{export_type}.csv")
    headers_by_type = {
        "pf_ecr": ["employee_id", "gross_salary", "pf_employee", "pf_employer"],
        "esi": ["employee_id", "gross_salary", "esi_employee", "esi_employer"],
        "pt": ["employee_id", "professional_tax", "gross_salary"],
        "tds_24q": ["employee_id", "gross_salary", "tds"],
        "form_16": ["employee_id", "gross_salary", "tds", "year"],
        "bank_advice": ["employee_id", "net_salary"],
        "pay_register": ["employee_id", "gross_salary", "total_deductions", "net_salary"],
        "accounting_journal": ["ledger", "employee_id", "debit", "credit"],
    }
    with open(file_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers_by_type[export_type])
        for record in records:
            if export_type == "accounting_journal":
                writer.writerow(["Salary Expense", record.employee_id, record.gross_salary or 0, 0])
                writer.writerow(["Salary Payable", record.employee_id, 0, record.net_salary or 0])
            elif export_type == "pf_ecr":
                writer.writerow([record.employee_id, record.gross_salary or 0, record.pf_employee or 0, record.pf_employer or 0])
            elif export_type == "esi":
                writer.writerow([record.employee_id, record.gross_salary or 0, record.esi_employee or 0, record.esi_employer or 0])
            elif export_type == "pt":
                writer.writerow([record.employee_id, record.professional_tax or 0, record.gross_salary or 0])
            elif export_type == "tds_24q":
                writer.writerow([record.employee_id, record.gross_salary or 0, record.tds or 0])
            elif export_type == "form_16":
                writer.writerow([record.employee_id, record.gross_salary or 0, record.tds or 0, run.year])
            elif export_type == "bank_advice":
                writer.writerow([record.employee_id, record.net_salary or 0])
            else:
                writer.writerow([record.employee_id, record.gross_salary or 0, record.total_deductions or 0, record.net_salary or 0])
    output_url = f"/uploads/exports/payroll/{run_id}/{export_type}.csv"
    batch = PayrollExportBatch(
        payroll_run_id=run_id,
        export_type=export_type,
        status="Generated",
        output_file_url=output_url,
        total_records=total_records,
        generated_by=current_user.id,
        remarks="CSV export generated." if readiness["ready"] else f"CSV export generated with {readiness['critical_issue_count']} readiness issue(s).",
    )
    db.add(batch)
    _audit(db, run_id, "export_generated", current_user.id, f"{export_type}:ready={readiness['ready']}:issues={readiness['critical_issue_count']}")
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/exports/{batch_id}/download")
def download_payroll_export(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    batch = db.query(PayrollExportBatch).filter(PayrollExportBatch.id == batch_id).first()
    if not batch or not batch.output_file_url:
        raise HTTPException(status_code=404, detail="Export file not found")
    file_path = os.path.join(settings.UPLOAD_DIR, batch.output_file_url.replace("/uploads/", "").replace("/", os.sep))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Export file missing on disk")
    return FileResponse(file_path, media_type="text/csv", filename=os.path.basename(file_path))


@router.get("/runs/{run_id}/audit", response_model=List[PayrollRunAuditLogSchema])
def get_payroll_audit(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    return db.query(PayrollRunAuditLog).filter(
        PayrollRunAuditLog.payroll_run_id == run_id
    ).order_by(PayrollRunAuditLog.id.desc()).all()


@router.get("/runs/{run_id}/worksheet", response_model=List[PayrollRunEmployeeSchema])
def list_payroll_worksheet(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    _get_payroll_run_or_404(db, run_id)
    return db.query(PayrollRunEmployee).filter(PayrollRunEmployee.payroll_run_id == run_id).order_by(PayrollRunEmployee.id).all()


@router.put("/runs/{run_id}/worksheet/{row_id}", response_model=PayrollRunEmployeeSchema)
def update_payroll_worksheet_row(
    run_id: int,
    row_id: int,
    data: PayrollRunEmployeeAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    run = _get_payroll_run_or_404(db, run_id)
    try:
        crud_payroll.coerce_payroll_run_status(run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if run.status in {crud_payroll.PAYROLL_RUN_STATUS_LOCKED, crud_payroll.PAYROLL_RUN_STATUS_PAID}:
        raise HTTPException(status_code=400, detail="Payroll run is locked")

    row = db.query(PayrollRunEmployee).filter(
        PayrollRunEmployee.id == row_id,
        PayrollRunEmployee.payroll_run_id == run_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Payroll worksheet row not found")

    action = data.action.strip().lower()
    reason = (data.reason or "").strip() or None
    if action == "hold":
        row.status = "Held"
        row.approval_status = "On Hold"
        row.hold_reason = reason or "Held from payroll console"
        row.skip_reason = None
    elif action == "skip":
        row.status = "Skipped"
        row.approval_status = "Skipped"
        row.skip_reason = reason or "Skipped from payroll console"
        row.hold_reason = None
    elif action == "clear":
        row.status = "Calculated"
        row.approval_status = "Pending"
        row.hold_reason = None
        row.skip_reason = None
    elif action == "approve":
        if row.hold_reason or row.skip_reason:
            raise HTTPException(status_code=400, detail="Clear hold/skip before approving this employee")
        row.status = "Approved"
        row.approval_status = "Approved"
        row.approved_by = current_user.id
        row.approved_at = datetime.now(timezone.utc)
    else:
        raise HTTPException(status_code=400, detail="action must be hold, skip, clear, or approve")

    _audit(db, run_id, f"worksheet_employee_{action}", current_user.id, f"row_id={row_id}:{reason or ''}")
    db.commit()
    db.refresh(row)
    return row


@router.post("/runs/{run_id}/worksheet/process", response_model=PayrollWorksheetProcessSchema, status_code=201)
def process_payroll_worksheet(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    run = _get_payroll_run_or_404(db, run_id)
    try:
        crud_payroll.coerce_payroll_run_status(run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if run.status in {crud_payroll.PAYROLL_RUN_STATUS_LOCKED, crud_payroll.PAYROLL_RUN_STATUS_PAID}:
        raise HTTPException(status_code=400, detail="Payroll run is locked")
    period = _payroll_period_for_run(db, run)
    blocked = _payroll_input_blockers(db, run)
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run_id).all()
    processed = 0
    snapshots_created = 0
    for record in records:
        attendance_input = None
        if period:
            attendance_input = db.query(PayrollAttendanceInput).filter(
                PayrollAttendanceInput.period_id == period.id,
                PayrollAttendanceInput.employee_id == record.employee_id,
            ).first()
        row = db.query(PayrollRunEmployee).filter(
            PayrollRunEmployee.payroll_run_id == run_id,
            PayrollRunEmployee.employee_id == record.employee_id,
        ).first()
        if not row:
            row = PayrollRunEmployee(payroll_run_id=run_id, employee_id=record.employee_id)
            db.add(row)
            db.flush()
        row.payroll_record_id = record.id
        manual_hold = bool(row.hold_reason)
        manual_skip = bool(row.skip_reason)
        row.status = "Skipped" if manual_skip else "Held" if manual_hold else "Blocked" if any(f"Employee {record.employee_id}:" in blocker for blocker in blocked) else "Calculated"
        row.input_status = attendance_input.source_status if attendance_input else "Missing"
        row.calculation_status = "Calculated"
        row.approval_status = "Skipped" if manual_skip else "On Hold" if manual_hold else "Pending"
        row.gross_salary = record.gross_salary or Decimal("0")
        row.total_deductions = record.total_deductions or Decimal("0")
        row.net_salary = record.net_salary or Decimal("0")
        if not manual_hold and not manual_skip:
            row.hold_reason = "; ".join(blocker for blocker in blocked if f"Employee {record.employee_id}:" in blocker) or None
        snapshot = PayrollCalculationSnapshot(
            payroll_run_id=run_id,
            run_employee_id=row.id,
            employee_id=record.employee_id,
            snapshot_type="Worksheet",
            attendance_input_json=_attendance_input_payload(attendance_input),
            result_json={
                "payroll_record_id": record.id,
                "working_days": str(record.working_days or 0),
                "present_days": str(record.present_days or 0),
                "lop_days": str(record.lop_days or 0),
                "gross_salary": str(record.gross_salary or 0),
                "total_deductions": str(record.total_deductions or 0),
                "net_salary": str(record.net_salary or 0),
            },
            formula_version_json={"engine": "legacy-run-v1", "snapshot_reason": "worksheet_process"},
            created_by=current_user.id,
        )
        db.add(snapshot)
        processed += 1
        snapshots_created += 1
    _audit(db, run_id, "worksheet_processed", current_user.id, f"processed={processed}:blocked={len(blocked)}")
    db.commit()
    return {"payroll_run_id": run_id, "employees_processed": processed, "snapshots_created": snapshots_created, "blocked": blocked}


@router.get("/runs/{run_id}/calculation-snapshots", response_model=List[PayrollCalculationSnapshotSchema])
def list_payroll_calculation_snapshots(
    run_id: int,
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollCalculationSnapshot).filter(PayrollCalculationSnapshot.payroll_run_id == run_id)
    if employee_id:
        query = query.filter(PayrollCalculationSnapshot.employee_id == employee_id)
    return query.order_by(PayrollCalculationSnapshot.id.desc()).limit(500).all()


@router.post("/arrear-runs", response_model=PayrollArrearRunSchema, status_code=201)
def create_payroll_arrear_run(
    data: PayrollArrearRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    run = PayrollArrearRun(
        payroll_run_id=data.payroll_run_id,
        period_id=data.period_id,
        name=data.name,
        reason=data.reason,
        created_by=current_user.id,
    )
    db.add(run)
    db.flush()
    for line in data.lines:
        db.add(PayrollArrearLine(arrear_run_id=run.id, **line.model_dump()))
    _audit(db, data.payroll_run_id, "arrear_run_created", current_user.id, data.name)
    db.commit()
    db.refresh(run)
    return run


@router.get("/arrear-runs", response_model=List[PayrollArrearRunSchema])
def list_payroll_arrear_runs(
    payroll_run_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollArrearRun)
    if payroll_run_id:
        query = query.filter(PayrollArrearRun.payroll_run_id == payroll_run_id)
    return query.order_by(PayrollArrearRun.id.desc()).limit(200).all()


@router.post("/off-cycle-runs", response_model=OffCyclePayrollRunSchema, status_code=201)
def create_off_cycle_payroll_run(
    data: OffCyclePayrollRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    item = OffCyclePayrollRun(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    _audit(db, None, "off_cycle_run_created", current_user.id, f"{data.run_type}:{data.month}/{data.year}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/off-cycle-runs", response_model=List[OffCyclePayrollRunSchema])
def list_off_cycle_payroll_runs(
    year: Optional[int] = Query(None),
    run_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(OffCyclePayrollRun)
    if year:
        query = query.filter(OffCyclePayrollRun.year == year)
    if run_type:
        query = query.filter(OffCyclePayrollRun.run_type == run_type)
    return query.order_by(OffCyclePayrollRun.id.desc()).limit(200).all()


@router.post("/payments/batches", response_model=PayrollPaymentBatchSchema, status_code=201)
def create_payment_batch(
    data: PayrollPaymentBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    from app.models.employee import Employee

    run = _get_payroll_run_or_404(db, data.payroll_run_id)
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run.id).all()
    if not records:
        raise HTTPException(status_code=400, detail="No payroll records available for payment batch")
    batch = PayrollPaymentBatch(
        payroll_run_id=run.id,
        bank_format_id=data.bank_format_id,
        debit_account=data.debit_account,
        created_by=current_user.id,
        status="Generated",
    )
    db.add(batch)
    db.flush()
    rows = []
    total_amount = Decimal("0")
    for record in records:
        employee = db.query(Employee).filter(Employee.id == record.employee_id).first()
        line = PayrollPaymentLine(
            batch_id=batch.id,
            payroll_record_id=record.id,
            employee_id=record.employee_id,
            net_amount=record.net_salary or Decimal("0"),
            bank_account=employee.account_number if employee else None,
            ifsc=employee.ifsc_code if employee else None,
            payment_status="Pending",
        )
        db.add(line)
        total_amount += line.net_amount or Decimal("0")
        rows.append([record.employee_id, employee.employee_id if employee else "", employee.account_number if employee else "", employee.ifsc_code if employee else "", record.net_salary or 0])
    file_path = _write_rows_file(
        os.path.join(settings.UPLOAD_DIR, "exports", "payroll", str(run.id), "payments"),
        f"payment_batch_{batch.id}.csv",
        ["employee_db_id", "employee_code", "account_number", "ifsc", "net_amount"],
        rows,
    )
    batch.total_amount = total_amount
    batch.generated_file_url = _file_url_from_upload_path(file_path)
    _audit(db, run.id, "payment_batch_generated", current_user.id, f"batch_id={batch.id}:amount={total_amount}")
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/payments/batches", response_model=List[PayrollPaymentBatchSchema])
def list_payment_batches(
    payroll_run_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(PayrollPaymentBatch)
    if payroll_run_id:
        query = query.filter(PayrollPaymentBatch.payroll_run_id == payroll_run_id)
    return query.order_by(PayrollPaymentBatch.id.desc()).limit(200).all()


@router.put("/payments/batches/{batch_id}/status-import", response_model=PayrollPaymentStatusImportSchema)
def import_payment_status(
    batch_id: int,
    data: PayrollPaymentStatusImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    batch = db.query(PayrollPaymentBatch).filter(PayrollPaymentBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Payment batch not found")
    updated = 0
    failed = 0
    for row in data.lines:
        query = db.query(PayrollPaymentLine).filter(PayrollPaymentLine.batch_id == batch_id)
        if row.payroll_record_id:
            query = query.filter(PayrollPaymentLine.payroll_record_id == row.payroll_record_id)
        elif row.employee_id:
            query = query.filter(PayrollPaymentLine.employee_id == row.employee_id)
        else:
            failed += 1
            continue
        line = query.first()
        if not line:
            failed += 1
            continue
        line.payment_status = row.payment_status
        line.utr_number = row.utr_number
        line.failure_reason = row.failure_reason
        if row.payment_status.lower() in {"paid", "success", "completed"}:
            line.payment_status = "Paid"
            line.paid_at = datetime.now(timezone.utc)
        elif row.payment_status.lower() in {"failed", "rejected"}:
            line.payment_status = "Failed"
        updated += 1
    statuses = {line.payment_status for line in batch.lines}
    if statuses and statuses <= {"Paid"}:
        batch.status = "Paid"
        batch.released_at = datetime.now(timezone.utc)
    elif "Failed" in statuses:
        batch.status = "Partially Failed"
    else:
        batch.status = "Processing"
    _audit(db, batch.payroll_run_id, "payment_status_imported", current_user.id, f"batch_id={batch_id}:updated={updated}:failed={failed}")
    db.commit()
    return {"batch_id": batch_id, "updated": updated, "failed": failed}


@router.post("/accounting/ledgers", response_model=AccountingLedgerSchema, status_code=201)
def create_accounting_ledger(data: AccountingLedgerCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    existing = db.query(AccountingLedger).filter(AccountingLedger.code == data.code).first()
    if existing:
        return existing
    item = AccountingLedger(**data.model_dump())
    db.add(item)
    _audit(db, None, "accounting_ledger_created", current_user.id, data.code)
    db.commit()
    db.refresh(item)
    return item


@router.get("/accounting/ledgers", response_model=List[AccountingLedgerSchema])
def list_accounting_ledgers(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(AccountingLedger).filter(AccountingLedger.is_active == True).order_by(AccountingLedger.code).all()


@router.post("/accounting/gl-mappings", response_model=PayrollGLMappingSchema, status_code=201)
def create_gl_mapping(data: PayrollGLMappingCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    item = PayrollGLMapping(**data.model_dump())
    db.add(item)
    _audit(db, None, "gl_mapping_created", current_user.id, data.component_name)
    db.commit()
    db.refresh(item)
    return item


@router.get("/accounting/gl-mappings", response_model=List[PayrollGLMappingSchema])
def list_gl_mappings(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(PayrollGLMapping).filter(PayrollGLMapping.is_active == True).order_by(PayrollGLMapping.component_name).all()


@router.post("/runs/{run_id}/accounting-journal", response_model=PayrollJournalEntrySchema, status_code=201)
def generate_accounting_journal(run_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    from app.models.employee import Employee

    run = _get_payroll_run_or_404(db, run_id)
    ledgers = _ensure_default_ledgers(db)
    journal = PayrollJournalEntry(payroll_run_id=run_id, status="Generated", generated_by=current_user.id)
    db.add(journal)
    db.flush()
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run_id).all()
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for record in records:
        employee = db.query(Employee).filter(Employee.id == record.employee_id).first()
        gross = Decimal(record.gross_salary or 0)
        deductions = Decimal(record.total_deductions or 0)
        net = Decimal(record.net_salary or 0)
        reimbursements = Decimal(record.reimbursements or 0)
        dept_id = employee.department_id if employee else None
        branch_id = employee.branch_id if employee else None
        lines = [
            (ledgers["SAL_EXP"], gross, Decimal("0"), "Gross payroll expense"),
            (ledgers["SAL_EXP"], reimbursements, Decimal("0"), "Approved reimbursement expense"),
            (ledgers["DED_PAY"], Decimal("0"), deductions, "Employee statutory/tax deductions"),
            (ledgers["SAL_PAY"], Decimal("0"), net, "Net salary payable"),
        ]
        for ledger, debit, credit, memo in lines:
            if debit == 0 and credit == 0:
                continue
            db.add(PayrollJournalLine(
                journal_entry_id=journal.id,
                ledger_id=ledger.id,
                ledger_code=ledger.code,
                ledger_name=ledger.name,
                employee_id=record.employee_id,
                component_name=memo,
                debit=debit,
                credit=credit,
                memo=f"{memo}; branch={branch_id}; department={dept_id}",
            ))
            total_debit += debit
            total_credit += credit
    journal.total_debit = total_debit
    journal.total_credit = total_credit
    if total_debit != total_credit:
        journal.status = "Unbalanced"
    _audit(db, run_id, "accounting_journal_generated", current_user.id, f"debit={total_debit}:credit={total_credit}")
    db.commit()
    db.refresh(journal)
    return journal


@router.get("/runs/{run_id}/accounting-journals", response_model=List[PayrollJournalEntrySchema])
def list_accounting_journals(run_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(PayrollJournalEntry).filter(PayrollJournalEntry.payroll_run_id == run_id).order_by(PayrollJournalEntry.id.desc()).all()


@router.post("/statutory/file-validations", response_model=StatutoryFileValidationSchema, status_code=201)
def validate_statutory_file(data: StatutoryFileValidationRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    query = db.query(PayrollRecord)
    if data.payroll_run_id:
        query = query.filter(PayrollRecord.payroll_run_id == data.payroll_run_id)
    records = query.all()
    errors = []
    rows = []
    for record in records:
        if data.file_type in {"pf_ecr", "PF_ECR"} and not record.pf_employee:
            errors.append({"employee_id": record.employee_id, "field": "pf_employee", "message": "PF employee amount is zero"})
        if data.file_type in {"esi", "ESI"} and record.gross_salary and record.gross_salary <= Decimal("21000") and not record.esi_employee:
            errors.append({"employee_id": record.employee_id, "field": "esi_employee", "message": "ESI eligible wage has no employee contribution"})
        if data.file_type in {"tds_24q", "TDS_24Q"} and record.tds is None:
            errors.append({"employee_id": record.employee_id, "field": "tds", "message": "TDS value missing"})
        rows.append([record.employee_id, record.gross_salary or 0, record.total_deductions or 0, record.net_salary or 0])
    file_path = _write_rows_file(
        os.path.join(settings.UPLOAD_DIR, "exports", "payroll", "statutory_validations"),
        f"{data.file_type}_{data.payroll_run_id or 'period'}_validation.csv",
        ["employee_id", "gross_salary", "total_deductions", "net_salary"],
        rows,
    )
    validation = StatutoryFileValidation(
        payroll_run_id=data.payroll_run_id,
        period_id=data.period_id,
        file_type=data.file_type,
        status="Failed" if errors else "Validated",
        total_rows=len(rows),
        error_count=len(errors),
        warning_count=0,
        output_file_url=_file_url_from_upload_path(file_path),
        validation_errors_json=errors,
        generated_by=current_user.id,
    )
    db.add(validation)
    _audit(db, data.payroll_run_id, "statutory_file_validated", current_user.id, f"{data.file_type}:errors={len(errors)}")
    db.commit()
    db.refresh(validation)
    return validation


@router.post("/statutory/templates/{template_type}", response_model=StatutoryTemplateFileSchema, status_code=201)
def generate_statutory_template(template_type: str, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    columns_by_type = {
        "pf_ecr": ["uan", "employee_name", "gross_wages", "epf_wages", "eps_wages", "edli_wages", "ee_share", "eps_share", "er_share"],
        "esi": ["ip_number", "employee_name", "days", "gross_wages", "employee_contribution", "employer_contribution"],
        "pt": ["employee_id", "employee_name", "state", "gross_salary", "pt_amount"],
        "tds_24q": ["pan", "employee_name", "gross_taxable_income", "deductions", "tds"],
        "form_16": ["pan", "employee_name", "financial_year", "taxable_income", "tax_deducted"],
    }
    headers = columns_by_type.get(template_type)
    if not headers:
        raise HTTPException(status_code=400, detail="Unsupported template type")
    file_path = _write_rows_file(
        os.path.join(settings.UPLOAD_DIR, "templates", "statutory"),
        f"{template_type}_template.csv",
        headers,
        [],
    )
    item = StatutoryTemplateFile(
        template_type=template_type,
        format_version="v1",
        file_url=_file_url_from_upload_path(file_path),
        generated_by=current_user.id,
    )
    db.add(item)
    _audit(db, None, "statutory_template_generated", current_user.id, template_type)
    db.commit()
    db.refresh(item)
    return item


@router.post("/runs/{run_id}/pre-run-checks", response_model=PayrollPreRunCheckSchema, status_code=201)
def add_pre_run_check(
    run_id: int,
    data: PayrollPreRunCheckCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    run = _get_payroll_run_or_404(db, run_id)
    check = PayrollPreRunCheck(payroll_run_id=run_id, **data.model_dump())
    db.add(check)
    _audit(db, run_id, "pre_run_check_added", current_user.id, f"{data.check_type}:{data.status}")
    db.commit()
    db.refresh(check)
    return check


@router.get("/runs/{run_id}/pre-run-checks", response_model=List[PayrollPreRunCheckSchema])
def list_pre_run_checks(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    return db.query(PayrollPreRunCheck).filter(PayrollPreRunCheck.payroll_run_id == run_id).order_by(PayrollPreRunCheck.id).all()


@router.post("/runs/{run_id}/manual-inputs", response_model=PayrollManualInputSchema, status_code=201)
def create_manual_input(
    run_id: int,
    data: PayrollManualInputCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    run = _get_payroll_run_or_404(db, run_id)
    _ensure_not_locked_period(db, run.month, run.year, "add payroll manual input")
    item = PayrollManualInput(payroll_run_id=run_id, created_by=current_user.id, **data.model_dump())
    db.add(item)
    _audit(db, run_id, "manual_input_created", current_user.id, f"{data.input_type}:{data.amount}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/runs/{run_id}/manual-inputs", response_model=List[PayrollManualInputSchema])
def list_manual_inputs(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    return db.query(PayrollManualInput).filter(PayrollManualInput.payroll_run_id == run_id).order_by(PayrollManualInput.id.desc()).all()


@router.put("/manual-inputs/{input_id}/review", response_model=PayrollManualInputSchema)
def review_manual_input(
    input_id: int,
    data: PayrollManualInputReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_approve")),
):
    item = db.query(PayrollManualInput).filter(PayrollManualInput.id == input_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Payroll manual input not found")
    action = data.action.lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    item.status = "Approved" if action == "approve" else "Rejected"
    item.approved_by = current_user.id
    item.approved_at = datetime.now(timezone.utc)
    item.remarks = data.remarks or item.remarks
    _audit(db, item.payroll_run_id, f"manual_input_{action}d", current_user.id, data.remarks)
    db.commit()
    db.refresh(item)
    return item


@router.post("/runs/{run_id}/unlock-requests", response_model=PayrollUnlockRequestSchema, status_code=201)
def create_unlock_request(
    run_id: int,
    data: PayrollUnlockRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    run = _get_payroll_run_or_404(db, run_id)
    try:
        crud_payroll.coerce_payroll_run_status(run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if run.status != crud_payroll.PAYROLL_RUN_STATUS_LOCKED:
        raise HTTPException(status_code=400, detail="Only locked payroll can be requested for unlock")
    request = PayrollUnlockRequest(payroll_run_id=run_id, reason=data.reason, requested_by=current_user.id)
    db.add(request)
    _audit(db, run_id, "unlock_requested", current_user.id, data.reason)
    db.commit()
    db.refresh(request)
    return request


@router.put("/unlock-requests/{request_id}/review", response_model=PayrollUnlockRequestSchema)
def review_unlock_request(
    request_id: int,
    data: PayrollUnlockReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_approve")),
):
    request = db.query(PayrollUnlockRequest).filter(PayrollUnlockRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Payroll unlock request not found")
    action = data.action.lower()
    request.reviewed_by = current_user.id
    request.reviewed_at = datetime.now(timezone.utc)
    request.review_remarks = data.remarks
    if action == "approve":
        request.status = "Approved"
        run = _get_payroll_run_or_404(db, request.payroll_run_id)
        crud_payroll.coerce_payroll_run_status(run)
        if run.status == crud_payroll.PAYROLL_RUN_STATUS_LOCKED:
            run.status = crud_payroll.PAYROLL_RUN_STATUS_CALCULATED
        _audit(
            db,
            request.payroll_run_id,
            "unlock_review_approved",
            current_user.id,
            "Payroll run unlocked for controlled correction. "
            f"Remarks: {data.remarks or ''}",
        )
    elif action == "reject":
        request.status = "Rejected"
    else:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    db.commit()
    db.refresh(request)
    return request


@router.get("/runs/{run_id}/records")
def get_payroll_records(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    records = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run_id).all()
    return [crud_payroll.build_payslip_payload(db, record) for record in records]


@router.post("/runs/{run_id}/payslip-publish", response_model=PayslipPublishBatchSchema, status_code=201)
def publish_payslips(
    run_id: int,
    data: PayslipPublishBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    run = _get_payroll_run_or_404(db, run_id)
    total = db.query(PayrollRecord).filter(PayrollRecord.payroll_run_id == run_id).count()
    batch = PayslipPublishBatch(
        payroll_run_id=run_id,
        status="Completed",
        total_payslips=total,
        published_count=total,
        email_dispatch_status=data.email_dispatch_status,
        output_file_url=data.output_file_url or f"/exports/payroll/{run_id}/payslips.zip",
        created_by=current_user.id,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    _audit(db, run_id, "payslips_published", current_user.id, f"{total} payslips")
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/payslip")
def get_payslip(
    month: int = Query(...),
    year: int = Query(...),
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    emp_id = employee_id
    if not emp_id:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        emp_id = current_user.employee.id
    elif not _can_view_other_payslips(current_user):
        if not current_user.employee or current_user.employee.id != emp_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this payslip")

    record = crud_payroll.get_payslip(db, emp_id, month, year)
    if not record:
        raise HTTPException(status_code=404, detail="Payslip not found for this period")
    return crud_payroll.build_payslip_payload(db, record)


@router.post("/payslip/{record_id}/pdf")
def generate_payslip_pdf(
    record_id: int,
    password_policy: str = Query("dob_or_aadhaar", pattern="^(none|dob_or_aadhaar|aadhaar_last4)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    record = db.query(PayrollRecord).filter(PayrollRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    run = record.payroll_run
    pdf_dir = os.path.join(settings.UPLOAD_DIR, "payslips", str(run.year), str(run.month))
    os.makedirs(pdf_dir, exist_ok=True)
    file_name = f"payslip_{record.employee_id}_{run.year}_{run.month}.pdf"
    file_path = os.path.join(pdf_dir, file_name)
    payload = crud_payroll.build_payslip_payload(db, record)
    employee_name = f"{record.employee.first_name} {record.employee.last_name}" if record.employee else str(record.employee_id)
    employee_code = record.employee.employee_id if record.employee else str(record.employee_id)
    sections = [
        ("Earnings", payload["earnings"]),
        ("Deductions", payload["deductions"]),
        ("Employer Contributions", payload["employer_contributions"]),
        ("Reimbursements", payload["reimbursements"]),
    ]
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(file_path, pagesize=A4)
        y = 800
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, "Payslip")
        y -= 28
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Employee: {employee_code} - {employee_name}")
        y -= 18
        c.drawString(50, y, f"Period: {run.month}/{run.year}")
        y -= 30
        for title, rows in sections:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y, title)
            y -= 16
            c.setFont("Helvetica", 10)
            for row in rows:
                c.drawString(60, y, row["component_name"])
                c.drawRightString(520, y, str(row["amount"]))
                y -= 14
            y -= 8
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"Net Salary: {record.net_salary}")
        c.save()
    except ModuleNotFoundError:
        lines = ["Payslip", f"Employee: {employee_code} - {employee_name}", f"Period: {run.month}/{run.year}", ""]
        for title, rows in sections:
            lines.append(title)
            lines.extend(f"{row['component_name']}: {row['amount']}" for row in rows)
            lines.append("")
        lines.append(f"Net Salary: {record.net_salary}")
        _write_basic_pdf(file_path, lines)
    protected = False
    password = _payslip_password_for_employee(record.employee, password_policy) if record.employee else None
    if password:
        try:
            from pypdf import PdfReader, PdfWriter

            protected_name = f"payslip_{record.employee_id}_{run.year}_{run.month}_protected.pdf"
            protected_path = os.path.join(pdf_dir, protected_name)
            reader = PdfReader(file_path)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt(password)
            with open(protected_path, "wb") as handle:
                writer.write(handle)
            file_name = protected_name
            file_path = protected_path
            protected = True
        except Exception as exc:
            _audit(db, run.id, "payslip_pdf_password_protection_skipped", current_user.id, str(exc))
    record.payslip_pdf_url = f"/uploads/payslips/{run.year}/{run.month}/{file_name}"
    record.payslip_generated_at = datetime.now(timezone.utc)
    _audit(db, run.id, "payslip_pdf_generated", current_user.id, f"record_id={record.id}")
    db.commit()
    return {"record_id": record.id, "payslip_pdf_url": record.payslip_pdf_url, "password_protected": protected}


@router.get("/payslip/{record_id}/pdf")
def download_payslip_pdf(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(PayrollRecord).filter(PayrollRecord.id == record_id).first()
    if not record or not record.payslip_pdf_url:
        raise HTTPException(status_code=404, detail="Payslip PDF not found")
    if not _can_view_other_payslips(current_user):
        if not current_user.employee or current_user.employee.id != record.employee_id:
            raise HTTPException(status_code=403, detail="Not authorized")
    file_path = os.path.join(settings.UPLOAD_DIR, record.payslip_pdf_url.replace("/uploads/", "").replace("/", os.sep))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Payslip PDF missing on disk")
    return FileResponse(file_path, media_type="application/pdf", filename=os.path.basename(file_path))


# ── Reimbursements ────────────────────────────────────────────────────────────

@router.get("/tax/regimes", response_model=List[TaxRegimeSchema])
def list_tax_regimes(
    financial_year: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(TaxRegime).filter(TaxRegime.is_active == True)
    if financial_year:
        query = query.filter(TaxRegime.financial_year == financial_year)
    return query.order_by(TaxRegime.financial_year.desc(), TaxRegime.regime_code).all()


@router.post("/tax/regimes", response_model=TaxRegimeSchema, status_code=201)
def create_tax_regime(data: TaxRegimeCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    regime = TaxRegime(**data.model_dump())
    db.add(regime)
    _audit(db, None, "tax_regime_created", current_user.id, f"{data.financial_year}:{data.regime_code}")
    db.commit()
    db.refresh(regime)
    return regime


@router.get("/tax/slabs", response_model=List[TaxSlabSchema])
def list_tax_slabs(tax_regime_id: int = Query(...), db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(TaxSlab).filter(TaxSlab.tax_regime_id == tax_regime_id).order_by(TaxSlab.sequence).all()


@router.post("/tax/slabs", response_model=TaxSlabSchema, status_code=201)
def create_tax_slab(data: TaxSlabCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    if not db.query(TaxRegime).filter(TaxRegime.id == data.tax_regime_id).first():
        raise HTTPException(status_code=404, detail="Tax regime not found")
    slab = TaxSlab(**data.model_dump())
    db.add(slab)
    db.commit()
    db.refresh(slab)
    return slab


@router.get("/tax/sections", response_model=List[TaxSectionSchema])
def list_tax_sections(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    return db.query(TaxSection).filter(TaxSection.is_active == True).order_by(TaxSection.section_code).all()


@router.post("/tax/sections", response_model=TaxSectionSchema, status_code=201)
def create_tax_section(data: TaxSectionCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    section = TaxSection(**data.model_dump())
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.get("/tax/section-limits", response_model=List[TaxSectionLimitSchema])
def list_tax_section_limits(
    financial_year: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    return db.query(TaxSectionLimit).filter(TaxSectionLimit.financial_year == financial_year).order_by(TaxSectionLimit.id.desc()).all()


@router.post("/tax/section-limits", response_model=TaxSectionLimitSchema, status_code=201)
def create_tax_section_limit(data: TaxSectionLimitCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    limit = TaxSectionLimit(**data.model_dump())
    db.add(limit)
    db.commit()
    db.refresh(limit)
    return limit


@router.post("/tax/elections", response_model=EmployeeTaxRegimeElectionSchema, status_code=201)
def elect_tax_regime(data: EmployeeTaxRegimeElectionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if data.employee_id and not _has_permission(current_user, "payroll_run"):
        if not current_user.employee or current_user.employee.id != data.employee_id:
            raise HTTPException(status_code=403, detail="Not authorized")
    election = db.query(EmployeeTaxRegimeElection).filter(
        EmployeeTaxRegimeElection.employee_id == data.employee_id,
        EmployeeTaxRegimeElection.financial_year == data.financial_year,
    ).first()
    if election and election.locked_at:
        raise HTTPException(status_code=400, detail="Tax regime election is locked")
    if not election:
        election = EmployeeTaxRegimeElection(employee_id=data.employee_id, financial_year=data.financial_year)
        db.add(election)
    election.tax_regime_id = data.tax_regime_id
    if data.lock:
        election.locked_by = current_user.id
        election.locked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(election)
    return election


@router.post("/tax/previous-employment", response_model=PreviousEmploymentTaxDetailSchema, status_code=201)
def create_previous_employment_tax_detail(
    data: PreviousEmploymentTaxDetailCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _has_permission(current_user, "payroll_run"):
        if not current_user.employee or current_user.employee.id != data.employee_id:
            raise HTTPException(status_code=403, detail="Not authorized")
    item = PreviousEmploymentTaxDetail(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/tax/worksheets/project", response_model=EmployeeTaxWorksheetSchema, status_code=201)
def project_tax_worksheet(data: TaxWorksheetProjectRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_view"))):
    regime_id = data.tax_regime_id
    if not regime_id:
        election = db.query(EmployeeTaxRegimeElection).filter(
            EmployeeTaxRegimeElection.employee_id == data.employee_id,
            EmployeeTaxRegimeElection.financial_year == data.financial_year,
        ).first()
        regime_id = election.tax_regime_id if election else None
    regime = db.query(TaxRegime).filter(TaxRegime.id == regime_id).first() if regime_id else None
    if not regime:
        regime = db.query(TaxRegime).filter(
            TaxRegime.financial_year == data.financial_year,
            TaxRegime.is_default == True,
            TaxRegime.is_active == True,
        ).first()
    if not regime:
        raise HTTPException(status_code=404, detail="Tax regime not found")

    previous = db.query(PreviousEmploymentTaxDetail).filter(
        PreviousEmploymentTaxDetail.employee_id == data.employee_id,
        PreviousEmploymentTaxDetail.financial_year == data.financial_year,
    ).all()
    previous_income = sum((item.taxable_income or Decimal("0")) for item in previous)
    previous_tds = sum((item.tds_deducted or Decimal("0")) for item in previous)
    gross = data.gross_taxable_income + previous_income
    total_deductions = data.exemptions + data.deductions + Decimal(regime.standard_deduction_amount or 0)
    taxable_income = max(Decimal("0"), gross - total_deductions)
    slabs = db.query(TaxSlab).filter(TaxSlab.tax_regime_id == regime.id).order_by(TaxSlab.sequence).all()
    base_tax = _calculate_tax_from_slabs(taxable_income, slabs)
    rebate, surcharge, cess, projected_tax = _tax_with_rebate_surcharge_and_cess(base_tax, taxable_income, regime)
    balance_tax = max(Decimal("0"), projected_tax - previous_tds - data.paid_tds).quantize(Decimal("0.01"))
    remaining_months = max(1, min(12, data.remaining_months))
    monthly_tds = (balance_tax / Decimal(remaining_months)).quantize(Decimal("0.01"))

    worksheet = EmployeeTaxWorksheet(
        employee_id=data.employee_id,
        financial_year=data.financial_year,
        tax_regime_id=regime.id,
        gross_taxable_income=data.gross_taxable_income,
        exemptions=data.exemptions,
        deductions=data.deductions,
        previous_employment_income=previous_income,
        previous_tds=previous_tds,
        projected_tax=projected_tax,
        monthly_tds=monthly_tds,
        paid_tds=data.paid_tds,
        balance_tax=balance_tax,
    )
    db.add(worksheet)
    db.flush()
    db.add(EmployeeTaxWorksheetLine(
        worksheet_id=worksheet.id,
        line_type="Taxable Income",
        description="Gross taxable income after exemptions, deductions, and previous employment",
        amount=gross,
        taxable_amount=taxable_income,
    ))
    db.add(EmployeeTaxWorksheetLine(
        worksheet_id=worksheet.id,
        line_type="Tax",
        description=f"Tax as per {regime.name}: base {base_tax}, rebate {rebate}, surcharge {surcharge}, cess {cess}",
        amount=projected_tax,
        taxable_amount=taxable_income,
    ))
    _audit(db, None, "tax_worksheet_projected", current_user.id, f"employee_id={data.employee_id}")
    db.commit()
    db.refresh(worksheet)
    return worksheet


@router.get("/tax/compare")
def compare_tax_regimes(
    employee_id: int = Query(...),
    financial_year: str = Query(...),
    gross_taxable_income: Decimal = Query(...),
    deductions: Decimal = Query(Decimal("0")),
    exemptions: Decimal = Query(Decimal("0")),
    paid_tds: Decimal = Query(Decimal("0")),
    remaining_months: int = Query(12),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    previous = db.query(PreviousEmploymentTaxDetail).filter(
        PreviousEmploymentTaxDetail.employee_id == employee_id,
        PreviousEmploymentTaxDetail.financial_year == financial_year,
    ).all()
    previous_income = sum((item.taxable_income or Decimal("0")) for item in previous)
    previous_tds = sum((item.tds_deducted or Decimal("0")) for item in previous)
    regimes = db.query(TaxRegime).filter(TaxRegime.financial_year == financial_year, TaxRegime.is_active == True).all()
    rows = []
    for regime in regimes:
        allowed_deductions = Decimal("0") if regime.regime_code.upper() == "NEW" else deductions
        allowed_exemptions = Decimal("0") if regime.regime_code.upper() == "NEW" else exemptions
        taxable_income = max(
            Decimal("0"),
            gross_taxable_income + previous_income - allowed_deductions - allowed_exemptions - Decimal(regime.standard_deduction_amount or 0),
        )
        slabs = db.query(TaxSlab).filter(TaxSlab.tax_regime_id == regime.id).order_by(TaxSlab.sequence).all()
        base_tax = _calculate_tax_from_slabs(taxable_income, slabs)
        rebate, surcharge, cess, projected_tax = _tax_with_rebate_surcharge_and_cess(base_tax, taxable_income, regime)
        balance_tax = max(Decimal("0"), projected_tax - previous_tds - paid_tds).quantize(Decimal("0.01"))
        rows.append({
            "tax_regime_id": regime.id,
            "regime_code": regime.regime_code,
            "regime_name": regime.name,
            "taxable_income": taxable_income,
            "base_tax": base_tax,
            "rebate": rebate,
            "surcharge": surcharge,
            "cess": cess,
            "projected_tax": projected_tax,
            "balance_tax": balance_tax,
            "monthly_tds": (balance_tax / Decimal(max(1, min(12, remaining_months)))).quantize(Decimal("0.01")),
        })
    rows.sort(key=lambda row: row["projected_tax"])
    return {"employee_id": employee_id, "financial_year": financial_year, "recommended_regime": rows[0] if rows else None, "regimes": rows}


@router.get("/tax/cycles", response_model=List[TaxDeclarationCycleSchema])
def list_tax_cycles(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(TaxDeclarationCycle).order_by(TaxDeclarationCycle.start_date.desc()).all()


@router.post("/tax/cycles", response_model=TaxDeclarationCycleSchema, status_code=201)
def create_tax_cycle(data: TaxDeclarationCycleCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    if data.end_date < data.start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be before start_date")
    cycle = TaxDeclarationCycle(**data.model_dump())
    db.add(cycle)
    _audit(db, None, "tax_cycle_created", current_user.id, data.financial_year)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.get("/tax/declarations", response_model=List[TaxDeclarationSchema])
def list_tax_declarations(
    cycle_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(TaxDeclaration)
    if cycle_id:
        query = query.filter(TaxDeclaration.cycle_id == cycle_id)
    if status:
        query = query.filter(TaxDeclaration.status == status)
    if _has_permission(current_user, "payroll_view") and (employee_id or current_user.is_superuser):
        if employee_id:
            query = query.filter(TaxDeclaration.employee_id == employee_id)
    else:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        query = query.filter(TaxDeclaration.employee_id == current_user.employee.id)
    return query.order_by(TaxDeclaration.id.desc()).all()


@router.post("/tax/declarations", response_model=TaxDeclarationSchema, status_code=201)
def create_tax_declaration(data: TaxDeclarationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cycle = db.query(TaxDeclarationCycle).filter(TaxDeclarationCycle.id == data.cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Tax declaration cycle not found")
    if cycle.status == "Locked":
        raise HTTPException(status_code=400, detail="Tax declaration cycle is locked")
    employee_id = data.employee_id
    if employee_id and not _has_permission(current_user, "payroll_run"):
        raise HTTPException(status_code=403, detail="Not authorized to submit for another employee")
    if not employee_id:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        employee_id = current_user.employee.id
    declaration = TaxDeclaration(
        cycle_id=data.cycle_id,
        employee_id=employee_id,
        section=data.section,
        declared_amount=data.declared_amount,
        description=data.description,
    )
    db.add(declaration)
    db.commit()
    db.refresh(declaration)
    return declaration


@router.put("/tax/declarations/{declaration_id}/review", response_model=TaxDeclarationSchema)
def review_tax_declaration(declaration_id: int, data: TaxDeclarationReview, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    declaration = db.query(TaxDeclaration).filter(TaxDeclaration.id == declaration_id).first()
    if not declaration:
        raise HTTPException(status_code=404, detail="Tax declaration not found")
    declaration.status = data.status
    if data.approved_amount is not None:
        declaration.approved_amount = data.approved_amount
    declaration.review_remarks = data.review_remarks
    declaration.reviewed_by = current_user.id
    declaration.reviewed_at = datetime.now(timezone.utc)
    _audit(db, None, "tax_declaration_reviewed", current_user.id, f"id={declaration_id}:{data.status}")
    db.commit()
    db.refresh(declaration)
    return declaration


@router.post("/tax/proofs", response_model=TaxDeclarationProofSchema, status_code=201)
def submit_tax_proof(data: TaxDeclarationProofCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    declaration = db.query(TaxDeclaration).filter(TaxDeclaration.id == data.declaration_id).first()
    if not declaration:
        raise HTTPException(status_code=404, detail="Tax declaration not found")
    if not _has_permission(current_user, "payroll_run"):
        if not current_user.employee or declaration.employee_id != current_user.employee.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    proof = TaxDeclarationProof(**data.model_dump())
    declaration.status = "Proof Submitted"
    db.add(proof)
    db.commit()
    db.refresh(proof)
    return proof


@router.put("/tax/proofs/{proof_id}/verify", response_model=TaxDeclarationProofSchema)
def verify_tax_proof(proof_id: int, data: TaxDeclarationProofReview, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("payroll_run"))):
    proof = db.query(TaxDeclarationProof).filter(TaxDeclarationProof.id == proof_id).first()
    if not proof:
        raise HTTPException(status_code=404, detail="Tax proof not found")
    proof.status = data.status
    proof.verified_by = current_user.id
    proof.verified_at = datetime.now(timezone.utc)
    proof.verification_remarks = data.verification_remarks
    if data.status == "Verified":
        proof.declaration.status = "Approved"
        proof.declaration.approved_amount = proof.declaration.declared_amount
    elif data.status == "Rejected":
        proof.declaration.status = "Rejected"
    _audit(db, None, "tax_proof_verified", current_user.id, f"id={proof_id}:{data.status}")
    db.commit()
    db.refresh(proof)
    return proof


@router.get("/tax/projection")
def tax_projection(cycle_id: int = Query(...), employee_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    emp_id = employee_id
    if emp_id and not _has_permission(current_user, "payroll_view"):
        raise HTTPException(status_code=403, detail="Not authorized")
    if not emp_id:
        if not current_user.employee:
            raise HTTPException(status_code=400, detail="No employee profile")
        emp_id = current_user.employee.id
    salary = db.query(EmployeeSalary).filter(EmployeeSalary.employee_id == emp_id, EmployeeSalary.is_active == True).first()
    annual_ctc = salary.ctc if salary else Decimal("0")
    declarations = db.query(TaxDeclaration).filter(TaxDeclaration.employee_id == emp_id, TaxDeclaration.cycle_id == cycle_id).all()
    declared = sum((item.declared_amount or Decimal("0")) for item in declarations)
    approved = sum((item.approved_amount or Decimal("0")) for item in declarations)
    cycle = db.query(TaxDeclarationCycle).filter(TaxDeclarationCycle.id == cycle_id).first()
    if cycle:
        approved += Decimal(
            db.query(func.coalesce(func.sum(EmployeeTaxDeclarationItem.approved_amount), 0))
            .join(EmployeeTaxDeclaration, EmployeeTaxDeclaration.id == EmployeeTaxDeclarationItem.declaration_id)
            .filter(
                EmployeeTaxDeclaration.employee_id == emp_id,
                EmployeeTaxDeclaration.financial_year == cycle.financial_year,
                EmployeeTaxDeclaration.status.in_(["approved", "partially_approved"]),
                EmployeeTaxDeclarationItem.status == "approved",
            )
            .scalar()
            or 0
        )
    taxable_income = max(Decimal("0"), annual_ctc - approved)
    projected_tds = taxable_income * Decimal("0.10") if taxable_income else Decimal("0")
    return {
        "employee_id": emp_id,
        "cycle_id": cycle_id,
        "annual_ctc": annual_ctc,
        "declared_amount": declared,
        "approved_amount": approved,
        "projected_taxable_income": taxable_income,
        "projected_tds": projected_tds,
    }


@router.post("/reimbursements", response_model=ReimbursementSchema, status_code=201)
def create_reimbursement(
    data: ReimbursementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.employee:
        raise HTTPException(status_code=400, detail="No employee profile")
    _ensure_not_locked_for_date(db, data.date, "create reimbursement")
    reimb = Reimbursement(employee_id=current_user.employee.id, **data.model_dump())
    db.add(reimb)
    db.flush()
    db.add(ReimbursementLedger(
        reimbursement_id=reimb.id,
        employee_id=reimb.employee_id,
        action="Submitted",
        amount=reimb.amount,
        status_to=reimb.status,
        actor_user_id=current_user.id,
        remarks=reimb.description,
    ))
    db.commit()
    db.refresh(reimb)
    return reimb


@router.get("/reimbursements", response_model=List[ReimbursementSchema])
def list_reimbursements(
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import and_
    q = db.query(Reimbursement)
    emp_id = employee_id or (current_user.employee.id if current_user.employee else None)
    if emp_id and not current_user.is_superuser:
        q = q.filter(Reimbursement.employee_id == emp_id)
    if status:
        q = q.filter(Reimbursement.status == status)
    return q.order_by(Reimbursement.id.desc()).all()


@router.put("/reimbursements/{reimbursement_id}/review", response_model=ReimbursementSchema)
def review_reimbursement(
    reimbursement_id: int,
    data: ReimbursementReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_approve")),
):
    reimbursement = db.query(Reimbursement).filter(Reimbursement.id == reimbursement_id).first()
    if not reimbursement:
        raise HTTPException(status_code=404, detail="Reimbursement not found")
    action = data.action.lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    old_status = reimbursement.status
    reimbursement.status = "Approved" if action == "approve" else "Rejected"
    reimbursement.approved_by = current_user.id if action == "approve" else None
    db.add(ReimbursementLedger(
        reimbursement_id=reimbursement.id,
        employee_id=reimbursement.employee_id,
        action=reimbursement.status,
        amount=reimbursement.amount,
        status_from=old_status,
        status_to=reimbursement.status,
        actor_user_id=current_user.id,
        remarks=data.remarks,
    ))
    db.commit()
    db.refresh(reimbursement)
    return reimbursement


@router.get("/reimbursements/{reimbursement_id}/ledger", response_model=List[ReimbursementLedgerSchema])
def get_reimbursement_ledger(
    reimbursement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    return db.query(ReimbursementLedger).filter(
        ReimbursementLedger.reimbursement_id == reimbursement_id
    ).order_by(ReimbursementLedger.id).all()


@router.post("/loans", response_model=EmployeeLoanSchema, status_code=201)
def create_employee_loan(
    data: EmployeeLoanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    interest_amount = (data.principal_amount * data.interest_rate / Decimal("100")).quantize(Decimal("0.01"))
    total_payable = data.principal_amount + interest_amount
    loan = EmployeeLoan(
        employee_id=data.employee_id,
        loan_type=data.loan_type,
        principal_amount=data.principal_amount,
        interest_rate=data.interest_rate,
        total_payable=total_payable,
        emi_amount=data.emi_amount,
        start_month=data.start_month,
        start_year=data.start_year,
        tenure_months=data.tenure_months,
        balance_amount=total_payable,
        approved_by=current_user.id,
        approved_at=datetime.now(timezone.utc),
        created_by=current_user.id,
    )
    db.add(loan)
    db.flush()
    remaining = total_payable
    for index in range(data.tenure_months):
        due_month, due_year = _month_add(data.start_month, data.start_year, index)
        due_amount = min(data.emi_amount, remaining)
        principal_component = min(data.principal_amount / Decimal(str(data.tenure_months)), due_amount).quantize(Decimal("0.01"))
        interest_component = max(Decimal("0"), due_amount - principal_component).quantize(Decimal("0.01"))
        db.add(EmployeeLoanInstallment(
            loan_id=loan.id,
            installment_number=index + 1,
            due_month=due_month,
            due_year=due_year,
            due_amount=due_amount,
            principal_component=principal_component,
            interest_component=interest_component,
        ))
        remaining -= due_amount
    db.add(EmployeeLoanLedger(
        loan_id=loan.id,
        employee_id=loan.employee_id,
        action="Loan Created",
        amount=total_payable,
        balance_after=total_payable,
        actor_user_id=current_user.id,
    ))
    db.commit()
    db.refresh(loan)
    return loan


@router.get("/loans", response_model=List[EmployeeLoanSchema])
def list_employee_loans(
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(EmployeeLoan)
    if employee_id:
        query = query.filter(EmployeeLoan.employee_id == employee_id)
    if status:
        query = query.filter(EmployeeLoan.status == status)
    return query.order_by(EmployeeLoan.id.desc()).limit(200).all()


@router.get("/loans/{loan_id}/installments", response_model=List[EmployeeLoanInstallmentSchema])
def list_loan_installments(
    loan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    return db.query(EmployeeLoanInstallment).filter(EmployeeLoanInstallment.loan_id == loan_id).order_by(EmployeeLoanInstallment.installment_number).all()


@router.get("/loans/{loan_id}/ledger", response_model=List[EmployeeLoanLedgerSchema])
def list_loan_ledger(
    loan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    return db.query(EmployeeLoanLedger).filter(EmployeeLoanLedger.loan_id == loan_id).order_by(EmployeeLoanLedger.id).all()


@router.post("/settlements", response_model=FullFinalSettlementSchema, status_code=201)
def create_full_final_settlement(
    data: FullFinalSettlementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    payable_lines = sum((line.amount for line in data.lines if line.line_type == "Payable"), Decimal("0"))
    recovery_lines = sum((line.amount for line in data.lines if line.line_type == "Recovery"), Decimal("0"))
    net_payable = (
        data.leave_encashment_amount
        + data.gratuity_amount
        + data.other_payables
        + payable_lines
        - data.notice_recovery_amount
        - data.loan_recovery_amount
        - data.other_recoveries
        - recovery_lines
    )
    settlement = FullFinalSettlement(
        employee_id=data.employee_id,
        exit_record_id=data.exit_record_id,
        settlement_date=data.settlement_date,
        leave_encashment_amount=data.leave_encashment_amount,
        notice_recovery_amount=data.notice_recovery_amount,
        gratuity_amount=data.gratuity_amount,
        loan_recovery_amount=data.loan_recovery_amount,
        other_payables=data.other_payables,
        other_recoveries=data.other_recoveries,
        net_payable=net_payable,
        settlement_letter_url=data.settlement_letter_url,
        prepared_by=current_user.id,
        remarks=data.remarks,
    )
    db.add(settlement)
    db.flush()
    for line in data.lines:
        db.add(FullFinalSettlementLine(settlement_id=settlement.id, **line.model_dump()))
    db.commit()
    db.refresh(settlement)
    return settlement


@router.get("/settlements", response_model=List[FullFinalSettlementSchema])
def list_full_final_settlements(
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view")),
):
    query = db.query(FullFinalSettlement)
    if employee_id:
        query = query.filter(FullFinalSettlement.employee_id == employee_id)
    if status:
        query = query.filter(FullFinalSettlement.status == status)
    return query.order_by(FullFinalSettlement.id.desc()).limit(200).all()


@router.put("/settlements/{settlement_id}/approve", response_model=FullFinalSettlementSchema)
def approve_full_final_settlement(
    settlement_id: int,
    remarks: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_approve")),
):
    settlement = db.query(FullFinalSettlement).filter(FullFinalSettlement.id == settlement_id).first()
    if not settlement:
        raise HTTPException(status_code=404, detail="Full and final settlement not found")
    settlement.status = "Approved"
    settlement.approved_by = current_user.id
    settlement.approved_at = datetime.now(timezone.utc)
    settlement.remarks = remarks or settlement.remarks
    db.commit()
    db.refresh(settlement)
    return settlement
