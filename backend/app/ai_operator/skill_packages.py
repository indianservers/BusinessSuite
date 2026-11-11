"""Portable skill definitions with server-owned, session-bound import reviews."""
from datetime import datetime,timedelta,timezone
import re
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field,model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_operator import saved_agents as agents
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_operator.suite_tools import Strict,TOOLS
from app.ai_operator.service import digest
from app.ai_agents.security import company,seal,verify

router=APIRouter(prefix='/suite/agents/catalog',tags=['Skill packages'])


class Package(Strict):
    format:Literal['businesssuite-agent-skill-v1']
    name:str=Field(min_length=1,max_length=120)
    instructions:str=Field(min_length=1,max_length=4000)
    tools:list[str]=Field(min_length=1,max_length=40)

    @model_validator(mode='after')
    def valid(self):
        if re.search(r'\b(?:AIza[A-Za-z0-9_-]{20,}|AQ\.[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})\b',self.name+'\n'+self.instructions):raise ValueError('Keep credentials in the server connection vault')
        agents.Skill(name=self.name,instructions=self.instructions,tools=self.tools)
        return self


class Import(Strict):
    request_key:UUID
    package:Package
    workspace_id:int|None=Field(default=None,gt=0)


class Confirmation(Strict):
    preview_hash:str=Field(min_length=64,max_length=64)


def now():return datetime.now(timezone.utc)


def payload(data):return {'package':data.package.model_dump(),'workspace_id':data.workspace_id}


def owned(db,user,ident):
    row=db.query(AssistantConversation).filter_by(id=ident,user_id=user.id,organization_id=company(user),deleted_at=None).with_for_update().populate_existing().first()
    if not row or not row.references.get('skill_import'):raise HTTPException(404,'Skill import not found')
    verify(db,user,row.security_context,history=True)
    from app.ai_operator.suite import authorize
    if authorize(db,user,row.workspace_id)!=row.references['scope_key']:raise HTTPException(403,'Skill import scope changed')
    return row


def public(row):
    refs=row.references
    return {'id':row.id,'package':refs['package'],'workspace_id':row.workspace_id,'preview_hash':refs['preview_hash'],
        'expires_at':refs['expires_at'],'skill_id':refs.get('skill_id'),
        'tools':[{'name':t,'module':TOOLS[t].module,'reviewed_action':TOOLS[t].method!='GET'} for t in refs['package']['tools']]}


def check_access(db,user,package,workspace_id):
    modules=sorted({TOOLS[t].module for t in package.tools})
    return agents.access(db,user,agents.Config(name=package.name,instructions=package.instructions,tools=package.tools,modules=modules,workspace_id=workspace_id))


@router.get('/skills/{ident}/export')
def export(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=agents.owned_skill(db,user,ident)
    if row.references.get('library_origin'):raise HTTPException(409,'Use the organization library to share linked definitions; portable exports require an original private skill')
    value=Package(format='businesssuite-agent-skill-v1',**{k:row.references['config'][k] for k in ('name','instructions','tools')})
    check_access(db,user,value,row.workspace_id)
    agents.audit(db,user,row,'skill_exported');db.commit();return value.model_dump()


@router.post('/skill-imports/preview')
def preview(data:Import,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    scope=check_access(db,user,data.package,data.workspace_id)
    # One actor's import requests serialize; existing request keys never create
    # another review or private skill, including after a lost response.
    db.query(User.id).filter_by(id=user.id).with_for_update().one()
    hashed=digest(payload(data))
    existing=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(
        AssistantConversation.references['skill_import_key'].as_string()==str(data.request_key)).first()
    if existing:
        row=owned(db,user,existing.id)
        if row.references['preview_hash']!=hashed:raise HTTPException(409,'Import request key belongs to a different definition')
        return public(row)
    active=db.query(AssistantConversation.id).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(
        AssistantConversation.references['skill_import'].as_boolean()==True,
        AssistantConversation.references['skill_id'].as_integer().is_(None),
        AssistantConversation.references['expires_at'].as_string()>now().isoformat()).count()
    if active>=20:raise HTTPException(422,'Finish existing import reviews or wait for their one-hour expiry')
    row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=data.workspace_id,title='Skill import: '+data.package.name[:120],
        references={'skill_import':True,'skill_import_key':str(data.request_key),'scope_key':scope,**payload(data),
            'preview_hash':hashed,'grant':seal(db,user,hashed),'expires_at':(now()+timedelta(hours=1)).isoformat()})
    db.add(row);db.flush();db.commit();return public(row)


@router.post('/skill-imports/{ident}/confirm')
def confirm(ident:int,data:Confirmation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident);refs=row.references
    hashed=digest({k:refs[k] for k in ('package','workspace_id')})
    if hashed!=data.preview_hash or hashed!=refs['preview_hash']:raise HTTPException(409,'Import changed; review the original definition')
    if refs.get('skill_id'):return {'skill':agents.public_skill(agents.owned_skill(db,user,refs['skill_id'])),'import_id':row.id}
    if now()>=datetime.fromisoformat(refs['expires_at']):raise HTTPException(409,'Import review expired; upload again')
    verify(db,user,refs['grant'],payload=hashed,confirmation=True)
    value=Package.model_validate(refs['package']);check_access(db,user,value,row.workspace_id)
    skill=agents.store_skill(db,user,agents.Skill(**{k:refs['package'][k] for k in ('name','instructions','tools')},workspace_id=row.workspace_id))
    row.references={**refs,'skill_id':skill.id};db.commit()
    return {'skill':agents.public_skill(skill),'import_id':row.id}
