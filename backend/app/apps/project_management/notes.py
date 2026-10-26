from app.core.rich_text import rich_text_type
"""Personal notes. Project membership and administrator roles never confer access."""
from datetime import datetime, timezone
from html import unescape
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import or_, update, func
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import get_project_for_action, get_task_project_for_action, can_access_project
from .models import PMSNote, PMSNoteRevision, PMSProject, PMSTask, PMSNoteFolder, PMSNoteShare, PMSNoteEvent

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
    folder_id: int | None = Field(default=None, gt=0)
    favorite: bool = False
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


def readable(db, note_id, user):
    note = db.get(PMSNote, note_id)
    if note and note.owner_id == user.id:
        return note
    if note and not note.deleted_at and db.query(PMSNoteShare.id).filter_by(note_id=note_id, user_id=user.id).first():
        from .access import organization_id_for
        owner = db.get(User, note.owner_id)
        if owner and organization_id_for(owner) == organization_id_for(user) and (not note.project_id or can_access_project(db, db.get(PMSProject, note.project_id), user, "browse")):
            return note
    raise HTTPException(404, "Note not found")


def folder_owned(db, folder_id, user):
    folder = db.query(PMSNoteFolder).filter_by(id=folder_id, owner_id=user.id, deleted_at=None).first()
    if not folder: raise HTTPException(404, "Folder not found")
    return folder


def validate_links(db, data, user, previous=None):
    if getattr(data, "folder_id", None):
        folder = folder_owned(db, data.folder_id, user)
        if (folder.project_id, folder.task_id) != (data.project_id, data.task_id):
            raise HTTPException(422, "Note project and task must match its folder")
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
    payload = {key: getattr(note, key) for key in ("id", "title", "tags", "pinned", "archived", "version", "created_at", "updated_at", "deleted_at", "folder_id", "favorite")}
    payload.update(project_id=note.project_id, task_id=note.task_id,
                   project_name=project.name if accessible else "Personal" if note.project_id is None else "Unavailable project",
                   project_kind="personal" if note.project_id is None else "project",
                   project_key=f"personal:{note.owner_id}" if note.project_id is None else f"project:{note.project_id}",
                   visibility="shared" if db.query(PMSNoteShare.id).filter_by(note_id=note.id).first() else "private",
                   can_edit=note.owner_id == user.id, can_share=note.owner_id == user.id,
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
def list_notes(q: str = Query(default="", max_length=200), view: Literal["all", "pinned", "favorites", "recent", "shared", "quick", "archive", "trash"] = "all",
               folder_id: int | None = None, task_id: int | None = None, sort: Literal["modified", "created", "title"] = "modified",
               project_id: int | None = None, personal: bool = False, tag: str = Query(default="", max_length=40),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(PMSNote)
    if view == "shared":
        query = query.filter(PMSNote.id.in_(db.query(PMSNoteShare.note_id).filter(PMSNoteShare.user_id == user.id)))
    else:
        query = query.filter(PMSNote.owner_id == user.id)
    if folder_id is not None:
        folder_owned(db, folder_id, user)
        query = query.filter(PMSNote.folder_id == folder_id)
    if task_id is not None: query = query.filter(PMSNote.task_id == task_id)
    if view == "favorites": query = query.filter(PMSNote.favorite.is_(True))
    if view == "quick": query = query.filter(PMSNote.project_id.is_(None), PMSNote.folder_id.is_(None))
    query = query.filter(PMSNote.deleted_at.is_not(None)) if view == "trash" else query.filter(PMSNote.deleted_at.is_(None), PMSNote.archived.is_(view == "archive"))
    if view == "pinned":
        query = query.filter(PMSNote.pinned.is_(True))
    if personal:
        query = query.filter(PMSNote.project_id.is_(None))
    elif project_id is not None:
        query = query.filter(PMSNote.project_id == project_id)
    if q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(or_(PMSNote.title.ilike(f"%{term}%", escape="\\"), PMSNote.content.ilike(f"%{term}%", escape="\\"), func.cast(PMSNote.tags, __import__("sqlalchemy").String).ilike(f"%{term}%", escape="\\")))
    order = PMSNote.title.asc() if sort == "title" else PMSNote.created_at.desc() if sort == "created" else PMSNote.updated_at.desc()
    rows = query.order_by(PMSNote.pinned.desc(), order, PMSNote.id.desc()).all()
    if view == "shared":
        rows = [row for row in rows if _may_read(db, row.id, user)]
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
    return result(db, readable(db, note_id, user), user)


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


def _may_read(db, note_id, user):
    try: readable(db, note_id, user); return True
    except HTTPException: return False


class FolderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    parent_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)
    task_id: int | None = Field(default=None, gt=0)
    color: str = Field(default="#8b5cf6", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: Literal["folder", "book", "idea", "meeting", "code"] = "folder"
    position: int = Field(default=0, ge=0, le=1000000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip(): raise ValueError("Folder name is required")
        return value.strip()


class FolderSave(FolderInput):
    version: int = Field(gt=0)


def folder_result(folder):
    return {key: getattr(folder, key) for key in ("id", "name", "parent_id", "project_id", "task_id", "color", "icon", "position", "version")}


@router.get("/note-folders")
def folders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(PMSNoteFolder).filter_by(owner_id=user.id, deleted_at=None).order_by(PMSNoteFolder.position, PMSNoteFolder.id).all()
    counts = dict(db.query(PMSNote.folder_id, func.count(PMSNote.id)).filter_by(owner_id=user.id, deleted_at=None, archived=False).group_by(PMSNote.folder_id).all())
    return [dict(folder_result(folder), count=counts.get(folder.id, 0)) for folder in rows]


def check_parent(db, data, user, folder=None):
    # Serialize tree mutations for an owner; two simultaneous moves cannot create a cycle.
    db.query(User).filter_by(id=user.id).with_for_update().first()
    parent = folder_owned(db, data.parent_id, user) if data.parent_id else None
    visited = {folder.id} if folder else set()
    current = parent
    while current:
        if current.id in visited: raise HTTPException(422, "A folder cannot be moved inside itself or its descendants")
        visited.add(current.id)
        current = folder_owned(db, current.parent_id, user) if current.parent_id else None
    if parent and (data.project_id, data.task_id) != (parent.project_id, parent.task_id):
        raise HTTPException(422, "Nested folders must belong to the same project and task")
    if folder and (data.project_id, data.task_id) != (folder.project_id, folder.task_id):
        raise HTTPException(422, "Move the notes individually to change project or task scope")
    validate_links(db, data, user)


@router.post("/note-folders", status_code=201)
def create_folder(data: FolderInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_parent(db, data, user)
    folder = PMSNoteFolder(owner_id=user.id, **data.model_dump())
    db.add(folder); db.commit(); db.refresh(folder)
    return folder_result(folder)


@router.put("/note-folders/{folder_id}")
def save_folder(folder_id: int, data: FolderSave, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    folder = folder_owned(db, folder_id, user)
    check_parent(db, data, user, folder)
    count = db.execute(update(PMSNoteFolder).where(PMSNoteFolder.id == folder.id, PMSNoteFolder.version == data.version).values(**data.model_dump(exclude={"version"}), version=data.version+1).execution_options(synchronize_session=False)).rowcount
    if count != 1: db.rollback(); raise HTTPException(409, "Folder changed. Reload before trying again.")
    db.commit(); db.expire_all()
    return folder_result(folder_owned(db, folder_id, user))


@router.delete("/note-folders/{folder_id}")
def remove_folder(folder_id: int, data: VersionInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    folder = folder_owned(db, folder_id, user)
    db.query(User).filter_by(id=user.id).with_for_update().first()
    if db.query(PMSNoteFolder.id).filter_by(parent_id=folder_id, deleted_at=None).first() or db.query(PMSNote.id).filter_by(folder_id=folder_id).first():
        raise HTTPException(409, "Move this folder's notes (including archived and trashed notes) and subfolders before removing it")
    count = db.execute(update(PMSNoteFolder).where(PMSNoteFolder.id == folder.id, PMSNoteFolder.version == data.version).values(deleted_at=datetime.now(timezone.utc), version=data.version+1).execution_options(synchronize_session=False)).rowcount
    if count != 1: db.rollback(); raise HTTPException(409, "Folder changed. Reload before removing it.")
    db.commit(); return {"removed": True}


class ShareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    version: int = Field(gt=0)


@router.get("/notes/{note_id}/shares")
def note_shares(note_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned(db, note_id, user)
    return [{"user_id": person.id, "email": person.email} for person in db.query(User).join(PMSNoteShare, PMSNoteShare.user_id == User.id).filter(PMSNoteShare.note_id == note_id)]


@router.post("/notes/{note_id}/shares")
def share_note(note_id: int, data: ShareInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .access import organization_id_for
    note = owned(db, note_id, user)
    if note.deleted_at or note.version != data.version: raise HTTPException(409, "Save or reload the active note before sharing")
    person = db.query(User).filter(func.lower(User.email) == data.email.strip().lower(), User.is_active.is_(True)).first()
    if not person or person.id == user.id or organization_id_for(person) != organization_id_for(user): raise HTTPException(422, "Choose an active colleague in your organization")
    if note.project_id and not can_access_project(db, db.get(PMSProject, note.project_id), person, "browse"): raise HTTPException(403, "This colleague cannot access the linked project")
    if not db.query(PMSNoteShare.id).filter_by(note_id=note_id, user_id=person.id).first():
        db.add(PMSNoteShare(note_id=note_id, user_id=person.id))
        db.add(PMSNoteEvent(note_id=note_id, actor_id=user.id, action="share"))
    db.commit(); return {"shared": True, "user_id": person.id, "email": person.email}


@router.delete("/notes/{note_id}/shares/{person_id}")
def revoke_share(note_id: int, person_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned(db, note_id, user)
    db.query(PMSNoteShare).filter_by(note_id=note_id, user_id=person_id).delete()
    db.add(PMSNoteEvent(note_id=note_id, actor_id=user.id, action="revoke_share"))
    db.commit(); return {"revoked": True}


class BulkItem(BaseModel):
    id: int = Field(gt=0)
    version: int = Field(gt=0)


class BulkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BulkItem] = Field(min_length=1, max_length=200)
    action: Literal["move", "archive", "unarchive", "trash", "restore"]
    folder_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)
    task_id: int | None = Field(default=None, gt=0)


@router.post("/note-actions/bulk")
def bulk_notes(data: BulkInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if len({item.id for item in data.items}) != len(data.items): raise HTTPException(422, "Select each note once")
    rows = [(owned(db, item.id, user), item.version) for item in data.items]
    if data.action == "move": validate_links(db, data, user)
    for note, version in rows:
        if note.version != version: db.rollback(); raise HTTPException(409, "A selected note changed. Reload; no notes were updated.")
        if note.deleted_at and data.action != "restore": raise HTTPException(409, "Restore trashed notes before moving or archiving them")
    for note, version in rows:
        values = {"version": version+1, "updated_at": datetime.now(timezone.utc)}
        if data.action == "move": values.update(folder_id=data.folder_id, project_id=data.project_id, task_id=data.task_id)
        elif data.action in {"archive", "unarchive"}: values["archived"] = data.action == "archive"
        else: values["deleted_at"] = datetime.now(timezone.utc) if data.action == "trash" else None
        count = db.execute(update(PMSNote).where(PMSNote.id == note.id, PMSNote.owner_id == user.id, PMSNote.version == version).values(**values).execution_options(synchronize_session=False)).rowcount
        if count != 1: db.rollback(); raise HTTPException(409, "A selected note changed. No notes were updated.")
        db.expire(note); db.refresh(note); revision(db, note)
        db.add(PMSNoteEvent(note_id=note.id, actor_id=user.id, action=data.action))
    db.commit(); return {"updated": len(rows)}
