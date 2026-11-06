"""Task work queues, applied before counting and pagination."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import func

from .models import CRMTask


def apply_task_queue(query, queue: str, timezone_name: str = "UTC", *, now=None):
    if queue not in {"all", "open", "completed", "overdue", "today", "week", "unscheduled"}:
        raise HTTPException(422, "Unknown task queue")
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Invalid task timezone")
    if queue == "all":
        return query
    closed = func.lower(func.trim(CRMTask.status)).in_(["done", "completed", "complete", "cancelled", "canceled"])
    if queue == "completed":
        return query.filter(func.lower(func.trim(CRMTask.status)).in_(["done", "completed", "complete"]))
    query = query.filter(~closed)
    if queue == "open":
        return query
    if queue == "unscheduled":
        return query.filter(CRMTask.due_date.is_(None))
    local_date = (now or datetime.now(timezone.utc)).astimezone(zone).date()
    start = datetime.combine(local_date, time.min, tzinfo=zone).astimezone(timezone.utc)
    if queue == "overdue":
        return query.filter(CRMTask.due_date < start)
    end = datetime.combine(local_date + timedelta(days=7 if queue == "week" else 1), time.min, tzinfo=zone).astimezone(timezone.utc)
    return query.filter(CRMTask.due_date >= start, CRMTask.due_date < end)
