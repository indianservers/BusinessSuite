from __future__ import annotations
from app.core.storage import persist_file, upload_exists, FileResponse

import csv
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import RequirePermission, get_db
from app.models.employee import Employee
from app.models.payroll import (
    EmployeeStatutoryProfile,
    ESIRule,
    PFRule,
    PayrollRecord,
    PayrollRun,
    PayrollRunAuditLog,
    StatutoryExport,
)
from app.models.user import User
from app.schemas.payroll import StatutoryExportGenerateRequest, StatutoryExportSchema


router = APIRouter(prefix="/hrms/compliance", tags=["HRMS Compliance Exports"])


def _current_company_id(user: User) -> int | None:
    if user.employee and user.employee.branch:
        return user.employee.branch.company_id
    return None


def _get_scoped_run(db: Session, payroll_run_id: int, user: User) -> PayrollRun:
    run = db.query(PayrollRun).filter(PayrollRun.id == payroll_run_id, PayrollRun.deleted_at.is_(None)).first()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    if not user.is_superuser:
        company_id = _current_company_id(user)
        if not company_id or run.company_id != company_id:
            raise HTTPException(status_code=404, detail="Payroll run not found")
    return run


def _audit(db: Session, run_id: int, action: str, actor_id: int, details: str) -> None:
    db.add(PayrollRunAuditLog(payroll_run_id=run_id, action=action, actor_user_id=actor_id, details=details))


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_rupee(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown employee"
    return " ".join(part for part in [employee.first_name, employee.middle_name, employee.last_name] if part).strip()


def _statutory_profile(db: Session, employee_id: int) -> EmployeeStatutoryProfile | None:
    return db.query(EmployeeStatutoryProfile).filter(EmployeeStatutoryProfile.employee_id == employee_id).first()


def _pf_rule(db: Session, run: PayrollRun) -> PFRule | None:
    basis = run.pay_period_end or run.run_date or datetime(run.year, run.month, 1).date()
    return (
        db.query(PFRule)
        .filter(PFRule.is_active.is_(True), PFRule.effective_from <= basis)
        .filter((PFRule.effective_to.is_(None)) | (PFRule.effective_to >= basis))
        .order_by(PFRule.effective_from.desc())
        .first()
    )


def _esi_rule(db: Session, run: PayrollRun) -> ESIRule | None:
    basis = run.pay_period_end or run.run_date or datetime(run.year, run.month, 1).date()
    return (
        db.query(ESIRule)
        .filter(ESIRule.is_active.is_(True), ESIRule.effective_from <= basis)
        .filter((ESIRule.effective_to.is_(None)) | (ESIRule.effective_to >= basis))
        .order_by(ESIRule.effective_from.desc())
        .first()
    )


def _records(db: Session, run: PayrollRun) -> list[PayrollRecord]:
    return (
        db.query(PayrollRecord)
        .filter(PayrollRecord.payroll_run_id == run.id)
        .order_by(PayrollRecord.employee_id)
        .all()
    )


def _export_dir(run: PayrollRun) -> str:
    path = os.path.join(settings.UPLOAD_DIR, "exports", "statutory", str(run.id))
    os.makedirs(path, exist_ok=True)
    return path


def _file_url(file_path: str) -> str:
    persist_file(file_path)
    rel = os.path.relpath(file_path, settings.UPLOAD_DIR).replace(os.sep, "/")
    return f"/uploads/{rel}"


def _pf_preview(db: Session, run: PayrollRun) -> dict[str, Any]:
    rule = _pf_rule(db, run)
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    total = Decimal("0.00")
    if not rule:
        errors.append("PF rule is not configured for this payroll period")
    wage_ceiling = _money(rule.wage_ceiling if rule else 15000)
    employee_rate = _money(rule.employee_rate if rule else 12) / Decimal("100")
    employer_rate = _money(rule.employer_rate if rule else 12) / Decimal("100")
    eps_rate = _money(rule.eps_rate if rule else Decimal("8.33")) / Decimal("100")
    for index, record in enumerate(_records(db, run), start=1):
        employee = record.employee or db.query(Employee).filter(Employee.id == record.employee_id).first()
        profile = _statutory_profile(db, record.employee_id)
        name = _employee_name(employee)
        uan = ((profile.uan if profile and profile.uan else employee.uan_number if employee else "") or "").strip()
        gross_wages = _money(record.gross_salary)
        wage_base = _money(record.basic or record.gross_salary)
        epf_wages = min(wage_base, wage_ceiling)
        eps_wages = epf_wages if not profile or profile.pension_applicable else Decimal("0.00")
        edli_wages = epf_wages
        employee_pf = _money(record.pf_employee) if record.pf_employee else _round_rupee(epf_wages * employee_rate)
        employer_total = _money(record.pf_employer) if record.pf_employer else _round_rupee(epf_wages * employer_rate)
        eps_contribution = min(_round_rupee(eps_wages * eps_rate), employer_total)
        employer_pf = employer_total - eps_contribution
        row_errors: list[str] = []
        if not profile:
            row_errors.append("PF eligibility profile is missing")
        elif not profile.pf_applicable:
            row_errors.append("Employee is not marked PF eligible")
        if not uan or len(uan) != 12 or not uan.isdigit():
            row_errors.append("UAN is missing or invalid")
        if epf_wages <= 0:
            row_errors.append("PF wage base is missing")
        if employee_pf <= 0 or employer_total <= 0:
            row_errors.append("PF contribution amount is missing")
        errors.extend([f"{name}: {error}" for error in row_errors])
        if not row_errors:
            total += employee_pf + employer_total
        rows.append(
            {
                "row": index,
                "uan": uan,
                "member_name": name,
                "gross_wages": gross_wages,
                "epf_wages": epf_wages,
                "eps_wages": eps_wages,
                "edli_wages": edli_wages,
                "employee_pf_contribution": employee_pf,
                "employer_pf_contribution": employer_pf,
                "eps_contribution": eps_contribution,
                "ncp_days": _money(record.lop_days),
                "refunds": Decimal("0.00"),
                "validation_errors": row_errors,
            }
        )
    return {
        "payroll_run_id": run.id,
        "export_type": "pf_ecr",
        "rule": rule.name if rule else None,
        "total_employees": sum(1 for row in rows if not row["validation_errors"]),
        "total_amount": total,
        "validation_errors": errors,
        "rows": rows,
    }


def _esi_preview(db: Session, run: PayrollRun) -> dict[str, Any]:
    rule = _esi_rule(db, run)
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    total = Decimal("0.00")
    if not rule:
        errors.append("ESI rule is not configured for this payroll period")
    threshold = _money(rule.wage_threshold if rule else 21000)
    employee_rate = _money(rule.employee_rate if rule else Decimal("0.75")) / Decimal("100")
    employer_rate = _money(rule.employer_rate if rule else Decimal("3.25")) / Decimal("100")
    for index, record in enumerate(_records(db, run), start=1):
        employee = record.employee or db.query(Employee).filter(Employee.id == record.employee_id).first()
        profile = _statutory_profile(db, record.employee_id)
        name = _employee_name(employee)
        gross_wages = _money(record.gross_salary)
        if gross_wages > threshold and not (profile and profile.esi_applicable):
            continue
        esic_number = ((profile.esi_ip_number if profile and profile.esi_ip_number else employee.esic_number if employee else "") or "").strip()
        employee_esi = _money(record.esi_employee) if record.esi_employee else _round_rupee(gross_wages * employee_rate)
        employer_esi = _money(record.esi_employer) if record.esi_employer else _round_rupee(gross_wages * employer_rate)
        row_errors: list[str] = []
        if not profile:
            row_errors.append("ESI eligibility profile is missing")
        elif not profile.esi_applicable:
            row_errors.append("Employee is not marked ESI eligible")
        if not esic_number:
            row_errors.append("ESIC number is missing")
        if gross_wages <= 0:
            row_errors.append("ESI wage base is missing")
        if employee_esi <= 0 or employer_esi <= 0:
            row_errors.append("ESI contribution amount is missing")
        errors.extend([f"{name}: {error}" for error in row_errors])
        if not row_errors:
            total += employee_esi + employer_esi
        rows.append(
            {
                "row": index,
                "esic_number": esic_number,
                "employee_name": name,
                "gross_wages": gross_wages,
                "employee_esi": employee_esi,
                "employer_esi": employer_esi,
                "payable_days": _money(record.paid_days),
                "validation_errors": row_errors,
            }
        )
    return {
        "payroll_run_id": run.id,
        "export_type": "esi_challan",
        "rule": rule.name if rule else None,
        "total_employees": sum(1 for row in rows if not row["validation_errors"]),
        "total_amount": total,
        "validation_errors": errors,
        "rows": rows,
    }


def _write_csv(file_path: str, headers: list[str], rows: list[list[Any]]) -> None:
    with open(file_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    persist_file(file_path)


def _create_export(db: Session, run: PayrollRun, export_type: str, rows: list[dict[str, Any]], total: Decimal, file_path: str, user: User) -> StatutoryExport:
    item = StatutoryExport(
        organization_id=run.company_id,
        payroll_run_id=run.id,
        export_type=export_type,
        file_path=_file_url(file_path),
        total_employees=len(rows),
        total_amount=total,
        generated_by=user.id,
        download_count=0,
    )
    db.add(item)
    _audit(db, run.id, f"{export_type}_generated", user.id, f"amount={total}:rows={len(rows)}")
    db.commit()
    db.refresh(item)
    return item


@router.get("/pf-ecr/preview")
def preview_pf_ecr(
    payrollRunId: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view", "payroll_run")),
):
    run = _get_scoped_run(db, payrollRunId, current_user)
    return _pf_preview(db, run)


@router.post("/pf-ecr/generate", response_model=StatutoryExportSchema, status_code=201)
def generate_pf_ecr(
    data: StatutoryExportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    run = _get_scoped_run(db, data.payroll_run_id, current_user)
    preview = _pf_preview(db, run)
    if preview["validation_errors"]:
        raise HTTPException(status_code=400, detail={"message": "PF ECR validation failed", "validation_errors": preview["validation_errors"]})
    file_path = os.path.join(_export_dir(run), f"pf_ecr_{run.year}_{run.month}_{run.id}.csv")
    headers = ["UAN", "Member Name", "Gross Wages", "EPF Wages", "EPS Wages", "EDLI Wages", "Employee PF", "Employer PF", "EPS", "NCP Days", "Refunds"]
    _write_csv(
        file_path,
        headers,
        [[row["uan"], row["member_name"], row["gross_wages"], row["epf_wages"], row["eps_wages"], row["edli_wages"], row["employee_pf_contribution"], row["employer_pf_contribution"], row["eps_contribution"], row["ncp_days"], row["refunds"]] for row in preview["rows"]],
    )
    return _create_export(db, run, "pf_ecr", preview["rows"], preview["total_amount"], file_path, current_user)


@router.get("/esi/preview")
def preview_esi(
    payrollRunId: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view", "payroll_run")),
):
    run = _get_scoped_run(db, payrollRunId, current_user)
    return _esi_preview(db, run)


@router.post("/esi/generate", response_model=StatutoryExportSchema, status_code=201)
def generate_esi(
    data: StatutoryExportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    run = _get_scoped_run(db, data.payroll_run_id, current_user)
    preview = _esi_preview(db, run)
    if preview["validation_errors"]:
        raise HTTPException(status_code=400, detail={"message": "ESI challan validation failed", "validation_errors": preview["validation_errors"]})
    file_path = os.path.join(_export_dir(run), f"esi_challan_{run.year}_{run.month}_{run.id}.csv")
    headers = ["ESIC Number", "Employee Name", "Gross Wages", "Employee ESI", "Employer ESI", "Payable Days"]
    _write_csv(
        file_path,
        headers,
        [[row["esic_number"], row["employee_name"], row["gross_wages"], row["employee_esi"], row["employer_esi"], row["payable_days"]] for row in preview["rows"]],
    )
    return _create_export(db, run, "esi_challan", preview["rows"], preview["total_amount"], file_path, current_user)


@router.get("/exports/{export_id}/download")
def download_export(
    export_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view", "payroll_run")),
):
    item = db.query(StatutoryExport).filter(StatutoryExport.id == export_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Statutory export not found")
    _get_scoped_run(db, item.payroll_run_id, current_user)
    if not item.file_path.startswith("/uploads/"):
        raise HTTPException(status_code=404, detail="Statutory export file not found")
    file_path = os.path.join(settings.UPLOAD_DIR, item.file_path.replace("/uploads/", "", 1).replace("/", os.sep))
    if not upload_exists(file_path):
        raise HTTPException(status_code=404, detail="Statutory export file missing on disk")
    item.downloaded_at = datetime.now(timezone.utc)
    item.download_count = (item.download_count or 0) + 1
    db.commit()
    return FileResponse(file_path, media_type="text/csv", filename=os.path.basename(file_path))
