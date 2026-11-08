"""Owner-only CRM/PMS scheduled report links through the durable email outbox.

Every occurrence executes under current owner permissions. Emails contain no report
rows or public download tokens; opening the report rechecks current access.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.apps.automation.models import AutomationScheduledJob as Job
from app.services.email_dispatch import queue_email, user_can_receive
from app.core.config import settings
from app.access.service import activate_run_context, release_run_context, background_scope

class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    frequency: str = Field(default="daily", pattern="^(daily|weekly)$")
    at: str = Field(default="09:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    weekday: int = Field(default=0, ge=0, le=6)
    @model_validator(mode="after")
    def zone(self):
        try: ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError): raise ValueError("Choose an IANA timezone") from None
        return self


def next_occurrence(config, now):
    zone = ZoneInfo(config["timezone"]); local = now.astimezone(zone)
    hour, minute = map(int, config["at"].split(":"))
    for i in range(9):
        day = local.date() + timedelta(days=i)
        if config["frequency"] == "weekly" and day.weekday() != config["weekday"]: continue
        candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone).astimezone(timezone.utc)
        if candidate > now: return candidate
    raise ValueError("No next occurrence")


def authorize(db, domain, identity, user):
    from app.module_registry import is_app_enabled
    if domain not in {"crm", "pms"} or not is_app_enabled("crm" if domain == "crm" else "project_management"):
        raise HTTPException(404, "Report module is unavailable")
    if domain == "crm":
        from app.apps.crm.report_builder import _row
        from app.apps.crm.deal_grid import capabilities
        row = _row(db, identity, user)
        if not capabilities(user).get("export"): raise HTTPException(403, "Deal export permission is required for scheduled reporting")
        return row
    if domain == "pms":
        from app.apps.project_management.access import get_project_for_action
        return get_project_for_action(db, identity, user, "browse")
    raise HTTPException(404, "Report domain not found")


def _query(db, domain, identity, user):
    return db.query(Job).filter_by(job_type="domain_report", module_name="crm" if domain == "crm" else "project_management", record_type=domain, record_id=identity, created_by=user.id)


def payload(row):
    if not row: return None
    return {"id": row.id, **row.payload_json["schedule"], "next_run_at": row.run_at, "status": row.status, "last_error": row.last_error, "last_run_at": row.payload_json.get("last_run_at"), "last_outbox_id": row.payload_json.get("last_outbox_id")}


def get_schedule(domain: str, identity: int, db=Depends(get_db), user=Depends(get_current_user)):
    authorize(db, domain, identity, user)
    row = _query(db, domain, identity, user).first()
    result = payload(row)
    if result and result.get("last_outbox_id"):
        from app.models.email_outbox import EmailOutbox
        outbox = db.get(EmailOutbox, result["last_outbox_id"])
        result["delivery_status"] = outbox.status if outbox else None
    return result


def save_schedule(domain: str, identity: int, data: ScheduleInput, db=Depends(get_db), user=Depends(get_current_user)):
    source = authorize(db, domain, identity, user)
    from app.services.metrics.queries import company_id
    company = company_id(user)
    if not user_can_receive(db, user.id, user.email, company): raise HTTPException(422, "An active company email is required")
    from app.branches.models import BranchOwnership
    table = "analytics_reports" if domain == "crm" else "pms_projects"
    scope = db.query(BranchOwnership).filter_by(resource_table=table, resource_key=str(identity), company_id=company).first()
    if not scope: raise HTTPException(409, "Report branch scope cannot be verified")
    # Lock the source to serialize first-time upserts for this private owner schedule.
    db.query(type(source)).filter(type(source).id == source.id).with_for_update().first()
    row = _query(db, domain, identity, user).with_for_update().populate_existing().first()
    if not row:
        row = Job(job_type="domain_report", module_name="crm" if domain == "crm" else "project_management", record_type=domain, record_id=identity, organization_id=company, created_by=user.id, attempts=0)
        db.add(row)
    raw = dict(row.payload_json or {})
    raw.update(schedule=data.model_dump(), branch_id=scope.branch_id)
    row.payload_json = raw; row.status = "scheduled" if data.enabled else "paused"; row.last_error = None
    row.run_at = next_occurrence(raw["schedule"], datetime.now(timezone.utc))
    db.commit(); db.refresh(row); return payload(row)


@contextmanager
def owner_scope(db, row):
    user = db.query(User).filter_by(id=row.created_by).populate_existing().first()
    if not user or not user.is_active: raise HTTPException(403, "Schedule owner unavailable")
    activate_run_context(db, user, SimpleNamespace(scope_key=f"company:{row.organization_id}"))
    try:
        with background_scope(db, user, row.module_name, "view", branch_id=row.payload_json["branch_id"]):
            authorize(db, row.record_type, row.record_id, user)
            yield user
    finally: release_run_context(db)


def outbox_allowed(db, outbox):
    try:
        identity = int(outbox.event_key.split(":")[1]); row = db.get(Job, identity)
        if not row or row.job_type != "domain_report" or row.created_by != outbox.recipient_user_id or row.organization_id != outbox.organization_id: return False
        with owner_scope(db, row): return row.status != "paused"
    except Exception: return False


def dispatch(db, now=None, limit=10):
    now = now or datetime.now(timezone.utc); count = 0
    for _ in range(min(limit, 25)):
        row = db.query(Job).filter(Job.job_type == "domain_report", Job.status == "scheduled", Job.run_at <= now).order_by(Job.run_at, Job.id).with_for_update(skip_locked=True).first()
        if not row: break
        try:
            with owner_scope(db, row) as user:
                if row.record_type == "crm":
                    from app.apps.crm.report_builder import export
                    export(row.record_id, "csv", None, db, user)
                    path = "/crm/reports"
                else:
                    from app.apps.project_management.scheduling import export_variance
                    export_variance(row.record_id, None, "csv", db, user)
                    path = f"/pms/gantt?project={row.record_id}"
                if not user_can_receive(db, user.id, user.email, row.organization_id): raise HTTPException(403, "Recipient unavailable")
                occurrence = row.run_at.replace(tzinfo=timezone.utc) if row.run_at.tzinfo is None else row.run_at
                event_key=f"domain-report:{row.id}:{occurrence.isoformat()}"
                outbox = queue_email(db, recipient=user.email, user_id=user.id, organization_id=row.organization_id, module=row.module_name,
                    event_key=event_key, subject="Your scheduled report link is ready",
                    body="Your scheduled report was checked successfully. Sign in to open and export it:\n" + settings.FRONTEND_PUBLIC_URL.rstrip("/") + path + "\nThe link shows current authorized data when opened; no historical snapshot or attachment is included.")
                db.flush()
                if outbox is None:
                    from app.models.email_outbox import EmailOutbox
                    outbox = db.query(EmailOutbox).filter_by(event_key=event_key).one()
                row.payload_json = {**row.payload_json, "last_run_at": now.isoformat(), "last_outbox_id": outbox.id}
                row.last_error = None
                row.run_at = next_occurrence(row.payload_json["schedule"], now)
        except Exception:
            row.status = "blocked"; row.last_error = "Report, export access, branch or recipient unavailable; correct it and save the schedule to resume"
        db.commit(); count += 1
    return {"processed": count}


def router_for(domain):
    """Mount only the adapter belonging to the containing module."""
    adapter = APIRouter()

    @adapter.get(f"/{domain}/{{identity}}/delivery-schedule")
    def read(identity: int, db=Depends(get_db), user=Depends(get_current_user)):
        return get_schedule(domain, identity, db, user)

    @adapter.put(f"/{domain}/{{identity}}/delivery-schedule")
    def write(identity: int, data: ScheduleInput, db=Depends(get_db), user=Depends(get_current_user)):
        return save_schedule(domain, identity, data, db, user)

    return adapter
