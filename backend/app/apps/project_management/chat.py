from app.core.rich_text import rich_text_type
"""Permission-scoped workspace messaging. Database state is authoritative."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, func, update, exists, and_, literal_column
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.storage import persist_file, upload_exists, materialize_file
from app.models.user import User
from app.models.notification import Notification
from .chat_models import (
    ChatConversation as Room,
    ChatMember as Member,
    ChatMessage as Message,
    ChatAttachment as Attachment,
)
from .models import (
    PMSWorkspace,
    PMSWorkspaceMember,
    PMSWorkspaceEntry,
    PMSDirectConversation,
    PMSDirectMessage,
    PMSFileAsset,
    PMSProject,
)
from .workspaces import workspace_member
from .access import (
    get_project_for_action,
    accessible_project_query,
    organization_id_for,
)

from app.shared.communication.contexts import can_view_contexts as _context_visible, denied_rooms

router = APIRouter(prefix="/workspaces/{wid}/chat")
summary_router = APIRouter()


@summary_router.get("/messaging/unread")
def unread_summary(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    from .workspace_lifecycle import archived_ids
    # Current workspace membership is part of the query, never a cached room list.
    denied = denied_rooms(db, user)
    count = (
        db.query(func.count(Message.id))
        .join(Room, Room.id == Message.conversation_id)
        .join(PMSWorkspace, PMSWorkspace.id == Room.workspace_id)
        .join(
            Member,
            and_(
                Member.conversation_id == Room.id,
                Member.user_id == user.id,
                Member.active.is_(True),
            ),
        )
        .join(
            PMSWorkspaceMember,
            and_(
                PMSWorkspaceMember.workspace_id == Room.workspace_id,
                PMSWorkspaceMember.user_id == user.id,
            ),
        )
        .filter(
            PMSWorkspace.organization_id == organization_id_for(user),
            PMSWorkspace.id.notin_(archived_ids()),
            Message.id > Member.history_after,
            or_(Message.parent_id.is_(None), Message.parent_id > Member.history_after),
            Message.conversation_id.notin_(denied),
            Message.id > Member.read_id,
            Message.author_id != user.id,
            Message.deleted_at.is_(None),
        )
        .scalar()
    )
    return {"unread": count or 0}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoomInput(Strict):
    kind: Literal["channel", "group", "dm"]
    name: str = Field(default="", max_length=120)
    description: rich_text_type(1000, 0) = Field(default="")
    visibility: Literal["public", "private"] = "private"
    participants: list[int] = Field(default_factory=list, max_length=50)


class RoomEdit(Strict):
    name: str = Field(min_length=1, max_length=120)
    description: rich_text_type(1000, 0) = Field(default="")
    archived: bool = False


class Send(Strict):
    body: rich_text_type(20000, 0) = Field(default="")
    client_id: UUID
    parent_id: int | None = Field(default=None, gt=0)
    attachment_ids: list[int] = Field(default_factory=list, max_length=10)


class Edit(Strict):
    body: rich_text_type(20000, 1) = Field()


class MemberChange(Strict):
    user_id: int = Field(gt=0)


class Read(Strict):
    message_id: int = Field(ge=0)


class Mute(Strict):
    muted: bool


def commit_chat(db, wid, rid=None, extra_ids=()):
    from app.shared.communication.models import CommunicationEvent
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(211028004)"))
    db.add(CommunicationEvent(workspace_id=wid, conversation_id=rid))
    db.commit()
    # Send no conversation metadata or content. Recheck current room and workspace
    # membership before selecting recipients; removed members get only one revocation hint.
    from .realtime import broadcast_pms_event_from_thread

    room_ids = (
        db.query(Member.user_id).filter(
            Member.conversation_id == rid, Member.active.is_(True)
        )
        if rid
        else []
    )
    ids = [
        uid
        for uid, in db.query(PMSWorkspaceMember.user_id)
        .join(User, User.id == PMSWorkspaceMember.user_id)
        .filter(
            PMSWorkspaceMember.workspace_id == wid,
            User.is_active.is_(True),
            or_(
                PMSWorkspaceMember.user_id.in_(room_ids),
                PMSWorkspaceMember.user_id.in_(extra_ids),
            ),
        )
    ]
    broadcast_pms_event_from_thread(
        {"id": str(uuid4()), "type": "chat.invalidate", "recipientIds": ids}
    )


def workspace(db, wid, user, write=False):
    w, m = workspace_member(db, wid, user)
    if w.organization_id != organization_id_for(user):
        raise HTTPException(404, "Workspace not found")
    if not user.is_active or (write and m.role == "Guest"):
        raise HTTPException(403, "Active workspace collaborators required")
    return m


def eligible(db, wid, ids):
    org = db.get(PMSWorkspace, wid).organization_id
    found = {
        u.id
        for u in db.query(User)
        .join(PMSWorkspaceMember, User.id == PMSWorkspaceMember.user_id)
        .filter(
            PMSWorkspaceMember.workspace_id == wid,
            PMSWorkspaceMember.role != "Guest",
            User.is_active.is_(True),
            PMSWorkspaceMember.user_id.in_(ids),
        )
        .all()
        if organization_id_for(u) == org
    }
    if found != set(ids):
        raise HTTPException(422, "Choose active collaborators from this workspace")


def floor(db, rid):
    return db.query(func.max(Message.id)).filter_by(conversation_id=rid).scalar() or 0


def membership(db, room, uid):
    return db.get(Member, (room.id, uid))


def ensure_room(db, wid, key, **values):
    row = db.query(Room).filter_by(key=key).first()
    if not row:
        try:
            with db.begin_nested():
                row = Room(workspace_id=wid, key=key, **values)
                db.add(row)
                db.flush()
        except IntegrityError:
            row = db.query(Room).filter_by(key=key).one()
    return row


def sync_legacy(db, wid, user):
    """Lazy, repeat-safe backfill, no notifications. Legacy records and IDs remain intact."""
    from .models import PMSWorkspace

    db.query(PMSWorkspace).filter_by(id=wid).with_for_update().one()
    if db.get_bind().dialect.name == "sqlite":
        # SQLite has no row-level FOR UPDATE; serialize first-open backfills and
        # read-marker creation with a no-op write before checking source rows.
        db.execute(
            update(PMSWorkspace)
            .where(PMSWorkspace.id == wid)
            .values(name=PMSWorkspace.name)
        )
    owner = (
        db.query(PMSWorkspaceMember)
        .filter_by(workspace_id=wid, role="Owner")
        .order_by(PMSWorkspaceMember.id)
        .first()
    )
    general = ensure_room(
        db,
        wid,
        f"general:{wid}",
        kind="general",
        name="general",
        visibility="public",
        owner_id=owner.user_id if owner else user.id,
    )
    db.query(Room).filter_by(id=general.id).with_for_update().one()
    imported = 0
    for entry in (
        db.query(PMSWorkspaceEntry)
        .filter_by(workspace_id=wid, kind="chat")
        .filter(~exists().where(Message.legacy_entry_id == PMSWorkspaceEntry.id))
        .order_by(PMSWorkspaceEntry.id)
        .yield_per(200)
    ):
        db.add(
            Message(
                conversation_id=general.id,
                author_id=entry.author_id,
                body=entry.body,
                client_id=f"entry:{entry.id}",
                legacy_entry_id=entry.id,
                created_at=entry.created_at,
            )
        )
        imported += 1
        if imported % 200 == 0:
            db.flush()
    legacy = (
        db.query(PMSDirectConversation)
        .filter(
            PMSDirectConversation.workspace_id == wid,
            or_(
                PMSDirectConversation.first_user_id == user.id,
                PMSDirectConversation.second_user_id == user.id,
            ),
        )
        .all()
    )
    for old in legacy:
        room = ensure_room(
            db,
            wid,
            f"dm:{wid}:{old.first_user_id}:{old.second_user_id}",
            kind="dm",
            name="Direct message",
            owner_id=old.first_user_id,
            visibility="private",
            legacy_dm_id=old.id,
        )
        db.query(Room).filter_by(id=room.id).with_for_update().one()
        for uid in [old.first_user_id, old.second_user_id]:
            if not membership(db, room, uid):
                db.add(Member(conversation_id=room.id, user_id=uid))
        for msg in (
            db.query(PMSDirectMessage)
            .filter_by(conversation_id=old.id)
            .filter(
                ~exists().where(Message.legacy_dm_message_id == PMSDirectMessage.id)
            )
            .order_by(PMSDirectMessage.id)
            .yield_per(200)
        ):
            db.add(
                Message(
                    conversation_id=room.id,
                    author_id=msg.author_id,
                    body=msg.body,
                    client_id=msg.client_id,
                    legacy_dm_message_id=msg.id,
                    created_at=msg.created_at,
                )
            )
            imported += 1
            if imported % 200 == 0:
                db.flush()
    db.flush()
    if not membership(db, general, user.id):
        db.add(Member(conversation_id=general.id, user_id=user.id))
    db.commit()


def access(db, wid, rid, user, write=False, manage=False):
    wm = workspace(db, wid, user, write)
    if manage and wm.role == "Guest":
        raise HTTPException(403, "Guests cannot manage conversations")
    room = db.query(Room).filter_by(id=rid, workspace_id=wid).first()
    member = membership(db, room, user.id) if room else None
    if not room or not member or not member.active:
        raise HTTPException(404, "Conversation not found or membership ended")
    if (
        manage
        and room.owner_id != user.id
        and not (room.kind in {"channel", "general"} and wm.role in {"Owner", "Admin"})
    ):
        raise HTTPException(403, "Conversation manager required")
    if write and room.archived:
        raise HTTPException(409, "Archived conversations are read-only")
    if write and room.kind == "dm":
        eligible(
            db,
            wid,
            [
                m.user_id
                for m in db.query(Member).filter_by(conversation_id=rid, active=True)
            ],
        )
    from app.shared.communication.contexts import authorize_contexts
    authorize_contexts(db, user, rid)
    return room, member


def locked_access(db, wid, rid, user, write=False, manage=False):
    access(db, wid, rid, user, write, manage)
    db.query(Room).filter_by(id=rid).with_for_update().one()
    # Membership/role may have changed while waiting for a concurrent send or removal.
    db.expire_all()
    return access(db, wid, rid, user, write, manage)


def visible_query(db, room, member):
    return db.query(Message).filter(
        Message.conversation_id == room.id,
        Message.id > member.history_after,
        or_(Message.parent_id.is_(None), Message.parent_id > member.history_after),
    )


def unread(db, room, member, uid):
    return (
        visible_query(db, room, member)
        .filter(
            Message.id > member.read_id,
            Message.author_id != uid,
            Message.deleted_at.is_(None),
        )
        .count()
    )


def room_data(db, room, member, uid):
    from app.shared.communication.models import Preference, Draft
    from app.core.rich_text import rich_text_plain
    preference = db.get(Preference, (room.id, uid)) if member and member.active else None
    latest = visible_query(db, room, member).filter(Message.deleted_at.is_(None)).order_by(Message.id.desc()).first() if member and member.active else None
    ids = (
        db.query(Member.user_id)
        .join(
            PMSWorkspaceMember,
            and_(
                PMSWorkspaceMember.user_id == Member.user_id,
                PMSWorkspaceMember.workspace_id == room.workspace_id,
            ),
        )
        .filter(Member.conversation_id == room.id, Member.active.is_(True))
        .all()
    )
    users = (
        db.query(User)
        .filter(User.id.in_([i[0] for i in ids]), User.is_active.is_(True))
        .all()
    )
    return {
        "id": room.id,
        "kind": room.kind,
        "name": room.name,
        "description": room.description,
        "visibility": room.visibility,
        "archived": room.archived,
        "owner_id": room.owner_id,
        "joined": bool(member and member.active),
        "favorite": preference.favorite if preference else False,
        "has_draft": db.query(Draft).filter_by(conversation_id=room.id,user_id=uid).filter(Draft.body != "").first() is not None if member and member.active else False,
        "last_message": rich_text_plain(latest.body)[:120] if latest else "",
        "last_message_at": latest.created_at if latest else None,
        "muted": member.muted if member else False,
        "unread": unread(db, room, member, uid) if member and member.active else 0,
        "participants": (
            [{"id": u.id, "email": u.email} for u in users]
            if member and member.active
            else []
        ),
    }


def message_data(db, msg, member):
    from app.core.rich_text import rich_text_plain
    allowed_files = db.query(PMSFileAsset.id).filter(
        PMSFileAsset.project_id.in_(
            accessible_project_query(db, db.get(User, member.user_id)).with_entities(
                PMSProject.id
            )
        ),
        PMSFileAsset.deleted_at.is_(None),
    )
    attachments = (
        []
        if msg.deleted_at
        else [
            {
                "id": a.id,
                "name": a.name,
                "size": a.size,
                "mime": a.mime,
                "project_file_id": a.project_file_id,
            }
            for a in db.query(Attachment).filter(
                Attachment.message_id == msg.id,
                or_(
                    Attachment.project_file_id.is_(None),
                    Attachment.project_file_id.in_(allowed_files),
                ),
            )
        ]
    )
    replies = db.query(Message).filter(
        Message.parent_id == msg.id,
        Message.id > member.history_after,
        Message.deleted_at.is_(None),
    )
    last = replies.order_by(Message.id.desc()).first()
    root = (
        db.query(Message)
        .filter(
            Message.id == msg.parent_id,
            Message.conversation_id == msg.conversation_id,
            Message.id > member.history_after,
        )
        .first()
        if msg.parent_id
        else None
    )
    return {
        "id": msg.id,
        "author_id": msg.author_id,
        "body": "" if msg.deleted_at else msg.body,
        "parent_id": msg.parent_id,
        "root_preview": rich_text_plain(root.body)[:160] if root and not root.deleted_at else None,
        "created_at": msg.created_at,
        "edited_at": msg.edited_at,
        "deleted_at": msg.deleted_at,
        "reply_count": replies.count(),
        "latest_reply": rich_text_plain(last.body)[:120] if last else None,
        "attachments": attachments,
        "client_id": msg.client_id,
        "legacy_message_id": msg.legacy_dm_message_id,
        "legacy_entry_id": msg.legacy_entry_id,
    }


@router.get("/conversations")
def conversations(
    wid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    workspace(db, wid, user)
    sync_legacy(db, wid, user)
    member_ids = db.query(Member.conversation_id).filter_by(
        user_id=user.id, active=True
    )
    rooms = (
        db.query(Room)
        .filter(
            Room.workspace_id == wid,
            or_(Room.id.in_(member_ids), Room.visibility == "public"),
        )
        .order_by(Room.id)
        .all()
    )
    return {
        "conversations": [
            room_data(db, r, membership(db, r, user.id), user.id) for r in rooms if _context_visible(db, user, r.id)
        ],
        "user_id": user.id,
        "can_send": workspace(db, wid, user).role != "Guest",
    }


@router.post("/conversations", status_code=201)
def create_room(
    wid: int,
    data: RoomInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wm = workspace(db, wid, user, True)
    if data.kind == "channel" and wm.role not in {"Owner", "Admin"}:
        raise HTTPException(403, "Workspace administrators create channels")
    ids = sorted(set(data.participants + [user.id]))
    eligible(db, wid, ids)
    if data.kind == "dm" and len(ids) != 2:
        raise HTTPException(422, "Choose exactly one other collaborator")
    if data.kind == "group" and len(ids) < 3:
        raise HTTPException(422, "Group messages need at least three participants")
    if data.kind == "channel" and not data.name.strip():
        raise HTTPException(422, "Channel name is required")
    if data.kind == "dm":
        from .direct_messages import start_conversation, StartInput

        start_conversation(
            wid, StartInput(user_id=next(i for i in ids if i != user.id)), db, user
        )
        sync_legacy(db, wid, user)
        room = db.query(Room).filter_by(key=f"dm:{wid}:{ids[0]}:{ids[1]}").one()
    else:
        room = Room(
            workspace_id=wid,
            key=str(uuid4()),
            kind=data.kind,
            name=data.name.strip() or "Group message",
            description=data.description,
            visibility=data.visibility if data.kind == "channel" else "private",
            owner_id=user.id,
        )
        db.add(room)
        db.flush()
        for uid in ids:
            db.add(Member(conversation_id=room.id, user_id=uid))
        commit_chat(db, wid, room.id)
    return room_data(db, room, membership(db, room, user.id), user.id)


@router.put("/conversations/{rid}")
def edit_room(
    wid: int,
    rid: int,
    data: RoomEdit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room, member = locked_access(db, wid, rid, user, manage=True)
    if room.kind == "dm" or not data.name.strip():
        raise HTTPException(422, "Use a nonblank channel or group name")
    room.name = data.name.strip()
    room.description = data.description
    room.archived = data.archived
    commit_chat(db, wid, rid)
    return room_data(db, room, member, user.id)


@router.post("/conversations/{rid}/join")
def join(
    wid: int,
    rid: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace(db, wid, user, True)
    room = (
        db.query(Room)
        .filter_by(id=rid, workspace_id=wid, visibility="public", archived=False)
        .with_for_update()
        .first()
    )
    if not room:
        raise HTTPException(404, "Public channel not found")
    member = membership(db, room, user.id)
    if not member:
        member = Member(conversation_id=rid, user_id=user.id)
        db.add(member)
    member.active = True
    commit_chat(db, wid, rid)
    return room_data(db, room, member, user.id)


@router.post("/conversations/{rid}/members")
def add_member(
    wid: int,
    rid: int,
    data: MemberChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room, _ = locked_access(db, wid, rid, user, write=True, manage=True)
    if room.kind == "dm":
        raise HTTPException(
            409, "Create a new group; direct-message history stays private"
        )
    eligible(db, wid, [data.user_id])
    m = membership(db, room, data.user_id)
    if m and m.active:
        return {"ok": True}
    if not m:
        m = Member(conversation_id=rid, user_id=data.user_id)
        db.add(m)
    m.history_after = floor(db, rid)
    m.read_id = m.history_after
    m.active = True
    commit_chat(db, wid, rid)
    return {"ok": True}


@router.delete("/conversations/{rid}/members/{uid}")
def remove_member(
    wid: int,
    rid: int,
    uid: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room, _ = locked_access(db, wid, rid, user, manage=uid != user.id)
    if room.kind in {"dm", "general"}:
        raise HTTPException(409, "This membership cannot be removed")
    if uid == room.owner_id:
        if room.kind != "group" or uid != user.id:
            raise HTTPException(409, "Channel owners must archive rather than leave")
        successor = (
            db.query(Member)
            .join(
                PMSWorkspaceMember,
                and_(
                    PMSWorkspaceMember.user_id == Member.user_id,
                    PMSWorkspaceMember.workspace_id == wid,
                ),
            )
            .filter(
                Member.conversation_id == rid,
                Member.active.is_(True),
                Member.user_id != uid,
                PMSWorkspaceMember.role != "Guest",
            )
            .order_by(Member.user_id)
            .first()
        )
        if not successor:
            raise HTTPException(
                409, "No eligible successor; archive this group instead"
            )
        room.owner_id = successor.user_id
    m = membership(db, room, uid)
    if m:
        m.active = False
        commit_chat(db, wid, rid, extra_ids=[uid])
    return {"ok": True}


@router.get("/conversations/{rid}/messages")
def history(
    wid: int,
    rid: int,
    before: int | None = Query(None, gt=0),
    parent_id: int | None = Query(None, gt=0),
    around: int | None = Query(None, gt=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room, m = access(db, wid, rid, user)
    sync_legacy(db, wid, user)
    room, m = access(db, wid, rid, user)
    q = visible_query(db, room, m)
    root = None
    if parent_id:
        root = q.filter(Message.id == parent_id, Message.parent_id.is_(None)).first()
        if not root:
            raise HTTPException(404, "Thread not found")
    if around:
        target = q.filter(Message.id == around).first()
        if not target:
            raise HTTPException(404, "Message not found")
        parent_id = target.parent_id
        before = around + 1
        root = q.filter(Message.id == parent_id).first() if parent_id else None
    q = q.filter(Message.parent_id == parent_id)
    if before:
        q = q.filter(Message.id < before)
    rows = q.order_by(Message.id.desc()).limit(limit + 1).all()
    return {
        "messages": [message_data(db, r, m) for r in reversed(rows[:limit])],
        "before": rows[limit - 1].id if len(rows) > limit else None,
        "root": message_data(db, root, m) if root else None,
        "thread_id": parent_id,
        "read_through": floor(db, rid),
    }


@router.post("/conversations/{rid}/messages")
def send(
    wid: int,
    rid: int,
    data: Send,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room, m = locked_access(db, wid, rid, user, True)
    body = data.body.strip()
    if not body and not data.attachment_ids:
        raise HTTPException(422, "Write a message or attach a file")
    if len(set(data.attachment_ids)) != len(data.attachment_ids):
        raise HTTPException(422, "Duplicate attachment")
    previous = (
        db.query(Message)
        .filter_by(
            conversation_id=rid, author_id=user.id, client_id=str(data.client_id)
        )
        .first()
    )
    if previous:
        if (
            previous.body != body
            or previous.parent_id != data.parent_id
            or sorted(
                a.id for a in db.query(Attachment).filter_by(message_id=previous.id)
            )
            != sorted(data.attachment_ids)
        ):
            raise HTTPException(409, "Request ID already used")
        return message_data(db, previous, m)
    if (
        data.parent_id
        and not visible_query(db, room, m)
        .filter(
            Message.id == data.parent_id,
            Message.parent_id.is_(None),
            Message.deleted_at.is_(None),
        )
        .first()
    ):
        raise HTTPException(422, "Choose a visible root message in this conversation")
    if (
        db.query(Message)
        .filter(
            Message.author_id == user.id,
            Message.created_at > datetime.utcnow() - timedelta(minutes=1),
        )
        .count()
        >= 60
    ):
        raise HTTPException(429, "Please wait before sending more messages")
    files = (
        db.query(Attachment)
        .filter(
            Attachment.id.in_(data.attachment_ids),
            Attachment.owner_id == user.id,
            Attachment.conversation_id == rid,
            Attachment.message_id.is_(None),
            Attachment.created_at > datetime.utcnow() - timedelta(hours=24),
        )
        .with_for_update()
        .all()
    )
    if len(files) != len(data.attachment_ids):
        raise HTTPException(422, "Attachment unavailable, expired, or already used")
    for a in files:
        if a.project_file_id:
            f = db.get(PMSFileAsset, a.project_file_id)
            if not f or f.deleted_at:
                raise HTTPException(422, "Project file is no longer available")
            get_project_for_action(db, f.project_id, user, "browse")
    msg = Message(
        conversation_id=rid,
        author_id=user.id,
        body=body,
        parent_id=data.parent_id,
        client_id=str(data.client_id),
    )
    try:
        with db.begin_nested():
            db.add(msg)
            db.flush()
            for a in files:
                if (
                    db.execute(
                        update(Attachment)
                        .where(Attachment.id == a.id, Attachment.message_id.is_(None))
                        .values(message_id=msg.id)
                    ).rowcount
                    != 1
                ):
                    raise HTTPException(409, "Attachment was already sent")
            # Legacy main timelines remain usable. Replies stay in the thread timeline.
            if room.legacy_dm_id and not data.parent_id:
                old = PMSDirectMessage(
                    conversation_id=room.legacy_dm_id,
                    author_id=user.id,
                    body=body or "[Attachment]",
                    client_id=str(data.client_id),
                )
                db.add(old)
                db.flush()
                msg.legacy_dm_message_id = old.id
            if room.kind == "general" and not data.parent_id:
                old = PMSWorkspaceEntry(
                    workspace_id=wid,
                    author_id=user.id,
                    kind="chat",
                    body=body or "[Attachment]",
                )
                db.add(old)
                db.flush()
                msg.legacy_entry_id = old.id
            recipients = (
                db.query(Member)
                .join(
                    PMSWorkspaceMember,
                    and_(
                        PMSWorkspaceMember.user_id == Member.user_id,
                        PMSWorkspaceMember.workspace_id == wid,
                    ),
                )
                .join(User, User.id == Member.user_id)
                .filter(
                    Member.conversation_id == rid,
                    Member.active.is_(True),
                    Member.muted.is_(False),
                    Member.user_id != user.id,
                    User.is_active.is_(True),
                )
                .all()
            )
            for recipient in recipients:
                from app.shared.communication.reminders import should_notify
                if not should_notify(db, rid, db.get(User, recipient.user_id), body):
                    continue
                if not _context_visible(db, db.get(User, recipient.user_id), rid):
                    continue
                if data.parent_id and data.parent_id <= recipient.history_after:
                    continue
                db.add(
                    Notification(
                        company_id=organization_id_for(user),
                        user_id=recipient.user_id,
                        title="New workspace message",
                        message="Open Messages to view an update in a conversation you joined.",
                        module="project_management",
                        event_type="chat.message",
                        related_entity_type="pms_chat",
                        related_entity_id=msg.id,
                        action_url=f"/pms/messages?workspace={wid}&conversation={rid}&message={msg.id}"
                        + (f"&thread={data.parent_id}" if data.parent_id else ""),
                    )
                )
        commit_chat(db, wid, rid)
    except IntegrityError:
        previous = (
            db.query(Message)
            .filter_by(
                conversation_id=rid, author_id=user.id, client_id=str(data.client_id)
            )
            .first()
        )
        if not previous:
            raise HTTPException(
                409, "Concurrent message request; retry with the same ID"
            )
        if (
            previous.body != body
            or previous.parent_id != data.parent_id
            or sorted(
                a.id for a in db.query(Attachment).filter_by(message_id=previous.id)
            )
            != sorted(data.attachment_ids)
        ):
            raise HTTPException(409, "Request ID already used")
        return message_data(db, previous, m)
    return message_data(db, msg, m)


@router.patch("/conversations/{rid}/messages/{mid}")
def edit_message(
    wid: int,
    rid: int,
    mid: int,
    data: Edit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room, m = locked_access(db, wid, rid, user, True)
    msg = (
        visible_query(db, room, m)
        .filter(
            Message.id == mid,
            Message.author_id == user.id,
            Message.deleted_at.is_(None),
        )
        .first()
    )
    if not msg:
        raise HTTPException(404, "Message not found")
    if not data.body.strip():
        raise HTTPException(422, "Message cannot be blank")
    from app.shared.communication.models import Revision
    db.add(Revision(workspace_id=wid, message_id=mid, user_id=user.id, body=msg.body))
    msg.body = data.body.strip()
    msg.edited_at = datetime.utcnow()
    if msg.legacy_dm_message_id:
        db.get(PMSDirectMessage, msg.legacy_dm_message_id).body = msg.body
    if msg.legacy_entry_id:
        db.get(PMSWorkspaceEntry, msg.legacy_entry_id).body = msg.body
    commit_chat(db, wid, rid)
    return message_data(db, msg, m)


@router.delete("/conversations/{rid}/messages/{mid}")
def delete_message(
    wid: int,
    rid: int,
    mid: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room, m = locked_access(db, wid, rid, user, True)
    msg = (
        visible_query(db, room, m)
        .filter(Message.id == mid, Message.author_id == user.id)
        .first()
    )
    if not msg:
        raise HTTPException(404, "Message not found")
    msg.deleted_at = datetime.utcnow()
    if msg.legacy_dm_message_id:
        db.get(PMSDirectMessage, msg.legacy_dm_message_id).body = "[Deleted message]"
    if msg.legacy_entry_id:
        db.get(PMSWorkspaceEntry, msg.legacy_entry_id).body = "[Deleted message]"
    commit_chat(db, wid, rid)
    return {"ok": True}


@router.put("/conversations/{rid}/read")
def read(
    wid: int,
    rid: int,
    data: Read,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room, m = locked_access(db, wid, rid, user)
    target = min(data.message_id, floor(db, rid))
    db.execute(
        update(Member)
        .where(
            Member.conversation_id == rid,
            Member.user_id == user.id,
            Member.read_id < target,
        )
        .values(read_id=target)
    )
    commit_chat(db, wid, rid)
    return {"unread": unread(db, room, m, user.id)}


@router.put("/conversations/{rid}/mute")
def mute(
    wid: int,
    rid: int,
    data: Mute,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _, m = locked_access(db, wid, rid, user)
    m.muted = data.muted
    commit_chat(db, wid, rid)
    return {"ok": True}


@router.post("/read-all")
def read_all(
    wid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    workspace(db, wid, user)
    for m in (
        db.query(Member)
        .join(Room, Room.id == Member.conversation_id)
        .filter(
            Room.workspace_id == wid, Member.user_id == user.id, Member.active.is_(True), Room.id.notin_(denied_rooms(db,user,wid))
        )
    ):
        target = floor(db, m.conversation_id)
        db.execute(
            update(Member)
            .where(
                Member.conversation_id == m.conversation_id,
                Member.user_id == user.id,
                Member.read_id < target,
            )
            .values(read_id=target)
        )
    commit_chat(db, wid, extra_ids=[user.id])
    return {"ok": True}


@router.get("/search")
def search(
    wid: int,
    q: str = Query("", max_length=200),
    conversation_id: int | None = None,
    author_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    attachments: bool = False,
    before: int | None = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace(db, wid, user)
    if len(q.split()) > 12:
        raise HTTPException(422, "Use at most 12 search words")
    date_from = (
        date_from.astimezone(timezone.utc).replace(tzinfo=None)
        if date_from and date_from.tzinfo
        else date_from
    )
    date_to = (
        date_to.astimezone(timezone.utc).replace(tzinfo=None)
        if date_to and date_to.tzinfo
        else date_to
    )
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Start date must precede end date")
    sync_legacy(db, wid, user)
    workspace(db, wid, user)
    query = (
        db.query(Message, Room, Member)
        .join(Room, Room.id == Message.conversation_id)
        .join(
            Member,
            and_(
                Member.conversation_id == Room.id,
                Member.user_id == user.id,
                Member.active.is_(True),
            ),
        )
        .filter(
            Room.workspace_id == wid,
            Message.id > Member.history_after,
            or_(Message.parent_id.is_(None), Message.parent_id > Member.history_after),
            Message.deleted_at.is_(None),
        )
    )
    query = query.filter(Room.id.notin_(denied_rooms(db, user, wid)))
    files = db.query(PMSFileAsset.id).filter(
        PMSFileAsset.project_id.in_(
            accessible_project_query(db, user).with_entities(PMSProject.id)
        ),
        PMSFileAsset.deleted_at.is_(None),
    )
    for term in q.split()[:12]:
        filename = (
            exists()
            .where(Attachment.message_id == Message.id)
            .where(
                or_(
                    Attachment.project_file_id.is_(None),
                    Attachment.project_file_id.in_(files),
                )
            )
            .where(
                Attachment.name.ilike(
                    "%" + term.replace("%", "\\%").replace("_", "\\_") + "%",
                    escape="\\",
                )
            )
        )
        body_match = (
            (
                func.to_tsvector(literal_column("'simple'"), Message.body).op("@@")(
                    func.plainto_tsquery(literal_column("'simple'"), term)
                )
            )
            if db.get_bind().dialect.name == "postgresql"
            else Message.body.ilike(
                "%" + term.replace("%", "\\%").replace("_", "\\_") + "%", escape="\\"
            )
        )
        query = query.filter(or_(body_match, filename))
    if conversation_id:
        query = query.filter(Room.id == conversation_id)
    if author_id:
        query = query.filter(Message.author_id == author_id)
    if date_from:
        query = query.filter(Message.created_at >= date_from)
    if date_to:
        query = query.filter(Message.created_at <= date_to)
    if attachments:
        query = query.filter(
            exists()
            .where(Attachment.message_id == Message.id)
            .where(
                or_(
                    Attachment.project_file_id.is_(None),
                    Attachment.project_file_id.in_(files),
                )
            )
        )
    if before:
        query = query.filter(Message.id < before)
    rows = query.order_by(Message.id.desc()).limit(51).all()
    return {
        "results": [
            {
                **message_data(db, msg, m),
                "conversation_id": r.id,
                "conversation_name": r.name,
                "root_id": msg.parent_id,
            }
            for msg, r, m in rows[:50]
        ],
        "before": rows[49][0].id if len(rows) > 50 else None,
    }


ALLOWED = {
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".zip": "application/zip",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.post("/conversations/{rid}/attachments", status_code=201)
def upload(
    wid: int,
    rid: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    access(db, wid, rid, user, True)
    if (
        db.query(Attachment)
        .filter(
            Attachment.owner_id == user.id,
            Attachment.created_at > datetime.utcnow() - timedelta(hours=1),
        )
        .count()
        >= 100
    ):
        raise HTTPException(429, "Upload limit reached; try again later")
    name = Path((file.filename or "file").replace("\\", "/")).name
    name = "".join(c for c in name if c.isprintable())[:180]
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(422, "Unsupported file type")
    limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    payload = file.file.read(limit + 1)
    if len(payload) > limit:
        raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB")
    if not payload:
        raise HTTPException(422, "File is empty")
    if payload.startswith((b"MZ", b"\x7fELF")):
        raise HTTPException(422, "Executable files are not allowed")
    if suffix == ".pdf" and not payload.startswith(b"%PDF-"):
        raise HTTPException(422, "Invalid PDF")
    if suffix == ".png" and not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(422, "Invalid PNG")
    if suffix in {".jpg", ".jpeg"} and not payload.startswith(b"\xff\xd8\xff"):
        raise HTTPException(422, "Invalid JPEG")
    if suffix == ".webp" and not (
        payload.startswith(b"RIFF") and payload[8:12] == b"WEBP"
    ):
        raise HTTPException(422, "Invalid WebP")
    if suffix in {".zip", ".docx", ".xlsx"} and not payload.startswith(b"PK"):
        raise HTTPException(422, "Invalid archive file")
    path = (
        Path(settings.UPLOAD_DIR).resolve()
        / "pms"
        / "chat"
        / str(rid)
        / (str(uuid4()) + suffix)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    try:
        persist_file(str(path))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    row = Attachment(
        conversation_id=rid,
        owner_id=user.id,
        name=name,
        mime=ALLOWED[suffix],
        size=len(payload),
        path=str(path),
    )
    db.add(row)
    commit_chat(db, wid, rid)
    db.refresh(row)
    return {"id": row.id, "name": row.name, "size": row.size, "mime": row.mime}


class ShareFile(Strict):
    file_id: int = Field(gt=0)


@router.get("/project-files")
def project_files(
    wid: int,
    before: int | None = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace(db, wid, user)
    q = (
        db.query(PMSFileAsset)
        .join(PMSProject, PMSProject.id == PMSFileAsset.project_id)
        .filter(
            PMSProject.workspace_id == wid,
            PMSFileAsset.deleted_at.is_(None),
            PMSFileAsset.project_id.in_(
                accessible_project_query(db, user).with_entities(PMSProject.id)
            ),
        )
    )
    if before:
        q = q.filter(PMSFileAsset.id < before)
    rows = q.order_by(PMSFileAsset.id.desc()).limit(51).all()
    return {
        "items": [
            {
                "id": f.id,
                "name": f.original_name or f.file_name,
                "size": f.size_bytes or 0,
            }
            for f in rows[:50]
        ],
        "before": rows[49].id if len(rows) > 50 else None,
    }


@router.post("/conversations/{rid}/project-file", status_code=201)
def share_file(
    wid: int,
    rid: int,
    data: ShareFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    access(db, wid, rid, user, True)
    f = db.query(PMSFileAsset).filter_by(id=data.file_id, deleted_at=None).first()
    if not f or not f.project_id:
        raise HTTPException(404, "Project file not found")
    project = get_project_for_action(db, f.project_id, user, "browse")
    if project.workspace_id != wid:
        raise HTTPException(422, "File must belong to this workspace")
    a = Attachment(
        conversation_id=rid,
        owner_id=user.id,
        name=(f.original_name or f.file_name)[:180],
        mime=(
            f.mime_type
            if f.mime_type and not f.mime_type.startswith("image/")
            else "application/octet-stream"
        ),
        size=f.size_bytes or 0,
        path=f.storage_path,
        project_file_id=f.id,
    )
    db.add(a)
    commit_chat(db, wid, rid)
    db.refresh(a)
    return {"id": a.id, "name": a.name, "size": a.size, "mime": a.mime}


@router.delete("/conversations/{rid}/attachments/{aid}")
def cancel_upload(
    wid: int,
    rid: int,
    aid: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    access(db, wid, rid, user, True)
    a = (
        db.query(Attachment)
        .filter_by(id=aid, conversation_id=rid, owner_id=user.id, message_id=None)
        .first()
    )
    if not a:
        raise HTTPException(404, "Unused upload not found")
    if not a.project_file_id:
        from .chat_cleanup import delete_chat_blob

        delete_chat_blob(a.path)
    db.delete(a)
    commit_chat(db, wid, rid)
    return {"ok": True}


@router.get("/conversations/{rid}/attachments/{aid}")
def download(
    wid: int,
    rid: int,
    aid: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room, m = access(db, wid, rid, user)
    a = db.query(Attachment).filter_by(id=aid, conversation_id=rid).first()
    if not a:
        raise HTTPException(404, "Attachment not found")
    if a.message_id:
        if (
            not visible_query(db, room, m)
            .filter(Message.id == a.message_id, Message.deleted_at.is_(None))
            .first()
        ):
            raise HTTPException(404, "Attachment not found")
    elif a.owner_id != user.id or a.created_at < datetime.utcnow() - timedelta(
        hours=24
    ):
        raise HTTPException(404, "Attachment not found")
    if a.project_file_id:
        f = db.get(PMSFileAsset, a.project_file_id)
        if not f or f.deleted_at:
            raise HTTPException(404, "Project file unavailable")
        get_project_for_action(db, f.project_id, user, "browse")
    if not upload_exists(a.path):
        raise HTTPException(404, "Stored file unavailable")
    path = materialize_file(a.path)
    # Proxy bytes after authorization; never return a reusable public storage URL.
    from fastapi.responses import FileResponse

    return FileResponse(
        path,
        filename=a.name,
        media_type=a.mime,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
