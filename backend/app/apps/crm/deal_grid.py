"""CRM adapter for the suite's universal grid query contract."""
import csv
import io
import json
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, ValidationError, Field
from sqlalchemy import func, or_, case, cast, String
from sqlalchemy.orm import joinedload

from app.core.deps import get_db, RequirePermission
from app.models.user import User
from app.shared.data_grid import GridField, parse_query, apply_filters, apply_path, apply_sort, field_for, safe_cell, FilterGroup
from .models import CRMDeal, CRMPipelineStage, CRMPipeline, CRMCompany
from .productivity import READ, rows, allowed
from . import deal_workspace as workspace
from . import lead_management as lm

router = APIRouter(prefix="/deal-workspace/grid", tags=["CRM shared grid adapter"])


class ArchiveRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(gt=0)
    version: int = Field(ge=1)


class ArchiveSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[ArchiveRecord] = Field(min_length=1, max_length=200)


@router.post("/archive")
def archive_selection(data: ArchiveSelection, db=Depends(get_db), user=Depends(RequirePermission("crm_admin", "crm_manage", "crm_deals_manage"))):
    if not capabilities(user)["archive"]: raise HTTPException(403, "Archive permission is required")
    if len({r.id for r in data.records}) != len(data.records): raise HTTPException(422, "Select each record once")
    result = []
    for item in data.records:
        try:
            record = rows(db,user,"deals").filter(CRMDeal.id==item.id).with_for_update(of=CRMDeal).first()
            if not record: raise HTTPException(404, "Deal not found in your permitted scope")
            if record.version != item.version: raise HTTPException(409, "This deal changed; refresh before archiving")
            lm.core().delete_record("deals", item.id, db=db, current_user=user)
            result.append({"id":item.id,"saved":True})
        except HTTPException as error:
            db.expire_all()
            result.append({"id":item.id,"saved":False,"message":error.detail})
    return {"items":result}


class BaseFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search: str = ""
    currency: str = ""
    pipeline_id: int | None = None
    owner_id: int | None = None
    stage_id: int | None = None
    status: str = ""
    priority: str = ""
    deal_type: str = ""
    start: date | None = None
    end: date | None = None
    no_next: bool = False
    industry: str = ""
    source: str = ""
    team_id: int | None = None
    entered_stage_id: int | None = None
    lost_reason: str = ""


def fields():
    labels = {"id": "Record ID", "name": "Deal name", "amount": "Deal value", "currency": "Currency", "probability": "Probability", "weighted": "Weighted value", "pipeline_id": "Pipeline", "stage_id": "Stage", "owner_user_id": "Owner", "company_id": "Company", "expected_close_date": "Expected close", "next_follow_up_at": "Next action", "priority": "Priority", "status": "Status", "created_at": "Created", "updated_at": "Updated", "deal_type": "Deal type", "source": "Source"}
    kinds = {"id": "id", "amount": "number", "probability": "number", "weighted": "number", "pipeline_id": "id", "stage_id": "id", "owner_user_id": "id", "company_id": "id", "expected_close_date": "date", "next_follow_up_at": "datetime", "created_at": "datetime", "updated_at": "datetime"}
    return {key: GridField(CRMDeal.amount * CRMDeal.probability / 100 if key == "weighted" else getattr(CRMDeal, key), kinds.get(key, "text"), title, key not in {"name", "amount", "weighted", "created_at", "updated_at", "next_follow_up_at", "probability"}) for key, title in labels.items()}


def scoped_query(db, user, raw_base, state):
    lm.core()._assert_entity_permission("deals", user, "view")
    try: base = BaseFilters.model_validate_json(raw_base)
    except ValidationError: raise HTTPException(422, "Invalid deal filters")
    if base.start and base.end and base.start > base.end: raise HTTPException(422, "Start date must be before end date")
    values = base.model_dump(); values["search"] = state.search or values["search"]
    return apply_filters(workspace.filtered(db, user, **values), state, fields())


def capabilities(user):
    grant = (getattr(user, "_suite_grants", None) or {}).get("crm")
    actions = set(grant.get("actions", [])) if grant else None
    manage = allowed(user, "deals", "manage")
    return {"edit": manage and (actions is None or "edit" in actions), "export": actions is None or "export" in actions, "archive": manage and (actions is None or "delete" in actions), "assign": manage and lm.core()._crm_can_assign_beyond_self(user), "manualProbability": manage and lm.core()._crm_can_assign_beyond_self(user)}


def names_for(db, user, field, identities):
    ids = [int(v) for v in identities if v is not None]
    if not ids: return {}
    if field == "stage_id":
        return {r.id: r.name for r in db.query(CRMPipelineStage).filter(CRMPipelineStage.id.in_(ids), CRMPipelineStage.organization_id == lm.core()._organization_id(db, user)).all()}
    if field == "pipeline_id":
        return {r.id: r.name for r in db.query(CRMPipeline).filter(CRMPipeline.id.in_(ids), CRMPipeline.organization_id == lm.core()._organization_id(db, user)).all()}
    if field == "company_id":
        return {r.id: r.name for r in rows(db, user, "companies").filter(CRMCompany.id.in_(ids)).all()} if allowed(user, "companies", "view") else {}
    if field == "owner_user_id":
        from .lead_assignment import candidate_organization
        return {r.id: getattr(r.person, "display_name", None) or r.email for r in db.query(User).filter(User.id.in_(ids)).all() if candidate_organization(r) == lm.core()._organization_id(db, user)}
    return {}


def serialize_items(db, user, items, include_health=True):
    company = names_for(db, user, "company_id", [r.company_id for r in items])
    owner = names_for(db, user, "owner_user_id", [r.owner_user_id for r in items])
    pipeline = names_for(db, user, "pipeline_id", [r.pipeline_id for r in items])
    entered = dict(db.query(workspace.CRMTimelineEvent.record_id,func.max(workspace.CRMTimelineEvent.occurred_at)).filter(workspace.CRMTimelineEvent.organization_id==lm.core()._organization_id(db,user),workspace.CRMTimelineEvent.record_type=="deal",workspace.CRMTimelineEvent.event_type=="stage_change",workspace.CRMTimelineEvent.record_id.in_([r.id for r in items])).group_by(workspace.CRMTimelineEvent.record_id).all()) if items and include_health else {}
    record_fields = ("id", "organization_id", "name", "company_id", "pipeline_id", "stage_id", "owner_user_id", "amount", "currency", "probability", "status", "priority", "expected_close_date", "next_follow_up_at", "created_at", "updated_at", "deal_type", "source", "version")
    return [{**{key:getattr(r,key) for key in record_fields}, "has_catalog_items":bool(r.catalog_items), "planning":{"milestones":(r.planning or {}).get("milestones",[])}, "company_name": company.get(r.company_id), "owner_name": owner.get(r.owner_user_id), "pipeline_name": pipeline.get(r.pipeline_id), "stage_name": r.stage.name if r.stage else None, "stage_color": r.stage.color if r.stage else None, **({"health":workspace.health(r,entered.get(r.id))} if include_health else {}), "weighted": round(float(r.amount or 0) * (r.probability or 0) / 100, 2)} for r in items]


def money_aggregates(query, group_column=None):
    columns = ([group_column] if group_column is not None else []) + [CRMDeal.currency, func.count(CRMDeal.id), func.sum(CRMDeal.amount), func.avg(CRMDeal.amount), func.min(CRMDeal.amount), func.max(CRMDeal.amount), func.sum(CRMDeal.amount * CRMDeal.probability / 100)]
    groups = ([group_column] if group_column is not None else []) + [CRMDeal.currency]
    values = query.order_by(None).with_entities(*columns).group_by(*groups).all()
    return [{"key": r[0] if group_column is not None else None, "currency": r[-7] or "Unknown", "count": r[-6], "sum": round(float(r[-5] or 0), 2), "avg": round(float(r[-4] or 0), 2), "min": float(r[-3] or 0), "max": float(r[-2] or 0), "weighted": round(float(r[-1] or 0), 2)} for r in values]


@router.get("/query")
def query(state: str = Query("{}", max_length=16000), base: str = Query("{}", max_length=6000), db=Depends(get_db), user=Depends(RequirePermission(*READ))):
    parsed = parse_query(state); adapter = fields(); q = scoped_query(db, user, base, parsed)
    total = q.count(); branch = apply_path(q, parsed, adapter)
    result = {"total": total, "permissions": capabilities(user), "rows": [], "groups": [], "page": parsed.page, "pageSize": parsed.pageSize}
    if not parsed.path:
        result["aggregates"] = money_aggregates(q)
        result["context"] = {"summary": workspace.summarize_query(q, db, user)}
    if len(parsed.path) < len(parsed.grouping):
        name = parsed.grouping[len(parsed.path)]; column = field_for(adapter, name).expression
        keys_query = branch.order_by(None).with_entities(column).distinct()
        result["pageTotal"] = keys_query.count()
        keys = [row[0] for row in keys_query.order_by(column.asc().nullslast()).offset((parsed.page - 1) * parsed.pageSize).limit(parsed.pageSize).all()]
        constrained = branch.filter(or_(column.in_([v for v in keys if v is not None]), column.is_(None))) if None in keys else branch.filter(column.in_(keys))
        aggregates = money_aggregates(constrained, column) if keys else []
        names = names_for(db, user, name, keys) if field_for(adapter, name).kind == "id" else {}
        for key in keys:
            sums = [{k: v for k, v in r.items() if k != "key"} for r in aggregates if r["key"] == key]
            value = key.isoformat() if isinstance(key, date) else key
            result["groups"].append({"field": name, "value": value, "label": names.get(key, str(value)) if value is not None else "Not set", "count": sum(r["count"] for r in sums), "aggregates": sums, "path": [p.model_dump() for p in parsed.path] + [{"field": name, "value": value}]})
    else:
        result["pageTotal"] = branch.count()
        items = apply_sort(branch, parsed, adapter, CRMDeal.id).options(joinedload(CRMDeal.stage)).offset((parsed.page - 1) * parsed.pageSize).limit(parsed.pageSize).all()
        result["rows"] = serialize_items(db, user, items)
    return result


def without_field(group, field):
    return FilterGroup(logic=group.logic, rules=[without_field(rule, field) if isinstance(rule, FilterGroup) else rule for rule in group.rules if isinstance(rule, FilterGroup) or rule.field != field])


@router.get("/facets")
def facets(field: str, search: str = Query("", max_length=100), state: str = Query("{}", max_length=16000), base: str = Query("{}", max_length=6000), db=Depends(get_db), user=Depends(RequirePermission(*READ))):
    parsed = parse_query(state); parsed.filters = without_field(parsed.filters, field)
    q = scoped_query(db, user, base, parsed); definition = field_for(fields(), field); column = definition.expression
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        if definition.kind == "id" and field in {"pipeline_id", "stage_id", "company_id", "owner_user_id"}:
            if field == "company_id" and allowed(user, "companies", "view"): lookup = rows(db, user, "companies").filter(CRMCompany.name.ilike(f"%{escaped}%", escape="\\")).with_entities(CRMCompany.id)
            elif field == "stage_id": lookup = db.query(CRMPipelineStage.id).filter(CRMPipelineStage.name.ilike(f"%{escaped}%", escape="\\"), CRMPipelineStage.organization_id == lm.core()._organization_id(db, user))
            elif field == "pipeline_id": lookup = db.query(CRMPipeline.id).filter(CRMPipeline.name.ilike(f"%{escaped}%", escape="\\"), CRMPipeline.organization_id == lm.core()._organization_id(db, user))
            elif field == "owner_user_id":
                from app.common.models import CommonPerson
                lookup = db.query(User.id).filter(User.email.ilike(f"%{escaped}%", escape="\\"), or_(User.id == user.id, User.person.has(CommonPerson.organization_id == lm.core()._organization_id(db,user))))
            else: lookup = db.query(CRMCompany.id).filter(False)
            q = q.filter(column.in_(lookup))
        else: q = q.filter(cast(column, String).ilike(f"%{escaped}%", escape="\\"))
    results = q.order_by(None).with_entities(column, func.count(CRMDeal.id)).group_by(column).order_by(column.asc().nullslast()).limit(201).all()
    names = names_for(db, user, field, [r[0] for r in results[:200]]) if definition.kind == "id" else {}
    return {"values": [{"value": value.isoformat() if isinstance(value, date) else value, "label": names.get(value, str(value)) if value is not None else "Not set", "count": count} for value, count in results[:200]], "hasMore": len(results) > 200}


@router.get("/export")
def export(format: Literal["csv", "xlsx", "pdf", "clipboard"] = "csv", scope: Literal["visible", "selected", "filtered"] = "filtered", ids: str = Query("[]", max_length=4000), columns: str = Query('["name","amount","currency","stage_id","owner_user_id"]', max_length=2000), include_summaries: bool = False, include_groups: bool = False, state: str = Query("{}", max_length=16000), base: str = Query("{}", max_length=6000), db=Depends(get_db), user=Depends(RequirePermission(*READ))):
    parsed = parse_query(state); adapter = fields(); q = scoped_query(db, user, base, parsed)
    if not capabilities(user)["export"]: raise HTTPException(403, "Export permission is required")
    try:
        selected_columns = json.loads(columns); selected_ids = json.loads(ids)
        if not isinstance(selected_columns, list) or not 1 <= len(selected_columns) <= len(adapter) or len(set(selected_columns)) != len(selected_columns): raise ValueError()
        for key in selected_columns: field_for(adapter, key)
        if not isinstance(selected_ids, list) or len(selected_ids) > 200 or any(type(v) is not int or v <= 0 for v in selected_ids): raise ValueError()
    except (ValueError, TypeError): raise HTTPException(422, "Choose valid export columns and up to 200 row IDs")
    if scope != "filtered":
        q = q.filter(CRMDeal.id.in_(selected_ids))
    limit = 2000 if format == "pdf" else 20000
    total = q.count()
    if total > limit: raise HTTPException(422, f"Narrow the filters to export at most {limit:,} deals")
    # Project only export fields: descriptions, planning JSON and attachments are
    # never materialized just to export a name/value spreadsheet.
    keys = list(dict.fromkeys([*selected_columns, *parsed.grouping]))
    projected = apply_sort(q, parsed, adapter, CRMDeal.id).with_entities(*(adapter[key].expression for key in keys)).yield_per(500)
    records = [dict(zip(keys, row)) for row in projected]
    for dimension in ("stage_id", "pipeline_id", "company_id", "owner_user_id"):
        if dimension not in keys: continue
        labels = names_for(db, user, dimension, list({r[dimension] for r in records if r[dimension] is not None}))
        for record in records: record[dimension] = labels.get(record[dimension], record[dimension])
    headings = [adapter[key].label for key in selected_columns]
    table = [headings]
    section_rows = []
    if include_groups and parsed.grouping:
        records.sort(key=lambda r: tuple(str(r.get(field) or "") for field in parsed.grouping))
    previous = None
    for record in records:
        if include_groups and parsed.grouping:
            group = tuple(str(record.get(field) or "Not set") for field in parsed.grouping)
            if group != previous:
                section_rows.append(len(table))
                table.append([" / ".join(group)] + [""] * (len(headings) - 1)); previous = group
        table.append([safe_cell(record.get(key)) for key in selected_columns])
    if include_summaries:
        for row in money_aggregates(q):
            summary = f"{row['currency']} · {row['count']} deals · Sum {row['sum']:,.2f} · Average {row['avg']:,.2f} · Min {row['min']:,.2f} · Max {row['max']:,.2f}"
            section_rows.append(len(table))
            table.append([summary] + [""] * (len(headings) - 1))
    lm.core()._create_crm_audit_log(db, user_id=user.id, entity_type="deals", entity_id=None, action="EXPORT", description=f"Shared grid {format} export", new_values={"count": total, "scope": scope, "columns": selected_columns})
    db.commit()
    if format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        workbook = Workbook(); sheet = workbook.active; sheet.title = "Deals"
        for row in table: sheet.append(row)
        for index in section_rows:
            sheet.merge_cells(start_row=index + 1, start_column=1, end_row=index + 1, end_column=len(headings))
            sheet.cell(index + 1, 1).font = Font(bold=True, color="334155")
            sheet.cell(index + 1, 1).alignment = Alignment(wrap_text=True)
        sheet.freeze_panes = "A2"; sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]: cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="334155")
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(45, max(15, len(str(column[0].value)) + 3))
            for cell in column[1:]:
                if isinstance(cell.value, float): cell.number_format = '#,##0.00'
        output = io.BytesIO(); workbook.save(output)
        content, mime = output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif format == "pdf":
        from reportlab.platypus import SimpleDocTemplate, LongTable, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from xml.sax.saxutils import escape
        output = io.BytesIO(); styles = getSampleStyleSheet(); styles["BodyText"].fontSize = 7; styles["BodyText"].leading = 10
        rendered = [[Paragraph(escape(str(v)).replace("\n", "<br/>"), styles["BodyText"]) for v in row] for row in table]
        report = LongTable(rendered, repeatRows=1, colWidths=[(landscape(A4)[0] - 48) / len(headings)] * len(headings))
        for index in section_rows:
            report.setStyle(TableStyle([("SPAN", (0, index), (-1, index)), ("BACKGROUND", (0, index), (-1, index), colors.HexColor("#e2e8f0"))]))
        report.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e2e8f0")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6)]))
        SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=26, bottomMargin=26).build([Paragraph("Deals · Business Suite", styles["Title"]), Spacer(1, 12), report])
        content, mime = output.getvalue(), "application/pdf"
    else:
        output = io.StringIO(); csv.writer(output, delimiter="\t" if format == "clipboard" else ",").writerows(table)
        content, mime = output.getvalue().encode("utf-8-sig"), "text/tab-separated-values" if format == "clipboard" else "text/csv"
    return Response(content, media_type=mime, headers={"Content-Disposition": f'attachment; filename="deals.{format if format != "clipboard" else "tsv"}"'})
