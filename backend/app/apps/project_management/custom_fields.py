"""Typed custom columns shared across company tasks and projects."""
import json
import math
from urllib.parse import urlparse
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.input_validation import national_phone,calling_code,email_address
from app.core.deps import get_current_user,get_db
from app.models.user import User
from .access import accessible_project_query,can_access_project,get_project_for_action,get_task_project_for_action,organization_id_for,has_any_permission
from .models import PMSCustomField,PMSCustomFieldValue,PMSProjectCustomFieldValue,PMSProject
router=APIRouter()

class FieldInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name:str=Field(min_length=1,max_length=120)
    field_type:Literal["text","long_text","number","money","date","checkbox","dropdown","email","phone","website","rating","progress"]
    options:list[str]=Field(default_factory=list,max_length=50)
    task_type:str=Field(default="",max_length=40)
    entity_type:Literal["task","project","both"]="task"

class LibraryFieldInput(FieldInput):
    scope:Literal["company","project"]="company"
    project_id:int|None=Field(None,gt=0)

class EditFieldInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name:str=Field(min_length=1,max_length=120)
    options:list[str]=Field(default_factory=list,max_length=50)
    archived:bool|None=None

class ValueInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    value:str|float|bool|None
    country_code:str|None=None

class RecordBatch(BaseModel):
    model_config=ConfigDict(extra="forbid")
    entity:Literal["task","project"]
    ids:list[int]=Field(max_length=100)


def shared_manager(user):
    return user.is_superuser or has_any_permission(user,{"pms_admin"})


def field_data(field):
    return {"id":field.id,"name":field.name,"field_type":field.field_type,"options":json.loads(field.options_json),"task_type":field.task_type,"created_at":field.created_at,"project_id":field.project_id,"entity_type":field.entity_type,"archived":field.archived,"scope":"project" if field.project_id else "company"}


def library_query(db,user):
    ids=accessible_project_query(db,user).with_entities(PMSProject.id)
    return db.query(PMSCustomField).filter(or_(PMSCustomField.project_id.in_(ids),and_(PMSCustomField.project_id.is_(None),PMSCustomField.organization_id==organization_id_for(user))))


def applicable(db,user,project,entity,task_type=""):
    q=library_query(db,user).filter(PMSCustomField.archived.is_(False),PMSCustomField.entity_type.in_([entity,"both"]),or_(PMSCustomField.project_id==project.id,PMSCustomField.project_id.is_(None)))
    if entity=="task":q=q.filter(or_(PMSCustomField.task_type=="",PMSCustomField.task_type==task_type))
    return q.order_by(PMSCustomField.id).all()


def manage_field(db,user,field):
    if field.project_id:return get_project_for_action(db,field.project_id,user,"edit_project")
    if field.organization_id!=organization_id_for(user) or not shared_manager(user):raise HTTPException(403,"Company custom columns require a PMS administrator")


def validate_definition(data):
    name=data.name.strip();options=[o.strip() for o in data.options]
    if not name or any(not o or len(o)>120 for o in options) or len(options)!=len(set(options)):raise HTTPException(422,"Use a name and unique, non-empty options of up to 120 characters")
    if (data.field_type=="dropdown")!=bool(options):raise HTTPException(422,"Only dropdown fields require options")
    if data.entity_type=="project" and data.task_type:raise HTTPException(422,"Task-type scope applies only to task fields")
    return name,options


def persist_definition(db,user,data,project=None):
    name,options=validate_definition(data)
    if project:get_project_for_action(db,project.id,user,"edit_project")
    elif not shared_manager(user):raise HTTPException(403,"Company custom columns require a PMS administrator")
    company=organization_id_for(user)
    if not project and company is None:raise HTTPException(403,"Choose a verified company before creating shared fields")
    if data.task_type:
        from .task_types import validate_task_type
        validate_task_type(db,data.task_type,company)
    scope=f"project:{project.id}" if project else f"company:{company}"
    q=db.query(PMSCustomField).filter(PMSCustomField.project_id==project.id) if project else db.query(PMSCustomField).filter(PMSCustomField.scope_key==scope)
    if q.count()>=100:raise HTTPException(422,"This location already has 100 custom fields")
    if q.filter(PMSCustomField.name==name).first():raise HTTPException(409,"A field with this name already exists in this location")
    row=PMSCustomField(project_id=project.id if project else None,organization_id=company,scope_key=scope,entity_type=data.entity_type,name=name,task_type=data.task_type,field_type=data.field_type,options_json=json.dumps(options),archived=False)
    db.add(row)
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,"A field with this name already exists")
    return field_data(row)


@router.get("/custom-fields")
def field_manager(include_archived:bool=False,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    projects=accessible_project_query(db,user).all();names={p.id:p for p in projects}
    fields=library_query(db,user)
    if not include_archived:fields=fields.filter(PMSCustomField.archived.is_(False))
    return {"fields":[{**field_data(f),"project_name":names[f.project_id].name if f.project_id in names else "All company projects","can_manage":can_access_project(db,names[f.project_id],user,"edit_project") if f.project_id in names else shared_manager(user)} for f in fields.order_by(PMSCustomField.name)],"projects":[{"id":p.id,"name":p.name,"can_manage":can_access_project(db,p,user,"edit_project")} for p in projects],"can_manage_shared":shared_manager(user)}


@router.post("/custom-fields",status_code=201)
def create_shared_field(data:LibraryFieldInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    project=get_project_for_action(db,data.project_id,user,"edit_project") if data.scope=="project" and data.project_id else None
    if data.scope=="project" and project is None:raise HTTPException(422,"Choose a project")
    return persist_definition(db,user,data,project)


@router.get("/projects/{project_id}/custom-fields")
def list_fields(project_id:int,entity:Literal["task","project"]="task",db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    project=get_project_for_action(db,project_id,user)
    fields=library_query(db,user).filter(PMSCustomField.archived.is_(False),PMSCustomField.entity_type.in_([entity,"both"]),or_(PMSCustomField.project_id==project_id,PMSCustomField.project_id.is_(None))).order_by(PMSCustomField.id).all()
    return {"fields":[field_data(f) for f in fields],"can_manage":can_access_project(db,project,user,"edit_project")}


@router.post("/projects/{project_id}/custom-fields",status_code=201)
def create_field(project_id:int,data:FieldInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return persist_definition(db,user,data,get_project_for_action(db,project_id,user,"edit_project"))


def edit_definition(db,user,field,data):
    manage_field(db,user,field)
    name,options=validate_definition(FieldInput(name=data.name,field_type=field.field_type,options=data.options,entity_type=field.entity_type,task_type=field.task_type))
    duplicate=library_query(db,user).filter(PMSCustomField.id!=field.id,PMSCustomField.name==name,PMSCustomField.project_id==field.project_id)
    if not field.project_id:duplicate=duplicate.filter(PMSCustomField.organization_id==field.organization_id)
    if duplicate.first():raise HTTPException(409,"A field with this name already exists")
    if field.field_type=="dropdown":
        used=[]
        for model in [PMSCustomFieldValue,PMSProjectCustomFieldValue]:used.extend(json.loads(r.value_json) for r in db.query(model).filter_by(field_id=field.id))
        if any(v is not None and v not in options for v in used):raise HTTPException(409,"Keep dropdown options already used by records")
    field.name,field.options_json=name,json.dumps(options)
    if data.archived is not None:field.archived=data.archived
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,"A field with this name already exists")
    return field_data(field)


@router.put("/custom-fields/{field_id}")
def edit_shared_field(field_id:int,data:EditFieldInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    field=library_query(db,user).filter(PMSCustomField.id==field_id).first()
    if not field:raise HTTPException(404,"Field not found")
    return edit_definition(db,user,field,data)


@router.put("/projects/{project_id}/custom-fields/{field_id}")
def edit_field(project_id:int,field_id:int,data:EditFieldInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    get_project_for_action(db,project_id,user,"edit_project")
    field=db.query(PMSCustomField).filter_by(id=field_id,project_id=project_id).first()
    if not field:raise HTTPException(404,"Field not found")
    return edit_definition(db,user,field,data)


def validate_value(field,data):
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
    return value


def record_fields(db,user,entity,ident):
    if entity=="task":
        record,project=get_task_project_for_action(db,ident,user);model=PMSCustomFieldValue;key="task_id"
    else:record=project=get_project_for_action(db,ident,user);model=PMSProjectCustomFieldValue;key="project_id"
    fields=applicable(db,user,project,entity,getattr(record,"work_type",""))
    values={r.field_id:json.loads(r.value_json) for r in db.query(model).filter(getattr(model,key)==ident)}
    return {"fields":[{**field_data(f),"value":values.get(f.id).get("national_number") if f.field_type=="phone" and isinstance(values.get(f.id),dict) else values.get(f.id),"country_code":values.get(f.id).get("country_code") if f.field_type=="phone" and isinstance(values.get(f.id),dict) else None} for f in fields],"can_edit":can_access_project(db,project,user,"manage_tasks" if entity=="task" else "edit_project"),"can_manage":can_access_project(db,project,user,"edit_project")}


@router.get("/tasks/{task_id}/custom-fields")
def task_fields(task_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return record_fields(db,user,"task",task_id)


@router.get("/projects/{project_id}/field-values")
def project_fields(project_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return record_fields(db,user,"project",project_id)


def apply_record_fields(db,user,entity,record,values,project=None,*,validate_only=False):
    if values is None:return
    if len(values)>100:raise HTTPException(422,"Too many custom field values")
    project=project or (db.get(PMSProject,record.project_id) if entity=="task" else record)
    definitions={f.id:f for f in applicable(db,user,project,entity,getattr(record,"work_type",""))}
    model=PMSCustomFieldValue if entity=="task" else PMSProjectCustomFieldValue;key="task_id" if entity=="task" else "project_id"
    prepared=[]
    for raw,value in values.items():
        if not str(raw).isdigit() or int(raw) not in definitions:raise HTTPException(422,"Custom field is not applicable to this record")
        field=definitions[int(raw)]
        try:data=ValueInput(**value) if isinstance(value,dict) else ValueInput(value=value)
        except ValidationError:raise HTTPException(422,"Invalid custom field value") from None
        prepared.append((field.id,validate_value(field,data)))
    if validate_only:return
    for field_id,value in prepared:
        row=db.query(model).filter(getattr(model,key)==record.id,model.field_id==field_id).first()
        if row:row.value_json=json.dumps(value)
        else:db.add(model(**{key:record.id,"field_id":field_id,"value_json":json.dumps(value)}))


@router.put("/tasks/{task_id}/custom-fields/{field_id}")
def save_value(task_id:int,field_id:int,data:ValueInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    task,project=get_task_project_for_action(db,task_id,user,"manage_tasks")
    apply_record_fields(db,user,"task",task,{str(field_id):data.model_dump()},project);db.commit()
    return {"field_id":field_id,"value":data.value}


@router.put("/projects/{project_id}/field-values/{field_id}")
def save_project_value(project_id:int,field_id:int,data:ValueInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    project=get_project_for_action(db,project_id,user,"edit_project")
    apply_record_fields(db,user,"project",project,{str(field_id):data.model_dump()});db.commit()
    return {"field_id":field_id,"value":data.value}


@router.post("/custom-fields/records")
def batch_records(data:RecordBatch,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if any(type(i)is not int or i<=0 for i in data.ids):raise HTTPException(422,"Use positive record IDs")
    return {"records":{str(i):record_fields(db,user,data.entity,i) for i in sorted(set(data.ids))}}


def copy_project_fields(db,source,target,task_map):
    """Clone project definitions and remap their values in the clone transaction."""
    mapping={}
    for field in db.query(PMSCustomField).filter_by(project_id=source.id).all():
        copied=PMSCustomField(project_id=target.id,organization_id=target.organization_id,scope_key=f"project:{target.id}",name=field.name,field_type=field.field_type,task_type=field.task_type,entity_type=field.entity_type,options_json=field.options_json,archived=field.archived)
        db.add(copied);db.flush();mapping[field.id]=copied.id
    def target_field(ident):
        if ident in mapping:return mapping[ident]
        field=db.get(PMSCustomField,ident)
        return ident if field and field.project_id is None and field.organization_id==target.organization_id else None
    for row in db.query(PMSProjectCustomFieldValue).filter_by(project_id=source.id).all():
        ident=target_field(row.field_id)
        if ident:db.add(PMSProjectCustomFieldValue(project_id=target.id,field_id=ident,value_json=row.value_json))
    if task_map:
        for row in db.query(PMSCustomFieldValue).filter(PMSCustomFieldValue.task_id.in_(task_map)).all():
            ident=target_field(row.field_id)
            if ident:db.add(PMSCustomFieldValue(task_id=task_map[row.task_id],field_id=ident,value_json=row.value_json))
