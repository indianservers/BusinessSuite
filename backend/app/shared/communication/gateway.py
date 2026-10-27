"""Common API facade. Delegates to existing services without a PMS module grant.
Every delegated endpoint still enforces current workspace/conversation membership.
"""
from pydantic import Field
from inspect import signature
from functools import wraps
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.apps.project_management import chat, workspaces
from . import api
from .models import ConversationContext
from .contexts import resolve

router = APIRouter(prefix="/collaboration", tags=["BusinessSuite Communication Engine"])


def delegate(endpoint):
    @wraps(endpoint)
    def call(*args, **kwargs):
        return endpoint(*args, **kwargs)
    call.__signature__ = signature(endpoint, eval_str=True)
    return call


for source in [chat.router, api.router]:
    for route in source.routes:
        router.add_api_route(route.path, delegate(route.endpoint), methods=list(route.methods), response_model=route.response_model, status_code=route.status_code)
router.add_api_route("/unread", delegate(chat.unread_summary), methods=["GET"])
router.add_api_route("/workspaces", delegate(workspaces.list_workspaces), methods=["GET"])
router.add_api_route("/workspaces/{workspace_id}/members", delegate(workspaces.members), methods=["GET"])


@router.get("/contexts/lookup")
def lookup(workspace_id: int, module: str, entity_type: str, entity_id: int = Query(gt=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chat.workspace(db, workspace_id, user)
    resolve(db, user, module, entity_type, entity_id)
    row = db.query(ConversationContext).filter_by(workspace_id=workspace_id, module=module, entity_type=entity_type, entity_id=entity_id).first()
    if not row: return {"conversation_id": None}
    chat.access(db, workspace_id, row.conversation_id, user)
    return {"conversation_id": row.conversation_id}


@router.get("/workspaces/{wid}/projects")
def task_projects(wid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    chat.workspace(db, wid, user)
    from app.apps.project_management.access import accessible_project_query, can_access_project
    from app.apps.project_management.models import PMSProject
    rows = accessible_project_query(db, user).filter(PMSProject.workspace_id == wid).limit(200).all()
    return [{"id": p.id, "name": p.name} for p in rows if can_access_project(db, p, user, "manage_tasks")]


@router.get("/tasks/{task_id}/source")
def task_source(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.apps.project_management.access import get_task_project_for_action
    from .models import FollowUp
    get_task_project_for_action(db, task_id, user, "browse")
    row = db.query(FollowUp).filter_by(task_id=task_id).first()
    if not row: return {"source": None}
    api.message(db, row.workspace_id, row.conversation_id, row.message_id, user)
    return {"source": api.followup_data(db, row, user)}


@router.get("/events")
def events(cursor: int | None = Query(None, ge=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from sqlalchemy import func, or_
    from .models import CommunicationEvent
    from app.apps.project_management.chat_models import ChatMember
    from app.apps.project_management.models import PMSWorkspaceMember
    member_workspaces = db.query(PMSWorkspaceMember.workspace_id).filter_by(user_id=user.id)
    member_rooms = db.query(ChatMember.conversation_id).filter_by(user_id=user.id, active=True)
    query = db.query(CommunicationEvent).filter(CommunicationEvent.workspace_id.in_(member_workspaces), or_(CommunicationEvent.conversation_id.is_(None), CommunicationEvent.conversation_id.in_(member_rooms)))
    from .contexts import denied_rooms
    query = query.filter(or_(CommunicationEvent.conversation_id.is_(None), CommunicationEvent.conversation_id.notin_(denied_rooms(db,user))))
    high = query.with_entities(func.max(CommunicationEvent.id)).scalar() or 0
    if cursor is None: return {"cursor": high,"changed":False}
    rows = query.filter(CommunicationEvent.id>cursor).order_by(CommunicationEvent.id).limit(100).all()
    return {"cursor":rows[-1].id if rows else max(cursor,high),"changed":bool(rows)}


class StartContext(api.ContextInput):
    workspace_id: int = Field(gt=0)


@router.post("/context-conversations", status_code=201)
def start_context(data: StartContext, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.apps.project_management.models import PMSWorkspace
    chat.workspace(db,data.workspace_id,user,True)
    # Serialize canonical context creation without rebuilding or duplicating records.
    db.query(PMSWorkspace).filter_by(id=data.workspace_id).with_for_update().one()
    resolve(db,user,data.module,data.entity_type,data.entity_id)
    existing = db.query(ConversationContext).filter_by(workspace_id=data.workspace_id,module=data.module,entity_type=data.entity_type,entity_id=data.entity_id).first()
    if existing:
        chat.access(db,data.workspace_id,existing.conversation_id,user)
        return {"conversation_id":existing.conversation_id}
    from app.apps.project_management.chat_models import ChatConversation, ChatMember
    from uuid import uuid4
    room=ChatConversation(workspace_id=data.workspace_id,key=str(uuid4()),kind="group",name=f"{data.entity_type.title()} #{data.entity_id}",description="Internal authorized record discussion",visibility="private",owner_id=user.id)
    db.add(room);db.flush()
    db.add(ChatMember(conversation_id=room.id,user_id=user.id,active=True,history_after=0,read_id=0))
    db.add(ConversationContext(workspace_id=data.workspace_id,conversation_id=room.id,module=data.module,entity_type=data.entity_type,entity_id=data.entity_id,created_by=user.id))
    api.audit(db,data.workspace_id,user,"chat.context.created",room.id)
    chat.commit_chat(db,data.workspace_id,room.id)
    return {"conversation_id":room.id}
