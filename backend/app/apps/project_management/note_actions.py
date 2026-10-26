from app.core.rich_text import rich_text_type
"""Private note attachments and explicit, reviewed note-to-task publication."""
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Literal
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import can_access_project, get_project_for_action, get_task_project_for_action
from .models import PMSNote, PMSNoteAttachment, PMSNoteTaskLink, PMSProject, PMSTask
from .notes import owned, readable, private_response

router = APIRouter(dependencies=[Depends(private_response)])
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
        ".webp": "image/webp", ".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/plain",
        ".csv": "text/csv", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".zip": "application/zip"}


def writable(db, note_id, user):
    note = db.query(PMSNote).filter_by(id=note_id, owner_id=user.id).with_for_update().populate_existing().first()
    if note is None:
        raise HTTPException(404, "Note not found")
    if note.deleted_at:
        raise HTTPException(409, "Restore the note before changing its attachments or creating tasks")
    return note


def attachment_result(row):
    return {"id": row.id, "filename": row.filename, "media_type": row.media_type,
            "size": row.size, "created_at": row.created_at, "deleted_at": row.deleted_at}


def attachment(db, note_id, attachment_id, user, include_deleted=False):
    readable(db, note_id, user)
    row = db.query(PMSNoteAttachment).filter_by(id=attachment_id, note_id=note_id).first()
    if row is None or (row.deleted_at and not include_deleted):
        raise HTTPException(404, "Attachment not found")
    return row


@router.get("/notes/{note_id}/attachments")
def list_attachments(note_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    note = readable(db, note_id, user)
    rows = db.query(PMSNoteAttachment).filter_by(note_id=note_id).order_by(PMSNoteAttachment.id).all()
    return {"items": [attachment_result(r) for r in rows if r.deleted_at is None],
            "removed_items": [attachment_result(r) for r in rows if r.deleted_at is not None and note.owner_id == user.id],
            "max_file_bytes": min(settings.MAX_UPLOAD_SIZE_MB, 10) * 1024 * 1024,
            "max_note_bytes": 50 * 1024 * 1024, "max_files": 20}


def validated_file(file):
    name = PurePosixPath((file.filename or "").replace("\\", "/")).name
    if not name or len(name) > 255 or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise HTTPException(422, "Choose a file with a valid filename (up to 255 characters)")
    ext = PurePosixPath(name).suffix.lower()
    if ext not in MIME:
        raise HTTPException(415, "Supported files: images (PNG, JPG, GIF, WebP), PDF, TXT, Markdown, CSV, Office documents and ZIP")
    limit = min(settings.MAX_UPLOAD_SIZE_MB, 10) * 1024 * 1024
    chunks, size = [], 0
    while chunk := file.file.read(65536):
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"File exceeds the {limit // (1024 * 1024)} MB upload limit")
        chunks.append(chunk)
    body = b"".join(chunks)
    if not body:
        raise HTTPException(422, "Empty files cannot be attached")
    signatures = {".png": body.startswith(b"\x89PNG\r\n\x1a\n"), ".jpg": body.startswith(b"\xff\xd8\xff"),
                  ".jpeg": body.startswith(b"\xff\xd8\xff"), ".gif": body[:6] in (b"GIF87a", b"GIF89a"),
                  ".webp": body.startswith(b"RIFF") and body[8:12] == b"WEBP", ".pdf": body.startswith(b"%PDF-"),
                  ".docx": body.startswith(b"PK\x03\x04"), ".xlsx": body.startswith(b"PK\x03\x04"),
                  ".pptx": body.startswith(b"PK\x03\x04"), ".zip": body.startswith((b"PK\x03\x04", b"PK\x05\x06"))}
    if ext in signatures and not signatures[ext]:
        raise HTTPException(415, "File contents do not match the file type")
    if ext in {".txt", ".md", ".csv"}:
        try:
            body.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(415, "Text attachments must use UTF-8 encoding") from None
    return name, MIME[ext], body


@router.post("/notes/{note_id}/attachments", status_code=201)
def upload_attachment(note_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    writable(db, note_id, user)
    name, media_type, body = validated_file(file)
    count, size = db.query(func.count(PMSNoteAttachment.id), func.coalesce(func.sum(PMSNoteAttachment.size), 0)).filter_by(note_id=note_id).one()
    if count >= 20 or size + len(body) > 50 * 1024 * 1024:
        raise HTTPException(413, "Note attachment limit reached (20 files or 50 MB, including removed files kept for undo)")
    row = PMSNoteAttachment(note_id=note_id, filename=name, media_type=media_type, size=len(body), body=body)
    db.add(row); db.commit(); db.refresh(row)
    return attachment_result(row)


@router.get("/notes/{note_id}/attachments/{attachment_id}/download")
def download_attachment(note_id: int, attachment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = attachment(db, note_id, attachment_id, user)
    return Response(row.body, media_type=row.media_type, headers={"Cache-Control": "private, no-store",
                    "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox",
                    "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.filename, safe='')}"})


@router.delete("/notes/{note_id}/attachments/{attachment_id}")
def remove_attachment(note_id: int, attachment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    writable(db, note_id, user)
    row = attachment(db, note_id, attachment_id, user)
    row.deleted_at = datetime.now(timezone.utc); db.commit()
    return {"removed": True, "id": row.id}


@router.post("/notes/{note_id}/attachments/{attachment_id}/restore")
def restore_attachment(note_id: int, attachment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    writable(db, note_id, user)
    row = attachment(db, note_id, attachment_id, user, True)
    row.deleted_at = None; db.commit()
    return attachment_result(row)


class TaskFromNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=220)
    description: rich_text_type(10000, 0) = Field(default="")
    due_date: date | None = None
    priority: Literal["Low", "Medium", "High", "Urgent"] = "Medium"
    publish_to_project: Literal[True]
    request_key: UUID

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Task title cannot be blank")
        return value.strip()


def task_result(task):
    return {"id": task.id, "task_key": task.task_key, "title": task.title, "project_id": task.project_id,
            "status": task.status, "due_date": task.due_date, "priority": task.priority}


@router.get("/notes/{note_id}/tasks")
def list_note_tasks(note_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned(db, note_id, user)
    rows = db.query(PMSTask, PMSProject).join(PMSNoteTaskLink, PMSNoteTaskLink.task_id == PMSTask.id).join(PMSProject, PMSProject.id == PMSTask.project_id).filter(
        PMSNoteTaskLink.note_id == note_id, PMSTask.deleted_at.is_(None), PMSProject.deleted_at.is_(None)).order_by(PMSNoteTaskLink.id.desc()).all()
    return [task_result(task) for task, project in rows if can_access_project(db, project, user, "browse")]


@router.post("/notes/{note_id}/tasks", status_code=201)
def create_note_task(note_id: int, data: TaskFromNote, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    writable(db, note_id, user)
    project = get_project_for_action(db, data.project_id, user, "manage_tasks")
    key = str(data.request_key)
    digest = sha256(json.dumps(data.model_dump(mode="json", exclude={"request_key"}), sort_keys=True).encode()).hexdigest()
    previous = db.query(PMSNoteTaskLink).filter_by(note_id=note_id, request_key=key).first()
    if previous:
        if previous.request_hash != digest:
            raise HTTPException(409, "This request was already used for a different task")
        task = db.get(PMSTask, previous.task_id)
        if task is None or task.deleted_at:
            raise HTTPException(409, "Previously created task is no longer available")
        get_task_project_for_action(db, task.id, user, "browse")
        return task_result(task)
    # Use the established task creation service, but commit note-link and task together.
    # No private note ID, body, attachment, or title is implicitly copied into the task.
    from .api.router import create_task_operation, _broadcast_realtime
    from .schemas import PMSTaskCreate
    task = create_task_operation(project.id, PMSTaskCreate(
        title=data.title, description=data.description, priority=data.priority, due_date=data.due_date,
        task_key=f"{project.project_key[:10]}-{uuid4().hex[:12].upper()}", reporter_user_id=user.id), db, user, commit=False)
    db.add(PMSNoteTaskLink(note_id=note_id, task_id=task.id, request_key=key, request_hash=digest))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = db.query(PMSNoteTaskLink).filter_by(note_id=note_id, request_key=key).first()
        if previous is None or previous.request_hash != digest:
            raise HTTPException(409, "Task creation conflicted. Reload before trying again") from None
        task, _ = get_task_project_for_action(db, previous.task_id, user, "browse")
        return task_result(task)
    _broadcast_realtime(user, "task.created", project_id=project.id, task_id=task.id, message=f"Created task {task.task_key}")
    return task_result(task)
