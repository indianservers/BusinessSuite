"""Workspace-scoped reporting relationships, independent of access roles."""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSWorkspace, PMSWorkspaceMember, PMSWorkspaceEntry, PMSWorkspaceTeam
from .workspaces import workspace_member

router = APIRouter()

class ReportingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    manager_id: int | None = Field(default=None, gt=0)
    display_name: str = Field(default="", max_length=120)
    job_title: str = Field(default="", max_length=120)


def collaborators(db, wid):
    return db.query(PMSWorkspaceMember, User).join(User, User.id == PMSWorkspaceMember.user_id).filter(PMSWorkspaceMember.workspace_id == wid, PMSWorkspaceMember.role != "Guest", User.is_active.is_(True)).all()


def config_row(db, wid):
    return db.query(PMSWorkspaceEntry).filter_by(workspace_id=wid, kind="org_chart").populate_existing().order_by(PMSWorkspaceEntry.id).first()


def chart(db, wid, can_manage):
    rows = collaborators(db, wid)
    eligible = {u.id for _, u in rows}
    row = config_row(db, wid)
    saved = json.loads(row.body) if row else {"revision": 0, "people": {}}
    teams = db.query(PMSWorkspaceTeam).filter_by(workspace_id=wid).order_by(PMSWorkspaceTeam.name).all()
    memberships = {uid: [] for uid in eligible}
    for t in teams:
        for uid in json.loads(t.member_ids_json):
            if uid in memberships:
                memberships[uid].append({"id": t.id, "name": t.name})
    people = []
    for m, u in rows:
        person = saved["people"].get(str(u.id), {})
        manager = person.get("manager_id")
        people.append({"id": u.id, "email": u.email, "name": person.get("display_name") or u.email.split("@")[0].replace(".", " ").replace("_", " ").title(), "display_name": person.get("display_name", ""), "job_title": person.get("job_title", ""), "role": m.role, "manager_id": manager if manager in eligible else None, "teams": memberships[u.id]})
    people.sort(key=lambda p: (p["name"].casefold(), p["id"]))
    return {"revision": saved["revision"], "can_manage": can_manage, "positions": saved.get("positions", {}), "people": people, "teams": [{"id": t.id, "name": t.name} for t in teams]}


@router.get("/workspaces/{wid}/org-chart")
def get_chart(wid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, member = workspace_member(db, wid, user)
    return chart(db, wid, member.role in {"Owner", "Admin"})


class ChartPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(ge=0, le=20000, allow_inf_nan=False)
    y: float = Field(ge=0, le=20000, allow_inf_nan=False)


class ChartLayoutInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    positions: dict[int, ChartPoint] = Field(max_length=1000)


@router.put("/workspaces/{wid}/org-chart/layout")
def save_layout(wid: int, data: ChartLayoutInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, wid, user, True)
    db.execute(update(PMSWorkspace).where(PMSWorkspace.id == wid).values(name=PMSWorkspace.name))
    row = config_row(db, wid)
    saved = json.loads(row.body) if row else {"revision": 0, "people": {}}
    if saved["revision"] != data.revision: raise HTTPException(409, "The chart changed. Reload before arranging it.")
    eligible = {u.id for _, u in collaborators(db, wid)}
    if not set(data.positions).issubset(eligible): raise HTTPException(422, "Arrange active people from this workspace only")
    saved.update(revision=saved["revision"] + 1, positions={str(k): v.model_dump() for k,v in data.positions.items()})
    if row: row.body = json.dumps(saved)
    else: db.add(PMSWorkspaceEntry(workspace_id=wid, author_id=user.id, kind="org_chart", body=json.dumps(saved)))
    db.commit()
    return chart(db, wid, True)


@router.put("/workspaces/{wid}/org-chart/{person_id}")
def set_reporting(wid: int, person_id: int, data: ReportingInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace_member(db, wid, user, True)
    # Serialize the first configuration insert as well as subsequent graph edits.
    db.execute(update(PMSWorkspace).where(PMSWorkspace.id == wid).values(name=PMSWorkspace.name))
    row = config_row(db, wid)
    saved = json.loads(row.body) if row else {"revision": 0, "people": {}}
    if saved["revision"] != data.revision:
        raise HTTPException(409, "The organization chart changed. Reload before saving.")
    eligible = {u.id for _, u in collaborators(db, wid)}
    if person_id not in eligible or (data.manager_id is not None and data.manager_id not in eligible):
        raise HTTPException(422, "Choose active collaborators from this workspace; guests cannot be in reporting lines")
    people = saved["people"]
    cursor = data.manager_id
    visited = {person_id}
    while cursor is not None and cursor in eligible:
        if cursor in visited:
            raise HTTPException(422, "This reporting line would create a cycle")
        visited.add(cursor)
        cursor = people.get(str(cursor), {}).get("manager_id")
    # Drop stale metadata when a collaborator has left the workspace.
    people = {key: value for key, value in people.items() if int(key) in eligible}
    people[str(person_id)] = {"manager_id": data.manager_id, "display_name": data.display_name.strip(), "job_title": data.job_title.strip()}
    saved = {**saved, "revision": saved["revision"] + 1, "people": people}
    if row:
        row.body = json.dumps(saved)
    else:
        db.add(PMSWorkspaceEntry(workspace_id=wid, author_id=user.id, kind="org_chart", body=json.dumps(saved)))
    db.commit()
    return chart(db, wid, True)
