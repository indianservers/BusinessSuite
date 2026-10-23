"""One persisted timer per user, with atomic stop and stale-session protection."""
import math
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import get_project_for_action, get_task_project_for_action
from .models import PMSRunningTimer, PMSTimeLog, PMSActivity

router = APIRouter()


class StartInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int = Field(gt=0)
    task_id: int | None = None
    session_key: UUID
    timezone: str = Field(default="UTC", max_length=80)
    description: str = Field(default="", max_length=10000)
    is_billable: bool = False


class StopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_key: UUID


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def output(row):
    return {"active": row.active, "session_key": row.session_key, "project_id": row.project_id,
            "task_id": row.task_id, "started_at": utc(row.started_at), "timezone": row.timezone,
            "description": row.description, "is_billable": row.is_billable, "log_id": row.log_id}


@router.get("/timer")
def get_timer(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(PMSRunningTimer, user.id)
    return output(row) if row and row.active else None


@router.post("/timer/start")
def start_timer(data: StartInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_for_action(db, data.project_id, user, "log_time")
    if data.task_id:
        task, _ = get_task_project_for_action(db, data.task_id, user, "log_time")
        if task.project_id != data.project_id:
            raise HTTPException(422, "Task must belong to the selected project")
    try:
        ZoneInfo(data.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Choose a valid time zone")
    row = db.query(PMSRunningTimer).filter_by(user_id=user.id).with_for_update().first()
    if row and row.active:
        if row.session_key == str(data.session_key):
            return output(row)
        raise HTTPException(409, "Stop your current timer before starting another")
    if row and row.session_key == str(data.session_key):
        raise HTTPException(409, "This timer session has already ended")
    row = row or PMSRunningTimer(user_id=user.id)
    for key in ("project_id", "task_id", "timezone", "description", "is_billable"):
        setattr(row, key, getattr(data, key))
    row.session_key, row.started_at, row.active, row.log_id = str(data.session_key), datetime.now(timezone.utc), True, None
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A timer was started concurrently; refresh your timer")
    return output(row)


@router.post("/timer/stop")
def stop_timer(data: StopInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(PMSRunningTimer).filter_by(user_id=user.id).with_for_update().first()
    if not row or row.session_key != str(data.session_key):
        raise HTTPException(409, "Timer session changed; refresh before stopping")
    if not row.active:
        return {"log_id": row.log_id, "active": False}
    get_project_for_action(db, row.project_id, user, "log_time")
    if row.task_id:
        get_task_project_for_action(db, row.task_id, user, "log_time")
    end = datetime.now(timezone.utc)
    start = utc(row.started_at)
    minutes = max(1, math.ceil((end - start).total_seconds() / 60))
    log = PMSTimeLog(user_id=user.id, project_id=row.project_id, task_id=row.task_id,
        log_date=start.astimezone(ZoneInfo(row.timezone)).date(), start_time=start, end_time=end,
        duration_minutes=minutes, description=row.description, is_billable=row.is_billable,
        approval_status="Pending")
    db.add(log)
    db.flush()
    row.active, row.log_id = False, log.id
    db.add(PMSActivity(project_id=row.project_id, task_id=row.task_id, actor_user_id=user.id,
        action="time.logged", entity_type="time_log", entity_id=log.id, summary=f"Timer logged {minutes} minutes"))
    db.commit()
    return {"log_id": log.id, "active": False, "duration_minutes": minutes}


@router.post("/timer/discard")
def discard_timer(data: StopInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(PMSRunningTimer).filter_by(user_id=user.id).with_for_update().first()
    if not row or row.session_key != str(data.session_key):
        raise HTTPException(409, "Timer session changed; refresh first")
    row.active = False
    db.commit()
    return {"active": False}
