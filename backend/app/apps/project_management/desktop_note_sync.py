"""Versioned interchange for the signed-in owner's standalone personal notes."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSNote, PMSNoteAttachment, PMSNoteEvent, PMSNoteShare, PMSNoteTaskLink
from .notes import NoteInput, private_response, require_note_action, revision, versioned_owned_update

router = APIRouter(prefix="/desktop-sync/notes", dependencies=[Depends(private_response)])
FIELDS = ("title", "content", "tags", "favorite", "pinned", "archived")


class NoteContent(NoteInput):
    project_id: None = None
    task_id: None = None
    folder_id: None = None
    trashed: bool = False


class SyncWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    note: NoteContent


def eligible(user):
    return (
        PMSNote.owner_id == user.id,
        PMSNote.project_id.is_(None),
        PMSNote.task_id.is_(None),
        PMSNote.folder_id.is_(None),
        PMSNote.visibility_scope == "private",
        ~select(PMSNoteShare.id).where(PMSNoteShare.note_id == PMSNote.id).exists(),
        ~select(PMSNoteAttachment.id).where(PMSNoteAttachment.note_id == PMSNote.id).exists(),
        ~select(PMSNoteTaskLink.id).where(PMSNoteTaskLink.note_id == PMSNote.id).exists(),
        ~PMSNote.content.contains("data-note-image"),
    )


def serialize(note):
    return {"id": note.sync_id, "version": note.version, "note": {
        **{key: getattr(note, key) for key in FIELDS}, "trashed": note.deleted_at is not None,
    }}


@router.get("")
def snapshot(after: int = Query(default=0, ge=0), db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    require_note_action(user, "view")
    rows = db.scalars(select(PMSNote).where(*eligible(user), PMSNote.id > after)
                      .order_by(PMSNote.id).limit(51)).all()
    page = rows[:50]
    return {
        "tenant": db.info.get("tenant_uuid"),
        "company_id": getattr(user, "organization_id", None),
        "items": [serialize(row) for row in page],
        "next": page[-1].id if len(rows) > len(page) else None,
    }


@router.get("/{sync_id}")
def read_note(sync_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_note_action(user, "view")
    note = db.scalar(select(PMSNote).where(PMSNote.sync_id == str(sync_id), *eligible(user)))
    if note is None:
        raise HTTPException(404, "This note is unavailable for sync.")
    return serialize(note)


@router.put("/{sync_id}")
def write_note(sync_id: UUID, change: SyncWrite, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if "data-note-image" in change.note.content:
        raise HTTPException(422, "Notes with embedded attachments cannot be synced.")
    note = db.scalar(select(PMSNote).where(PMSNote.sync_id == str(sync_id), *eligible(user)).with_for_update())
    if (note.version if note else 0) != change.expected_version:
        raise HTTPException(409, "This note changed or is unavailable. Run sync again.")

    now = datetime.now(timezone.utc)
    values = change.note.model_dump(include=set(FIELDS))
    values.update(title=change.note.title.strip() or "Untitled note",
                  updated_at=now, deleted_at=now if change.note.trashed else None)
    try:
        if note is None:
            require_note_action(user, "create")
            note = PMSNote(sync_id=str(sync_id), owner_id=user.id, **values)
            db.add(note)
            db.flush()
        else:
            require_note_action(user, "edit")
            if bool(note.deleted_at) != change.note.trashed:
                require_note_action(user, "delete")
            if note.deleted_at and change.note.trashed:
                values["deleted_at"] = note.deleted_at
            if not versioned_owned_update(db, note, change.expected_version, values):
                raise HTTPException(409, "This note changed. Run sync again.")
        revision(db, note)
        db.add(PMSNoteEvent(note_id=note.id, actor_id=user.id, action="desktop_sync"))
        result = serialize(note)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "This note changed or is unavailable. Run sync again.") from error
    return result
