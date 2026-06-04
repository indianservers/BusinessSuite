"""Project Management (KaryaFlow) API routes."""
import base64
import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import asc, case, desc, func, or_
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.core.security import verify_access_token
from app.db.session import SessionLocal
from app.models.user import User
from app.models.notification import Notification
from app.apps.project_management.models import (
    PMSClient, PMSProject, PMSProjectMember, PMSTask, PMSBoard, PMSBoardColumn,
    PMSMilestone, PMSSprint, PMSSprintRetroActionItem, PMSComment, PMSTimeLog, PMSTimesheet, PMSFileAsset, PMSTaskDependency,
    PMSChecklistItem, PMSTag, PMSTaskTag, PMSClientApproval, PMSEpic, PMSComponent, PMSRelease, PMSMention,
    PMSUserCapacity, PMSRisk, PMSProjectIntake,
    PMSDevIntegration, PMSDevLink, PMSSavedFilter, PMSActivity
)
from app.apps.project_management.access import (
    accessible_project_query,
    can_access_project,
    get_project_for_action,
    get_task_project_for_action,
    has_any_permission,
    organization_id_for,
    PMS_GLOBAL_MANAGE_PROJECTS,
    PMS_GLOBAL_MANAGE_TASKS,
    PMS_GLOBAL_TIME,
)
from app.apps.project_management.schemas import (
    PMSProjectCreate, PMSProjectUpdate, PMSProjectResponse,
    PMSProjectIntakeCreate, PMSProjectIntakeReview, PMSProjectIntakeResponse,
    PMSTaskCreate, PMSTaskUpdate, PMSTaskResponse,
    PMSClientCreate, PMSClientUpdate, PMSClientResponse,
    PMSMilestoneCreate, PMSMilestoneUpdate, PMSMilestoneResponse,
    PMSBoardCreate, PMSBoardResponse,
    PMSProjectMemberCreate, PMSProjectMemberUpdate, PMSProjectMemberResponse,
    PMSEpicCreate, PMSEpicUpdate, PMSEpicResponse,
    PMSComponentCreate, PMSComponentUpdate, PMSComponentResponse,
    PMSReleaseCreate, PMSReleaseUpdate, PMSReleaseResponse,
    PMSCommentCreate, PMSCommentUpdate, PMSCommentResponse,
    PMSTimeLogCreate, PMSTimeLogUpdate, PMSTimeLogResponse,
    PMSTimesheetCreate, PMSTimesheetUpdate, PMSTimesheetResponse, PMSTimesheetRejectRequest,
    PMSRiskCreate, PMSRiskUpdate, PMSRiskResponse,
    PMSSprintCreate, PMSSprintUpdate, PMSSprintResponse,
    SprintCompleteRequest, PMSSprintReviewResponse, SprintBurndownResponse, ProjectVelocityResponse,
    PMSFileAssetCreate, PMSFileAssetUpdate, PMSFileAssetResponse,
    PMSClientApprovalCreate, PMSClientApprovalUpdate, PMSClientApprovalResponse,
    PMSTaskDependencyCreate, PMSTaskDependencyResponse, PMSTaskDependencyDetail,
    PMSChecklistItemCreate, PMSChecklistItemUpdate, PMSChecklistItemResponse, PMSTagCreate, PMSTagResponse,
    TaskBulkUpdateRequest, TaskBulkUpdateResponse,
    PMSSavedFilterCreate, PMSSavedFilterUpdate, PMSSavedFilterResponse,
    PMSActivityResponse, ReleaseReadinessResponse, WorkloadResponse,
    KanbanBoard, TaskReorderRequest, ProjectMetrics, DashboardResponse,
)
from app.apps.project_management.realtime import broadcast_pms_event, broadcast_pms_event_from_thread, pms_realtime_manager

router = APIRouter(prefix="/project-management", tags=["Project Management"])


DONE_STATUSES = {"Done", "Completed", "Closed", "Resolved"}
PMS_UPLOAD_ROOT = Path(os.getenv("PMS_UPLOAD_ROOT", "uploads/pms")).resolve()
PMS_MAX_ATTACHMENT_BYTES = int(os.getenv("PMS_MAX_ATTACHMENT_BYTES", str(25 * 1024 * 1024)))
PMS_ALLOWED_ATTACHMENT_TYPES = {
    "application/pdf",
    "application/zip",
    "application/x-zip-compressed",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/csv",
    "text/markdown",
    "text/plain",
}


TASK_ACTIVITY_FIELD_MAP = {
    "status": "status.changed",
    "priority": "priority.changed",
    "assignee_user_id": "assignee.changed",
    "sprint_id": "sprint.changed",
    "epic_id": "epic.changed",
    "story_points": "story_points.changed",
    "due_date": "due_date.changed",
}


class ChecklistReorderRequest(BaseModel):
    item_ids: list[int]


class TaskTagAttachRequest(BaseModel):
    tag_id: int | None = None
    name: str | None = None


class TaskSprintMoveRequest(BaseModel):
    sprint_id: int
    position: int | None = None
    allow_completed: bool = False


class TaskReorderListRequest(BaseModel):
    task_ids: list[int]


class SubtaskCreateRequest(BaseModel):
    title: str
    description: str | None = None
    status: str = "To Do"
    priority: str = "Medium"
    assignee_user_id: int | None = None
    due_date: date | None = None
    story_points: int | None = None
    task_key: str | None = None


class TaskDependencyCreateRequest(BaseModel):
    source_task_id: int
    target_task_id: int
    dependency_type: str = "Finish To Start"
    lag_days: int = 0


class TaskScheduleUpdateRequest(BaseModel):
    start_date: date | None = None
    due_date: date | None = None


class EpicScheduleUpdateRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    target_date: date | None = None
    status: str | None = None


class DevIntegrationCreateRequest(BaseModel):
    provider: str
    project_id: int
    repo_owner: str
    repo_name: str
    access_token: str | None = None
    webhook_secret: str | None = None
    is_active: bool = True


class ProjectCloneRequest(BaseModel):
    name: str
    project_key: str
    include_milestones: bool = True
    include_tasks: bool = True
    include_dependencies: bool = True
    include_team: bool = False
    as_template: bool = False
    status: str = "Planned"


def _task_points(task: PMSTask) -> int:
    return int(task.story_points or 0)


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _weeks_between(start: date, end: date) -> list[date]:
    cursor = _week_start(start)
    last = _week_start(end)
    weeks: list[date] = []
    while cursor <= last:
        weeks.append(cursor)
        cursor += timedelta(days=7)
    return weeks


def _json_ready(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _loads_json(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _model_payload(model) -> dict:
    return {column.key: _json_ready(getattr(model, column.key)) for column in model.__table__.columns}


def _pms_fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_dev_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _pms_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt_dev_secret(value: str | None) -> str | None:
    if not value:
        return None
    return _pms_fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def _user_display_name(user: User | None) -> str | None:
    if not user:
        return None
    employee = getattr(user, "employee", None)
    employee_name = getattr(employee, "full_name", None) or getattr(employee, "name", None)
    return employee_name or getattr(user, "email", None)


def _safe_attachment_name(filename: str | None) -> str:
    raw_name = Path(filename or "attachment").name.strip() or "attachment"
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw_name).strip(" .")
    return safe[:180] or "attachment"


def _validate_attachment_upload(upload: UploadFile) -> None:
    content_type = upload.content_type or "application/octet-stream"
    if content_type.startswith("image/"):
        return
    if content_type in PMS_ALLOWED_ATTACHMENT_TYPES:
        return
    raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type}")


def _file_payload(file_asset: PMSFileAsset, uploader: User | None = None) -> dict:
    payload = _model_payload(file_asset)
    payload["uploaded_by_name"] = _user_display_name(uploader)
    payload["download_url"] = f"/project-management/attachments/{file_asset.id}/download"
    if (file_asset.mime_type or "").startswith("image/") or file_asset.mime_type == "application/pdf":
        payload["preview_url"] = payload["download_url"]
    return payload


def _file_payloads(db: Session, files: list[PMSFileAsset]) -> list[dict]:
    user_ids = {item.uploaded_by_user_id for item in files if item.uploaded_by_user_id}
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    users_by_id = {user.id: user for user in users}
    return [_file_payload(item, users_by_id.get(item.uploaded_by_user_id)) for item in files]


def _get_file_for_action(db: Session, file_id: int, current_user: User, action: str = "browse") -> tuple[PMSFileAsset, PMSProject]:
    file_asset = db.query(PMSFileAsset).filter(
        PMSFileAsset.id == file_id,
        PMSFileAsset.deleted_at == None,
    ).first()
    if not file_asset:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if not file_asset.project_id:
        raise HTTPException(status_code=404, detail="Attachment project not found")
    project = get_project_for_action(db, file_asset.project_id, current_user, action)
    return file_asset, project


def _json_loads_or_empty(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _saved_view_payload(saved_filter: PMSSavedFilter) -> dict:
    payload = _model_payload(saved_filter)
    payload["filters"] = _json_loads_or_empty(saved_filter.filters_json, {})
    payload["sort"] = _json_loads_or_empty(saved_filter.sort_json, {})
    payload["columns"] = _json_loads_or_empty(saved_filter.columns_json, {})
    payload["visibility"] = saved_filter.visibility or ("workspace" if saved_filter.is_shared else "private")
    payload["is_default"] = bool(saved_filter.is_default)
    return payload


def _apply_saved_view_payload(saved_filter: PMSSavedFilter, data: dict) -> None:
    if "filters" in data:
        saved_filter.filters_json = json.dumps(data.get("filters") or {}, default=str)
    if "sort" in data:
        saved_filter.sort_json = json.dumps(data.get("sort") or {}, default=str)
    if "columns" in data:
        saved_filter.columns_json = json.dumps(data.get("columns") or {}, default=str)
    if "visibility" in data and data.get("visibility") is not None:
        visibility = str(data["visibility"]).lower()
        if visibility not in {"private", "team", "workspace"}:
            raise HTTPException(status_code=400, detail="Visibility must be private, team, or workspace")
        saved_filter.visibility = visibility
        saved_filter.is_shared = visibility != "private"
    if "is_default" in data and data.get("is_default") is not None:
        saved_filter.is_default = bool(data["is_default"])
    if "query" in data and data.get("query"):
        saved_filter.query = data["query"]
    elif not saved_filter.query:
        saved_filter.query = json.dumps(_json_loads_or_empty(saved_filter.filters_json, {}), default=str)


def _can_manage_saved_view(db: Session, saved_filter: PMSSavedFilter, current_user: User) -> bool:
    if saved_filter.user_id == current_user.id:
        return True
    if saved_filter.project_id:
        project = get_project_for_action(db, saved_filter.project_id, current_user, "browse")
        return can_access_project(db, project, current_user, "manage_tasks")
    return has_any_permission(current_user, PMS_GLOBAL_MANAGE_TASKS | PMS_GLOBAL_MANAGE_PROJECTS)


def _task_list_payload(
    task: PMSTask,
    projects_by_id: dict[int, PMSProject],
    epics_by_id: dict[int, PMSEpic],
    sprints_by_id: dict[int, PMSSprint],
    users_by_id: dict[int, User],
    tags_by_task_id: dict[int, list[str]],
    subtask_counts_by_task_id: dict[int, tuple[int, int]] | None = None,
) -> dict:
    project = projects_by_id.get(task.project_id)
    epic = epics_by_id.get(task.epic_id) if task.epic_id else None
    sprint = sprints_by_id.get(task.sprint_id) if task.sprint_id else None
    assignee = users_by_id.get(task.assignee_user_id) if task.assignee_user_id else None
    reporter = users_by_id.get(task.reporter_user_id) if task.reporter_user_id else None
    payload = _model_payload(task)
    subtask_total, subtask_done = (subtask_counts_by_task_id or {}).get(task.id, (0, 0))
    payload.update({
        "project_name": project.name if project else None,
        "project_key": project.project_key if project else None,
        "epic_name": epic.name if epic else task.initiative,
        "sprint_name": sprint.name if sprint else None,
        "assignee_name": _user_display_name(assignee),
        "reporter_name": _user_display_name(reporter),
        "tags": tags_by_task_id.get(task.id, []),
        "subtask_count": subtask_total,
        "completed_subtask_count": subtask_done,
    })
    return payload


def _record_activity(
    db: Session,
    project_id: int,
    current_user: User,
    action: str,
    entity_type: str,
    entity_id: int | None,
    summary: str,
    task_id: int | None = None,
    sprint_id: int | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(PMSActivity(
        project_id=project_id,
        task_id=task_id,
        sprint_id=sprint_id,
        actor_user_id=getattr(current_user, "id", None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata_json=json.dumps(metadata or {}, default=str),
    ))


def _accessible_project_ids(db: Session, current_user: User) -> set[int]:
    return {row[0] for row in accessible_project_query(db, current_user).with_entities(PMSProject.id).all()}


def _actor_payload(current_user: User) -> dict:
    return {
        "id": current_user.id,
        "name": _user_display_name(current_user),
        "email": getattr(current_user, "email", None),
    }


def _broadcast_realtime(
    current_user: User,
    event_type: str,
    *,
    project_id: int,
    message: str,
    task_id: int | None = None,
    sprint_id: int | None = None,
    entity: dict | None = None,
    data: dict | None = None,
) -> None:
    broadcast_pms_event_from_thread({
        "type": event_type,
        "organizationId": organization_id_for(current_user),
        "projectId": project_id,
        "taskId": task_id,
        "sprintId": sprint_id,
        "actor": _actor_payload(current_user),
        "message": message,
        "entity": entity or {},
        "data": data or {},
    })


@router.websocket("/realtime")
async def pms_realtime_socket(websocket: WebSocket, token: str | None = None):
    """Authenticated PMS realtime channel with organization and project access scoping."""
    if not token:
        await websocket.close(code=1008)
        return
    payload = verify_access_token(token)
    user_id = payload.get("sub") if payload else None
    if not user_id:
        await websocket.close(code=1008)
        return

    db = SessionLocal()
    try:
        current_user = db.query(User).filter(User.id == int(user_id)).first()
        if not current_user or not current_user.is_active:
            await websocket.close(code=1008)
            return
        accessible_ids = _accessible_project_ids(db, current_user)
        await pms_realtime_manager.connect(
            websocket,
            user_id=current_user.id,
            organization_id=organization_id_for(current_user),
            accessible_project_ids=accessible_ids,
        )
        await websocket.send_json({
            "type": "connected",
            "organizationId": organization_id_for(current_user),
            "actor": _actor_payload(current_user),
            "projectIds": sorted(accessible_ids),
            "createdAt": datetime.utcnow().isoformat(),
        })
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            if action == "subscribe":
                requested_project_ids = {int(item) for item in message.get("projectIds", []) if str(item).isdigit()}
                requested_task_ids = {int(item) for item in message.get("taskIds", []) if str(item).isdigit()}
                allowed_project_ids = requested_project_ids.intersection(accessible_ids) if requested_project_ids else set()
                allowed_task_ids: set[int] = set()
                if requested_task_ids:
                    task_rows = db.query(PMSTask.id, PMSTask.project_id).filter(
                        PMSTask.id.in_(requested_task_ids),
                        PMSTask.deleted_at == None,
                    ).all()
                    for task_id, project_id in task_rows:
                        if project_id in accessible_ids:
                            allowed_task_ids.add(task_id)
                            allowed_project_ids.add(project_id)
                await pms_realtime_manager.subscribe(websocket, project_ids=allowed_project_ids, task_ids=allowed_task_ids)
                await websocket.send_json({
                    "type": "subscribed",
                    "projectIds": sorted(allowed_project_ids),
                    "taskIds": sorted(allowed_task_ids),
                    "createdAt": datetime.utcnow().isoformat(),
                })
            elif action in {"presence", "typing"}:
                project_id = message.get("projectId")
                if project_id is None or int(project_id) not in accessible_ids:
                    continue
                task_id = message.get("taskId")
                await broadcast_pms_event({
                    "type": "user.presence" if action == "presence" else "user.typing",
                    "organizationId": organization_id_for(current_user),
                    "projectId": int(project_id),
                    "taskId": int(task_id) if task_id is not None else None,
                    "actor": _actor_payload(current_user),
                    "message": message.get("message") or ("Viewing task" if action == "presence" else "Typing"),
                    "data": {"state": message.get("state")},
                })
    except WebSocketDisconnect:
        await pms_realtime_manager.disconnect(websocket)
    except Exception:
        await pms_realtime_manager.disconnect(websocket)
        await websocket.close(code=1011)
    finally:
        db.close()


def _load_task_tags(db: Session, task_ids: list[int]) -> dict[int, list[PMSTag]]:
    if not task_ids:
        return {}
    rows = db.query(PMSTaskTag.task_id, PMSTag).join(PMSTag, PMSTag.id == PMSTaskTag.tag_id).filter(
        PMSTaskTag.task_id.in_(task_ids)
    ).order_by(PMSTag.name).all()
    tags_by_task_id: dict[int, list[PMSTag]] = {}
    for task_id, tag in rows:
        tags_by_task_id.setdefault(task_id, []).append(tag)
    return tags_by_task_id


def _load_subtask_counts(db: Session, task_ids: list[int]) -> dict[int, tuple[int, int]]:
    if not task_ids:
        return {}
    rows = db.query(
        PMSTask.parent_task_id,
        func.count(PMSTask.id),
        func.sum(case((PMSTask.status.in_(DONE_STATUSES), 1), else_=0)),
    ).filter(
        PMSTask.parent_task_id.in_(task_ids),
        PMSTask.deleted_at == None,
    ).group_by(PMSTask.parent_task_id).all()
    return {parent_id: (int(total or 0), int(done or 0)) for parent_id, total, done in rows}


def _load_attachment_counts(db: Session, task_ids: list[int]) -> dict[int, int]:
    if not task_ids:
        return {}
    rows = db.query(PMSFileAsset.task_id, func.count(PMSFileAsset.id)).filter(
        PMSFileAsset.task_id.in_(task_ids),
        PMSFileAsset.deleted_at == None,
    ).group_by(PMSFileAsset.task_id).all()
    return {task_id: int(total or 0) for task_id, total in rows}


def _attach_task_counts(db: Session, tasks: list[PMSTask] | PMSTask | None):
    if not tasks:
        return tasks
    task_list = [tasks] if isinstance(tasks, PMSTask) else list(tasks)
    task_ids = [task.id for task in task_list]
    counts = _load_subtask_counts(db, task_ids)
    attachment_counts = _load_attachment_counts(db, task_ids)
    for task in task_list:
        total, done = counts.get(task.id, (0, 0))
        setattr(task, "subtask_count", total)
        setattr(task, "completed_subtask_count", done)
        setattr(task, "attachment_count", attachment_counts.get(task.id, 0))
    return tasks


def _attach_subtask_counts(db: Session, tasks: list[PMSTask] | PMSTask | None):
    return _attach_task_counts(db, tasks)


def _task_list_context(db: Session, tasks: list[PMSTask]):
    task_ids = [task.id for task in tasks]
    project_ids = {task.project_id for task in tasks}
    epic_ids = {task.epic_id for task in tasks if task.epic_id}
    sprint_ids = {task.sprint_id for task in tasks if task.sprint_id}
    user_ids = {task.assignee_user_id for task in tasks if task.assignee_user_id} | {task.reporter_user_id for task in tasks if task.reporter_user_id}
    projects_by_id = {project.id: project for project in db.query(PMSProject).filter(PMSProject.id.in_(project_ids)).all()} if project_ids else {}
    epics_by_id = {epic.id: epic for epic in db.query(PMSEpic).filter(PMSEpic.id.in_(epic_ids)).all()} if epic_ids else {}
    sprints_by_id = {sprint.id: sprint for sprint in db.query(PMSSprint).filter(PMSSprint.id.in_(sprint_ids)).all()} if sprint_ids else {}
    users_by_id = {user.id: user for user in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    tags_by_task_id: dict[int, list[str]] = {}
    if task_ids:
        tag_rows = db.query(PMSTaskTag.task_id, PMSTag.name).join(PMSTag, PMSTag.id == PMSTaskTag.tag_id).filter(
            PMSTaskTag.task_id.in_(task_ids)
        ).order_by(PMSTag.name).all()
        for task_id, tag_name in tag_rows:
            tags_by_task_id.setdefault(task_id, []).append(tag_name)
    return projects_by_id, epics_by_id, sprints_by_id, users_by_id, tags_by_task_id


def _task_list_payloads(db: Session, tasks: list[PMSTask]) -> list[dict]:
    context = _task_list_context(db, tasks)
    task_ids = [task.id for task in tasks]
    subtask_counts = _load_subtask_counts(db, task_ids)
    attachment_counts = _load_attachment_counts(db, task_ids)
    payloads = [_task_list_payload(task, *context, subtask_counts) for task in tasks]
    for payload in payloads:
        payload["attachment_count"] = attachment_counts.get(payload["id"], 0)
    return payloads


def _epic_end_date(epic: PMSEpic):
    return getattr(epic, "end_date", None) or epic.target_date


def _epic_payload(db: Session, epic: PMSEpic, project: PMSProject, owner: User | None, tasks: list[PMSTask], dependencies: list[PMSTaskDependency]) -> dict:
    task_payloads = _task_list_payloads(db, tasks)
    total_points = sum(_task_points(task) for task in tasks)
    completed_points = sum(_task_points(task) for task in tasks if task.status in DONE_STATUSES)
    completed_tasks = len([task for task in tasks if task.status in DONE_STATUSES])
    progress = round((completed_points / total_points) * 100) if total_points else (round((completed_tasks / len(tasks)) * 100) if tasks else 0)
    payload = _model_payload(epic)
    payload.update({
        "organization_id": epic.organization_id or project.organization_id,
        "project_name": project.name,
        "project_key": project.project_key,
        "owner_name": _user_display_name(owner),
        "end_date": _json_ready(_epic_end_date(epic)),
        "progress_percent": progress,
        "task_count": len(tasks),
        "completed_task_count": completed_tasks,
        "story_points": total_points,
        "completed_story_points": completed_points,
        "tasks": task_payloads,
        "dependencies": [
            _dependency_detail_payload(dep, {task.id: task for task in tasks})
            for dep in dependencies
        ],
    })
    return payload


def _ensure_valid_parent_task(db: Session, project_id: int, task_id: int | None, parent_task_id: int | None) -> PMSTask | None:
    if parent_task_id is None:
        return None
    if task_id and parent_task_id == task_id:
        raise HTTPException(status_code=400, detail="A task cannot be its own parent")
    parent = db.query(PMSTask).filter(
        PMSTask.id == parent_task_id,
        PMSTask.project_id == project_id,
        PMSTask.deleted_at == None,
    ).first()
    if not parent:
        raise HTTPException(status_code=400, detail="Parent task must exist in the same project")
    ancestor_id = parent.parent_task_id
    visited = {parent.id}
    while ancestor_id:
        if task_id and ancestor_id == task_id:
            raise HTTPException(status_code=400, detail="A sub-task cannot be parent of its own ancestor")
        if ancestor_id in visited:
            raise HTTPException(status_code=400, detail="Circular parent task relationship detected")
        visited.add(ancestor_id)
        ancestor = db.query(PMSTask).filter(PMSTask.id == ancestor_id, PMSTask.deleted_at == None).first()
        ancestor_id = ancestor.parent_task_id if ancestor else None
    return parent


def _next_subtask_key(db: Session, parent: PMSTask) -> str:
    base = parent.task_key[:24] if len(parent.task_key) > 24 else parent.task_key
    count = db.query(PMSTask).filter(PMSTask.parent_task_id == parent.id).count() + 1
    while True:
        key = f"{base}-S{count}"[:30].upper()
        existing = db.query(PMSTask).filter(PMSTask.project_id == parent.project_id, PMSTask.task_key == key).first()
        if not existing:
            return key
        count += 1


def _normalize_dependency_type(value: str | None) -> str:
    normalized = (value or "Finish To Start").strip().lower().replace("_", " ").replace("-", " ")
    aliases = {
        "finish to start": "Finish To Start",
        "fs": "Finish To Start",
        "start to start": "Start To Start",
        "ss": "Start To Start",
        "finish to finish": "Finish To Finish",
        "ff": "Finish To Finish",
        "start to finish": "Start To Finish",
        "sf": "Start To Finish",
    }
    if normalized not in aliases:
        raise HTTPException(status_code=400, detail="Unsupported dependency type")
    return aliases[normalized]


def _dependency_successors(db: Session, task_id: int) -> list[int]:
    return [
        row[0]
        for row in db.query(PMSTaskDependency.task_id)
        .join(PMSTask, PMSTask.id == PMSTaskDependency.task_id)
        .filter(PMSTaskDependency.depends_on_task_id == task_id, PMSTask.deleted_at == None)
        .all()
    ]


def _would_create_dependency_cycle(db: Session, source_task_id: int, target_task_id: int) -> bool:
    if source_task_id == target_task_id:
        return True
    stack = [target_task_id]
    visited: set[int] = set()
    while stack:
        current = stack.pop()
        if current == source_task_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(_dependency_successors(db, current))
    return False


def _dependency_detail_payload(dep: PMSTaskDependency, related: dict[int, PMSTask]) -> dict:
    target = related.get(dep.task_id)
    source = related.get(dep.depends_on_task_id)
    return {
        "id": dep.id,
        "task_id": dep.task_id,
        "depends_on_task_id": dep.depends_on_task_id,
        "source_task_id": dep.depends_on_task_id,
        "target_task_id": dep.task_id,
        "dependency_type": dep.dependency_type,
        "lag_days": getattr(dep, "lag_days", 0) or 0,
        "created_at": dep.created_at,
        "task_key": target.task_key if target else None,
        "depends_on_task_key": source.task_key if source else None,
        "task_title": target.title if target else None,
        "depends_on_task_title": source.title if source else None,
        "source_task_key": source.task_key if source else None,
        "target_task_key": target.task_key if target else None,
        "source_task_title": source.title if source else None,
        "target_task_title": target.title if target else None,
    }


def _dev_integration_payload(row: PMSDevIntegration, project: PMSProject | None = None) -> dict:
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "project_id": row.project_id,
        "project_name": project.name if project else None,
        "provider": row.provider,
        "repo_owner": row.repo_owner,
        "repo_name": row.repo_name,
        "is_active": row.is_active,
        "has_access_token": bool(row.access_token_encrypted),
        "has_webhook_secret": bool(row.webhook_secret_encrypted),
        "created_at": _json_ready(row.created_at),
        "updated_at": _json_ready(row.updated_at),
    }


def _dev_link_payload(row: PMSDevLink) -> dict:
    item = _model_payload(row)
    item["metadata"] = _loads_json(row.metadata_json, {})
    item.pop("metadata_json", None)
    return item


def _normalize_dev_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized not in {"github", "gitlab"}:
        raise HTTPException(status_code=400, detail="provider must be github or gitlab")
    return normalized


def _find_dev_task_keys(text: str, tasks: list[PMSTask]) -> list[PMSTask]:
    haystack = (text or "").upper()
    if not haystack:
        return []
    matched = []
    for task in tasks:
        key = (task.task_key or "").upper()
        if key and re.search(rf"(?<![A-Z0-9]){re.escape(key)}(?![A-Z0-9])", haystack):
            matched.append(task)
    return matched


def _upsert_dev_link(
    db: Session,
    task: PMSTask,
    project: PMSProject,
    provider: str,
    link_type: str,
    external_id: str,
    title: str | None,
    url: str | None,
    status_value: str | None,
    author: str | None,
    metadata: dict | None = None,
) -> PMSDevLink:
    link = db.query(PMSDevLink).filter(
        PMSDevLink.task_id == task.id,
        PMSDevLink.provider == provider,
        PMSDevLink.link_type == link_type,
        PMSDevLink.external_id == external_id,
    ).first()
    created = False
    if not link:
        link = PMSDevLink(
            organization_id=project.organization_id,
            task_id=task.id,
            provider=provider,
            link_type=link_type,
            external_id=external_id,
        )
        created = True
    link.title = title
    link.url = url
    link.status = status_value
    link.author = author
    link.metadata_json = json.dumps(metadata or {}, default=str)
    db.add(link)
    db.flush()
    system_actor = type("SystemActor", (), {"id": None})()
    _record_activity(
        db,
        project.id,
        system_actor,
        "development.link_added" if created else "development.link_updated",
        "development",
        link.id,
        f"Linked {provider} {link_type} to {task.task_key}",
        task_id=task.id,
        metadata={"provider": provider, "link_type": link_type, "external_id": external_id, "status": status_value},
    )
    if link_type in {"pr", "mr"} and status_value == "merged" and task.status not in DONE_STATUSES:
        task.status = "Done"
        db.add(task)
        _record_activity(
            db,
            project.id,
            system_actor,
            "status.changed",
            "task",
            task.id,
            f"Moved {task.task_key} to Done after merged {provider} {link_type}",
            task_id=task.id,
            metadata={"automation": "dev_link_merged", "provider": provider, "link_type": link_type},
        )
    return link


def _github_signature_valid(raw_body: bytes, secret: str, signature: str | None) -> bool:
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _project_repo_integrations(db: Session, provider: str, owner: str, repo: str) -> list[PMSDevIntegration]:
    owner = (owner or "").lower()
    repo = (repo or "").lower()
    return db.query(PMSDevIntegration).filter(
        PMSDevIntegration.provider == provider,
        func.lower(PMSDevIntegration.repo_owner) == owner,
        func.lower(PMSDevIntegration.repo_name) == repo,
        PMSDevIntegration.is_active == True,
    ).all()


def _process_dev_payload(db: Session, integration: PMSDevIntegration, provider: str, payload: dict, event_name: str | None) -> list[PMSDevLink]:
    project = db.query(PMSProject).filter(PMSProject.id == integration.project_id, PMSProject.deleted_at == None).first()
    if not project:
        return []
    tasks = db.query(PMSTask).filter(PMSTask.project_id == project.id, PMSTask.deleted_at == None).all()
    created_links: list[PMSDevLink] = []

    if provider == "github":
        if event_name == "push":
            branch = str(payload.get("ref") or "").replace("refs/heads/", "")
            branch_tasks = _find_dev_task_keys(branch, tasks)
            for task in branch_tasks:
                created_links.append(_upsert_dev_link(db, task, project, provider, "branch", branch, branch, None, "active", None, {"ref": payload.get("ref")}))
            for commit in payload.get("commits") or []:
                text = " ".join([str(commit.get("message") or ""), branch])
                for task in _find_dev_task_keys(text, tasks):
                    author = ((commit.get("author") or {}).get("name") or (commit.get("committer") or {}).get("name"))
                    created_links.append(_upsert_dev_link(db, task, project, provider, "commit", str(commit.get("id")), commit.get("message"), commit.get("url"), "pushed", author, commit))
        elif event_name in {"pull_request", "pull_request_review"}:
            pr = payload.get("pull_request") or {}
            status_value = "merged" if pr.get("merged") else (pr.get("state") or "open")
            text = " ".join([str(pr.get("title") or ""), str(pr.get("body") or ""), str((pr.get("head") or {}).get("ref") or "")])
            for task in _find_dev_task_keys(text, tasks):
                author = (pr.get("user") or {}).get("login")
                created_links.append(_upsert_dev_link(db, task, project, provider, "pr", str(pr.get("number")), pr.get("title"), pr.get("html_url"), status_value, author, pr))

    if provider == "gitlab":
        kind = payload.get("object_kind") or event_name
        if kind == "push":
            branch = str(payload.get("ref") or "").replace("refs/heads/", "")
            for task in _find_dev_task_keys(branch, tasks):
                created_links.append(_upsert_dev_link(db, task, project, provider, "branch", branch, branch, None, "active", None, {"ref": payload.get("ref")}))
            for commit in payload.get("commits") or []:
                text = " ".join([str(commit.get("message") or ""), branch])
                for task in _find_dev_task_keys(text, tasks):
                    author = (commit.get("author") or {}).get("name")
                    created_links.append(_upsert_dev_link(db, task, project, provider, "commit", str(commit.get("id")), commit.get("title") or commit.get("message"), commit.get("url"), "pushed", author, commit))
        elif kind == "merge_request":
            mr = payload.get("object_attributes") or {}
            state = mr.get("state") or "open"
            status_value = "merged" if state == "merged" or mr.get("merged_at") else state
            text = " ".join([str(mr.get("title") or ""), str(mr.get("description") or ""), str(mr.get("source_branch") or "")])
            for task in _find_dev_task_keys(text, tasks):
                author = (payload.get("user") or {}).get("username") or (payload.get("user") or {}).get("name")
                created_links.append(_upsert_dev_link(db, task, project, provider, "mr", str(mr.get("iid") or mr.get("id")), mr.get("title"), mr.get("url"), status_value, author, mr))
    return created_links


def _risk_score(probability: int | None, impact: int | None) -> int:
    probability_value = min(max(int(probability or 1), 1), 5)
    impact_value = min(max(int(impact or 1), 1), 5)
    return probability_value * impact_value


def _risk_severity(score: int | None) -> str:
    value = int(score or 0)
    if value >= 15:
        return "high"
    if value >= 8:
        return "medium"
    return "low"


def _open_high_risks(risks: list[PMSRisk] | None) -> list[PMSRisk]:
    return [
        risk
        for risk in (risks or [])
        if risk.status in {"open", "mitigating"} and int(risk.risk_score or 0) >= 15 and risk.deleted_at is None
    ]


def _portfolio_health(project: PMSProject, tasks: list[PMSTask], sprints: list[PMSSprint], risks: list[PMSRisk] | None = None) -> str:
    today = date.today()
    open_tasks = [task for task in tasks if task.status not in DONE_STATUSES]
    overdue_tasks = [task for task in open_tasks if task.due_date and task.due_date < today]
    blocked_tasks = [task for task in open_tasks if task.is_blocking or task.status == "Blocked"]
    high_risks = _open_high_risks(risks)
    active_sprints = [sprint for sprint in sprints if sprint.status == "Active"]
    sprint_pressure = any(
        sprint.end_date < today and int(sprint.completed_story_points or 0) < int(sprint.committed_story_points or 0)
        for sprint in active_sprints
    )
    if blocked_tasks or len(overdue_tasks) >= 5 or any(int(risk.risk_score or 0) >= 20 for risk in high_risks):
        return "Blocked"
    if overdue_tasks or sprint_pressure or high_risks:
        return "At Risk"
    if project.due_date and project.due_date < today and int(project.progress_percent or 0) < 100:
        return "At Risk"
    if project.start_date and project.due_date and project.progress_percent is not None:
        total_days = max((project.due_date - project.start_date).days, 1)
        elapsed_days = min(max((today - project.start_date).days, 0), total_days)
        expected_progress = (elapsed_days / total_days) * 100
        if expected_progress - int(project.progress_percent or 0) > 25:
            return "At Risk"
    return "Good"


def _portfolio_project_payload(project: PMSProject, owner: User | None, client: PMSClient | None, tasks: list[PMSTask], sprints: list[PMSSprint], milestones: list[PMSMilestone], risks: list[PMSRisk] | None = None) -> dict:
    today = date.today()
    open_tasks = [task for task in tasks if task.status not in DONE_STATUSES]
    overdue_tasks = [task for task in open_tasks if task.due_date and task.due_date < today]
    blocked_tasks = [task for task in open_tasks if task.is_blocking or task.status == "Blocked"]
    open_risks = [risk for risk in (risks or []) if risk.status in {"open", "mitigating"} and risk.deleted_at is None]
    high_risks = _open_high_risks(risks)
    active_sprint = next((sprint for sprint in sprints if sprint.status == "Active"), None)
    upcoming_milestones = [milestone for milestone in milestones if milestone.due_date and milestone.due_date >= today and milestone.status not in DONE_STATUSES]
    calculated_health = _portfolio_health(project, tasks, sprints, risks)
    return {
        "id": project.id,
        "name": project.name,
        "project_key": project.project_key,
        "owner_id": project.manager_user_id,
        "owner_name": _user_display_name(owner),
        "client_id": project.client_id,
        "client_name": client.name if client else None,
        "status": project.status,
        "health": calculated_health,
        "stored_health": project.health,
        "progress_percent": int(project.progress_percent or 0),
        "open_tasks": len(open_tasks),
        "overdue_tasks": len(overdue_tasks),
        "blocked_tasks": len(blocked_tasks),
        "risk_count": len(open_risks),
        "open_high_risks": len(high_risks),
        "total_tasks": len(tasks),
        "sprint_status": active_sprint.status if active_sprint else (sprints[0].status if sprints else "No sprint"),
        "active_sprint_name": active_sprint.name if active_sprint else None,
        "upcoming_milestones": len(upcoming_milestones),
        "start_date": _json_ready(project.start_date),
        "due_date": _json_ready(project.due_date),
        "budget_amount": _json_ready(project.budget_amount),
        "actual_cost": _json_ready(project.actual_cost),
    }


def _portfolio_context(db: Session, current_user: User, owner_id: int | None = None, client_id: int | None = None, status_filter: str | None = None) -> tuple[list[PMSProject], dict[int, list[PMSTask]], dict[int, list[PMSSprint]], dict[int, list[PMSMilestone]], dict[int, list[PMSRisk]], dict[int, User], dict[int, PMSClient]]:
    query = accessible_project_query(db, current_user)
    if owner_id:
        query = query.filter(PMSProject.manager_user_id == owner_id)
    if client_id:
        query = query.filter(PMSProject.client_id == client_id)
    if status_filter:
        query = query.filter(PMSProject.status == status_filter)
    projects = query.order_by(PMSProject.name).all()
    project_ids = [project.id for project in projects]
    tasks = db.query(PMSTask).filter(PMSTask.project_id.in_(project_ids), PMSTask.deleted_at == None).all() if project_ids else []
    sprints = db.query(PMSSprint).filter(PMSSprint.project_id.in_(project_ids)).order_by(PMSSprint.start_date.desc()).all() if project_ids else []
    milestones = db.query(PMSMilestone).filter(PMSMilestone.project_id.in_(project_ids)).all() if project_ids else []
    risks = db.query(PMSRisk).filter(PMSRisk.project_id.in_(project_ids), PMSRisk.deleted_at == None).all() if project_ids else []
    tasks_by_project: dict[int, list[PMSTask]] = {}
    sprints_by_project: dict[int, list[PMSSprint]] = {}
    milestones_by_project: dict[int, list[PMSMilestone]] = {}
    risks_by_project: dict[int, list[PMSRisk]] = {}
    for task in tasks:
        tasks_by_project.setdefault(task.project_id, []).append(task)
    for sprint in sprints:
        sprints_by_project.setdefault(sprint.project_id, []).append(sprint)
    for milestone in milestones:
        milestones_by_project.setdefault(milestone.project_id, []).append(milestone)
    for risk in risks:
        risks_by_project.setdefault(risk.project_id, []).append(risk)
    owner_ids = {project.manager_user_id for project in projects if project.manager_user_id}
    client_ids = {project.client_id for project in projects if project.client_id}
    owners = {user.id: user for user in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}
    clients = {client.id: client for client in db.query(PMSClient).filter(PMSClient.id.in_(client_ids)).all()} if client_ids else {}
    return projects, tasks_by_project, sprints_by_project, milestones_by_project, risks_by_project, owners, clients


def _report_project_ids(db: Session, current_user: User, project_id: int | None = None) -> list[int]:
    query = accessible_project_query(db, current_user)
    if project_id:
        query = query.filter(PMSProject.id == project_id)
    return [row[0] for row in query.with_entities(PMSProject.id).all()]


def _report_task_query(
    db: Session,
    current_user: User,
    project_id: int | None = None,
    assignee_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    project_ids = _report_project_ids(db, current_user, project_id)
    query = db.query(PMSTask).filter(PMSTask.deleted_at == None)
    if not project_ids:
        return query.filter(PMSTask.id == -1)
    query = query.filter(PMSTask.project_id.in_(project_ids))
    if assignee_id:
        query = query.filter(PMSTask.assignee_user_id == assignee_id)
    if start_date:
        query = query.filter(func.date(PMSTask.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(PMSTask.created_at) <= end_date)
    return query


def _project_financial_rows(db: Session, current_user: User, project_id: int | None = None) -> list[dict]:
    project_ids = _report_project_ids(db, current_user, project_id)
    projects = db.query(PMSProject).filter(PMSProject.id.in_(project_ids or [0])).order_by(PMSProject.name).all()
    rows: list[dict] = []
    for project in projects:
        tasks = db.query(PMSTask).filter(PMSTask.project_id == project.id, PMSTask.deleted_at == None).all()
        logs = db.query(PMSTimeLog).filter(PMSTimeLog.project_id == project.id).all()
        planned_hours = Decimal(project.estimated_hours or 0) or sum((task.estimated_hours or Decimal("0")) for task in tasks)
        actual_hours = sum(Decimal(log.duration_minutes or 0) for log in logs) / Decimal("60")
        billable_hours = sum(Decimal(log.duration_minutes or 0) for log in logs if log.is_billable) / Decimal("60")
        estimated_cost = Decimal(project.estimated_cost or 0)
        cost_rate = (estimated_cost / planned_hours) if planned_hours else Decimal("0")
        timesheet_cost = actual_hours * cost_rate
        actual_cost = Decimal(project.actual_cost or 0) + timesheet_cost
        budget = Decimal(project.budget_amount or 0) or estimated_cost
        variance = budget - actual_cost
        rows.append({
            "project_id": project.id,
            "project_key": project.project_key,
            "project_name": project.name,
            "client_id": project.client_id,
            "category": project.category,
            "status": project.status,
            "billing_status": project.billing_status or "Unbilled",
            "budget_amount": _json_ready(budget),
            "estimated_hours": _json_ready(planned_hours),
            "actual_hours": _json_ready(actual_hours),
            "billable_hours": _json_ready(billable_hours),
            "estimated_cost": _json_ready(estimated_cost),
            "actual_cost": _json_ready(actual_cost),
            "variance_amount": _json_ready(variance),
            "profitability_amount": _json_ready(variance),
            "profitability_percent": round(float((variance / budget * Decimal("100")) if budget else Decimal("0")), 2),
        })
    return rows


def _status_changes_for_tasks(db: Session, task_ids: list[int]) -> dict[int, list[dict]]:
    if not task_ids:
        return {}
    activities = db.query(PMSActivity).filter(
        PMSActivity.task_id.in_(task_ids),
        PMSActivity.action == "status.changed",
    ).order_by(PMSActivity.created_at.asc(), PMSActivity.id.asc()).all()
    by_task: dict[int, list[dict]] = {}
    for activity in activities:
        metadata = _loads_json(activity.metadata_json, {})
        by_task.setdefault(activity.task_id, []).append({
            "task_id": activity.task_id,
            "old_status": metadata.get("old_value"),
            "new_status": metadata.get("new_value"),
            "changed_by": activity.actor_user_id,
            "changed_at": activity.created_at,
        })
    return by_task


def _task_status_on(task: PMSTask, changes: list[dict], day_end: datetime) -> str | None:
    if task.created_at and task.created_at.replace(tzinfo=None) > day_end.replace(tzinfo=None):
        return None
    status = task.status
    for change in reversed(changes):
        changed_at = change["changed_at"]
        if changed_at and changed_at.replace(tzinfo=None) > day_end.replace(tzinfo=None):
            status = change.get("old_status") or status
        else:
            break
    return status


def _task_started_at(task: PMSTask, changes: list[dict]) -> datetime | None:
    active_statuses = {"In Progress", "In Review", "Blocked"} | DONE_STATUSES
    for change in changes:
        if change.get("new_status") in active_statuses:
            return change.get("changed_at")
    return task.created_at if task.status in active_statuses else None


def _task_completed_at(task: PMSTask, changes: list[dict]) -> datetime | None:
    if task.completed_at:
        return task.completed_at
    for change in changes:
        if change.get("new_status") in DONE_STATUSES:
            return change.get("changed_at")
    return task.updated_at if task.status in DONE_STATUSES else None


def _date_range_defaults(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=29))
    if start > end:
        raise HTTPException(status_code=400, detail="from date must be before to date")
    return start, end


def _csv_response(filename: str, headers: list[str], rows: list[list]) -> StreamingResponse:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _simple_pdf_response(filename: str, title: str, lines: list[str]) -> Response:
    escaped_lines = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:100] for line in lines[:40]]
    content_lines = ["BT", "/F1 16 Tf", "72 760 Td", f"({title}) Tj", "/F1 10 Tf"]
    for line in escaped_lines:
        content_lines.extend(["0 -16 Td", f"({line}) Tj"])
    content_lines.append("ET")
    stream = "\n".join(content_lines)
    pdf = (
        "%PDF-1.4\n"
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        f"5 0 obj << /Length {len(stream.encode('utf-8'))} >> stream\n{stream}\nendstream endobj\n"
        "xref\n0 6\n0000000000 65535 f \n"
        "trailer << /Root 1 0 R /Size 6 >>\nstartxref\n0\n%%EOF"
    )
    return Response(
        content=pdf.encode("utf-8"),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _dependency_conflict(dep: PMSTaskDependency, source: PMSTask, target: PMSTask) -> str | None:
    lag = timedelta(days=getattr(dep, "lag_days", 0) or 0)
    dep_type = _normalize_dependency_type(dep.dependency_type)
    source_start = source.start_date
    source_end = source.due_date or source.start_date
    target_start = target.start_date
    target_end = target.due_date or target.start_date
    if dep_type == "Finish To Start" and source_end and target_start and target_start < source_end + lag:
        return f"{target.task_key} starts before {source.task_key} finishes"
    if dep_type == "Start To Start" and source_start and target_start and target_start < source_start + lag:
        return f"{target.task_key} starts before {source.task_key} starts"
    if dep_type == "Finish To Finish" and source_end and target_end and target_end < source_end + lag:
        return f"{target.task_key} finishes before {source.task_key} finishes"
    if dep_type == "Start To Finish" and source_start and target_end and target_end < source_start + lag:
        return f"{target.task_key} finishes before {source.task_key} starts"
    return None


def _task_dependency_warnings(db: Session, task_ids: list[int]) -> list[dict]:
    if not task_ids:
        return []
    deps = db.query(PMSTaskDependency).filter(
        or_(PMSTaskDependency.task_id.in_(task_ids), PMSTaskDependency.depends_on_task_id.in_(task_ids))
    ).all()
    related_ids = {dep.task_id for dep in deps} | {dep.depends_on_task_id for dep in deps}
    related = {task.id: task for task in db.query(PMSTask).filter(PMSTask.id.in_(related_ids), PMSTask.deleted_at == None).all()} if related_ids else {}
    warnings = []
    for dep in deps:
        source = related.get(dep.depends_on_task_id)
        target = related.get(dep.task_id)
        if not source or not target:
            continue
        conflict = _dependency_conflict(dep, source, target)
        if conflict:
            warnings.append({
                "dependency_id": dep.id,
                "source_task_id": source.id,
                "target_task_id": target.id,
                "dependency_type": dep.dependency_type,
                "message": conflict,
            })
    return warnings


MENTION_RE = re.compile(r"@\[([^\]]+)\]\(user:(\d+)\)")


def _extract_mention_user_ids(body: str | None, explicit_ids: list[int] | None = None) -> list[int]:
    ids = [int(match.group(2)) for match in MENTION_RE.finditer(body or "")]
    ids.extend(int(user_id) for user_id in (explicit_ids or []) if user_id)
    return list(dict.fromkeys(ids))


def _project_user_query(db: Session, project: PMSProject):
    member_ids = db.query(PMSProjectMember.user_id).filter(PMSProjectMember.project_id == project.id)
    query = db.query(User).filter(
        User.is_active == True,
        or_(User.id.in_(member_ids), User.id == project.manager_user_id),
    )
    user_org_id = project.organization_id
    if user_org_id is not None and hasattr(User, "organization_id"):
        query = query.filter(User.organization_id == user_org_id)
    return query


def _pms_user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": _user_display_name(user) or user.email,
    }


def _comment_mentions(db: Session, comment_ids: list[int]) -> dict[int, list[dict]]:
    if not comment_ids:
        return {}
    mentions = db.query(PMSMention).filter(PMSMention.comment_id.in_(comment_ids)).order_by(PMSMention.created_at).all()
    users = {user.id: user for user in db.query(User).filter(User.id.in_([mention.mentioned_user_id for mention in mentions])).all()} if mentions else {}
    by_comment: dict[int, list[dict]] = {}
    for mention in mentions:
        user = users.get(mention.mentioned_user_id)
        by_comment.setdefault(mention.comment_id, []).append({
            "id": mention.id,
            "mentioned_user_id": mention.mentioned_user_id,
            "mentioned_by_user_id": mention.mentioned_by_user_id,
            "task_id": mention.task_id,
            "project_id": mention.project_id,
            "comment_id": mention.comment_id,
            "read_at": mention.read_at,
            "created_at": mention.created_at,
            "user": _pms_user_payload(user) if user else None,
        })
    return by_comment


def _comment_payload(comment: PMSComment, mentions_by_comment: dict[int, list[dict]] | None = None) -> dict:
    payload = _model_payload(comment)
    payload["mentions"] = (mentions_by_comment or {}).get(comment.id, [])
    return payload


def _replace_comment_mentions(
    db: Session,
    project: PMSProject,
    task: PMSTask,
    comment: PMSComment,
    current_user: User,
    mention_user_ids: list[int],
) -> None:
    db.query(PMSMention).filter(PMSMention.comment_id == comment.id).delete()
    if not mention_user_ids:
        return
    allowed_users = {user.id: user for user in _project_user_query(db, project).filter(User.id.in_(mention_user_ids)).all()}
    for mentioned_user_id in mention_user_ids:
        if mentioned_user_id == current_user.id or mentioned_user_id not in allowed_users:
            continue
        notification = Notification(
            company_id=None,
            user_id=mentioned_user_id,
            title=f"Mentioned on {task.task_key}",
            message=f"{_user_display_name(current_user) or current_user.email} mentioned you on {task.title}",
            module="pms",
            event_type="pms.mention",
            related_entity_type="pms_task",
            related_entity_id=task.id,
            action_url=f"/pms/projects/{project.id}/tasks/{task.id}",
            priority="normal",
            channels=["in_app"],
        )
        db.add(notification)
        db.flush()
        mention = PMSMention(
            project_id=project.id,
            task_id=task.id,
            comment_id=comment.id,
            mentioned_user_id=mentioned_user_id,
            mentioned_by_user_id=current_user.id,
            notification_id=notification.id,
        )
        db.add(mention)
        _record_activity(
            db,
            project.id,
            current_user,
            "mention.created",
            "comment",
            comment.id,
            f"Mentioned {allowed_users[mentioned_user_id].email} on {task.task_key}",
            task_id=task.id,
            metadata={"comment_id": comment.id, "mentioned_user_id": mentioned_user_id},
        )


def _get_time_log_for_action(db: Session, time_log_id: int, current_user: User, action: str = "log_time") -> tuple[PMSTimeLog, PMSProject]:
    time_log = db.query(PMSTimeLog).filter(PMSTimeLog.id == time_log_id).first()
    if not time_log:
        raise HTTPException(status_code=404, detail="Time log not found")
    project = get_project_for_action(db, time_log.project_id, current_user, "browse")
    if time_log.user_id != current_user.id and not can_access_project(db, project, current_user, "manage_tasks"):
        raise HTTPException(status_code=403, detail="Time log access denied")
    if action == "log_time":
        get_project_for_action(db, time_log.project_id, current_user, "log_time")
    return time_log, project


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _can_manage_timesheets(user: User) -> bool:
    return has_any_permission(user, PMS_GLOBAL_TIME | PMS_GLOBAL_MANAGE_PROJECTS | PMS_GLOBAL_MANAGE_TASKS)


def _timesheet_logs(db: Session, sheet: PMSTimesheet) -> list[PMSTimeLog]:
    week_end = sheet.week_start_date + timedelta(days=6)
    return db.query(PMSTimeLog).filter(
        PMSTimeLog.user_id == sheet.user_id,
        PMSTimeLog.log_date >= sheet.week_start_date,
        PMSTimeLog.log_date <= week_end,
        (PMSTimeLog.timesheet_id == sheet.id) | (PMSTimeLog.timesheet_id == None),
    ).order_by(PMSTimeLog.log_date.asc(), PMSTimeLog.id.asc()).all()


def _timesheet_payload(db: Session, sheet: PMSTimesheet) -> dict:
    logs = _timesheet_logs(db, sheet)
    project_ids = {log.project_id for log in logs}
    task_ids = {log.task_id for log in logs if log.task_id}
    projects = {project.id: project for project in db.query(PMSProject).filter(PMSProject.id.in_(project_ids)).all()} if project_ids else {}
    tasks = {task.id: task for task in db.query(PMSTask).filter(PMSTask.id.in_(task_ids)).all()} if task_ids else {}
    daily_totals = {(sheet.week_start_date + timedelta(days=index)).isoformat(): 0 for index in range(7)}
    entries = []
    total = 0
    billable = 0
    for log in logs:
        if log.timesheet_id is None:
            log.timesheet_id = sheet.id
            db.add(log)
        minutes = int(log.duration_minutes or 0)
        total += minutes
        if log.is_billable:
            billable += minutes
        day_key = log.log_date.isoformat()
        daily_totals[day_key] = daily_totals.get(day_key, 0) + minutes
        task = tasks.get(log.task_id)
        project = projects.get(log.project_id)
        entries.append({
            "id": log.id,
            "time_log_id": log.id,
            "project_id": log.project_id,
            "project_name": project.name if project else None,
            "task_id": log.task_id,
            "task_key": task.task_key if task else None,
            "task_title": task.title if task else None,
            "log_date": log.log_date,
            "duration_minutes": minutes,
            "description": log.description,
            "is_billable": log.is_billable,
            "approval_status": log.approval_status,
        })
    return {
        "id": sheet.id,
        "organization_id": sheet.organization_id,
        "user_id": sheet.user_id,
        "week_start_date": sheet.week_start_date,
        "status": sheet.status,
        "submitted_at": sheet.submitted_at,
        "approved_by_user_id": sheet.approved_by_user_id,
        "approved_at": sheet.approved_at,
        "rejection_reason": sheet.rejection_reason,
        "total_minutes": total,
        "billable_minutes": billable,
        "non_billable_minutes": total - billable,
        "daily_totals": daily_totals,
        "entries": entries,
        "created_at": sheet.created_at,
        "updated_at": sheet.updated_at,
    }


def _get_timesheet_for_action(db: Session, timesheet_id: int, current_user: User, action: str = "view") -> PMSTimesheet:
    sheet = db.query(PMSTimesheet).filter(PMSTimesheet.id == timesheet_id).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    same_org = sheet.organization_id == organization_id_for(current_user)
    if current_user.is_superuser:
        return sheet
    if action in {"approve", "reject"}:
        if not same_org or not _can_manage_timesheets(current_user):
            raise HTTPException(status_code=403, detail="Timesheet approval access denied")
        return sheet
    if sheet.user_id == current_user.id:
        return sheet
    if same_org and _can_manage_timesheets(current_user):
        return sheet
    raise HTTPException(status_code=403, detail="Timesheet access denied")


def _replace_timesheet_entries(db: Session, sheet: PMSTimesheet, entries: list, current_user: User) -> None:
    if sheet.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected timesheets can be edited")
    if sheet.user_id != current_user.id and not _can_manage_timesheets(current_user):
        raise HTTPException(status_code=403, detail="Cannot edit another user's timesheet")
    week_end = sheet.week_start_date + timedelta(days=6)
    existing = _timesheet_logs(db, sheet)
    existing_by_id = {log.id: log for log in existing}
    seen_ids: set[int] = set()
    for entry in entries:
        if entry.duration_minutes <= 0:
            continue
        if entry.log_date < sheet.week_start_date or entry.log_date > week_end:
            raise HTTPException(status_code=400, detail="Entry date must be inside the timesheet week")
        project = get_project_for_action(db, entry.project_id, current_user, "log_time")
        if entry.task_id:
            task, task_project = get_task_project_for_action(db, entry.task_id, current_user, "log_time")
            if task_project.id != project.id:
                raise HTTPException(status_code=400, detail="Task does not belong to selected project")
        log = existing_by_id.get(entry.time_log_id) if entry.time_log_id else None
        if log and log.user_id != sheet.user_id:
            raise HTTPException(status_code=400, detail="Time log does not belong to this timesheet user")
        if not log:
            log = PMSTimeLog(user_id=sheet.user_id, timesheet_id=sheet.id)
            db.add(log)
        log.project_id = entry.project_id
        log.task_id = entry.task_id
        log.log_date = entry.log_date
        log.duration_minutes = entry.duration_minutes
        log.description = entry.description
        log.is_billable = entry.is_billable
        log.approval_status = "Pending"
        log.timesheet_id = sheet.id
        db.add(log)
        db.flush()
        seen_ids.add(log.id)
    for log in existing:
        if log.id not in seen_ids and log.timesheet_id == sheet.id:
            db.delete(log)
    sheet.status = "draft"
    sheet.rejection_reason = None
    db.add(sheet)


def _sync_sprint_rollups(db: Session, sprint: PMSSprint) -> None:
    tasks = db.query(PMSTask).filter(
        PMSTask.sprint_id == sprint.id,
        PMSTask.deleted_at == None,
    ).all()
    sprint.committed_task_count = sprint.committed_task_count or len(tasks)
    if sprint.status == "Completed":
        sprint.completed_story_points = sum(_task_points(task) for task in tasks if task.status in DONE_STATUSES)
        sprint.velocity_points = sprint.completed_story_points


def _sprint_task_summary(task: PMSTask) -> dict:
    return {
        "id": task.id,
        "task_key": task.task_key,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "story_points": _task_points(task),
        "assignee_user_id": task.assignee_user_id,
        "due_date": task.due_date,
    }


def _next_sprint_action_task_key(db: Session, sprint: PMSSprint, project: PMSProject) -> str:
    base = re.sub(r"[^A-Z0-9]+", "", (project.project_key or "PMS").upper())[:12] or "PMS"
    prefix = f"{base}-RET"
    count = db.query(PMSTask).filter(PMSTask.project_id == sprint.project_id, PMSTask.task_key.ilike(f"{prefix}%")).count() + 1
    while True:
        key = f"{prefix}-{count}"[:30].upper()
        existing = db.query(PMSTask).filter(PMSTask.project_id == sprint.project_id, PMSTask.task_key == key).first()
        if not existing:
            return key
        count += 1


def _upsert_sprint_action_items(
    db: Session,
    sprint: PMSSprint,
    project: PMSProject,
    current_user: User,
    action_items: list[dict],
    create_tasks: bool = False,
) -> list[PMSSprintRetroActionItem]:
    if not action_items:
        return db.query(PMSSprintRetroActionItem).filter(PMSSprintRetroActionItem.sprint_id == sprint.id).all()
    existing = db.query(PMSSprintRetroActionItem).filter(PMSSprintRetroActionItem.sprint_id == sprint.id).all()
    for item in existing:
        db.delete(item)
    db.flush()
    created_items: list[PMSSprintRetroActionItem] = []
    for raw_item in action_items:
        title = str(raw_item.get("title") or "").strip()
        if not title:
            continue
        owner_user_id = raw_item.get("owner_user_id")
        due_date_value = raw_item.get("due_date")
        if isinstance(due_date_value, str) and due_date_value:
            due_date_value = date.fromisoformat(due_date_value)
        elif not due_date_value:
            due_date_value = None
        task_id = None
        if create_tasks:
            task = PMSTask(
                project_id=sprint.project_id,
                sprint_id=None,
                title=title,
                description=f"Retrospective action item from {sprint.name}",
                task_key=_next_sprint_action_task_key(db, sprint, project),
                work_type="Task",
                status="To Do",
                priority="Medium",
                assignee_user_id=owner_user_id,
                reporter_user_id=current_user.id,
                due_date=due_date_value,
            )
            db.add(task)
            db.flush()
            task_id = task.id
            _record_activity(db, sprint.project_id, current_user, "subtask.created", "task", task.id, f"Created retro action task {task.task_key}", task_id=task.id, sprint_id=sprint.id)
        action_item = PMSSprintRetroActionItem(
            organization_id=organization_id_for(current_user),
            sprint_id=sprint.id,
            title=title,
            owner_user_id=owner_user_id,
            due_date=due_date_value,
            created_task_id=task_id,
            status=raw_item.get("status") or "Open",
        )
        db.add(action_item)
        created_items.append(action_item)
    return created_items


def _sync_task_planning_links(db: Session, project_id: int, task_data: dict) -> None:
    """Validate normalized planning links and mirror labels for existing UI fields."""
    if task_data.get("epic_id"):
        epic = db.query(PMSEpic).filter(
            PMSEpic.id == task_data["epic_id"],
            PMSEpic.project_id == project_id,
            PMSEpic.deleted_at == None,
        ).first()
        if not epic:
            raise HTTPException(status_code=400, detail="Epic does not belong to selected project")
        task_data["epic_key"] = epic.epic_key
        task_data["initiative"] = epic.name
    if task_data.get("component_id"):
        component = db.query(PMSComponent).filter(
            PMSComponent.id == task_data["component_id"],
            PMSComponent.project_id == project_id,
        ).first()
        if not component:
            raise HTTPException(status_code=400, detail="Component does not belong to selected project")
        task_data["component"] = component.name
    if task_data.get("release_id"):
        release = db.query(PMSRelease).filter(
            PMSRelease.id == task_data["release_id"],
            PMSRelease.project_id == project_id,
            PMSRelease.deleted_at == None,
        ).first()
        if not release:
            raise HTTPException(status_code=400, detail="Release does not belong to selected project")
        task_data["release_name"] = release.name
        task_data["fix_version"] = release.name


def _reorder_tasks_in_scope(db: Session, project_id: int, task_ids: list[int], sprint_id: int | None) -> list[PMSTask]:
    requested_ids = list(dict.fromkeys(task_ids))
    if len(requested_ids) != len(task_ids):
        raise HTTPException(status_code=400, detail="Task reorder cannot contain duplicate task ids")
    tasks = db.query(PMSTask).filter(
        PMSTask.id.in_(requested_ids),
        PMSTask.project_id == project_id,
        PMSTask.deleted_at == None,
    ).all()
    tasks_by_id = {task.id: task for task in tasks}
    if set(tasks_by_id) != set(requested_ids):
        raise HTTPException(status_code=404, detail="One or more tasks were not found in this project")
    for task in tasks:
        if task.sprint_id != sprint_id:
            raise HTTPException(status_code=400, detail="All reordered tasks must be in the selected backlog or sprint")
    for index, task_id in enumerate(requested_ids, start=1):
        tasks_by_id[task_id].rank = index
        db.add(tasks_by_id[task_id])
    return [tasks_by_id[task_id] for task_id in requested_ids]


@router.get("/module-info")
def module_info():
    return {
        "key": "project_management",
        "name": "KaryaFlow",
        "status": "installed",
        "description": "Complete project management with Kanban, Gantt, milestones, and collaboration",
        "modules": [
            "clients",
            "projects",
            "project-members",
            "epics",
            "components",
            "releases",
            "boards",
            "board-columns",
            "tasks",
            "dependencies",
            "bulk-updates",
            "saved-filters",
            "activity-feed",
            "release-readiness",
            "workload-capacity",
            "velocity-burndown",
            "checklists",
            "milestones",
            "sprints",
            "files",
            "comments",
            "time-logs",
            "client-approvals",
            "project-intake",
        ],
    }


# ============= CLIENTS =============
@router.post("/clients", response_model=PMSClientResponse)
def create_client(
    client_in: PMSClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new client."""
    if not has_any_permission(current_user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(status_code=403, detail="Project management permission required")
    db_client = PMSClient(
        organization_id=organization_id_for(current_user),
        **client_in.dict()
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


@router.get("/clients", response_model=list[PMSClientResponse])
def list_clients(
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all clients for the organization."""
    if not has_any_permission(current_user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(status_code=403, detail="Project management permission required")
    clients = db.query(PMSClient).filter(
        PMSClient.organization_id == organization_id_for(current_user),
        PMSClient.deleted_at == None
    ).offset(skip).limit(limit).all()
    return clients


@router.get("/clients/{client_id}", response_model=PMSClientResponse)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific client."""
    if not has_any_permission(current_user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(status_code=403, detail="Project management permission required")
    client = db.query(PMSClient).filter(
        PMSClient.id == client_id,
        PMSClient.organization_id == organization_id_for(current_user)
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/clients/{client_id}", response_model=PMSClientResponse)
def update_client(
    client_id: int,
    client_in: PMSClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a client."""
    if not has_any_permission(current_user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(status_code=403, detail="Project management permission required")
    client = db.query(PMSClient).filter(
        PMSClient.id == client_id,
        PMSClient.organization_id == organization_id_for(current_user)
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    update_data = client_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)
    
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/clients/{client_id}")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft delete a client."""
    if not has_any_permission(current_user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(status_code=403, detail="Project management permission required")
    client = db.query(PMSClient).filter(
        PMSClient.id == client_id,
        PMSClient.organization_id == organization_id_for(current_user)
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    from datetime import datetime
    client.deleted_at = datetime.utcnow()
    db.add(client)
    db.commit()
    return {"message": "Client deleted"}


def _project_key_from_title(db: Session, organization_id: int | None, title: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title.upper())
    base = "".join(word[:3] for word in words[:2])[:8] or "PRJ"
    candidate = base
    counter = 1
    while db.query(PMSProject).filter(PMSProject.organization_id == organization_id, PMSProject.project_key == candidate).first():
        counter += 1
        candidate = f"{base}{counter}"[:20]
    return candidate


@router.post("/intake", response_model=PMSProjectIntakeResponse, status_code=status.HTTP_201_CREATED)
def create_project_intake(
    intake_in: PMSProjectIntakeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    intake = PMSProjectIntake(
        organization_id=organization_id_for(current_user),
        requester_user_id=current_user.id,
        requester_email=intake_in.requester_email or current_user.email,
        requester_name=intake_in.requester_name or _user_display_name(current_user),
        **intake_in.dict(exclude={"requester_email", "requester_name"}),
    )
    db.add(intake)
    db.commit()
    db.refresh(intake)
    return intake


@router.get("/intake", response_model=list[PMSProjectIntakeResponse])
def list_project_intakes(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0),
    limit: int = Query(100, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PMSProjectIntake).filter(PMSProjectIntake.organization_id == organization_id_for(current_user))
    if not has_any_permission(current_user, PMS_GLOBAL_MANAGE_PROJECTS):
        query = query.filter(PMSProjectIntake.requester_user_id == current_user.id)
    if status_filter:
        query = query.filter(PMSProjectIntake.status == status_filter)
    return query.order_by(desc(PMSProjectIntake.created_at)).offset(skip).limit(limit).all()


@router.post("/intake/{intake_id}/review", response_model=PMSProjectIntakeResponse)
def review_project_intake(
    intake_id: int,
    review: PMSProjectIntakeReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_any_permission(current_user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(status_code=403, detail="Project management permission required")
    intake = db.query(PMSProjectIntake).filter(
        PMSProjectIntake.id == intake_id,
        PMSProjectIntake.organization_id == organization_id_for(current_user),
    ).first()
    if not intake:
        raise HTTPException(status_code=404, detail="Project intake not found")
    if intake.status not in {"submitted", "needs_info"}:
        raise HTTPException(status_code=400, detail="Only submitted intakes can be reviewed")

    decision = review.status.lower()
    if decision not in {"approved", "rejected", "needs_info"}:
        raise HTTPException(status_code=400, detail="status must be approved, rejected, or needs_info")

    if decision == "approved":
        client_id = intake.client_id
        if not client_id and intake.client_name:
            client = PMSClient(
                organization_id=organization_id_for(current_user),
                name=intake.client_name,
                company_name=intake.client_name,
            )
            db.add(client)
            db.flush()
            client_id = client.id
        project_key = (review.project_key or _project_key_from_title(db, organization_id_for(current_user), intake.title)).upper()
        if db.query(PMSProject).filter(
            PMSProject.organization_id == organization_id_for(current_user),
            PMSProject.project_key == project_key,
        ).first():
            raise HTTPException(status_code=400, detail="Project key already exists")
        project = PMSProject(
            organization_id=organization_id_for(current_user),
            client_id=client_id,
            manager_user_id=review.manager_user_id or current_user.id,
            name=intake.title,
            project_key=project_key,
            description=intake.description,
            status="Active",
            priority=intake.priority,
            start_date=intake.desired_start_date,
            due_date=intake.desired_due_date,
            budget_amount=intake.budget_amount,
        )
        db.add(project)
        db.flush()
        db.add(PMSProjectMember(project_id=project.id, user_id=current_user.id, role="Manager"))
        if project.manager_user_id and project.manager_user_id != current_user.id:
            db.add(PMSProjectMember(project_id=project.id, user_id=project.manager_user_id, role="Manager"))
        intake.created_project_id = project.id

    intake.status = decision
    intake.review_notes = review.review_notes
    intake.reviewed_by_user_id = current_user.id
    intake.reviewed_at = datetime.utcnow()
    db.add(intake)
    db.commit()
    db.refresh(intake)
    return intake


# ============= PROJECTS =============
@router.post("/projects", response_model=PMSProjectResponse)
def create_project(
    project_in: PMSProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new project."""
    if not has_any_permission(current_user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(status_code=403, detail="Project management permission required")
    # Check unique constraint on project_key
    existing = db.query(PMSProject).filter(
        PMSProject.organization_id == organization_id_for(current_user),
        PMSProject.project_key == project_in.project_key.upper()
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project key already exists")
    
    db_project = PMSProject(
        organization_id=organization_id_for(current_user),
        **project_in.dict()
    )
    if not db_project.owner_user_id:
        db_project.owner_user_id = db_project.manager_user_id or current_user.id
    if db_project.planned_start_date and not db_project.start_date:
        db_project.start_date = db_project.planned_start_date
    if db_project.planned_end_date and not db_project.due_date:
        db_project.due_date = db_project.planned_end_date
    db.add(db_project)
    db.flush()
    _record_activity(db, db_project.id, current_user, "project.created", "project", db_project.id, f"Created project {db_project.project_key}")
    db.commit()
    db.refresh(db_project)
    if not db.query(PMSProjectMember).filter(
        PMSProjectMember.project_id == db_project.id,
        PMSProjectMember.user_id == current_user.id,
    ).first():
        db.add(PMSProjectMember(project_id=db_project.id, user_id=current_user.id, role="Manager"))
        if db_project.manager_user_id and db_project.manager_user_id != current_user.id:
            db.add(PMSProjectMember(project_id=db_project.id, user_id=db_project.manager_user_id, role="Manager"))
        db.commit()
    _broadcast_realtime(
        current_user,
        "project.updated",
        project_id=db_project.id,
        message=f"Project {db_project.name} was created",
        entity={"id": db_project.id, "name": db_project.name, "projectKey": db_project.project_key},
    )
    return db_project


@router.get("/projects", response_model=list[PMSProjectResponse])
def list_projects(
    skip: int = Query(0),
    limit: int = Query(100),
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all projects for the organization."""
    query = accessible_project_query(db, current_user)
    
    if status:
        query = query.filter(PMSProject.status == status)
    
    projects = query.offset(skip).limit(limit).all()
    return projects


@router.get("/projects/{project_id}", response_model=PMSProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific project."""
    return get_project_for_action(db, project_id, current_user)


@router.patch("/projects/{project_id}", response_model=PMSProjectResponse)
def update_project(
    project_id: int,
    project_in: PMSProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a project."""
    project = get_project_for_action(db, project_id, current_user, "edit_project")
    
    before = {field: getattr(project, field) for field in project_in.dict(exclude_unset=True)}
    update_data = project_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    if update_data.get("status") in {"Completed", "Cancelled"} and not project.actual_end_date:
        project.actual_end_date = date.today()
    if update_data.get("status") == "Active" and not project.actual_start_date:
        project.actual_start_date = date.today()
    
    db.add(project)
    if update_data:
        _record_activity(db, project.id, current_user, "project.updated", "project", project.id, f"Updated project {project.project_key}", metadata={"changed_fields": update_data, "old_values": before})
    if "status" in update_data:
        _record_activity(db, project.id, current_user, "project.status_changed", "project", project.id, f"Changed project status to {project.status}", metadata={"old_value": before.get("status"), "new_value": project.status})
    if "budget_amount" in update_data or "estimated_cost" in update_data:
        _record_activity(db, project.id, current_user, "project.budget_changed", "project", project.id, f"Changed project budget for {project.project_key}", metadata={"old_values": before, "new_values": update_data})
    db.commit()
    db.refresh(project)
    _broadcast_realtime(
        current_user,
        "project.updated",
        project_id=project.id,
        message=f"Project {project.name} was updated",
        entity={"id": project.id, "name": project.name, "projectKey": project.project_key},
        data={"changedFields": list(update_data.keys())},
    )
    return project


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft delete a project."""
    project = get_project_for_action(db, project_id, current_user, "edit_project")
    
    from datetime import datetime
    project.deleted_at = datetime.utcnow()
    db.add(project)
    _record_activity(db, project.id, current_user, "project.deleted", "project", project.id, f"Deleted project {project.project_key}")
    db.commit()
    return {"message": "Project deleted"}


@router.post("/projects/{project_id}/archive", response_model=PMSProjectResponse)
def archive_project(
    project_id: int,
    archive: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_action(db, project_id, current_user, "edit_project")
    project.is_archived = archive
    _record_activity(db, project.id, current_user, "project.archived" if archive else "project.unarchived", "project", project.id, f"{'Archived' if archive else 'Unarchived'} project {project.project_key}")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.post("/projects/{project_id}/clone", response_model=PMSProjectResponse, status_code=status.HTTP_201_CREATED)
def clone_project(
    project_id: int,
    clone_in: ProjectCloneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = get_project_for_action(db, project_id, current_user, "browse")
    if not can_access_project(db, source, current_user, "edit_project") and not has_any_permission(current_user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(status_code=403, detail="Project management permission required")
    project_key = clone_in.project_key.upper()
    if db.query(PMSProject).filter(PMSProject.organization_id == source.organization_id, PMSProject.project_key == project_key).first():
        raise HTTPException(status_code=400, detail="Project key already exists")
    cloned = PMSProject(
        organization_id=source.organization_id,
        client_id=source.client_id,
        manager_user_id=source.manager_user_id or current_user.id,
        owner_user_id=source.owner_user_id or source.manager_user_id or current_user.id,
        department_id=source.department_id,
        branch_id=source.branch_id,
        name=clone_in.name,
        project_key=project_key,
        category=source.category,
        description=source.description,
        status=clone_in.status,
        priority=source.priority,
        health="Good",
        start_date=source.start_date,
        due_date=source.due_date,
        planned_start_date=source.planned_start_date,
        planned_end_date=source.planned_end_date,
        budget_amount=source.budget_amount,
        estimated_hours=source.estimated_hours,
        estimated_cost=source.estimated_cost,
        billing_status="Unbilled",
        is_client_visible=source.is_client_visible,
        is_template=clone_in.as_template,
    )
    db.add(cloned)
    db.flush()
    milestone_map: dict[int, int] = {}
    if clone_in.include_milestones:
        for milestone in db.query(PMSMilestone).filter(PMSMilestone.project_id == source.id).all():
            item = PMSMilestone(
                project_id=cloned.id,
                owner_user_id=milestone.owner_user_id,
                name=milestone.name,
                description=milestone.description,
                status="Not Started",
                start_date=milestone.start_date,
                due_date=milestone.due_date,
                progress_percent=0,
                client_approval_status=milestone.client_approval_status,
            )
            db.add(item)
            db.flush()
            milestone_map[milestone.id] = item.id
    task_map: dict[int, int] = {}
    if clone_in.include_tasks:
        source_tasks = db.query(PMSTask).filter(PMSTask.project_id == source.id, PMSTask.deleted_at == None).order_by(PMSTask.parent_task_id.isnot(None), PMSTask.id).all()
        for task in source_tasks:
            item = PMSTask(
                project_id=cloned.id,
                milestone_id=milestone_map.get(task.milestone_id),
                parent_task_id=task_map.get(task.parent_task_id),
                assignee_user_id=task.assignee_user_id,
                reporter_user_id=current_user.id,
                title=task.title,
                description=task.description,
                task_key=task.task_key.replace(source.project_key, cloned.project_key, 1) if task.task_key.startswith(source.project_key) else f"{cloned.project_key}-{len(task_map) + 1}",
                work_type=task.work_type,
                status="To Do",
                priority=task.priority,
                start_date=task.start_date,
                due_date=task.due_date,
                estimated_hours=task.estimated_hours,
                original_estimate_hours=task.original_estimate_hours,
                remaining_estimate_hours=task.remaining_estimate_hours,
                story_points=task.story_points,
                rank=task.rank,
                security_level=task.security_level,
                position=task.position,
                is_client_visible=task.is_client_visible,
                recurrence_rule=task.recurrence_rule,
                recurrence_interval=task.recurrence_interval,
                recurrence_until=task.recurrence_until,
            )
            db.add(item)
            db.flush()
            task_map[task.id] = item.id
    if clone_in.include_tasks and clone_in.include_dependencies:
        for dependency in db.query(PMSTaskDependency).filter(PMSTaskDependency.task_id.in_(list(task_map.keys()) or [0])).all():
            if dependency.task_id in task_map and dependency.depends_on_task_id in task_map:
                db.add(PMSTaskDependency(
                    task_id=task_map[dependency.task_id],
                    depends_on_task_id=task_map[dependency.depends_on_task_id],
                    dependency_type=dependency.dependency_type,
                    lag_days=dependency.lag_days,
                ))
    team_user_ids: set[int] = set()
    if clone_in.include_team:
        for member in db.query(PMSProjectMember).filter(PMSProjectMember.project_id == source.id).all():
            db.add(PMSProjectMember(project_id=cloned.id, user_id=member.user_id, role=member.role, allocation_percent=member.allocation_percent))
            team_user_ids.add(member.user_id)
    if current_user.id not in team_user_ids:
        db.add(PMSProjectMember(project_id=cloned.id, user_id=current_user.id, role="Project Manager"))
    _record_activity(db, cloned.id, current_user, "project.cloned", "project", cloned.id, f"Cloned project {source.project_key} into {cloned.project_key}", metadata={"source_project_id": source.id})
    db.commit()
    db.refresh(cloned)
    return cloned


@router.get("/project-templates", response_model=list[PMSProjectResponse])
def list_project_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return accessible_project_query(db, current_user).filter(PMSProject.is_template == True).order_by(PMSProject.name).all()


# ============= PROJECT MEMBERS =============
@router.post("/projects/{project_id}/members", response_model=PMSProjectMemberResponse, status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_id: int,
    member_in: PMSProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a user to a project with a project role."""
    get_project_for_action(db, project_id, current_user, "manage_members")
    existing = db.query(PMSProjectMember).filter(
        PMSProjectMember.project_id == project_id,
        PMSProjectMember.user_id == member_in.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project member already exists")
    member = PMSProjectMember(project_id=project_id, **member_in.dict())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/projects/{project_id}/members", response_model=list[PMSProjectMemberResponse])
def list_project_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List project members visible to project users."""
    get_project_for_action(db, project_id, current_user, "browse")
    return db.query(PMSProjectMember).filter(PMSProjectMember.project_id == project_id).all()


@router.patch("/projects/{project_id}/members/{member_id}", response_model=PMSProjectMemberResponse)
def update_project_member(
    project_id: int,
    member_id: int,
    member_in: PMSProjectMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a project member role."""
    get_project_for_action(db, project_id, current_user, "manage_members")
    member = db.query(PMSProjectMember).filter(
        PMSProjectMember.id == member_id,
        PMSProjectMember.project_id == project_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Project member not found")
    for field, value in member_in.dict(exclude_unset=True).items():
        setattr(member, field, value)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/projects/{project_id}/members/{member_id}")
def remove_project_member(
    project_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a user from a project."""
    get_project_for_action(db, project_id, current_user, "manage_members")
    member = db.query(PMSProjectMember).filter(
        PMSProjectMember.id == member_id,
        PMSProjectMember.project_id == project_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Project member not found")
    db.delete(member)
    db.commit()
    return {"message": "Project member removed"}


# ============= EPICS, COMPONENTS, RELEASES =============
@router.post("/projects/{project_id}/epics", response_model=PMSEpicResponse, status_code=status.HTTP_201_CREATED)
def create_epic(
    project_id: int,
    epic_in: PMSEpicCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a project epic."""
    project = get_project_for_action(db, project_id, current_user, "manage_tasks")
    existing = db.query(PMSEpic).filter(
        PMSEpic.project_id == project_id,
        PMSEpic.epic_key == epic_in.epic_key.upper(),
        PMSEpic.deleted_at == None,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Epic key already exists in this project")
    data = epic_in.dict()
    if data.get("end_date") and not data.get("target_date"):
        data["target_date"] = data["end_date"]
    if data.get("target_date") and not data.get("end_date"):
        data["end_date"] = data["target_date"]
    epic = PMSEpic(project_id=project_id, organization_id=project.organization_id, **data)
    db.add(epic)
    db.commit()
    db.refresh(epic)
    return epic


@router.get("/projects/{project_id}/epics", response_model=list[PMSEpicResponse])
def list_epics(
    project_id: int,
    status_filter: str = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List project epics."""
    get_project_for_action(db, project_id, current_user, "browse")
    query = db.query(PMSEpic).filter(PMSEpic.project_id == project_id, PMSEpic.deleted_at == None)
    if status_filter:
        query = query.filter(PMSEpic.status == status_filter)
    return query.order_by(PMSEpic.created_at.desc()).all()


@router.patch("/epics/{epic_id}", response_model=PMSEpicResponse)
def update_epic(
    epic_id: int,
    epic_in: PMSEpicUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a project epic."""
    epic = db.query(PMSEpic).filter(PMSEpic.id == epic_id, PMSEpic.deleted_at == None).first()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    get_project_for_action(db, epic.project_id, current_user, "manage_tasks")
    update_data = epic_in.dict(exclude_unset=True)
    if "end_date" in update_data and "target_date" not in update_data:
        update_data["target_date"] = update_data["end_date"]
    if "target_date" in update_data and "end_date" not in update_data:
        update_data["end_date"] = update_data["target_date"]
    for field, value in update_data.items():
        setattr(epic, field, value)
    db.add(epic)
    db.commit()
    db.refresh(epic)
    return epic


@router.get("/roadmap")
def get_roadmap(
    projectId: int = Query(None),
    ownerId: int = Query(None),
    status: str = Query(None),
    from_date: date = Query(None, alias="from"),
    to: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return cross-project epic roadmap data for accessible projects."""
    accessible_project_ids = accessible_project_query(db, current_user).with_entities(PMSProject.id)
    project_query = accessible_project_query(db, current_user)
    if projectId:
        get_project_for_action(db, projectId, current_user, "browse")
        project_query = project_query.filter(PMSProject.id == projectId)
    projects = project_query.order_by(PMSProject.name).all()
    project_ids = [project.id for project in projects]
    projects_by_id = {project.id: project for project in projects}

    epic_query = db.query(PMSEpic).filter(PMSEpic.deleted_at == None, PMSEpic.project_id.in_(project_ids)) if project_ids else db.query(PMSEpic).filter(False)
    if ownerId:
        epic_query = epic_query.filter(PMSEpic.owner_user_id == ownerId)
    if status:
        epic_query = epic_query.filter(PMSEpic.status == status)
    if from_date:
        epic_query = epic_query.filter(or_(PMSEpic.end_date == None, PMSEpic.end_date >= from_date, PMSEpic.target_date >= from_date))
    if to:
        epic_query = epic_query.filter(or_(PMSEpic.start_date == None, PMSEpic.start_date <= to))
    epics = epic_query.order_by(PMSEpic.start_date.is_(None), PMSEpic.start_date, PMSEpic.target_date, PMSEpic.name).all()
    epic_ids = [epic.id for epic in epics]

    tasks = db.query(PMSTask).filter(
        PMSTask.deleted_at == None,
        PMSTask.epic_id.in_(epic_ids),
    ).order_by(PMSTask.rank.is_(None), PMSTask.rank, PMSTask.position, PMSTask.id).all() if epic_ids else []
    tasks_by_epic_id: dict[int, list[PMSTask]] = {}
    for task in tasks:
        tasks_by_epic_id.setdefault(task.epic_id, []).append(task)

    task_ids = [task.id for task in tasks]
    dependencies = db.query(PMSTaskDependency).filter(
        or_(PMSTaskDependency.task_id.in_(task_ids), PMSTaskDependency.depends_on_task_id.in_(task_ids))
    ).all() if task_ids else []
    dependencies_by_epic_id: dict[int, list[PMSTaskDependency]] = {}
    task_epic_by_id = {task.id: task.epic_id for task in tasks}
    for dependency in dependencies:
        epic_id = task_epic_by_id.get(dependency.task_id) or task_epic_by_id.get(dependency.depends_on_task_id)
        if epic_id:
            dependencies_by_epic_id.setdefault(epic_id, []).append(dependency)

    owner_ids = {epic.owner_user_id for epic in epics if epic.owner_user_id}
    owners_by_id = {user.id: user for user in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}

    sprint_query = db.query(PMSSprint).filter(PMSSprint.project_id.in_(project_ids)) if project_ids else db.query(PMSSprint).filter(False)
    if from_date:
        sprint_query = sprint_query.filter(PMSSprint.end_date >= from_date)
    if to:
        sprint_query = sprint_query.filter(PMSSprint.start_date <= to)
    sprints = sprint_query.order_by(PMSSprint.start_date).all()

    return {
        "projects": [{"id": project.id, "name": project.name, "project_key": project.project_key} for project in projects],
        "owners": [{"id": user.id, "name": _user_display_name(user)} for user in owners_by_id.values()],
        "statuses": [row[0] for row in db.query(PMSEpic.status).filter(PMSEpic.project_id.in_(project_ids), PMSEpic.deleted_at == None).distinct().order_by(PMSEpic.status).all()] if project_ids else [],
        "sprints": [
            {
                "id": sprint.id,
                "project_id": sprint.project_id,
                "project_name": projects_by_id.get(sprint.project_id).name if projects_by_id.get(sprint.project_id) else None,
                "name": sprint.name,
                "status": sprint.status,
                "start_date": sprint.start_date,
                "end_date": sprint.end_date,
            }
            for sprint in sprints
        ],
        "epics": [
            _epic_payload(db, epic, projects_by_id[epic.project_id], owners_by_id.get(epic.owner_user_id), tasks_by_epic_id.get(epic.id, []), dependencies_by_epic_id.get(epic.id, []))
            for epic in epics
            if epic.project_id in projects_by_id
        ],
    }


@router.patch("/epics/{epic_id}/schedule")
def update_epic_schedule(
    epic_id: int,
    schedule_in: EpicScheduleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update epic schedule/status from roadmap planning."""
    epic = db.query(PMSEpic).filter(PMSEpic.id == epic_id, PMSEpic.deleted_at == None).first()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    project = get_project_for_action(db, epic.project_id, current_user, "manage_tasks")
    previous = {"start_date": epic.start_date, "end_date": _epic_end_date(epic), "status": epic.status}
    update_data = schedule_in.dict(exclude_unset=True)
    if "start_date" in update_data:
        epic.start_date = update_data["start_date"]
    if "end_date" in update_data or "target_date" in update_data:
        epic.end_date = update_data.get("end_date", update_data.get("target_date"))
        epic.target_date = epic.end_date
    if "status" in update_data and update_data["status"]:
        epic.status = update_data["status"]
    if epic.start_date and _epic_end_date(epic) and epic.start_date > _epic_end_date(epic):
        raise HTTPException(status_code=400, detail="Epic start date cannot be after end date")
    db.add(epic)
    if previous["start_date"] != epic.start_date or previous["end_date"] != _epic_end_date(epic):
        _record_activity(
            db,
            project.id,
            current_user,
            "epic.schedule_changed",
            "epic",
            epic.id,
            f"Updated roadmap dates for {epic.epic_key}",
            metadata={"old": previous, "new": {"start_date": epic.start_date, "end_date": _epic_end_date(epic)}},
        )
    if previous["status"] != epic.status:
        _record_activity(
            db,
            project.id,
            current_user,
            "epic.status_changed",
            "epic",
            epic.id,
            f"Changed {epic.epic_key} status to {epic.status}",
            metadata={"old_status": previous["status"], "new_status": epic.status},
        )
    db.commit()
    db.refresh(epic)
    return _epic_payload(db, epic, project, db.query(User).filter(User.id == epic.owner_user_id).first() if epic.owner_user_id else None, db.query(PMSTask).filter(PMSTask.epic_id == epic.id, PMSTask.deleted_at == None).all(), [])


@router.get("/epics/{epic_id}/tasks")
def list_epic_tasks(
    epic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tasks assigned to an epic."""
    epic = db.query(PMSEpic).filter(PMSEpic.id == epic_id, PMSEpic.deleted_at == None).first()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    get_project_for_action(db, epic.project_id, current_user, "browse")
    tasks = db.query(PMSTask).filter(PMSTask.epic_id == epic.id, PMSTask.deleted_at == None).order_by(PMSTask.rank.is_(None), PMSTask.rank, PMSTask.position, PMSTask.id).all()
    return _task_list_payloads(db, tasks)


@router.post("/projects/{project_id}/components", response_model=PMSComponentResponse, status_code=status.HTTP_201_CREATED)
def create_component(
    project_id: int,
    component_in: PMSComponentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a project component."""
    get_project_for_action(db, project_id, current_user, "manage_tasks")
    existing = db.query(PMSComponent).filter(
        PMSComponent.project_id == project_id,
        PMSComponent.name == component_in.name,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Component already exists in this project")
    component = PMSComponent(project_id=project_id, **component_in.dict())
    db.add(component)
    db.commit()
    db.refresh(component)
    return component


@router.get("/projects/{project_id}/components", response_model=list[PMSComponentResponse])
def list_components(
    project_id: int,
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List project components."""
    get_project_for_action(db, project_id, current_user, "browse")
    query = db.query(PMSComponent).filter(PMSComponent.project_id == project_id)
    if active_only:
        query = query.filter(PMSComponent.is_active == True)
    return query.order_by(PMSComponent.name).all()


@router.patch("/components/{component_id}", response_model=PMSComponentResponse)
def update_component(
    component_id: int,
    component_in: PMSComponentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a project component."""
    component = db.query(PMSComponent).filter(PMSComponent.id == component_id).first()
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")
    get_project_for_action(db, component.project_id, current_user, "manage_tasks")
    for field, value in component_in.dict(exclude_unset=True).items():
        setattr(component, field, value)
    db.add(component)
    db.commit()
    db.refresh(component)
    return component


@router.post("/projects/{project_id}/releases", response_model=PMSReleaseResponse, status_code=status.HTTP_201_CREATED)
def create_release(
    project_id: int,
    release_in: PMSReleaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a project release."""
    get_project_for_action(db, project_id, current_user, "manage_tasks")
    existing = db.query(PMSRelease).filter(
        PMSRelease.project_id == project_id,
        PMSRelease.name == release_in.name,
        PMSRelease.deleted_at == None,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Release already exists in this project")
    release = PMSRelease(project_id=project_id, **release_in.dict())
    db.add(release)
    db.commit()
    db.refresh(release)
    return release


@router.get("/projects/{project_id}/releases", response_model=list[PMSReleaseResponse])
def list_releases(
    project_id: int,
    status_filter: str = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List project releases."""
    get_project_for_action(db, project_id, current_user, "browse")
    query = db.query(PMSRelease).filter(PMSRelease.project_id == project_id, PMSRelease.deleted_at == None)
    if status_filter:
        query = query.filter(PMSRelease.status == status_filter)
    return query.order_by(PMSRelease.release_date.is_(None), PMSRelease.release_date, PMSRelease.id).all()


@router.patch("/releases/{release_id}", response_model=PMSReleaseResponse)
def update_release(
    release_id: int,
    release_in: PMSReleaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a project release."""
    release = db.query(PMSRelease).filter(PMSRelease.id == release_id, PMSRelease.deleted_at == None).first()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    get_project_for_action(db, release.project_id, current_user, "manage_tasks")
    for field, value in release_in.dict(exclude_unset=True).items():
        setattr(release, field, value)
    db.add(release)
    db.commit()
    db.refresh(release)
    return release


@router.get("/releases/{release_id}/readiness", response_model=ReleaseReadinessResponse)
def get_release_readiness(
    release_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summarize release readiness, blockers, severity, and overdue risk."""
    release = db.query(PMSRelease).filter(PMSRelease.id == release_id, PMSRelease.deleted_at == None).first()
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    get_project_for_action(db, release.project_id, current_user, "browse")
    tasks = db.query(PMSTask).filter(
        PMSTask.project_id == release.project_id,
        PMSTask.release_id == release_id,
        PMSTask.deleted_at == None,
    ).all()
    total = len(tasks)
    done = len([task for task in tasks if task.status in DONE_STATUSES])
    today = date.today()
    open_blockers = len([task for task in tasks if task.is_blocking and task.status not in DONE_STATUSES])
    overdue = len([task for task in tasks if task.due_date and task.due_date < today and task.status not in DONE_STATUSES])
    severity_counts: dict[str, int] = {}
    for task in tasks:
        if task.severity:
            severity_counts[task.severity] = severity_counts.get(task.severity, 0) + 1
    readiness = release.readiness_percent if release.readiness_percent is not None else int((done / total) * 100) if total else 0
    health = "Blocked" if open_blockers else "At Risk" if overdue or severity_counts.get("S1", 0) else "Ready" if readiness >= 90 else "On Track"
    return {
        "release_id": release.id,
        "release_name": release.name,
        "readiness_percent": readiness,
        "health": health,
        "total_tasks": total,
        "done_tasks": done,
        "open_blockers": open_blockers,
        "overdue_tasks": overdue,
        "severity_counts": severity_counts,
    }


# ============= TASKS (KANBAN & CRUD) =============
@router.post("/projects/{project_id}/tasks", response_model=PMSTaskResponse)
def create_task(
    project_id: int,
    task_in: PMSTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new task in a project."""
    # Verify project exists
    get_project_for_action(db, project_id, current_user, "manage_tasks")
    
    # Check unique constraint on task_key
    existing = db.query(PMSTask).filter(
        PMSTask.project_id == project_id,
        PMSTask.task_key == task_in.task_key.upper()
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Task key already exists in this project")
    
    task_data = task_in.dict()
    task_data['project_id'] = project_id
    parent_task = _ensure_valid_parent_task(db, project_id, None, task_data.get("parent_task_id"))
    if parent_task and not task_data.get("sprint_id"):
        task_data["sprint_id"] = parent_task.sprint_id
    if parent_task and not task_data.get("epic_id"):
        task_data["epic_id"] = parent_task.epic_id
    if parent_task and task_data.get("work_type") in (None, "Task"):
        task_data["work_type"] = "Sub-task"
    _sync_task_planning_links(db, project_id, task_data)
    if not task_data.get("column_id"):
        board = db.query(PMSBoard).filter(PMSBoard.project_id == project_id).first()
        if not board:
            board = PMSBoard(project_id=project_id, name="Default Board", board_type="Kanban")
            db.add(board)
            db.commit()
            db.refresh(board)
        status_to_key = {
            "Backlog": "BACKLOG",
            "To Do": "TODO",
            "In Progress": "IN_PROGRESS",
            "In Review": "IN_REVIEW",
            "Blocked": "IN_PROGRESS",
            "Done": "DONE",
        }
        target_status_key = status_to_key.get(task_data.get("status", "To Do"), "TODO")
        column = db.query(PMSBoardColumn).filter(
            PMSBoardColumn.board_id == board.id,
            PMSBoardColumn.status_key == target_status_key,
        ).first()
        if not column:
            defaults = [
                ("Backlog", "BACKLOG", 0),
                ("To Do", "TODO", 1),
                ("In Progress", "IN_PROGRESS", 2),
                ("In Review", "IN_REVIEW", 3),
                ("Done", "DONE", 4),
            ]
            for name, status_key, position in defaults:
                db.add(PMSBoardColumn(board_id=board.id, name=name, status_key=status_key, position=position))
            db.commit()
            column = db.query(PMSBoardColumn).filter(
                PMSBoardColumn.board_id == board.id,
                PMSBoardColumn.status_key == target_status_key,
            ).first()
        task_data["board_id"] = board.id
        task_data["column_id"] = column.id if column else None
        task_data["position"] = db.query(PMSTask).filter(
            PMSTask.project_id == project_id,
            PMSTask.column_id == task_data["column_id"],
            PMSTask.deleted_at == None,
        ).count()
    if task_data.get("rank") is None:
        task_data["rank"] = db.query(PMSTask).filter(
            PMSTask.project_id == project_id,
            PMSTask.deleted_at == None,
        ).count() + 1
    db_task = PMSTask(**task_data)
    
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    _record_activity(db, project_id, current_user, "task.created", "task", db_task.id, f"Created task {db_task.task_key}", task_id=db_task.id)
    if db_task.parent_task_id:
        _record_activity(
            db,
            project_id,
            current_user,
            "subtask.created",
            "task",
            db_task.id,
            f"Created sub-task {db_task.task_key}",
            task_id=db_task.parent_task_id,
            metadata={"subtask_id": db_task.id, "subtask_key": db_task.task_key, "title": db_task.title},
        )
    db.commit()
    _attach_subtask_counts(db, db_task)
    _broadcast_realtime(
        current_user,
        "task.created",
        project_id=project_id,
        task_id=db_task.id,
        message=f"Created task {db_task.task_key}",
        entity={"id": db_task.id, "taskKey": db_task.task_key, "title": db_task.title, "status": db_task.status},
    )
    return db_task


@router.get("/projects/{project_id}/tasks", response_model=list[PMSTaskResponse])
def list_tasks(
    project_id: int,
    skip: int = Query(0),
    limit: int = Query(100),
    status: str = Query(None),
    assignee_id: int = Query(None),
    sprint_id: int = Query(None),
    epic_id: int = Query(None),
    component_id: int = Query(None),
    release_id: int = Query(None),
    work_type: str = Query(None),
    epic_key: str = Query(None),
    component: str = Query(None),
    severity: str = Query(None),
    fix_version: str = Query(None),
    release_name: str = Query(None),
    security_level: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all tasks in a project."""
    # Verify project exists
    get_project_for_action(db, project_id, current_user, "browse")
    
    query = db.query(PMSTask).filter(
        PMSTask.project_id == project_id,
        PMSTask.deleted_at == None
    )
    
    if status:
        query = query.filter(PMSTask.status == status)
    if assignee_id:
        query = query.filter(PMSTask.assignee_user_id == assignee_id)
    if sprint_id:
        query = query.filter(PMSTask.sprint_id == sprint_id)
    if epic_id:
        query = query.filter(PMSTask.epic_id == epic_id)
    if component_id:
        query = query.filter(PMSTask.component_id == component_id)
    if release_id:
        query = query.filter(PMSTask.release_id == release_id)
    if work_type:
        query = query.filter(PMSTask.work_type == work_type)
    if epic_key:
        query = query.filter(PMSTask.epic_key == epic_key)
    if component:
        query = query.filter(PMSTask.component == component)
    if severity:
        query = query.filter(PMSTask.severity == severity)
    if fix_version:
        query = query.filter(PMSTask.fix_version == fix_version)
    if release_name:
        query = query.filter(PMSTask.release_name == release_name)
    if security_level:
        query = query.filter(PMSTask.security_level == security_level)
    
    tasks = query.order_by(PMSTask.rank.is_(None), PMSTask.rank, PMSTask.position, PMSTask.id).offset(skip).limit(limit).all()
    _attach_subtask_counts(db, tasks)
    return tasks


@router.get("/tasks")
def list_all_tasks(
    projectId: int = Query(None),
    sprintId: int = Query(None),
    epicId: int = Query(None),
    status: str = Query(None),
    priority: str = Query(None),
    assigneeId: int = Query(None),
    reporterId: int = None,
    tag: str = Query(None),
    search: str = Query(None),
    dueFrom: date = Query(None),
    dueTo: date = Query(None),
    createdFrom: date = None,
    createdTo: date = None,
    updatedFrom: date = None,
    updatedTo: date = None,
    storyPointsMin: int = None,
    storyPointsMax: int = None,
    sortBy: str = Query("updatedDate"),
    sortOrder: str = Query("desc"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all accessible PMS tasks for the issue navigator/table view."""
    accessible_project_ids = accessible_project_query(db, current_user).with_entities(PMSProject.id)
    query = db.query(PMSTask).join(PMSProject, PMSProject.id == PMSTask.project_id).filter(
        PMSTask.deleted_at == None,
        PMSTask.project_id.in_(accessible_project_ids),
    )

    if projectId:
        query = query.filter(PMSTask.project_id == projectId)
    if sprintId:
        query = query.filter(PMSTask.sprint_id == sprintId)
    if epicId:
        query = query.filter(PMSTask.epic_id == epicId)
    if status:
        query = query.filter(PMSTask.status == status)
    if priority:
        query = query.filter(PMSTask.priority == priority)
    if assigneeId:
        query = query.filter(PMSTask.assignee_user_id == assigneeId)
    if reporterId:
        query = query.filter(PMSTask.reporter_user_id == reporterId)
    if dueFrom:
        query = query.filter(PMSTask.due_date >= dueFrom)
    if dueTo:
        query = query.filter(PMSTask.due_date <= dueTo)
    if createdFrom:
        query = query.filter(func.date(PMSTask.created_at) >= createdFrom)
    if createdTo:
        query = query.filter(func.date(PMSTask.created_at) <= createdTo)
    if updatedFrom:
        query = query.filter(func.date(PMSTask.updated_at) >= updatedFrom)
    if updatedTo:
        query = query.filter(func.date(PMSTask.updated_at) <= updatedTo)
    if storyPointsMin is not None:
        query = query.filter(PMSTask.story_points >= storyPointsMin)
    if storyPointsMax is not None:
        query = query.filter(PMSTask.story_points <= storyPointsMax)
    if tag:
        query = query.join(PMSTaskTag, PMSTaskTag.task_id == PMSTask.id).join(PMSTag, PMSTag.id == PMSTaskTag.tag_id)
        query = query.filter(PMSTag.name == tag)
        user_org_id = organization_id_for(current_user)
        if user_org_id is not None and not current_user.is_superuser:
            query = query.filter(PMSTag.organization_id == user_org_id)
        query = query.distinct()
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            PMSTask.title.ilike(term),
            PMSTask.task_key.ilike(term),
            PMSTask.description.ilike(term),
            PMSTask.epic_key.ilike(term),
            PMSTask.initiative.ilike(term),
            PMSTask.component.ilike(term),
            PMSTask.release_name.ilike(term),
            PMSProject.name.ilike(term),
            PMSProject.project_key.ilike(term),
        ))

    priority_order = case(
        (PMSTask.priority == "Low", 1),
        (PMSTask.priority == "Medium", 2),
        (PMSTask.priority == "High", 3),
        (PMSTask.priority == "Urgent", 4),
        else_=0,
    )
    sort_map = {
        "dueDate": PMSTask.due_date,
        "due_date": PMSTask.due_date,
        "priority": priority_order,
        "updatedDate": PMSTask.updated_at,
        "updated_at": PMSTask.updated_at,
        "createdDate": PMSTask.created_at,
        "created_at": PMSTask.created_at,
        "storyPoints": PMSTask.story_points,
        "story_points": PMSTask.story_points,
        "status": PMSTask.status,
    }
    sort_column = sort_map.get(sortBy, PMSTask.updated_at)
    sort_expression = desc(sort_column) if sortOrder.lower() == "desc" else asc(sort_column)

    total = query.order_by(None).count()
    tasks = query.order_by(sort_expression, desc(PMSTask.id)).offset((page - 1) * pageSize).limit(pageSize).all()

    task_ids = [task.id for task in tasks]
    project_ids = {task.project_id for task in tasks}
    epic_ids = {task.epic_id for task in tasks if task.epic_id}
    sprint_ids = {task.sprint_id for task in tasks if task.sprint_id}
    user_ids = {task.assignee_user_id for task in tasks if task.assignee_user_id} | {task.reporter_user_id for task in tasks if task.reporter_user_id}

    projects_by_id = {project.id: project for project in db.query(PMSProject).filter(PMSProject.id.in_(project_ids)).all()} if project_ids else {}
    epics_by_id = {epic.id: epic for epic in db.query(PMSEpic).filter(PMSEpic.id.in_(epic_ids)).all()} if epic_ids else {}
    sprints_by_id = {sprint.id: sprint for sprint in db.query(PMSSprint).filter(PMSSprint.id.in_(sprint_ids)).all()} if sprint_ids else {}
    users_by_id = {user.id: user for user in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    tags_by_task_id: dict[int, list[str]] = {}
    if task_ids:
        tag_rows = db.query(PMSTaskTag.task_id, PMSTag.name).join(PMSTag, PMSTag.id == PMSTaskTag.tag_id).filter(
            PMSTaskTag.task_id.in_(task_ids)
        ).order_by(PMSTag.name).all()
        for task_id, tag_name in tag_rows:
            tags_by_task_id.setdefault(task_id, []).append(tag_name)

    filters_task_query = db.query(PMSTask).filter(
        PMSTask.deleted_at == None,
        PMSTask.project_id.in_(accessible_project_ids),
    )
    visible_project_ids = [row[0] for row in accessible_project_ids.all()]
    assignee_ids = [row[0] for row in filters_task_query.with_entities(PMSTask.assignee_user_id).filter(PMSTask.assignee_user_id != None).distinct().all()]
    reporter_ids = [row[0] for row in filters_task_query.with_entities(PMSTask.reporter_user_id).filter(PMSTask.reporter_user_id != None).distinct().all()]
    filter_user_ids = set(assignee_ids + reporter_ids)
    filter_users = {user.id: user for user in db.query(User).filter(User.id.in_(filter_user_ids)).all()} if filter_user_ids else {}
    tag_names = [
        row[0] for row in db.query(PMSTag.name)
        .join(PMSTaskTag, PMSTaskTag.tag_id == PMSTag.id)
        .join(PMSTask, PMSTask.id == PMSTaskTag.task_id)
        .filter(PMSTask.project_id.in_(visible_project_ids), PMSTask.deleted_at == None)
        .distinct()
        .order_by(PMSTag.name)
        .all()
    ] if visible_project_ids else []

    subtask_counts_by_task_id = _load_subtask_counts(db, task_ids)

    return {
        "items": [_task_list_payload(task, projects_by_id, epics_by_id, sprints_by_id, users_by_id, tags_by_task_id, subtask_counts_by_task_id) for task in tasks],
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "pages": (total + pageSize - 1) // pageSize,
        "filters": {
            "projects": [
                {"id": project.id, "name": project.name, "project_key": project.project_key}
                for project in accessible_project_query(db, current_user).order_by(PMSProject.name).all()
            ],
            "sprints": [
                {"id": sprint.id, "name": sprint.name, "project_id": sprint.project_id}
                for sprint in db.query(PMSSprint).filter(PMSSprint.project_id.in_(visible_project_ids)).order_by(PMSSprint.start_date.desc()).all()
            ] if visible_project_ids else [],
            "epics": [
                {"id": epic.id, "name": epic.name, "epic_key": epic.epic_key, "project_id": epic.project_id}
                for epic in db.query(PMSEpic).filter(PMSEpic.project_id.in_(visible_project_ids), PMSEpic.deleted_at == None).order_by(PMSEpic.name).all()
            ] if visible_project_ids else [],
            "statuses": [row[0] for row in filters_task_query.with_entities(PMSTask.status).filter(PMSTask.status != None).distinct().order_by(PMSTask.status).all()],
            "priorities": [row[0] for row in filters_task_query.with_entities(PMSTask.priority).filter(PMSTask.priority != None).distinct().order_by(PMSTask.priority).all()],
            "assignees": [{"id": user_id, "name": _user_display_name(filter_users.get(user_id))} for user_id in assignee_ids if filter_users.get(user_id)],
            "reporters": [{"id": user_id, "name": _user_display_name(filter_users.get(user_id))} for user_id in reporter_ids if filter_users.get(user_id)],
            "tags": tag_names,
        },
    }


@router.get("/backlog")
def get_backlog(
    projectId: int = Query(...),
    search: str = Query(None),
    sortBy: str = Query("rank"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return project backlog plus active/future/completed sprint task groups."""
    project = get_project_for_action(db, projectId, current_user, "browse")
    task_query = db.query(PMSTask).filter(
        PMSTask.project_id == project.id,
        PMSTask.deleted_at == None,
    )
    if search:
        term = f"%{search.strip()}%"
        task_query = task_query.filter(or_(PMSTask.title.ilike(term), PMSTask.task_key.ilike(term), PMSTask.description.ilike(term)))
    sort_map = {
        "priority": case(
            (PMSTask.priority == "Urgent", 1),
            (PMSTask.priority == "High", 2),
            (PMSTask.priority == "Medium", 3),
            (PMSTask.priority == "Low", 4),
            else_=5,
        ),
        "rank": PMSTask.rank,
        "createdDate": PMSTask.created_at,
        "created_at": PMSTask.created_at,
    }
    sort_column = sort_map.get(sortBy, PMSTask.rank)
    tasks = task_query.order_by(PMSTask.sprint_id.isnot(None), sort_column.is_(None), sort_column, PMSTask.position, PMSTask.id).all()
    tasks_by_sprint: dict[int | None, list[PMSTask]] = {}
    for task in tasks:
        tasks_by_sprint.setdefault(task.sprint_id, []).append(task)
    sprints = db.query(PMSSprint).filter(PMSSprint.project_id == project.id).order_by(
        case(
            (PMSSprint.status == "Active", 1),
            (PMSSprint.status == "Planned", 2),
            (PMSSprint.status == "Completed", 3),
            else_=4,
        ),
        PMSSprint.start_date,
        PMSSprint.id,
    ).all()
    return {
        "project": {"id": project.id, "name": project.name, "project_key": project.project_key},
        "backlog": _task_list_payloads(db, tasks_by_sprint.get(None, [])),
        "sprints": [
            {
                "id": sprint.id,
                "project_id": sprint.project_id,
                "name": sprint.name,
                "goal": sprint.goal,
                "status": sprint.status,
                "start_date": sprint.start_date,
                "end_date": sprint.end_date,
                "capacity_hours": float(sprint.capacity_hours or 0),
                "committed_task_count": sprint.committed_task_count,
                "committed_story_points": sprint.committed_story_points,
                "completed_story_points": sprint.completed_story_points,
                "scope_change_count": sprint.scope_change_count,
                "carry_forward_task_count": sprint.carry_forward_task_count,
                "started_at": sprint.started_at,
                "completed_at": sprint.completed_at,
                "created_at": sprint.created_at,
                "updated_at": sprint.updated_at,
                "tasks": _task_list_payloads(db, tasks_by_sprint.get(sprint.id, [])),
            }
            for sprint in sprints
        ],
    }


@router.get("/gantt")
def get_gantt(
    projectId: int = Query(None),
    sprintId: int = Query(None),
    assigneeId: int = Query(None),
    epicId: int = Query(None),
    status: str = Query(None),
    from_date: date = Query(None, alias="from"),
    to_date: date = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return scheduled tasks and dependencies for the Gantt/timeline view."""
    accessible_project_ids = accessible_project_query(db, current_user).with_entities(PMSProject.id)
    query = db.query(PMSTask).filter(
        PMSTask.deleted_at == None,
        PMSTask.project_id.in_(accessible_project_ids),
        or_(PMSTask.start_date != None, PMSTask.due_date != None),
    )
    if projectId:
        get_project_for_action(db, projectId, current_user, "browse")
        query = query.filter(PMSTask.project_id == projectId)
    if sprintId:
        query = query.filter(PMSTask.sprint_id == sprintId)
    if assigneeId:
        query = query.filter(PMSTask.assignee_user_id == assigneeId)
    if epicId:
        query = query.filter(PMSTask.epic_id == epicId)
    if status:
        query = query.filter(PMSTask.status == status)
    if from_date:
        query = query.filter(or_(PMSTask.due_date == None, PMSTask.due_date >= from_date))
    if to_date:
        query = query.filter(or_(PMSTask.start_date == None, PMSTask.start_date <= to_date))
    tasks = query.order_by(PMSTask.start_date.is_(None), PMSTask.start_date, PMSTask.due_date, PMSTask.rank, PMSTask.id).all()
    task_ids = [task.id for task in tasks]
    deps = db.query(PMSTaskDependency).filter(
        or_(PMSTaskDependency.task_id.in_(task_ids), PMSTaskDependency.depends_on_task_id.in_(task_ids))
    ).all() if task_ids else []
    related_ids = ({dep.task_id for dep in deps} | {dep.depends_on_task_id for dep in deps} | set(task_ids))
    related = {task.id: task for task in db.query(PMSTask).filter(PMSTask.id.in_(related_ids), PMSTask.deleted_at == None).all()} if related_ids else {}
    dependency_payloads = [
        _dependency_detail_payload(dep, related)
        for dep in deps
        if related.get(dep.task_id) and related.get(dep.depends_on_task_id)
    ]
    projects = [
        {"id": project.id, "name": project.name, "project_key": project.project_key}
        for project in accessible_project_query(db, current_user).order_by(PMSProject.name).all()
    ]
    visible_project_ids = [project["id"] for project in projects]
    sprints = [
        {"id": sprint.id, "name": sprint.name, "project_id": sprint.project_id, "status": sprint.status}
        for sprint in db.query(PMSSprint).filter(PMSSprint.project_id.in_(visible_project_ids)).order_by(PMSSprint.start_date.desc()).all()
    ] if visible_project_ids else []
    epics = [
        {"id": epic.id, "name": epic.name, "epic_key": epic.epic_key, "project_id": epic.project_id}
        for epic in db.query(PMSEpic).filter(PMSEpic.project_id.in_(visible_project_ids), PMSEpic.deleted_at == None).order_by(PMSEpic.name).all()
    ] if visible_project_ids else []
    assignee_ids = [row[0] for row in db.query(PMSTask.assignee_user_id).filter(PMSTask.project_id.in_(visible_project_ids), PMSTask.assignee_user_id != None).distinct().all()] if visible_project_ids else []
    users = {user.id: user for user in db.query(User).filter(User.id.in_(assignee_ids)).all()} if assignee_ids else {}
    filters_task_query = db.query(PMSTask).filter(PMSTask.project_id.in_(visible_project_ids), PMSTask.deleted_at == None) if visible_project_ids else None
    return {
        "tasks": _task_list_payloads(db, tasks),
        "dependencies": dependency_payloads,
        "warnings": _task_dependency_warnings(db, task_ids),
        "filters": {
            "projects": projects,
            "sprints": sprints,
            "epics": epics,
            "assignees": [{"id": user_id, "name": _user_display_name(users.get(user_id))} for user_id in assignee_ids if users.get(user_id)],
            "statuses": [row[0] for row in filters_task_query.with_entities(PMSTask.status).filter(PMSTask.status != None).distinct().order_by(PMSTask.status).all()] if filters_task_query is not None else [],
        },
    }


@router.patch("/tasks/bulk", response_model=TaskBulkUpdateResponse)
def bulk_update_tasks(
    bulk_in: TaskBulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk update common planning fields across selected tasks."""
    tasks = db.query(PMSTask).filter(
        PMSTask.id.in_(bulk_in.task_ids),
        PMSTask.deleted_at == None,
    ).all()
    if len(tasks) != len(set(bulk_in.task_ids)):
        raise HTTPException(status_code=404, detail="One or more tasks were not found")

    update_data = bulk_in.dict(exclude={"task_ids"}, exclude_unset=True)
    by_project: dict[int, list[PMSTask]] = {}
    for task in tasks:
        by_project.setdefault(task.project_id, []).append(task)
    for project_id, project_tasks in by_project.items():
        get_project_for_action(db, project_id, current_user, "manage_tasks")
        _sync_task_planning_links(db, project_id, update_data)
        if update_data.get("sprint_id"):
            sprint = db.query(PMSSprint).filter(PMSSprint.id == update_data["sprint_id"], PMSSprint.project_id == project_id).first()
            if not sprint:
                raise HTTPException(status_code=400, detail="Sprint does not belong to selected project")
            if sprint.status == "Active":
                sprint.scope_change_count = (sprint.scope_change_count or 0) + len(project_tasks)
        for task in project_tasks:
            for field, value in update_data.items():
                setattr(task, field, value)
            _record_activity(db, project_id, current_user, "bulk_updated", "task", task.id, f"Bulk updated {task.task_key}", task_id=task.id, metadata=update_data)
            db.add(task)

    db.commit()
    for task in tasks:
        db.refresh(task)
    return {"updated_count": len(tasks), "tasks": tasks}


@router.get("/tasks/{task_id}", response_model=PMSTaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific task."""
    task, _project = get_task_project_for_action(db, task_id, current_user, "browse")
    _attach_subtask_counts(db, task)
    return task


@router.patch("/tasks/{task_id}/schedule")
def update_task_schedule(
    task_id: int,
    schedule_in: TaskScheduleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update task start/end dates from the Gantt view."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    old_values = {"start_date": _json_ready(task.start_date), "due_date": _json_ready(task.due_date)}
    if schedule_in.start_date is not None:
        task.start_date = schedule_in.start_date
    if schedule_in.due_date is not None:
        task.due_date = schedule_in.due_date
    if task.start_date and task.due_date and task.due_date < task.start_date:
        raise HTTPException(status_code=400, detail="Due date cannot be before start date")
    db.add(task)
    _record_activity(
        db,
        project.id,
        current_user,
        "schedule.changed",
        "task",
        task.id,
        f"Rescheduled {task.task_key}",
        task_id=task.id,
        metadata={
            "old_values": old_values,
            "new_values": {"start_date": _json_ready(task.start_date), "due_date": _json_ready(task.due_date)},
        },
    )
    db.commit()
    db.refresh(task)
    _attach_subtask_counts(db, task)
    return {"task": task, "warnings": _task_dependency_warnings(db, [task.id])}


@router.post("/tasks/{task_id}/dependencies", response_model=PMSTaskDependencyResponse, status_code=status.HTTP_201_CREATED)
def add_task_dependency(
    task_id: int,
    dependency_in: PMSTaskDependencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark another task as a blocker/dependency for this task."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    blocker = db.query(PMSTask).filter(
        PMSTask.id == dependency_in.depends_on_task_id,
        PMSTask.project_id == project.id,
        PMSTask.deleted_at == None,
    ).first()
    if not blocker:
        raise HTTPException(status_code=404, detail="Dependency task not found in this project")
    if blocker.id == task.id:
        raise HTTPException(status_code=400, detail="A task cannot depend on itself")
    dependency_in.dependency_type = _normalize_dependency_type(dependency_in.dependency_type)
    if _would_create_dependency_cycle(db, blocker.id, task.id):
        raise HTTPException(status_code=400, detail="Dependency would create a circular relationship")
    existing = db.query(PMSTaskDependency).filter(
        PMSTaskDependency.task_id == task.id,
        PMSTaskDependency.depends_on_task_id == blocker.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Dependency already exists")
    dependency = PMSTaskDependency(task_id=task.id, **dependency_in.dict())
    blocker.is_blocking = True
    _record_activity(
        db,
        project.id,
        current_user,
        "dependency.added",
        "task_dependency",
        task.id,
        f"{blocker.task_key} now blocks {task.task_key}",
        task_id=task.id,
        metadata={"depends_on_task_id": blocker.id},
    )
    db.add(blocker)
    db.add(dependency)
    db.commit()
    db.refresh(dependency)
    return dependency


@router.get("/tasks/{task_id}/dependencies", response_model=list[PMSTaskDependencyDetail])
def list_task_dependencies(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List blockers and dependent work for a task."""
    task, _project = get_task_project_for_action(db, task_id, current_user, "browse")
    dependencies = db.query(PMSTaskDependency).filter(
        or_(PMSTaskDependency.task_id == task.id, PMSTaskDependency.depends_on_task_id == task.id)
    ).all()
    task_ids = {dep.task_id for dep in dependencies} | {dep.depends_on_task_id for dep in dependencies}
    related = {item.id: item for item in db.query(PMSTask).filter(PMSTask.id.in_(task_ids)).all()} if task_ids else {}
    return [_dependency_detail_payload(dep, related) for dep in dependencies]


@router.post("/task-dependencies", response_model=PMSTaskDependencyDetail, status_code=status.HTTP_201_CREATED)
def create_task_dependency(
    dependency_in: TaskDependencyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a dependency using Gantt source/target terminology."""
    source, source_project = get_task_project_for_action(db, dependency_in.source_task_id, current_user, "manage_tasks")
    target = db.query(PMSTask).filter(
        PMSTask.id == dependency_in.target_task_id,
        PMSTask.project_id == source_project.id,
        PMSTask.deleted_at == None,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target task not found in the same project")
    dependency_type = _normalize_dependency_type(dependency_in.dependency_type)
    if _would_create_dependency_cycle(db, source.id, target.id):
        raise HTTPException(status_code=400, detail="Dependency would create a circular relationship")
    existing = db.query(PMSTaskDependency).filter(
        PMSTaskDependency.task_id == target.id,
        PMSTaskDependency.depends_on_task_id == source.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Dependency already exists")
    dependency = PMSTaskDependency(
        task_id=target.id,
        depends_on_task_id=source.id,
        dependency_type=dependency_type,
        lag_days=dependency_in.lag_days,
    )
    source.is_blocking = True
    db.add(source)
    db.add(dependency)
    db.flush()
    _record_activity(
        db,
        source_project.id,
        current_user,
        "dependency.added",
        "task_dependency",
        dependency.id,
        f"{source.task_key} now blocks {target.task_key}",
        task_id=target.id,
        metadata={"source_task_id": source.id, "target_task_id": target.id, "dependency_type": dependency_type, "lag_days": dependency_in.lag_days},
    )
    db.commit()
    db.refresh(dependency)
    return _dependency_detail_payload(dependency, {source.id: source, target.id: target})


@router.delete("/task-dependencies/{dependency_id}")
def delete_task_dependency(
    dependency_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a dependency by id."""
    dependency = db.query(PMSTaskDependency).filter(PMSTaskDependency.id == dependency_id).first()
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency not found")
    target, project = get_task_project_for_action(db, dependency.task_id, current_user, "manage_tasks")
    blocker_id = dependency.depends_on_task_id
    db.delete(dependency)
    db.flush()
    still_blocks = db.query(PMSTaskDependency).filter(PMSTaskDependency.depends_on_task_id == blocker_id).count()
    if not still_blocks:
        blocker = db.query(PMSTask).filter(PMSTask.id == blocker_id).first()
        if blocker:
            blocker.is_blocking = False
            db.add(blocker)
    _record_activity(db, project.id, current_user, "dependency.removed", "task_dependency", dependency_id, f"Removed dependency link for {target.task_key}", task_id=target.id)
    db.commit()
    return {"message": "Dependency removed"}


@router.delete("/tasks/{task_id}/dependencies/{dependency_id}")
def remove_task_dependency(
    task_id: int,
    dependency_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a blocker/dependency link."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    dependency = db.query(PMSTaskDependency).filter(
        PMSTaskDependency.id == dependency_id,
        or_(PMSTaskDependency.task_id == task.id, PMSTaskDependency.depends_on_task_id == task.id),
    ).first()
    if not dependency:
        raise HTTPException(status_code=404, detail="Dependency not found")
    blocker_id = dependency.depends_on_task_id
    db.delete(dependency)
    db.flush()
    still_blocks = db.query(PMSTaskDependency).filter(PMSTaskDependency.depends_on_task_id == blocker_id).count()
    if not still_blocks:
        blocker = db.query(PMSTask).filter(PMSTask.id == blocker_id).first()
        if blocker:
            blocker.is_blocking = False
            db.add(blocker)
    _record_activity(db, project.id, current_user, "dependency.removed", "task_dependency", dependency_id, f"Removed dependency link for {task.task_key}", task_id=task.id)
    db.commit()
    return {"message": "Dependency removed"}


@router.patch("/tasks/{task_id}", response_model=PMSTaskResponse)
def update_task(
    task_id: int,
    task_in: PMSTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a task."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")

    update_data = task_in.dict(exclude_unset=True)
    old_values = {field: _json_ready(getattr(task, field)) for field in update_data}
    if update_data.get("story_points") is not None and update_data["story_points"] < 0:
        raise HTTPException(status_code=400, detail="Story points must be non-negative")
    if "parent_task_id" in update_data:
        parent = _ensure_valid_parent_task(db, project.id, task.id, update_data.get("parent_task_id"))
        if parent and parent.project_id != task.project_id:
            raise HTTPException(status_code=400, detail="Parent task must be in the same project")
    _sync_task_planning_links(db, project.id, update_data)
    if "sprint_id" in update_data and update_data["sprint_id"] != task.sprint_id and update_data["sprint_id"]:
        sprint = db.query(PMSSprint).filter(PMSSprint.id == update_data["sprint_id"], PMSSprint.project_id == project.id).first()
        if not sprint:
            raise HTTPException(status_code=400, detail="Sprint does not belong to selected project")
        if sprint.status == "Active":
            sprint.scope_change_count = (sprint.scope_change_count or 0) + 1
    for field, value in update_data.items():
        setattr(task, field, value)

    if task.sprint_id:
        sprint = db.query(PMSSprint).filter(PMSSprint.id == task.sprint_id).first()
        if sprint:
            _sync_sprint_rollups(db, sprint)
    changed_fields = []
    for field, new_value in update_data.items():
        old_value = old_values.get(field)
        normalized_new = _json_ready(new_value)
        if normalized_new == old_value:
            continue
        changed_fields.append(field)
        if field in TASK_ACTIVITY_FIELD_MAP:
            label = field.replace("_id", "").replace("_", " ")
            _record_activity(
                db,
                project.id,
                current_user,
                TASK_ACTIVITY_FIELD_MAP[field],
                "task",
                task.id,
                f"Changed {label} on {task.task_key}",
                task_id=task.id,
                metadata={"field": field, "old_value": old_value, "new_value": normalized_new},
            )
    if task.parent_task_id and "status" in changed_fields and task.status in DONE_STATUSES and old_values.get("status") not in DONE_STATUSES:
        parent = db.query(PMSTask).filter(PMSTask.id == task.parent_task_id, PMSTask.deleted_at == None).first()
        if parent:
            _record_activity(
                db,
                project.id,
                current_user,
                "subtask.completed",
                "task",
                task.id,
                f"Completed sub-task {task.task_key}",
                task_id=parent.id,
                metadata={"subtask_id": task.id, "subtask_key": task.task_key, "title": task.title},
            )
    if changed_fields:
        _record_activity(
            db,
            project.id,
            current_user,
            "task.updated",
            "task",
            task.id,
            f"Updated task {task.task_key}",
            task_id=task.id,
            metadata={"changed_fields": changed_fields, "old_values": old_values, "new_values": {field: _json_ready(update_data[field]) for field in changed_fields}},
        )
    db.add(task)
    db.commit()
    db.refresh(task)
    _attach_subtask_counts(db, task)
    event_type = "task.updated"
    if "status" in changed_fields:
        event_type = "task.status_changed"
    elif "assignee_user_id" in changed_fields:
        event_type = "task.assignee_changed"
    _broadcast_realtime(
        current_user,
        event_type,
        project_id=project.id,
        task_id=task.id,
        message=f"Updated task {task.task_key}",
        entity={"id": task.id, "taskKey": task.task_key, "title": task.title, "status": task.status},
        data={"changedFields": changed_fields, "oldValues": old_values},
    )
    return task


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft delete a task."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")

    from datetime import datetime
    task.deleted_at = datetime.utcnow()
    db.add(task)
    if task.parent_task_id:
        _record_activity(
            db,
            project.id,
            current_user,
            "subtask.deleted",
            "task",
            task.id,
            f"Deleted sub-task {task.task_key}",
            task_id=task.parent_task_id,
            metadata={"subtask_id": task.id, "subtask_key": task.task_key, "title": task.title},
        )
    db.commit()
    return {"message": "Task deleted"}


@router.post("/tasks/{task_id}/move-to-sprint", response_model=PMSTaskResponse)
def move_task_to_sprint(
    task_id: int,
    move_in: TaskSprintMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign a task to an active or future sprint."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    sprint = db.query(PMSSprint).filter(PMSSprint.id == move_in.sprint_id, PMSSprint.project_id == project.id).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    if sprint.status == "Completed" and not move_in.allow_completed:
        raise HTTPException(status_code=400, detail="Cannot move tasks to completed sprint")
    old_sprint_id = task.sprint_id
    task.sprint_id = sprint.id
    if sprint.status == "Active" and old_sprint_id != sprint.id:
        sprint.scope_change_count = (sprint.scope_change_count or 0) + 1
    if move_in.position is not None:
        task.rank = max(move_in.position, 1)
    elif task.rank is None:
        task.rank = db.query(PMSTask).filter(PMSTask.project_id == project.id, PMSTask.sprint_id == sprint.id, PMSTask.deleted_at == None).count() + 1
    db.add(task)
    db.add(sprint)
    _record_activity(
        db,
        project.id,
        current_user,
        "sprint.changed",
        "task",
        task.id,
        f"Moved {task.task_key} to {sprint.name}",
        task_id=task.id,
        sprint_id=sprint.id,
        metadata={"old_value": old_sprint_id, "new_value": sprint.id, "field": "sprint_id"},
    )
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/remove-from-sprint", response_model=PMSTaskResponse)
def remove_task_from_sprint(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a task back to the project backlog."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    old_sprint_id = task.sprint_id
    task.sprint_id = None
    task.rank = db.query(PMSTask).filter(PMSTask.project_id == project.id, PMSTask.sprint_id == None, PMSTask.deleted_at == None).count() + 1
    db.add(task)
    _record_activity(
        db,
        project.id,
        current_user,
        "sprint.changed",
        "task",
        task.id,
        f"Moved {task.task_key} to backlog",
        task_id=task.id,
        metadata={"old_value": old_sprint_id, "new_value": None, "field": "sprint_id"},
    )
    db.commit()
    db.refresh(task)
    return task


@router.post("/backlog/reorder", response_model=list[PMSTaskResponse])
def reorder_backlog(
    reorder_in: TaskReorderListRequest,
    projectId: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reorder tasks in the project backlog."""
    project = get_project_for_action(db, projectId, current_user, "manage_tasks")
    tasks = _reorder_tasks_in_scope(db, project.id, reorder_in.task_ids, None)
    _record_activity(db, project.id, current_user, "backlog.reordered", "backlog", None, "Reordered project backlog", metadata={"task_ids": reorder_in.task_ids})
    db.commit()
    return tasks


@router.post("/sprints/{sprint_id}/reorder-tasks", response_model=list[PMSTaskResponse])
def reorder_sprint_tasks(
    sprint_id: int,
    reorder_in: TaskReorderListRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reorder tasks inside one sprint."""
    sprint = db.query(PMSSprint).filter(PMSSprint.id == sprint_id).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    project = get_project_for_action(db, sprint.project_id, current_user, "manage_tasks")
    tasks = _reorder_tasks_in_scope(db, project.id, reorder_in.task_ids, sprint.id)
    _record_activity(db, project.id, current_user, "sprint.reordered", "sprint", sprint.id, f"Reordered tasks in {sprint.name}", sprint_id=sprint.id, metadata={"task_ids": reorder_in.task_ids})
    db.commit()
    return tasks


@router.get("/tasks/{task_id}/activity", response_model=list[PMSActivityResponse])
def list_task_activity(
    task_id: int,
    limit: int = Query(100),
    sortOrder: str = Query("desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List activity for one task."""
    task, _project = get_task_project_for_action(db, task_id, current_user, "browse")
    order = asc(PMSActivity.created_at) if sortOrder.lower() == "asc" else desc(PMSActivity.created_at)
    return db.query(PMSActivity).filter(PMSActivity.task_id == task.id).order_by(order, desc(PMSActivity.id)).limit(limit).all()


@router.get("/tasks/{task_id}/attachments", response_model=list[PMSFileAssetResponse])
def list_task_attachments(
    task_id: int,
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List file metadata attached to one task."""
    task, _project = get_task_project_for_action(db, task_id, current_user, "browse")
    files = db.query(PMSFileAsset).filter(
        PMSFileAsset.task_id == task.id,
        PMSFileAsset.deleted_at == None,
    ).order_by(desc(PMSFileAsset.created_at)).offset(skip).limit(limit).all()
    return _file_payloads(db, files)


@router.post("/tasks/{task_id}/attachments", response_model=PMSFileAssetResponse, status_code=status.HTTP_201_CREATED)
def upload_task_attachment(
    task_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a binary file and attach it to a task."""
    task, project = get_task_project_for_action(db, task_id, current_user, "upload")
    _validate_attachment_upload(file)
    original_name = _safe_attachment_name(file.filename)
    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    target_dir = PMS_UPLOAD_ROOT / "tasks" / str(task.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = (target_dir / stored_name).resolve()
    if not str(target_path).startswith(str(PMS_UPLOAD_ROOT)):
        raise HTTPException(status_code=400, detail="Invalid attachment path")

    size_bytes = 0
    try:
        with target_path.open("wb") as output:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > PMS_MAX_ATTACHMENT_BYTES:
                    output.close()
                    target_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="Attachment exceeds the configured size limit")
                output.write(chunk)
    finally:
        file.file.close()

    if size_bytes == 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Attachment cannot be empty")

    file_asset = PMSFileAsset(
        uploaded_by_user_id=current_user.id,
        project_id=project.id,
        task_id=task.id,
        file_name=stored_name,
        original_name=original_name,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        storage_path=str(target_path),
        visibility="Internal",
    )
    db.add(file_asset)
    db.flush()
    _record_activity(
        db,
        project.id,
        current_user,
        "attachment.added",
        "file",
        file_asset.id,
        f"Attached {file_asset.original_name}",
        task_id=task.id,
        metadata={"file_id": file_asset.id, "file_name": file_asset.original_name, "size_bytes": size_bytes},
    )
    db.commit()
    db.refresh(file_asset)
    _broadcast_realtime(
        current_user,
        "task.attachment_added",
        project_id=project.id,
        task_id=task.id,
        message=f"Attached {file_asset.original_name}",
        entity={"id": file_asset.id, "taskId": task.id, "fileName": file_asset.original_name},
        data={"sizeBytes": size_bytes},
    )
    return _file_payload(file_asset, current_user)


@router.get("/tasks/{task_id}/time-logs", response_model=list[PMSTimeLogResponse])
def list_task_time_logs(
    task_id: int,
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List time logs for one task."""
    task, _project = get_task_project_for_action(db, task_id, current_user, "browse")
    return db.query(PMSTimeLog).filter(PMSTimeLog.task_id == task.id).order_by(desc(PMSTimeLog.log_date), desc(PMSTimeLog.id)).offset(skip).limit(limit).all()


@router.post("/tasks/{task_id}/time-logs", response_model=PMSTimeLogResponse, status_code=status.HTTP_201_CREATED)
def create_task_time_log(
    task_id: int,
    timelog_in: PMSTimeLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a time log entry for one task."""
    task, project = get_task_project_for_action(db, task_id, current_user, "log_time")
    if timelog_in.project_id != project.id:
        raise HTTPException(status_code=400, detail="Task does not belong to selected project")
    data = timelog_in.dict()
    data["task_id"] = task.id
    db_timelog = PMSTimeLog(user_id=current_user.id, **data)
    db.add(db_timelog)
    db.flush()
    _record_activity(
        db,
        project.id,
        current_user,
        "time.logged",
        "time_log",
        db_timelog.id,
        f"Logged {db_timelog.duration_minutes} minutes on {task.task_key}",
        task_id=task.id,
        metadata={"duration_minutes": db_timelog.duration_minutes, "is_billable": db_timelog.is_billable},
    )
    db.commit()
    db.refresh(db_timelog)
    return db_timelog


@router.get("/tasks/{task_id}/checklists", response_model=list[PMSChecklistItemResponse])
def list_task_checklists(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List checklist items for one task."""
    task, _project = get_task_project_for_action(db, task_id, current_user, "browse")
    return db.query(PMSChecklistItem).filter(PMSChecklistItem.task_id == task.id).order_by(PMSChecklistItem.position, PMSChecklistItem.id).all()


@router.post("/tasks/{task_id}/checklists", response_model=PMSChecklistItemResponse, status_code=status.HTTP_201_CREATED)
def create_task_checklist_item(
    task_id: int,
    item_in: PMSChecklistItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a checklist item for one task."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    data = item_in.dict()
    fields_set = getattr(item_in, "model_fields_set", getattr(item_in, "__fields_set__", set()))
    if "position" not in fields_set:
        data["position"] = db.query(PMSChecklistItem).filter(PMSChecklistItem.task_id == task.id).count()
    item = PMSChecklistItem(task_id=task.id, **data)
    db.add(item)
    _record_activity(db, project.id, current_user, "checklist.item_added", "checklist_item", None, f"Added checklist item to {task.task_key}", task_id=task.id)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/tasks/{task_id}/checklists/{item_id}", response_model=PMSChecklistItemResponse)
def update_task_checklist_item(
    task_id: int,
    item_id: int,
    item_in: PMSChecklistItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a checklist item for one task."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    item = db.query(PMSChecklistItem).filter(PMSChecklistItem.id == item_id, PMSChecklistItem.task_id == task.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    update_data = item_in.dict(exclude_unset=True)
    was_completed = bool(item.is_completed)
    for field, value in update_data.items():
        setattr(item, field, value)
    action = "checklist.item_updated"
    summary = f"Updated checklist item on {task.task_key}"
    if "is_completed" in update_data and update_data["is_completed"] != was_completed:
        action = "checklist.item_completed" if update_data["is_completed"] else "checklist.item_reopened"
        summary = f"{'Completed' if update_data['is_completed'] else 'Reopened'} checklist item on {task.task_key}"
    _record_activity(db, project.id, current_user, action, "checklist_item", item.id, summary, task_id=task.id, metadata=update_data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/tasks/{task_id}/checklist", response_model=list[PMSChecklistItemResponse])
def list_task_checklist(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Singular checklist alias for task detail consumers."""
    return list_task_checklists(task_id=task_id, db=db, current_user=current_user)


@router.post("/tasks/{task_id}/checklist", response_model=PMSChecklistItemResponse, status_code=status.HTTP_201_CREATED)
def create_task_checklist_entry(
    task_id: int,
    item_in: PMSChecklistItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Singular checklist alias for creating task checklist items."""
    return create_task_checklist_item(task_id=task_id, item_in=item_in, db=db, current_user=current_user)


@router.patch("/checklist/{item_id}", response_model=PMSChecklistItemResponse)
def update_checklist_entry(
    item_id: int,
    item_in: PMSChecklistItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a checklist item by id."""
    item = db.query(PMSChecklistItem).filter(PMSChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    return update_task_checklist_item(task_id=item.task_id, item_id=item.id, item_in=item_in, db=db, current_user=current_user)


@router.delete("/checklist/{item_id}")
def delete_checklist_entry(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a checklist item by id."""
    item = db.query(PMSChecklistItem).filter(PMSChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    task, project = get_task_project_for_action(db, item.task_id, current_user, "manage_tasks")
    db.delete(item)
    _record_activity(db, project.id, current_user, "checklist.item_deleted", "checklist_item", item_id, f"Deleted checklist item from {task.task_key}", task_id=task.id)
    db.commit()
    return {"message": "Checklist item deleted"}


@router.post("/tasks/{task_id}/checklist/reorder", response_model=list[PMSChecklistItemResponse])
def reorder_task_checklist(
    task_id: int,
    reorder_in: ChecklistReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reorder checklist items for one task."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    existing = db.query(PMSChecklistItem).filter(PMSChecklistItem.task_id == task.id).all()
    existing_by_id = {item.id: item for item in existing}
    requested_ids = list(dict.fromkeys(reorder_in.item_ids))
    if set(requested_ids) != set(existing_by_id):
        raise HTTPException(status_code=400, detail="Checklist reorder must include every item exactly once")
    for index, item_id in enumerate(requested_ids):
        existing_by_id[item_id].position = index
        db.add(existing_by_id[item_id])
    _record_activity(db, project.id, current_user, "checklist.reordered", "checklist_item", None, f"Reordered checklist on {task.task_key}", task_id=task.id)
    db.commit()
    return db.query(PMSChecklistItem).filter(PMSChecklistItem.task_id == task.id).order_by(PMSChecklistItem.position, PMSChecklistItem.id).all()


@router.get("/tasks/{task_id}/subtasks", response_model=list[PMSTaskResponse])
def list_task_subtasks(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List direct sub-tasks for one task."""
    task, _project = get_task_project_for_action(db, task_id, current_user, "browse")
    subtasks = db.query(PMSTask).filter(
        PMSTask.parent_task_id == task.id,
        PMSTask.deleted_at == None,
    ).order_by(PMSTask.position, PMSTask.id).all()
    _attach_subtask_counts(db, subtasks)
    return subtasks


@router.post("/tasks/{task_id}/subtasks", response_model=PMSTaskResponse, status_code=status.HTTP_201_CREATED)
def create_task_subtask(
    task_id: int,
    subtask_in: SubtaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a child sub-task under an existing task."""
    parent, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    if subtask_in.story_points is not None and subtask_in.story_points < 0:
        raise HTTPException(status_code=400, detail="Story points must be non-negative")
    task_key = (subtask_in.task_key or _next_subtask_key(db, parent)).upper()
    existing = db.query(PMSTask).filter(PMSTask.project_id == project.id, PMSTask.task_key == task_key).first()
    if existing:
        raise HTTPException(status_code=400, detail="Task key already exists in this project")
    position = db.query(PMSTask).filter(PMSTask.parent_task_id == parent.id, PMSTask.deleted_at == None).count()
    subtask = PMSTask(
        project_id=project.id,
        board_id=parent.board_id,
        column_id=parent.column_id,
        milestone_id=parent.milestone_id,
        sprint_id=parent.sprint_id,
        epic_id=parent.epic_id,
        component_id=parent.component_id,
        release_id=parent.release_id,
        parent_task_id=parent.id,
        assignee_user_id=subtask_in.assignee_user_id,
        reporter_user_id=getattr(current_user, "id", None) or parent.reporter_user_id,
        title=subtask_in.title,
        description=subtask_in.description,
        task_key=task_key,
        work_type="Sub-task",
        status=subtask_in.status,
        priority=subtask_in.priority,
        due_date=subtask_in.due_date,
        story_points=subtask_in.story_points,
        position=position,
        rank=position + 1,
        security_level=parent.security_level,
        is_client_visible=parent.is_client_visible,
    )
    db.add(subtask)
    db.flush()
    _record_activity(db, project.id, current_user, "task.created", "task", subtask.id, f"Created task {subtask.task_key}", task_id=subtask.id)
    _record_activity(
        db,
        project.id,
        current_user,
        "subtask.created",
        "task",
        subtask.id,
        f"Created sub-task {subtask.task_key}",
        task_id=parent.id,
        metadata={"subtask_id": subtask.id, "subtask_key": subtask.task_key, "title": subtask.title},
    )
    db.commit()
    db.refresh(subtask)
    _attach_subtask_counts(db, subtask)
    return subtask


@router.get("/tasks/{task_id}/links", response_model=list[PMSTaskDependencyDetail])
def list_task_links(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Alias dependency links for task detail tabs."""
    return list_task_dependencies(task_id=task_id, db=db, current_user=current_user)


@router.get("/tasks/{task_id}/tags", response_model=list[PMSTagResponse])
def list_task_tags(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tags attached to one task."""
    task, _project = get_task_project_for_action(db, task_id, current_user, "browse")
    return db.query(PMSTag).join(PMSTaskTag, PMSTaskTag.tag_id == PMSTag.id).filter(PMSTaskTag.task_id == task.id).order_by(PMSTag.name).all()


@router.get("/tags", response_model=list[PMSTagResponse])
def list_tags(
    q: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List organization-scoped task tags."""
    user_org_id = organization_id_for(current_user)
    query = db.query(PMSTag)
    if not current_user.is_superuser:
        query = query.filter(PMSTag.organization_id == user_org_id)
    if q:
        query = query.filter(PMSTag.name.ilike(f"%{q.strip()}%"))
    return query.order_by(PMSTag.name).all()


@router.post("/tags", response_model=PMSTagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(
    tag_in: PMSTagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an organization-scoped task tag."""
    if not has_any_permission(current_user, PMS_GLOBAL_MANAGE_TASKS):
        raise HTTPException(status_code=403, detail="Tag creation denied")
    user_org_id = organization_id_for(current_user)
    normalized = tag_in.name.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Tag name is required")
    existing = db.query(PMSTag).filter(
        PMSTag.organization_id == user_org_id,
        func.lower(PMSTag.name) == normalized.lower(),
    ).first()
    if existing:
        return existing
    tag = PMSTag(organization_id=user_org_id, name=normalized, color=tag_in.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.post("/tasks/{task_id}/tags", response_model=PMSTagResponse, status_code=status.HTTP_201_CREATED)
def add_task_tag(
    task_id: int,
    tag_in: TaskTagAttachRequest | None = None,
    name: str = Query(None, min_length=1, max_length=100),
    tag_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach an organization-scoped tag to one task."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    requested_tag_id = tag_id or (tag_in.tag_id if tag_in else None)
    requested_name = name or (tag_in.name if tag_in else None)
    if requested_tag_id:
        tag = db.query(PMSTag).filter(
            PMSTag.id == requested_tag_id,
            PMSTag.organization_id == project.organization_id,
        ).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
    else:
        normalized = (requested_name or "").strip()
        if not normalized:
            raise HTTPException(status_code=400, detail="Tag name or tag id is required")
        tag = db.query(PMSTag).filter(
            PMSTag.organization_id == project.organization_id,
            func.lower(PMSTag.name) == normalized.lower(),
        ).first()
        if not tag:
            tag = PMSTag(organization_id=project.organization_id, name=normalized)
            db.add(tag)
            db.flush()
    existing = db.query(PMSTaskTag).filter(PMSTaskTag.task_id == task.id, PMSTaskTag.tag_id == tag.id).first()
    if not existing:
        db.add(PMSTaskTag(task_id=task.id, tag_id=tag.id))
        _record_activity(db, project.id, current_user, "tag.added", "task", task.id, f"Tagged {task.task_key} with {tag.name}", task_id=task.id, metadata={"tag_id": tag.id, "tag_name": tag.name})
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/tasks/{task_id}/tags/{tag_id}")
def remove_task_tag(
    task_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a tag from one task without deleting the organization tag."""
    task, project = get_task_project_for_action(db, task_id, current_user, "manage_tasks")
    tag = db.query(PMSTag).filter(PMSTag.id == tag_id, PMSTag.organization_id == project.organization_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    link = db.query(PMSTaskTag).filter(PMSTaskTag.task_id == task.id, PMSTaskTag.tag_id == tag.id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Task tag not found")
    db.delete(link)
    _record_activity(db, project.id, current_user, "tag.removed", "task", task.id, f"Removed {tag.name} from {task.task_key}", task_id=task.id, metadata={"tag_id": tag.id, "tag_name": tag.name})
    db.commit()
    return {"message": "Tag removed"}


# ============= KANBAN BOARD =============
@router.get("/projects/{project_id}/board", response_model=KanbanBoard)
def get_kanban_board(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get Kanban board with columns and tasks."""
    get_project_for_action(db, project_id, current_user, "browse")

    # Get or create default board
    board = db.query(PMSBoard).filter(
        PMSBoard.project_id == project_id
    ).first()

    if not board:
        # Create default board with standard columns
        board = PMSBoard(
            project_id=project_id,
            name="Default Board",
            board_type="Kanban"
        )
        db.add(board)
        db.commit()
        db.refresh(board)

        # Create default columns
        default_columns = [
            ("Backlog", "BACKLOG", 0),
            ("To Do", "TODO", 1),
            ("In Progress", "IN_PROGRESS", 2),
            ("In Review", "IN_REVIEW", 3),
            ("Done", "DONE", 4),
        ]

        for name, status_key, position in default_columns:
            col = PMSBoardColumn(
                board_id=board.id,
                name=name,
                status_key=status_key,
                position=position
            )
            db.add(col)
        db.commit()

    # Get columns with tasks
    columns = db.query(PMSBoardColumn).filter(
        PMSBoardColumn.board_id == board.id
    ).order_by(PMSBoardColumn.position).all()

    columns_data = []
    for col in columns:
        tasks = db.query(PMSTask).filter(
            PMSTask.project_id == project_id,
            PMSTask.column_id == col.id,
            PMSTask.deleted_at == None
        ).order_by(PMSTask.position).all()
        tags_by_task_id = _load_task_tags(db, [task.id for task in tasks])
        _attach_subtask_counts(db, tasks)
        for task in tasks:
            task.tags = tags_by_task_id.get(task.id, [])

        columns_data.append({
            "id": col.id,
            "board_id": col.board_id,
            "name": col.name,
            "status_key": col.status_key,
            "position": col.position,
            "wip_limit": col.wip_limit,
            "is_collapsed": col.is_collapsed,
            "color": col.color,
            "tasks": tasks,
            "task_count": len(tasks)
        })
    
    return {
        "id": board.id,
        "project_id": board.project_id,
        "name": board.name,
        "board_type": board.board_type,
        "created_at": board.created_at,
        "columns": columns_data
    }


@router.post("/projects/{project_id}/board/reorder")
def reorder_task(
    project_id: int,
    reorder_req: TaskReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reorder task within or between columns (Drag & Drop)."""
    get_project_for_action(db, project_id, current_user, "manage_tasks")
    
    task = db.query(PMSTask).filter(
        PMSTask.id == reorder_req.task_id,
        PMSTask.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update task's column and position
    task.column_id = reorder_req.column_id
    task.position = reorder_req.position
    column = db.query(PMSBoardColumn).filter(PMSBoardColumn.id == reorder_req.column_id).first()
    if column:
        status_map = {
            "BACKLOG": "Backlog",
            "TODO": "To Do",
            "IN_PROGRESS": "In Progress",
            "IN_REVIEW": "In Review",
            "DONE": "Done",
        }
        task.status = status_map.get(column.status_key, task.status)
    
    db.add(task)
    db.commit()
    db.refresh(task)
    _broadcast_realtime(
        current_user,
        "task.status_changed",
        project_id=project_id,
        task_id=task.id,
        message=f"Moved task {task.task_key}",
        entity={"id": task.id, "taskKey": task.task_key, "title": task.title, "status": task.status},
        data={"columnId": task.column_id, "position": task.position},
    )
    
    return {"message": "Task reordered", "task": task}


# ============= COMMENTS (COLLABORATION) =============
@router.post("/tasks/{task_id}/comments", response_model=PMSCommentResponse)
def add_comment_to_task(
    task_id: int,
    comment_in: PMSCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a comment to a task (Collaboration)."""
    task, project = get_task_project_for_action(db, task_id, current_user, "comment")
    
    comment_data = comment_in.dict(exclude={"mentioned_user_ids"})
    if comment_data.get("body_format") not in {"markdown", "plain"}:
        raise HTTPException(status_code=400, detail="Unsupported comment body format")
    comment_data['author_user_id'] = current_user.id
    comment_data['task_id'] = task_id
    comment_data['project_id'] = project.id
    
    db_comment = PMSComment(**comment_data)
    db.add(db_comment)
    db.flush()
    mention_user_ids = _extract_mention_user_ids(db_comment.body, comment_in.mentioned_user_ids)
    _replace_comment_mentions(db, project, task, db_comment, current_user, mention_user_ids)
    _record_activity(
        db,
        project.id,
        current_user,
        "comment.added",
        "comment",
        db_comment.id,
        f"Added comment on {task.task_key}",
        task_id=task.id,
        metadata={"comment_id": db_comment.id, "body_preview": (db_comment.body or "")[:160]},
    )
    db.commit()
    db.refresh(db_comment)
    _broadcast_realtime(
        current_user,
        "task.comment_added",
        project_id=project.id,
        task_id=task.id,
        message=f"Added comment on {task.task_key}",
        entity={"id": db_comment.id, "taskId": task.id},
        data={"bodyPreview": (db_comment.body or "")[:160]},
    )
    return _comment_payload(db_comment, _comment_mentions(db, [db_comment.id]))


@router.get("/tasks/{task_id}/comments", response_model=list[PMSCommentResponse])
def list_task_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all comments on a task."""
    task, project = get_task_project_for_action(db, task_id, current_user, "browse")
    
    query = db.query(PMSComment).filter(
        PMSComment.task_id == task_id,
        PMSComment.deleted_at == None
    )
    if not can_access_project(db, project, current_user, "manage_tasks"):
        query = query.filter(PMSComment.is_internal == False)
    comments = query.order_by(desc(PMSComment.created_at)).all()
    mentions = _comment_mentions(db, [comment.id for comment in comments])
    return [_comment_payload(comment, mentions) for comment in comments]


@router.patch("/comments/{comment_id}", response_model=PMSCommentResponse)
def update_comment(
    comment_id: int,
    comment_in: PMSCommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a comment."""
    comment = db.query(PMSComment).filter(PMSComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    if comment.author_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Can only edit your own comments")
    task = None
    project = None
    if comment.task_id:
        task, project = get_task_project_for_action(db, comment.task_id, current_user, "comment")
    
    update_data = comment_in.dict(exclude_unset=True)
    if update_data.get("body_format") and update_data["body_format"] not in {"markdown", "plain"}:
        raise HTTPException(status_code=400, detail="Unsupported comment body format")
    update_data['is_edited'] = True
    for field, value in update_data.items():
        setattr(comment, field, value)
    db.add(comment)
    if task and project and "body" in update_data:
        _replace_comment_mentions(db, project, task, comment, current_user, _extract_mention_user_ids(comment.body))
        _record_activity(
            db,
            project.id,
            current_user,
            "comment.updated",
            "comment",
            comment.id,
            f"Updated comment on {task.task_key}",
            task_id=task.id,
            metadata={"comment_id": comment.id},
        )
    db.commit()
    db.refresh(comment)
    return _comment_payload(comment, _comment_mentions(db, [comment.id]))


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a comment."""
    comment = db.query(PMSComment).filter(PMSComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.author_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Can only delete your own comments")
    task = None
    if comment.task_id:
        task, _project = get_task_project_for_action(db, comment.task_id, current_user, "comment")

    from datetime import datetime
    comment.deleted_at = datetime.utcnow()
    db.add(comment)
    if task:
        _record_activity(db, task.project_id, current_user, "comment.deleted", "comment", comment.id, f"Deleted comment on {task.task_key}", task_id=task.id, metadata={"comment_id": comment.id})
    db.commit()
    return {"message": "Comment deleted"}


@router.get("/users/search")
def search_pms_users(
    q: str = Query("", max_length=120),
    projectId: int = Query(None),
    taskId: int = Query(None),
    limit: int = Query(10, ge=1, le=25),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search mentionable users scoped to a PMS project/task."""
    if taskId:
        task, project = get_task_project_for_action(db, taskId, current_user, "browse")
    elif projectId:
        project = get_project_for_action(db, projectId, current_user, "browse")
    else:
        accessible_project_ids = accessible_project_query(db, current_user).with_entities(PMSProject.id)
        member_ids = db.query(PMSProjectMember.user_id).filter(PMSProjectMember.project_id.in_(accessible_project_ids))
        query = db.query(User).filter(User.is_active == True, User.id.in_(member_ids))
        term = f"%{q.strip()}%"
        if q.strip():
            query = query.filter(User.email.ilike(term))
        return [_pms_user_payload(user) for user in query.order_by(User.email).limit(limit).all()]
    query = _project_user_query(db, project)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(User.email.ilike(term))
    return [_pms_user_payload(user) for user in query.order_by(User.email).limit(limit).all()]


@router.get("/notifications")
def list_pms_notifications(
    unreadOnly: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List current user's PMS notifications."""
    query = db.query(Notification).filter(Notification.user_id == current_user.id, Notification.module == "pms")
    if unreadOnly:
        query = query.filter(Notification.is_read == False)
    return [
        {
            "id": item.id,
            "title": item.title,
            "message": item.message,
            "event_type": item.event_type,
            "related_entity_type": item.related_entity_type,
            "related_entity_id": item.related_entity_id,
            "action_url": item.action_url,
            "is_read": item.is_read,
            "read_at": item.read_at,
            "created_at": item.created_at,
        }
        for item in query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(100).all()
    ]


@router.patch("/notifications/{notification_id}/read")
def mark_pms_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a PMS notification and linked mention as read."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
        Notification.module == "pms",
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    from datetime import timezone
    now = datetime.now(timezone.utc)
    notification.is_read = True
    notification.read_at = now
    mention = db.query(PMSMention).filter(PMSMention.notification_id == notification.id).first()
    if mention and not mention.read_at:
        mention.read_at = now
        db.add(mention)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return {"id": notification.id, "is_read": notification.is_read, "read_at": notification.read_at}


# ============= MILESTONES =============
@router.post("/projects/{project_id}/milestones", response_model=PMSMilestoneResponse)
def create_milestone(
    project_id: int,
    milestone_in: PMSMilestoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a milestone for a project."""
    get_project_for_action(db, project_id, current_user, "manage_tasks")
    
    db_milestone = PMSMilestone(
        project_id=project_id,
        **milestone_in.dict()
    )
    db.add(db_milestone)
    db.commit()
    db.refresh(db_milestone)
    return db_milestone


@router.get("/projects/{project_id}/milestones", response_model=list[PMSMilestoneResponse])
def list_milestones(
    project_id: int,
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all milestones for a project."""
    get_project_for_action(db, project_id, current_user, "browse")
    
    milestones = db.query(PMSMilestone).filter(
        PMSMilestone.project_id == project_id
    ).offset(skip).limit(limit).all()
    return milestones


@router.post("/milestones/{milestone_id}/submit-approval", response_model=PMSClientApprovalResponse)
def submit_milestone_approval(
    milestone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a milestone for client approval."""
    milestone = db.query(PMSMilestone).filter(PMSMilestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    project = get_project_for_action(db, milestone.project_id, current_user, "manage_tasks")

    milestone.client_approval_status = "Pending"
    approval = PMSClientApproval(
        project_id=project.id,
        milestone_id=milestone.id,
        requested_by_user_id=current_user.id,
        status="Pending",
    )
    db.add(milestone)
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


@router.post("/milestones/{milestone_id}/approve", response_model=PMSMilestoneResponse)
def approve_milestone(
    milestone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a milestone from the client portal."""
    from datetime import datetime

    milestone = db.query(PMSMilestone).filter(PMSMilestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    get_project_for_action(db, milestone.project_id, current_user, "approve")
    milestone.client_approval_status = "Approved"
    milestone.client_approved_at = datetime.utcnow()
    db.query(PMSClientApproval).filter(
        PMSClientApproval.milestone_id == milestone_id,
        PMSClientApproval.status == "Pending",
    ).update({"status": "Approved", "decided_at": datetime.utcnow()})
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.post("/milestones/{milestone_id}/reject", response_model=PMSMilestoneResponse)
def reject_milestone(
    milestone_id: int,
    approval_in: PMSClientApprovalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reject a milestone with a reason."""
    from datetime import datetime

    milestone = db.query(PMSMilestone).filter(PMSMilestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    get_project_for_action(db, milestone.project_id, current_user, "approve")
    if not approval_in.remarks:
        raise HTTPException(status_code=400, detail="Rejection reason is required")
    milestone.client_approval_status = "Rejected"
    milestone.client_rejected_reason = approval_in.remarks
    db.query(PMSClientApproval).filter(
        PMSClientApproval.milestone_id == milestone_id,
        PMSClientApproval.status == "Pending",
    ).update({"status": "Rejected", "remarks": approval_in.remarks, "decided_at": datetime.utcnow()})
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


# ============= SPRINTS =============
@router.post("/projects/{project_id}/sprints", response_model=PMSSprintResponse)
def create_sprint(
    project_id: int,
    sprint_in: PMSSprintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a sprint for a project."""
    get_project_for_action(db, project_id, current_user, "manage_tasks")
    sprint = PMSSprint(project_id=project_id, **sprint_in.dict())
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    _broadcast_realtime(
        current_user,
        "sprint.updated",
        project_id=project_id,
        sprint_id=sprint.id,
        message=f"Sprint {sprint.name} was created",
        entity={"id": sprint.id, "name": sprint.name, "status": sprint.status},
    )
    return sprint


@router.get("/projects/{project_id}/sprints", response_model=list[PMSSprintResponse])
def list_sprints(
    project_id: int,
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List project sprints."""
    get_project_for_action(db, project_id, current_user, "browse")
    return db.query(PMSSprint).filter(PMSSprint.project_id == project_id).offset(skip).limit(limit).all()


@router.get("/sprints/{sprint_id}/review", response_model=PMSSprintReviewResponse)
def get_sprint_review(
    sprint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return sprint review notes, retro action items, and completion task split."""
    sprint = db.query(PMSSprint).filter(PMSSprint.id == sprint_id).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    get_project_for_action(db, sprint.project_id, current_user, "browse")
    tasks = db.query(PMSTask).filter(PMSTask.sprint_id == sprint.id, PMSTask.deleted_at == None).all()
    action_items = db.query(PMSSprintRetroActionItem).filter(PMSSprintRetroActionItem.sprint_id == sprint.id).order_by(PMSSprintRetroActionItem.created_at.asc()).all()
    return {
        "sprint": sprint,
        "action_items": action_items,
        "completed_tasks": [_sprint_task_summary(task) for task in tasks if task.status in DONE_STATUSES],
        "incomplete_tasks": [_sprint_task_summary(task) for task in tasks if task.status not in DONE_STATUSES],
    }


@router.patch("/sprints/{sprint_id}/review", response_model=PMSSprintReviewResponse)
def update_sprint_review(
    sprint_id: int,
    review_in: SprintCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update sprint review and retrospective notes without changing sprint status."""
    sprint = db.query(PMSSprint).filter(PMSSprint.id == sprint_id).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    project = get_project_for_action(db, sprint.project_id, current_user, "manage_tasks")
    sprint.review_notes = review_in.review_notes
    sprint.retrospective_notes = review_in.retrospective_notes
    sprint.what_went_well = review_in.what_went_well
    sprint.what_did_not_go_well = review_in.what_did_not_go_well
    sprint.outcome = review_in.outcome
    _upsert_sprint_action_items(db, sprint, project, current_user, review_in.action_items, review_in.create_action_item_tasks)
    _record_activity(db, sprint.project_id, current_user, "sprint.review_updated", "sprint", sprint.id, f"Updated review notes for {sprint.name}", sprint_id=sprint.id)
    db.add(sprint)
    db.commit()
    return get_sprint_review(sprint_id, db, current_user)


@router.post("/sprints/{sprint_id}/start", response_model=PMSSprintResponse)
def start_sprint(
    sprint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a sprint and capture the committed scope snapshot."""
    sprint = db.query(PMSSprint).filter(PMSSprint.id == sprint_id).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    get_project_for_action(db, sprint.project_id, current_user, "manage_tasks")
    if sprint.status == "Completed":
        raise HTTPException(status_code=400, detail="Completed sprints cannot be restarted")
    tasks = db.query(PMSTask).filter(PMSTask.sprint_id == sprint.id, PMSTask.deleted_at == None).all()
    committed_points = sum(_task_points(task) for task in tasks)
    sprint.status = "Active"
    sprint.started_at = datetime.utcnow()
    sprint.committed_task_count = len(tasks)
    sprint.committed_story_points = committed_points
    sprint.completed_story_points = sum(_task_points(task) for task in tasks if task.status in DONE_STATUSES)
    sprint.commitment_snapshot = json.dumps([
        {"id": task.id, "task_key": task.task_key, "title": task.title, "story_points": _task_points(task), "status": task.status}
        for task in tasks
    ], default=str)
    _record_activity(db, sprint.project_id, current_user, "started", "sprint", sprint.id, f"Started sprint {sprint.name}", sprint_id=sprint.id)
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    _broadcast_realtime(
        current_user,
        "sprint.updated",
        project_id=sprint.project_id,
        sprint_id=sprint.id,
        message=f"Started sprint {sprint.name}",
        entity={"id": sprint.id, "name": sprint.name, "status": sprint.status},
    )
    return sprint


@router.post("/sprints/{sprint_id}/complete", response_model=PMSSprintResponse)
def complete_sprint(
    sprint_id: int,
    complete_in: SprintCompleteRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete a sprint and optionally carry unfinished work forward."""
    sprint = db.query(PMSSprint).filter(PMSSprint.id == sprint_id).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    project = get_project_for_action(db, sprint.project_id, current_user, "manage_tasks")
    complete_in = complete_in or SprintCompleteRequest()
    carry_forward_sprint = None
    if complete_in.carry_forward_sprint_id:
        carry_forward_sprint = db.query(PMSSprint).filter(
            PMSSprint.id == complete_in.carry_forward_sprint_id,
            PMSSprint.project_id == sprint.project_id,
        ).first()
        if not carry_forward_sprint:
            raise HTTPException(status_code=400, detail="Carry-forward sprint does not belong to this project")
        if carry_forward_sprint.status == "Completed":
            raise HTTPException(status_code=400, detail="Cannot carry unfinished tasks into a completed sprint")
    tasks = db.query(PMSTask).filter(PMSTask.sprint_id == sprint.id, PMSTask.deleted_at == None).all()
    completed = [task for task in tasks if task.status in DONE_STATUSES]
    unfinished = [task for task in tasks if task.status not in DONE_STATUSES]
    incomplete_action = complete_in.incomplete_action
    if incomplete_action == "move_to_next_sprint" and not carry_forward_sprint:
        incomplete_action = "keep_in_sprint"
    if complete_in.carry_forward_sprint_id and incomplete_action == "move_to_next_sprint":
        incomplete_action = "move_to_next_sprint"
    if incomplete_action == "move_to_next_sprint" and carry_forward_sprint:
        for task in unfinished:
            task.sprint_id = carry_forward_sprint.id
            db.add(task)
        carry_forward_sprint.scope_change_count = (carry_forward_sprint.scope_change_count or 0) + len(unfinished)
        db.add(carry_forward_sprint)
    elif incomplete_action == "move_to_backlog":
        for task in unfinished:
            task.sprint_id = None
            db.add(task)
    sprint.status = "Completed"
    sprint.completed_at = datetime.utcnow()
    sprint.completed_by_user_id = current_user.id
    sprint.completed_story_points = sum(_task_points(task) for task in completed)
    sprint.velocity_points = sprint.completed_story_points
    sprint.carry_forward_task_count = len(unfinished)
    sprint.review_notes = complete_in.review_notes
    sprint.retrospective_notes = complete_in.retrospective_notes
    sprint.what_went_well = complete_in.what_went_well
    sprint.what_did_not_go_well = complete_in.what_did_not_go_well
    sprint.outcome = complete_in.outcome
    sprint.completion_summary = json.dumps({
        "completed_task_count": len(completed),
        "unfinished_task_count": len(unfinished),
        "incomplete_action": incomplete_action,
        "carry_forward_sprint_id": carry_forward_sprint.id if carry_forward_sprint else None,
        "review_notes": complete_in.review_notes,
        "retrospective_notes": complete_in.retrospective_notes,
        "outcome": complete_in.outcome,
        "action_item_count": len([item for item in complete_in.action_items if item.get("title")]),
    }, default=str)
    _upsert_sprint_action_items(db, sprint, project, current_user, complete_in.action_items, complete_in.create_action_item_tasks)
    _record_activity(db, sprint.project_id, current_user, "completed", "sprint", sprint.id, f"Completed sprint {sprint.name}", sprint_id=sprint.id)
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    _broadcast_realtime(
        current_user,
        "sprint.updated",
        project_id=sprint.project_id,
        sprint_id=sprint.id,
        message=f"Completed sprint {sprint.name}",
        entity={"id": sprint.id, "name": sprint.name, "status": sprint.status},
        data={"completedTaskCount": len(completed), "unfinishedTaskCount": len(unfinished)},
    )
    return sprint


@router.get("/sprints/{sprint_id}/burndown", response_model=SprintBurndownResponse)
def get_sprint_burndown(
    sprint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a sprint burndown series from commitment and completion dates."""
    sprint = db.query(PMSSprint).filter(PMSSprint.id == sprint_id).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    get_project_for_action(db, sprint.project_id, current_user, "browse")
    tasks = db.query(PMSTask).filter(PMSTask.sprint_id == sprint.id, PMSTask.deleted_at == None).all()
    committed = int(sprint.committed_story_points or sum(_task_points(task) for task in tasks))
    completed = sum(_task_points(task) for task in tasks if task.status in DONE_STATUSES)
    start = sprint.start_date
    end = sprint.end_date
    days = max((end - start).days, 1)
    points = []
    for offset in range(days + 1):
        day = start + timedelta(days=offset)
        ideal = max(committed - (committed * offset / days), 0)
        actual_completed = completed if day >= date.today() or sprint.status == "Completed" else 0
        points.append({
            "date": day,
            "ideal_remaining_points": ideal,
            "actual_remaining_points": max(committed - actual_completed, 0),
            "completed_points": actual_completed,
        })
    return {
        "sprint_id": sprint.id,
        "committed_story_points": committed,
        "completed_story_points": completed,
        "remaining_story_points": max(committed - completed, 0),
        "points": points,
    }


@router.get("/projects/{project_id}/velocity", response_model=ProjectVelocityResponse)
def get_project_velocity(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return completed sprint velocity history for a project."""
    get_project_for_action(db, project_id, current_user, "browse")
    sprints = db.query(PMSSprint).filter(
        PMSSprint.project_id == project_id,
        PMSSprint.status == "Completed",
    ).order_by(PMSSprint.end_date).all()
    items = [
        {"id": sprint.id, "name": sprint.name, "end_date": sprint.end_date, "velocity_points": int(sprint.velocity_points or sprint.completed_story_points or 0)}
        for sprint in sprints
    ]
    average = sum(item["velocity_points"] for item in items) / len(items) if items else 0
    return {"project_id": project_id, "average_velocity_points": average, "sprints": items}


# ============= REPORTS & ANALYTICS =============
@router.get("/reports/task-distribution")
def report_task_distribution(
    projectId: int = Query(None),
    assigneeId: int = Query(None),
    from_: date = Query(None, alias="from"),
    to: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tasks = _report_task_query(db, current_user, projectId, assigneeId, from_, to).all()
    by_status: dict[str, dict] = {}
    by_priority: dict[str, dict] = {}
    by_assignee: dict[str, dict] = {}
    for task in tasks:
        points = _task_points(task)
        by_status.setdefault(task.status or "Unspecified", {"name": task.status or "Unspecified", "tasks": 0, "story_points": 0})
        by_status[task.status or "Unspecified"]["tasks"] += 1
        by_status[task.status or "Unspecified"]["story_points"] += points
        by_priority.setdefault(task.priority or "Unspecified", {"name": task.priority or "Unspecified", "tasks": 0, "story_points": 0})
        by_priority[task.priority or "Unspecified"]["tasks"] += 1
        by_priority[task.priority or "Unspecified"]["story_points"] += points
        key = str(task.assignee_user_id or "Unassigned")
        by_assignee.setdefault(key, {"assignee_id": task.assignee_user_id, "name": key, "tasks": 0, "story_points": 0})
        by_assignee[key]["tasks"] += 1
        by_assignee[key]["story_points"] += points
    user_ids = [item["assignee_id"] for item in by_assignee.values() if item["assignee_id"]]
    users = {user.id: _user_display_name(user) for user in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    for item in by_assignee.values():
        if item["assignee_id"]:
            item["name"] = users.get(item["assignee_id"], item["name"])
    return {
        "total_tasks": len(tasks),
        "total_story_points": sum(_task_points(task) for task in tasks),
        "by_status": list(by_status.values()),
        "by_priority": list(by_priority.values()),
        "by_assignee": list(by_assignee.values()),
    }


@router.get("/reports/burndown")
def report_burndown(
    sprintId: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_sprint_burndown(sprintId, db=db, current_user=current_user)


@router.get("/reports/velocity")
def report_velocity(
    projectId: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_project_velocity(projectId, db=db, current_user=current_user)


@router.get("/reports/cumulative-flow")
def report_cumulative_flow(
    projectId: int = Query(None),
    from_: date = Query(None, alias="from"),
    to: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start, end = _date_range_defaults(from_, to)
    tasks = _report_task_query(db, current_user, projectId, None, None, end).all()
    changes_by_task = _status_changes_for_tasks(db, [task.id for task in tasks])
    statuses = sorted({task.status for task in tasks if task.status} | {"Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done"})
    points = []
    cursor = start
    while cursor <= end:
        day_end = datetime.combine(cursor, datetime.max.time())
        row = {"date": cursor.isoformat()}
        for status_name in statuses:
            row[status_name] = 0
        for task in tasks:
            status_name = _task_status_on(task, changes_by_task.get(task.id, []), day_end)
            if status_name:
                row[status_name] = row.get(status_name, 0) + 1
        points.append(row)
        cursor += timedelta(days=1)
    return {"statuses": statuses, "points": points}


@router.get("/reports/cycle-time")
def report_cycle_time(
    projectId: int = Query(None),
    assigneeId: int = Query(None),
    from_: date = Query(None, alias="from"),
    to: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start, end = _date_range_defaults(from_, to)
    tasks = _report_task_query(db, current_user, projectId, assigneeId, None, end).all()
    changes_by_task = _status_changes_for_tasks(db, [task.id for task in tasks])
    items = []
    for task in tasks:
        completed_at = _task_completed_at(task, changes_by_task.get(task.id, []))
        if not completed_at or completed_at.date() < start or completed_at.date() > end:
            continue
        started_at = _task_started_at(task, changes_by_task.get(task.id, [])) or task.created_at
        lead_hours = max((completed_at - task.created_at).total_seconds() / 3600, 0) if task.created_at else 0
        cycle_hours = max((completed_at - started_at).total_seconds() / 3600, 0) if started_at else lead_hours
        items.append({
            "task_id": task.id,
            "task_key": task.task_key,
            "title": task.title,
            "assignee_id": task.assignee_user_id,
            "story_points": _task_points(task),
            "started_at": _json_ready(started_at),
            "completed_at": _json_ready(completed_at),
            "lead_time_hours": round(lead_hours, 2),
            "cycle_time_hours": round(cycle_hours, 2),
        })
    avg_lead = sum(item["lead_time_hours"] for item in items) / len(items) if items else 0
    avg_cycle = sum(item["cycle_time_hours"] for item in items) / len(items) if items else 0
    return {"average_lead_time_hours": round(avg_lead, 2), "average_cycle_time_hours": round(avg_cycle, 2), "items": items}


@router.get("/reports/time-in-status")
def report_time_in_status(
    projectId: int = Query(None),
    from_: date = Query(None, alias="from"),
    to: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _start, end = _date_range_defaults(from_, to)
    now = datetime.combine(end, datetime.max.time())
    tasks = _report_task_query(db, current_user, projectId, None, None, end).all()
    changes_by_task = _status_changes_for_tasks(db, [task.id for task in tasks])
    totals: dict[str, float] = {}
    items = []
    for task in tasks:
        cursor = task.created_at or now
        current_status = changes_by_task.get(task.id, [{}])[0].get("old_status") or task.status
        task_status_hours: dict[str, float] = {}
        for change in changes_by_task.get(task.id, []):
            changed_at = change["changed_at"]
            hours = max((changed_at - cursor).total_seconds() / 3600, 0) if changed_at and cursor else 0
            task_status_hours[current_status] = task_status_hours.get(current_status, 0) + hours
            totals[current_status] = totals.get(current_status, 0) + hours
            current_status = change.get("new_status") or current_status
            cursor = changed_at
        hours = max((now - cursor).total_seconds() / 3600, 0) if cursor else 0
        task_status_hours[current_status] = task_status_hours.get(current_status, 0) + hours
        totals[current_status] = totals.get(current_status, 0) + hours
        items.append({"task_id": task.id, "task_key": task.task_key, "statuses": {key: round(value, 2) for key, value in task_status_hours.items()}})
    return {
        "statuses": [{"status": key, "hours": round(value, 2), "days": round(value / 24, 2)} for key, value in sorted(totals.items())],
        "items": items,
    }


@router.get("/reports/project-health")
def report_project_health(
    projectId: int = Query(None),
    from_: date = Query(None, alias="from"),
    to: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start, end = _date_range_defaults(from_, to)
    projects, tasks_by_project, sprints_by_project, _milestones_by_project, risks_by_project, _owners, _clients = _portfolio_context(db, current_user)
    if projectId:
        projects = [project for project in projects if project.id == projectId]
    points = []
    cursor = start
    while cursor <= end:
        row = {"date": cursor.isoformat(), "Good": 0, "At Risk": 0, "Blocked": 0, "Completed": 0}
        for project in projects:
            health = _portfolio_health(project, tasks_by_project.get(project.id, []), sprints_by_project.get(project.id, []), risks_by_project.get(project.id, []))
            row[health] = row.get(health, 0) + 1
        points.append(row)
        cursor += timedelta(days=7)
    return {"points": points}


@router.get("/reports/team-performance")
def report_team_performance(
    projectId: int = Query(None),
    sprintId: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tasks = _report_task_query(db, current_user, projectId).all()
    if sprintId:
        sprint = db.query(PMSSprint).filter(PMSSprint.id == sprintId).first()
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint not found")
        get_project_for_action(db, sprint.project_id, current_user, "browse")
        tasks = [task for task in tasks if task.sprint_id == sprintId]
    changes_by_task = _status_changes_for_tasks(db, [task.id for task in tasks])
    by_user: dict[int | str, dict] = {}
    for task in tasks:
        key: int | str = task.assignee_user_id or "unassigned"
        row = by_user.setdefault(key, {"assignee_id": task.assignee_user_id, "name": "Unassigned", "assigned_tasks": 0, "completed_tasks": 0, "assigned_points": 0, "completed_points": 0, "avg_cycle_time_hours": 0, "_cycles": []})
        row["assigned_tasks"] += 1
        row["assigned_points"] += _task_points(task)
        if task.status in DONE_STATUSES:
            row["completed_tasks"] += 1
            row["completed_points"] += _task_points(task)
            completed_at = _task_completed_at(task, changes_by_task.get(task.id, []))
            started_at = _task_started_at(task, changes_by_task.get(task.id, [])) or task.created_at
            if completed_at and started_at:
                row["_cycles"].append(max((completed_at - started_at).total_seconds() / 3600, 0))
    user_ids = [key for key in by_user if isinstance(key, int)]
    users = {user.id: _user_display_name(user) for user in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    items = []
    for key, row in by_user.items():
        cycles = row.pop("_cycles")
        row["name"] = users.get(key, "Unassigned") if isinstance(key, int) else "Unassigned"
        row["completion_rate"] = round((row["completed_tasks"] / row["assigned_tasks"]) * 100, 2) if row["assigned_tasks"] else 0
        row["avg_cycle_time_hours"] = round(sum(cycles) / len(cycles), 2) if cycles else 0
        items.append(row)
    return {"items": items}


@router.get("/reports/status-dashboard")
def report_project_status_dashboard(
    projectId: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects, tasks_by_project, sprints_by_project, milestones_by_project, risks_by_project, owners, clients = _portfolio_context(db, current_user)
    if projectId:
        projects = [project for project in projects if project.id == projectId]
    payloads = [
        _portfolio_project_payload(
            project,
            owners.get(project.manager_user_id),
            clients.get(project.client_id),
            tasks_by_project.get(project.id, []),
            sprints_by_project.get(project.id, []),
            milestones_by_project.get(project.id, []),
            risks_by_project.get(project.id, []),
        )
        for project in projects
    ]
    by_status: dict[str, int] = {}
    by_health: dict[str, int] = {}
    for item in payloads:
        by_status[item["status"] or "Unspecified"] = by_status.get(item["status"] or "Unspecified", 0) + 1
        by_health[item["health"] or "Unspecified"] = by_health.get(item["health"] or "Unspecified", 0) + 1
    return {"total_projects": len(payloads), "by_status": by_status, "by_health": by_health, "projects": payloads}


@router.get("/reports/overdue-tasks")
def report_overdue_tasks(
    projectId: int = Query(None),
    assigneeId: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    tasks = _report_task_query(db, current_user, projectId, assigneeId).filter(
        PMSTask.status.notin_(DONE_STATUSES),
        PMSTask.due_date != None,
        PMSTask.due_date < today,
    ).order_by(PMSTask.due_date.asc()).all()
    return {
        "count": len(tasks),
        "items": [
            {
                "task_id": task.id,
                "task_key": task.task_key,
                "title": task.title,
                "project_id": task.project_id,
                "assignee_user_id": task.assignee_user_id,
                "status": task.status,
                "priority": task.priority,
                "due_date": task.due_date,
                "days_overdue": (today - task.due_date).days if task.due_date else 0,
            }
            for task in tasks
        ],
    }


@router.get("/reports/milestone-progress")
def report_milestone_progress(
    projectId: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_ids = _report_project_ids(db, current_user, projectId)
    milestones = db.query(PMSMilestone).filter(PMSMilestone.project_id.in_(project_ids or [0])).order_by(PMSMilestone.due_date.asc().nullslast()).all()
    items = []
    for milestone in milestones:
        tasks = db.query(PMSTask).filter(PMSTask.milestone_id == milestone.id, PMSTask.deleted_at == None).all()
        done = len([task for task in tasks if task.status in DONE_STATUSES])
        calculated_progress = round(done / len(tasks) * 100, 2) if tasks else float(milestone.progress_percent or 0)
        items.append({
            "milestone_id": milestone.id,
            "project_id": milestone.project_id,
            "name": milestone.name,
            "status": milestone.status,
            "start_date": milestone.start_date,
            "due_date": milestone.due_date,
            "stored_progress_percent": milestone.progress_percent,
            "calculated_progress_percent": calculated_progress,
            "total_tasks": len(tasks),
            "completed_tasks": done,
            "client_approval_status": milestone.client_approval_status,
        })
    return {"count": len(items), "items": items}


@router.get("/reports/planned-vs-actual")
def report_planned_vs_actual(
    projectId: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_ids = _report_project_ids(db, current_user, projectId)
    projects = db.query(PMSProject).filter(PMSProject.id.in_(project_ids or [0])).order_by(PMSProject.name).all()
    rows = []
    for project in projects:
        tasks = db.query(PMSTask).filter(PMSTask.project_id == project.id, PMSTask.deleted_at == None).all()
        logs = db.query(PMSTimeLog).filter(PMSTimeLog.project_id == project.id).all()
        planned_hours = Decimal(project.estimated_hours or 0) or sum((task.estimated_hours or Decimal("0")) for task in tasks)
        actual_hours = sum(Decimal(log.duration_minutes or 0) for log in logs) / Decimal("60")
        planned_start = project.planned_start_date or project.start_date
        planned_end = project.planned_end_date or project.due_date
        actual_start = project.actual_start_date
        actual_end = project.actual_end_date or (project.completed_at.date() if project.completed_at else None)
        rows.append({
            "project_id": project.id,
            "project_key": project.project_key,
            "project_name": project.name,
            "planned_start_date": planned_start,
            "planned_end_date": planned_end,
            "actual_start_date": actual_start,
            "actual_end_date": actual_end,
            "planned_hours": _json_ready(planned_hours),
            "actual_hours": _json_ready(actual_hours),
            "hour_variance": _json_ready(actual_hours - planned_hours),
            "schedule_variance_days": (actual_end - planned_end).days if actual_end and planned_end else None,
        })
    return {"count": len(rows), "items": rows}


@router.get("/reports/timesheet")
def report_timesheet(
    projectId: int = Query(None),
    userId: int = Query(None),
    from_: date = Query(None, alias="from"),
    to: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_ids = _report_project_ids(db, current_user, projectId)
    query = db.query(PMSTimeLog).filter(PMSTimeLog.project_id.in_(project_ids or [0]))
    if userId:
        query = query.filter(PMSTimeLog.user_id == userId)
    if from_:
        query = query.filter(PMSTimeLog.log_date >= from_)
    if to:
        query = query.filter(PMSTimeLog.log_date <= to)
    logs = query.order_by(PMSTimeLog.log_date.desc()).all()
    return {
        "total_hours": _json_ready(sum(Decimal(log.duration_minutes or 0) for log in logs) / Decimal("60")),
        "billable_hours": _json_ready(sum(Decimal(log.duration_minutes or 0) for log in logs if log.is_billable) / Decimal("60")),
        "non_billable_hours": _json_ready(sum(Decimal(log.duration_minutes or 0) for log in logs if not log.is_billable) / Decimal("60")),
        "items": [
            {
                "id": log.id,
                "project_id": log.project_id,
                "task_id": log.task_id,
                "user_id": log.user_id,
                "log_date": log.log_date,
                "hours": _json_ready(Decimal(log.duration_minutes or 0) / Decimal("60")),
                "is_billable": log.is_billable,
                "approval_status": log.approval_status,
            }
            for log in logs
        ],
    }


@router.get("/reports/resource-utilization")
def report_resource_utilization(
    projectId: int = Query(None),
    from_: date = Query(None, alias="from"),
    to: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start, end = _date_range_defaults(from_, to)
    project_ids = _report_project_ids(db, current_user, projectId)
    logs = db.query(PMSTimeLog).filter(
        PMSTimeLog.project_id.in_(project_ids or [0]),
        PMSTimeLog.log_date >= start,
        PMSTimeLog.log_date <= end,
    ).all()
    capacities = {
        row.user_id: Decimal(row.capacity_hours or 0)
        for row in db.query(PMSUserCapacity).filter(PMSUserCapacity.week_start_date.in_(_weeks_between(start, end))).all()
    }
    by_user: dict[int, dict] = {}
    for log in logs:
        row = by_user.setdefault(log.user_id, {"user_id": log.user_id, "logged_hours": Decimal("0"), "billable_hours": Decimal("0")})
        row["logged_hours"] += Decimal(log.duration_minutes or 0) / Decimal("60")
        if log.is_billable:
            row["billable_hours"] += Decimal(log.duration_minutes or 0) / Decimal("60")
    users = {user.id: _user_display_name(user) for user in db.query(User).filter(User.id.in_(list(by_user) or [0])).all()}
    items = []
    for user_id, row in by_user.items():
        capacity = capacities.get(user_id, Decimal("40") * Decimal(len(_weeks_between(start, end)) or 1))
        items.append({
            "user_id": user_id,
            "name": users.get(user_id),
            "logged_hours": _json_ready(row["logged_hours"]),
            "billable_hours": _json_ready(row["billable_hours"]),
            "capacity_hours": _json_ready(capacity),
            "utilization_percent": round(float((row["logged_hours"] / capacity * Decimal("100")) if capacity else Decimal("0")), 2),
        })
    return {"items": items}


@router.get("/reports/budget-vs-actual")
def report_budget_vs_actual(
    projectId: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"items": _project_financial_rows(db, current_user, projectId)}


@router.get("/reports/client-profitability")
def report_client_profitability(
    projectId: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = _project_financial_rows(db, current_user, projectId)
    by_client: dict[str, dict] = {}
    for row in rows:
        key = str(row["client_id"] or "No client")
        item = by_client.setdefault(key, {"client_id": row["client_id"], "projects": 0, "budget_amount": 0.0, "actual_cost": 0.0, "profitability_amount": 0.0})
        item["projects"] += 1
        item["budget_amount"] += float(row["budget_amount"] or 0)
        item["actual_cost"] += float(row["actual_cost"] or 0)
        item["profitability_amount"] += float(row["profitability_amount"] or 0)
    return {"items": list(by_client.values()), "projects": rows}


@router.get("/reports/dependency-delays")
def report_dependency_delays(
    projectId: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_ids = _report_project_ids(db, current_user, projectId)
    tasks = {task.id: task for task in db.query(PMSTask).filter(PMSTask.project_id.in_(project_ids or [0]), PMSTask.deleted_at == None).all()}
    dependencies = db.query(PMSTaskDependency).filter(PMSTaskDependency.task_id.in_(list(tasks) or [0])).all()
    delays = []
    for dep in dependencies:
        task = tasks.get(dep.task_id)
        blocker = tasks.get(dep.depends_on_task_id)
        if not task or not blocker or not blocker.due_date:
            continue
        allowed_start = blocker.due_date + timedelta(days=dep.lag_days or 0)
        target_date = task.start_date or task.due_date
        if target_date and target_date < allowed_start:
            delays.append({
                "dependency_id": dep.id,
                "task_id": task.id,
                "task_key": task.task_key,
                "depends_on_task_id": blocker.id,
                "depends_on_task_key": blocker.task_key,
                "dependency_type": dep.dependency_type,
                "lag_days": dep.lag_days,
                "allowed_start": allowed_start,
                "scheduled_start": target_date,
                "delay_days": (allowed_start - target_date).days,
            })
    return {"count": len(delays), "items": delays}


@router.get("/reports/export")
def export_reports(
    report: str = Query("task-distribution"),
    format: str = Query("csv"),
    projectId: int = Query(None),
    sprintId: int = Query(None),
    assigneeId: int = Query(None),
    from_: date = Query(None, alias="from"),
    to: date = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if report == "cycle-time":
        data = report_cycle_time(projectId, assigneeId, from_, to, db, current_user)
        rows = [[item["task_key"], item["title"], item["lead_time_hours"], item["cycle_time_hours"], item["completed_at"]] for item in data["items"]]
        headers = ["Task", "Title", "Lead Time Hours", "Cycle Time Hours", "Completed At"]
    elif report == "team-performance":
        data = report_team_performance(projectId, sprintId, db, current_user)
        rows = [[item["name"], item["assigned_tasks"], item["completed_tasks"], item["assigned_points"], item["completed_points"], item["completion_rate"]] for item in data["items"]]
        headers = ["Assignee", "Assigned Tasks", "Completed Tasks", "Assigned Points", "Completed Points", "Completion Rate"]
    else:
        data = report_task_distribution(projectId, assigneeId, from_, to, db, current_user)
        rows = [[item["name"], item["tasks"], item["story_points"]] for item in data["by_status"]]
        headers = ["Status", "Tasks", "Story Points"]
    safe_report = re.sub(r"[^a-z0-9_-]+", "-", report.lower())
    if format.lower() == "pdf":
        lines = [", ".join(map(str, headers))] + [", ".join(map(str, row)) for row in rows]
        return _simple_pdf_response(f"{safe_report}.pdf", f"PMS {report} report", lines)
    return _csv_response(f"{safe_report}.{'xlsx' if format.lower() in {'excel', 'xlsx'} else 'csv'}", headers, rows)


# ============= FILES =============
@router.post("/files", response_model=PMSFileAssetResponse)
def create_file_metadata(
    file_in: PMSFileAssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create file metadata. Actual binary upload can be plugged in later."""
    if file_in.project_id:
        get_project_for_action(db, file_in.project_id, current_user, "upload")
    if file_in.task_id:
        task, _project = get_task_project_for_action(db, file_in.task_id, current_user, "upload")
        if file_in.project_id and task.project_id != file_in.project_id:
            raise HTTPException(status_code=400, detail="Task does not belong to selected project")
    file_asset = PMSFileAsset(
        **file_in.dict(exclude={"uploaded_by_user_id"}),
        uploaded_by_user_id=current_user.id,
    )
    db.add(file_asset)
    db.flush()
    if file_asset.task_id:
        _record_activity(
            db,
            file_asset.project_id,
            current_user,
            "attachment.added",
            "file",
            file_asset.id,
            f"Attached {file_asset.original_name or file_asset.file_name}",
            task_id=file_asset.task_id,
            metadata={"file_id": file_asset.id, "file_name": file_asset.original_name or file_asset.file_name},
        )
    db.commit()
    db.refresh(file_asset)
    return _file_payload(file_asset, current_user)


@router.get("/files", response_model=list[PMSFileAssetResponse])
def list_files(
    project_id: int = Query(None),
    task_id: int = Query(None),
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List accessible file metadata."""
    accessible_project_ids = accessible_project_query(db, current_user).with_entities(PMSProject.id)
    query = db.query(PMSFileAsset).filter(
        PMSFileAsset.deleted_at == None,
        PMSFileAsset.project_id.in_(accessible_project_ids),
    )
    if project_id:
        query = query.filter(PMSFileAsset.project_id == project_id)
    if task_id:
        query = query.filter(PMSFileAsset.task_id == task_id)
    files = query.order_by(desc(PMSFileAsset.created_at)).offset(skip).limit(limit).all()
    return _file_payloads(db, files)


@router.patch("/files/{file_id}", response_model=PMSFileAssetResponse)
def update_file_metadata(
    file_id: int,
    file_in: PMSFileAssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update file metadata."""
    file_asset = db.query(PMSFileAsset).filter(PMSFileAsset.id == file_id).first()
    if not file_asset:
        raise HTTPException(status_code=404, detail="File not found")
    if file_asset.project_id:
        get_project_for_action(db, file_asset.project_id, current_user, "upload")
    for field, value in file_in.dict(exclude_unset=True).items():
        setattr(file_asset, field, value)
    db.add(file_asset)
    db.commit()
    db.refresh(file_asset)
    return _file_payload(file_asset, current_user)


@router.get("/attachments/{file_id}/download")
def download_attachment(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Authenticated download route for a PMS attachment."""
    file_asset, _project = _get_file_for_action(db, file_id, current_user, "browse")
    storage_path = Path(file_asset.storage_path).resolve()
    if not storage_path.exists() or not storage_path.is_file():
        raise HTTPException(status_code=404, detail="Stored attachment file not found")
    return FileResponse(
        path=str(storage_path),
        filename=file_asset.original_name or file_asset.file_name,
        media_type=file_asset.mime_type or "application/octet-stream",
    )


@router.delete("/attachments/{file_id}")
def delete_attachment(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete an attachment after validating project access."""
    file_asset, project = _get_file_for_action(db, file_id, current_user, "upload")
    file_asset.deleted_at = datetime.utcnow()
    db.add(file_asset)
    if file_asset.task_id:
        _record_activity(
            db,
            project.id,
            current_user,
            "attachment.deleted",
            "file",
            file_asset.id,
            f"Deleted attachment {file_asset.original_name or file_asset.file_name}",
            task_id=file_asset.task_id,
            metadata={"file_id": file_asset.id, "file_name": file_asset.original_name or file_asset.file_name},
        )
    db.commit()
    return {"message": "Attachment deleted"}


# ============= TIMESHEETS & TIME TRACKING =============
@router.get("/timesheets", response_model=list[PMSTimesheetResponse])
def list_timesheets(
    weekStart: date | None = Query(None),
    userId: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List weekly PMS timesheets scoped to the current user or approver visibility."""
    query = db.query(PMSTimesheet)
    if current_user.is_superuser:
        pass
    elif _can_manage_timesheets(current_user):
        query = query.filter(PMSTimesheet.organization_id == organization_id_for(current_user))
    else:
        query = query.filter(PMSTimesheet.user_id == current_user.id)
    if weekStart:
        query = query.filter(PMSTimesheet.week_start_date == _week_start(weekStart))
    if userId:
        if userId != current_user.id and not _can_manage_timesheets(current_user):
            raise HTTPException(status_code=403, detail="Cannot view another user's timesheets")
        query = query.filter(PMSTimesheet.user_id == userId)
    if status_filter:
        query = query.filter(PMSTimesheet.status == status_filter)
    sheets = query.order_by(desc(PMSTimesheet.week_start_date), desc(PMSTimesheet.id)).limit(100).all()
    payload = [_timesheet_payload(db, sheet) for sheet in sheets]
    db.commit()
    return payload


@router.post("/timesheets", response_model=PMSTimesheetResponse, status_code=status.HTTP_201_CREATED)
def create_timesheet(
    timesheet_in: PMSTimesheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or return a weekly PMS timesheet for a user."""
    user_id = timesheet_in.user_id or current_user.id
    if user_id != current_user.id and not _can_manage_timesheets(current_user):
        raise HTTPException(status_code=403, detail="Cannot create another user's timesheet")
    org_id = organization_id_for(current_user)
    week_start = _week_start(timesheet_in.week_start_date)
    sheet = db.query(PMSTimesheet).filter(
        PMSTimesheet.organization_id == org_id,
        PMSTimesheet.user_id == user_id,
        PMSTimesheet.week_start_date == week_start,
    ).first()
    if not sheet:
        sheet = PMSTimesheet(organization_id=org_id, user_id=user_id, week_start_date=week_start, status="draft")
        db.add(sheet)
        db.flush()
    if timesheet_in.entries:
        _replace_timesheet_entries(db, sheet, timesheet_in.entries, current_user)
    db.commit()
    db.refresh(sheet)
    return _timesheet_payload(db, sheet)


@router.patch("/timesheets/{timesheet_id}", response_model=PMSTimesheetResponse)
def update_timesheet(
    timesheet_id: int,
    timesheet_in: PMSTimesheetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replace editable weekly timesheet entries."""
    sheet = _get_timesheet_for_action(db, timesheet_id, current_user, "edit")
    if timesheet_in.week_start_date:
        sheet.week_start_date = _week_start(timesheet_in.week_start_date)
    _replace_timesheet_entries(db, sheet, timesheet_in.entries, current_user)
    db.commit()
    db.refresh(sheet)
    return _timesheet_payload(db, sheet)


@router.post("/timesheets/{timesheet_id}/submit", response_model=PMSTimesheetResponse)
def submit_timesheet(
    timesheet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a draft or rejected PMS timesheet for approval."""
    sheet = _get_timesheet_for_action(db, timesheet_id, current_user, "edit")
    if sheet.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner can submit their timesheet")
    if sheet.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected timesheets can be submitted")
    logs = _timesheet_logs(db, sheet)
    if not logs:
        raise HTTPException(status_code=400, detail="Cannot submit an empty timesheet")
    sheet.status = "submitted"
    sheet.submitted_at = datetime.utcnow()
    sheet.rejection_reason = None
    for log in logs:
        log.timesheet_id = sheet.id
        log.approval_status = "Submitted"
        db.add(log)
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return _timesheet_payload(db, sheet)


@router.post("/timesheets/{timesheet_id}/approve", response_model=PMSTimesheetResponse)
def approve_timesheet(
    timesheet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a submitted PMS timesheet."""
    sheet = _get_timesheet_for_action(db, timesheet_id, current_user, "approve")
    if sheet.status != "submitted":
        raise HTTPException(status_code=400, detail="Only submitted timesheets can be approved")
    sheet.status = "approved"
    sheet.approved_by_user_id = current_user.id
    sheet.approved_at = datetime.utcnow()
    sheet.rejection_reason = None
    for log in _timesheet_logs(db, sheet):
        log.approval_status = "Approved"
        log.approved_by_user_id = current_user.id
        log.approved_at = sheet.approved_at
        db.add(log)
        _record_activity(db, log.project_id, current_user, "timesheet.approved", "timesheet", sheet.id, "Approved timesheet entry", task_id=log.task_id, metadata={"timesheet_id": sheet.id, "time_log_id": log.id})
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return _timesheet_payload(db, sheet)


@router.post("/timesheets/{timesheet_id}/reject", response_model=PMSTimesheetResponse)
def reject_timesheet(
    timesheet_id: int,
    reject_in: PMSTimesheetRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reject a submitted PMS timesheet with comments."""
    sheet = _get_timesheet_for_action(db, timesheet_id, current_user, "reject")
    if sheet.status != "submitted":
        raise HTTPException(status_code=400, detail="Only submitted timesheets can be rejected")
    sheet.status = "rejected"
    sheet.rejection_reason = reject_in.rejection_reason
    sheet.approved_by_user_id = current_user.id
    sheet.approved_at = datetime.utcnow()
    for log in _timesheet_logs(db, sheet):
        log.approval_status = "Rejected"
        db.add(log)
        _record_activity(db, log.project_id, current_user, "timesheet.rejected", "timesheet", sheet.id, "Rejected timesheet entry", task_id=log.task_id, metadata={"timesheet_id": sheet.id, "time_log_id": log.id, "reason": reject_in.rejection_reason})
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return _timesheet_payload(db, sheet)


@router.post("/time-logs", response_model=PMSTimeLogResponse)
def create_time_log(
    timelog_in: PMSTimeLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a time log entry."""
    # Verify project exists
    get_project_for_action(db, timelog_in.project_id, current_user, "log_time")
    if timelog_in.task_id:
        task, _project = get_task_project_for_action(db, timelog_in.task_id, current_user, "log_time")
        if task.project_id != timelog_in.project_id:
            raise HTTPException(status_code=400, detail="Task does not belong to selected project")

    db_timelog = PMSTimeLog(user_id=current_user.id, **timelog_in.dict())
    db.add(db_timelog)
    db.flush()
    _record_activity(
        db,
        timelog_in.project_id,
        current_user,
        "time.logged",
        "time_log",
        db_timelog.id,
        f"Logged {db_timelog.duration_minutes} minutes",
        task_id=db_timelog.task_id,
        metadata={"duration_minutes": db_timelog.duration_minutes, "is_billable": db_timelog.is_billable},
    )
    db.commit()
    db.refresh(db_timelog)
    return db_timelog


@router.patch("/time-logs/{time_log_id}", response_model=PMSTimeLogResponse)
def update_time_log(
    time_log_id: int,
    timelog_in: PMSTimeLogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a time log entry."""
    time_log, project = _get_time_log_for_action(db, time_log_id, current_user, "log_time")
    if time_log.timesheet_id:
        sheet = db.query(PMSTimesheet).filter(PMSTimesheet.id == time_log.timesheet_id).first()
        if sheet and sheet.status not in {"draft", "rejected"}:
            raise HTTPException(status_code=400, detail="Submitted or approved timesheet logs cannot be edited")
    update_data = timelog_in.dict(exclude_unset=True)
    if "task_id" in update_data and update_data["task_id"]:
        task, _task_project = get_task_project_for_action(db, update_data["task_id"], current_user, "log_time")
        if task.project_id != project.id:
            raise HTTPException(status_code=400, detail="Task does not belong to selected project")
    if "approval_status" in update_data and time_log.user_id == current_user.id and not can_access_project(db, project, current_user, "manage_tasks"):
        raise HTTPException(status_code=403, detail="Only task managers can change time approval status")
    for field, value in update_data.items():
        setattr(time_log, field, value)
    db.add(time_log)
    _record_activity(
        db,
        project.id,
        current_user,
        "time.updated",
        "time_log",
        time_log.id,
        "Updated time log",
        task_id=time_log.task_id,
        metadata=update_data,
    )
    db.commit()
    db.refresh(time_log)
    return time_log


@router.delete("/time-logs/{time_log_id}")
def delete_time_log(
    time_log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a time log entry."""
    time_log, project = _get_time_log_for_action(db, time_log_id, current_user, "log_time")
    if time_log.timesheet_id:
        sheet = db.query(PMSTimesheet).filter(PMSTimesheet.id == time_log.timesheet_id).first()
        if sheet and sheet.status not in {"draft", "rejected"}:
            raise HTTPException(status_code=400, detail="Submitted or approved timesheet logs cannot be deleted")
    task_id = time_log.task_id
    duration = time_log.duration_minutes
    db.delete(time_log)
    _record_activity(
        db,
        project.id,
        current_user,
        "time.deleted",
        "time_log",
        time_log_id,
        f"Deleted time log of {duration} minutes",
        task_id=task_id,
        metadata={"duration_minutes": duration},
    )
    db.commit()
    return {"message": "Time log deleted"}


@router.get("/time-logs", response_model=list[PMSTimeLogResponse])
def list_time_logs(
    skip: int = Query(0),
    limit: int = Query(100),
    project_id: int = Query(None),
    user_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List time logs."""
    accessible_project_ids = accessible_project_query(db, current_user).with_entities(PMSProject.id)
    query = db.query(PMSTimeLog).filter(PMSTimeLog.project_id.in_(accessible_project_ids))
    
    if project_id:
        # Verify project access
        get_project_for_action(db, project_id, current_user, "browse")
        query = query.filter(PMSTimeLog.project_id == project_id)
    
    if user_id:
        query = query.filter(PMSTimeLog.user_id == user_id)
    
    timelogs = query.offset(skip).limit(limit).all()
    return timelogs


# ============= SAVED FILTERS, ACTIVITY, REPORTS =============
@router.get("/saved-views", response_model=list[PMSSavedFilterResponse])
def list_saved_views(
    entityType: str = Query("task"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List saved views for the current user and shared workspace/team views."""
    org_id = organization_id_for(current_user)
    accessible_project_ids = accessible_project_query(db, current_user).with_entities(PMSProject.id)
    query = db.query(PMSSavedFilter).filter(
        PMSSavedFilter.entity_type == entityType,
        or_(PMSSavedFilter.user_id == current_user.id, PMSSavedFilter.is_shared == True, PMSSavedFilter.visibility.in_(["team", "workspace"])),
        or_(PMSSavedFilter.project_id == None, PMSSavedFilter.project_id.in_(accessible_project_ids)),
    )
    if org_id is not None and not current_user.is_superuser:
        query = query.filter(or_(PMSSavedFilter.organization_id == org_id, PMSSavedFilter.user_id == current_user.id))
    return [_saved_view_payload(item) for item in query.order_by(desc(PMSSavedFilter.is_default), PMSSavedFilter.name).all()]


@router.post("/saved-views", response_model=PMSSavedFilterResponse, status_code=status.HTTP_201_CREATED)
def create_saved_view(
    view_in: PMSSavedFilterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a saved task view with filters, sort state, and visible columns."""
    if view_in.project_id:
        get_project_for_action(db, view_in.project_id, current_user, "browse")
    data = view_in.dict()
    saved_filter = PMSSavedFilter(
        organization_id=organization_id_for(current_user),
        project_id=data.get("project_id"),
        user_id=current_user.id,
        name=view_in.name,
        view_type=view_in.view_type or "task_list",
        entity_type=view_in.entity_type or "task",
        query=view_in.query or json.dumps(view_in.filters or {}, default=str),
    )
    _apply_saved_view_payload(saved_filter, data)
    if saved_filter.is_default:
        db.query(PMSSavedFilter).filter(
            PMSSavedFilter.user_id == current_user.id,
            PMSSavedFilter.entity_type == saved_filter.entity_type,
            PMSSavedFilter.id != saved_filter.id,
        ).update({"is_default": False}, synchronize_session=False)
    db.add(saved_filter)
    db.commit()
    db.refresh(saved_filter)
    return _saved_view_payload(saved_filter)


@router.patch("/saved-views/{view_id}", response_model=PMSSavedFilterResponse)
def update_saved_view(
    view_id: int,
    view_in: PMSSavedFilterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a saved task view."""
    saved_filter = db.query(PMSSavedFilter).filter(PMSSavedFilter.id == view_id).first()
    if not saved_filter:
        raise HTTPException(status_code=404, detail="Saved view not found")
    if not _can_manage_saved_view(db, saved_filter, current_user):
        raise HTTPException(status_code=403, detail="Can only edit your own views unless you manage the project")
    data = view_in.dict(exclude_unset=True)
    for field in ("name", "view_type", "entity_type"):
        if field in data and data[field] is not None:
            setattr(saved_filter, field, data[field])
    _apply_saved_view_payload(saved_filter, data)
    if saved_filter.is_default:
        db.query(PMSSavedFilter).filter(
            PMSSavedFilter.user_id == saved_filter.user_id,
            PMSSavedFilter.entity_type == saved_filter.entity_type,
            PMSSavedFilter.id != saved_filter.id,
        ).update({"is_default": False}, synchronize_session=False)
    db.add(saved_filter)
    db.commit()
    db.refresh(saved_filter)
    return _saved_view_payload(saved_filter)


@router.delete("/saved-views/{view_id}")
def delete_saved_view(
    view_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a saved task view."""
    saved_filter = db.query(PMSSavedFilter).filter(PMSSavedFilter.id == view_id).first()
    if not saved_filter:
        raise HTTPException(status_code=404, detail="Saved view not found")
    if not _can_manage_saved_view(db, saved_filter, current_user):
        raise HTTPException(status_code=403, detail="Can only delete your own views unless you manage the project")
    db.delete(saved_filter)
    db.commit()
    return {"message": "Saved view deleted"}


@router.post("/projects/{project_id}/saved-filters", response_model=PMSSavedFilterResponse, status_code=status.HTTP_201_CREATED)
def create_saved_filter(
    project_id: int,
    filter_in: PMSSavedFilterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a project board/backlog/report filter."""
    get_project_for_action(db, project_id, current_user, "browse")
    data = filter_in.dict(exclude={"project_id", "filters", "sort", "columns"})
    if not data.get("query"):
        data["query"] = json.dumps(filter_in.filters or {}, default=str)
    saved_filter = PMSSavedFilter(
        project_id=project_id,
        organization_id=organization_id_for(current_user),
        user_id=current_user.id,
        **data,
    )
    if filter_in.filters is not None:
        saved_filter.filters_json = json.dumps(filter_in.filters, default=str)
    if filter_in.sort is not None:
        saved_filter.sort_json = json.dumps(filter_in.sort, default=str)
    if filter_in.columns is not None:
        saved_filter.columns_json = json.dumps(filter_in.columns, default=str)
    db.add(saved_filter)
    _record_activity(db, project_id, current_user, "created", "saved_filter", None, f"Saved filter {filter_in.name}")
    db.commit()
    db.refresh(saved_filter)
    return saved_filter


@router.get("/projects/{project_id}/saved-filters", response_model=list[PMSSavedFilterResponse])
def list_saved_filters(
    project_id: int,
    view_type: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user-owned and shared saved filters for a project."""
    get_project_for_action(db, project_id, current_user, "browse")
    query = db.query(PMSSavedFilter).filter(
        PMSSavedFilter.project_id == project_id,
        or_(PMSSavedFilter.user_id == current_user.id, PMSSavedFilter.is_shared == True),
    )
    if view_type:
        query = query.filter(PMSSavedFilter.view_type == view_type)
    return query.order_by(PMSSavedFilter.is_shared.desc(), PMSSavedFilter.name).all()


@router.patch("/saved-filters/{filter_id}", response_model=PMSSavedFilterResponse)
def update_saved_filter(
    filter_id: int,
    filter_in: PMSSavedFilterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a saved filter."""
    saved_filter = db.query(PMSSavedFilter).filter(PMSSavedFilter.id == filter_id).first()
    if not saved_filter:
        raise HTTPException(status_code=404, detail="Saved filter not found")
    get_project_for_action(db, saved_filter.project_id, current_user, "browse")
    if saved_filter.user_id != current_user.id and not can_access_project(db, get_project_for_action(db, saved_filter.project_id, current_user, "browse"), current_user, "manage_tasks"):
        raise HTTPException(status_code=403, detail="Can only edit your own filters")
    for field, value in filter_in.dict(exclude_unset=True).items():
        setattr(saved_filter, field, value)
    db.add(saved_filter)
    db.commit()
    db.refresh(saved_filter)
    return saved_filter


@router.delete("/saved-filters/{filter_id}")
def delete_saved_filter(
    filter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a saved filter."""
    saved_filter = db.query(PMSSavedFilter).filter(PMSSavedFilter.id == filter_id).first()
    if not saved_filter:
        raise HTTPException(status_code=404, detail="Saved filter not found")
    get_project_for_action(db, saved_filter.project_id, current_user, "browse")
    if saved_filter.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Can only delete your own filters")
    db.delete(saved_filter)
    db.commit()
    return {"message": "Saved filter deleted"}


@router.get("/projects/{project_id}/activity", response_model=list[PMSActivityResponse])
def list_project_activity(
    project_id: int,
    task_id: int = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return recent activity for a project or task."""
    get_project_for_action(db, project_id, current_user, "browse")
    query = db.query(PMSActivity).filter(PMSActivity.project_id == project_id)
    if task_id:
        query = query.filter(PMSActivity.task_id == task_id)
    return query.order_by(desc(PMSActivity.created_at)).limit(limit).all()


@router.get("/projects/{project_id}/workload", response_model=WorkloadResponse)
def get_project_workload(
    project_id: int,
    group_by: str = Query("user"),
    sprint_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return capacity/workload grouped by user or sprint."""
    get_project_for_action(db, project_id, current_user, "browse")
    query = db.query(PMSTask).filter(PMSTask.project_id == project_id, PMSTask.deleted_at == None, PMSTask.status.notin_(DONE_STATUSES))
    if sprint_id:
        query = query.filter(PMSTask.sprint_id == sprint_id)
    tasks = query.all()
    today = date.today()
    grouped: dict[int | None, dict] = {}
    key_field = "sprint_id" if group_by == "sprint" else "assignee_user_id"
    for task in tasks:
        key = getattr(task, key_field)
        item = grouped.setdefault(key, {
            "user_id": task.assignee_user_id if group_by != "sprint" else None,
            "sprint_id": task.sprint_id if group_by == "sprint" else None,
            "task_count": 0,
            "story_points": 0,
            "estimated_hours": 0.0,
            "overdue_tasks": 0,
            "capacity_hours": None,
            "load_percent": None,
        })
        item["task_count"] += 1
        item["story_points"] += _task_points(task)
        item["estimated_hours"] += float(task.estimated_hours or task.remaining_estimate_hours or task.original_estimate_hours or 0)
        if task.due_date and task.due_date < today:
            item["overdue_tasks"] += 1
    if group_by == "sprint":
        sprints = {sprint.id: sprint for sprint in db.query(PMSSprint).filter(PMSSprint.project_id == project_id).all()}
        for item in grouped.values():
            sprint = sprints.get(item["sprint_id"])
            if sprint and sprint.capacity_hours:
                item["capacity_hours"] = float(sprint.capacity_hours)
                item["load_percent"] = round((item["estimated_hours"] / item["capacity_hours"]) * 100, 1) if item["capacity_hours"] else None
    return {"project_id": project_id, "group_by": group_by, "items": list(grouped.values())}


@router.get("/workload")
def get_workload_heatmap(
    projectId: int = Query(None),
    teamId: int = Query(None),
    sprintId: int = Query(None),
    from_date: date = Query(None, alias="from"),
    to: date = Query(None),
    basis: str = Query("hours"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return assignee-by-week workload and capacity for accessible PMS projects."""
    del teamId  # Team-level filtering can be connected when team membership data is introduced.
    today = date.today()
    range_start = _week_start(from_date or today)
    range_end = _week_start(to or (range_start + timedelta(weeks=7)))
    if range_end < range_start:
        raise HTTPException(status_code=400, detail="Date range is invalid")
    if basis not in {"hours", "story_points", "task_count"}:
        raise HTTPException(status_code=400, detail="basis must be hours, story_points, or task_count")

    project_query = accessible_project_query(db, current_user)
    if projectId:
        get_project_for_action(db, projectId, current_user, "browse")
        project_query = project_query.filter(PMSProject.id == projectId)
    projects = project_query.order_by(PMSProject.name).all()
    project_ids = [project.id for project in projects]
    if not project_ids:
        return {"basis": basis, "from": range_start, "to": range_end, "weeks": [], "projects": [], "sprints": [], "users": [], "rows": [], "summary": {"over_capacity": 0, "near_capacity": 0, "under_capacity": 0}}

    task_query = db.query(PMSTask).filter(
        PMSTask.deleted_at == None,
        PMSTask.project_id.in_(project_ids),
        PMSTask.assignee_user_id != None,
        or_(PMSTask.start_date == None, PMSTask.start_date <= range_end + timedelta(days=6)),
        or_(PMSTask.due_date == None, PMSTask.due_date >= range_start),
    )
    if sprintId:
        task_query = task_query.filter(PMSTask.sprint_id == sprintId)
    tasks = task_query.order_by(PMSTask.due_date.is_(None), PMSTask.due_date, PMSTask.id).all()

    member_user_ids = {
        row[0]
        for row in db.query(PMSProjectMember.user_id).filter(PMSProjectMember.project_id.in_(project_ids)).all()
        if row[0]
    }
    assignee_ids = {task.assignee_user_id for task in tasks if task.assignee_user_id}
    user_ids = member_user_ids | assignee_ids
    users_by_id = {user.id: user for user in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    weeks = _weeks_between(range_start, range_end)

    capacity_rows = db.query(PMSUserCapacity).filter(
        PMSUserCapacity.user_id.in_(user_ids),
        PMSUserCapacity.week_start_date.in_(weeks),
    ).all() if user_ids and weeks else []
    capacity_by_user_week = {(row.user_id, row.week_start_date): float(row.capacity_hours or 0) for row in capacity_rows}

    sprint_rows = db.query(PMSSprint).filter(PMSSprint.project_id.in_(project_ids)).all()
    sprints_by_id = {sprint.id: sprint for sprint in sprint_rows}
    sprint_capacity_by_week: dict[tuple[int, date], float] = {}
    sprint_assignees_by_week: dict[tuple[int, date], set[int]] = {}
    for task in tasks:
        if not task.sprint_id or not task.assignee_user_id:
            continue
        task_start = task.start_date or task.due_date or range_start
        task_end = task.due_date or task.start_date or range_end
        for week in _weeks_between(max(range_start, task_start), min(range_end, task_end)):
            sprint_assignees_by_week.setdefault((task.sprint_id, week), set()).add(task.assignee_user_id)
    for sprint in sprint_rows:
        if not sprint.capacity_hours:
            continue
        for week in _weeks_between(max(range_start, sprint.start_date), min(range_end, sprint.end_date)):
            assignee_count = max(len(sprint_assignees_by_week.get((sprint.id, week), set())), 1)
            sprint_capacity_by_week[(sprint.id, week)] = float(sprint.capacity_hours) / assignee_count

    cells: dict[tuple[int, date], dict] = {}
    for user_id in user_ids:
        for week in weeks:
            capacity = capacity_by_user_week.get((user_id, week))
            cells[(user_id, week)] = {
                "week_start": week,
                "planned_hours": 0.0,
                "story_points": 0,
                "task_count": 0,
                "capacity_hours": capacity if capacity is not None else 40.0,
                "utilization_percent": 0.0,
                "status": "under",
                "tasks": [],
            }

    for task in tasks:
        user_id = task.assignee_user_id
        if not user_id:
            continue
        task_start = task.start_date or task.due_date or range_start
        task_end = task.due_date or task.start_date or range_end
        task_weeks = _weeks_between(max(range_start, task_start), min(range_end, task_end))
        if not task_weeks:
            task_weeks = [range_start]
        planned_hours = float(task.estimated_hours or task.remaining_estimate_hours or task.original_estimate_hours or (_task_points(task) * 6) or 0)
        hours_share = planned_hours / len(task_weeks) if task_weeks else planned_hours
        points_share = _task_points(task) / len(task_weeks) if task_weeks else _task_points(task)
        for week in task_weeks:
            cell = cells.setdefault((user_id, week), {
                "week_start": week,
                "planned_hours": 0.0,
                "story_points": 0,
                "task_count": 0,
                "capacity_hours": 40.0,
                "utilization_percent": 0.0,
                "status": "under",
                "tasks": [],
            })
            if task.sprint_id and (user_id, week) not in capacity_by_user_week:
                cell["capacity_hours"] = sprint_capacity_by_week.get((task.sprint_id, week), cell["capacity_hours"])
            cell["planned_hours"] += hours_share
            cell["story_points"] += points_share
            cell["task_count"] += 1
            cell["tasks"].append({
                "id": task.id,
                "task_key": task.task_key,
                "title": task.title,
                "project_id": task.project_id,
                "sprint_id": task.sprint_id,
                "status": task.status,
                "priority": task.priority,
                "start_date": _json_ready(task.start_date),
                "due_date": _json_ready(task.due_date),
                "planned_hours": round(hours_share, 2),
                "story_points": round(points_share, 2),
            })

    summary = {"over_capacity": 0, "near_capacity": 0, "under_capacity": 0}
    rows = []
    for user_id in sorted(user_ids, key=lambda uid: (_user_display_name(users_by_id.get(uid)) or "").lower()):
        row_cells = []
        totals = {"planned_hours": 0.0, "story_points": 0.0, "task_count": 0, "capacity_hours": 0.0}
        for week in weeks:
            cell = cells[(user_id, week)]
            load_value = cell["planned_hours"] if basis == "hours" else cell["story_points"] if basis == "story_points" else cell["task_count"]
            capacity = cell["capacity_hours"] or 0
            utilization = round((load_value / capacity) * 100, 1) if capacity else 0
            status_value = "over" if utilization > 100 else "near" if utilization >= 85 else "under"
            cell.update({
                "planned_hours": round(cell["planned_hours"], 2),
                "story_points": round(cell["story_points"], 2),
                "load_value": round(load_value, 2),
                "load_unit": "hours" if basis == "hours" else "points" if basis == "story_points" else "tasks",
                "utilization_percent": utilization,
                "status": status_value,
                "week_start": _json_ready(week),
            })
            summary[f"{status_value}_capacity"] += 1
            totals["planned_hours"] += cell["planned_hours"]
            totals["story_points"] += cell["story_points"]
            totals["task_count"] += cell["task_count"]
            totals["capacity_hours"] += capacity
            row_cells.append(cell)
        rows.append({
            "user_id": user_id,
            "user_name": _user_display_name(users_by_id.get(user_id)) or f"User {user_id}",
            "email": getattr(users_by_id.get(user_id), "email", None),
            "cells": row_cells,
            "totals": {
                "planned_hours": round(totals["planned_hours"], 2),
                "story_points": round(totals["story_points"], 2),
                "task_count": totals["task_count"],
                "capacity_hours": round(totals["capacity_hours"], 2),
                "utilization_percent": round(((totals["planned_hours"] if basis == "hours" else totals["story_points"] if basis == "story_points" else totals["task_count"]) / totals["capacity_hours"]) * 100, 1) if totals["capacity_hours"] else 0,
            },
        })

    return {
        "basis": basis,
        "from": _json_ready(range_start),
        "to": _json_ready(range_end),
        "weeks": [{"week_start": _json_ready(week), "label": f"{week.strftime('%b %d')}"} for week in weeks],
        "projects": [{"id": project.id, "name": project.name, "project_key": project.project_key} for project in projects],
        "sprints": [
            {"id": sprint.id, "project_id": sprint.project_id, "name": sprint.name, "status": sprint.status, "start_date": _json_ready(sprint.start_date), "end_date": _json_ready(sprint.end_date)}
            for sprint in sprint_rows
        ],
        "users": [{"id": user_id, "name": _user_display_name(users_by_id.get(user_id)) or f"User {user_id}"} for user_id in user_ids],
        "rows": rows,
        "summary": summary,
    }


@router.get("/dev-integrations")
def list_dev_integrations(
    projectId: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List repository integrations for accessible PMS projects without exposing secrets."""
    project_query = accessible_project_query(db, current_user)
    if projectId:
        get_project_for_action(db, projectId, current_user, "browse")
        project_query = project_query.filter(PMSProject.id == projectId)
    projects = project_query.all()
    projects_by_id = {project.id: project for project in projects}
    if not projects_by_id:
        return []
    integrations = db.query(PMSDevIntegration).filter(PMSDevIntegration.project_id.in_(projects_by_id)).order_by(PMSDevIntegration.created_at.desc()).all()
    return [_dev_integration_payload(item, projects_by_id.get(item.project_id)) for item in integrations]


@router.post("/dev-integrations", status_code=status.HTTP_201_CREATED)
def create_dev_integration(
    integration_in: DevIntegrationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update a GitHub/GitLab repository mapping for a PMS project."""
    provider = _normalize_dev_provider(integration_in.provider)
    project = get_project_for_action(db, integration_in.project_id, current_user, "manage_tasks")
    repo_owner = integration_in.repo_owner.strip()
    repo_name = integration_in.repo_name.strip()
    if not repo_owner or not repo_name:
        raise HTTPException(status_code=400, detail="Repository owner and name are required")
    integration = db.query(PMSDevIntegration).filter(
        PMSDevIntegration.project_id == project.id,
        PMSDevIntegration.provider == provider,
        func.lower(PMSDevIntegration.repo_owner) == repo_owner.lower(),
        func.lower(PMSDevIntegration.repo_name) == repo_name.lower(),
    ).first()
    if not integration:
        integration = PMSDevIntegration(
            organization_id=project.organization_id,
            project_id=project.id,
            provider=provider,
            repo_owner=repo_owner,
            repo_name=repo_name,
        )
    integration.is_active = integration_in.is_active
    if integration_in.access_token:
        integration.access_token_encrypted = _encrypt_dev_secret(integration_in.access_token)
    if integration_in.webhook_secret:
        integration.webhook_secret_encrypted = _encrypt_dev_secret(integration_in.webhook_secret)
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return _dev_integration_payload(integration, project)


@router.delete("/dev-integrations/{integration_id}")
def delete_dev_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a repository integration mapping."""
    integration = db.query(PMSDevIntegration).filter(PMSDevIntegration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Development integration not found")
    get_project_for_action(db, integration.project_id, current_user, "manage_tasks")
    db.delete(integration)
    db.commit()
    return {"message": "Development integration deleted"}


@router.get("/tasks/{task_id}/dev-links")
def list_task_dev_links(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List branches, commits, pull requests, and merge requests linked to a task."""
    get_task_project_for_action(db, task_id, current_user, "browse")
    links = db.query(PMSDevLink).filter(PMSDevLink.task_id == task_id).order_by(desc(PMSDevLink.updated_at), desc(PMSDevLink.created_at)).all()
    return [_dev_link_payload(item) for item in links]


@router.post("/dev-integrations/webhook/github")
async def github_dev_webhook(request: Request, db: Session = Depends(get_db)):
    """Ingest GitHub push and pull request events and link them to task keys."""
    raw_body = await request.body()
    payload = json.loads(raw_body.decode("utf-8") or "{}")
    repo = payload.get("repository") or {}
    owner = ((repo.get("owner") or {}).get("login") or (repo.get("owner") or {}).get("name") or "").strip()
    repo_name = (repo.get("name") or "").strip()
    integrations = _project_repo_integrations(db, "github", owner, repo_name)
    if not integrations:
        raise HTTPException(status_code=404, detail="GitHub repository integration not found")
    signature = request.headers.get("X-Hub-Signature-256")
    links: list[PMSDevLink] = []
    for integration in integrations:
        secret = _decrypt_dev_secret(integration.webhook_secret_encrypted)
        if not _github_signature_valid(raw_body, secret or "", signature):
            raise HTTPException(status_code=401, detail="Invalid GitHub webhook signature")
        links.extend(_process_dev_payload(db, integration, "github", payload, request.headers.get("X-GitHub-Event")))
    db.commit()
    return {"linked": len(links), "links": [_dev_link_payload(item) for item in links]}


@router.post("/dev-integrations/webhook/gitlab")
async def gitlab_dev_webhook(request: Request, db: Session = Depends(get_db)):
    """Ingest GitLab push and merge request events and link them to task keys."""
    raw_body = await request.body()
    payload = json.loads(raw_body.decode("utf-8") or "{}")
    project_data = payload.get("project") or {}
    path = project_data.get("path_with_namespace") or ""
    parts = path.split("/") if path else []
    owner = "/".join(parts[:-1]) if len(parts) > 1 else str(project_data.get("namespace") or "")
    repo_name = parts[-1] if parts else str(project_data.get("name") or "")
    integrations = _project_repo_integrations(db, "gitlab", owner, repo_name)
    if not integrations:
        raise HTTPException(status_code=404, detail="GitLab repository integration not found")
    token = request.headers.get("X-Gitlab-Token")
    links: list[PMSDevLink] = []
    for integration in integrations:
        secret = _decrypt_dev_secret(integration.webhook_secret_encrypted)
        if not secret or not token or not hmac.compare_digest(secret, token):
            raise HTTPException(status_code=401, detail="Invalid GitLab webhook token")
        links.extend(_process_dev_payload(db, integration, "gitlab", payload, request.headers.get("X-Gitlab-Event")))
    db.commit()
    return {"linked": len(links), "links": [_dev_link_payload(item) for item in links]}


# ============= RISK REGISTER =============
def _get_risk_for_action(db: Session, risk_id: int, current_user: User, action: str = "browse") -> tuple[PMSRisk, PMSProject]:
    risk = db.query(PMSRisk).filter(PMSRisk.id == risk_id, PMSRisk.deleted_at == None).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")
    project = get_project_for_action(db, risk.project_id, current_user, action)
    return risk, project


def _validate_risk_task(db: Session, task_id: int | None, project_id: int, current_user: User) -> None:
    if not task_id:
        return
    task, task_project = get_task_project_for_action(db, task_id, current_user, "browse")
    if task.project_id != project_id or task_project.id != project_id:
        raise HTTPException(status_code=400, detail="Linked task must belong to the risk project")


@router.get("/risks", response_model=list[PMSRiskResponse])
def list_risks(
    projectId: int = Query(None),
    status: str = Query(None),
    ownerId: int = Query(None),
    severity: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List project risks visible to the current user."""
    if projectId:
        get_project_for_action(db, projectId, current_user, "browse")
        project_ids = [projectId]
    else:
        project_ids = [row[0] for row in accessible_project_query(db, current_user).with_entities(PMSProject.id).all()]
    if not project_ids:
        return []

    query = db.query(PMSRisk).filter(PMSRisk.project_id.in_(project_ids), PMSRisk.deleted_at == None)
    if status:
        query = query.filter(PMSRisk.status == status)
    if ownerId:
        query = query.filter(PMSRisk.owner_user_id == ownerId)
    if severity:
        normalized = severity.lower()
        if normalized == "high":
            query = query.filter(PMSRisk.risk_score >= 15)
        elif normalized == "medium":
            query = query.filter(PMSRisk.risk_score >= 8, PMSRisk.risk_score < 15)
        elif normalized == "low":
            query = query.filter(PMSRisk.risk_score < 8)
    return query.order_by(desc(PMSRisk.risk_score), asc(PMSRisk.due_date), desc(PMSRisk.created_at)).all()


@router.post("/risks", response_model=PMSRiskResponse, status_code=status.HTTP_201_CREATED)
def create_risk(
    risk_in: PMSRiskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a risk in a project risk register."""
    project = get_project_for_action(db, risk_in.project_id, current_user, "manage_tasks")
    _validate_risk_task(db, risk_in.linked_task_id, project.id, current_user)
    risk = PMSRisk(
        organization_id=project.organization_id or organization_id_for(current_user),
        project_id=project.id,
        linked_task_id=risk_in.linked_task_id,
        title=risk_in.title.strip(),
        description=risk_in.description,
        category=risk_in.category,
        probability=risk_in.probability,
        impact=risk_in.impact,
        risk_score=_risk_score(risk_in.probability, risk_in.impact),
        status=risk_in.status,
        owner_user_id=risk_in.owner_user_id,
        mitigation_plan=risk_in.mitigation_plan,
        contingency_plan=risk_in.contingency_plan,
        due_date=risk_in.due_date,
    )
    db.add(risk)
    db.flush()
    _record_activity(
        db,
        project.id,
        current_user,
        "risk.created",
        "risk",
        risk.id,
        f"Created risk {risk.title}",
        task_id=risk.linked_task_id,
        metadata={"risk_score": risk.risk_score, "severity": _risk_severity(risk.risk_score)},
    )
    db.commit()
    db.refresh(risk)
    return risk


@router.patch("/risks/{risk_id}", response_model=PMSRiskResponse)
def update_risk(
    risk_id: int,
    risk_in: PMSRiskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a project risk."""
    risk, project = _get_risk_for_action(db, risk_id, current_user, "manage_tasks")
    update_data = risk_in.model_dump(exclude_unset=True)
    target_project_id = update_data.get("project_id", risk.project_id)
    if target_project_id != risk.project_id:
        project = get_project_for_action(db, target_project_id, current_user, "manage_tasks")
    _validate_risk_task(db, update_data.get("linked_task_id", risk.linked_task_id), target_project_id, current_user)

    for field, value in update_data.items():
        if field == "title" and isinstance(value, str):
            value = value.strip()
        setattr(risk, field, value)
    if "project_id" in update_data:
        risk.organization_id = project.organization_id or organization_id_for(current_user)
    if "probability" in update_data or "impact" in update_data:
        risk.risk_score = _risk_score(risk.probability, risk.impact)
    _record_activity(
        db,
        project.id,
        current_user,
        "risk.updated",
        "risk",
        risk.id,
        f"Updated risk {risk.title}",
        task_id=risk.linked_task_id,
        metadata=update_data,
    )
    db.commit()
    db.refresh(risk)
    return risk


@router.delete("/risks/{risk_id}")
def delete_risk(
    risk_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a project risk."""
    risk, project = _get_risk_for_action(db, risk_id, current_user, "manage_tasks")
    risk.deleted_at = datetime.utcnow()
    _record_activity(
        db,
        project.id,
        current_user,
        "risk.deleted",
        "risk",
        risk.id,
        f"Deleted risk {risk.title}",
        task_id=risk.linked_task_id,
    )
    db.commit()
    return {"message": "Risk deleted successfully"}


@router.get("/portfolio/summary")
def get_portfolio_summary(
    ownerId: int = Query(None),
    clientId: int = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return executive portfolio summary for projects visible to the user."""
    projects, tasks_by_project, sprints_by_project, milestones_by_project, risks_by_project, owners, clients = _portfolio_context(db, current_user, ownerId, clientId, status)
    today = date.today()
    project_payloads = [
        _portfolio_project_payload(project, owners.get(project.manager_user_id), clients.get(project.client_id), tasks_by_project.get(project.id, []), sprints_by_project.get(project.id, []), milestones_by_project.get(project.id, []), risks_by_project.get(project.id, []))
        for project in projects
    ]
    all_tasks = [task for tasks in tasks_by_project.values() for task in tasks]
    open_tasks = [task for task in all_tasks if task.status not in DONE_STATUSES]
    open_estimated_hours = sum(float(task.estimated_hours or task.remaining_estimate_hours or task.original_estimate_hours or 0) for task in open_tasks)
    active_assignees = {task.assignee_user_id for task in open_tasks if task.assignee_user_id}
    upcoming_milestones = [
        milestone
        for milestones in milestones_by_project.values()
        for milestone in milestones
        if milestone.due_date and today <= milestone.due_date <= today + timedelta(days=30) and milestone.status not in DONE_STATUSES
    ]
    health_counts: dict[str, int] = {}
    task_status_counts: dict[str, int] = {}
    for item in project_payloads:
        health_counts[item["health"]] = health_counts.get(item["health"], 0) + 1
    for task in all_tasks:
        task_status_counts[task.status] = task_status_counts.get(task.status, 0) + 1
    return {
        "total_projects": len(projects),
        "active_projects": len([project for project in projects if project.status not in {"Completed", "Archived", "Cancelled"}]),
        "overdue_projects": len([item for item in project_payloads if item["due_date"] and date.fromisoformat(item["due_date"]) < today and item["progress_percent"] < 100]),
        "at_risk_projects": len([item for item in project_payloads if item["health"] in {"At Risk", "Blocked"}]),
        "completed_projects": len([project for project in projects if project.status == "Completed" or int(project.progress_percent or 0) >= 100]),
        "total_open_tasks": len(open_tasks),
        "team_workload_summary": {
            "open_estimated_hours": round(open_estimated_hours, 2),
            "active_assignees": len(active_assignees),
            "avg_open_hours_per_assignee": round(open_estimated_hours / len(active_assignees), 2) if active_assignees else 0,
        },
        "upcoming_milestones": len(upcoming_milestones),
        "health_distribution": [{"name": key, "value": value} for key, value in sorted(health_counts.items())],
        "tasks_by_status": [{"name": key, "value": value} for key, value in sorted(task_status_counts.items())],
        "filters": {
            "owners": [{"id": user.id, "name": _user_display_name(user)} for user in owners.values()],
            "clients": [{"id": client.id, "name": client.name} for client in clients.values()],
            "statuses": sorted({project.status for project in projects if project.status}),
            "health": sorted({item["health"] for item in project_payloads}),
        },
    }


@router.get("/portfolio/projects")
def get_portfolio_projects(
    ownerId: int = Query(None),
    clientId: int = Query(None),
    status: str = Query(None),
    health: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return portfolio project table rows for accessible projects."""
    projects, tasks_by_project, sprints_by_project, milestones_by_project, risks_by_project, owners, clients = _portfolio_context(db, current_user, ownerId, clientId, status)
    rows = [
        _portfolio_project_payload(project, owners.get(project.manager_user_id), clients.get(project.client_id), tasks_by_project.get(project.id, []), sprints_by_project.get(project.id, []), milestones_by_project.get(project.id, []), risks_by_project.get(project.id, []))
        for project in projects
    ]
    if health:
        rows = [row for row in rows if row["health"] == health]
    return {"items": rows}


@router.get("/portfolio/health-trend")
def get_portfolio_health_trend(
    ownerId: int = Query(None),
    clientId: int = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return lightweight portfolio trend data from current accessible project state."""
    projects, tasks_by_project, sprints_by_project, milestones_by_project, risks_by_project, owners, clients = _portfolio_context(db, current_user, ownerId, clientId, status)
    today = date.today()
    month_starts = []
    cursor = date(today.year, today.month, 1)
    for index in range(5, -1, -1):
        month = cursor.month - index
        year = cursor.year
        while month <= 0:
            month += 12
            year -= 1
        month_starts.append(date(year, month, 1))
    payloads = [
        _portfolio_project_payload(project, owners.get(project.manager_user_id), clients.get(project.client_id), tasks_by_project.get(project.id, []), sprints_by_project.get(project.id, []), milestones_by_project.get(project.id, []), risks_by_project.get(project.id, []))
        for project in projects
    ]
    trend = []
    for month_start in month_starts:
        next_month = date(month_start.year + (1 if month_start.month == 12 else 0), 1 if month_start.month == 12 else month_start.month + 1, 1)
        active_rows = [
            row for row in payloads
            if (not row["start_date"] or date.fromisoformat(row["start_date"]) < next_month)
            and (not row["due_date"] or date.fromisoformat(row["due_date"]) >= month_start)
        ]
        month_tasks = [
            task
            for tasks in tasks_by_project.values()
            for task in tasks
            if task.created_at and task.created_at.date() < next_month and (not task.due_date or task.due_date >= month_start)
        ]
        trend.append({
            "month": month_start.strftime("%b %Y"),
            "project_count": len(active_rows),
            "at_risk": len([row for row in active_rows if row["health"] in {"At Risk", "Blocked"}]),
            "avg_progress": round(sum(row["progress_percent"] for row in active_rows) / len(active_rows), 1) if active_rows else 0,
            "open_tasks": len([task for task in month_tasks if task.status not in DONE_STATUSES]),
            "overdue_tasks": len([task for task in month_tasks if task.status not in DONE_STATUSES and task.due_date and task.due_date < today]),
        })
    return {"items": trend}


# ============= DASHBOARD =============
@router.get("/dashboard/{project_id}")
def get_project_dashboard(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get project dashboard metrics."""
    project = get_project_for_action(db, project_id, current_user, "browse")
    
    # Calculate metrics
    total_tasks = db.query(PMSTask).filter(
        PMSTask.project_id == project_id,
        PMSTask.deleted_at == None
    ).count()
    
    completed_tasks = db.query(PMSTask).filter(
        PMSTask.project_id == project_id,
        PMSTask.status == "Done",
        PMSTask.deleted_at == None
    ).count()
    
    overdue_tasks = db.query(PMSTask).filter(
        PMSTask.project_id == project_id,
        PMSTask.status != "Done",
        PMSTask.due_date < __import__('datetime').date.today(),
        PMSTask.deleted_at == None
    ).count()

    open_high_risks = db.query(PMSRisk).filter(
        PMSRisk.project_id == project_id,
        PMSRisk.deleted_at == None,
        PMSRisk.status.in_(["open", "mitigating"]),
        PMSRisk.risk_score >= 15,
    ).count()
    
    metrics = {
        "total_projects": 1,
        "active_projects": 1 if project.status == "Active" else 0,
        "completed_projects": 1 if project.status == "Completed" else 0,
        "overdue_projects": 1 if project.due_date and project.due_date < __import__('datetime').date.today() else 0,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "overdue_tasks": overdue_tasks,
        "high_risks": open_high_risks,
        "pending_approvals": db.query(PMSClientApproval).filter(
            PMSClientApproval.project_id == project_id,
            PMSClientApproval.status == "Pending"
        ).count(),
        "team_utilization": 0.0,
        "hours_logged_this_week": 0,
        "upcoming_milestones": db.query(PMSMilestone).filter(
            PMSMilestone.project_id == project_id,
            PMSMilestone.status != "Completed"
        ).count(),
        "recent_activities": 0,
    }
    
    return {
        "project": project,
        "metrics": metrics
    }
