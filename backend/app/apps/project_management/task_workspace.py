"""Scoped task collaboration, optimistic progress and append-only audit events."""
from datetime import date, datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.core.rich_text import PREFIX, sanitize_rich_text, rich_text_plain
import bleach
from app.models.user import User
from .models import PMSTask, PMSTaskWorkspaceState, PMSTaskUpdateEntry, PMSActivity, PMSChecklistItem, PMSFileAsset, PMSTimeLog, PMSComment, PMSTaskWatcher, PMSTaskReadPosition
from .access import get_task_project_for_action, can_access_project, organization_id_for
from .task_studio import version, publish

router = APIRouter(prefix="/task-workspace", tags=["PMS Task Workspace"])

def manager_ids(db, project):
    ids = {project.manager_user_id, project.owner_user_id} - {None}
    if not ids and project.workspace_id:
        from .models import PMSWorkspaceMember
        ids = {row.user_id for row in db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.workspace_id == project.workspace_id, PMSWorkspaceMember.role.in_(["Owner", "Admin"]))}
    return ids

def clean_body(value):
    return sanitize_rich_text(value) if value.startswith(PREFIX) else bleach.clean(value, tags=[], strip=True)

@router.post("/tasks/{task_id}/watch")
def watch(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import _record_activity
    task, project = scoped_task(db, task_id, user, "browse")
    row = db.get(PMSTaskWatcher, (task.id, user.id))
    if row: db.delete(row)
    else: db.add(PMSTaskWatcher(task_id=task.id, user_id=user.id))
    _record_activity(db, project.id, user, "task.watch_changed", "task", task.id, "Changed task watching", task_id=task.id)
    db.commit(); publish(user, task, "task.updated")
    return {"watching": row is None}

@router.post("/tasks/{task_id}/read")
def mark_read(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, project = scoped_task(db, task_id, user, "browse")
    query = db.query(func.max(PMSComment.id)).filter(PMSComment.task_id == task.id, PMSComment.deleted_at.is_(None))
    if not can_access_project(db, project, user, "manage_tasks"): query = query.filter(PMSComment.is_internal.is_(False))
    latest = query.scalar() or 0
    row = db.get(PMSTaskReadPosition, (task.id, user.id))
    if not row: row = PMSTaskReadPosition(task_id=task.id, user_id=user.id, last_comment_id=0)
    row.last_comment_id = max(row.last_comment_id, latest)
    db.add(row); db.commit()
    return {"ok": True}

class DiscussionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    emoji: Literal["like", "celebrate", "seen"] | None = None
    resolved: bool | None = None

@router.post("/comments/{comment_id}/actions")
def discussion_action(comment_id: int, data: DiscussionAction, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .models import PMSComment, PMSCommentReaction
    from .api.router import _record_activity
    comment = db.query(PMSComment).filter_by(id=comment_id, deleted_at=None).with_for_update().first()
    if not comment or not comment.task_id: raise HTTPException(404, "Task comment not found")
    task, project = scoped_task(db, comment.task_id, user, "comment")
    if comment.is_internal and not can_access_project(db, project, user, "manage_tasks"): raise HTTPException(403, "This discussion is internal")
    if data.resolved is not None:
        if comment.author_user_id != user.id and not can_access_project(db, project, user, "approve"): raise HTTPException(403, "Only the author or a reviewer can resolve discussions")
        comment.is_resolved = data.resolved
    if data.emoji:
        row = db.query(PMSCommentReaction).filter_by(comment_id=comment.id, user_id=user.id, emoji=data.emoji).first()
        if row: db.delete(row)
        else: db.add(PMSCommentReaction(comment_id=comment.id, user_id=user.id, emoji=data.emoji))
    _record_activity(db, project.id, user, "task.discussion_updated", "comment", comment.id, "Updated task discussion", task_id=task.id, metadata={"resolved": data.resolved, "reaction": data.emoji})
    db.commit(); publish(user, task, "task.updated")
    return {"ok": True}

def can_work(db, task, project, user):
    if not can_access_project(db, project, user, "comment"): return False
    if user.id in task.assignee_user_ids or user.id in {project.owner_user_id, project.manager_user_id} or can_access_project(db, project, user, "approve"): return True
    from .models import PMSTaskGroupTarget, PMSWorkspaceTeamMember
    teams = db.query(PMSTaskGroupTarget.target_id).filter_by(task_id=task.id, kind="teams")
    if db.query(PMSWorkspaceTeamMember).filter(PMSWorkspaceTeamMember.team_id.in_(teams), PMSWorkspaceTeamMember.user_id == user.id).first(): return True
    from app.apps.interns_hub.management_models import InternBatchMembership
    from app.models.employee import Employee
    batches = db.query(PMSTaskGroupTarget.target_id).filter_by(task_id=task.id, kind="batches")
    # Only test the actor's membership; PMS access must not require reading HR records.
    membership_table, employee_table = InternBatchMembership.__table__, Employee.__table__
    return db.execute(select(membership_table.c.id).join(employee_table, employee_table.c.id == membership_table.c.employee_id).where(membership_table.c.batch_id.in_(batches), membership_table.c.status == "Active", employee_table.c.user_id == user.id, employee_table.c.deleted_at.is_(None), employee_table.c.status.notin_(["Inactive", "Terminated", "Suspended"])).limit(1)).first() is not None


def scoped_task(db, task_id, user, action="browse"):
    task, project = get_task_project_for_action(db, task_id, user, action)
    employee = getattr(user, "employee", None)
    intern = (user.role and user.role.name.lower() == "intern") or (employee and (employee.employment_type or "").lower() == "intern")
    if intern and not can_work(db, task, project, user): raise HTTPException(404, "Assigned task not found")
    return task, project


def state(db, task, lock=False):
    if lock:
        db.query(PMSTask).filter_by(id=task.id).with_for_update().one()
        db.refresh(task)
    return db.get(PMSTaskWorkspaceState, task.id)

def person(db, identity):
    from .people_management import public_person
    account = db.get(User, identity) if identity else None
    return public_person(db, account) if account else {"id": identity, "name": "Former collaborator"}

def entry_payload(db, row, user, manager):
    return {"id": row.id, "kind": row.kind, "body": row.body, "progress": row.progress, "minutes": row.minutes,
        "author": person(db, row.author_id), "created_at": row.created_at, "updated_at": row.updated_at,
        "resolved": row.resolved, "follow_up_date": row.follow_up_date, "category": row.category, "severity": row.severity,
        "responsible": person(db, row.responsible_user_id) if row.responsible_user_id else None,
        "assistance": row.assistance, "file_ids": row.file_ids, "revision": row.revision,
        "can_edit": manager or row.author_id == user.id, "can_resolve": manager or user.id in {row.author_id, row.responsible_user_id}}

@router.get("/tasks/{task_id}")
def detail(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .schemas import PMSTaskResponse
    from .my_work import targets
    task, project = scoped_task(db, task_id, user, "browse")
    current = state(db, task)
    checks = db.query(PMSChecklistItem).filter_by(task_id=task.id).all()
    mode = current.progress_mode if current else "manual"
    progress = round(100 * sum(c.is_completed for c in checks) / len(checks)) if mode == "checklist" and checks else current.progress if current else 0
    if task.status in {"Done", "Completed", "Closed"}:
        progress = 100
    blockers = db.query(PMSTaskUpdateEntry).filter_by(task_id=task.id, kind="blocker", resolved=False, deleted_at=None).order_by(PMSTaskUpdateEntry.id.desc()).all()
    manager = can_access_project(db, project, user, "approve")
    read_position = db.get(PMSTaskReadPosition, (task.id, user.id))
    unread = db.query(PMSComment).filter(PMSComment.task_id == task.id, PMSComment.deleted_at.is_(None), PMSComment.id > (read_position.last_comment_id if read_position else 0), PMSComment.author_user_id != user.id)
    if not can_access_project(db, project, user, "manage_tasks"): unread = unread.filter(PMSComment.is_internal.is_(False))
    return {"unread_comments": unread.count(), "is_watching": db.get(PMSTaskWatcher, (task.id, user.id)) is not None, "watcher_count": db.query(PMSTaskWatcher).filter_by(task_id=task.id).count(), "task": PMSTaskResponse.model_validate(task).model_dump(), "project": {"id": project.id, "name": project.name, "workspace_id": project.workspace_id, "is_general": project.is_task_collection},
        "progress": progress, "progress_mode": mode, "revision": current.revision if current else 0, "version": version(db, task),
        "source_managed": any(a.source_key for a in task.assignments), "can_work": can_work(db, task, project, user), "can_manage": can_access_project(db, project, user, "manage_tasks"), "can_review": manager,
        "assignees": [person(db, uid) for uid in task.assignee_user_ids], "groups": targets(db, task.id),
        "manager": person(db, project.manager_user_id or project.owner_user_id), "creator": person(db, task.reporter_user_id),
        "blockers": [entry_payload(db, row, user, manager) for row in blockers],
        "minutes": db.query(func.coalesce(func.sum(PMSTimeLog.duration_minutes), 0)).filter_by(task_id=task.id).scalar()}

@router.get("/tasks/{task_id}/entries")
def entries(task_id: int, page: int = Query(1, ge=1), kind: Literal["all", "update", "blocker", "review", "followup"] = "all", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, project = scoped_task(db, task_id, user, "browse")
    query = db.query(PMSTaskUpdateEntry).filter_by(task_id=task.id, deleted_at=None)
    if kind != "all": query = query.filter_by(kind=kind)
    total = query.count()
    manager = can_access_project(db, project, user, "approve")
    return {"items": [entry_payload(db, row, user, manager) for row in query.order_by(PMSTaskUpdateEntry.id.desc()).offset((page-1)*20).limit(20)], "total": total, "pages": (total+19)//20}

class EntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["update", "blocker", "followup"] = "update"
    body: str = Field(min_length=1, max_length=100000)
    progress: int | None = Field(None, ge=0, le=100)
    minutes: int = Field(0, ge=0, le=1440)
    category: str = Field("Other", max_length=40)
    severity: Literal["Low", "Medium", "High", "Critical"] = "Medium"
    responsible_user_id: int | None = None
    follow_up_date: date | None = None
    assistance: str = Field("", max_length=4000)
    file_ids: list[int] = Field(default_factory=list, max_length=20)
    mentioned_user_ids: list[int] = Field(default_factory=list, max_length=30)
    revision: int

@router.post("/tasks/{task_id}/entries", status_code=201)
def add_entry(task_id: int, data: EntryInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import _record_activity, _project_user_query
    from app.models.notification import Notification
    from app.services.metrics.queries import business_day
    task, project = scoped_task(db, task_id, user, "comment")
    if not can_work(db, task, project, user): raise HTTPException(403, "Task assignment or manager access is required to publish work updates")
    current = state(db, task, True)
    if (current.revision if current else 0) != data.revision: raise HTTPException(409, "Task progress changed. Refresh before posting; your draft is retained.")
    if data.kind == "followup" and not data.follow_up_date: raise HTTPException(422, "Choose a follow-up date")
    body = clean_body(data.body)
    if not rich_text_plain(body).strip(): raise HTTPException(422, "Write an update before posting")
    ids = set(data.mentioned_user_ids) | ({data.responsible_user_id} if data.responsible_user_id else set())
    allowed = {u.id for u in _project_user_query(db, project).filter(User.id.in_(ids), User.is_active.is_(True))}
    if ids - allowed: raise HTTPException(422, "Choose active collaborators with access to this task")
    files = {f.id for f in db.query(PMSFileAsset).filter(PMSFileAsset.id.in_(data.file_ids), PMSFileAsset.task_id == task.id)}
    if files != set(data.file_ids): raise HTTPException(422, "Attachments must belong to this task")
    if data.minutes and not can_access_project(db, project, user, "log_time"): raise HTTPException(403, "Time logging is not allowed")
    current = current or PMSTaskWorkspaceState(task_id=task.id, progress=0, progress_mode="manual", revision=0)
    if data.progress is not None:
        if current.progress_mode == "checklist": raise HTTPException(409, "Progress is calculated from the checklist")
        current.progress = data.progress
    current.revision += 1
    db.add(current)
    row = PMSTaskUpdateEntry(task_id=task.id, author_id=user.id, kind=data.kind, body=body, progress=data.progress, minutes=data.minutes,
        category=data.category if data.kind == "blocker" else None, severity=data.severity if data.kind == "blocker" else None,
        responsible_user_id=data.responsible_user_id, follow_up_date=data.follow_up_date, assistance=data.assistance, file_ids=sorted(files))
    db.add(row); db.flush()
    if data.minutes:
        db.add(PMSTimeLog(user_id=user.id, project_id=project.id, task_id=task.id, log_date=business_day(db, user), duration_minutes=data.minutes, description=rich_text_plain(body)[:4000], is_billable=False))
    recipients = set(data.mentioned_user_ids) | {row.user_id for row in db.query(PMSTaskWatcher).filter_by(task_id=task.id)}
    if data.kind in {"blocker", "followup"}: recipients |= manager_ids(db, project) | {data.responsible_user_id}
    for identity in recipients - {None, user.id}:
        account = db.get(User, identity)
        if account and can_access_project(db, project, account, "browse"):
            db.add(Notification(company_id=organization_id_for(user), user_id=identity, title="Task blocker reported" if data.kind == "blocker" else "Task follow-up scheduled" if data.kind == "followup" else "Mentioned in a task update" if identity in data.mentioned_user_ids else "Task update posted", message=task.title, module="project_management", event_type="task."+data.kind, action_url=f"/pms/tasks/{task.id}"))
    _record_activity(db, project.id, user, "task."+data.kind+"_posted", "task", task.id, f"Posted {data.kind} on {task.task_key}", task_id=task.id, metadata={"entry_id": row.id, "progress": data.progress, "minutes": data.minutes})
    db.commit(); publish(user, task, "task.updated")
    return entry_payload(db, row, user, can_access_project(db, project, user, "approve"))

class EditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int
    body: str | None = Field(None, max_length=100000)
    resolved: bool | None = None
    delete: bool = False

@router.patch("/entries/{entry_id}")
def edit_entry(entry_id: int, data: EditEntry, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import _record_activity
    row = db.query(PMSTaskUpdateEntry).filter_by(id=entry_id, deleted_at=None).with_for_update().first()
    if not row: raise HTTPException(404, "Update not found")
    task, project = scoped_task(db, row.task_id, user, "comment")
    manager = can_access_project(db, project, user, "approve")
    if row.author_id != user.id and not manager and not (row.responsible_user_id == user.id and data.resolved is not None and data.body is None and not data.delete): raise HTTPException(403, "Only the author or a manager can edit; responsible people may resolve their own follow-ups and blockers")
    if row.kind == "review": raise HTTPException(403, "Review decisions are immutable")
    if row.revision != data.revision: raise HTTPException(409, "This update changed. Reload before editing.")
    before = {"body": row.body, "resolved": row.resolved}
    if data.body is not None:
        row.body = clean_body(data.body)
        if not rich_text_plain(row.body).strip(): raise HTTPException(422, "Write an update")
    if data.resolved is not None:
        if row.kind not in {"blocker", "followup"}: raise HTTPException(422, "Only blockers and follow-ups can be resolved")
        row.resolved = data.resolved
    if data.delete:
        if row.kind == "blocker" and not row.resolved: raise HTTPException(409, "Resolve the blocker before deleting it")
        row.deleted_at = datetime.now(timezone.utc)
    row.revision += 1
    _record_activity(db, project.id, user, "task.update_edited", "task", task.id, f"Edited task update on {task.task_key}", task_id=task.id, metadata={"entry_id": row.id, "before": before, "resolved": row.resolved, "deleted": data.delete})
    db.commit(); publish(user, task, "task.updated")
    return {"ok": True}

class ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["start", "submit", "approve", "rework", "progress_mode", "status"]
    status: Literal["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done", "Cancelled"] | None = None
    version: str
    feedback: str = Field("", max_length=10000)
    progress_mode: Literal["manual", "checklist"] = "manual"

@router.post("/tasks/{task_id}/actions")
def action(task_id: int, data: ActionInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .api.router import update_task_operation, _record_activity
    from .schemas import PMSTaskUpdate
    task, project = scoped_task(db, task_id, user, "browse")
    current = state(db, task, True)
    if data.version != version(db, task): raise HTTPException(409, "The task changed. Refresh before continuing.")
    manager = can_access_project(db, project, user, "approve")
    if data.action == "status" and data.status == "Done" and not manager: raise HTTPException(403, "Use Submit for Review; a manager must approve completion")
    if data.action in {"approve", "rework"}:
        if not manager: raise HTTPException(403, "Manager approval permission is required")
        if task.status != "In Review": raise HTTPException(409, "This task is not awaiting review")
        if data.action == "rework" and not data.feedback.strip(): raise HTTPException(422, "Provide feedback before requesting rework")
    elif not can_work(db, task, project, user): raise HTTPException(403, "Task assignment or manager access is required")
    if data.action == "progress_mode":
        current = current or PMSTaskWorkspaceState(task_id=task.id, progress=0, progress_mode="manual", revision=0)
        current.progress_mode = data.progress_mode; current.revision += 1; db.add(current)
    else:
        status = data.status if data.action == "status" else {"start": "In Progress", "submit": "In Review", "approve": "Done", "rework": "In Progress"}[data.action]
        if not status: raise HTTPException(422, "Choose a status")
        if data.action == "submit" or data.action == "status" and status == "In Review":
            from .management import completion
            blockers = completion(db, task)["blockers"]
            if blockers: raise HTTPException(409, "; ".join(blockers))
        update_task_operation(task.id, PMSTaskUpdate(status=status), db, user, commit=False)
        if data.action in {"submit", "approve", "rework"} or data.action == "status" and status in {"In Review", "Done"}:
            db.add(PMSTaskUpdateEntry(task_id=task.id, author_id=user.id, kind="review", body=clean_body(data.feedback or (data.action.title() + " · " + status)), file_ids=[]))
    if data.action in {"submit", "approve", "rework"}:
        from app.models.notification import Notification
        recipients = manager_ids(db, project) if data.action == "submit" else set(task.assignee_user_ids)
        recipients |= {row.user_id for row in db.query(PMSTaskWatcher).filter_by(task_id=task.id)}
        for identity in recipients - {user.id}:
            account = db.get(User, identity)
            if account and account.is_active and can_access_project(db, project, account, "browse"):
                db.add(Notification(company_id=organization_id_for(user), user_id=identity, title="Task " + ("submitted for review" if data.action == "submit" else "approved" if data.action == "approve" else "rework requested"), message=task.title + (" — " + data.feedback if data.feedback else ""), module="project_management", event_type="task.review", action_url=f"/pms/tasks/{task.id}"))
    _record_activity(db, project.id, user, "task.workspace_"+data.action, "task", task.id, f"{data.action.title()} · {task.task_key}", task_id=task.id, metadata={"feedback": data.feedback, "progress_mode": data.progress_mode})
    db.commit(); publish(user, task, "task.updated")
    return detail(task.id, db, user)

@router.get("/tasks/{task_id}/history")
def history(task_id: int, page: int = Query(1, ge=1), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scoped_task(db, task_id, user, "browse")
    query = db.query(PMSActivity).filter_by(task_id=task_id)
    total = query.count()
    return {"items": [{"id": row.id, "summary": row.summary, "action": row.action, "actor": person(db, row.actor_user_id), "created_at": row.created_at} for row in query.order_by(PMSActivity.id.desc()).offset((page-1)*30).limit(30)], "pages": (total+29)//30, "total": total}
