"""Persistent, versioned workspace tools. All data inherits organization/environment scope."""
from typing import Literal
from datetime import datetime, timezone
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field,field_validator
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.deps import get_db,RequirePermission
from .models import PowerResource
from .service import scoped,organization,validate_environment,serialize,record_change

router=APIRouter(prefix='/workspaces',tags=['Power Apps tools'],dependencies=[Depends(RequirePermission('power_apps_view'))])
Kind=Literal['forms','tables','app-builder','notifications']
class Entry(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(min_length=1,max_length=80)
    values:dict[str,str]=Field(max_length=30)
    @field_validator('values')
    @classmethod
    def bounded(cls,value):
        if any(len(k)>160 or len(v)>4000 for k,v in value.items()): raise ValueError('Entry values are too long')
        return value
class Definition(BaseModel):
    model_config=ConfigDict(extra='forbid')
    fields:list[str]=Field(default_factory=list,max_length=30)
    entries:list[Entry]=Field(default_factory=list,max_length=1000)
    content:str=Field(default='',max_length=16000)
    acknowledged:bool=False
    table_id:int|None=None
    @field_validator('fields')
    @classmethod
    def valid_fields(cls,values):
        values=[v.strip() for v in values]
        if any(not v or len(v)>160 for v in values) or len(values)!=len(set(values)): raise ValueError('Use unique, nonempty field names')
        return values
class Payload(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=180)
    description:str=Field(default='',max_length=4000)
    definition:Definition
    expected_version:int|None=Field(default=None,ge=1)
    @field_validator('name')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():raise ValueError('Enter a name')
        return v.strip()
def query(db,user,environment,kind):
    validate_environment(db,user,environment)
    return scoped(db,PowerResource,user,environment).filter(PowerResource.application_id==kind,PowerResource.archived_at.is_(None))
def find(db,user,environment,kind,identity):
    row=query(db,user,environment,kind).filter(PowerResource.id==identity).first()
    if not row:raise HTTPException(404,'Resource not found')
    return row
def validate_definition(db,user,environment,kind,definition):
    if kind in ['forms','tables'] and not definition.fields:raise HTTPException(422,'Add at least one field')
    ids=[e.id for e in definition.entries]
    if len(ids)!=len(set(ids)):raise HTTPException(422,'Entry identities must be unique')
    if any(set(e.values)-set(definition.fields) for e in definition.entries):raise HTTPException(422,'Entry contains an unknown field; remove its data before removing the field')
    if kind not in ['forms','tables'] and definition.entries:raise HTTPException(422,'This tool does not accept table entries')
    if definition.table_id is not None:find(db,user,environment,'tables',definition.table_id)
@router.get('/{kind}')
def listing(kind:Kind,environment:str='development',db:Session=Depends(get_db),user=Depends(RequirePermission('power_apps_view'))):
    return {'items':[serialize(r) for r in query(db,user,environment,kind).order_by(PowerResource.id.desc()).limit(500)]}
@router.post('/{kind}',status_code=201)
def create(kind:Kind,data:Payload,environment:str='development',db:Session=Depends(get_db),user=Depends(RequirePermission('power_apps_create'))):
    validate_environment(db,user,environment);validate_definition(db,user,environment,kind,data.definition)
    row=PowerResource(organization_id=organization(user),environment=environment,application_id=kind,name=data.name,description=data.description,definition=data.definition.model_dump(),owner_user_id=user.id,status='draft',version=1)
    db.add(row);db.flush();record_change(db,user,row,'tool_created');db.commit();db.refresh(row);return serialize(row)
@router.get('/{kind}/{identity}')
def read(kind:Kind,identity:int,environment:str='development',db:Session=Depends(get_db),user=Depends(RequirePermission('power_apps_view'))):return serialize(find(db,user,environment,kind,identity))
@router.put('/{kind}/{identity}')
def update(kind:Kind,identity:int,data:Payload,environment:str='development',db:Session=Depends(get_db),user=Depends(RequirePermission('power_apps_edit'))):
    row=find(db,user,environment,kind,identity);validate_definition(db,user,environment,kind,data.definition)
    if data.expected_version is None:raise HTTPException(422,'Expected version is required')
    changed=query(db,user,environment,kind).filter(PowerResource.id==identity,PowerResource.version==data.expected_version).update({PowerResource.name:data.name,PowerResource.description:data.description,PowerResource.definition:data.definition.model_dump(),PowerResource.version:PowerResource.version+1,PowerResource.updated_at:func.now()},synchronize_session=False)
    if not changed:raise HTTPException(409,'Resource changed; refresh before saving')
    db.refresh(row);record_change(db,user,row,'tool_updated');db.commit();return serialize(row)
@router.delete('/{kind}/{identity}',status_code=204)
def remove(kind:Kind,identity:int,expected_version:int=Query(ge=1),environment:str='development',db:Session=Depends(get_db),user=Depends(RequirePermission('power_apps_delete'))):
    row=find(db,user,environment,kind,identity)
    if kind=='tables':
        for app in db.query(PowerResource).filter_by(organization_id=organization(user),environment=environment,application_id='app-builder',archived_at=None).all():
            if app.definition.get('table_id')==identity:raise HTTPException(409,'This table is used by an app page; unlink it first')
    changed=query(db,user,environment,kind).filter(PowerResource.id==identity,PowerResource.version==expected_version).update({PowerResource.archived_at:datetime.now(timezone.utc),PowerResource.version:PowerResource.version+1},synchronize_session=False)
    if not changed:raise HTTPException(409,'Resource changed; refresh before deleting')
    db.refresh(row);record_change(db,user,row,'tool_deleted');db.commit()
