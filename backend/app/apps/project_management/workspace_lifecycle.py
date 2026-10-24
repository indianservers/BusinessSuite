"""Organization-scoped Admin reset; workspace records are never deleted."""

import hashlib
import json
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, select
from sqlalchemy.orm import Session
from app.db.base_class import Base
from app.core.deps import get_db, get_current_user
from app.models.user import User


class WorkspaceArchive(Base):
    __tablename__ = "pms_workspace_archives"
    workspace_id = Column(Integer, ForeignKey("pms_workspaces.id"), primary_key=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    batch_key = Column(String(32), nullable=False)
    restored_at = Column(DateTime)


def archived_ids():
    return select(WorkspaceArchive.workspace_id).where(
        WorkspaceArchive.deleted_at.is_not(None)
    )


def is_archived(db, workspace_id):
    return (
        db.query(WorkspaceArchive.workspace_id)
        .filter(
            WorkspaceArchive.workspace_id == workspace_id,
            WorkspaceArchive.deleted_at.is_not(None),
        )
        .first()
        is not None
    )


def admin(user=Depends(get_current_user)):
    from .access import has_any_permission

    if not has_any_permission(user, {"pms_admin"}):
        raise HTTPException(403, "PMS administrator required")
    return user


def scoped(db, user):
    from .models import PMSWorkspace
    from .access import organization_id_for

    return db.query(PMSWorkspace).filter(
        PMSWorkspace.organization_id == organization_id_for(user)
    )


def fingerprint(ids):
    return hashlib.sha256(json.dumps(sorted(ids)).encode()).hexdigest()


router = APIRouter(prefix="/admin/workspaces", tags=["Workspace administration"])


@router.get("")
def listing(db: Session = Depends(get_db), user: User = Depends(admin)):
    from .models import PMSWorkspaceMember

    rows = scoped(db, user).order_by("id").all()
    result = []
    for workspace in rows:
        archive = db.get(WorkspaceArchive, workspace.id)
        owners = (
            db.query(User.email)
            .join(PMSWorkspaceMember, PMSWorkspaceMember.user_id == User.id)
            .filter(
                PMSWorkspaceMember.workspace_id == workspace.id,
                PMSWorkspaceMember.role == "Owner",
            )
            .all()
        )
        result.append(
            {
                "id": workspace.id,
                "name": workspace.name,
                "owners": [r[0] for r in owners],
                "deleted_at": archive.deleted_at if archive else None,
                "restored_at": archive.restored_at if archive else None,
            }
        )
    ids = [row["id"] for row in result if not row["deleted_at"]]
    return {
        "items": result,
        "active_count": len(ids),
        "preview_hash": fingerprint(ids),
        "scope": "All workspaces in your organization, regardless of whether an admin or user created them.",
    }


class ResetInput(BaseModel):
    confirmation: str
    preview_hash: str


@router.post("/reset-all")
def reset(data: ResetInput, db: Session = Depends(get_db), user: User = Depends(admin)):
    if data.confirmation != "RESET ALL WORKSPACES":
        raise HTTPException(422, "Type RESET ALL WORKSPACES to confirm")
    rows = scoped(db, user).with_for_update().all()
    active = [row for row in rows if not is_archived(db, row.id)]
    if fingerprint([row.id for row in active]) != data.preview_hash:
        raise HTTPException(
            409, "Workspace list changed. Refresh the preview before resetting."
        )
    batch = uuid4().hex
    now = datetime.utcnow()
    for workspace in active:
        marker = db.get(WorkspaceArchive, workspace.id)
        if not marker:
            marker = WorkspaceArchive(workspace_id=workspace.id)
            db.add(marker)
        marker.deleted_at = now
        marker.deleted_by = user.id
        marker.batch_key = batch
        marker.restored_at = None
    db.commit()
    return {"soft_deleted": len(active), "batch_key": batch, "restorable": True}


@router.post("/{workspace_id}/restore")
def restore(
    workspace_id: int, db: Session = Depends(get_db), user: User = Depends(admin)
):
    workspace = scoped(db, user).filter_by(id=workspace_id).with_for_update().first()
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    marker = db.get(WorkspaceArchive, workspace_id)
    if not marker or not marker.deleted_at:
        raise HTTPException(409, "Workspace is already active")
    marker.deleted_at = None
    marker.restored_at = datetime.utcnow()
    db.commit()
    return {"id": workspace_id, "restored": True}
