"""Project-scoped typed fields; definitions and values use project permissions."""
import json
import math
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import can_access_project, get_project_for_action, get_task_project_for_action
from .models import PMSCustomField, PMSCustomFieldValue

router = APIRouter()


class FieldInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    field_type: Literal["text", "number", "date", "checkbox", "dropdown"]
    options: list[str] = Field(default_factory=list, max_length=50)


class ValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | float | bool | None


def field_data(field):
    return {"id": field.id, "name": field.name, "field_type": field.field_type,
            "options": json.loads(field.options_json)}


@router.get("/projects/{project_id}/custom-fields")
def list_fields(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_project_for_action(db, project_id, user)
    fields = db.query(PMSCustomField).filter_by(project_id=project_id).order_by(PMSCustomField.id).all()
    return {"fields": [field_data(field) for field in fields],
            "can_manage": can_access_project(db, project, user, "edit_project")}


@router.post("/projects/{project_id}/custom-fields", status_code=201)
def create_field(project_id: int, data: FieldInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_for_action(db, project_id, user, "edit_project")
    name = data.name.strip()
    options = [option.strip() for option in data.options]
    if not name or any(not option or len(option) > 120 for option in options) or len(options) != len(set(options)):
        raise HTTPException(422, "Use a name and unique, non-empty options of up to 120 characters")
    if (data.field_type == "dropdown") != bool(options):
        raise HTTPException(422, "Only dropdown fields require options")
    if db.query(PMSCustomField).filter_by(project_id=project_id).count() >= 50:
        raise HTTPException(422, "This project already has 50 custom fields")
    field = PMSCustomField(project_id=project_id, name=name, field_type=data.field_type, options_json=json.dumps(options))
    db.add(field)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A field with this name already exists")
    db.refresh(field)
    return field_data(field)


@router.get("/tasks/{task_id}/custom-fields")
def task_fields(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, project = get_task_project_for_action(db, task_id, user)
    fields = db.query(PMSCustomField).filter_by(project_id=task.project_id).order_by(PMSCustomField.id).all()
    values = {row.field_id: json.loads(row.value_json) for row in db.query(PMSCustomFieldValue).filter_by(task_id=task_id)}
    return {"fields": [{**field_data(field), "value": values.get(field.id)} for field in fields],
            "can_edit": can_access_project(db, project, user, "manage_tasks"),
            "can_manage": can_access_project(db, project, user, "edit_project")}


@router.put("/tasks/{task_id}/custom-fields/{field_id}")
def save_value(task_id: int, field_id: int, data: ValueInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, _ = get_task_project_for_action(db, task_id, user, "manage_tasks")
    field = db.query(PMSCustomField).filter_by(id=field_id, project_id=task.project_id).first()
    if not field:
        raise HTTPException(404, "Field not found in this project")
    value = data.value
    valid = value is None
    if value is not None:
        if field.field_type == "text": valid = isinstance(value, str) and len(value) <= 4000
        elif field.field_type == "number": valid = type(value) in (int, float) and math.isfinite(value)
        elif field.field_type == "checkbox": valid = type(value) is bool
        elif field.field_type == "dropdown": valid = isinstance(value, str) and value in json.loads(field.options_json)
        elif field.field_type == "date":
            try:
                valid = isinstance(value, str) and date.fromisoformat(value).isoformat() == value
            except (ValueError, TypeError): valid = False
    if not valid:
        raise HTTPException(422, "Value does not match this field's type or options")
    row = db.query(PMSCustomFieldValue).filter_by(task_id=task_id, field_id=field_id).first()
    if row: row.value_json = json.dumps(value)
    else: db.add(PMSCustomFieldValue(task_id=task_id, field_id=field_id, value_json=json.dumps(value)))
    db.commit()
    return {"field_id": field_id, "value": value}
