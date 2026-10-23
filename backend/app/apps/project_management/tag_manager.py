"""Organization tag governance, with usage limited to accessible active tasks."""
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import accessible_project_query, has_any_permission, organization_id_for, PMS_GLOBAL_MANAGE_PROJECTS
from .models import PMSTag, PMSTaskTag, PMSTask, PMSProject

router = APIRouter()


class TagInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    color: str = "#7c3aed"


class DeleteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tag_ids: list[int] = Field(min_length=1, max_length=100)


def can_manage(user):
    return has_any_permission(user, PMS_GLOBAL_MANAGE_PROJECTS)


def managed_tag(db, tag_id, user):
    if not can_manage(user):
        raise HTTPException(403, "Tag administration permission required")
    row = db.query(PMSTag).filter_by(id=tag_id, organization_id=organization_id_for(user)).first()
    if not row:
        raise HTTPException(404, "Tag not found in your organization")
    return row


@router.get("/tag-manager")
def library(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tags = db.query(PMSTag).filter_by(organization_id=organization_id_for(user)).order_by(PMSTag.name).all()
    projects = accessible_project_query(db, user).with_entities(PMSProject.id)
    usage = db.query(PMSTaskTag.tag_id, PMSTask.id, PMSProject.id, PMSProject.name).join(PMSTask, PMSTask.id == PMSTaskTag.task_id).join(PMSProject, PMSProject.id == PMSTask.project_id).filter(PMSTask.project_id.in_(projects), PMSTask.deleted_at.is_(None), PMSTaskTag.tag_id.in_([tag.id for tag in tags])).all()
    result = []
    for tag in tags:
        rows = [row for row in usage if row[0] == tag.id]
        locations = {row[2]: row[3] for row in rows}
        result.append({"id": tag.id, "name": tag.name, "color": tag.color, "created_at": tag.created_at,
                       "usage": len(rows), "projects": [{"id": key, "name": name} for key, name in locations.items()]})
    return {"tags": result, "can_manage": can_manage(user)}


@router.put("/tag-manager/{tag_id}")
def edit_tag(tag_id: int, data: TagInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tag = managed_tag(db, tag_id, user)
    name = data.name.strip()
    if not name or not re.fullmatch(r"#[0-9a-fA-F]{6}", data.color):
        raise HTTPException(422, "Provide a name and six-digit hex color")
    duplicate = db.query(PMSTag).filter(PMSTag.organization_id == organization_id_for(user), func.lower(PMSTag.name) == name.lower(), PMSTag.id != tag_id).first()
    if duplicate:
        raise HTTPException(409, "A tag with that name already exists")
    tag.name, tag.color = name, data.color
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A tag with that name already exists")
    return {"id": tag.id, "name": tag.name, "color": tag.color}


@router.post("/tag-manager/delete")
def delete_tags(data: DeleteInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tags = [managed_tag(db, tag_id, user) for tag_id in set(data.tag_ids)]
    ids = [tag.id for tag in tags]
    db.query(PMSTaskTag).filter(PMSTaskTag.tag_id.in_(ids)).delete(synchronize_session=False)
    for tag in tags:
        db.delete(tag)
    db.commit()
    return {"deleted": ids}
