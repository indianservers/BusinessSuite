"""Opt-in project transition policies stored in the existing workspace registry."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.core.rich_text import rich_text_plain
from .access import get_project_for_action, revalidate_project_actor
from .models import PMSProject, PMSWorkspace, PMSWorkspaceEntry

router = APIRouter()
Status = Literal["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done"]
RequiredField = Literal["assignee", "due_date", "description"]


class Transition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Status
    target: Status
    required_fields: list[RequiredField] = Field(default_factory=list, max_length=3)
    approval_user_ids: list[int] = Field(default_factory=list, max_length=10)


class Scheme(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    enabled: bool = False
    transitions: list[Transition] = Field(default_factory=list, max_length=30)
    work_type_transitions: dict[str, list[Transition]] = Field(default_factory=dict, max_length=60)

    @model_validator(mode="after")
    def valid_graph(self):
        for rules in [self.transitions, *self.work_type_transitions.values()]:
            edges = [(rule.source, rule.target) for rule in rules]
            if len(edges) > 30 or len(edges) != len(set(edges)) or any(a == b for a, b in edges):
                raise ValueError("Transitions must be unique, change status and number at most 30")
            if self.enabled and not edges:
                raise ValueError("An enabled workflow needs at least one transition per configured scope")
            for rule in rules:
                if len(set(rule.approval_user_ids)) != len(rule.approval_user_ids) or any(uid <= 0 for uid in rule.approval_user_ids):
                    raise ValueError("Approval routes need unique, positive user IDs")
        return self


def entry(db, project):
    if not project.workspace_id:
        return None
    # Hex project keys fit the existing VARCHAR(12) kind for integer project IDs.
    return db.query(PMSWorkspaceEntry).filter_by(
        workspace_id=project.workspace_id, kind=f"wf{project.id:x}"
    ).populate_existing().first()


@router.get("/projects/{project_id}/workflow-scheme")
def read_scheme(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_project_for_action(db, project_id, user)
    row = entry(db, project)
    return json.loads(row.body) if row else Scheme(revision=0).model_dump()


@router.put("/projects/{project_id}/workflow-scheme")
def save_scheme(project_id: int, data: Scheme, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_project_for_action(db, project_id, user, "edit_project")
    if not project.workspace_id:
        raise HTTPException(422, "Move this project into a workspace before configuring its workflow")
    # Serializes first publication as well as edits, without adding a parallel table.
    db.query(PMSWorkspace).filter_by(id=project.workspace_id).with_for_update().one()
    revalidate_project_actor(db, project, user, "edit_project")
    from .task_types import validate_task_type
    from .automations import _eligible_assignee
    for name in data.work_type_transitions:
        validate_task_type(db, name, project.organization_id)
    for rules in [data.transitions, *data.work_type_transitions.values()]:
        for rule in rules:
            for uid in rule.approval_user_ids:
                reviewer = db.get(User, uid)
                from .access import can_access_project
                if not _eligible_assignee(db, project.workspace_id, uid) or not can_access_project(db, project, reviewer, "manage_tasks"):
                    raise HTTPException(422, "Approvers need active task-management access to this project")
    row = entry(db, project)
    previous = json.loads(row.body) if row else Scheme(revision=0).model_dump()
    if previous["revision"] != data.revision:
        raise HTTPException(409, "Workflow changed. Reload before saving")
    payload = {**data.model_dump(), "revision": data.revision + 1}
    if row:
        row.body = json.dumps(payload)
    else:
        db.add(PMSWorkspaceEntry(workspace_id=project.workspace_id, author_id=user.id,
                                 kind=f"wf{project.id:x}", body=json.dumps(payload)))
    from .api.router import _record_activity
    _record_activity(db, project.id, user, "workflow.updated", "project", project.id,
                     "Updated project transition policy", metadata={"before": previous, "after": payload})
    db.commit()
    return payload


def current_scheme(db, task):
    row = entry(db, db.get(PMSProject, task.project_id))
    return Scheme.model_validate_json(row.body) if row else Scheme(revision=0)


def guard_work_type_change(db, task, changes):
    if changes.get("work_type") and changes["work_type"] != task.work_type:
        if current_scheme(db, task).enabled and (task.status not in {"Backlog", "To Do"} or changes.get("status", task.status) != task.status):
            raise HTTPException(409, "Change work type separately while the task is in Backlog or To Do")


def transition_for(scheme, task, status):
    rules = scheme.work_type_transitions.get(task.work_type, scheme.transitions)
    return next((r for r in rules if r.source == task.status and r.target == status), None)


def guard_scheme(db, task, status, changes=None, *, check_approval=True):
    if status == task.status:
        return
    scheme = current_scheme(db, task)
    if not scheme.enabled:
        return
    guard_work_type_change(db, task, changes or {})
    rule = transition_for(scheme, task, status)
    if rule is None:
        raise HTTPException(409, f"Project workflow does not allow {task.status} → {status}")
    changes = changes or {}
    assignees = changes.get("assignee_user_ids", task.assignee_user_ids)
    if "assignee_user_id" in changes and "assignee_user_ids" not in changes:
        assignees = [changes["assignee_user_id"]] if changes["assignee_user_id"] else []
    values = {"assignee": assignees, "due_date": changes.get("due_date", task.due_date),
              "description": rich_text_plain(changes.get("description", task.description))}
    missing = [name for name in rule.required_fields if not values[name] or isinstance(values[name], str) and not values[name].strip()]
    if missing:
        raise HTTPException(409, "This transition requires: " + ", ".join(missing))
    if rule.approval_user_ids and check_approval:
        from .transition_approvals import consume_approval
        consume_approval(db, task, status, scheme, rule, changes)
