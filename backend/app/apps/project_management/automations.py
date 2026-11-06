"""Workspace-scoped, deterministic task automation. No scripts or external calls."""
import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSActivity, PMSProject, PMSWorkspaceEntry, PMSWorkspaceMember

router = APIRouter()


class RuleSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    at: str = Field(default="09:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    due_offset_days: int = Field(default=0, ge=-365, le=365)

    @model_validator(mode="after")
    def valid_zone(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose an IANA timezone") from None
        return self


class RuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    project_id: int = Field(gt=0)
    trigger: Literal["task.created", "task.status_changed", "schedule.daily", "task.due_date"]
    status: Literal["", "To Do", "In Progress", "In Review", "Blocked", "Done"] = ""
    action: Literal["set_priority", "assign_user"]
    priority: Literal["Low", "Medium", "High", "Urgent"] = "High"
    assignee_id: int | None = None
    enabled: bool = True
    conditions: dict | None = None
    schedule: RuleSchedule | None = None

    @model_validator(mode="after")
    def validate_conditions(self):
        timed = self.trigger in {"schedule.daily", "task.due_date"}
        if timed != (self.schedule is not None):
            raise ValueError("Time-based triggers require a schedule; event triggers do not use one")
        if self.trigger == "schedule.daily" and self.schedule.due_offset_days:
            raise ValueError("Due-date offset applies only to due-date triggers")
        if self.conditions is None:
            return self
        from app.shared.runtime import validate_condition
        validate_condition(self.conditions)
        remaining = [self.conditions]
        count = 0
        while remaining:
            node = remaining.pop()
            count += 1
            if count > 40:
                raise ValueError("Use at most 40 condition nodes")
            if "all" in node or "any" in node:
                remaining.extend(node.get("all", node.get("any")))
                continue
            field, operator, value = node["field"], node.get("operator", "equals"), node.get("value")
            if set(node) - {"field", "operator", "value"}:
                raise ValueError("Unsupported condition fields")
            if field not in {"status", "priority", "work_type", "title", "due_date", "assignee_user_id"}:
                raise ValueError("Choose a supported task condition field")
            if operator not in {"equals", "not_equals", "contains", "in", "not_in", "is_empty", "is_not_empty", "date_before", "date_after"}:
                raise ValueError("Choose a supported task condition operator")
            if operator in {"date_before", "date_after"} and field != "due_date":
                raise ValueError("Date comparisons require a due date")
            if operator in {"in", "not_in"}:
                if not isinstance(value, list) or len(value) > 30 or any(not isinstance(v, (str, int)) or isinstance(v, bool) for v in value):
                    raise ValueError("Membership conditions need a list of up to 30 values")
            elif operator not in {"is_empty", "is_not_empty"} and (not isinstance(value, (str, int)) or isinstance(value, bool)):
                raise ValueError("Condition value must be text or a user ID")
            if len(json.dumps(node)) > 2000:
                raise ValueError("Condition value is too long")
        return self


class ToggleInput(BaseModel):
    enabled: bool


def _manage(db, workspace_id, user):
    from .workspaces import workspace_member
    return workspace_member(db, workspace_id, user, True)


def _payload(row):
    return {**{k: v for k, v in json.loads(row.body).items() if not k.startswith("_")}, "id": row.id, "created_at": row.created_at}


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
    revision = int(json.loads(row.body).get("_revision", 1)) + 1
    row.body = json.dumps({**data.model_dump(mode="json"), "_revision": revision})
    db.commit()
    return _payload(row)


@router.get("/workspaces/{workspace_id}/automation-runs")
def list_runs(workspace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, workspace_id, user)
    rows = db.query(PMSActivity).join(PMSProject, PMSProject.id == PMSActivity.project_id).filter(PMSProject.workspace_id == workspace_id, PMSActivity.action.like("automation.%")).order_by(PMSActivity.id.desc()).limit(50).all()
    return [{"id": row.id, "summary": row.summary, "task_id": row.task_id, "action": row.action, "created_at": row.created_at} for row in rows]


def _eligible_assignee(db, workspace_id, user_id):
    from .access import module_identity_allowed
    from .models import PMSWorkspace
    target = db.get(User, user_id) if user_id else None
    workspace = db.get(PMSWorkspace, workspace_id)
    if not target or not workspace or not module_identity_allowed(db, target, workspace.organization_id or 1):
        return False
    return db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.workspace_id == workspace_id, PMSWorkspaceMember.user_id == user_id, PMSWorkspaceMember.role != "Guest").first()


def apply_task_rules(db, task, project, actor, trigger):
    """Apply each matching rule once in the task transaction; never recurse."""
    if not project.workspace_id:
        return
    rows = db.query(PMSWorkspaceEntry).filter_by(workspace_id=project.workspace_id, kind="auto_rule").order_by(PMSWorkspaceEntry.id).limit(100).all()
    for row in rows:
        rule = json.loads(row.body)
        if not rule.get("enabled") or rule["project_id"] != project.id or rule["trigger"] != trigger or not _matches(rule, task):
            continue
        _apply_rule(db, row, rule, task, project, actor)


def _matches(rule, task):
    if rule.get("status") and rule["status"] != task.status:
        return False
    if not rule.get("conditions"):
        return True
    from app.shared.runtime import condition
    values = {key: getattr(task, key) for key in ("status", "priority", "work_type", "title", "assignee_user_id")}
    values["due_date"] = task.due_date.isoformat() if task.due_date else None
    return condition(rule["conditions"], values)


def _apply_rule(db, row, rule, task, project, actor):
    """Shared action path for event and clock triggers. Return False on revoked assignment."""
    skipped = False
    if rule["action"] == "set_priority":
        if task.priority == rule["priority"]:
            return True
        task.priority = rule["priority"]
    else:
        target = rule.get("assignee_id")
        if not _eligible_assignee(db, project.workspace_id, target):
            skipped = True
        elif target in task.assignee_user_ids:
            return True
        else:
            task.assignee_user_ids = sorted(set(task.assignee_user_ids + [target]))
            task.assignee_user_id = task.assignee_user_id or target
    db.add(PMSActivity(project_id=project.id, task_id=task.id, actor_user_id=actor.id, action="automation.skipped" if skipped else "automation.executed", entity_type="automation", entity_id=row.id, summary=f'{rule["name"]}: {"assignee no longer eligible" if skipped else rule["action"]} on {task.task_key}'[:300], metadata_json=json.dumps({"rule_id": row.id, "trigger": rule["trigger"]})))
    return not skipped
