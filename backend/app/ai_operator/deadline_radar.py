"""Typed, deterministic artifact over the existing authorized PMS task source.

Only configuration is saved by the workbench. Task data is read afresh, never
stored in an artifact snapshot or sent to a model merely to render the radar.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.ai_operator.suite_tools import Strict
from app.core.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter(prefix='/workspace', tags=['AI workspace'])


class RadarConfig(Strict):
    horizon_days: int = Field(default=30, ge=1, le=365, strict=True)
    include_completed: bool = Field(default=False, strict=True)
    timezone: str = 'Asia/Kolkata'

    @model_validator(mode='after')
    def timezone_exists(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Choose a valid timezone') from None
        return self


def build_radar(tasks, today: date, config: RadarConfig):
    end = today + timedelta(days=config.horizon_days)
    counts = dict(overdue=0, today=0, upcoming=0, undated=0, later=0, completed=0)
    rows = []
    for task in tasks:
        completed = (task.status or '').strip().lower() in {'done', 'completed', 'cancelled', 'canceled', 'closed'}
        if completed:
            counts['completed'] += 1
            if not config.include_completed:
                continue
        due = task.due_date
        bucket = ('completed' if completed else 'undated' if due is None else
                  'overdue' if due < today else 'today' if due == today else
                  'upcoming' if due <= end else 'later')
        if not completed:
            counts[bucket] += 1
        if bucket == 'later':
            continue
        rows.append({'id': task.id, 'task_key': task.task_key, 'title': task.title,
                     'status': task.status, 'priority': task.priority,
                     'due_date': due.isoformat() if due else None,
                     'days_remaining': (due - today).days if due else None,
                     'bucket': bucket, 'project_id': task.project_id})
    rows.sort(key=lambda row: (row['bucket'] == 'completed', row['due_date'] or '9999-12-31', row['id']))
    return {'today': today.isoformat(), 'through': end.isoformat(), 'counts': counts, 'items': rows}


@router.get('/deadline-radar')
def deadline_radar(project_id: int = Query(gt=0), horizon_days: int = Query(30, ge=1, le=365),
                   include_completed: bool = False, timezone: str = 'Asia/Kolkata',
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from fastapi import HTTPException
    from app.ai_operator.workbench import access
    from app.apps.project_management.models import PMSTask
    try:
        config = RadarConfig(horizon_days=horizon_days, include_completed=include_completed, timezone=timezone)
    except ValueError:
        raise HTTPException(422, 'Invalid Deadline Radar configuration') from None
    project, _ = access(db, user, project_id)
    # Match the canonical project task source: project permission + nondeleted
    # tasks. Bound the read and disclose incomplete coverage rather than claiming
    # company-wide absence. Earliest dated work takes precedence over undated work.
    tasks = db.query(PMSTask).filter_by(project_id=project.id, deleted_at=None).order_by(
        PMSTask.due_date.is_(None), PMSTask.due_date, PMSTask.id).limit(2001).all()
    result = build_radar(tasks[:2000], datetime.now(ZoneInfo(config.timezone)).date(), config)
    return {**result, 'project': {'id': project.id, 'name': project.name, 'workspace_id': project.workspace_id},
            'config': config.model_dump(), 'coverage': {'scanned': min(len(tasks), 2000),
            'complete': len(tasks) <= 2000, 'limit': 2000}, 'source': 'PMS project tasks',
            'generated_at': datetime.now(ZoneInfo(config.timezone)).isoformat()}
