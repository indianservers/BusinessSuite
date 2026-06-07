from __future__ import annotations

import csv
import html
import os
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
from typing import Any

from fastapi import HTTPException
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.apps.analytics.models import AnalyticsReport
from app.apps.communication.models import CommunicationCampaign
from app.apps.crm.models import CRMCompany, CRMContact, CRMDeal, CRMLead, CRMQuotation
from app.apps.srm.models import (
    SRMBillingPlan,
    SRMContract,
    SRMEngagement,
    SRMInvoice,
    SRMProfitabilitySnapshot,
    SRMReceipt,
    SRMSalesOrder,
)
from app.core.config import settings


DATA_SOURCES: dict[str, tuple[Any, list[str], bool]] = {
    "crm_leads": (CRMLead, ["id", "full_name", "email", "phone", "source", "status", "estimated_value"], False),
    "crm_accounts": (CRMCompany, ["id", "name", "industry", "email", "phone", "status", "annual_revenue"], False),
    "crm_contacts": (CRMContact, ["id", "full_name", "email", "phone", "lifecycle_stage", "status"], False),
    "crm_deals": (CRMDeal, ["id", "name", "amount", "status", "probability", "expected_close_date"], False),
    "crm_quotes": (CRMQuotation, ["id", "quote_number", "status", "subtotal", "tax_amount", "total_amount"], True),
    "communication_campaigns": (CommunicationCampaign, ["id", "name", "type", "status", "sent_count", "failed_count", "blocked_count"], False),
    "srm_sales_orders": (SRMSalesOrder, ["id", "order_number", "status", "customer_id", "total_amount"], True),
    "srm_contracts": (SRMContract, ["id", "contract_number", "status", "customer_id", "contract_value"], True),
    "srm_engagements": (SRMEngagement, ["id", "name", "status", "customer_id", "sales_order_id"], False),
    "srm_billing_plans": (SRMBillingPlan, ["id", "name", "status", "billing_type", "total_amount"], True),
    "srm_invoices": (SRMInvoice, ["id", "invoice_number", "status", "customer_id", "total_amount", "paid_amount"], True),
    "srm_receipts": (SRMReceipt, ["id", "receipt_number", "status", "customer_id", "amount"], True),
    "srm_collections": (SRMInvoice, ["id", "invoice_number", "status", "customer_id", "total_amount", "paid_amount", "due_date"], True),
    "srm_profitability": (SRMProfitabilitySnapshot, ["id", "engagement_id", "customer_id", "invoiced_amount", "cost_amount", "gross_margin_amount"], True),
}


FINANCIAL_SOURCES = {name for name, (_, _, financial) in DATA_SOURCES.items() if financial}
MAX_SYNC_EXPORT_ROWS = 5000


def ensure_source_allowed(module_name: str, financial_allowed: bool) -> None:
    if module_name not in DATA_SOURCES and module_name != "lead_to_cash":
        raise HTTPException(status_code=400, detail="Unsupported analytics data source")
    if module_name in FINANCIAL_SOURCES and not financial_allowed:
        raise HTTPException(status_code=403, detail="Financial analytics permission required")


def default_fields(module_name: str) -> list[str]:
    if module_name == "lead_to_cash":
        return ["deal_id", "deal_name", "deal_amount", "sales_order", "invoice", "collection_status", "margin"]
    return DATA_SOURCES[module_name][1]


def run_report(db: Session, report: AnalyticsReport, financial_allowed: bool, page: int = 1, page_size: int = 50, extra_filters: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_source_allowed(report.module_name, financial_allowed)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 500)
    fields = list(report.fields_json or default_fields(report.module_name))
    filters = {**(report.filters_json or {}), **(extra_filters or {})}
    rows = cross_module_rows(db) if report.module_name == "lead_to_cash" else source_rows(db, report.module_name, fields, filters, (page - 1) * page_size, page_size)
    if report.module_name == "lead_to_cash":
        total = len(rows)
        rows = rows[(page - 1) * page_size : page * page_size]
    else:
        total = count_rows(db, report.module_name, filters)
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "fields": fields, "async_ready": total > MAX_SYNC_EXPORT_ROWS}


def source_rows(db: Session, module_name: str, fields: list[str], filters: dict[str, Any], offset: int, limit: int) -> list[dict[str, Any]]:
    model = DATA_SOURCES[module_name][0]
    query = db.query(model)
    if hasattr(model, "deleted_at"):
        query = query.filter(model.deleted_at.is_(None))
    for field, value in filters.items():
        if value in (None, "") or not hasattr(model, field):
            continue
        query = query.filter(getattr(model, field) == value)
    if hasattr(model, "id"):
        query = query.order_by(model.id.desc())
    rows = query.offset(offset).limit(limit).all()
    return [serialize_row(item, fields) for item in rows]


def count_rows(db: Session, module_name: str, filters: dict[str, Any]) -> int:
    model = DATA_SOURCES[module_name][0]
    query = db.query(func.count(model.id))
    if hasattr(model, "deleted_at"):
        query = query.filter(model.deleted_at.is_(None))
    for field, value in filters.items():
        if value in (None, "") or not hasattr(model, field):
            continue
        query = query.filter(getattr(model, field) == value)
    return int(query.scalar() or 0)


def serialize_row(item: Any, fields: list[str]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for field in fields:
        value = getattr(item, field, None)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = float(value)
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        row[field] = value
    return row


def cross_module_rows(db: Session) -> list[dict[str, Any]]:
    deals = db.query(CRMDeal).order_by(CRMDeal.id.desc()).limit(100).all()
    rows: list[dict[str, Any]] = []
    for deal in deals:
        order = db.query(SRMSalesOrder).filter(SRMSalesOrder.crm_deal_id == deal.id).first()
        invoice = db.query(SRMInvoice).filter(SRMInvoice.sales_order_id == order.id).first() if order else None
        margin = db.query(SRMProfitabilitySnapshot).filter(SRMProfitabilitySnapshot.customer_id == getattr(deal, "company_id", None)).order_by(SRMProfitabilitySnapshot.snapshot_at.desc()).first()
        rows.append({
            "deal_id": deal.id,
            "deal_name": deal.name,
            "deal_amount": float(deal.amount or 0),
            "sales_order": order.order_number if order else None,
            "invoice": invoice.invoice_number if invoice else None,
            "collection_status": invoice.status if invoice else "not_billed",
            "margin": float(getattr(margin, "gross_margin_amount", 0) or 0) if margin else 0,
        })
    return rows


def write_export(report: AnalyticsReport, payload: dict[str, Any], export_type: str, export_id: int) -> tuple[str, int]:
    rows = payload["items"]
    fields = payload["fields"]
    export_dir = os.path.join(settings.UPLOAD_DIR, "analytics", str(report.id or "adhoc"))
    os.makedirs(export_dir, exist_ok=True)
    file_path = os.path.join(export_dir, f"analytics-export-{export_id}.{export_type}")
    if export_type == "csv":
        write_csv(file_path, rows, fields)
    elif export_type == "xlsx":
        write_xlsx(file_path, rows, fields)
    elif export_type == "pdf":
        write_pdf(file_path, report.name, rows, fields)
    else:
        raise HTTPException(status_code=400, detail="Unsupported export type")
    return file_path, len(rows)


def write_csv(file_path: str, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with open(file_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(file_path: str, rows: list[dict[str, Any]], fields: list[str]) -> None:
    sheet_rows = [fields] + [[row.get(field, "") for field in fields] for row in rows]
    sheet_xml = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for r_idx, row in enumerate(sheet_rows, start=1):
        sheet_xml.append(f'<row r="{r_idx}">')
        for c_idx, value in enumerate(row, start=1):
            cell_ref = f"{_column_letter(c_idx)}{r_idx}"
            sheet_xml.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{html.escape(str(value if value is not None else ""))}</t></is></c>')
        sheet_xml.append("</row>")
    sheet_xml.append("</sheetData></worksheet>")
    with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", "".join(sheet_xml))


def write_pdf(file_path: str, title: str, rows: list[dict[str, Any]], fields: list[str]) -> None:
    styles = getSampleStyleSheet()
    story = [Paragraph(html.escape(title), styles["Title"]), Spacer(1, 12)]
    table_data = [fields] + [[str(row.get(field, "") if row.get(field) is not None else "")[:80] for field in fields] for row in rows[:100]]
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 7)]))
    story.append(table)
    SimpleDocTemplate(file_path, pagesize=letter).build(story)


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters
