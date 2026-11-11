"""Private reusable agents. Profiles restrict capabilities; they never grant them.

Runs reuse suite conversations, module memory, reviews, checkpoints and receipts.
Recurring preparation reuses the durable scheduler; project event rules keep their consent controls.
"""
from typing import Literal
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field,model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_operator.suite_tools import Strict,TOOLS
from app.ai_operator.assistant_models import AssistantConversation,AssistantMessage
from app.ai_agents.security import company,verify
from app.ai_agents.services.audit import AiAuditService
from app.ai_operator.suite_memory import MemoryText

router=APIRouter(prefix='/suite/agents',tags=['Saved action agents'])


class Config(Strict):
    name:str=Field(min_length=1,max_length=120)
    instructions:str=Field(min_length=1,max_length=4000)
    modules:list[Literal['CRM','PMS','HRMS','SRM','FAM']]=Field(min_length=1,max_length=5)
    tools:list[str]=Field(min_length=1,max_length=40)
    memory:list[str]=Field(default_factory=list,max_length=20)
    workspace_id:int|None=Field(default=None,gt=0)
    project_id:int|None=Field(default=None,gt=0)
    provider:Literal['preferred','local','gemini','openai','claude']='preferred'
    skill_ids:list[int]=Field(default_factory=list,max_length=10)
    connection_ids:list[int]=Field(default_factory=list,max_length=20)
    mcp_ids:list[int]=Field(default_factory=list,max_length=10)
    environment:Literal['development','staging','production']='development'
    revision:int|None=Field(default=None,ge=1)

    @model_validator(mode='after')
    def valid(self):
        if not self.name.strip() or not self.instructions.strip():raise ValueError('Provide agent name and instructions')
        if len(set(self.modules))!=len(self.modules) or len(set(self.tools))!=len(self.tools):raise ValueError('Do not duplicate modules or tools')
        if self.provider=='local' and 'FAM' in self.modules:raise ValueError('Finance agents require a connected provider or the server module default')
        MemoryText.safe_text(self.instructions)
        for text in self.memory:MemoryText(text=text)
        for ids in (self.skill_ids,self.connection_ids,self.mcp_ids):
            if len(set(ids))!=len(ids) or any(type(i) is not int or i<=0 for i in ids):raise ValueError('Select unique existing positive binding IDs')
        from app.ai_agents.security_catalog import SUITE
        if any(name not in TOOLS or name not in SUITE or TOOLS[name].module not in self.modules for name in self.tools):raise ValueError('Select code-approved tools within the selected modules')
        return self


def access(db,user,data):
    from app.ai_operator.agent_memory import authorize
    scope=None
    for module in data.modules:scope=authorize(db,user,data.workspace_id,module,data.project_id)
    for ident in data.skill_ids:
        skill=owned_skill(db,user,ident)
        if skill.workspace_id!=data.workspace_id or not set(skill.references['config']['tools'])<=set(data.tools):raise HTTPException(403,'Skill tools must be explicitly allowed in this agent workspace')
    if data.connection_ids:
        from app.core.deps import RequirePermission
        from app.apps.power_apps.integrations.vault import connection
        RequirePermission('power_apps_view')(user)
        for ident in data.connection_ids:connection(db,user,data.environment,ident)
    if data.mcp_ids:
        from app.ai_operator.agent_mcp import owned as mcp_owned
        for ident in data.mcp_ids:
            binding=mcp_owned(db,user,ident)
            if binding.workspace_id!=data.workspace_id or binding.references['config']['environment']!=data.environment:raise HTTPException(403,'MCP binding is outside this agent workspace/environment')
    return scope


def owned(db,user,ident,lock=False):
    q=db.query(AssistantConversation).filter_by(id=ident,user_id=user.id,organization_id=company(user),deleted_at=None)
    row=(q.with_for_update() if lock else q).first()
    if not row or not row.references.get('saved_agent'):raise HTTPException(404,'Agent not found')
    verify(db,user,row.security_context,history=True)
    data=Config.model_validate(row.references['config'])
    if access(db,user,data)!=row.references['scope_key']:raise HTTPException(403,'Agent scope changed')
    return row


def public(row):
    return {'id':row.id,**row.references['config'],'revision':row.references['revision'],
        'library_origin':row.references.get('library_origin'),'execution':'reviewed','trigger_support':'Manual and reviewed recurring preparation; PMS playbooks, monitors and consent-bound event rules remain available through allowed tools.'}


@router.get('')
def listing(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    scope=authorize(db,user,workspace_id);items=[]
    rows=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=workspace_id,deleted_at=None).filter(
        AssistantConversation.references['saved_agent'].as_boolean()==True,
        AssistantConversation.references['scope_key'].as_string()==scope).order_by(AssistantConversation.id.desc()).limit(50)
    for row in rows:
        try:items.append(public(owned(db,user,row.id)))
        except HTTPException:continue
    from app.ai_agents.security_catalog import SUITE
    return {'items':items,'tools':[{'name':name,'module':tool.module,'write':tool.method!='GET','description':tool.description,'permissions':list(tool.permissions)} for name,tool in TOOLS.items() if name in SUITE and tool.module in ('CRM','PMS','HRMS','SRM','FAM')]}


@router.post('')
def create(data:Config,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=store(db,user,data);db.commit();return public(row)


def store(db,user,data):
    """Stage a profile in the caller's transaction, including compound reviews."""
    scope=access(db,user,data)
    count=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(AssistantConversation.references['saved_agent'].as_boolean()==True).count()
    if count>=50:raise HTTPException(422,'Archive an unused agent before adding more')
    row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=data.workspace_id,title=data.name,
        references={'saved_agent':True,'scope_key':scope,'revision':1,'config':data.model_dump(exclude={'revision'})})
    db.add(row);db.flush();audit(db,user,row,'created');return row


def audit(db,user,row,action):
    AiAuditService(db).log(user=user,agent_id=None,module='CROSS',action='saved_agent.'+action,
        input_json={'profile_id':row.id},output_json={'revision':row.references['revision']},status='success')


@router.put('/{ident}')
def edit(ident:int,data:Config,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,True);scope=access(db,user,data)
    if data.workspace_id!=row.workspace_id or scope!=row.references['scope_key']:raise HTTPException(422,'Agent workspace cannot change')
    if data.revision!=row.references['revision']:raise HTTPException(409,'Agent changed; reload before editing')
    row.references={**row.references,'revision':data.revision+1,'config':data.model_dump(exclude={'revision'})};row.title=data.name
    audit(db,user,row,'updated');db.commit();return public(row)


@router.delete('/{ident}')
def archive(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,True);row.deleted_at=datetime.now(timezone.utc);audit(db,user,row,'archived');db.commit();return {'archived':True}


@router.get('/{ident}/activity')
def activity(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    owned(db,user,ident)
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_operator.suite import owned as run_owned,public as run_public
    rows=db.query(SuiteRun).filter_by(user_id=user.id).filter(SuiteRun.result['request']['agent_id'].as_integer()==ident).order_by(SuiteRun.id.desc()).limit(50)
    return {'items':[run_public(run_owned(db,user,r.id)) for r in rows]}


def context(db,user,data,parent):
    pending=(parent.result or {}).get('request',{}).get('agent_id') if parent and parent.status in ('needs_clarification','awaiting_approval') else None
    if pending and data.agent_id and pending!=data.agent_id:
        raise HTTPException(409,'Finish or cancel the pending draft before switching agents, or start a new chat')
    ident=data.agent_id or ((parent.result or {}).get('request',{}).get('agent_id') if parent and parent.status in ('needs_clarification','awaiting_approval') else None)
    if not ident:return None
    row=owned(db,user,ident);runtime_access(db,user,row);profile=public(row)
    profile['skills']=[public_skill(owned_skill(db,user,i)) for i in profile['skill_ids']]
    from app.ai_operator.agent_mcp import owned as mcp_owned,public as mcp_public
    profile['mcp_tools']=[mcp_public(mcp_owned(db,user,i)) for i in profile['mcp_ids']]
    profile['connectors']=[]
    if profile['connection_ids']:
        from app.apps.power_apps.integrations import vault
        from app.apps.power_apps.integrations.registry import REGISTRY
        for i in profile['connection_ids']:
            conn=vault.connection(db,user,profile['environment'],i);spec=REGISTRY.get(conn.connector_id)
            profile['connectors'].append({'id':conn.id,'name':conn.name,'provider':conn.connector_id,'health':conn.health,
                'writes_enabled':conn.writes_enabled,'actions':[a.model_dump() for a in spec.actions] if spec else []})
    if data.workspace_id!=profile['workspace_id']:raise HTTPException(403,'Run this agent in its configured workspace')
    if data.module and data.module not in profile['modules']:raise HTTPException(403,'Module is outside this agent scope')
    if profile['project_id']:
        if data.project_id and data.project_id!=profile['project_id']:raise HTTPException(403,'Project is outside this agent scope')
        data.project_id=profile['project_id']
    data.agent_id=ident
    if not data.module and len(profile['modules'])==1:data.module=profile['modules'][0]
    if data.provider=='preferred':data.provider=profile['provider']
    return profile


class Skill(Strict):
    name:str=Field(min_length=1,max_length=120)
    instructions:str=Field(min_length=1,max_length=4000)
    tools:list[str]=Field(min_length=1,max_length=40)
    workspace_id:int|None=Field(default=None,gt=0)
    revision:int|None=Field(default=None,ge=1)

    @model_validator(mode='after')
    def valid(self):
        modules=sorted({TOOLS[t].module for t in self.tools if t in TOOLS})
        Config(name=self.name,instructions=self.instructions,modules=modules,tools=self.tools,workspace_id=self.workspace_id)
        return self


def owned_skill(db,user,ident,lock=False):
    query=db.query(AssistantConversation).filter_by(id=ident,user_id=user.id,organization_id=company(user),deleted_at=None)
    row=(query.with_for_update().populate_existing() if lock else query).first()
    if not row or not row.references.get('agent_skill'):raise HTTPException(404,'Skill not found')
    verify(db,user,row.security_context,history=True)
    from app.ai_operator.suite import authorize
    if authorize(db,user,row.workspace_id)!=row.references['scope_key']:raise HTTPException(403,'Skill scope changed')
    return row


def public_skill(row):return {'id':row.id,**row.references['config'],'revision':row.references['revision'],'library_origin':row.references.get('library_origin')}


def skill_version(db,row):
    value=public_skill(row);revision=value['revision']
    existing=db.query(AssistantMessage.id).filter_by(conversation_id=row.id,tool='agent.skill.version',request_key=f'skill-version:{revision}').first()
    if not existing:
        from app.ai_operator.service import digest
        db.add(AssistantMessage(conversation_id=row.id,request_key=f'skill-version:{revision}',request_hash=digest(value),
            prompt='Saved skill revision',tool='agent.skill.version',arguments={'revision':revision},result=value,status='stored'))
        db.flush()


@router.get('/catalog/skills/{ident}/versions')
def skill_versions(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned_skill(db,user,ident)
    values=db.query(AssistantMessage).filter_by(conversation_id=row.id,tool='agent.skill.version').order_by(AssistantMessage.id.desc()).limit(50)
    result=[]
    for version in values:
        verify(db,user,version.security_context,history=True);result.append(version.result)
    if not result:result=[public_skill(row)]
    return {'items':result,'current_revision':row.references['revision']}


@router.get('/catalog/skills')
def skills(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    scope=authorize(db,user,workspace_id)
    rows=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=workspace_id,deleted_at=None).filter(
        AssistantConversation.references['agent_skill'].as_boolean()==True,AssistantConversation.references['scope_key'].as_string()==scope).order_by(AssistantConversation.id.desc()).limit(50)
    return {'items':[public_skill(owned_skill(db,user,r.id)) for r in rows]}


def store_skill(db,user,data,row=None,origin=None):
    """Stage a skill and its version history in the caller's transaction."""
    modules=sorted({TOOLS[t].module for t in data.tools if t in TOOLS})
    scope=access(db,user,Config(name=data.name,instructions=data.instructions,modules=modules,tools=data.tools,workspace_id=data.workspace_id))
    if row:
        if data.revision!=row.references['revision']:raise HTTPException(409,'Skill changed; reload before editing')
        if data.workspace_id!=row.workspace_id:raise HTTPException(422,'Skill workspace cannot change')
        skill_version(db,row)
        row.references={**row.references,'revision':data.revision+1,'config':data.model_dump(exclude={'revision'})};row.title=data.name
    else:
        if db.query(AssistantConversation.id).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(AssistantConversation.references['agent_skill'].as_boolean()==True).count()>=50:raise HTTPException(422,'Archive unused skills before adding more')
        row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=data.workspace_id,title=data.name,
            references={'agent_skill':True,'scope_key':scope,'revision':1,'config':data.model_dump(exclude={'revision'})})
        db.add(row);db.flush()
    if origin is not None:row.references={**row.references,'library_origin':origin}
    skill_version(db,row);audit(db,user,row,'skill_updated' if data.revision else 'skill_created')
    return row


@router.post('/catalog/skills')
def create_skill(data:Skill,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=store_skill(db,user,data);db.commit();return public_skill(row)


@router.put('/catalog/skills/{ident}')
def update_skill(ident:int,data:Skill,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=store_skill(db,user,data,owned_skill(db,user,ident,True));db.commit();return public_skill(row)


@router.delete('/catalog/skills/{ident}')
def archive_skill(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned_skill(db,user,ident);row.deleted_at=datetime.now(timezone.utc);audit(db,user,row,'skill_archived');db.commit();return {'archived':True}


def enforce(db,user,run,steps):
    ident=(run.result or {}).get('request',{}).get('agent_id')
    if not ident:return
    row=owned(db,user,ident);runtime_access(db,user,row);profile=public(row)
    if profile['revision']!=(run.result or {}).get('agent',{}).get('revision'):raise HTTPException(409,'Agent changed since planning; prepare a fresh review')
    current={str(i):owned_skill(db,user,i).references['revision'] for i in profile['skill_ids']}
    if current!=(run.result or {}).get('agent',{}).get('skill_revisions',{}):raise HTTPException(409,'Agent skill changed since planning; prepare a fresh review')
    if any(s.tool not in profile['tools'] for s in steps):raise HTTPException(403,'Tool is outside this agent scope')


def runtime_access(db,user,row):
    from app.ai_operator.agent_library import validate_origin
    validate_origin(db,user,row)
    for ident in row.references.get('config',{}).get('skill_ids',[]):validate_origin(db,user,owned_skill(db,user,ident))
