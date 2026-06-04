from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.deps import RequirePermission, get_current_user, get_db
from app.models.company import Company
from app.models.employee import Employee
from app.models.payroll import EmployeeTaxDeclaration, EmployeeTaxDeclarationItem, PayrollRecord, PayrollRun
from app.models.statutory_compliance import Form16Record, PayrollLegalEntity
from app.models.user import User


router = APIRouter(prefix="/hrms/form16", tags=["HRMS Form 16"])


class Form16GenerateRequest(BaseModel):
    financialYear: str = Field(..., min_length=7, max_length=20)
    employeeIds: list[int] | None = None


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _has_permission(user: User, permission: str) -> bool:
    if user.is_superuser:
        return True
    return permission in {p.name for p in (user.role.permissions if user.role else [])}


def _can_manage(user: User) -> bool:
    return _has_permission(user, "payroll_run") or _has_permission(user, "payroll_view") or _has_permission(user, "payroll_approve")


def _current_company_id(user: User) -> int | None:
    if user.employee and user.employee.branch:
        return user.employee.branch.company_id
    return None


def _employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown employee"
    return " ".join(part for part in [employee.first_name, employee.middle_name, employee.last_name] if part).strip()


def _fy_window(financial_year: str) -> tuple[date, date]:
    start_text = financial_year.split("-")[0]
    if len(start_text) != 4 or not start_text.isdigit():
        raise HTTPException(status_code=400, detail="Financial year must be formatted as YYYY-YY, for example 2025-26")
    start_year = int(start_text)
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def _payroll_records(db: Session, financial_year: str, employee_id: int, company_id: int | None) -> list[PayrollRecord]:
    from sqlalchemy import tuple_

    start, end = _fy_window(financial_year)
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    query = (
        db.query(PayrollRecord)
        .join(PayrollRun, PayrollRun.id == PayrollRecord.payroll_run_id)
        .filter(PayrollRecord.employee_id == employee_id, PayrollRun.deleted_at.is_(None))
        .filter(tuple_(PayrollRun.year, PayrollRun.month).in_(months))
    )
    if company_id:
        query = query.filter(PayrollRun.company_id == company_id)
    return query.order_by(PayrollRun.year, PayrollRun.month).all()


def _approved_declarations(db: Session, financial_year: str, employee_id: int) -> tuple[Decimal, list[dict[str, Any]]]:
    rows = (
        db.query(EmployeeTaxDeclarationItem, EmployeeTaxDeclaration)
        .join(EmployeeTaxDeclaration, EmployeeTaxDeclaration.id == EmployeeTaxDeclarationItem.declaration_id)
        .filter(
            EmployeeTaxDeclaration.employee_id == employee_id,
            EmployeeTaxDeclaration.financial_year == financial_year,
            EmployeeTaxDeclaration.status.in_(["approved", "partially_approved"]),
            EmployeeTaxDeclarationItem.status == "approved",
        )
        .all()
    )
    total = Decimal("0.00")
    details = []
    for item, _declaration in rows:
        amount = _money(item.approved_amount)
        total += amount
        details.append({
            "section": item.category.section if item.category else "",
            "name": item.category.name if item.category else "Approved deduction",
            "amount": amount,
        })
    return total, details


def _company_name(db: Session, company_id: int | None) -> str:
    legal_entity = (
        db.query(PayrollLegalEntity)
        .filter(PayrollLegalEntity.company_id == company_id if company_id else PayrollLegalEntity.is_default == True, PayrollLegalEntity.is_active == True)
        .order_by(PayrollLegalEntity.is_default.desc(), PayrollLegalEntity.id.desc())
        .first()
    )
    if legal_entity:
        return legal_entity.legal_name
    company = db.query(Company).filter(Company.id == company_id).first() if company_id else None
    return (company.legal_name or company.name) if company else "Company"


def _form16_dir(employee_id: int, financial_year: str) -> str:
    path = os.path.join(settings.UPLOAD_DIR, "form16", str(employee_id), financial_year.replace("/", "-"))
    os.makedirs(path, exist_ok=True)
    return path


def _file_url(path: str) -> str:
    rel = os.path.relpath(path, settings.UPLOAD_DIR).replace(os.sep, "/")
    return f"/uploads/{rel}"


def _disk_path(file_url: str | None) -> str | None:
    if not file_url or not file_url.startswith("/uploads/"):
        return None
    path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, file_url.replace("/uploads/", "", 1).replace("/", os.sep)))
    root = os.path.abspath(settings.UPLOAD_DIR)
    if not path.startswith(root):
        return None
    return path


def _compute_form16(db: Session, employee: Employee, financial_year: str, company_id: int | None) -> dict[str, Any]:
    records = _payroll_records(db, financial_year, employee.id, company_id)
    gross_salary = sum((_money(record.gross_salary) for record in records), Decimal("0.00"))
    total_deductions = sum((_money(record.total_deductions) for record in records), Decimal("0.00"))
    tax_deducted = sum((_money(record.tds) for record in records), Decimal("0.00"))
    approved_deductions, declaration_details = _approved_declarations(db, financial_year, employee.id)
    taxable_income = max(gross_salary - approved_deductions, Decimal("0.00"))
    monthwise = [
        {
            "month": f"{record.payroll_run.month:02d}/{record.payroll_run.year}" if record.payroll_run else "",
            "gross": _money(record.gross_salary),
            "tds": _money(record.tds),
        }
        for record in records
    ]
    return {
        "gross_salary": gross_salary,
        "payroll_deductions": total_deductions,
        "approved_deductions": approved_deductions,
        "taxable_income": taxable_income,
        "tax_deducted": tax_deducted,
        "monthwise_tds": monthwise,
        "declarations": declaration_details,
    }


def _write_part_b_pdf(path: str, employee: Employee, company_name: str, financial_year: str, computation: dict[str, Any]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    rows = [
        ["Gross salary", f"INR {computation['gross_salary']}"],
        ["Approved Chapter VI-A / exemption deductions", f"INR {computation['approved_deductions']}"],
        ["Taxable salary/income", f"INR {computation['taxable_income']}"],
        ["Total tax deducted at source", f"INR {computation['tax_deducted']}"],
    ]
    month_rows = [["Month", "Gross Salary", "TDS Deducted"]] + [[row["month"], f"INR {row['gross']}", f"INR {row['tds']}"] for row in computation["monthwise_tds"]]
    declaration_rows = [["Section", "Particular", "Approved Amount"]] + [[row["section"], row["name"], f"INR {row['amount']}"] for row in computation["declarations"]]
    if len(declaration_rows) == 1:
        declaration_rows.append(["-", "No approved declarations/proofs", "INR 0.00"])
    story = [
        Paragraph("Form 16 - Part B", styles["Title"]),
        Paragraph(company_name, styles["Heading2"]),
        Paragraph(f"Financial Year: {financial_year}", styles["Normal"]),
        Paragraph(f"Employee: {_employee_name(employee)} ({employee.employee_id})", styles["Normal"]),
        Paragraph(f"PAN: {employee.pan_number or '-'}", styles["Normal"]),
        Spacer(1, 0.2 * inch),
        Paragraph("Salary and Tax Computation", styles["Heading3"]),
        Table(rows, colWidths=[3.6 * inch, 2.2 * inch]),
        Spacer(1, 0.2 * inch),
        Paragraph("Month-wise Salary and TDS", styles["Heading3"]),
        Table(month_rows, repeatRows=1),
        Spacer(1, 0.2 * inch),
        Paragraph("Approved Investment Declarations / Exemptions", styles["Heading3"]),
        Table(declaration_rows, repeatRows=1),
        Spacer(1, 0.35 * inch),
        Paragraph("This certificate has been generated from payroll records and approved tax proofs.", styles["Italic"]),
        Paragraph("Digital signature status: pending external signing connector.", styles["Italic"]),
    ]
    for item in story:
        if isinstance(item, Table):
            item.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
    doc.build(story)


def _combine_pdfs(part_a_url: str | None, part_b_url: str, employee_id: int, financial_year: str) -> str:
    part_b_path = _disk_path(part_b_url)
    if not part_b_path or not os.path.exists(part_b_path):
        return part_b_url
    part_a_path = _disk_path(part_a_url)
    if not part_a_path or not os.path.exists(part_a_path):
        return part_b_url
    try:
        from pypdf import PdfMerger
    except ImportError:
        try:
            from PyPDF2 import PdfMerger
        except ImportError:
            return part_b_url

    out_path = os.path.join(_form16_dir(employee_id, financial_year), "form16_combined.pdf")
    merger = PdfMerger()
    merger.append(part_a_path)
    merger.append(part_b_path)
    with open(out_path, "wb") as handle:
        merger.write(handle)
    merger.close()
    return _file_url(out_path)


def _serialize(record: Form16Record, include_employee: bool = True) -> dict[str, Any]:
    return {
        "id": record.id,
        "organizationId": record.organization_id,
        "employeeId": record.employee_id,
        "employee": {
            "id": record.employee.id,
            "employeeId": record.employee.employee_id,
            "name": _employee_name(record.employee),
            "pan": record.employee.pan_number,
        } if include_employee and record.employee else None,
        "financialYear": record.financial_year,
        "partAFilePath": record.part_a_file_path,
        "partBFilePath": record.part_b_file_path,
        "combinedFilePath": record.combined_file_path,
        "status": record.status,
        "taxableIncome": record.taxable_income,
        "taxDeducted": record.tax_deducted,
        "digitalSignatureStatus": "pending_signature" if record.status == "generated" else "not_configured",
        "digitalSignatureProvider": None,
        "signatureHookStatus": "connector_not_configured",
        "generatedBy": record.generated_by,
        "generatedAt": record.generated_at,
        "publishedAt": record.published_at,
    }


def _load_record(db: Session, record_id: int) -> Form16Record:
    record = db.query(Form16Record).options(joinedload(Form16Record.employee)).filter(Form16Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Form 16 record not found")
    return record


def _enforce_access(record: Form16Record, user: User, manage_required: bool = False) -> None:
    if _can_manage(user):
        if not user.is_superuser:
            company_id = _current_company_id(user)
            if not company_id or record.organization_id != company_id:
                raise HTTPException(status_code=404, detail="Form 16 record not found")
        return
    if manage_required:
        raise HTTPException(status_code=403, detail="Payroll permission required")
    if not user.employee or record.employee_id != user.employee.id or record.status != "published":
        raise HTTPException(status_code=403, detail="Employees can access only their published Form 16")


@router.get("")
def list_form16(
    financialYear: str = Query(...),
    employeeId: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Form16Record).options(joinedload(Form16Record.employee)).filter(Form16Record.financial_year == financialYear)
    if _can_manage(current_user):
        if employeeId:
            query = query.filter(Form16Record.employee_id == employeeId)
        if not current_user.is_superuser:
            company_id = _current_company_id(current_user)
            if company_id:
                query = query.filter(Form16Record.organization_id == company_id)
    else:
        if not current_user.employee:
            raise HTTPException(status_code=403, detail="No employee profile")
        query = query.filter(Form16Record.employee_id == current_user.employee.id, Form16Record.status == "published")
    return [_serialize(record) for record in query.order_by(Form16Record.id.desc()).all()]


@router.post("/generate")
def generate_form16(
    payload: Form16GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    company_id = None if current_user.is_superuser else _current_company_id(current_user)
    if not current_user.is_superuser and not company_id:
        raise HTTPException(status_code=403, detail="Company scope is required")
    employee_query = db.query(Employee).filter(Employee.deleted_at.is_(None))
    if payload.employeeIds:
        employee_query = employee_query.filter(Employee.id.in_(payload.employeeIds))
    else:
        employee_ids = {record.employee_id for record in _payroll_records_for_fy(db, payload.financialYear, company_id)}
        employee_query = employee_query.filter(Employee.id.in_(employee_ids))
    records: list[Form16Record] = []
    for employee in employee_query.all():
        computation = _compute_form16(db, employee, payload.financialYear, company_id)
        if computation["gross_salary"] <= 0 and computation["tax_deducted"] <= 0:
            continue
        out_dir = _form16_dir(employee.id, payload.financialYear)
        part_b_path = os.path.join(out_dir, "form16_part_b.pdf")
        _write_part_b_pdf(part_b_path, employee, _company_name(db, company_id), payload.financialYear, computation)
        record = (
            db.query(Form16Record)
            .filter(Form16Record.employee_id == employee.id, Form16Record.financial_year == payload.financialYear, Form16Record.organization_id == company_id)
            .first()
        )
        if not record:
            record = Form16Record(employee_id=employee.id, financial_year=payload.financialYear, organization_id=company_id)
            db.add(record)
        record.part_b_file_path = _file_url(part_b_path)
        record.combined_file_path = _combine_pdfs(record.part_a_file_path, record.part_b_file_path, employee.id, payload.financialYear)
        record.taxable_income = computation["taxable_income"]
        record.tax_deducted = computation["tax_deducted"]
        record.status = "generated"
        record.generated_by = current_user.id
        record.generated_at = datetime.now(timezone.utc)
        records.append(record)
    db.commit()
    for record in records:
        db.refresh(record)
    return [_serialize(record) for record in records]


def _payroll_records_for_fy(db: Session, financial_year: str, company_id: int | None) -> list[PayrollRecord]:
    start, end = _fy_window(financial_year)
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    from sqlalchemy import tuple_

    query = db.query(PayrollRecord).join(PayrollRun, PayrollRun.id == PayrollRecord.payroll_run_id).filter(tuple_(PayrollRun.year, PayrollRun.month).in_(months))
    if company_id:
        query = query.filter(PayrollRun.company_id == company_id)
    return query.all()


@router.post("/{record_id}/upload-part-a")
def upload_part_a(
    record_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    record = _load_record(db, record_id)
    _enforce_access(record, current_user, manage_required=True)
    if (file.content_type or "").lower() != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Part A upload must be a PDF")
    out_dir = _form16_dir(record.employee_id, record.financial_year)
    filename = f"form16_part_a_{uuid.uuid4().hex}.pdf"
    out_path = os.path.join(out_dir, filename)
    with open(out_path, "wb") as handle:
        handle.write(file.file.read())
    record.part_a_file_path = _file_url(out_path)
    if record.part_b_file_path:
        record.combined_file_path = _combine_pdfs(record.part_a_file_path, record.part_b_file_path, record.employee_id, record.financial_year)
    db.commit()
    db.refresh(record)
    return _serialize(record)


@router.post("/{record_id}/publish")
def publish_form16(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_approve", "payroll_run")),
):
    record = _load_record(db, record_id)
    _enforce_access(record, current_user, manage_required=True)
    if not record.combined_file_path and not record.part_b_file_path:
        raise HTTPException(status_code=400, detail="Generate Form 16 PDF before publishing")
    record.status = "published"
    record.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return _serialize(record)


@router.get("/{record_id}/download")
def download_form16(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = _load_record(db, record_id)
    _enforce_access(record, current_user)
    file_url = record.combined_file_path or record.part_b_file_path or record.part_a_file_path
    path = _disk_path(file_url)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Form 16 PDF not found")
    return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))
