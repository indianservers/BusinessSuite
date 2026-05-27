from __future__ import annotations

import csv
import html
import os
import re
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import RequirePermission, get_db
from app.models.company import Company
from app.models.employee import Employee
from app.models.payroll import (
    BankAdviceFormat,
    PayrollBankFileValidation,
    PayrollBankExport,
    PayrollRecord,
    PayrollRun,
    PayrollRunAuditLog,
)
from app.services.bank_file_validators import validate_bank_file_rows
from app.models.user import User
from app.schemas.payroll import (
    PayrollBankAdviceGenerateRequest,
    PayrollBankAdvicePreviewSchema,
    PayrollBankExportSchema,
)


router = APIRouter(prefix="/hrms/payroll", tags=["HRMS Payroll Bank Advice"])

APPROVED_RUN_STATUSES = {"approved", "locked", "paid"}
EXPORT_TYPES = {"pdf", "xlsx", "txt"}
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$", re.IGNORECASE)


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


def _company_name(db: Session, run: PayrollRun) -> str:
    company = db.query(Company).filter(Company.id == run.company_id).first() if run.company_id else None
    if company:
        return company.legal_name or company.name
    return "Company"


def _employee_name(employee: Employee | None) -> str:
    if not employee:
        return "Unknown employee"
    return " ".join(part for part in [employee.first_name, employee.middle_name, employee.last_name] if part).strip()


def _mask_account(account_number: str | None) -> str | None:
    if not account_number:
        return None
    clean = str(account_number).strip()
    if len(clean) <= 4:
        return "*" * len(clean)
    return f"{'*' * (len(clean) - 4)}{clean[-4:]}"


def _normalise_amount(value: Any) -> Decimal:
    amount = value if isinstance(value, Decimal) else Decimal(str(value or 0))
    return amount.quantize(Decimal("0.01"))


def _payroll_month(run: PayrollRun) -> str:
    return f"{run.month:02d}/{run.year}"


def _bank_rows(db: Session, run: PayrollRun) -> tuple[list[dict[str, Any]], list[str], Decimal]:
    records = (
        db.query(PayrollRecord)
        .filter(PayrollRecord.payroll_run_id == run.id)
        .order_by(PayrollRecord.employee_id)
        .all()
    )
    rows: list[dict[str, Any]] = []
    all_errors: list[str] = []
    total = Decimal("0.00")
    for record in records:
        employee = db.query(Employee).filter(Employee.id == record.employee_id, Employee.deleted_at.is_(None)).first()
        employee_name = _employee_name(employee)
        account_number = (employee.account_number or "").strip() if employee else ""
        ifsc = (employee.ifsc_code or "").strip().upper() if employee else ""
        bank_name = (employee.bank_name or "").strip() if employee else ""
        amount = _normalise_amount(record.net_salary)
        errors: list[str] = []
        if not employee:
            errors.append("Employee record is missing")
        if not employee_name or employee_name == "Unknown employee":
            errors.append("Account holder name is missing")
        if not bank_name:
            errors.append("Bank name is missing")
        if not account_number:
            errors.append("Account number is missing")
        elif not re.fullmatch(r"[0-9]{6,18}", account_number):
            errors.append("Account number must be 6-18 digits")
        if not ifsc:
            errors.append("IFSC is missing")
        elif not IFSC_RE.fullmatch(ifsc):
            errors.append("IFSC format is invalid")
        if amount <= 0:
            errors.append("Payment amount must be greater than zero")
        if errors:
            all_errors.extend([f"{employee_name}: {error}" for error in errors])
        else:
            total += amount
        rows.append(
            {
                "payroll_record_id": record.id,
                "employee_id": record.employee_id,
                "employee_code": employee.employee_id if employee else None,
                "employee_name": employee_name,
                "account_holder_name": employee_name,
                "bank_name": bank_name or None,
                "account_number": account_number or None,
                "account_number_masked": _mask_account(account_number),
                "ifsc": ifsc or None,
                "net_payable": amount,
                "narration": f"Salary {_payroll_month(run)}",
                "validation_errors": errors,
            }
        )
    return rows, all_errors, total


def _preview_payload(db: Session, run: PayrollRun, bank_name: str | None = None, payment_mode: str | None = None) -> dict[str, Any]:
    rows, validation_errors, total = _bank_rows(db, run)
    bank_validation = validate_bank_file_rows(rows, bank_name or "Payroll Bank", payment_mode) if bank_name else None
    if bank_validation and bank_validation["errors"]:
        validation_errors.extend([f"Row {item.get('row', '-')}: {item.get('message')}" for item in bank_validation["errors"]])
    return {
        "payroll_run_id": run.id,
        "payroll_month": _payroll_month(run),
        "status": run.status,
        "company_name": _company_name(db, run),
        "bank_name": bank_name,
        "total_employees": sum(1 for row in rows if not row["validation_errors"]),
        "total_amount": total,
        "validation_errors": validation_errors,
        "bank_file_validation": bank_validation,
        "rows": [{key: value for key, value in row.items() if key != "account_number"} for row in rows],
    }


def _export_dir(run: PayrollRun) -> str:
    return os.path.join(settings.UPLOAD_DIR, "exports", "payroll", str(run.id), "bank_advice")


def _file_url(file_path: str) -> str:
    rel_path = os.path.relpath(file_path, settings.UPLOAD_DIR).replace(os.sep, "/")
    return f"/uploads/{rel_path}"


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "bank_advice"


def _write_pdf(file_path: str, company_name: str, bank_name: str, run: PayrollRun, rows: list[dict[str, Any]], total: Decimal) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet

        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = [
            Paragraph("Bank Payment Advice", styles["Title"]),
            Paragraph(company_name, styles["Heading2"]),
            Paragraph(f"Bank: {bank_name or 'Not specified'}", styles["Normal"]),
            Paragraph(f"Payroll Month: {_payroll_month(run)}", styles["Normal"]),
            Paragraph(f"Employee Count: {len(rows)}", styles["Normal"]),
            Paragraph(f"Total Amount: INR {total}", styles["Normal"]),
            Spacer(1, 0.2 * inch),
        ]
        table_rows = [["Employee", "Account", "IFSC", "Net Payable", "Narration"]]
        for row in rows:
            table_rows.append([
                row["employee_name"],
                row["account_number"],
                row["ifsc"],
                f"{row['net_payable']}",
                row["narration"],
            ])
        table = Table(table_rows, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (3, 1), (3, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
        story.extend([Spacer(1, 0.6 * inch), Paragraph("Authorized Signatory", styles["Heading3"])])
        doc.build(story)
    except Exception:
        from app.api.v1.payroll import _write_basic_pdf

        lines = [
            "Bank Payment Advice",
            company_name,
            f"Bank: {bank_name or 'Not specified'}",
            f"Payroll Month: {_payroll_month(run)}",
            f"Employee Count: {len(rows)}",
            f"Total Amount: INR {total}",
            "",
            "Employee | Account | IFSC | Net Payable | Narration",
        ]
        lines.extend([f"{row['employee_name']} | {row['account_number']} | {row['ifsc']} | {row['net_payable']} | {row['narration']}" for row in rows[:35]])
        lines.extend(["", "Authorized Signatory"])
        _write_basic_pdf(file_path, lines)


def _xlsx_cell(value: Any) -> str:
    if isinstance(value, Decimal):
        return f"<c><v>{value}</v></c>"
    return f'<c t="inlineStr"><is><t>{html.escape("" if value is None else str(value))}</t></is></c>'


def _write_xlsx(file_path: str, rows: list[dict[str, Any]]) -> None:
    headers = ["Employee name", "Employee code", "Account number", "IFSC", "Net payable", "Narration"]
    sheet_rows = [headers] + [
        [
            row["employee_name"],
            row["employee_code"],
            row["account_number"],
            row["ifsc"],
            row["net_payable"],
            row["narration"],
        ]
        for row in rows
    ]
    xml_rows = []
    for index, row in enumerate(sheet_rows, start=1):
        cells = "".join(_xlsx_cell(value) for value in row)
        xml_rows.append(f'<row r="{index}">{cells}</row>')
    sheet_xml = f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    workbook_xml = '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Bank Advice" sheetId="1" r:id="rId1"/></sheets></workbook>'
    rels_xml = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    workbook_rels_xml = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
    content_types_xml = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def _write_txt(file_path: str, rows: list[dict[str, Any]], bank_format: BankAdviceFormat | None = None) -> None:
    delimiter = (bank_format.delimiter if bank_format else "|") or "|"
    columns = [item.strip() for item in ((bank_format.column_order if bank_format else "") or "").split(",") if item.strip()]
    if not columns:
        columns = ["employee_name", "account_number", "ifsc", "net_payable", "narration"]
    column_map = {
        "employee_id": "employee_code",
        "employee_name": "employee_name",
        "account_holder_name": "account_holder_name",
        "account_number": "account_number",
        "ifsc": "ifsc",
        "net_salary": "net_payable",
        "net_payable": "net_payable",
        "narration": "narration",
    }
    with open(file_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        if bank_format and bank_format.include_header:
            writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(column_map.get(column, column), "") for column in columns])


@router.get("/{payroll_run_id}/bank-advice/preview", response_model=PayrollBankAdvicePreviewSchema)
def preview_bank_advice(
    payroll_run_id: int,
    bank_name: str | None = None,
    payment_mode: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view", "payroll_run")),
):
    run = _get_scoped_run(db, payroll_run_id, current_user)
    return _preview_payload(db, run, bank_name, payment_mode)


@router.get("/{payroll_run_id}/bank-exports", response_model=list[PayrollBankExportSchema])
def list_bank_exports(
    payroll_run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view", "payroll_run")),
):
    run = _get_scoped_run(db, payroll_run_id, current_user)
    return (
        db.query(PayrollBankExport)
        .filter(PayrollBankExport.payroll_run_id == run.id)
        .order_by(PayrollBankExport.id.desc())
        .all()
    )


@router.post("/{payroll_run_id}/bank-advice/generate", response_model=PayrollBankExportSchema, status_code=201)
def generate_bank_advice(
    payroll_run_id: int,
    data: PayrollBankAdviceGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_run")),
):
    run = _get_scoped_run(db, payroll_run_id, current_user)
    export_type = data.export_type.lower()
    if export_type not in EXPORT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported bank advice export type")
    if (run.status or "").lower() not in APPROVED_RUN_STATUSES:
        raise HTTPException(status_code=400, detail="Bank advice can be generated only after payroll approval")

    rows, validation_errors, total = _bank_rows(db, run)
    bank_format = db.query(BankAdviceFormat).filter(BankAdviceFormat.id == data.bank_format_id, BankAdviceFormat.is_active == True).first() if data.bank_format_id else None
    bank_name = data.bank_name or (bank_format.bank_name if bank_format else None) or "Payroll Bank"
    bank_validation = validate_bank_file_rows(rows, bank_name=bank_name, payment_mode=data.payment_mode)
    db.add(PayrollBankFileValidation(
        payroll_run_id=run.id,
        bank_name=bank_name,
        status=bank_validation["status"],
        error_count=len(bank_validation["errors"]),
        errors_json=bank_validation["errors"],
        warnings_json=bank_validation["warnings"],
        created_by=current_user.id,
    ))
    if bank_validation["errors"]:
        db.commit()
        raise HTTPException(status_code=400, detail={"message": "Bank-specific file validation failed", "validation": bank_validation})
    if validation_errors:
        raise HTTPException(status_code=400, detail={"message": "Bank advice validation failed", "validation_errors": validation_errors})
    if not rows:
        raise HTTPException(status_code=400, detail="No payroll records available for bank advice")

    export_dir = _export_dir(run)
    os.makedirs(export_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    filename = f"bank_advice_{_safe_filename(bank_name)}_{timestamp}.{export_type}"
    file_path = os.path.join(export_dir, filename)

    if export_type == "pdf":
        _write_pdf(file_path, _company_name(db, run), bank_name, run, rows, total)
    elif export_type == "xlsx":
        _write_xlsx(file_path, rows)
    else:
        _write_txt(file_path, rows, bank_format)

    export = PayrollBankExport(
        organization_id=run.company_id,
        payroll_run_id=run.id,
        export_type=export_type,
        bank_name=bank_name,
        total_employees=len(rows),
        total_amount=total,
        file_path=_file_url(file_path),
        generated_by=current_user.id,
        download_count=0,
    )
    db.add(export)
    _audit(db, run.id, "bank_advice_generated", current_user.id, f"{export_type}:{bank_name}:amount={total}")
    db.commit()
    db.refresh(export)
    return export


@router.get("/bank-exports/{export_id}/download")
def download_bank_export(
    export_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("payroll_view", "payroll_run")),
):
    export = db.query(PayrollBankExport).filter(PayrollBankExport.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Bank export not found")
    _get_scoped_run(db, export.payroll_run_id, current_user)
    if not export.file_path.startswith("/uploads/"):
        raise HTTPException(status_code=404, detail="Bank export file not found")
    file_path = os.path.join(settings.UPLOAD_DIR, export.file_path.replace("/uploads/", "", 1).replace("/", os.sep))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Bank export file missing on disk")

    export.downloaded_at = datetime.now(timezone.utc)
    export.download_count = (export.download_count or 0) + 1
    _audit(db, export.payroll_run_id, "bank_advice_downloaded", current_user.id, f"export_id={export.id}")
    db.commit()

    media_types = {
        "pdf": "application/pdf",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "txt": "text/plain",
    }
    return FileResponse(file_path, media_type=media_types.get(export.export_type, "application/octet-stream"), filename=os.path.basename(file_path))
