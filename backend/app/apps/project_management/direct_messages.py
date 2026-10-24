"""Private workspace messages; only current participants can read conversations."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSDirectConversation, PMSDirectMessage, PMSWorkspaceMember
from .workspaces import workspace_member

router = APIRouter()


class StartInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0)


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=20000)
    client_id: UUID


def conversation_data(db, row):
    users = db.query(User).filter(User.id.in_([row.first_user_id, row.second_user_id])).all()
    return {"id": row.id, "participants": [{"id": user.id, "email": user.email} for user in users], "created_at": row.created_at}


def message_data(row):
    return {"id": row.id, "author_id": row.author_id, "body": row.body, "created_at": row.created_at}


def access(db, workspace_id, conversation_id, user, write=False):
    _, member = workspace_member(db, workspace_id, user)
    row = db.query(PMSDirectConversation).filter_by(id=conversation_id, workspace_id=workspace_id).first()
    if not row or user.id not in {row.first_user_id, row.second_user_id}:
        raise HTTPException(404, "Conversation not found")
    if write:
        eligible = db.query(PMSWorkspaceMember).join(User, User.id == PMSWorkspaceMember.user_id).filter(
            PMSWorkspaceMember.workspace_id == workspace_id,
            PMSWorkspaceMember.user_id.in_([row.first_user_id, row.second_user_id]),
            PMSWorkspaceMember.role != "Guest", User.is_active == True).count()
        if member.role == "Guest" or eligible != 2:
            raise HTTPException(403, "Both participants must be active workspace collaborators to send messages")
    return row


@router.get("/workspaces/{workspace_id}/direct-conversations")
def list_conversations(workspace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = workspace_member(db, workspace_id, user)
    rows = db.query(PMSDirectConversation).filter(PMSDirectConversation.workspace_id == workspace_id,
        or_(PMSDirectConversation.first_user_id == user.id, PMSDirectConversation.second_user_id == user.id)).order_by(PMSDirectConversation.id.desc()).all()
    return {"conversations": [conversation_data(db, row) for row in rows], "can_send": member.role != "Guest", "user_id": user.id}


@router.post("/workspaces/{workspace_id}/direct-conversations")
def start_conversation(workspace_id: int, data: StartInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = workspace_member(db, workspace_id, user)
    if member.role == "Guest":
        raise HTTPException(403, "Guests have read-only access")
    if data.user_id == user.id:
        raise HTTPException(422, "Choose another collaborator")
    target = db.query(PMSWorkspaceMember).join(User, User.id == PMSWorkspaceMember.user_id).filter(
        PMSWorkspaceMember.workspace_id == workspace_id, PMSWorkspaceMember.user_id == data.user_id,
        PMSWorkspaceMember.role != "Guest", User.is_active == True).first()
    if not target:
        raise HTTPException(422, "Choose an active collaborator in this workspace")
    first, second = sorted([user.id, data.user_id])
    query = lambda: db.query(PMSDirectConversation).filter_by(workspace_id=workspace_id, first_user_id=first, second_user_id=second).first()
    row = query()
    if not row:
        row = PMSDirectConversation(workspace_id=workspace_id, first_user_id=first, second_user_id=second)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = query()
            if not row:
                raise
    return conversation_data(db, row)


@router.get("/workspaces/{workspace_id}/direct-conversations/{conversation_id}/messages")
def list_messages(workspace_id: int, conversation_id: int, before: int | None = Query(None, gt=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    access(db, workspace_id, conversation_id, user)
    query = db.query(PMSDirectMessage).filter_by(conversation_id=conversation_id)
    if before:
        query = query.filter(PMSDirectMessage.id < before)
    rows = query.order_by(PMSDirectMessage.id.desc()).limit(101).all()
    return {"messages": [message_data(row) for row in reversed(rows[:100])], "has_more": len(rows) > 100}


@router.post("/workspaces/{workspace_id}/direct-conversations/{conversation_id}/messages")
def send_message(workspace_id: int, conversation_id: int, data: MessageInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    access(db, workspace_id, conversation_id, user, write=True)
    from .chat import sync_legacy, send, Send
    from .chat_models import ChatConversation
    sync_legacy(db, workspace_id, user)
    room = db.query(ChatConversation).filter_by(legacy_dm_id=conversation_id).one()
    value = send(workspace_id, room.id, Send(body=data.body, client_id=data.client_id), db, user)
    return message_data(db.get(PMSDirectMessage, value["legacy_message_id"]))
