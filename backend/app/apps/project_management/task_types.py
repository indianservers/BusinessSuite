"""Organization-scoped type definitions used by task creation."""
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import accessible_project_query, organization_id_for, has_any_permission, PMS_GLOBAL_MANAGE_PROJECTS
from .models import PMSTaskType, PMSTask, PMSProject

router = APIRouter()
BUILTINS = ["Task", "Story", "Bug", "Sub-task"]


class TypeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=40)
    plural_name: str = Field(default="", max_length=60)
    description: str = Field(default="", max_length=1000)
    category: str = Field(default="General", min_length=1, max_length=60)
    icon: Literal["task", "milestone", "form", "meeting", "bug", "account", "asset", "goal", "request", "finance"] = "task"
    color: str = "#7c3aed"
    default_priority: Literal["Low", "Medium", "High", "Urgent"] = "Medium"
    archived: bool = False


def output(row, usage=0):
    return {"id": row.id, "name": row.name, "plural_name": row.plural_name or row.name + "s", "description": row.description, "category": row.category,
            "icon": row.icon, "color": row.color, "default_priority": row.default_priority,
            "archived": row.archived, "builtin": False, "usage": usage}


@router.get("/task-types")
def list_types(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project_ids = accessible_project_query(db, user).with_entities(PMSProject.id)
    usage = dict(db.query(PMSTask.work_type, func.count(PMSTask.id)).filter(PMSTask.project_id.in_(project_ids), PMSTask.deleted_at.is_(None)).group_by(PMSTask.work_type).all())
    custom = db.query(PMSTaskType).filter_by(organization_id=organization_id_for(user)).order_by(PMSTaskType.name).all()
    builtins = [{"id": None, "name": name, "plural_name": {"Story": "Stories", "Sub-task": "Sub-tasks"}.get(name, name + "s"), "description": "Built-in work item type", "category": "General", "icon": "bug" if name == "Bug" else "task", "color": "#7c3aed", "default_priority": "Medium", "archived": False, "builtin": True, "usage": usage.get(name, 0)} for name in BUILTINS]
    return {"types": builtins + [output(row, usage.get(row.name, 0)) for row in custom],
            "can_manage": has_any_permission(user, PMS_GLOBAL_MANAGE_PROJECTS)}


def persist(db, data, user, row=None):
    if not has_any_permission(user, PMS_GLOBAL_MANAGE_PROJECTS):
        raise HTTPException(403, "Task type administration permission required")
    name = data.name.strip()
    if not name or not data.category.strip() or not re.fullmatch(r"#[a-fA-F0-9]{6}", data.color):
        raise HTTPException(422, "Provide a name, category and six-digit hex color")
    if name.casefold() in {name.casefold() for name in BUILTINS}:
        raise HTTPException(409, "This is a built-in task type")
    if row and row.name != name:
        raise HTTPException(409, "Names are stable identifiers; create another type instead of renaming")
    duplicate = db.query(PMSTaskType).filter(PMSTaskType.organization_id == organization_id_for(user), func.lower(PMSTaskType.name) == name.lower()).first()
    if duplicate and (row is None or duplicate.id != row.id):
        raise HTTPException(409, "A task type with this name already exists")
    row = row or PMSTaskType(organization_id=organization_id_for(user))
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    row.name, row.category = name, data.category.strip()
    row.plural_name = data.plural_name.strip() or name + "s"
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Task type name conflict")
    return output(row)


@router.post("/task-types", status_code=201)
def create_type(data: TypeInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return persist(db, data, user)


@router.put("/task-types/{type_id}")
def edit_type(type_id: int, data: TypeInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.query(PMSTaskType).filter_by(id=type_id, organization_id=organization_id_for(user)).first()
    if not row:
        raise HTTPException(404, "Task type not found")
    return persist(db, data, user, row)


def validate_task_type(db, name, organization_id):
    if name in BUILTINS:
        return
    row = db.query(PMSTaskType).filter_by(organization_id=organization_id, name=name, archived=False).first()
    if not row:
        raise HTTPException(422, "Choose an active task type in this organization")
