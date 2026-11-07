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
from app.apps.crm.models import CRMCompany, CRMContact, CRMDeal, CRMLead, CRMQuotation, CRMTask, CRMCustomField, CRMCustomFieldValue
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
    'crm_tasks': (CRMTask, ['id', 'title', 'status', 'priority', 'due_date', 'deal_id'], False),
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
    source = report.data_source_json or {}
    if source.get('industry_pack'):
        if user is not None:
            from app.services.metrics.queries import company_id
            if source.get('company_id') != company_id(user):
                raise HTTPException(404, 'Analytics report not found')
        from app.models.platform import DomainPackRegistry
        pack = db.query(DomainPackRegistry).filter_by(company_id=source.get('company_id'), pack_key='industry:'+source['industry_pack'], status='Enabled').first()
        if not pack:
            raise HTTPException(409, 'This industry pack is disabled or unavailable')
        locked = source.get('locked_filters', {})
        if any(key in (extra_filters or {}) and extra_filters[key] != value for key, value in locked.items()):
            raise HTTPException(422, 'Industry report scope cannot be overridden')
    else:
        locked = {}
    filters={**(report.filters_json or {}),**(extra_filters or {}), **locked}
    if report.grouping_json:
        return grouped_report(db, report, filters, user, page, page_size)
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
            resource={"crm_leads":"leads","crm_accounts":"companies","crm_contacts":"contacts","crm_deals":"deals","crm_quotes":"quotations", 'crm_tasks': 'tasks'}[module_name]
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
        if module_name == 'crm_tasks' and field == 'pack_pipeline_id':
            deals = report_query(db, 'crm_deals', {'pipeline_id': value}, user).with_entities(CRMDeal.id)
            query = query.filter(CRMTask.deal_id.in_(deals))
            continue
        if field not in model.__table__.columns:raise HTTPException(422,"Unsupported report filter: "+field)
        query=query.filter(getattr(model,field)==value)
    return query


def source_rows(db:Session,module_name:str,fields:list[str],filters:dict[str,Any],offset:int,limit:int,user=None):
    model=DATA_SOURCES[module_name][0]
    rows=report_query(db,module_name,filters,user).order_by(model.id.desc()).offset(offset).limit(limit).all()
    output = [serialize_row(item,fields) for item in rows]
    custom = [field[7:] for field in fields if field.startswith('custom:')]
    if custom:
        if module_name != 'crm_deals':
            raise HTTPException(422, 'Custom report columns currently require the CRM deal adapter')
        definitions = db.query(CRMCustomField).filter(CRMCustomField.entity == 'deals', CRMCustomField.field_key.in_(custom),
            CRMCustomField.is_visible.is_(True), CRMCustomField.is_active.is_(True), CRMCustomField.deleted_at.is_(None)).all()
        field_map = {f.id: f.field_key for f in definitions}
        if set(custom) - set(field_map.values()):
            raise HTTPException(422, 'A report custom field is hidden, missing or unavailable')
        values = db.query(CRMCustomFieldValue).filter(CRMCustomFieldValue.custom_field_id.in_(field_map),
            CRMCustomFieldValue.record_id.in_([row.id for row in rows]), CRMCustomFieldValue.entity == 'deals', CRMCustomFieldValue.deleted_at.is_(None)).all()
        from app.apps.crm.api.router import _custom_field_value
        by_record = {row.id: output[index] for index, row in enumerate(rows)}
        for value in values:
            decoded = _custom_field_value(value)
            by_record[value.record_id]['custom:'+field_map[value.custom_field_id]] = decoded.isoformat() if hasattr(decoded, 'isoformat') else float(decoded) if isinstance(decoded, Decimal) else decoded
    return output


def grouped_report(db, report, filters, user, page, page_size):
    config = report.grouping_json
    groups, aggregates = config.get('group_by'), config.get('aggregates')
    if not isinstance(groups, list) or not 1 <= len(groups) <= 3 or not isinstance(aggregates, dict) or not 1 <= len(aggregates) <= 8:
        raise HTTPException(422, 'Grouped reports require bounded group_by and aggregates')
    model = DATA_SOURCES[report.module_name][0]
    allowed = set(default_fields(report.module_name)) | {'stage_id', 'pipeline_id', 'owner_user_id'}
    if any(key not in allowed or key not in model.__table__.c for key in groups):
        raise HTTPException(422, 'Unsupported report grouping')
    expressions = [getattr(model, key).label(key) for key in groups]
    for alias, spec in aggregates.items():
        if not isinstance(alias, str) or not alias.isidentifier() or alias in groups or not isinstance(spec, dict):
            raise HTTPException(422, 'Invalid aggregate definition')
        operation = spec.get('function')
        if operation == 'count':
            expression = func.count(model.id)
        else:
            key = spec.get('field')
            if key not in allowed or key not in model.__table__.c or operation not in {'sum', 'avg', 'min', 'max'}:
                raise HTTPException(422, 'Unsupported aggregate field or operation')
            from sqlalchemy import Numeric, Integer
            if not isinstance(model.__table__.c[key].type, (Numeric, Integer)):
                raise HTTPException(422, 'Aggregation requires a numeric field')
            expression = getattr(func, operation)(getattr(model, key))
        expressions.append(expression.label(alias))
    query = report_query(db, report.module_name, filters, user).with_entities(*expressions).group_by(*[getattr(model, key) for key in groups])
    total = query.count()
    items = query.order_by(*[getattr(model, key) for key in groups]).offset((page-1)*page_size).limit(page_size).all()
    columns = [*groups, *aggregates]
    rows = [{key: float(value) if isinstance(value, Decimal) else value.isoformat() if hasattr(value, 'isoformat') else value for key, value in zip(columns, item)} for item in items]
    return {'items': rows, 'total': total, 'page': page, 'page_size': page_size, 'fields': columns, 'async_ready': total > MAX_SYNC_EXPORT_ROWS, 'definition': 'Scoped grouped source rows before pagination'}


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
