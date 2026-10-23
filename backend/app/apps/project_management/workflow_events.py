"""Read-only integration feed. No external requests or workflow credentials."""
import json
from datetime import timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSActivity, PMSProject, PMSTask
from .workspaces import workspace_member

router = APIRouter()
EVENT_TYPES = ("task.created", "task.updated", "status.changed", "priority.changed", "assignee.changed", "schedule.changed", "automation.executed", "automation.skipped")
SAFE_FIELDS = {"status", "priority", "assignee_user_id", "assignee_user_ids", "start_date", "due_date", "work_type"}


@router.get("/workspaces/{workspace_id}/workflow-events")
def workflow_events(workspace_id: int, after_id: int = Query(0, ge=0), limit: int = Query(100, ge=2, le=200), replay: bool = True, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user, True)
    query = db.query(PMSActivity).join(PMSProject, PMSProject.id == PMSActivity.project_id).filter(PMSProject.workspace_id == workspace_id, PMSActivity.action.in_(EVENT_TYPES))
    # Replay recent IDs to tolerate delayed commits and consumer retries. Consumers
    # deduplicate event_id; next_cursor only advances over newly observed rows.
    overlap = list(reversed(query.filter(PMSActivity.id <= after_id).order_by(PMSActivity.id.desc()).limit(min(50, limit // 2)).all())) if replay and after_id else []
    remaining = limit - len(overlap)
    fresh = query.filter(PMSActivity.id > after_id).order_by(PMSActivity.id).limit(remaining + 1).all()
    has_more = len(fresh) > remaining
    fresh = fresh[:remaining]
    rows = overlap + fresh
    tasks = {task.id: task for task in db.query(PMSTask).filter(PMSTask.id.in_([row.task_id for row in rows if row.task_id]), PMSTask.deleted_at == None).all()}
    items = []
    for row in rows:
        task = tasks.get(row.task_id)
        metadata = json.loads(row.metadata_json or "{}")
        change = {key: {field: value for field, value in metadata.get(key, {}).items() if field in SAFE_FIELDS} for key in ("old_values", "new_values") if isinstance(metadata.get(key), dict)}
        timestamp = row.created_at.replace(tzinfo=timezone.utc) if row.created_at.tzinfo is None else row.created_at
        items.append({"event_id": f"pms:{workspace_id}:{row.id}", "id": row.id, "type": row.action, "occurred_at": timestamp.isoformat(), "project_id": row.project_id, "task_id": row.task_id, "actor_id": row.actor_user_id, "changes": change, "task": {"id": task.id, "key": task.task_key, "title": task.title, "work_type": task.work_type, "status": task.status, "priority": task.priority, "assignee_ids": task.assignee_user_ids, "start_date": task.start_date, "due_date": task.due_date} if task else None})
    return {"schema_version": "1", "workspace_id": workspace_id, "items": items, "next_cursor": fresh[-1].id if fresh else after_id, "has_more": has_more, "replayed": len(overlap)}
