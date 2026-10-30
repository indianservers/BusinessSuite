from app.core.rich_text import rich_text_type
"""Workspace collaboration, with email-bound, single-use invitations."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User, Role as UserRole
from app.models.notification import Notification
from .models import PMSWorkspace, PMSWorkspaceMember, PMSWorkspaceInvitation, PMSProject, PMSTask, PMSComment, PMSWorkspaceEntry
from .models import PMSActivity
from .access import has_any_permission, PMS_GLOBAL_MANAGE_PROJECTS, organization_id_for

from .workspace_lifecycle import is_archived, archived_ids

router = APIRouter()
Role = Literal["Admin", "Member", "Guest"]


@router.get("/workspaces/{workspace_id}/activity")
def workspace_activity(workspace_id: int, before: int | None = Query(None, gt=0), action: str = Query("", max_length=80), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user, True)
    query = db.query(PMSActivity, User.email).join(PMSProject, PMSProject.id == PMSActivity.project_id).outerjoin(User, User.id == PMSActivity.actor_user_id).filter(PMSProject.workspace_id == workspace_id)
    if before:
        query = query.filter(PMSActivity.id < before)
    if action.strip():
        query = query.filter(PMSActivity.action.ilike("%" + action.strip() + "%"))
    rows = query.order_by(PMSActivity.id.desc()).limit(limit + 1).all()
    return {"items": [{"id": event.id, "action": event.action, "summary": event.summary, "actor": email or "System", "task_id": event.task_id, "created_at": event.created_at} for event, email in rows[:limit]], "next_cursor": rows[limit - 1][0].id if len(rows) > limit else None}


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)


class InviteInput(BaseModel):
    email: str = Field(min_length=3, max_length=100, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    role: Role = "Member"


class MemberInput(BaseModel):
    role: Role


class AddMemberInput(MemberInput):
    user_id: int = Field(gt=0)


def share_token(invitation):
    """Reconstruct new invitation links without storing bearer tokens in plaintext."""
    from app.core.config import settings
    payload = f"pms-workspace-invitation:v1:{invitation.id}:{invitation.workspace_id}:{invitation.email}"
    return hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


@router.get("/workspace-invitations/mine")
def my_invitations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(PMSWorkspaceInvitation, PMSWorkspace.name).join(PMSWorkspace, PMSWorkspace.id == PMSWorkspaceInvitation.workspace_id).filter(
        PMSWorkspaceInvitation.email == user.email.strip().lower(), PMSWorkspaceInvitation.status == "pending",
        PMSWorkspaceInvitation.expires_at > datetime.utcnow(), PMSWorkspace.organization_id == organization_id_for(user),
        PMSWorkspace.id.notin_(archived_ids())).all()
    return [{"id": i.id, "workspace": name, "role": i.role, "expires_at": i.expires_at} for i, name in rows]


@router.post("/workspace-invitations/{invitation_id}/accept")
def accept_my_invitation(invitation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invitation = db.query(PMSWorkspaceInvitation).filter_by(id=invitation_id, email=user.email.strip().lower()).with_for_update().first()
    if not invitation:
        raise HTTPException(404, "Invitation not found")
    return _accept_invitation(db, invitation, user)


class AcceptInput(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ActivateInput(AcceptInput):
    password: str = Field(min_length=12, max_length=72)


def pending_invitation(db, token, *, lock=False):
    query = db.query(PMSWorkspaceInvitation).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest())
    invitation = (query.with_for_update() if lock else query).first()
    if not invitation or invitation.status != "pending" or invitation.expires_at <= datetime.utcnow() or is_archived(db, invitation.workspace_id):
        raise HTTPException(400, "Invitation is invalid, expired, or already used")
    return invitation


@router.get("/workspace-invitations/preview")
def preview_invitation(token: str, db: Session = Depends(get_db)):
    invitation = pending_invitation(db, token)
    workspace = db.get(PMSWorkspace, invitation.workspace_id)
    if not workspace:
        raise HTTPException(400, "Workspace no longer exists")
    return {"email": invitation.email, "workspace": workspace.name, "role": invitation.role,
            "expires_at": invitation.expires_at,
            "account_exists": db.query(User.id).filter(func.lower(User.email) == invitation.email).first() is not None}


@router.post("/workspace-invitations/activate", status_code=201)
def activate_invitation(data: ActivateInput, db: Session = Depends(get_db)):
    """A single-use invitation can create only its addressed account and membership."""
    invitation = pending_invitation(db, data.token, lock=True)
    if db.query(User.id).filter(func.lower(User.email) == invitation.email).first():
        raise HTTPException(409, "This account already exists. Sign in to accept the invitation.")
    workspace = db.get(PMSWorkspace, invitation.workspace_id)
    if not workspace or workspace.organization_id is not None:
        raise HTTPException(403, "Contact your workspace administrator to provision this account")
    role = db.query(UserRole).filter_by(name="pms_viewer" if invitation.role == "Guest" else "pms_team_member").first()
    if not role:
        raise HTTPException(503, "Workspace account roles are not configured")
    from app.core.security import get_password_hash
    user = User(email=invitation.email, hashed_password=get_password_hash(data.password),
                role_id=role.id, is_active=True, is_superuser=False)
    db.add(user)
    db.flush()
    db.add(PMSWorkspaceMember(workspace_id=invitation.workspace_id, user_id=user.id, role=invitation.role))
    invitation.status = "accepted"
    db.commit()
    return {"email": user.email, "workspace_id": invitation.workspace_id, "status": "accepted"}


def workspace_member(db, workspace_id, user, manage=False):
    from .people_management import scoped_workspace
    return scoped_workspace(db, workspace_id, user, manage)


@router.get("/workspaces")
def list_workspaces(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from .people_management import organization_admin
    if organization_admin(user):
        workspaces = db.query(PMSWorkspace).filter(PMSWorkspace.organization_id == organization_id_for(user), PMSWorkspace.id.notin_(archived_ids())).all()
        memberships = {m.workspace_id: m.role for m in db.query(PMSWorkspaceMember).filter_by(user_id=user.id)}
        return [{"id": w.id, "name": w.name, "role": memberships.get(w.id, "Admin"), "access_source": "Workspace membership" if w.id in memberships else "Organization role"} for w in workspaces]
    rows = db.query(PMSWorkspace, PMSWorkspaceMember.role).join(PMSWorkspaceMember, PMSWorkspaceMember.workspace_id == PMSWorkspace.id).filter(PMSWorkspaceMember.user_id == user.id, PMSWorkspace.id.notin_(archived_ids())).all()
    return [{"id": w.id, "name": w.name, "role": role} for w, role in rows]


@router.get("/workspaces/{workspace_id}/overview")
def overview(workspace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """One scoped dataset for the workspace board, people, and list views."""
    workspace, member = workspace_member(db, workspace_id, user)
    projects = db.query(PMSProject).filter_by(workspace_id=workspace_id, deleted_at=None).order_by(PMSProject.name).all()
    project_ids = [p.id for p in projects]
    tasks = db.query(PMSTask).filter(PMSTask.project_id.in_(project_ids), PMSTask.deleted_at.is_(None)).order_by(PMSTask.position, PMSTask.id).all() if project_ids else []
    counts = dict(db.query(PMSComment.task_id, func.count(PMSComment.id)).filter(PMSComment.task_id.in_([t.id for t in tasks])).group_by(PMSComment.task_id).all()) if tasks else {}
    return {
        "id": workspace.id, "name": workspace.name, "role": member.role,
        "projects": [{"id": p.id, "name": p.name, "project_key": p.project_key} for p in projects],
        "tasks": [{"id": t.id, "project_id": t.project_id, "task_key": t.task_key, "title": t.title, "description": t.description,
                   "status": t.status, "priority": t.priority, "assignee_user_id": t.assignee_user_id, "assignee_user_ids": t.assignee_user_ids,
                   "start_date": t.start_date, "due_date": t.due_date, "estimated_hours": t.estimated_hours, "position": t.position, "comments_count": counts.get(t.id, 0)} for t in tasks],
    }


@router.post("/workspaces", status_code=201)
def create_workspace(data: WorkspaceInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not has_any_permission(user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(403, "Project management permission required")
    if not data.name.strip():
        raise HTTPException(422, "Workspace name is required")
    workspace = PMSWorkspace(name=data.name.strip(), organization_id=organization_id_for(user))
    db.add(workspace)
    db.flush()
    db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="Owner"))
    db.commit()
    return {"id": workspace.id, "name": workspace.name, "role": "Owner"}


@router.get("/workspaces/{workspace_id}/members")
def members(workspace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user)
    rows = db.query(PMSWorkspaceMember, User.email).join(User, User.id == PMSWorkspaceMember.user_id).filter(PMSWorkspaceMember.workspace_id == workspace_id).all()
    from .people_management import public_person
    return [{**public_person(db, db.get(User, m.user_id)), "id": m.id, "user_id": m.user_id, "email": email, "role": m.role} for m, email in rows]


@router.get("/workspaces/{workspace_id}/eligible-people")
def eligible_people(workspace_id: int, q: str = Query("", max_length=150), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace, _ = workspace_member(db, workspace_id, user, True)
    query = db.query(User).filter(User.is_active.is_(True)).order_by(User.email)
    if q.strip():
        query = query.filter(User.email.ilike("%" + q.strip() + "%"))
    # Evaluate persisted tenancy, even for installation-wide superusers.
    from .people_management import public_person
    return [public_person(db, u) for u in query.all() if organization_id_for(u) == workspace.organization_id]


@router.post("/workspaces/{workspace_id}/members", status_code=201)
def add_workspace_member(workspace_id: int, data: AddMemberInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace, actor = workspace_member(db, workspace_id, user, True)
    if data.role == "Admin" and actor.role != "Owner":
        raise HTTPException(403, "Only the owner can appoint administrators")
    target = db.get(User, data.user_id)
    if not target or not target.is_active or organization_id_for(target) != workspace.organization_id:
        raise HTTPException(404, "Eligible workspace user not found")
    if db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=target.id).first():
        raise HTTPException(409, "User is already a workspace member")
    member = PMSWorkspaceMember(workspace_id=workspace_id, user_id=target.id, role=data.role)
    db.add(member)
    from .people_management import record
    record(db, user, target.id, "PMS_WORKSPACE_ADDED", "Added existing person directly", after={"role": data.role}, workspace_id=workspace_id)
    db.query(PMSWorkspaceInvitation).filter_by(workspace_id=workspace_id, email=target.email.lower(), status="pending").update({"status": "accepted"})
    db.add(Notification(user_id=target.id, title="Added to workspace", message=f"You were added to {workspace.name} as {data.role}.", module="project_management", event_type="workspace.member_added", action_url=f"/pms/workspaces?workspace={workspace_id}"))
    db.commit()
    return {"id": member.id, "user_id": target.id, "email": target.email, "role": member.role}


def editable_member(db, workspace_id, member_id, user):
    _, actor = workspace_member(db, workspace_id, user, True)
    target = db.query(PMSWorkspaceMember).filter_by(id=member_id, workspace_id=workspace_id).first()
    if not target:
        raise HTTPException(404, "Member not found")
    if target.role == "Owner" or (actor.role != "Owner" and target.role == "Admin" and not user.is_superuser):
        raise HTTPException(403, "Only the owner can manage administrators; the owner cannot be removed")
    return target, actor


@router.patch("/workspaces/{workspace_id}/members/{member_id}")
def change_role(workspace_id: int, member_id: int, data: MemberInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    target, actor = editable_member(db, workspace_id, member_id, user)
    if data.role == "Admin" and actor.role != "Owner":
        raise HTTPException(403, "Only the owner can appoint administrators")
    from .people_management import record
    record(db, user, target.user_id, "PMS_WORKSPACE_ROLE", "Workspace role updated", before={"role": target.role}, after={"role": data.role}, workspace_id=workspace_id)
    if data.role == "Guest":
        from .people_management import preview_data
        impact = preview_data(db, user, db.get(User, target.user_id), workspace_id)
        if impact["tasks"] or impact["projects"] or impact["approvals"] or impact["workflow_approvals"]:
            raise HTTPException(409, "Preview and transfer open assignments in Manage person before changing this collaborator to Guest")
    target.role = data.role
    if data.role == "Guest":
        _unassign_workspace_member(db, workspace_id, target.user_id)
    db.commit()
    return {"id": target.id, "role": target.role}


@router.delete("/workspaces/{workspace_id}/members/{member_id}")
def remove_member(workspace_id: int, member_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    target, _ = editable_member(db, workspace_id, member_id, user)
    from .people_management import preview_data, record
    impact = preview_data(db, user, db.get(User, target.user_id), workspace_id)
    if impact["tasks"] or impact["projects"] or impact["approvals"] or impact["workflow_approvals"]:
        raise HTTPException(409, "Open Manage person to preview affected assignments and reassign them before removal")
    record(db, user, target.user_id, "PMS_REMOVE_WORKSPACE", "Removed from workspace", workspace_id=workspace_id)
    removed_user_id = target.user_id
    _unassign_workspace_member(db, workspace_id, removed_user_id)
    from .models import PMSProjectMember
    project_ids = db.query(PMSProject.id).filter_by(workspace_id=workspace_id)
    db.query(PMSProjectMember).filter(PMSProjectMember.user_id == removed_user_id, PMSProjectMember.project_id.in_(project_ids)).delete(synchronize_session=False)
    db.delete(target)
    db.commit()
    from .realtime import pms_realtime_manager
    import anyio
    project_ids = {p[0] for p in db.query(PMSProject.id).filter_by(workspace_id=workspace_id).all()}
    anyio.from_thread.run(pms_realtime_manager.revoke_projects, removed_user_id, project_ids)
    return {"ok": True}


def _unassign_workspace_member(db: Session, workspace_id: int, user_id: int):
    tasks = db.query(PMSTask).join(PMSProject, PMSProject.id == PMSTask.project_id).filter(PMSProject.workspace_id == workspace_id).all()
    for task in tasks:
        if user_id in task.assignee_user_ids:
            remaining = [uid for uid in task.assignee_user_ids if uid != user_id]
            task.assignee_user_ids = remaining
            task.assignee_user_id = remaining[0] if remaining else None


@router.post("/workspaces/{workspace_id}/invitations", status_code=201)
def invite(workspace_id: int, data: InviteInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace, actor = workspace_member(db, workspace_id, user, True)
    if data.role == "Admin" and actor.role != "Owner":
        raise HTTPException(403, "Only the owner can invite administrators")
    email = data.email.strip().lower()
    recipient = db.query(User).filter(func.lower(User.email) == email).first()
    if recipient and db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=recipient.id).first():
        raise HTTPException(409, "User is already a member")
    db.query(PMSWorkspaceInvitation).filter_by(workspace_id=workspace_id, email=email, status="pending").update({"status": "revoked"})
    token = secrets.token_urlsafe(32)
    invitation = PMSWorkspaceInvitation(workspace_id=workspace_id, email=email, role=data.role, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=datetime.utcnow() + timedelta(days=7))
    db.add(invitation)
    db.flush()
    token = share_token(invitation)
    invitation.token_hash = hashlib.sha256(token.encode()).hexdigest()
    from app.services.email_dispatch import queue_email
    from app.core.config import settings
    queue_email(db, recipient=email, module="pms", organization_id=workspace.organization_id,
        subject="You are invited to a Business Suite workspace",
        body="You have been invited to a workspace. Open this single-use invitation to accept:\n"
            + settings.FRONTEND_PUBLIC_URL.rstrip("/") + "/pms/invitation?token=" + token,
        event_key="workspace-invite:" + invitation.token_hash)
    if recipient:
        db.add(Notification(user_id=recipient.id, title="Workspace invitation", message=f"You were invited to {workspace.name} as {data.role}. Open to accept your invitation.", module="project_management", event_type="email.workspace_invitation", action_url="/pms/invitation?token=" + token))
    db.commit()
    return {"id": invitation.id, "email": email, "role": data.role, "token": token, "status": "pending", "expires_at": invitation.expires_at, "delivery": "email_queued_and_share_link"}


@router.get("/workspaces/{workspace_id}/invitations")
def invitations(workspace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user, True)
    rows = db.query(PMSWorkspaceInvitation).filter_by(workspace_id=workspace_id).order_by(PMSWorkspaceInvitation.id.desc()).all()
    existing_emails = {e[0].lower() for e in db.query(User.email).filter(func.lower(User.email).in_([i.email for i in rows])).all()}
    return [{"id": i.id, "email": i.email, "role": i.role, "account_exists": i.email in existing_emails, "status": "expired" if i.status == "pending" and i.expires_at <= datetime.utcnow() else i.status, "expires_at": i.expires_at,
             "token": share_token(i) if i.status == "pending" and i.expires_at > datetime.utcnow() and hmac.compare_digest(hashlib.sha256(share_token(i).encode()).hexdigest(), i.token_hash) else None} for i in rows]


@router.post("/workspaces/{workspace_id}/invitations/{invitation_id}/resend", status_code=201)
def resend_invitation(workspace_id: int, invitation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user, True)
    invitation = db.query(PMSWorkspaceInvitation).filter_by(id=invitation_id, workspace_id=workspace_id).first()
    if not invitation:
        raise HTTPException(404, "Invitation not found")
    if invitation.status == "accepted":
        raise HTTPException(409, "This invitation has already been accepted")
    return invite(workspace_id, InviteInput(email=invitation.email, role=invitation.role), db, user)


@router.delete("/workspaces/{workspace_id}/invitations/{invitation_id}")
def revoke(workspace_id: int, invitation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user, True)
    invitation = db.query(PMSWorkspaceInvitation).filter_by(id=invitation_id, workspace_id=workspace_id).first()
    if not invitation:
        raise HTTPException(404, "Invitation not found")
    invitation.status = "revoked"
    db.commit()
    return {"ok": True}


@router.post("/workspace-invitations/accept")
def accept(data: AcceptInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invitation = pending_invitation(db, data.token, lock=True)
    return _accept_invitation(db, invitation, user)


def _accept_invitation(db, invitation, user):
    if invitation.status != "pending" or invitation.expires_at <= datetime.utcnow() or is_archived(db, invitation.workspace_id):
        raise HTTPException(400, "Invitation is invalid, expired, or already used")
    if invitation.email != user.email.strip().lower():
        raise HTTPException(403, "Sign in with the invited email address")
    workspace = db.get(PMSWorkspace, invitation.workspace_id)
    if not workspace or workspace.organization_id != organization_id_for(user):
        raise HTTPException(403, "Invitation belongs to another organization")
    if not db.query(PMSWorkspaceMember).filter_by(workspace_id=invitation.workspace_id, user_id=user.id).first():
        db.add(PMSWorkspaceMember(workspace_id=invitation.workspace_id, user_id=user.id, role=invitation.role))
    invitation.status = "accepted"
    db.commit()
    return {"workspace_id": invitation.workspace_id}


class EntryInput(BaseModel):
    kind: Literal["note", "chat"]
    body: rich_text_type(20000, 1) = Field()
    task_id: int | None = None


@router.get("/workspaces/{workspace_id}/entries")
def list_entries(workspace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user)
    rows = db.query(PMSWorkspaceEntry, User.email).join(User, User.id == PMSWorkspaceEntry.author_id).filter(PMSWorkspaceEntry.workspace_id == workspace_id, PMSWorkspaceEntry.kind.in_(["note", "chat"])).order_by(PMSWorkspaceEntry.id.desc()).limit(200).all()
    return [{"id": e.id, "kind": e.kind, "body": e.body, "task_id": e.task_id, "author_id": e.author_id, "author": email, "created_at": e.created_at} for e, email in reversed(rows)]


@router.post("/workspaces/{workspace_id}/entries", status_code=201)
def create_entry(workspace_id: int, data: EntryInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = workspace_member(db, workspace_id, user)
    if member.role == "Guest":
        raise HTTPException(403, "Guests have read-only access")
    if not data.body.strip():
        raise HTTPException(422, "Write a note or message first")
    if data.task_id is not None:
        task = db.query(PMSTask).join(PMSProject, PMSProject.id == PMSTask.project_id).filter(PMSTask.id == data.task_id, PMSTask.deleted_at.is_(None), PMSProject.workspace_id == workspace_id, PMSProject.deleted_at.is_(None)).first()
        if not task:
            raise HTTPException(422, "Task must belong to this workspace")
    entry = PMSWorkspaceEntry(workspace_id=workspace_id, author_id=user.id, kind=data.kind, body=data.body.strip(), task_id=data.task_id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    if data.kind == "chat":
        from .chat import sync_legacy, commit_chat
        from .chat_models import ChatMessage, ChatMember, ChatConversation
        sync_legacy(db, workspace_id, user)
        message = db.query(ChatMessage).filter_by(legacy_entry_id=entry.id).one()
        members = db.query(ChatMember).join(PMSWorkspaceMember, (PMSWorkspaceMember.user_id == ChatMember.user_id) & (PMSWorkspaceMember.workspace_id == workspace_id)).filter(ChatMember.conversation_id == message.conversation_id, ChatMember.active.is_(True), ChatMember.muted.is_(False), ChatMember.user_id != user.id).all()
        for recipient in members:
            db.add(Notification(user_id=recipient.user_id, title="New workspace message", message="Open Messages to view an update in a conversation you joined.", module="project_management", event_type="chat.message", related_entity_type="pms_chat", related_entity_id=message.id, action_url=f"/pms/messages?workspace={workspace_id}&conversation={message.conversation_id}&message={message.id}"))
        commit_chat(db, workspace_id, message.conversation_id)
    return {"id": entry.id}
