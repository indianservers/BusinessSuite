"""Versioned workspace form builder and transactional task intake."""
import csv
import io
import json
import math
import re
from datetime import date, datetime, timezone, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.audit_context import set_audit_entity
from app.models.user import User
from .access import get_project_for_action
from .automations import apply_task_rules
from .models import PMSWorkspaceEntry, PMSWorkspaceMember, PMSTask, PMSBoard, PMSBoardColumn, PMSActivity
from .workspaces import workspace_member

router = APIRouter()
FieldType = Literal["text", "textarea", "email", "phone", "url", "number", "date", "select", "radio", "multiselect", "checkbox", "rating", "section"]

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Condition(Strict):
    field: str
    operator: Literal["equals", "not_equals", "contains", "not_empty"] = "equals"
    value: str = Field(default="", max_length=500)

class Question(Strict):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_\-]{0,59}$")
    type: FieldType
    label: str = Field(min_length=1, max_length=160)
    help: str = Field(default="", max_length=500)
    placeholder: str = Field(default="", max_length=160)
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=50)
    min: float | None = None
    max: float | None = None
    condition: Condition | None = None

class Workflow(Strict):
    enabled: bool = False
    project_id: int | None = Field(default=None, gt=0)
    title_field: str = ""
    priority: Literal["Low", "Medium", "High", "Urgent"] = "Medium"
    assignee_id: int | None = Field(default=None, gt=0)
    due_days: int | None = Field(default=None, ge=0, le=365)

class Definition(Strict):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    submit_label: str = Field(default="Submit response", min_length=1, max_length=60)
    success_message: str = Field(default="Thank you. Your response has been saved.", min_length=1, max_length=500)
    accent: str = Field(default="#7c3aed", pattern=r"^#[0-9a-fA-F]{6}$")
    fields: list[Question] = Field(min_length=1, max_length=60)
    workflow: Workflow = Field(default_factory=Workflow)

    @model_validator(mode="after")
    def valid(self):
        if not self.name.strip():
            raise ValueError("Form name is required")
        seen = set()
        for f in self.fields:
            if not f.label.strip() or f.id in seen:
                raise ValueError("Questions need unique IDs and nonempty labels")
            if f.condition and f.condition.field not in seen:
                raise ValueError("Conditions must reference an earlier question")
            if f.type in {"select", "radio", "multiselect"} and (not f.options or any(not x.strip() or len(x) > 160 for x in f.options) or len(set(f.options)) != len(f.options)):
                raise ValueError("Choice fields need unique nonempty options, up to 160 characters")
            if any(v is not None and not math.isfinite(v) for v in [f.min, f.max]) or (f.min is not None and f.max is not None and f.min > f.max):
                raise ValueError("Invalid numeric range")
            seen.add(f.id)
        if self.workflow.enabled and (not self.workflow.project_id or not any(f.id == self.workflow.title_field and f.type == "text" and f.required and not f.condition for f in self.fields)):
            raise ValueError("Task workflows require a project and an unconditional required text title")
        if len(self.model_dump_json()) > 200000:
            raise ValueError("Form definition limit: 200 KB")
        return self

class Save(Strict):
    revision: int = Field(ge=0)
    definition: Definition
    publish: bool = False
    close: bool = False

class Submission(Strict):
    request_id: UUID
    version: int = Field(gt=0)
    answers: dict[str, str | list[str] | bool | int | float | None] = Field(default_factory=dict, max_length=60)


def row_for(db, wid, fid):
    row = db.query(PMSWorkspaceEntry).filter_by(workspace_id=wid, id=fid, kind="form_v2").with_for_update().first()
    if not row:
        raise HTTPException(404, "Form not found")
    return row


def output(row, admin):
    data = json.loads(row.body)
    if not admin:
        return {"id": row.id, "version": data["version"], "open": data["open"], "definition": data["published"]}
    return {"id": row.id, **data}


def validate_workflow(db, wid, definition, user):
    w = definition.workflow
    if not w.enabled:
        return
    project = get_project_for_action(db, w.project_id, user, "manage_tasks")
    if project.workspace_id != wid:
        raise HTTPException(422, "Workflow project must belong to this workspace")
    if w.assignee_id and not db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=w.assignee_id).filter(PMSWorkspaceMember.role != "Guest").first():
        raise HTTPException(422, "Assignee must be an active workspace member")


@router.get("/workspaces/{wid}/forms")
def list_forms(wid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = workspace_member(db, wid, user)
    admin = member.role in {"Owner", "Admin"}
    rows = db.query(PMSWorkspaceEntry).filter_by(workspace_id=wid, kind="form_v2").order_by(PMSWorkspaceEntry.id.desc()).all()
    return [output(r, admin) for r in rows if admin or json.loads(r.body)["published"]]


@router.post("/workspaces/{wid}/forms", status_code=201)
def create_form(wid: int, data: Definition, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, wid, user, True)
    validate_workflow(db, wid, data, user)
    if db.query(PMSWorkspaceEntry).filter_by(workspace_id=wid, kind="form_v2").count() >= 100:
        raise HTTPException(422, "Workspace limit: 100 forms")
    row = PMSWorkspaceEntry(workspace_id=wid, author_id=user.id, kind="form_v2", body=json.dumps({"draft": data.model_dump(), "published": None, "revision": 1, "version": 0, "open": False, "responses": 0}))
    db.add(row)
    db.commit()
    db.refresh(row)
    return output(row, True)


@router.put("/workspaces/{wid}/forms/{fid}")
def save_form(wid: int, fid: int, data: Save, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, wid, user, True)
    row = row_for(db, wid, fid)
    old = row.body
    saved = json.loads(old)
    if saved["revision"] != data.revision:
        raise HTTPException(409, "This form changed. Reload before saving.")
    validate_workflow(db, wid, data.definition, user)
    saved.update(draft=data.definition.model_dump(), revision=saved["revision"] + 1)
    if data.publish:
        saved.update(published=data.definition.model_dump(), version=saved["version"] + 1, open=True)
    if data.close:
        saved["open"] = False
    if db.execute(update(PMSWorkspaceEntry).where(PMSWorkspaceEntry.id == fid, PMSWorkspaceEntry.body == old).values(body=json.dumps(saved))).rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This form changed. Reload before saving.")
    db.commit()
    db.refresh(row)
    return output(row, True)


def visible(f, answers):
    c = f.condition
    if not c:
        return True
    value = answers.get(c.field)
    if c.operator == "not_empty":
        return value is not None and value != "" and value != [] and value is not False
    if c.operator == "contains":
        return c.value in value if isinstance(value, (str, list)) else False
    text = "" if value is None else (format(value, "g") if isinstance(value, float) else (",".join(value) if isinstance(value, list) else str(value)))
    same = text.lower() == c.value.lower()
    return same if c.operator == "equals" else not same


def clean_answers(definition, answers):
    if len(json.dumps(answers)) > 20000:
        raise HTTPException(422, "Total response limit: 20,000 characters")
    unknown = set(answers) - {f.id for f in definition.fields}
    if unknown:
        raise HTTPException(422, "Unknown question IDs")
    clean = {}
    for f in definition.fields:
        if f.type == "section" or not visible(f, clean):
            continue
        value = answers.get(f.id)
        empty = value is None or value == "" or value == [] or (f.type == "checkbox" and value is False)
        if empty:
            if f.required:
                raise HTTPException(422, f"{f.label}: response required")
            continue
        valid = True
        if f.type == "checkbox":
            valid = isinstance(value, bool)
        elif f.type == "multiselect":
            valid = isinstance(value, list) and len(value) <= 50 and len(set(value)) == len(value) and all(x in f.options for x in value)
        elif f.type in {"number", "rating"}:
            try:
                value = float(value) if not isinstance(value, (bool, list)) else float("nan")
                valid = math.isfinite(value) and (f.min is None or value >= f.min) and (f.max is None or value <= f.max)
                if f.type == "rating":
                    valid = valid and 1 <= value <= 5 and value.is_integer()
            except (TypeError, ValueError):
                valid = False
        else:
            valid = isinstance(value, str) and bool(value.strip()) and len(value) <= (10000 if f.type == "textarea" else 2000)
            if valid:
                value = value.strip()
                if f.type == "email":
                    valid = bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value))
                elif f.type == "url":
                    valid = bool(re.fullmatch(r"https?://[^\s/]+[^\s]*", value))
                elif f.type == "date":
                    try:
                        date.fromisoformat(value)
                    except ValueError:
                        valid = False
                elif f.type in {"select", "radio"}:
                    valid = value in f.options
                elif f.type == "phone":
                    valid = bool(re.fullmatch(r"[+()0-9 .-]{5,40}", value))
        if not valid:
            raise HTTPException(422, f"{f.label}: invalid response")
        clean[f.id] = value
    return clean


def _submit_form(wid, fid, data, db, user):
    _, membership = workspace_member(db, wid, user)
    if membership.role == "Guest":
        raise HTTPException(403, "Guests cannot submit workspace forms")
    row = row_for(db, wid, fid)
    old = row.body
    saved = json.loads(old)
    key = f"{fid}:{user.id}:{data.request_id}"
    prior = db.query(PMSWorkspaceEntry).filter_by(workspace_id=wid, kind="form_reply").filter(PMSWorkspaceEntry.body.contains(json.dumps({"key": key})[1:-1])).all()
    for r in prior:
        previous = json.loads(r.body)
        if previous["key"] == key:
            return {"id": r.id, "task_id": r.task_id, "replayed": True}
    if not saved["open"] or not saved["published"]:
        raise HTTPException(422, "This form is not accepting responses")
    if data.version != saved["version"]:
        raise HTTPException(409, "This form was republished. Reload before submitting.")
    if saved["responses"] >= 10000:
        raise HTTPException(422, "Form response limit reached")
    definition = Definition.model_validate(saved["published"])
    answers = clean_answers(definition, data.answers)
    # Serialize submissions and edits, including on SQLite; all effects commit together.
    saved["responses"] += 1
    if db.execute(update(PMSWorkspaceEntry).where(PMSWorkspaceEntry.id == fid, PMSWorkspaceEntry.body == old).values(body=json.dumps(saved))).rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Form changed. Retry your submission.")
    task = None
    w = definition.workflow
    if w.enabled:
        validate_workflow(db, wid, definition, user)
        project = get_project_for_action(db, w.project_id, user, "manage_tasks")
        board = db.query(PMSBoard).filter_by(project_id=project.id).order_by(PMSBoard.id).first()
        if not board:
            board = PMSBoard(project_id=project.id, name="Default Board", board_type="Kanban")
            db.add(board)
            db.flush()
        column = db.query(PMSBoardColumn).filter_by(board_id=board.id, status_key="TODO").first()
        if not column:
            column = PMSBoardColumn(board_id=board.id, name="To Do", status_key="TODO", position=1)
            db.add(column)
            db.flush()
        description = "\n\n".join(f"{f.label}: " + (", ".join(answers[f.id]) if isinstance(answers[f.id], list) else str(answers[f.id])) for f in definition.fields if f.id in answers)
        task = PMSTask(project_id=project.id, board_id=board.id, column_id=column.id, task_key="FORM-" + data.request_id.hex[:24].upper(), title=str(answers[w.title_field])[:220], description=description, reporter_user_id=user.id, status="To Do", priority=w.priority, due_date=date.today() + timedelta(days=w.due_days) if w.due_days is not None else None, position=0, rank=1)
        if w.assignee_id:
            task.assignee_user_ids = [w.assignee_id]
        db.add(task)
        db.flush()
        apply_task_rules(db, task, project, user, "task.created")
        db.add(PMSActivity(project_id=project.id, task_id=task.id, actor_user_id=user.id, action="task.created", entity_type="task", entity_id=task.id, summary=f"Created from form: {definition.name}"[:300]))
        set_audit_entity(project.id, task.id)
    reply = PMSWorkspaceEntry(workspace_id=wid, author_id=user.id, kind="form_reply", task_id=task.id if task else None, body=json.dumps({"key": key, "form_id": fid, "version": saved["version"], "answers": answers, "labels": {f.id: f.label for f in definition.fields}, "submitted_at": datetime.now(timezone.utc).isoformat(), "user_id": user.id}))
    db.add(reply)
    db.flush()
    db.refresh(reply)
    return {"id": reply.id, "task_id": reply.task_id, "replayed": False, "message": definition.success_message}


@router.post("/workspaces/{wid}/forms/{fid}/submit", status_code=201)
def submit_form(wid: int, fid: int, data: Submission, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    with db.begin_nested():
        result = _submit_form(wid, fid, data, db, user)
    db.commit()
    if result.get("task_id") and not result.get("replayed"):
        from .api.router import _broadcast_realtime
        task = db.get(PMSTask, result["task_id"])
        _broadcast_realtime(user, "task.created", project_id=task.project_id, task_id=task.id, message="Task created from form response")
    return result


def response_query(db, wid, fid):
    return db.query(PMSWorkspaceEntry).filter_by(workspace_id=wid, kind="form_reply").filter(PMSWorkspaceEntry.body.contains(f'"form_id": {fid},')).order_by(PMSWorkspaceEntry.id.desc())


def response_rows(db, wid, fid):
    return response_query(db, wid, fid).all()


@router.get("/workspaces/{wid}/forms/{fid}/responses")
def responses(wid: int, fid: int, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, wid, user, True)
    row_for(db, wid, fid)
    query = response_query(db, wid, fid)
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    return {"total": total, "items": [{"id": r.id, "task_id": r.task_id, **{k: v for k, v in json.loads(r.body).items() if k != "key"}} for r in rows]}


@router.get("/workspaces/{wid}/forms/{fid}/export")
def export(wid: int, fid: int, format: Literal["csv", "json"] = "csv", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, wid, user, True)
    row_for(db, wid, fid)
    rows = [{"id": r.id, "task_id": r.task_id, **{k: v for k, v in json.loads(r.body).items() if k != "key"}} for r in response_rows(db, wid, fid)]
    if format == "json":
        content, media = json.dumps(rows, ensure_ascii=False), "application/json"
    else:
        ids = list(dict.fromkeys(k for r in rows for k in r["answers"]))
        labels = {k: v for r in reversed(rows) for k, v in r["labels"].items()}
        stream = io.StringIO()
        writer = csv.writer(stream)
        def safe(value):
            text = str(value if value is not None else "")
            return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
        writer.writerow(["Response ID", "Submitted UTC", "User ID", "Task ID", "Version"] + [safe(labels.get(k, k) + " [" + k + "]") for k in ids])
        for r in rows:
            writer.writerow([r["id"], r["submitted_at"], r["user_id"], r["task_id"], r["version"]] + [safe("; ".join(r["answers"][k]) if isinstance(r["answers"].get(k), list) else r["answers"].get(k, "")) for k in ids])
        content, media = "\ufeff" + stream.getvalue(), "text/csv"
    return Response(content=content, media_type=media, headers={"Content-Disposition": f'attachment; filename="form-{fid}.{format}"'})
