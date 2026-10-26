from app.core.rich_text import rich_text_type
"""Persisted workspace goals, task templates and authenticated intake forms."""
import json
import secrets
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import get_project_for_action
from .automations import apply_task_rules
from .models import PMSActivity, PMSBoard, PMSBoardColumn, PMSProject, PMSTask, PMSWorkspaceEntry
from .workspaces import workspace_member

router = APIRouter()
KINDS = ("lib_goal", "lib_template", "lib_intake")


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["goal", "template", "intake"]
    name: str = Field(min_length=1, max_length=120)
    project_id: int = Field(gt=0)
    description: rich_text_type(4000, 0) = Field(default="")
    task_ids: list[int] = Field(default_factory=list, max_length=100)
    task_titles: list[str] = Field(default_factory=list, max_length=20)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Name is required")
        return value.strip()


class ApplyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    title: str = Field(default="", max_length=220)
    description: rich_text_type(10000, 0) = Field(default="")


class ToolToggle(BaseModel):
    enabled: bool


def payload(db, row):
    data = json.loads(row.body)
    result = {**data, "id": row.id}
    if data["kind"] == "goal":
        tasks = db.query(PMSTask).filter(PMSTask.id.in_(data["task_ids"]), PMSTask.project_id == data["project_id"], PMSTask.deleted_at == None).all()
        done = sum(task.status in ("Done", "Completed", "Closed") for task in tasks)
        result.update(total=len(tasks), completed=done, progress=round(done / len(tasks) * 100) if tasks else 0)
    return result


@router.get("/workspaces/{workspace_id}/tools")
def list_tools(workspace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user)
    rows = db.query(PMSWorkspaceEntry).filter(PMSWorkspaceEntry.workspace_id == workspace_id, PMSWorkspaceEntry.kind.in_(KINDS)).order_by(PMSWorkspaceEntry.id.desc()).all()
    return [payload(db, row) for row in rows]


@router.post("/workspaces/{workspace_id}/tools", status_code=201)
def create_tool(workspace_id: int, data: ToolInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user, True)
    project = get_project_for_action(db, data.project_id, user)
    if project.workspace_id != workspace_id:
        raise HTTPException(404, "Project not found in this workspace")
    if data.kind == "goal":
        ids = set(data.task_ids)
        count = db.query(PMSTask).filter(PMSTask.id.in_(ids), PMSTask.project_id == project.id, PMSTask.deleted_at == None).count()
        if not ids or count != len(ids):
            raise HTTPException(422, "Choose existing tasks from this project")
    if data.kind == "template":
        if not data.task_titles or any(not title.strip() or len(title.strip()) > 220 for title in data.task_titles):
            raise HTTPException(422, "Templates require 1–20 task titles, each up to 220 characters")
        data.task_titles = [title.strip() for title in data.task_titles]
    if db.query(PMSWorkspaceEntry).filter(PMSWorkspaceEntry.workspace_id == workspace_id, PMSWorkspaceEntry.kind.in_(KINDS)).count() >= 100:
        raise HTTPException(422, "This workspace already has 100 tools")
    row = PMSWorkspaceEntry(workspace_id=workspace_id, author_id=user.id, kind="lib_" + data.kind, body=data.model_dump_json())
    db.add(row)
    db.commit()
    db.refresh(row)
    from .api.router import _broadcast_realtime
    _broadcast_realtime(user, "project.updated", project_id=project.id, message=f"Saved workspace {data.kind}: {data.name}")
    return payload(db, row)


def tool_row(db, workspace_id, tool_id):
    row = db.query(PMSWorkspaceEntry).filter(PMSWorkspaceEntry.id == tool_id, PMSWorkspaceEntry.workspace_id == workspace_id, PMSWorkspaceEntry.kind.in_(KINDS)).with_for_update().first()
    if not row:
        raise HTTPException(404, "Tool not found")
    return row


@router.patch("/workspaces/{workspace_id}/tools/{tool_id}")
def toggle_tool(workspace_id: int, tool_id: int, data: ToolToggle, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user, True)
    row = tool_row(db, workspace_id, tool_id)
    value = json.loads(row.body)
    value["enabled"] = data.enabled
    row.body = json.dumps(value)
    db.commit()
    from .api.router import _broadcast_realtime
    _broadcast_realtime(user, "project.updated", project_id=value["project_id"], message=f"Updated workspace {value['kind']}: {value['name']}")
    return payload(db, row)


@router.post("/workspaces/{workspace_id}/tools/{tool_id}/apply")
def apply_tool(workspace_id: int, tool_id: int, data: ApplyInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, membership = workspace_member(db, workspace_id, user)
    if membership.role == "Guest":
        raise HTTPException(403, "Guests have read-only access")
    row = tool_row(db, workspace_id, tool_id)
    tool = json.loads(row.body)
    project = get_project_for_action(db, tool["project_id"], user, "manage_tasks")
    if project.workspace_id != workspace_id:
        raise HTTPException(404, "Project not found in this workspace")
    key = f"{tool_id}:{user.id}:{data.request_id}"
    previous = db.query(PMSWorkspaceEntry).filter_by(workspace_id=workspace_id, kind="lib_run").all()
    for run in previous:
        saved = json.loads(run.body)
        if saved["key"] == key:
            return {"task_ids": saved["task_ids"], "replayed": True}
    if not tool["enabled"] or tool["kind"] == "goal":
        raise HTTPException(422, "This tool cannot create tasks")
    titles = tool["task_titles"] if tool["kind"] == "template" else [data.title.strip()]
    if any(not title for title in titles):
        raise HTTPException(422, "A request title is required")
    board = db.query(PMSBoard).filter_by(project_id=project.id).order_by(PMSBoard.id).first()
    if not board:
        board = PMSBoard(project_id=project.id, name="Default Board", board_type="Kanban")
        db.add(board)
        db.flush()
        for index, (name, key_name) in enumerate([( "Backlog", "BACKLOG"), ("To Do", "TODO"), ("In Progress", "IN_PROGRESS"), ("In Review", "IN_REVIEW"), ("Done", "DONE")]):
            db.add(PMSBoardColumn(board_id=board.id, name=name, status_key=key_name, position=index))
        db.flush()
    column = db.query(PMSBoardColumn).filter_by(board_id=board.id, status_key="TODO").first()
    if not column:
        column = PMSBoardColumn(board_id=board.id, name="To Do", status_key="TODO", position=1)
        db.add(column)
        db.flush()
    position = db.query(PMSTask).filter_by(project_id=project.id).count()
    ids = []
    for index, title in enumerate(titles):
        task = PMSTask(project_id=project.id, board_id=board.id, column_id=column.id, task_key="REQ-" + secrets.token_hex(5).upper(), title=title, description=data.description or tool["description"], reporter_user_id=user.id, status="To Do", priority="Medium", position=position + index, rank=position + index + 1)
        db.add(task)
        db.flush()
        apply_task_rules(db, task, project, user, "task.created")
        ids.append(task.id)
        db.add(PMSActivity(project_id=project.id, task_id=task.id, actor_user_id=user.id, action="task.created", entity_type="task", entity_id=task.id, summary=f'Created from {tool["kind"]}: {tool["name"]}'[:300]))
    db.add(PMSWorkspaceEntry(workspace_id=workspace_id, author_id=user.id, kind="lib_run", body=json.dumps({"key": key, "task_ids": ids})))
    db.commit()
    from .api.router import _broadcast_realtime
    _broadcast_realtime(user, "task.created", project_id=project.id, task_id=ids[0], message=f"Created {len(ids)} tasks from {tool['name']}")
    return {"task_ids": ids, "replayed": False}
