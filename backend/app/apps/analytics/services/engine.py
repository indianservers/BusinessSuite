from __future__ import annotations
from app.core.storage import persist_file

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
        return ["deal_id", "deal_name", "deal_amount", "deal_currency", "sales_order", "invoice", "collection_status", "margin"]
    return DATA_SOURCES[module_name][1]


def run_report(db: Session, report: AnalyticsReport, financial_allowed: bool, page: int = 1, page_size: int = 50, extra_filters: dict[str, Any] | None = None, user=None, max_page_size:int=500) -> dict[str, Any]:
    ensure_source_allowed(report.module_name,financial_allowed)
    page=max(page,1);page_size=min(max(page_size,1),max_page_size)
    fields=list(report.fields_json or default_fields(report.module_name))
    filters={**(report.filters_json or {}),**(extra_filters or {})}
    if report.module_name=="lead_to_cash":
        query=report_query(db,"crm_deals",filters,user)
        total=query.count();rows=cross_module_rows(db,user,(page-1)*page_size,page_size,query)
    else:
        rows=source_rows(db,report.module_name,fields,filters,(page-1)*page_size,page_size,user)
        total=count_rows(db,report.module_name,filters,user)
    return {"items":rows,"total":total,"page":page,"page_size":page_size,"fields":fields,"async_ready":total>MAX_SYNC_EXPORT_ROWS,"definition":"Full scoped source query total before pagination. Lead-to-cash rows are unique deals; link counts and collections are separate measures."}


def report_query(db,module_name,filters,user=None):
    model=DATA_SOURCES[module_name][0]
    query=db.query(model)
    if user is not None:
        from app.services.metrics.registry import crm_query
        from app.services.metrics.queries import company_id
        if module_name.startswith("crm_"):
            resource={"crm_leads":"leads","crm_accounts":"companies","crm_contacts":"contacts","crm_deals":"deals","crm_quotes":"quotations"}[module_name]
            query=crm_query(db,user,resource)
        elif module_name in {"srm_invoices","srm_collections"}:
            from app.apps.srm.services.commercial import invoice_query
            query=invoice_query(db,user)
        elif module_name=="srm_sales_orders":
            from app.apps.srm.access import sales_order_query
            query=sales_order_query(db,user)
        elif module_name=="srm_engagements":
            from app.apps.srm.access import engagement_query
            query=engagement_query(db,user)
        elif module_name=="srm_profitability":
            from app.services.metrics.sales import latest_profitability_query
            query=latest_profitability_query(db,user)
        elif hasattr(model,"organization_id"):query=query.filter(func.coalesce(model.organization_id,1)==company_id(user))
    if hasattr(model,"deleted_at"):query=query.filter(model.deleted_at.is_(None))
    for field,value in filters.items():
        if value in (None,""):continue
        if field not in model.__table__.columns:raise HTTPException(422,"Unsupported report filter: "+field)
        query=query.filter(getattr(model,field)==value)
    return query


def source_rows(db:Session,module_name:str,fields:list[str],filters:dict[str,Any],offset:int,limit:int,user=None):
    model=DATA_SOURCES[module_name][0]
    rows=report_query(db,module_name,filters,user).order_by(model.id.desc()).offset(offset).limit(limit).all()
    return [serialize_row(item,fields) for item in rows]


def count_rows(db:Session,module_name:str,filters:dict[str,Any],user=None):
    model=DATA_SOURCES[module_name][0]
    return report_query(db,module_name,filters,user).with_entities(model.id).distinct().count()


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


def cross_module_rows(db:Session,user=None,offset=0,limit=500,query=None):
    # Stable identities and real deal/order links; never infer ownership from a company name.
    query=query if query is not None else report_query(db,"crm_deals",{},user)
    deals=query.order_by(CRMDeal.id.desc()).offset(offset).limit(limit).all();ids=[d.id for d in deals]
    order_query=report_query(db,"srm_sales_orders",{},user).filter(SRMSalesOrder.crm_deal_id.in_(ids))
    orders=order_query.order_by(SRMSalesOrder.id).all();order_ids=[o.id for o in orders]
    invoices=report_query(db,"srm_invoices",{},user).filter(SRMInvoice.sales_order_id.in_(order_ids)).order_by(SRMInvoice.id).all() if order_ids else []
    orders_by_deal={d.id:[] for d in deals};invoices_by_order={o.id:[] for o in orders}
    for order in orders:orders_by_deal[order.crm_deal_id].append(order)
    for invoice in invoices:invoices_by_order[invoice.sales_order_id].append(invoice)
    rows=[]
    for deal in deals:
        linked=orders_by_deal[deal.id];bills=[bill for order in linked for bill in invoices_by_order[order.id]]
        rows.append({"deal_id":deal.id,"deal_name":deal.name,"deal_amount":float(deal.amount) if deal.amount is not None else None,"deal_currency":deal.currency,
            "sales_order":linked[0].order_number if linked else None,"invoice":bills[0].invoice_number if bills else None,
            "sales_orders":[o.order_number for o in linked],"invoices":[i.invoice_number for i in bills],"order_count":len(linked),"invoice_count":len(bills),
            "collection_status":bills[0].status if len(bills)==1 else "multiple_invoices" if bills else "not_billed",
            "margin":None,"margin_note":"No single attributable margin is inferred from matching a customer. Use authorized engagement profitability snapshots."})
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
    persist_file(file_path)
    return file_path, len(rows)


def write_csv(file_path: str, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with open(file_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    persist_file(file_path)


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
