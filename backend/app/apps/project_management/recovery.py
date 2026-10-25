"""Server-owned savepoints, scoped exports, and conflict-aware task undo/redo."""

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSWorkspace, PMSProject, PMSTask, PMSWorkspaceMember, PMSActivity
from .recovery_models import RecoveryChange, RecoveryPoint, RecoveryPolicy
from .workspaces import workspace_member

router = APIRouter()
TASK_FIELDS = (
    "title",
    "description",
    "status",
    "priority",
    "start_date",
    "due_date",
    "estimated_hours",
    "story_points",
    "is_client_visible",
    "is_blocking",
    "position",
    "deleted_at",
    "completed_at",
    "column_id",
    "board_id",
    "assignee_user_id",
    "assignee_user_ids",
)


def ready(value):
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, datetime):
        return (
            value.astimezone(timezone.utc).replace(tzinfo=None)
            if value.tzinfo
            else value
        ).isoformat()
    return jsonable_encoder(value, custom_encoder={Decimal: str})


def task_state(task):
    result = {key: ready(getattr(task, key)) for key in TASK_FIELDS}
    result["_context"] = {
        column.name: ready(getattr(task, column.name))
        for column in PMSTask.__table__.columns
        if column.name not in {*TASK_FIELDS, "created_at", "updated_at"}
    }
    return result


def digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def record_edit(db, project, task, user, before):
    if not project.workspace_id or before == task_state(task):
        return
    # A fresh edit starts a new branch. Old redo entries remain as evidence.
    db.query(RecoveryChange).filter_by(
        workspace_id=project.workspace_id, actor_id=user.id, state="undone"
    ).update({"state": "discarded"})
    if before.get("_context") != task_state(task).get("_context"):
        # Structural changes are not partially reversed. They act as a history barrier.
        return
    if task.recurrence_rule and before.get("status") != task.status:
        # Completing a recurring task can spawn another task; never pretend a
        # single-record undo reverses that multi-record workflow.
        return
    db.add(
        RecoveryChange(
            workspace_id=project.workspace_id,
            task_id=task.id,
            actor_id=user.id,
            before=before,
            after=task_state(task),
            state="applied",
        )
    )


def event(db, project, task, user, action):
    db.add(
        PMSActivity(
            project_id=project.id,
            task_id=task.id,
            actor_user_id=user.id,
            action=action,
            entity_type="task",
            entity_id=task.id,
            summary=f"{action}: {task.task_key}",
        )
    )


def apply_state(db, task, state, workspace_id):
    ids = state.get("assignee_user_ids", [])
    eligible = {
        uid
        for (uid,) in db.query(User.id)
        .join(PMSWorkspaceMember, PMSWorkspaceMember.user_id == User.id)
        .filter(
            PMSWorkspaceMember.workspace_id == workspace_id,
            PMSWorkspaceMember.role != "Guest",
            User.is_active.is_(True),
        )
        .all()
    }
    if set(ids) - eligible:
        raise HTTPException(
            409,
            "A saved assignee no longer has workspace access. Resolve membership before recovery.",
        )
    from .models import PMSBoard, PMSBoardColumn

    board = db.get(PMSBoard, state.get("board_id")) if state.get("board_id") else None
    column = (
        db.get(PMSBoardColumn, state.get("column_id"))
        if state.get("column_id")
        else None
    )
    if (
        (board and board.project_id != task.project_id)
        or (state.get("board_id") and not board)
        or (
            state.get("column_id")
            and (not column or not board or column.board_id != board.id)
        )
    ):
        raise HTTPException(409, "Saved board or column is no longer available")
    for key in TASK_FIELDS:
        value = state[key]
        if value and key in {"start_date", "due_date"}:
            value = date.fromisoformat(value)
        if value and key in {"deleted_at", "completed_at"}:
            value = datetime.fromisoformat(value)
        if value is not None and key == "estimated_hours":
            value = Decimal(str(value))
        setattr(task, key, value)
    db.flush()
    if task.sprint_id:
        from .api.router import _sync_sprint_rollups
        from .models import PMSSprint

        sprint = db.get(PMSSprint, task.sprint_id)
        if sprint:
            _sync_sprint_rollups(db, sprint)


@router.get("/workspaces/{workspace_id}/recovery/history")
def history(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _, member = workspace_member(db, workspace_id, user)
    if member.role == "Guest":
        raise HTTPException(403, "Task editing access required")
    rows = (
        db.query(RecoveryChange)
        .filter_by(workspace_id=workspace_id, actor_id=user.id)
        .order_by(RecoveryChange.id.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": row.id,
            "task_id": row.task_id,
            "title": row.after.get("title"),
            "state": row.state,
            "created_at": row.created_at,
            "fields": [key for key in TASK_FIELDS if row.before[key] != row.after[key]],
        }
        for row in rows
    ]


@router.post("/workspaces/{workspace_id}/recovery/actions/{direction}")
def undo_redo(
    workspace_id: int,
    direction: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if direction not in {"undo", "redo"}:
        raise HTTPException(404, "Unknown recovery action")
    workspace_member(db, workspace_id, user)
    # Serialize recovery actions per workspace, including across workers.
    db.query(PMSWorkspace).filter_by(id=workspace_id).with_for_update().one()
    query = db.query(RecoveryChange).filter_by(
        workspace_id=workspace_id,
        actor_id=user.id,
        state="applied" if direction == "undo" else "undone",
    )
    row = (
        query.order_by(
            RecoveryChange.id.desc() if direction == "undo" else RecoveryChange.id.asc()
        )
        .with_for_update()
        .first()
    )
    if not row:
        raise HTTPException(409, f"Nothing to {direction}")
    task = db.query(PMSTask).filter_by(id=row.task_id).with_for_update().first()
    project = db.get(PMSProject, task.project_id) if task else None
    from .access import can_access_project

    if (
        not project
        or project.workspace_id != workspace_id
        or project.deleted_at
        or not can_access_project(db, project, user, "manage_tasks")
    ):
        raise HTTPException(403, "Current task editing access required")
    expected, target = (
        (row.after, row.before) if direction == "undo" else (row.before, row.after)
    )
    if task_state(task) != expected:
        raise HTTPException(
            409,
            "Task changed since this edit. Recovery stopped to preserve newer work.",
        )
    apply_state(db, task, target, workspace_id)
    row.state = "undone" if direction == "undo" else "applied"
    event(db, project, task, user, f"task.{direction}")
    db.commit()
    from .api.router import _broadcast_realtime

    _broadcast_realtime(
        user,
        "task.updated",
        project_id=project.id,
        task_id=task.id,
        message=f"Task {direction}",
    )
    return {"id": row.id, "task_id": task.id, "state": row.state}


def workspace_export(db, workspace_id):
    """Export workspace-owned PMS rows, following child FKs, never global users/secrets."""
    from app.db.base_class import Base

    known = {"pms_workspaces": [{"id": workspace_id}]}
    result = {}
    private = {
        "pms_private_notes",
        "pms_private_note_revisions",
        "pms_private_note_attachments",
        "pms_private_note_task_links",
        "pms_direct_conversations",
        "pms_direct_messages",
        "pms_saved_filters",
        "pms_planner_preferences",
        "pms_calendar_events",
        "pms_dev_integrations",
        "pms_workspace_invitations",
    }
    tables = [
        t
        for t in Base.metadata.sorted_tables
        if t.name.startswith("pms_")
        and not t.name.startswith(("pms_recovery_", "pms_assistant_", "pms_chat_"))
        and t.name not in private
    ]
    remaining = list(tables)
    for _ in range(len(tables) + 1):
        advanced = False
        for table in remaining[:]:
            filters = []
            if table.name == "pms_workspaces":
                filters = [table.c.id == workspace_id]
            elif "workspace_id" in table.c:
                filters = [table.c.workspace_id == workspace_id]
            else:
                for fk in table.foreign_keys:
                    parent = fk.column.table.name
                    if parent in known and parent != table.name:
                        values = [
                            r[fk.column.name]
                            for r in known[parent]
                            if fk.column.name in r
                        ]
                        if values:
                            filters.append(fk.parent.in_(values))
            if not filters:
                continue
            rows = [
                dict(row)
                for row in db.execute(select(table).where(or_(*filters))).mappings()
            ]
            if table.name == "pms_workspace_entries":
                # Private dashboard definitions and personal tool state stay private.
                rows = [
                    row
                    for row in rows
                    if row["kind"]
                    in {
                        "note",
                        "chat",
                        "auto_rule",
                        "lib_goal",
                        "lib_template",
                        "lib_intake",
                    }
                ]
            known[table.name] = rows
            result[table.name] = ready(rows)
            remaining.remove(table)
            advanced = True
        if not advanced:
            break
    return {
        "format": "businesssuite-workspace-v1",
        "workspace_id": workspace_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "tables": result,
        "task_content": {
            str(t.id): task_state(t)
            for t in db.query(PMSTask)
            .join(PMSProject)
            .filter(PMSProject.workspace_id == workspace_id)
            .all()
        },
    }


def make_point(db, workspace_id, user_id, name, automatic=False):
    data = workspace_export(db, workspace_id)
    row = RecoveryPoint(
        workspace_id=workspace_id,
        actor_id=user_id,
        name=name,
        automatic=automatic,
        payload=data,
        checksum=digest(data),
    )
    db.add(row)
    db.flush()
    return row


class PointInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class PolicyInput(BaseModel):
    enabled: bool
    interval_hours: int = Field(default=24, ge=1, le=720)
    retain_automatic: int = Field(default=14, ge=2, le=90)


def point_info(row):
    return {
        "id": row.id,
        "name": row.name,
        "automatic": row.automatic,
        "created_at": row.created_at,
        "checksum": row.checksum,
        "tasks": len(row.payload["task_content"]),
        "rows": sum(len(rows) for rows in row.payload["tables"].values()),
    }


@router.get("/workspaces/{workspace_id}/recovery")
def points(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace_member(db, workspace_id, user, True)
    policy = db.get(RecoveryPolicy, workspace_id)
    return {
        "points": [
            point_info(row)
            for row in db.query(RecoveryPoint)
            .filter_by(workspace_id=workspace_id)
            .order_by(RecoveryPoint.id.desc())
            .limit(100)
            .all()
        ],
        "policy": {
            "enabled": policy.enabled if policy else False,
            "interval_hours": policy.interval_hours if policy else 24,
            "retain_automatic": policy.retain_automatic if policy else 14,
            "last_success_at": policy.last_success_at if policy else None,
        },
    }


@router.post("/workspaces/{workspace_id}/recovery/savepoints", status_code=201)
def savepoint(
    workspace_id: int,
    data: PointInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace_member(db, workspace_id, user, True)
    if not data.name.strip():
        raise HTTPException(422, "Savepoint name required")
    row = make_point(db, workspace_id, user.id, data.name.strip())
    db.commit()
    return point_info(row)


@router.put("/workspaces/{workspace_id}/recovery/policy")
def policy_update(
    workspace_id: int,
    data: PolicyInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace_member(db, workspace_id, user, True)
    policy = db.get(RecoveryPolicy, workspace_id)
    if not policy:
        policy = RecoveryPolicy(workspace_id=workspace_id, actor_id=user.id)
        db.add(policy)
    for key, value in data.model_dump().items():
        setattr(policy, key, value)
    policy.actor_id = user.id
    db.commit()
    return {"saved": True}


def saved_point(db, workspace_id, point_id):
    row = (
        db.query(RecoveryPoint)
        .filter_by(id=point_id, workspace_id=workspace_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Savepoint not found")
    if digest(row.payload) != row.checksum:
        raise HTTPException(409, "Savepoint integrity check failed")
    return row


@router.get("/workspaces/{workspace_id}/recovery/savepoints/{point_id}/download")
def download(
    workspace_id: int,
    point_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace_member(db, workspace_id, user, True)
    row = saved_point(db, workspace_id, point_id)
    return Response(
        json.dumps(row.payload),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="workspace-{workspace_id}-savepoint-{point_id}.json"',
            "Cache-Control": "no-store",
        },
    )


class RestoreInput(BaseModel):
    confirm_name: str
    expected_current_hash: str = Field(min_length=64, max_length=64)


@router.get("/workspaces/{workspace_id}/recovery/savepoints/{point_id}/preview")
def preview(
    workspace_id: int,
    point_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace_member(db, workspace_id, user, True)
    row = saved_point(db, workspace_id, point_id)
    current = {
        str(t.id): task_state(t)
        for t in db.query(PMSTask)
        .join(PMSProject)
        .filter(PMSProject.workspace_id == workspace_id)
        .all()
    }
    saved = row.payload["task_content"]
    return {
        "expected_current_hash": digest(current),
        "changed_tasks": sum(current.get(key) != value for key, value in saved.items()),
        "newer_tasks_kept": len(set(current) - set(saved)),
        "missing_tasks": len(set(saved) - set(current)),
        "scope": "Task content, status, dates, assignment and soft-delete state only. New tasks, projects, comments, files, memberships and financial records are preserved.",
    }


@router.post("/workspaces/{workspace_id}/recovery/savepoints/{point_id}/restore")
def restore(
    workspace_id: int,
    point_id: int,
    data: RestoreInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace, _ = workspace_member(db, workspace_id, user, True)
    db.query(PMSWorkspace).filter_by(id=workspace_id).with_for_update().one()
    row = saved_point(db, workspace_id, point_id)
    if data.confirm_name != workspace.name:
        raise HTTPException(422, "Type the workspace name to confirm recovery")
    tasks = (
        db.query(PMSTask)
        .join(PMSProject)
        .filter(PMSProject.workspace_id == workspace_id)
        .with_for_update()
        .all()
    )
    current = {str(t.id): task_state(t) for t in tasks}
    if digest(current) != data.expected_current_hash:
        raise HTTPException(
            409, "Workspace changed after preview. Preview again before restoring."
        )
    saved = row.payload["task_content"]
    if set(saved) - set(current):
        raise HTTPException(
            409,
            "Some saved tasks were permanently removed. Use a full-system archive for complete recovery.",
        )
    safety = make_point(db, workspace_id, user.id, "Before restore: " + row.name[:140])
    count = 0
    for task in tasks:
        state = saved.get(str(task.id))
        if state and state != current[str(task.id)]:
            apply_state(db, task, state, workspace_id)
            event(
                db,
                db.get(PMSProject, task.project_id),
                task,
                user,
                "task.savepoint_restored",
            )
            count += 1
    db.query(RecoveryChange).filter_by(workspace_id=workspace_id).update(
        {"state": "discarded"}
    )
    db.commit()
    from .api.router import _broadcast_realtime

    for project in db.query(PMSProject).filter_by(workspace_id=workspace_id).all():
        _broadcast_realtime(
            user,
            "project.updated",
            project_id=project.id,
            message="Workspace savepoint restored",
        )
    return {"restored_tasks": count, "safety_savepoint_id": safety.id}


def run_due(db, now=None):
    from .workspace_lifecycle import is_archived
    from datetime import timedelta

    now = now or datetime.utcnow()
    completed = []
    for policy in (
        db.query(RecoveryPolicy)
        .filter_by(enabled=True)
        .with_for_update(skip_locked=True)
        .all()
    ):
        if is_archived(db, policy.workspace_id):
            continue
        if policy.last_success_at and now - policy.last_success_at < timedelta(
            hours=policy.interval_hours
        ):
            continue
        member = (
            db.query(PMSWorkspaceMember)
            .filter_by(workspace_id=policy.workspace_id, user_id=policy.actor_id)
            .first()
        )
        actor = db.get(User, policy.actor_id)
        if (
            not member
            or member.role not in {"Owner", "Admin"}
            or not actor
            or not actor.is_active
        ):
            continue
        point = make_point(
            db,
            policy.workspace_id,
            policy.actor_id,
            "Automatic " + now.isoformat(timespec="seconds"),
            True,
        )
        policy.last_success_at = now
        old = (
            db.query(RecoveryPoint)
            .filter_by(workspace_id=policy.workspace_id, automatic=True)
            .order_by(RecoveryPoint.id.desc())
            .offset(policy.retain_automatic)
            .all()
        )
        for row in old:
            db.delete(row)
        completed.append(point.id)
    db.commit()
    return completed
