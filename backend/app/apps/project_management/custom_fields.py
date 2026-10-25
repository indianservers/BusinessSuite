"""Project-scoped typed fields; definitions and values use project permissions."""
import json
import math
import re
from urllib.parse import urlparse
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.input_validation import national_phone,calling_code,email_address
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import accessible_project_query, can_access_project, get_project_for_action, get_task_project_for_action
from .models import PMSCustomField, PMSCustomFieldValue, PMSProject

router = APIRouter()


class FieldInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    field_type: Literal["text", "long_text", "number", "money", "date", "checkbox", "dropdown", "email", "phone", "website", "rating", "progress"]
    options: list[str] = Field(default_factory=list, max_length=50)
    task_type: str = Field(default="", max_length=40)


class ValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | float | bool | None
    country_code: str | None = None


def field_data(field):
    return {"id": field.id, "name": field.name, "field_type": field.field_type,
            "options": json.loads(field.options_json), "task_type": field.task_type, "created_at": field.created_at, "project_id": field.project_id}


@router.get("/projects/{project_id}/custom-fields")
def list_fields(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_project_for_action(db, project_id, user)
    fields = db.query(PMSCustomField).filter_by(project_id=project_id).order_by(PMSCustomField.id).all()
    return {"fields": [field_data(field) for field in fields],
            "can_manage": can_access_project(db, project, user, "edit_project")}


@router.post("/projects/{project_id}/custom-fields", status_code=201)
def create_field(project_id: int, data: FieldInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = get_project_for_action(db, project_id, user, "edit_project")
    if data.task_type:
        from .task_types import validate_task_type
        validate_task_type(db, data.task_type, project.organization_id)
    name = data.name.strip()
    options = [option.strip() for option in data.options]
    if not name or any(not option or len(option) > 120 for option in options) or len(options) != len(set(options)):
        raise HTTPException(422, "Use a name and unique, non-empty options of up to 120 characters")
    if (data.field_type == "dropdown") != bool(options):
        raise HTTPException(422, "Only dropdown fields require options")
    if db.query(PMSCustomField).filter_by(project_id=project_id).count() >= 50:
        raise HTTPException(422, "This project already has 50 custom fields")
    if db.query(PMSCustomField).filter_by(project_id=project_id, name=name).first():
        raise HTTPException(409, "A field with this name already exists")
    field = PMSCustomField(project_id=project_id, name=name, task_type=data.task_type, field_type=data.field_type, options_json=json.dumps(options))
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
    fields = db.query(PMSCustomField).filter_by(project_id=task.project_id).filter(or_(PMSCustomField.task_type == "", PMSCustomField.task_type == task.work_type)).order_by(PMSCustomField.id).all()
    values = {row.field_id: json.loads(row.value_json) for row in db.query(PMSCustomFieldValue).filter_by(task_id=task_id)}
    return {"fields": [{**field_data(field), "value": values.get(field.id).get('national_number') if field.field_type=='phone' and isinstance(values.get(field.id),dict) else values.get(field.id), "country_code": values.get(field.id).get('country_code') if field.field_type=='phone' and isinstance(values.get(field.id),dict) else None} for field in fields],
            "can_edit": can_access_project(db, project, user, "manage_tasks"),
            "can_manage": can_access_project(db, project, user, "edit_project")}


@router.put("/tasks/{task_id}/custom-fields/{field_id}")
def save_value(task_id: int, field_id: int, data: ValueInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task, _ = get_task_project_for_action(db, task_id, user, "manage_tasks")
    field = db.query(PMSCustomField).filter_by(id=field_id, project_id=task.project_id).first()
    if not field or (field.task_type and field.task_type != task.work_type):
        raise HTTPException(404, "Field not found for this task type and project")
    value = data.value
    valid = value is None
    if value is not None:
        if field.field_type in {"text", "long_text"}: valid = isinstance(value, str) and len(value) <= (20000 if field.field_type == "long_text" else 4000)
        elif field.field_type in {"number", "money"}: valid = type(value) in (int, float) and math.isfinite(value)
        elif field.field_type == "rating": valid = type(value) in (int, float) and math.isfinite(value) and float(value).is_integer() and 0 <= value <= 5
        elif field.field_type == "progress": valid = type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100
        elif field.field_type in {'email','phone'}:
            try:
                if field.field_type=='email':email_address(value)
                else:national_phone(value);calling_code(data.country_code)
                valid=True
            except ValueError as exc:raise HTTPException(422,detail=str(exc)) from None
        elif field.field_type == "website":
            try:
                valid = isinstance(value, str) and len(value) <= 2048 and not any(character.isspace() for character in value) and urlparse(value).scheme in {"http", "https"} and bool(urlparse(value).hostname)
            except ValueError:
                valid = False
        elif field.field_type == "checkbox": valid = type(value) is bool
        elif field.field_type == "dropdown": valid = isinstance(value, str) and value in json.loads(field.options_json)
        elif field.field_type == "date":
            try:
                valid = isinstance(value, str) and date.fromisoformat(value).isoformat() == value
            except (ValueError, TypeError): valid = False
    if not valid:
        raise HTTPException(422, "Value does not match this field's type or options")
    if field.field_type=='phone' and value is not None:value={'national_number':value,'country_code':data.country_code}
    row = db.query(PMSCustomFieldValue).filter_by(task_id=task_id, field_id=field_id).first()
    if row: row.value_json = json.dumps(value)
    else: db.add(PMSCustomFieldValue(task_id=task_id, field_id=field_id, value_json=json.dumps(value)))
    db.commit()
    return {"field_id": field_id, "value": value}


@router.get("/custom-fields")
def field_manager(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    projects = accessible_project_query(db, user).all()
    names = {project.id: project for project in projects}
    fields = db.query(PMSCustomField).filter(PMSCustomField.project_id.in_(list(names))).order_by(PMSCustomField.name).all()
    return {"fields": [{**field_data(field), "project_name": names[field.project_id].name,
                        "can_manage": can_access_project(db, names[field.project_id], user, "edit_project")} for field in fields],
            "projects": [{"id": project.id, "name": project.name, "can_manage": can_access_project(db, project, user, "edit_project")} for project in projects]}


class EditFieldInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    options: list[str] = Field(default_factory=list, max_length=50)


@router.put("/projects/{project_id}/custom-fields/{field_id}")
def edit_field(project_id: int, field_id: int, data: EditFieldInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_project_for_action(db, project_id, user, "edit_project")
    field = db.query(PMSCustomField).filter_by(id=field_id, project_id=project_id).first()
    if not field:
        raise HTTPException(404, "Field not found")
    name, options = data.name.strip(), [option.strip() for option in data.options]
    if not name or any(not option or len(option) > 120 for option in options) or len(options) != len(set(options)):
        raise HTTPException(422, "Use a name and unique non-empty options")
    if (field.field_type == "dropdown") != bool(options):
        raise HTTPException(422, "Only dropdown fields require options")
    duplicate = db.query(PMSCustomField).filter_by(project_id=project_id, name=name).first()
    if duplicate and duplicate.id != field_id:
        raise HTTPException(409, "A field with this name already exists")
    if field.field_type == "dropdown":
        used = {json.loads(row.value_json) for row in db.query(PMSCustomFieldValue).filter_by(field_id=field_id) if json.loads(row.value_json) is not None}
        if not used.issubset(set(options)):
            raise HTTPException(409, "Keep options that are already used by tasks")
    field.name, field.options_json = name, json.dumps(options)
    db.commit()
    return field_data(field)
