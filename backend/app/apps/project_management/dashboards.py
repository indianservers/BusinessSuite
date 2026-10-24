"""Owned dashboard definitions with organization-only sharing and recoverable deletion."""
import json
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSWorkspace, PMSWorkspaceEntry
from .workspaces import workspace_member
from .access import organization_id_for

router = APIRouter()
KIND = "dashboard_v1"

class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    visibility: Literal["private", "organization"] = "private"

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Dashboard name is required")
        return value.strip()

class Create(Definition):
    workspace_id: int = Field(gt=0)

class Edit(Definition):
    revision: int = Field(gt=0)

class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(gt=0)

def scoped(db, user):
    # NULL organization is never treated as a shared tenant.
    return db.query(PMSWorkspaceEntry).join(PMSWorkspace, PMSWorkspace.id == PMSWorkspaceEntry.workspace_id).filter(
        PMSWorkspaceEntry.kind == KIND,
        PMSWorkspace.organization_id == organization_id_for(user),
    )

def visible(row, user):
    data = json.loads(row.body)
    return row.author_id == user.id or (organization_id_for(user) is not None and data["visibility"] == "organization" and not data["deleted_at"])

def record(row):
    return {**json.loads(row.body), "id": row.id, "workspace_id": row.workspace_id, "owner_id": row.author_id, "created_at": row.created_at}

def find(db, user, did, owner=False):
    row = scoped(db, user).filter(PMSWorkspaceEntry.id == did).first()
    if not row or not visible(row, user):
        raise HTTPException(404, "Dashboard not found")
    if owner and row.author_id != user.id:
        raise HTTPException(403, "Only the dashboard owner can change it")
    return row

def share_allowed(user, visibility):
    if visibility == "organization" and organization_id_for(user) is None:
        raise HTTPException(422, "Organization sharing requires an organization account")

def persist(db, row, data, revision):
    old = row.body
    if json.loads(old)["revision"] != revision:
        raise HTTPException(409, "Dashboard changed. Refresh and try again")
    data.update(revision=revision + 1, updated_at=datetime.now(timezone.utc).isoformat())
    body = json.dumps(data)
    if db.execute(update(PMSWorkspaceEntry).where(PMSWorkspaceEntry.id == row.id, PMSWorkspaceEntry.body == old).values(body=body)).rowcount != 1:
        raise HTTPException(409, "Dashboard changed. Refresh and try again")
    db.commit()
    db.refresh(row)
    return record(row)

@router.get("/dashboards")
def listing(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [record(row) for row in scoped(db, user).order_by(PMSWorkspaceEntry.id.desc()).all() if visible(row, user)]

@router.post("/dashboards", status_code=201)
def create(data: Create, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace, member = workspace_member(db, data.workspace_id, user)
    if workspace.organization_id != organization_id_for(user):
        raise HTTPException(404, "Workspace not found")
    if member.role == "Guest":
        raise HTTPException(403, "Guests cannot create dashboards")
    share_allowed(user, data.visibility)
    payload = data.model_dump(exclude={"workspace_id"})
    payload.update(revision=1, deleted_at=None, updated_at=datetime.now(timezone.utc).isoformat())
    row = PMSWorkspaceEntry(workspace_id=data.workspace_id, author_id=user.id, kind=KIND, body=json.dumps(payload))
    db.add(row)
    db.commit()
    db.refresh(row)
    return record(row)

@router.get("/dashboards/{did}")
def detail(did: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = find(db, user, did)
    if json.loads(row.body)["deleted_at"]:
        raise HTTPException(404, "Dashboard is in Trash")
    return record(row)

@router.put("/dashboards/{did}")
def edit(did: int, data: Edit, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = find(db, user, did, owner=True)
    old = json.loads(row.body)
    if old["deleted_at"]:
        raise HTTPException(409, "Restore this dashboard before editing")
    share_allowed(user, data.visibility)
    old.update(data.model_dump(exclude={"revision"}))
    return persist(db, row, old, data.revision)

@router.post("/dashboards/{did}/trash")
def trash(did: int, data: Revision, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = find(db, user, did, owner=True)
    old = json.loads(row.body)
    old["deleted_at"] = old["deleted_at"] or datetime.now(timezone.utc).isoformat()
    return persist(db, row, old, data.revision)

@router.post("/dashboards/{did}/restore")
def restore(did: int, data: Revision, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = find(db, user, did, owner=True)
    old = json.loads(row.body)
    old["deleted_at"] = None
    return persist(db, row, old, data.revision)
