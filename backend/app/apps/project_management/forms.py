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
from app.forms.schema import Strict, Definition, Question, Condition, FieldType, Workflow, visible, clean_answers

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
