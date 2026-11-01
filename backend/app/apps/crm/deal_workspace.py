"""Reusable deal workspace queries and validation. All queries retain CRM visibility."""
import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, or_, and_, case, literal, union_all, select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_db, RequirePermission
from app.models.user import User
from . import lead_management as lm
from .models import CRMDeal, CRMPipelineStage, CRMTimelineEvent, CRMDealCollaborator
from .productivity import rows, READ, allowed

router = APIRouter(prefix="/deal-workspace", tags=["CRM deal workspace"])


@router.get("/permissions")
def permissions(db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    """Field-level capabilities for the current authorized CRM actor."""
    lm.core()._assert_entity_permission("deals", user, "view")
    return {"can_manage": allowed(user, "deals", "manage"), "can_assign": lm.core()._crm_can_assign_beyond_self(user), "can_manual_probability": lm.core()._crm_can_assign_beyond_self(user), "can_manage_pipelines": allowed(user, "pipelines", "manage")}


class Planning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qualification: dict[str, str | bool] = Field(default_factory=dict, max_length=30)
    financial: dict[str, str | float] = Field(default_factory=dict, max_length=20)
    dates: dict[str, str] = Field(default_factory=dict, max_length=15)
    milestones: list[dict[str, str]] = Field(default_factory=list, max_length=50)
    interest: str = Field(default="", max_length=2000)
    internal_notes: str = Field(default="", max_length=16000)
    closure: dict[str, str | bool | float] = Field(default_factory=dict, max_length=20)


class StagePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed_next_ids: list[int] = Field(default_factory=list, max_length=100)
    required: list[Literal["company_id", "contact_id", "amount", "expected_close_date", "next_follow_up_at", "lead_source"]] = Field(default_factory=list)
    approval_required: bool = False
    stagnation_days: int = Field(default=14, ge=1, le=365)


def guard(db, user, data, record=None):
    """Used by the existing create/update/import paths, not just the new UI."""
    crm = lm.core()
    org = crm._organization_id(db, user)
    for key in ("amount", "discount_amount", "expected_revenue"):
        if key in data and data[key] is not None:
            value = Decimal(str(data[key]))
            if not value.is_finite() or not 0 <= value <= Decimal("9999999999.99"):
                raise HTTPException(422, f"{key.replace('_', ' ').title()} must be a nonnegative supported monetary value")
    if "probability" in data and not 0 <= (data["probability"] or 0) <= 100:
        raise HTTPException(422, "Probability must be between 0 and 100")
    if "currency" in data:
        currency = str(data["currency"] or "").upper()
        if len(currency) != 3 or not currency.isalpha() or not currency.isascii():
            raise HTTPException(422, "Choose a three-letter currency code")
        data["currency"] = currency
        if record and record.catalog_items and currency != record.currency and "catalog_items" not in data:
            raise HTTPException(422, "Replace the catalog lines when changing currency; no automatic currency conversion is applied")
    if "priority" in data and data["priority"] not in {"Low", "Medium", "High", "Critical"}:
        raise HTTPException(422, "Choose a valid deal priority")
    if "deal_type" in data and data["deal_type"] not in {"New Business", "Existing Business", "Renewal", "Upsell", "Cross-sell"}:
        raise HTTPException(422, "Choose a valid deal type")
    if "planning" in data:
        try:
            planning = Planning.model_validate(data["planning"] or {})
            for key, value in planning.financial.items():
                if key in {"one_time_revenue", "recurring_revenue", "estimated_cost", "tax_rate", "contract_months"} and value != "":
                    number = Decimal(str(value))
                    if not number.is_finite() or number < 0 or number > Decimal("9999999999.99"):
                        raise ValueError()
                    if key == "tax_rate" and number > 100:
                        raise ValueError()
            for value in planning.dates.values():
                if value:
                    date.fromisoformat(value)
            for milestone in planning.milestones:
                if milestone.get("date"):
                    date.fromisoformat(milestone["date"])
            data["planning"] = planning.model_dump()
        except (ValidationError, ValueError, ArithmeticError):
            raise HTTPException(422, "Check the planning dates, financial values, and qualification details")
    for field, entity in (("company_id", "companies"), ("contact_id", "contacts")):
        if data.get(field) and (not record or data[field] != getattr(record, field)):
            crm._assert_record_visible(db, crm._get_resource(entity), data[field], org, user)
    if data.get("assigned_team_id"):
        crm._get_record(db, crm._get_resource("teams"), data["assigned_team_id"], org)
        if not crm._crm_can_assign_beyond_self(user) and data["assigned_team_id"] not in crm._crm_user_scope(db, user)["team_ids"]:
            raise HTTPException(403, "Choose a sales team within your permitted workspace scope")
    owner = data.get("owner_user_id")
    if owner and (not record or owner != record.owner_user_id):
        candidate = db.get(User, owner)
        from .lead_assignment import tenant
        if not candidate or not candidate.is_active or tenant(candidate) != org:
            raise HTTPException(422, "Choose an active owner in this organization")
        from .lead_assignment import ineligible_reason, employee_for_user
        eligibility = ineligible_reason(candidate, org, employee_for_user(db, candidate), {"crm_view", "crm_manage", "crm_admin", "crm_deals_view", "crm_deals_manage"})
        if eligibility: raise HTTPException(422, eligibility)
        if not allowed(candidate, "deals", "view"):
            raise HTTPException(422, "The selected owner needs CRM deal access")
    stage_id = data.get("stage_id", getattr(record, "stage_id", None))
    stage = db.query(CRMPipelineStage).filter_by(id=stage_id, organization_id=org, deleted_at=None).first() if stage_id else None
    if not stage:
        return  # Existing pipeline validator produces the canonical error.
    if not stage.active:
        raise HTTPException(422, "Choose an active pipeline stage")
    destination = "Won" if stage.is_won or stage.stage_type == "won" else "Lost" if stage.is_lost or stage.stage_type == "lost" else "Open"
    if "status" in data and data["status"] != destination:
        raise HTTPException(422, "Closed status must match the pipeline's Won or Lost stage")
    moving = not record or stage.id != record.stage_id
    if record and moving and record.status in {"Won", "Lost"} and not crm._crm_can_assign_beyond_self(user):
        raise HTTPException(403, "A sales manager must authorize reopening a closed deal")
    if record and moving:
        source = db.get(CRMPipelineStage, record.stage_id)
        next_ids = (source.policy_json or {}).get("allowed_next_ids", []) if source else []
        if next_ids and stage.id not in next_ids:
            raise HTTPException(422, "This stage transition is not allowed by the pipeline")
    if moving:
        policy = stage.policy_json or {}
        missing = [key for key in policy.get("required", []) if data.get(key, getattr(record, key, None)) in (None, "", 0)]
        if missing:
            raise HTTPException(422, "Complete the stage requirements: " + ", ".join(key.replace("_", " ") for key in missing))
        if policy.get("approval_required"):
            from .models import CRMApprovalRequest
            approved = record and db.query(CRMApprovalRequest).filter_by(organization_id=org, entity_type="deal", entity_id=record.id).order_by(CRMApprovalRequest.submitted_at.desc(), CRMApprovalRequest.id.desc()).first()
            if not approved or approved.status != "approved":
                raise HTTPException(422, "This stage requires an approved deal approval request")
        if destination == "Lost" and len(str(data.get("lost_reason", getattr(record, "lost_reason", "")) or "").strip()) < 5:
            raise HTTPException(422, "Provide a meaningful lost reason of at least five characters")
        data["status"] = destination
        if "probability" not in data:
            data["probability"] = stage.probability
    if "amount" in data or "probability" in data:
        data["expected_revenue"] = (Decimal(str(data.get("amount", getattr(record, "amount", 0)) or 0)) * Decimal(str(data.get("probability", getattr(record, "probability", 0)) or 0)) / 100).quantize(Decimal("0.01"))
    if "probability" in data and data["probability"] != stage.probability and not crm._crm_can_assign_beyond_self(user):
        raise HTTPException(403, "Manual probability overrides require a sales manager")


def filtered(db, user, search="", currency="", pipeline_id=None, owner_id=None, stage_id=None, status="", priority="", deal_type="", start=None, end=None, no_next=False, industry="", source="", team_id=None):
    q = rows(db, user, "deals")
    if search:
        matches = [CRMDeal.name.ilike(f"%{search}%"), CRMDeal.description.ilike(f"%{search}%")]
        from .models import CRMCompany, CRMContact
        if allowed(user, "companies", "view"):
            matches.append(CRMDeal.company_id.in_(rows(db, user, "companies").with_entities(CRMCompany.id).filter(CRMCompany.name.ilike(f"%{search}%"))))
        if allowed(user, "contacts", "view"):
            matches.append(CRMDeal.contact_id.in_(rows(db, user, "contacts").with_entities(CRMContact.id).filter(or_(CRMContact.full_name.ilike(f"%{search}%"), CRMContact.email.ilike(f"%{search}%")))))
        q = q.filter(or_(*matches))
    for field, value in (("currency", currency), ("pipeline_id", pipeline_id), ("owner_user_id", owner_id), ("stage_id", stage_id), ("status", status), ("priority", priority), ("deal_type", deal_type), ("industry", industry), ("assigned_team_id", team_id)):
        if value:
            q = q.filter(getattr(CRMDeal, field) == value)
    if source:
        q = q.filter(or_(CRMDeal.source == source, CRMDeal.lead_source == source))
    if start:
        q = q.filter(CRMDeal.expected_close_date >= start)
    if end:
        q = q.filter(CRMDeal.expected_close_date <= end)
    if no_next:
        q = q.filter(CRMDeal.next_follow_up_at.is_(None), CRMDeal.status == "Open")
    return q


def health(record, stage_entered=None):
    now = datetime.now(timezone.utc)
    def age(value):
        if not value:
            return None
        return max(0, (now - value.replace(tzinfo=value.tzinfo or timezone.utc)).days)
    age_days = age(record.created_at) or 0
    activity_gap = age(record.last_activity_at)
    stage_age = age(stage_entered or record.created_at) or 0
    threshold = (record.stage.policy_json or {}).get("stagnation_days", 14) if record.stage else 14
    reasons, penalty = [], 0
    if record.status == "Open":
        if record.next_follow_up_at and record.next_follow_up_at.replace(tzinfo=record.next_follow_up_at.tzinfo or timezone.utc) < now:
            reasons.append("Follow-up overdue"); penalty += 30
        if not record.next_follow_up_at:
            reasons.append("No next action scheduled"); penalty += 20
        if activity_gap is None:
            reasons.append("No recorded last activity"); penalty += 20
        elif activity_gap >= 14:
            reasons.append(f"No activity for {activity_gap} days"); penalty += 25
        if record.expected_close_date and record.expected_close_date < now.date():
            reasons.append("Expected closing date has passed"); penalty += 25
        if stage_age >= threshold:
            reasons.append(f"Current stage has exceeded its {threshold}-day stagnation threshold"); penalty += 15
        if age_days >= 90:
            reasons.append(f"Deal has been open {age_days} days"); penalty += 10
    score = max(0, 100 - penalty)
    level = "Critical" if score <= 30 else "At Risk" if score <= 50 else "Needs Attention" if score <= 75 else "Healthy"
    return {"score": score, "level": level, "reasons": reasons, "age_days": age_days, "stage_age_days": stage_age, "activity_gap_days": activity_gap,
            "definition": "100 minus 30 for overdue follow-up, 20 for no next action, 20 for no recorded activity or 25 for 14+ idle days, 25 for past closing date, 15 for a stage beyond its configured stagnation threshold, and 10 for age 90+ days. Closed deals have no open-work penalties."}


@router.get("/query")
def query(search: str = Query("", max_length=180), currency: str = "", pipeline_id: int | None = None, owner_id: int | None = None, stage_id: int | None = None, status: str = "", priority: str = "", deal_type: str = "", industry: str = "", source: str = "", team_id: int | None = None, start: date | None = None, end: date | None = None, no_next: bool = False, page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100), sort: str = "updated_at", direction: Literal["asc", "desc"] = "desc", db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    if start and end and start > end:
        raise HTTPException(422, "Start date must be before end date")
    q = filtered(db, user, search, currency, pipeline_id, owner_id, stage_id, status, priority, deal_type, start, end, no_next, industry, source, team_id)
    column = getattr(CRMDeal, sort) if sort in {"name", "amount", "probability", "priority", "expected_close_date", "created_at", "updated_at", "company_id", "currency", "stage_id", "owner_user_id", "status", "next_follow_up_at"} else CRMDeal.updated_at
    total = q.count()
    items = q.options(joinedload(CRMDeal.stage)).order_by(column.asc() if direction == "asc" else column.desc(), CRMDeal.id).offset((page - 1) * per_page).limit(per_page).all()
    entered = dict(db.query(CRMTimelineEvent.record_id, func.max(CRMTimelineEvent.occurred_at)).filter(CRMTimelineEvent.record_type == "deal", CRMTimelineEvent.event_type == "stage_change", CRMTimelineEvent.organization_id == lm.core()._organization_id(db, user), CRMTimelineEvent.record_id.in_([item.id for item in items])).group_by(CRMTimelineEvent.record_id).all()) if items else {}
    from .models import CRMCompany
    company_names = {item.id: item.name for item in rows(db, user, "companies").filter(CRMCompany.id.in_([deal.company_id for deal in items if deal.company_id])).all()} if items and allowed(user, "companies", "view") else {}
    from .lead_assignment import candidate_organization
    owner_names = {owner.id: owner.email for owner in db.query(User).filter(User.id.in_([deal.owner_user_id for deal in items if deal.owner_user_id])).all() if candidate_organization(owner) == lm.core()._organization_id(db, user)} if items else {}
    return {"items": [{**lm.core()._serialize(item), "company_name": company_names.get(item.company_id), "owner_name": owner_names.get(item.owner_user_id), "stage_name": item.stage.name if item.stage else None, "health": health(item, entered.get(item.id))} for item in items], "total": total, "page": page, "pages": (total + per_page - 1) // per_page, "can_manage": allowed(user, "deals", "manage"), "can_assign": lm.core()._crm_can_assign_beyond_self(user)}


@router.get("/summary")
def summary(currency: str = "", pipeline_id: int | None = None, owner_id: int | None = None, stage_id: int | None = None, status: str = "", priority: str = "", deal_type: str = "", industry: str = "", source: str = "", team_id: int | None = None, search: str = "", start: date | None = None, end: date | None = None, no_next: bool = False, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    q = filtered(db, user, search, currency, pipeline_id, owner_id, stage_id, status, priority, deal_type, start, end, no_next, industry, source, team_id)
    now = datetime.now(timezone.utc)
    month = now.date().replace(day=1)
    next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    opened = q.filter(CRMDeal.status == "Open")
    def count(condition):
        return q.filter(condition).count()
    money = opened.with_entities(CRMDeal.currency, func.sum(CRMDeal.amount), func.sum(CRMDeal.amount * CRMDeal.probability / 100)).group_by(CRMDeal.currency).all()
    forecast = opened.with_entities(CRMDeal.expected_close_date, CRMDeal.currency, func.sum(CRMDeal.amount), func.sum(CRMDeal.amount * CRMDeal.probability / 100), func.count(CRMDeal.id)).group_by(CRMDeal.expected_close_date, CRMDeal.currency).all()
    groups = {}
    for day, code, amount, weighted, number in forecast:
        key = (day.strftime("%Y-%m") if day else "Unscheduled", code or "Unknown")
        row = groups.setdefault(key, {"month": key[0], "currency": key[1], "amount": 0, "weighted": 0, "count": 0})
        row["amount"] += float(amount or 0); row["weighted"] += float(weighted or 0); row["count"] += number
    stages = q.with_entities(CRMDeal.stage_id, CRMDeal.currency, func.count(CRMDeal.id), func.sum(CRMDeal.amount)).group_by(CRMDeal.stage_id, CRMDeal.currency).all()
    breakdowns = {}
    for key, column in (("owner", CRMDeal.owner_user_id), ("pipeline", CRMDeal.pipeline_id), ("stage", CRMDeal.stage_id)):
        grouped = opened.with_entities(column, CRMDeal.currency, func.count(CRMDeal.id), func.sum(CRMDeal.amount), func.sum(CRMDeal.amount * CRMDeal.probability / 100)).group_by(column, CRMDeal.currency).all()
        breakdowns[key] = [{"id": identity, "currency": code or "Unknown", "count": number, "amount": float(amount or 0), "weighted": float(weighted or 0)} for identity, code, number, amount, weighted in grouped]
    closed = q.filter(CRMDeal.status.in_(["Won", "Lost"]))
    closed_count = closed.count()
    win_rate = round(q.filter(CRMDeal.status == "Won").count() / closed_count * 100, 2) if closed_count else None
    return {"counts": {"open": opened.count(), "closing_month": opened.filter(CRMDeal.expected_close_date >= month, CRMDeal.expected_close_date < next_month).count(), "won_month": count((CRMDeal.status == "Won") & (CRMDeal.closed_at >= datetime.combine(month, datetime.min.time())) & (CRMDeal.closed_at < datetime.combine(next_month, datetime.min.time()))), "lost_month": count((CRMDeal.status == "Lost") & (CRMDeal.closed_at >= datetime.combine(month, datetime.min.time())) & (CRMDeal.closed_at < datetime.combine(next_month, datetime.min.time()))), "overdue": opened.filter(CRMDeal.next_follow_up_at < now).count(), "without_activity": opened.filter(CRMDeal.last_activity_at.is_(None)).count(), "no_next_action": opened.filter(CRMDeal.next_follow_up_at.is_(None)).count()},
            "win_rate": win_rate, "breakdowns": breakdowns, "currencies": [{"currency": code or "Unknown", "pipeline": float(amount or 0), "weighted": float(weighted or 0)} for code, amount, weighted in money], "forecast": sorted(groups.values(), key=lambda item: (item["month"], item["currency"])), "stages": [{"stage_id": sid, "currency": code or "Unknown", "count": number, "amount": float(amount or 0)} for sid, code, number, amount in stages],
            "definitions": {"pipeline": "Sum of open deal amounts, separated by currency; no conversion.", "weighted": "Open deal amount multiplied by probability / 100.", "dates": "Date filters apply to expected closing date. Monthly wins/losses use actual closed_at in UTC. Forecast uses expected closing month.", "win_rate": "Won deals divided by Won plus Lost deals within the current filters; open deals are excluded. No closed deals means no rate.", "activity": "Without activity means no recorded last_activity_at timestamp. Overdue uses the current UTC instant."}}


@router.get("/duplicates")
def duplicates(name: str = Query(min_length=2, max_length=180), company_id: int | None = None, exclude_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    q = rows(db, user, "deals").filter(func.lower(CRMDeal.name) == name.strip().lower())
    if company_id:
        q = q.filter(CRMDeal.company_id == company_id)
    if exclude_id:
        q = q.filter(CRMDeal.id != exclude_id)
    return {"items": [{"id": item.id, "name": item.name, "status": item.status} for item in q.limit(10)]}


@router.get("/assignees")
def assignees(page: int = Query(1, ge=1), per_page: int = Query(100, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    from .lead_assignment import directory
    candidates, _ = directory(db, user, lm.core()._crm_can_assign_beyond_self(user), {"crm_view", "crm_manage", "crm_admin", "crm_deals_view", "crm_deals_manage"})
    candidates = [item for item in candidates if allowed(db.get(User, item["id"]), "deals", "view")]
    return {"items": candidates[(page - 1) * per_page:page * per_page], "total": len(candidates), "page": page, "pages": (len(candidates) + per_page - 1) // per_page}


@router.get("/teams")
def eligible_teams(page: int = Query(1, ge=1), per_page: int = Query(100, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    from .models import CRMTeam
    crm = lm.core(); crm._assert_entity_permission("deals", user, "view")
    query = db.query(CRMTeam).filter_by(organization_id=crm._organization_id(db, user), deleted_at=None, status="Active")
    if not crm._crm_can_assign_beyond_self(user): query = query.filter(CRMTeam.id.in_(crm._crm_user_scope(db, user)["team_ids"]))
    total = query.count()
    return {"items": [{"id": item.id, "name": item.name} for item in query.order_by(CRMTeam.name, CRMTeam.id).offset((page - 1) * per_page).limit(per_page)], "total": total, "page": page, "pages": (total + per_page - 1) // per_page}


@router.get("/export")
def export(format: Literal["csv", "xlsx"] = "csv", currency: str = "", pipeline_id: int | None = None, owner_id: int | None = None, stage_id: int | None = None, status: str = "", priority: str = "", deal_type: str = "", industry: str = "", source: str = "", team_id: int | None = None, search: str = "", start: date | None = None, end: date | None = None, no_next: bool = False, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    lm.core()._assert_entity_permission("deals", user, "view")
    q = filtered(db, user, search, currency, pipeline_id, owner_id, stage_id, status, priority, deal_type, start, end, no_next, industry, source, team_id)
    if q.count() > 20000:
        raise HTTPException(422, "Narrow the filters to export at most 20,000 deals")
    headers = ["ID", "Deal", "Currency", "Amount", "Probability", "Weighted value", "Stage ID", "Owner ID", "Expected close", "Priority", "Status"]
    def values():
        yield headers
        for item in q.order_by(CRMDeal.id).yield_per(500):
            name = "'" + item.name if item.name.lstrip().startswith(("=", "+", "-", "@")) else item.name
            yield [item.id, name, item.currency, float(item.amount or 0), item.probability, round(float(item.amount or 0) * (item.probability or 0) / 100, 2), item.stage_id, item.owner_user_id, str(item.expected_close_date or ""), item.priority, item.status]
    lm.core()._create_crm_audit_log(db, user_id=user.id, entity_type="deals", entity_id=None, action="EXPORT", description=f"Filtered {format} deal export", new_values={"count": q.count()})
    db.commit()
    if format == "xlsx":
        from openpyxl import Workbook
        book = Workbook(write_only=True); sheet = book.create_sheet("Deals")
        for row in values(): sheet.append(row)
        output = io.BytesIO(); book.save(output)
        return Response(output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="deals.xlsx"'})
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerows(values())
    return Response("\ufeff" + output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="deals.csv"'})


class CloseDeal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: Literal["Won", "Lost"]
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=2000)
    actual_close_date: date
    actual_value: Decimal = Field(ge=0, le=9999999999)
    currency: str = Field(min_length=3, max_length=3)
    quotation_id: int | None = None
    contract_reference: str = Field(default="", max_length=180)
    handover_notes: str = Field(default="", max_length=4000)
    competitor: str = Field(default="", max_length=180)
    reengagement_date: date | None = None
    onboarding: bool = False


class BulkChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[dict[str, int]] = Field(min_length=1, max_length=100)
    stage_id: int | None = None
    owner_user_id: int | None = None
    lost_reason: str = Field(default="", max_length=2000)


@router.post("/bulk")
def bulk(data: BulkChange, db: Session = Depends(get_db), user: User = Depends(RequirePermission("crm_manage", "crm_admin", "crm_deals_manage"))):
    if (data.stage_id is None) == (data.owner_user_id is None):
        raise HTTPException(422, "Choose one bulk change: stage or owner")
    crm = lm.core(); crm._assert_entity_permission("deals", user, "manage")
    if len({item.get("id") for item in data.records}) != len(data.records):
        raise HTTPException(422, "Select each deal only once")
    results = []
    for item in data.records:
        if set(item) != {"id", "version"}:
            raise HTTPException(422, "Each selected deal needs an ID and version")
        changes = {"expected_version": item["version"]}
        if data.stage_id is not None:
            changes["stage_id"] = data.stage_id
            if data.lost_reason: changes["lost_reason"] = data.lost_reason
        else:
            changes["owner_user_id"] = data.owner_user_id
        try:
            crm.update_record("deals", item["id"], crm.CRMRecordPayload(**changes), db, user)
            results.append({"id": item["id"], "saved": True})
        except HTTPException as error:
            # These whitelisted stage/owner changes fail validation before writes.
            # Do not roll back earlier successful per-record commits.
            db.expire_all()
            results.append({"id": item["id"], "saved": False, "message": error.detail if isinstance(error.detail, str) else "Stage requirements or permissions prevented this change"})
    return {"items": results, "definition": "Each deal is committed independently; failed records are retained for review. Version checks prevent duplicate retry updates."}


def visible_deal(db, user, ident):
    item = rows(db, user, "deals").filter(CRMDeal.id == ident).first()
    if not item: raise HTTPException(404, "Deal not found in your permitted scope")
    return item


@router.get("/{ident}/record")
def record_detail(ident: int, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    deal = visible_deal(db, user, ident)
    crm = lm.core()
    payload = {**crm._serialize(deal), "entity": "deals", "related": crm._related_for(db, "deals", deal, deal.organization_id, user), "customFields": crm._custom_fields_for(db, "deals", ident, deal.organization_id)}
    return secure_detail(db, user, payload)


@router.get("/{ident}/events")
def events(ident: int, history: bool = False, page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    deal = visible_deal(db, user, ident)
    crm = lm.core()
    audit_types = CRMTimelineEvent.event_type.in_(["field_change", "stage_change", "status_change", "owner_change", "collaborator_change", "system"])
    if not history:
        audit_types = or_(audit_types, and_(CRMTimelineEvent.event_type.in_(["call", "meeting", "whatsapp", "email"]), CRMTimelineEvent.metadata_json["sourceEntity"].as_string().is_(None)))
    audit = db.query(CRMTimelineEvent.id.label("id"), literal("history").label("source"), CRMTimelineEvent.occurred_at.label("at")).filter(CRMTimelineEvent.organization_id == deal.organization_id, CRMTimelineEvent.record_type == "deal", CRMTimelineEvent.record_id == ident, audit_types)
    queries = [audit.statement]
    if not history:
        for entity in ("activities", "notes", "tasks", "calls", "emails", "meetings"):
            if not allowed(user, entity, "view"): continue
            model = crm._get_resource(entity).model
            queries.append(rows(db, user, entity).filter(model.deal_id == ident).with_entities(model.id.label("id"), literal(entity).label("source"), model.created_at.label("at")).statement)
    communication = None
    if not history and (user.is_superuser or lm.core()._crm_permission_names(user).intersection({"communication_view", "communication_email_send"})):
        from app.apps.communication.models import CommunicationTimelineEvent
        communication = CommunicationTimelineEvent
        queries.append(db.query(communication.id.label("id"), literal("communication").label("source"), communication.created_at.label("at")).filter(communication.organization_id == deal.organization_id, communication.record_type == "deal", communication.record_id == ident).statement)
    combined = union_all(*queries).subquery() if len(queries) > 1 else audit.subquery()
    total = db.query(func.count()).select_from(combined).scalar()
    selected = db.execute(select(combined).order_by(combined.c.at.desc(), combined.c.source, combined.c.id.desc()).offset((page - 1) * per_page).limit(per_page)).mappings().all()
    items = []
    for entry in selected:
        if entry["source"] == "communication" and communication is not None:
            item = db.get(communication, entry["id"])
            items.append({"type": item.channel, "title": item.subject or item.event_type, "occurredAt": item.created_at, "record": {"description": item.summary, "status": item.event_type}})
        elif entry["source"] == "history":
            item = db.get(CRMTimelineEvent, entry["id"])
            items.append({"type": item.event_type, "title": item.title, "occurredAt": item.occurred_at, "record": crm._serialize(item)})
        else:
            model = crm._get_resource(entry["source"]).model
            item = db.get(model, entry["id"])
            title = "Internal note" if entry["source"] == "notes" else getattr(item, "title", None) or getattr(item, "subject", None) or entry["source"].title()
            items.append({"type": entry["source"], "title": title, "occurredAt": entry["at"], "record": crm._serialize(item)})
    return {"items": items, "total": total, "page": page, "pages": (total + per_page - 1) // per_page}


class CollaboratorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["Collaborator", "Secondary Owner", "Lead Originator", "Watcher"] = "Collaborator"
    watching: bool = True


@router.get("/{ident}/collaborators")
def collaborators(ident: int, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    deal = visible_deal(db, user, ident)
    entries = db.query(CRMDealCollaborator, User).join(User, CRMDealCollaborator.user_id == User.id).filter(CRMDealCollaborator.deal_id == ident, CRMDealCollaborator.organization_id == deal.organization_id).all()
    return {"items": [{"user_id": person.id, "name": person.email, "role": entry.role, "watching": entry.watching} for entry, person in entries], "can_assign": lm.core()._crm_can_assign_beyond_self(user)}


@router.put("/{ident}/collaborators/{user_id}")
def save_collaborator(ident: int, user_id: int, data: CollaboratorInput, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    crm = lm.core(); deal = visible_deal(db, user, ident)
    if not crm._crm_can_assign_beyond_self(user) and not (user_id == user.id and data.role == "Watcher"):
        raise HTTPException(403, "Manager authority is required to assign collaborators")
    db.refresh(deal, with_for_update=True)
    candidate = db.get(User, user_id)
    from .lead_assignment import tenant
    if not candidate or not candidate.is_active or tenant(candidate) != deal.organization_id or not allowed(candidate, "deals", "view"):
        raise HTTPException(422, "Choose an active CRM user in this organization")
    crm._assert_record_visible(db, crm._get_resource("deals"), ident, deal.organization_id, candidate)
    item = db.query(CRMDealCollaborator).filter_by(deal_id=ident, user_id=user_id, organization_id=deal.organization_id).first()
    if not item:
        item = CRMDealCollaborator(deal_id=ident, user_id=user_id, organization_id=deal.organization_id, created_by_user_id=user.id)
        db.add(item)
    item.role = data.role; item.watching = data.watching
    crm._create_timeline_activity(db, organization_id=deal.organization_id, entity_type="deal", entity_id=ident, activity_type="collaborator_change", title=f"{data.role} updated", body=f"User #{user_id}; notifications {'enabled' if data.watching else 'disabled'}", user_id=user.id)
    db.commit()
    return {"saved": True}


@router.delete("/{ident}/collaborators/{user_id}")
def remove_collaborator(ident: int, user_id: int, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    crm = lm.core(); deal = visible_deal(db, user, ident)
    if user_id != user.id and not crm._crm_can_assign_beyond_self(user):
        raise HTTPException(403, "Manager authority is required to remove another collaborator")
    db.query(CRMDealCollaborator).filter_by(deal_id=ident, user_id=user_id, organization_id=deal.organization_id).delete()
    crm._create_timeline_activity(db, organization_id=deal.organization_id, entity_type="deal", entity_id=ident, activity_type="collaborator_change", title="Collaborator removed", body=f"User #{user_id}", user_id=user.id)
    db.commit()
    return {"removed": True}


def notify_watchers(db, deal, actor):
    """In-app only, and recheck access when a watcher receives a notification."""
    from app.models.notification import Notification
    crm = lm.core()
    from .lead_assignment import candidate_organization
    entries = db.query(CRMDealCollaborator).filter_by(deal_id=deal.id, organization_id=deal.organization_id, watching=True).all()
    for entry in entries:
        if entry.user_id == actor.id: continue
        candidate = db.get(User, entry.user_id)
        if not candidate or not candidate.is_active or candidate_organization(candidate) != deal.organization_id or not allowed(candidate, "deals", "view"): continue
        try: crm._assert_record_visible(db, crm._get_resource("deals"), deal.id, deal.organization_id, candidate)
        except HTTPException: continue
        db.add(Notification(company_id=deal.organization_id, user_id=entry.user_id, module="crm", event_type="deal.updated", related_entity_type="deal", related_entity_id=deal.id, title="Watched deal updated", message=f"{deal.name} was updated by user #{actor.id} (revision {deal.version}).", channels=["in_app"]))


def secure_detail(db, user, payload):
    """A visible deal must not grant access to otherwise restricted child records."""
    related = payload.get("related", {})
    for key, entity in (("notes", "notes"), ("tasks", "tasks"), ("files", "files"), ("activities", "activities"), ("calls", "calls"), ("emails", "emails"), ("meetings", "meetings"), ("quotations", "quotations")):
        items = related.get(key)
        if not isinstance(items, list): continue
        if not allowed(user, entity, "view"):
            related[key] = []; continue
        model = lm.core()._get_resource(entity).model
        permitted = {item[0] for item in rows(db, user, entity).with_entities(model.id).filter(model.id.in_([entry.get("id") for entry in items])).all()}
        related[key] = [item for item in items if item.get("id") in permitted]
        if key == "files":
            related[key] = [{field: value for field, value in item.items() if field not in {"storage_path", "storagePath"}} for item in related[key]]
    for key, entity in (("account", "companies"), ("contact", "contacts")):
        item = related.get(key)
        if not item: continue
        if not allowed(user, entity, "view") or not rows(db, user, entity).filter(lm.core()._get_resource(entity).model.id == item["id"]).first():
            related[key] = None
    contacts = related.get("contacts", [])
    if contacts:
        if not allowed(user, "contacts", "view"): related["contacts"] = []
        else:
            from .models import CRMContact
            permitted = {item[0] for item in rows(db, user, "contacts").with_entities(CRMContact.id).filter(CRMContact.id.in_([link.get("contact_id") or link.get("contactId") for link in contacts])).all()}
            related["contacts"] = [link for link in contacts if (link.get("contact_id") or link.get("contactId")) in permitted]
    payload["related"] = related
    timeline = []
    for event in payload.get("timeline", []):
        entity = event.get("type")
        if entity in {"notes", "tasks", "files", "activities", "calls", "emails", "meetings", "quotations"}:
            if not allowed(user, entity, "view"): continue
            event_record = event.get("record", {})
            if event_record.get("id") and not rows(db, user, entity).filter(lm.core()._get_resource(entity).model.id == event_record["id"]).first(): continue
        timeline.append(event)
    payload["timeline"] = timeline
    return payload


@router.post("/{ident}/close")
def close(ident: int, data: CloseDeal, db: Session = Depends(get_db), user: User = Depends(RequirePermission("crm_manage", "crm_admin", "crm_deals_manage"))):
    crm = lm.core(); record = rows(db, user, "deals", lock=True).filter(CRMDeal.id == ident).first()
    if not record: raise HTTPException(404, "Deal not found")
    if record.status in {"Won", "Lost"}: raise HTTPException(409, "This deal is already closed")
    stage = db.query(CRMPipelineStage).filter_by(pipeline_id=record.pipeline_id, organization_id=record.organization_id, deleted_at=None, active=True).filter(or_(CRMPipelineStage.is_won.is_(True), CRMPipelineStage.stage_type == "won") if data.outcome == "Won" else or_(CRMPipelineStage.is_lost.is_(True), CRMPipelineStage.stage_type == "lost")).first()
    if not stage: raise HTTPException(422, f"Configure a Closed {data.outcome} stage in this pipeline first")
    if data.currency != record.currency: raise HTTPException(422, "Final currency must match this deal; update its financial information first")
    if record.catalog_items and data.actual_value != record.amount:
        raise HTTPException(422, "Update the catalog lines to match the final contract value before closing")
    if data.quotation_id:
        quote = crm._get_record(db, crm._get_resource("quotations"), data.quotation_id, record.organization_id)
        crm._assert_record_visible(db, crm._get_resource("quotations"), quote.id, record.organization_id, user)
        if quote.deal_id != ident: raise HTTPException(422, "Choose a quotation linked to this deal")
    planning = {**(record.planning or {}), "closure": data.model_dump(mode="json", exclude={"expected_version", "outcome", "actual_value"}, exclude_none=True)}
    corrections = {"stage_id": stage.id, "status": data.outcome, "amount": data.actual_value, "actual_close_date": data.actual_close_date, "planning": planning, "expected_version": data.expected_version, "probability": stage.probability, "win_reason" if data.outcome == "Won" else "lost_reason": data.reason}
    if data.onboarding or data.reengagement_date:
        from .models import CRMTask
        title = "Customer onboarding" if data.onboarding else "Review lost opportunity"
        db.add(CRMTask(organization_id=record.organization_id, owner_user_id=record.owner_user_id or user.id, deal_id=ident, title=title, description=data.handover_notes or data.reason, due_date=datetime.combine(data.reengagement_date or data.actual_close_date, datetime.min.time(), tzinfo=timezone.utc), status="To Do", created_by_user_id=user.id))
    return crm.update_record("deals", ident, crm.CRMRecordPayload(**corrections), db, user)


@router.get("/{ident}/insights")
def insights(ident: int, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*READ))):
    record = rows(db, user, "deals").filter(CRMDeal.id == ident).first()
    if not record:
        raise HTTPException(404, "Deal not found in your permitted scope")
    last_stage = db.query(func.max(CRMTimelineEvent.occurred_at)).filter_by(organization_id=record.organization_id, record_type="deal", record_id=record.id, event_type="stage_change").scalar()
    stage_entered = last_stage or record.created_at
    result = health(record, stage_entered)
    result["stage_name"] = record.stage.name if record.stage else "Unknown stage"
    result["pipeline_name"] = record.pipeline.name if record.pipeline else "Unknown pipeline"
    owner = db.get(User, record.owner_user_id) if record.owner_user_id else None
    result["owner_name"] = owner.email if owner else "Unassigned"
    result["stage_age_days"] = max(0, (datetime.now(timezone.utc) - stage_entered.replace(tzinfo=stage_entered.tzinfo or timezone.utc)).days) if stage_entered else None
    result["stage_age_basis"] = "Last recorded stage change, or creation time when no stage event exists"
    fields = (record.planning or {}).get("qualification", {})
    result["qualification_score"] = round(sum(bool(fields.get(key)) for key in ("budget_confirmed", "decision_authority", "business_need", "purchase_timeline", "decision_criteria", "champion", "economic_buyer")) / 7 * 100)
    return result


@router.put("/stage-policy/{ident}")
def stage_policy(ident: int, data: StagePolicy, db: Session = Depends(get_db), user: User = Depends(RequirePermission("crm_pipeline_manage", "crm_manage", "crm_admin"))):
    crm = lm.core(); crm._assert_entity_permission("pipelines", user, "manage")
    stage = crm._get_record(db, crm._get_resource("pipeline-stages"), ident, crm._organization_id(db, user))
    for sid in data.allowed_next_ids:
        target = db.query(CRMPipelineStage).filter_by(id=sid, pipeline_id=stage.pipeline_id, organization_id=stage.organization_id, deleted_at=None).first()
        if not target:
            raise HTTPException(422, "Allowed stages must belong to the same pipeline")
    before = stage.policy_json
    stage.policy_json = data.model_dump()
    crm._create_crm_audit_log(db, user_id=user.id, entity_type="pipeline-stages", entity_id=ident, action="UPDATE", old_values={"policy": before}, new_values={"policy": stage.policy_json}, description="Pipeline stage policy updated")
    db.commit()
    return stage.policy_json
