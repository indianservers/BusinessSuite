"""Scheduling helpers for CRM calls and meetings; reuse CRM visibility and writes."""
from datetime import datetime, time, timedelta, timezone
import hashlib
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import get_db, RequirePermission
from .models import CRMCallLog, CRMMeeting

router = APIRouter(prefix="/engagements", tags=["CRM engagements"])


class FollowUpInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=220)
    due: datetime


@router.post("/{kind}/{identity}/follow-up", status_code=201)
def follow_up(kind: Literal["meetings", "calls"], identity: int, data: FollowUpInput, db: Session = Depends(get_db), user=Depends(RequirePermission("crm_manage", "crm_admin", "crm_activities_manage"))):
    crm = core()
    crm._assert_entity_permission(kind, user, "view")
    crm._assert_entity_permission("tasks", user, "manage")
    org = crm._organization_id(db, user)
    resource = crm._get_resource(kind)
    record = crm._get_record(db, resource, identity, org)
    crm._assert_record_visible(db, resource, identity, org, user)
    due = utc(data.due)
    # Retry-safe within this actor's task-import uniqueness boundary.
    digest = hashlib.sha256(f"{kind}:{identity}:{data.title}:{due.isoformat()}".encode()).hexdigest()
    links = {key: getattr(record, key) for key in ("lead_id", "contact_id", "company_id", "deal_id") if getattr(record, key, None)}
    for key, value in links.items():
        crm._assert_record_visible(db, crm._get_resource(crm.RELATED_RESOURCE_BY_FIELD[key]), value, org, user)
    return crm.create_record("tasks", crm.CRMRecordPayload.model_validate({
        "title": data.title, "due_date": due.isoformat(), "status": "To Do", "priority": "Medium",
        "description": f"Follow-up from {kind[:-1]} #{identity}: {getattr(record, 'title', None) or getattr(record, 'outcome', None) or 'Customer conversation'}",
        "owner_user_id": user.id, "import_key": f"engagement:{digest}",
        "task_details": {"workType": "Follow-up", "relatedRecord": f"{kind} #{identity}", "sourceEntity": kind, "sourceId": identity}, **links,
    }), db, user)


def core():
    from .api import router as crm
    return crm


def utc(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(422, "Enter a valid date and time")
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def validate_engagement(model, values, record=None):
    if model is CRMMeeting:
        start = utc(values.get("start_time", getattr(record, "start_time", None)))
        end = utc(values.get("end_time", getattr(record, "end_time", None)))
        if not start or not end or end <= start:
            raise HTTPException(422, "Meeting end must be after its start")
    elif model is CRMCallLog and values.get("duration_seconds") is not None:
        if values["duration_seconds"] < 0:
            raise HTTPException(422, "Call duration cannot be negative")


def apply_engagement_view(query, model, view, timezone_name="UTC", now=None):
    if view not in {"all", "today", "upcoming", "past"}:
        raise HTTPException(422, "Unknown engagement view")
    try:
        zone = ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError):
        raise HTTPException(422, "Choose a valid time zone")
    if view == "all":
        return query
    at = now or datetime.now(timezone.utc)
    field = model.start_time if model is CRMMeeting else model.call_time
    if view == "today":
        day = at.astimezone(zone).date()
        start = datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc)
        end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
        return query.filter(field >= start, field < end)
    if view == "upcoming":
        query = query.filter(field >= at)
        if model is CRMMeeting:
            query = query.filter(~func.lower(func.coalesce(CRMMeeting.status, "")).in_(["cancelled", "canceled", "completed", "done"]))
        return query
    return query.filter(field < at)


@router.get("/permissions")
def permissions(user=Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "crm_activities_view", "crm_activities_manage"))):
    result = {}
    for entity in ("meetings", "calls"):
        result[entity] = {}
        for action in ("view", "manage"):
            try:
                core()._assert_entity_permission(entity, user, action)
                result[entity][action] = True
            except HTTPException:
                result[entity][action] = False
    return result


@router.get("/availability")
def availability(start: datetime, end: datetime, exclude_id: int | None = Query(None, gt=0), db: Session = Depends(get_db), user=Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "crm_activities_view", "crm_activities_manage"))):
    crm = core()
    crm._assert_entity_permission("meetings", user, "view")
    start, end = utc(start), utc(end)
    if end <= start or (end - start) > timedelta(days=31):
        raise HTTPException(422, "Choose an interval between zero and 31 days")
    resource = crm._get_resource("meetings")
    query = crm._apply_record_visibility(crm._base_query(db, resource, crm._organization_id(db, user)), resource, user, db)
    query = query.filter(CRMMeeting.owner_user_id == user.id, CRMMeeting.start_time < end, CRMMeeting.end_time > start, ~func.lower(func.coalesce(CRMMeeting.status, "")).in_(["cancelled", "canceled", "completed", "done"]))
    if exclude_id:
        query = query.filter(CRMMeeting.id != exclude_id)
    total = query.count()
    return {"scope": "Your visible meetings", "total": total, "items": [{"id": m.id, "title": m.title, "start": utc(m.start_time), "end": utc(m.end_time)} for m in query.order_by(CRMMeeting.start_time, CRMMeeting.id).limit(20)]}
