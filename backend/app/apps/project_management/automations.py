"""Workspace-scoped, deterministic task automation. No scripts or external calls."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSActivity, PMSProject, PMSWorkspaceEntry, PMSWorkspaceMember

router = APIRouter()


class RuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    project_id: int = Field(gt=0)
    trigger: Literal["task.created", "task.status_changed"]
    status: Literal["", "To Do", "In Progress", "In Review", "Blocked", "Done"] = ""
    action: Literal["set_priority", "assign_user"]
    priority: Literal["Low", "Medium", "High", "Urgent"] = "High"
    assignee_id: int | None = None
    enabled: bool = True


class ToggleInput(BaseModel):
    enabled: bool


def _manage(db, workspace_id, user):
    from .workspaces import workspace_member
    return workspace_member(db, workspace_id, user, True)


def _payload(row):
    return {**json.loads(row.body), "id": row.id, "created_at": row.created_at}


@router.get("/workspaces/{workspace_id}/automations")
def list_rules(workspace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, workspace_id, user)
    return [_payload(row) for row in db.query(PMSWorkspaceEntry).filter_by(workspace_id=workspace_id, kind="auto_rule").order_by(PMSWorkspaceEntry.id.desc()).all()]


@router.post("/workspaces/{workspace_id}/automations", status_code=201)
def create_rule(workspace_id: int, data: RuleInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, workspace_id, user)
    if not data.name.strip():
        raise HTTPException(422, "Rule name is required")
    if not db.query(PMSProject).filter_by(id=data.project_id, workspace_id=workspace_id).first():
        raise HTTPException(404, "Project not found in this workspace")
    if data.action == "assign_user" and not _eligible_assignee(db, workspace_id, data.assignee_id):
        raise HTTPException(422, "Choose an active workspace collaborator")
    if db.query(PMSWorkspaceEntry).filter_by(workspace_id=workspace_id, kind="auto_rule").count() >= 100:
        raise HTTPException(422, "This workspace already has 100 rules")
    row = PMSWorkspaceEntry(workspace_id=workspace_id, author_id=user.id, kind="auto_rule", body=data.model_dump_json())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _payload(row)


@router.patch("/workspaces/{workspace_id}/automations/{rule_id}")
def toggle_rule(workspace_id: int, rule_id: int, data: ToggleInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, workspace_id, user)
    row = db.query(PMSWorkspaceEntry).filter_by(id=rule_id, workspace_id=workspace_id, kind="auto_rule").with_for_update().first()
    if not row:
        raise HTTPException(404, "Rule not found")
    rule = json.loads(row.body)
    rule["enabled"] = data.enabled
    row.body = json.dumps(rule)
    db.commit()
    return _payload(row)


@router.put("/workspaces/{workspace_id}/automations/{rule_id}")
def edit_rule(workspace_id: int, rule_id: int, data: RuleInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, workspace_id, user)
    row = db.query(PMSWorkspaceEntry).filter_by(id=rule_id, workspace_id=workspace_id, kind="auto_rule").with_for_update().first()
    if not row:
        raise HTTPException(404, "Rule not found")
    if not data.name.strip():
        raise HTTPException(422, "Rule name is required")
    if not db.query(PMSProject).filter_by(id=data.project_id, workspace_id=workspace_id, deleted_at=None).first():
        raise HTTPException(404, "Project not found in this workspace")
    if data.action == "assign_user" and not _eligible_assignee(db, workspace_id, data.assignee_id):
        raise HTTPException(422, "Choose an active workspace collaborator")
    row.body = data.model_dump_json()
    db.commit()
    return _payload(row)


@router.get("/workspaces/{workspace_id}/automation-runs")
def list_runs(workspace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, workspace_id, user)
    rows = db.query(PMSActivity).join(PMSProject, PMSProject.id == PMSActivity.project_id).filter(PMSProject.workspace_id == workspace_id, PMSActivity.action.like("automation.%")).order_by(PMSActivity.id.desc()).limit(50).all()
    return [{"id": row.id, "summary": row.summary, "task_id": row.task_id, "action": row.action, "created_at": row.created_at} for row in rows]


def _eligible_assignee(db, workspace_id, user_id):
    return user_id and db.query(PMSWorkspaceMember).join(User, User.id == PMSWorkspaceMember.user_id).filter(PMSWorkspaceMember.workspace_id == workspace_id, PMSWorkspaceMember.user_id == user_id, PMSWorkspaceMember.role != "Guest", User.is_active == True).first()


def apply_task_rules(db, task, project, actor, trigger):
    """Apply each matching rule once in the task transaction; never recurse."""
    if not project.workspace_id:
        return
    rows = db.query(PMSWorkspaceEntry).filter_by(workspace_id=project.workspace_id, kind="auto_rule").order_by(PMSWorkspaceEntry.id).limit(100).all()
    for row in rows:
        rule = json.loads(row.body)
        if not rule.get("enabled") or rule["project_id"] != project.id or rule["trigger"] != trigger or (rule.get("status") and rule["status"] != task.status):
            continue
        skipped = False
        if rule["action"] == "set_priority":
            if task.priority == rule["priority"]:
                continue
            task.priority = rule["priority"]
        else:
            target = rule.get("assignee_id")
            if not _eligible_assignee(db, project.workspace_id, target):
                skipped = True
            elif target in task.assignee_user_ids:
                continue
            else:
                task.assignee_user_ids = sorted(set(task.assignee_user_ids + [target]))
                task.assignee_user_id = task.assignee_user_id or target
        db.add(PMSActivity(project_id=project.id, task_id=task.id, actor_user_id=actor.id, action="automation.skipped" if skipped else "automation.executed", entity_type="automation", entity_id=row.id, summary=f'{rule["name"]}: {"assignee no longer eligible" if skipped else rule["action"]} on {task.task_key}'[:300], metadata_json=json.dumps({"rule_id": row.id, "trigger": trigger})))
