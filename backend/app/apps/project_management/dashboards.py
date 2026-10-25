"""Backward-compatible dashboard builder API, using existing workspace entry storage."""

import json
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .models import PMSWorkspace, PMSWorkspaceEntry, PMSWorkspaceMember
from .workspaces import workspace_member
from .access import organization_id_for
from .dashboard_config import (
    Configuration,
    WIDGETS,
    TEMPLATES,
    template_config,
    validate_layout,
)
from .dashboard_engine import Engine

router = APIRouter()
KIND = "dashboard_v1"
HISTORY = "dashboard_revision_v2"
PREFERENCES = "dashboard_preferences_v2"


def now():
    return datetime.now(timezone.utc).isoformat()


class Share(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0)
    role: Literal["viewer", "editor"] = "viewer"


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    visibility: Literal["private", "selected", "workspace", "organization"] = "private"
    shared_users: list[Share] | None = Field(default=None, max_length=100)
    icon: (
        Literal[
            "dashboard", "projects", "team", "chart", "calendar", "target", "briefcase"
        ]
        | None
    ) = None
    accent: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    category: str | None = Field(default=None, max_length=80)
    archived: bool | None = None
    configuration: Configuration | None = None

    @field_validator("configuration")
    @classmethod
    def valid_layout(cls, value):
        return validate_layout(value)

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


class Preference(BaseModel):
    favorite: bool = True


class Transfer(Revision):
    owner_id: int = Field(gt=0)


class Permanent(Revision):
    name: str


class Suggest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=3, max_length=2000)
    workspace_id: int | None = Field(default=None, gt=0)
    provider: Literal["openai", "claude", "gemini"] | None = None


def scoped(db, user):
    from .workspace_lifecycle import archived_ids

    return (
        db.query(PMSWorkspaceEntry)
        .join(PMSWorkspace, PMSWorkspace.id == PMSWorkspaceEntry.workspace_id)
        .filter(
            PMSWorkspaceEntry.kind == KIND,
            PMSWorkspace.id.notin_(archived_ids()),
            PMSWorkspace.organization_id == organization_id_for(user),
        )
    )


def membership(db, row, user):
    return (
        db.query(PMSWorkspaceMember)
        .filter_by(workspace_id=row.workspace_id, user_id=user.id)
        .first()
    )


def visible(row, user, db=None):
    data = json.loads(row.body)
    if row.author_id == user.id:
        return True
    if data.get("deleted_at"):
        return False
    if data["visibility"] == "organization":
        return organization_id_for(user) is not None
    member = membership(db, row, user) if db else None
    return bool(
        member
        and (
            data["visibility"] == "workspace"
            or data["visibility"] == "selected"
            and any(s["user_id"] == user.id for s in data.get("shared_users", []))
        )
    )


def can_edit(db, row, user):
    member = membership(db, row, user)
    data = json.loads(row.body)
    return bool(
        member
        and member.role != "Guest"
        and (
            row.author_id == user.id
            or data["visibility"] == "selected"
            and any(
                s["user_id"] == user.id and s["role"] == "editor"
                for s in data.get("shared_users", [])
            )
        )
    )


def configuration(row):
    return Configuration.model_validate(
        json.loads(row.body).get("configuration")
        or template_config("project_overview").model_dump(mode="json")
    )


def record(row, user=None, db=None):
    payload = {
        **json.loads(row.body),
        "id": row.id,
        "workspace_id": row.workspace_id,
        "owner_id": row.author_id,
        "created_at": row.created_at,
    }
    payload.setdefault(
        "configuration", template_config("project_overview").model_dump(mode="json")
    )
    payload.setdefault("shared_users", [])
    payload.setdefault("archived", False)
    payload.setdefault("icon", "dashboard")
    payload.setdefault("accent", "#6d3df5")
    payload.setdefault("category", "")
    if user and db:
        payload.update(
            can_edit=can_edit(db, row, user), can_manage=row.author_id == user.id
        )
    return payload


def find(db, user, did, owner=False, editable=False):
    row = scoped(db, user).filter(PMSWorkspaceEntry.id == did).first()
    if not row or not visible(row, user, db):
        raise HTTPException(404, "Dashboard not found")
    if owner and row.author_id != user.id:
        raise HTTPException(
            403, "Only the dashboard owner can change sharing or lifecycle"
        )
    if editable and not can_edit(db, row, user):
        raise HTTPException(403, "Dashboard editor access required")
    return row


def share_allowed(db, user, workspace_id, data):
    if data.visibility == "organization" and organization_id_for(user) is None:
        raise HTTPException(
            422, "Organization sharing requires an organization account"
        )
    for share in data.shared_users or []:
        member = (
            db.query(PMSWorkspaceMember)
            .filter_by(workspace_id=workspace_id, user_id=share.user_id)
            .first()
        )
        if not member or share.role == "editor" and member.role == "Guest":
            raise HTTPException(
                422, "Share only with current workspace members; guests are read-only"
            )


def snapshot(db, row, old):
    payload = {
        "dashboard_id": row.id,
        "revision": old["revision"],
        "name": old["name"],
        "description": old.get("description", ""),
        "configuration": old.get("configuration")
        or template_config("project_overview").model_dump(mode="json"),
        "editor_id": old.get("last_editor_id", row.author_id),
        "saved_at": old.get("updated_at", now()),
    }
    db.add(
        PMSWorkspaceEntry(
            workspace_id=row.workspace_id,
            author_id=row.author_id,
            kind=HISTORY,
            body=json.dumps(payload),
        )
    )


def persist(db, row, data, revision, user):
    old = row.body
    if json.loads(old)["revision"] != revision:
        raise HTTPException(
            409,
            "Dashboard changed. Reload the latest version before saving; your draft is preserved",
        )
    data.update(revision=revision + 1, updated_at=now(), last_editor_id=user.id)
    if (
        db.execute(
            update(PMSWorkspaceEntry)
            .where(PMSWorkspaceEntry.id == row.id, PMSWorkspaceEntry.body == old)
            .values(body=json.dumps(data))
        ).rowcount
        != 1
    ):
        raise HTTPException(
            409, "Dashboard changed. Reload the latest version before saving"
        )
    snapshot(db, row, json.loads(old))
    db.commit()
    db.refresh(row)
    return record(row, user, db)


def preference_row(db, row, user):
    return (
        db.query(PMSWorkspaceEntry)
        .filter_by(workspace_id=row.workspace_id, author_id=user.id, kind=PREFERENCES)
        .first()
    )


@router.get("/dashboards/catalog")
def catalog(user: User = Depends(get_current_user)):
    return {
        "widgets": list(WIDGETS.values()),
        "templates": [
            {
                "id": key,
                "name": name,
                "configuration": template_config(key).model_dump(mode="json"),
            }
            for key, name, _ in TEMPLATES
        ],
        "sources": {
            "tasks": ["count", "estimated_hours", "actual_hours", "story_points"],
            "projects": ["count", "progress_percent", "budget_amount", "actual_cost"],
            "time": ["count", "duration_hours"],
            "activity": ["count"],
            "sprints": ["count"],
            "milestones": ["count"],
            "risks": ["count", "risk_score"],
        },
        "limits": {"widgets": 50, "source_records": 10000},
    }


@router.post("/dashboards/suggest")
def suggest(
    data: Suggest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if data.workspace_id:
        workspace_member(db, data.workspace_id, user)
    if data.provider:
        from .dashboard_suggestions import ai_preview

        preview = ai_preview(db, user, request, data)
        if preview is not None:
            return preview
    text = data.prompt.lower()
    key = (
        "executive"
        if "executive" in text or "portfolio" in text
        else (
            "team"
            if "team" in text or "workload" in text
            else (
                "sprint"
                if "sprint" in text or "agile" in text
                else (
                    "time"
                    if "hours" in text
                    else "deadlines" if "deadline" in text else "project_overview"
                )
            )
        )
    )
    config = template_config(key)
    if "priority" in text and any(word in text for word in ["donut", "pie", "chart"]):
        config = template_config("blank")
        config.widgets = template_config("tasks").widgets[5:6]
    return {
        "configuration": config.model_dump(mode="json"),
        "mode": "guided",
        "message": "Guided keyword-based layout suggestion. No AI provider was used. Review and confirm before saving; record data is queried separately under your permissions.",
    }


@router.get("/dashboards")
def listing(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    output = []
    preferences = {}
    for row in scoped(db, user).order_by(PMSWorkspaceEntry.id.desc()).all():
        if not visible(row, user, db):
            continue
        payload = record(row, user, db)
        if row.workspace_id not in preferences:
            pref = preference_row(db, row, user)
            preferences[row.workspace_id] = json.loads(pref.body) if pref else {}
        pref = preferences[row.workspace_id].get(str(row.id), {})
        output.append(
            {
                **payload,
                "favorite": bool(pref.get("favorite")),
                "last_viewed_at": pref.get("last_viewed_at"),
            }
        )
    return output


@router.post("/dashboards", status_code=201)
def create(
    data: Create, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    workspace, member = workspace_member(db, data.workspace_id, user)
    if workspace.organization_id != organization_id_for(user):
        raise HTTPException(404, "Workspace not found")
    if member.role == "Guest":
        raise HTTPException(403, "Guests cannot create dashboards")
    share_allowed(db, user, data.workspace_id, data)
    payload = data.model_dump(mode="json", exclude={"workspace_id"}, exclude_none=True)
    payload.setdefault(
        "configuration", template_config("project_overview").model_dump(mode="json")
    )
    payload.update(
        revision=1, deleted_at=None, updated_at=now(), last_editor_id=user.id
    )
    row = PMSWorkspaceEntry(
        workspace_id=data.workspace_id,
        author_id=user.id,
        kind=KIND,
        body=json.dumps(payload),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return record(row, user, db)


@router.get("/dashboards/{did}")
def detail(
    did: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    row = find(db, user, did)
    if json.loads(row.body).get("deleted_at"):
        raise HTTPException(404, "Dashboard is in Trash")
    return record(row, user, db)


@router.put("/dashboards/{did}")
def edit(
    did: int,
    data: Edit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = find(db, user, did, editable=True)
    old = json.loads(row.body)
    if old.get("deleted_at"):
        raise HTTPException(409, "Restore this dashboard before editing")
    share_allowed(db, user, row.workspace_id, data)
    if row.author_id != user.id and (
        data.visibility != old["visibility"]
        or data.shared_users is not None
        and data.model_dump()["shared_users"] != old.get("shared_users", [])
        or data.archived is not None
        and data.archived != old.get("archived", False)
    ):
        raise HTTPException(
            403, "Only the owner can change sharing or archive the dashboard"
        )
    old.update(data.model_dump(mode="json", exclude={"revision"}, exclude_none=True))
    return persist(db, row, old, data.revision, user)


@router.post("/dashboards/{did}/query")
def query(
    did: int,
    config: Configuration,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = find(db, user, did)
    if json.loads(row.body).get("deleted_at"):
        raise HTTPException(404, "Dashboard is in Trash")
    return Engine(db, user, row.workspace_id).batch(config)


@router.get("/dashboards/{did}/scope")
def scope(
    did: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    from .models import (
        PMSTag,
        PMSTaskTag,
        PMSTask,
        PMSSprint,
        PMSWorkspaceTeam,
        PMSCustomField,
    )

    row = find(db, user, did)
    engine = Engine(db, user, row.workspace_id)
    projects = [
        {"id": p.id, "name": p.name, "status": p.status} for p in engine.projects
    ]
    sprints = (
        db.query(PMSSprint).filter(PMSSprint.project_id.in_(engine.ids)).all()
        if engine.ids
        else []
    )
    tags = (
        db.query(PMSTag)
        .join(PMSTaskTag, PMSTaskTag.tag_id == PMSTag.id)
        .join(PMSTask, PMSTask.id == PMSTaskTag.task_id)
        .filter(PMSTask.project_id.in_(engine.ids), PMSTask.deleted_at == None)
        .distinct()
        .all()
        if engine.ids
        else []
    )
    teams = (
        db.query(PMSWorkspaceTeam).filter_by(workspace_id=row.workspace_id).all()
        if engine.ids
        else []
    )
    fields = (
        db.query(PMSCustomField).filter(PMSCustomField.project_id.in_(engine.ids)).all()
        if engine.ids
        else []
    )
    return {
        "projects": projects,
        "people": [{"id": uid, "name": name} for uid, name in engine.people.items()],
        "sprints": [{"id": r.id, "name": r.name} for r in sprints],
        "teams": [{"id": r.id, "name": r.name} for r in teams],
        "tags": [{"id": r.id, "name": r.name} for r in tags],
        "custom_fields": [{"id": r.id, "name": r.name} for r in fields],
    }


@router.post("/dashboards/{did}/favorite")
def favorite(
    did: int,
    data: Preference,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = find(db, user, did)
    pref = preference_row(db, row, user)
    body = json.loads(pref.body) if pref else {}
    body.setdefault(str(did), {})["favorite"] = data.favorite
    if pref:
        pref.body = json.dumps(body)
    else:
        db.add(
            PMSWorkspaceEntry(
                workspace_id=row.workspace_id,
                author_id=user.id,
                kind=PREFERENCES,
                body=json.dumps(body),
            )
        )
    db.commit()
    return {"favorite": data.favorite}


@router.post("/dashboards/{did}/visit")
def visit(
    did: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    row = find(db, user, did)
    pref = preference_row(db, row, user)
    body = json.loads(pref.body) if pref else {}
    body.setdefault(str(did), {})["last_viewed_at"] = now()
    if pref:
        pref.body = json.dumps(body)
    else:
        db.add(
            PMSWorkspaceEntry(
                workspace_id=row.workspace_id,
                author_id=user.id,
                kind=PREFERENCES,
                body=json.dumps(body),
            )
        )
    db.commit()
    return {"viewed": True}


@router.get("/dashboards/{did}/history")
def history(
    did: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    row = find(db, user, did, editable=True)
    records = (
        db.query(PMSWorkspaceEntry)
        .filter_by(workspace_id=row.workspace_id, kind=HISTORY)
        .order_by(PMSWorkspaceEntry.id.desc())
        .all()
    )
    return [
        {**json.loads(r.body), "id": r.id, "created_at": r.created_at}
        for r in records
        if json.loads(r.body).get("dashboard_id") == did
    ][:30]


@router.post("/dashboards/{did}/history/{rid}/restore")
def restore_version(
    did: int,
    rid: int,
    data: Revision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = find(db, user, did, editable=True)
    prior = db.get(PMSWorkspaceEntry, rid)
    if (
        not prior
        or prior.kind != HISTORY
        or json.loads(prior.body).get("dashboard_id") != did
    ):
        raise HTTPException(404, "Revision not found")
    old = json.loads(row.body)
    if old.get("deleted_at"):
        raise HTTPException(409, "Restore dashboard from Trash first")
    previous = json.loads(prior.body)
    old.update(
        configuration=Configuration.model_validate(
            previous["configuration"]
        ).model_dump(mode="json"),
        name=previous["name"],
        description=previous.get("description", ""),
    )
    return persist(db, row, old, data.revision, user)


@router.post("/dashboards/{did}/duplicate", status_code=201)
def duplicate(
    did: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    row = find(db, user, did)
    old = record(row)
    return create(
        Create(
            workspace_id=row.workspace_id,
            name=(old["name"] + " (copy)")[:120],
            description=old.get("description", ""),
            configuration=configuration(row),
            visibility="private",
            icon=old.get("icon", "dashboard"),
            accent=old.get("accent", "#6d3df5"),
        ),
        db,
        user,
    )


@router.post("/dashboards/{did}/transfer")
def transfer(
    did: int,
    data: Transfer,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = find(db, user, did, owner=True)
    member = (
        db.query(PMSWorkspaceMember)
        .filter_by(workspace_id=row.workspace_id, user_id=data.owner_id)
        .first()
    )
    if not member or member.role == "Guest":
        raise HTTPException(422, "New owner must be a workspace collaborator")
    old = json.loads(row.body)
    # Include ownership in the compare-and-swap, so a concurrent transfer cannot win silently.
    if old["revision"] != data.revision:
        raise HTTPException(409, "Dashboard changed")
    old.update(revision=data.revision + 1, updated_at=now(), last_editor_id=user.id)
    before = row.body
    if (
        db.execute(
            update(PMSWorkspaceEntry)
            .where(
                PMSWorkspaceEntry.id == did,
                PMSWorkspaceEntry.body == before,
                PMSWorkspaceEntry.author_id == user.id,
            )
            .values(author_id=data.owner_id, body=json.dumps(old))
        ).rowcount
        != 1
    ):
        raise HTTPException(409, "Dashboard changed")
    snapshot(db, row, json.loads(before))
    db.commit()
    db.refresh(row)
    return record(row)


@router.post("/dashboards/{did}/trash")
def trash(
    did: int,
    data: Revision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = find(db, user, did, owner=True)
    old = json.loads(row.body)
    old["deleted_at"] = old.get("deleted_at") or now()
    return persist(db, row, old, data.revision, user)


@router.post("/dashboards/{did}/restore")
def restore(
    did: int,
    data: Revision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = find(db, user, did, owner=True)
    old = json.loads(row.body)
    old["deleted_at"] = None
    return persist(db, row, old, data.revision, user)


@router.delete("/dashboards/{did}")
def permanent(
    did: int,
    data: Permanent,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = find(db, user, did, owner=True)
    old = json.loads(row.body)
    if not old.get("deleted_at") or data.name != old["name"]:
        raise HTTPException(
            422, "Move to Trash and type the exact dashboard name first"
        )
    if old["revision"] != data.revision:
        raise HTTPException(409, "Dashboard changed")
    if (
        db.execute(
            PMSWorkspaceEntry.__table__.delete().where(
                PMSWorkspaceEntry.id == did, PMSWorkspaceEntry.body == row.body
            )
        ).rowcount
        != 1
    ):
        raise HTTPException(409, "Dashboard changed")
    for prior in (
        db.query(PMSWorkspaceEntry)
        .filter_by(workspace_id=row.workspace_id, kind=HISTORY)
        .all()
    ):
        if json.loads(prior.body).get("dashboard_id") == did:
            db.delete(prior)
    db.commit()
    return {"deleted": True}
