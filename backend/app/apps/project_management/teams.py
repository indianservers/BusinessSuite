"""Workspace team groups. Group membership never grants workspace access."""
import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSWorkspaceTeam, PMSWorkspaceMember
from .workspaces import workspace_member

router = APIRouter()


class TeamInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    alias: str = Field(min_length=2, max_length=60)
    member_ids: list[int] = Field(default_factory=list, max_length=500)


def output(db, team):
    eligible = {row.user_id for row in db.query(PMSWorkspaceMember).filter_by(workspace_id=team.workspace_id) if row.role != "Guest"}
    return {"id": team.id, "name": team.name, "alias": team.alias,
            "member_ids": [uid for uid in json.loads(team.member_ids_json) if uid in eligible]}


@router.get("/workspaces/{workspace_id}/teams")
def list_teams(workspace_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = workspace_member(db, workspace_id, user)
    teams = db.query(PMSWorkspaceTeam).filter_by(workspace_id=workspace_id).order_by(PMSWorkspaceTeam.name).all()
    return {"teams": [output(db, team) for team in teams], "can_manage": member.role in {"Owner", "Admin"}}


def persist_team(db, workspace_id, data, team=None):
    name, alias = data.name.strip(), data.alias.strip().lower()
    if not name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", alias):
        raise HTTPException(422, "Use a name and an alias with lowercase letters, digits and single hyphens")
    duplicate = db.query(PMSWorkspaceTeam).filter_by(workspace_id=workspace_id, alias=alias).first()
    if duplicate and (team is None or duplicate.id != team.id):
        raise HTTPException(409, "This team alias is already used in the workspace")
    ids = sorted(set(data.member_ids))
    eligible = {row.user_id for row in db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace_id) if row.role != "Guest"}
    if not set(ids).issubset(eligible):
        raise HTTPException(422, "Choose existing workspace collaborators; guests cannot join teams")
    team = team or PMSWorkspaceTeam(workspace_id=workspace_id)
    team.name, team.alias, team.member_ids_json = name, alias, json.dumps(ids)
    db.add(team)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This team alias is already used in the workspace")
    db.refresh(team)
    return output(db, team)


@router.post("/workspaces/{workspace_id}/teams", status_code=201)
def create_team(workspace_id: int, data: TeamInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user, True)
    return persist_team(db, workspace_id, data)


@router.put("/workspaces/{workspace_id}/teams/{team_id}")
def update_team(workspace_id: int, team_id: int, data: TeamInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, workspace_id, user, True)
    team = db.query(PMSWorkspaceTeam).filter_by(id=team_id, workspace_id=workspace_id).first()
    if not team:
        raise HTTPException(404, "Team not found")
    return persist_team(db, workspace_id, data, team)
