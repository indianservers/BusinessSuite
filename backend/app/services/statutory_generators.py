import csv
import io
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session
from app.models.employee import Employee
from app.models.payroll import (
    EmployeeStatutoryProfile,
    LWFSlab,
    PayrollRecord,
    PayrollStatutoryContributionLine,
    ProfessionalTaxSlab,
    TDS26ASReconciliation,
)
from app.models.statutory_compliance import PayrollLegalEntity


PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
TAN_RE = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
UAN_RE = re.compile(r"^[0-9]{12}$")
ESI_IP_RE = re.compile(r"^[A-Z0-9]{5,20}$")
PF_ESTABLISHMENT_RE = re.compile(r"^[A-Z0-9]{5,25}$")
ESI_EMPLOYER_RE = re.compile(r"^[0-9]{17}$")


EXPORT_SCHEMAS: dict[str, list[str]] = {
    "pf_ecr": [
        "UAN", "Member Name", "Gross Wages", "EPF Wages", "EPS Wages",
        "EDLI Wages", "EPF Contribution", "EPS Contribution",
        "EPF EPS Diff", "NCP Days", "Refund of Advances",
    ],
    "esi": ["IP Number", "IP Name", "No of Days", "Total Wages", "ESI Contribution"],
    "pt": ["Employee Name", "PAN", "Gross Salary", "PT Amount", "Period", "State", "Registration Number"],
    "lwf": ["Employee Name", "PAN", "Gross Salary", "Employee LWF", "Employer LWF", "Period", "State", "Registration Number"],
    "tds_24q": ["Employee PAN", "Employee Name", "Total TDS Deducted", "Total Income Paid", "Period From", "Period To", "TAN"],
    "tds_26q": ["Deductee PAN", "Deductee Name", "Section", "Payment Amount", "TDS Deducted", "Deduction Date", "TAN"],
}


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _error(row: int, field: str, code: str, message: str, severity: str = "error") -> dict[str, Any]:
    return {
        "row": row,
        "field": field,
        "code": code,
        "message": message,
        "error": message,
        "severity": severity,
    }


def _employee_name(emp: Employee) -> str:
    return " ".join(part for part in [emp.first_name, emp.last_name] if part).strip()


def _lines_for_run(db: Session, payroll_run_id: int, component: str):
    return (
        db.query(PayrollStatutoryContributionLine)
        .join(PayrollRecord, PayrollRecord.id == PayrollStatutoryContributionLine.payroll_record_id)
        .join(Employee, Employee.id == PayrollRecord.employee_id)
        .filter(
            PayrollRecord.payroll_run_id == payroll_run_id,
            PayrollStatutoryContributionLine.component == component,
        )
        .order_by(Employee.employee_id)
        .all()
    )


def _profile(db: Session, employee_id: int) -> EmployeeStatutoryProfile | None:
    return db.query(EmployeeStatutoryProfile).filter(EmployeeStatutoryProfile.employee_id == employee_id).first()


def _write_csv(header: list[str], rows: list[list[object]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue()


def _validate_employer(legal_entity: PayrollLegalEntity | None, export_type: str) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if not legal_entity:
        return [_error(1, "legal_entity", "EMPLOYER_LEGAL_ENTITY_MISSING", "Active/default employer legal entity is required")]
    pan = (legal_entity.pan or "").strip().upper()
    tan = (legal_entity.tan or "").strip().upper()
    if export_type in {"pf_ecr", "esi", "pt", "lwf", "tds_24q", "tds_26q"} and pan and not PAN_RE.match(pan):
        errors.append(_error(1, "employer_pan", "EMPLOYER_PAN_INVALID", "Employer PAN is invalid"))
    if export_type in {"tds_24q", "tds_26q"}:
        if not TAN_RE.match(tan):
            errors.append(_error(1, "tan", "EMPLOYER_TAN_INVALID", "Employer TAN is required and must be valid for TDS returns"))
    if export_type == "pf_ecr" and not PF_ESTABLISHMENT_RE.match((legal_entity.pf_establishment_code or "").strip().upper()):
        errors.append(_error(1, "pf_establishment_code", "EMPLOYER_PF_CODE_INVALID", "PF establishment code is required and must be alphanumeric"))
    if export_type == "esi" and not ESI_EMPLOYER_RE.match((legal_entity.esi_employer_code or "").strip()):
        errors.append(_error(1, "esi_employer_code", "EMPLOYER_ESI_CODE_INVALID", "ESI employer code must be 17 digits"))
    if export_type == "pt" and not (legal_entity.pt_registration_number or "").strip():
        errors.append(_error(1, "pt_registration_number", "EMPLOYER_PT_REGISTRATION_MISSING", "PT registration number is required"))
    if export_type == "lwf" and not (legal_entity.lwf_registration_number or "").strip():
        errors.append(_error(1, "lwf_registration_number", "EMPLOYER_LWF_REGISTRATION_MISSING", "LWF registration number is required"))
    return errors


def generate_pf_ecr(db: Session, payroll_run_id: int, legal_entity: PayrollLegalEntity | None = None) -> tuple[str, list[dict]]:
    errors: list[dict] = []
    errors.extend(_validate_employer(legal_entity, "pf_ecr"))
    rows: list[list[object]] = []
    for i, c in enumerate(_lines_for_run(db, payroll_run_id, "PF"), start=2):
        emp = c.payroll_record.employee if c.payroll_record else db.query(Employee).get(c.employee_id)
        statutory = _profile(db, emp.id) if emp else None
        uan = (statutory.uan if statutory and statutory.uan else getattr(emp, "uan_number", None) or "").strip()
        if not UAN_RE.match(uan):
            errors.append(_error(i, "UAN", "UAN_INVALID", f"Invalid UAN for {_employee_name(emp)}"))
        if not statutory or not statutory.pf_applicable:
            errors.append(_error(i, "PF Profile", "PF_PROFILE_MISSING", f"PF statutory profile missing or inactive for {_employee_name(emp)}"))
        if _money(c.employee_amount) <= 0 or _money(c.employer_amount) <= 0:
            errors.append(_error(i, "Contribution", "PF_CONTRIBUTION_MISSING", f"PF contribution missing for {_employee_name(emp)}"))
        epf_wages = min(float(c.wage_base or 0), 15000)
        eps_wages = min(epf_wages, 15000)
        epf_contrib = float(_money(c.employee_amount or Decimal(epf_wages) * Decimal("0.12")))
        eps_contrib = round(eps_wages * 0.0833, 2)
        rows.append([
            uan,
            _employee_name(emp),
            float(c.wage_base or 0),
            epf_wages,
            eps_wages,
            epf_wages,
            epf_contrib,
            eps_contrib,
            round(epf_contrib - eps_contrib, 2),
            0,
            0,
        ])
    return _write_csv(EXPORT_SCHEMAS["pf_ecr"], rows), errors


def generate_esi_return(db: Session, payroll_run_id: int, legal_entity: PayrollLegalEntity | None = None) -> tuple[str, list[dict]]:
    errors: list[dict] = []
    errors.extend(_validate_employer(legal_entity, "esi"))
    rows: list[list[object]] = []
    for i, c in enumerate(_lines_for_run(db, payroll_run_id, "ESI"), start=2):
        emp = c.payroll_record.employee if c.payroll_record else db.query(Employee).get(c.employee_id)
        statutory = _profile(db, emp.id) if emp else None
        wages = float(c.wage_base or 0)
        if wages > 21000:
            continue
        ip_number = (statutory.esi_ip_number if statutory and statutory.esi_ip_number else getattr(emp, "esic_number", None) or "").strip()
        if not ESI_IP_RE.match(ip_number):
            errors.append(_error(i, "IP Number", "ESI_IP_INVALID", f"Missing or invalid ESI IP number for {_employee_name(emp)}"))
        if not statutory or not statutory.esi_applicable:
            errors.append(_error(i, "ESI Profile", "ESI_PROFILE_MISSING", f"ESI statutory profile missing or inactive for {_employee_name(emp)}"))
        if _money(c.employee_amount) <= 0:
            errors.append(_error(i, "ESI Contribution", "ESI_CONTRIBUTION_MISSING", f"ESI contribution missing for {_employee_name(emp)}"))
        rows.append([ip_number, _employee_name(emp), int(c.payroll_record.paid_days or 0), wages, float(_money(c.employee_amount or Decimal(str(wages)) * Decimal("0.0075")))])
    return _write_csv(EXPORT_SCHEMAS["esi"], rows), errors


def generate_pt_challan(db: Session, payroll_run_id: int, state: str, legal_entity: PayrollLegalEntity | None = None) -> tuple[str, list[dict]]:
    errors: list[dict] = []
    errors.extend(_validate_employer(legal_entity, "pt"))
    rows: list[list[object]] = []
    records = db.query(PayrollRecord).join(Employee).filter(PayrollRecord.payroll_run_id == payroll_run_id).all()
    for i, record in enumerate(records, start=2):
        emp = record.employee
        gross = float(record.gross_salary or 0)
        slab = (
            db.query(ProfessionalTaxSlab)
            .filter(
                ProfessionalTaxSlab.state == state,
                ProfessionalTaxSlab.salary_from <= gross,
                ProfessionalTaxSlab.is_active.is_(True),
            )
            .filter((ProfessionalTaxSlab.salary_to.is_(None)) | (ProfessionalTaxSlab.salary_to >= gross))
            .order_by(ProfessionalTaxSlab.salary_from.desc())
            .first()
        )
        amount = float(slab.employee_amount if slab else record.professional_tax or 0)
        pan = (emp.pan_number or "").strip().upper()
        if not PAN_RE.match(pan):
            errors.append(_error(i, "PAN", "PAN_INVALID", f"Missing or invalid PAN for {_employee_name(emp)}"))
        if amount <= 0 and gross > 0:
            errors.append(_error(i, "PT Amount", "PT_AMOUNT_MISSING", f"Professional tax amount missing for {_employee_name(emp)}", "warning"))
        rows.append([_employee_name(emp), pan, gross, amount, f"{record.payroll_run.month}/{record.payroll_run.year}", state, (legal_entity.pt_registration_number if legal_entity else "")])
    return _write_csv(EXPORT_SCHEMAS["pt"], rows), errors


def generate_lwf_return(db: Session, payroll_run_id: int, state: str, legal_entity: PayrollLegalEntity | None = None) -> tuple[str, list[dict]]:
    errors: list[dict] = []
    errors.extend(_validate_employer(legal_entity, "lwf"))
    rows: list[list[object]] = []
    records = db.query(PayrollRecord).join(Employee).filter(PayrollRecord.payroll_run_id == payroll_run_id).all()
    for i, record in enumerate(records, start=2):
        emp = record.employee
        gross = _money(record.gross_salary)
        line = next((line for line in record.components if (line.component_name or "").lower().startswith("lwf")), None)
        statutory_line = (
            db.query(PayrollStatutoryContributionLine)
            .filter(PayrollStatutoryContributionLine.payroll_record_id == record.id, PayrollStatutoryContributionLine.component == "LWF")
            .first()
        )
        employee_amount = _money(statutory_line.employee_amount if statutory_line else line.amount if line else 0)
        employer_amount = _money(statutory_line.employer_amount if statutory_line else 0)
        slab = (
            db.query(LWFSlab)
            .filter(LWFSlab.state == state, LWFSlab.salary_from <= gross, LWFSlab.is_active.is_(True))
            .filter((LWFSlab.salary_to.is_(None)) | (LWFSlab.salary_to >= gross))
            .order_by(LWFSlab.salary_from.desc())
            .first()
        )
        if not slab and employee_amount <= 0:
            errors.append(_error(i, "LWF Slab", "LWF_SLAB_MISSING", f"LWF slab or contribution line missing for {_employee_name(emp)}"))
        pan = (emp.pan_number or "").strip().upper()
        if not PAN_RE.match(pan):
            errors.append(_error(i, "PAN", "PAN_INVALID", f"Missing or invalid PAN for {_employee_name(emp)}"))
        rows.append([_employee_name(emp), pan, gross, employee_amount, employer_amount, f"{record.payroll_run.month}/{record.payroll_run.year}", state, (legal_entity.lwf_registration_number if legal_entity else "")])
    return _write_csv(EXPORT_SCHEMAS["lwf"], rows), errors


def generate_tds_24q(db: Session, payroll_run_id: int, quarter: int, year: int, legal_entity: PayrollLegalEntity | None = None) -> tuple[str, list[dict]]:
    errors: list[dict] = []
    errors.extend(_validate_employer(legal_entity, "tds_24q"))
    rows: list[list[object]] = []
    records = db.query(PayrollRecord).join(Employee).filter(PayrollRecord.payroll_run_id == payroll_run_id).all()
    start_month = (quarter - 1) * 3 + 1
    period_from = date(year, start_month, 1).isoformat()
    period_to = date(year, start_month + 2, 28).isoformat()
    for i, record in enumerate(records, start=2):
        emp = record.employee
        pan = (emp.pan_number or "").strip().upper()
        if not PAN_RE.match(pan):
            errors.append(_error(i, "PAN", "PAN_INVALID", f"Invalid PAN for {_employee_name(emp)}"))
        if _money(record.gross_salary) <= 0:
            errors.append(_error(i, "Income", "TDS_INCOME_MISSING", f"Income paid is missing for {_employee_name(emp)}"))
        recon = db.query(TDS26ASReconciliation).filter(TDS26ASReconciliation.employee_id == emp.id).order_by(TDS26ASReconciliation.id.desc()).first()
        if recon and abs(_money(recon.reported_26as_tds) - _money(record.tds)) > Decimal("1.00"):
            errors.append(_error(i, "TDS Reconciliation", "TDS_RECON_MISMATCH", f"TDS reconciliation mismatch for {_employee_name(emp)}"))
        rows.append([pan, _employee_name(emp), float(record.tds or 0), float(record.gross_salary or 0), period_from, period_to, (legal_entity.tan if legal_entity else "")])
    return _write_csv(EXPORT_SCHEMAS["tds_24q"], rows), errors


def generate_tds_26q(db: Session, payroll_run_id: int, quarter: int, year: int, legal_entity: PayrollLegalEntity | None = None) -> tuple[str, list[dict]]:
    errors: list[dict] = []
    errors.extend(_validate_employer(legal_entity, "tds_26q"))
    rows: list[list[object]] = []
    records = db.query(PayrollRecord).join(Employee).filter(PayrollRecord.payroll_run_id == payroll_run_id, PayrollRecord.tds > 0).all()
    deduction_date = date(year, min(quarter * 3, 12), 28).isoformat()
    for i, record in enumerate(records, start=2):
        emp = record.employee
        pan = (emp.pan_number or "").strip().upper()
        if not PAN_RE.match(pan):
            errors.append(_error(i, "PAN", "PAN_INVALID", f"Invalid deductee PAN for {_employee_name(emp)}"))
        rows.append([pan, _employee_name(emp), "194J/Other non-salary", float(record.gross_salary or 0), float(record.tds or 0), deduction_date, (legal_entity.tan if legal_entity else "")])
    return _write_csv(EXPORT_SCHEMAS["tds_26q"], rows), errors
