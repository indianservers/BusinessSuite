from app.core.rich_text import rich_text_type
"""Personal notes. Project membership and administrator roles never confer access."""
from datetime import datetime, timezone
from html import unescape
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, update
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import get_project_for_action, get_task_project_for_action, can_access_project
from .models import PMSNote, PMSNoteRevision, PMSProject, PMSTask

def private_response(response: Response):
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(dependencies=[Depends(private_response)])


class NoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Untitled note", max_length=180)
    content: rich_text_type(200000, 0) = Field(default="")
    # None represents the owner's built-in Personal notes project, never an unfiled note.
    project_id: int | None = Field(default=None, gt=0, description="PMS project ID, or null for your private Personal project (default).")
    task_id: int | None = Field(default=None, gt=0)
    tags: list[str] = Field(default_factory=list, max_length=20)
    pinned: bool = False
    archived: bool = False

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values):
        tags = list(dict.fromkeys(v.strip().lower() for v in values if v.strip()))
        if any(len(v) > 40 for v in tags):
            raise ValueError("Tags must be 40 characters or fewer")
        return tags


class NoteSave(NoteInput):
    version: int = Field(gt=0)


class VersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(gt=0)


def owned(db, note_id, user):
    note = db.query(PMSNote).filter_by(id=note_id, owner_id=user.id).first()
    if note is None:
        raise HTTPException(404, "Note not found")
    return note


def validate_links(db, data, user, previous=None):
    # Preserve inaccessible old associations while still allowing the owner to unlink them.
    if data.project_id is not None and (previous is None or data.project_id != previous.project_id):
        get_project_for_action(db, data.project_id, user, "browse")
    if data.task_id is not None:
        if data.project_id is None:
            raise HTTPException(422, "Choose a project before linking a task")
        if previous is None or (data.task_id, data.project_id) != (previous.task_id, previous.project_id):
            task, _ = get_task_project_for_action(db, data.task_id, user)
            if task.project_id != data.project_id:
                raise HTTPException(422, "Task must belong to the selected project")


def result(db, note, user, full=True):
    project = db.get(PMSProject, note.project_id) if note.project_id else None
    accessible = project is not None and project.deleted_at is None and can_access_project(db, project, user, "browse")
    task = db.get(PMSTask, note.task_id) if note.task_id and accessible else None
    payload = {key: getattr(note, key) for key in ("id", "title", "tags", "pinned", "archived", "version", "created_at", "updated_at", "deleted_at")}
    payload.update(project_id=note.project_id, task_id=note.task_id,
                   project_name=project.name if accessible else "Personal" if note.project_id is None else "Unavailable project",
                   project_kind="personal" if note.project_id is None else "project",
                   project_key=f"personal:{note.owner_id}" if note.project_id is None else f"project:{note.project_id}",
                   visibility="private",
                   task_title=task.title if task is not None and task.deleted_at is None else None,
                   preview=note_excerpt(note.content))
    if full:
        payload["content"] = note.content
    return payload


def note_excerpt(content):
    text = re.sub(r"<[^>]*>", "", content)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|>\s+|[-*+]\s+(?:\[[ xX]\]\s*)?|\d+\.\s+)", "", text)
    text = re.sub(r"\*\*|__|\+\+|==|~~|`", "", text)
    return " ".join(unescape(text).split())[:160]


def revision(db, note):
    db.add(PMSNoteRevision(note_id=note.id, version=note.version, title=note.title, content=note.content))


@router.get("/notes")
def list_notes(q: str = Query(default="", max_length=200), view: Literal["all", "pinned", "archive", "trash"] = "all",
               project_id: int | None = None, personal: bool = False, tag: str = Query(default="", max_length=40),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(PMSNote).filter(PMSNote.owner_id == user.id)
    query = query.filter(PMSNote.deleted_at.is_not(None)) if view == "trash" else query.filter(PMSNote.deleted_at.is_(None), PMSNote.archived.is_(view == "archive"))
    if view == "pinned":
        query = query.filter(PMSNote.pinned.is_(True))
    if personal:
        query = query.filter(PMSNote.project_id.is_(None))
    elif project_id is not None:
        query = query.filter(PMSNote.project_id == project_id)
    if q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(or_(PMSNote.title.ilike(f"%{term}%", escape="\\"), PMSNote.content.ilike(f"%{term}%", escape="\\")))
    rows = query.order_by(PMSNote.pinned.desc(), PMSNote.updated_at.desc(), PMSNote.id.desc()).all()
    return [result(db, row, user, False) for row in rows if not tag or tag.strip().lower() in row.tags]


@router.post("/notes", status_code=201)
def create_note(data: NoteInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    validate_links(db, data, user)
    note = PMSNote(owner_id=user.id, **data.model_dump())
    note.title = note.title.strip() or "Untitled note"
    db.add(note)
    db.flush()
    revision(db, note)
    db.commit()
    db.refresh(note)
    return result(db, note, user)


@router.get("/notes/{note_id}")
def get_note(note_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return result(db, owned(db, note_id, user), user)


@router.put("/notes/{note_id}")
def save_note(note_id: int, data: NoteSave, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    note = owned(db, note_id, user)
    if note.deleted_at:
        raise HTTPException(409, "Restore the note before editing")
    validate_links(db, data, user, note)
    values = data.model_dump(exclude={"version"})
    values.update(title=data.title.strip() or "Untitled note", version=data.version + 1, updated_at=datetime.now(timezone.utc))
    count = db.execute(update(PMSNote).where(PMSNote.id == note_id, PMSNote.owner_id == user.id,
        PMSNote.version == data.version, PMSNote.deleted_at.is_(None)).values(**values).execution_options(synchronize_session=False)).rowcount
    if count != 1:
        db.rollback()
        raise HTTPException(409, "This note changed in another tab. Your draft is kept. Reload the latest note before saving.")
    db.refresh(note)
    revision(db, note)
    db.commit()
    return result(db, note, user)


def change_deleted(db, note_id, data, user, deleted):
    note = owned(db, note_id, user)
    count = db.execute(update(PMSNote).where(PMSNote.id == note.id, PMSNote.owner_id == user.id, PMSNote.version == data.version).values(
        deleted_at=datetime.now(timezone.utc) if deleted else None, version=data.version + 1,
        updated_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False)).rowcount
    if count != 1:
        db.rollback()
        raise HTTPException(409, "Note changed. Reload before trying again.")
    db.refresh(note)
    revision(db, note)
    db.commit()
    return result(db, note, user)


@router.delete("/notes/{note_id}")
def trash_note(note_id: int, data: VersionInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return change_deleted(db, note_id, data, user, True)


@router.post("/notes/{note_id}/restore")
def restore_note(note_id: int, data: VersionInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return change_deleted(db, note_id, data, user, False)


@router.get("/notes/{note_id}/revisions")
def list_revisions(note_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned(db, note_id, user)
    rows = db.query(PMSNoteRevision).filter_by(note_id=note_id).order_by(PMSNoteRevision.version.desc()).all()
    return [{"version": r.version, "title": r.title, "created_at": r.created_at} for r in rows]


@router.get("/notes/{note_id}/revisions/{version}")
def get_revision(note_id: int, version: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned(db, note_id, user)
    row = db.query(PMSNoteRevision).filter_by(note_id=note_id, version=version).first()
    if row is None:
        raise HTTPException(404, "Revision not found")
    return {"version": row.version, "title": row.title, "content": row.content}
