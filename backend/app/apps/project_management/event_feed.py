"""Durable, access-scoped collaboration feed shared by all API instances."""
from datetime import datetime, timezone
import json
from sqlalchemy import text, func
from app.models.deployment import CollaborationEvent


def append_event(db, event):
    if not event.get("projectId"):
        return
    if db.get_bind().dialect.name == "postgresql":
        # Serialize append commits so a polling cursor never skips a late commit.
        db.execute(text("SELECT pg_advisory_xact_lock(211028003)"))
    row = CollaborationEvent(project_id=int(event["projectId"]), payload=json.loads(json.dumps(event, default=str)),
                             created_at=datetime.now(timezone.utc))
    db.add(row)
    db.commit()


def read_events(db, accessible_ids, cursor=None, limit=100, task_id=None, task_filter=None):
    high = db.query(func.max(CollaborationEvent.id)).scalar() or 0
    if cursor is None:
        return {"cursor": high, "events": []}
    rows = db.query(CollaborationEvent).filter(CollaborationEvent.id > cursor,
        CollaborationEvent.project_id.in_(accessible_ids)).order_by(CollaborationEvent.id).limit(limit).all()
    candidates = {int(row.payload["taskId"]) for row in rows if row.payload.get("taskId")}
    allowed = task_filter(candidates) if task_filter and candidates else candidates
    selected = [row for row in rows if (task_id is None or row.payload.get("taskId") == task_id) and (not row.payload.get("taskId") or int(row.payload["taskId"]) in allowed)]
    return {"cursor": rows[-1].id if rows else high,
            "events": [{**row.payload, "id": str(row.id)} for row in selected]}
