"""Conversational, private agent authoring. Proposals never activate work.

Definitions reuse saved profiles, existing assistant messages, provider telemetry
and reviewed scheduler previews. The server owns the transcript and review hash.
"""
import json,re
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from typing import Literal
from uuid import UUID,uuid5,NAMESPACE_URL
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field,model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_operator.assistant_models import AssistantConversation,AssistantMessage
from app.ai_operator.suite_tools import Strict,TOOLS
from app.ai_operator.saved_agents import Config,access,store,public as profile_public
from app.ai_operator.agent_templates import templates
from app.ai_operator.service import digest
from app.ai_agents.security import company,verify,seal

router=APIRouter(prefix='/suite/agents/builder',tags=['Conversational agent builder'])
Provider=Literal['preferred','local','gemini','openai','claude']


class ScheduleRule(Strict):
    frequency:Literal['daily','weekly','once']='daily'
    at:str=Field(default='09:00',pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    weekday:int|None=Field(default=None,ge=0,le=6)
    expires_days:int=Field(default=30,ge=1,le=365)


class Draft(Strict):
    name:str=Field(min_length=1,max_length=120)
    instructions:str=Field(min_length=1,max_length=4000)
    tools:list[str]=Field(default_factory=list,max_length=40)
    memory:list[str]=Field(default_factory=list,max_length=20)
    run_prompt:str=Field(default='',max_length=4000)
    schedule:ScheduleRule|None=None
    question:str|None=Field(default=None,max_length=1000)


class Message(Strict):
    request_key:UUID
    text:str=Field(min_length=1,max_length=4000)
    context_id:int|None=Field(default=None,gt=0)
    revision:int|None=Field(default=None,ge=1)
    workspace_id:int|None=Field(default=None,gt=0)
    project_id:int|None=Field(default=None,gt=0)
    module:Literal['CRM','PMS','HRMS','SRM','FAM']|None=None
    provider:Provider='preferred'
    execution_provider:Provider|None=None
    timezone:str='Asia/Kolkata'

    @model_validator(mode='after')
    def valid(self):
        from app.ai_operator.suite_memory import MemoryText
        MemoryText.safe_text(self.text)
        if re.search(r'\b(?:AIza[A-Za-z0-9_-]{20,}|AQ\.[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})\b',self.text):raise ValueError('Configure credentials in the server connection vault, not agent instructions')
        try:ZoneInfo(self.timezone)
        except (ValueError,KeyError):raise ValueError('Choose an IANA timezone') from None
        return self


class Apply(Strict):
    preview_hash:str=Field(min_length=64,max_length=64)


def owned(db,user,ident,lock=False):
    from app.ai_operator.suite import authorize
    q=db.query(AssistantConversation).filter_by(id=ident,user_id=user.id,organization_id=company(user),deleted_at=None)
    row=(q.with_for_update() if lock else q).first()
    if not row or not row.references.get('agent_builder'):raise HTTPException(404,'Agent builder conversation not found')
    verify(db,user,row.security_context,history=True)
    if authorize(db,user,row.workspace_id)!=row.references['scope_key']:raise HTTPException(403,'Builder workspace changed')
    return row


def local_draft(text,previous,module,prediction=None):
    lower=text.casefold();items=templates();key=None
    choices=[('invoice-followup',r'invoice|collection'),('finance',r'finance|accounting|voucher'),
        ('recruitment',r'recruit|interview|hiring'),('performance',r'performance|productivity'),
        ('lead-qualification',r'qualif'),('customer-followup',r'customer follow|follow.up agent'),
        ('delivery',r'delivery|customer commitment'),('project',r'project coordinator|project manager|project agent'),
        ('management-reporting',r'management|weekly report|monthly report'),('business-intelligence',r'business intelligence|analytics agent'),
        ('marketing',r'marketing|campaign'),('support',r'customer support'),('hr',r'\bhr\b|hrms|onboarding'),('crm-sales',r'\bcrm\b|sales assistant|sales agent')]
    configuration_only=bool(previous and re.match(r'(?i)^\s*(?:at\b|only\b|read.only\b|remember\b|call it\b|name it\b|use (?:local|gemini)\b|no schedule\b|manual only\b)',text))
    if not configuration_only:
        for name,pattern in choices:
            if re.search(pattern,lower):key=name;break
    if not key and not configuration_only and (not previous or re.match(r'(?i)^(?:create|build|design|set up|i need)\b',text)):
        if prediction and prediction['score']>=.80 and prediction['margin']>=.20 and prediction['label'] in {t['id'] for t in items}:
            key=prediction['label'];prediction['used']=True
    if key:
        chosen=next(t for t in items if t['id']==key)
        draft=Draft(name=chosen['name'],instructions=chosen['instructions'],tools=chosen['tools'])
    elif previous:draft=Draft.model_validate(previous)
    else:
        fallback=next(t for t in items if t['id']=={'PMS':'project','HRMS':'hr','SRM':'invoice-followup','FAM':'finance'}.get(module,'crm-sales'))
        draft=Draft(name=fallback['name'],instructions=fallback['instructions'],tools=fallback['tools'],question='What role and work should this agent handle?')
    if previous and not key:draft.question=None
    objective=re.search(r'(?i)\b(?:that|which|who)\s+(.+)',text)
    if objective:
        draft.run_prompt=objective[1].strip()
        draft.instructions=re.sub(r'\nRequested objective:.*$','',draft.instructions,flags=re.S)+'\nRequested objective: '+draft.run_prompt
    elif not previous:draft.run_prompt=''
    named=re.search(r'(?i)\b(?:call it|name (?:it|the agent)|named)\s+["“]?([^"”\n.!]+)',text)
    if named:draft.name=named[1].strip()[:120]
    if re.search(r'\bread.only\b|no changes|only read',lower):draft.tools=[t for t in draft.tools if TOOLS[t].method=='GET']
    scope=re.search(r'(?i)\bonly\s+(CRM|PMS|HRMS|SRM|FAM)\b',text)
    if scope:draft.tools=[t for t in draft.tools if TOOLS[t].module==scope[1].upper()]
    explicit=re.findall(r'\b(?:crm|pms|hrms|srm|fam)\.[a-z_]+\b',lower)
    if explicit:
        if any(t not in TOOLS for t in explicit):draft.question='One requested tool is unavailable. Choose from the approved tool catalog.'
        else:draft.tools=list(dict.fromkeys([*draft.tools,*explicit]))[:40]
    if re.search(r'\b(?:no schedule|remove (?:the )?schedule|manual only|unschedule)\b',lower):draft.schedule=None
    elif re.search(r'\bevery\b|\bdaily\b|\bweekly\b|\bat\s+\d',lower):
        rule=draft.schedule or ScheduleRule()
        if re.search(r'\bweekly\b|every (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)',lower):rule.frequency='weekly'
        elif re.search(r'\bdaily\b|every (?:day|morning|evening)',lower):rule.frequency='daily'
        weekday=re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',lower)
        if weekday:rule.weekday='monday tuesday wednesday thursday friday saturday sunday'.split().index(weekday[1])
        clock=re.search(r'\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b',lower)
        if clock:
            hour=int(clock[1]);minute=int(clock[2] or '0')
            if hour>23 or minute>59 or clock[3] and not 1<=hour<=12:draft.question='What valid time should the agent run?'
            else:
                if clock[3]:hour=hour%12+(12 if clock[3]=='pm' else 0)
                rule.at=f'{hour:02}:{minute:02}'
        elif 'evening' in lower:rule.at='18:00'
        expiry=re.search(r'\b(?:for|expires? (?:in|after))\s+(\d{1,3})\s+days?\b',lower)
        if expiry:
            days=int(expiry[1])
            if 1<=days<=365:rule.expires_days=days
            else:draft.question='Choose an expiry from 1 to 365 days.'
        if re.search(r'weekdays|monthly|hourly|every \d+ (?:hours?|minutes?)',lower):draft.question='This builder currently supports daily or weekly schedules. Which cadence should I prepare?'
        draft.schedule=rule
    memory=re.search(r'(?i)\bremember\s*:\s*(.+)',text)
    if memory:draft.memory=list(dict.fromkeys([*draft.memory,memory[1].strip()]))[:20]
    if not draft.tools:draft.question='No tools remain for that scope. Which supported module or role should the agent use?'
    control=re.search(r'(?i)\bat\s+\d|\b(?:daily|weekly|every|call it|name it|remember|use local|use gemini|read.only|manual only|no schedule|only CRM|only PMS|only HRMS)\b',text)
    if previous and not key and not draft.run_prompt and not control and not draft.question:
        draft.run_prompt=text
        draft.instructions+='\nRequested objective: '+text
    if draft.schedule and not draft.run_prompt:draft.question='What specific work should the agent prepare each time it runs?'
    return draft


def schedule_spec(rule,zone):
    if not rule:return None
    current=datetime.now(ZoneInfo(zone));hour,minute=map(int,rule.at.split(':'))
    first=current.replace(hour=hour,minute=minute,second=0,microsecond=0)
    if rule.frequency=='weekly' and rule.weekday is not None:first+=timedelta(days=(rule.weekday-first.weekday())%7)
    if first<=current:first+=timedelta(days=7 if rule.frequency=='weekly' else 1)
    # Round-trip normalizes a nonexistent daylight-saving wall time.
    first=first.astimezone(timezone.utc)
    expiry=min(first+timedelta(days=rule.expires_days),datetime.now(timezone.utc)+timedelta(days=365))
    return {'scheduled_at':first.isoformat(),'expires_at':expiry.isoformat(),'timezone':zone,'frequency':rule.frequency}


def constraints_for(text,prior):
    result=dict(prior or {})
    if re.search(r'(?i)\bread.only\b|\bonly read\b|\bno changes\b',text):result['read_only']=True
    elif re.search(r'(?i)\ballow (?:reviewed )?(?:writes|changes|actions)\b',text):result['read_only']=False
    scoped=re.search(r'(?i)\bonly\s+(CRM|PMS|HRMS|SRM|FAM)\b',text)
    if scoped:result['modules']=[scoped[1].upper()]
    if re.search(r'(?i)\bonly\s+use\b',text):
        named=re.findall(r'\b(?:crm|pms|hrms|srm|fam)\.[a-z_]+\b',text.casefold())
        if named:result['tools']=list(dict.fromkeys(named))
    return result


def public(row):
    refs=row.references
    return {'context_id':row.id,'revision':refs['revision'],'draft':refs.get('draft'),'config':refs.get('config'),
        'preview_hash':refs.get('preview_hash'),'schedule':refs.get('schedule'),'question':refs.get('question'),
        'agent_id':refs.get('applied_agent_id'),'schedule_id':refs.get('applied_schedule_id'),'provider':refs.get('provider'),
        'local_prediction':refs.get('local_prediction'),
        'constraints':refs.get('constraints',{}),
        'knowledge':refs.get('knowledge',[]),'execution':'Saving creates a private profile and optional schedule preview. Activation and business actions require separate review.'}


@router.get('/model-status')
def model_status(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    from app.ai_operator.builder_tensorflow import status
    authorize(db,user,None);return status()


@router.get('/{ident}')
def get(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident)
    messages=db.query(AssistantMessage).filter_by(conversation_id=row.id,tool='agent.builder').order_by(AssistantMessage.id).limit(20)
    history=[]
    for message in messages:
        verify(db,user,message.security_context,history=True);history.append({'text':message.prompt,'proposal':message.proposal})
    return {**public(row),'messages':history}


@router.get('')
def listing(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    scope=authorize(db,user,workspace_id)
    rows=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=workspace_id,deleted_at=None).filter(
        AssistantConversation.references['agent_builder'].as_boolean()==True,AssistantConversation.references['scope_key'].as_string()==scope).order_by(AssistantConversation.id.desc()).limit(30)
    items=[]
    for row in rows:
        try:items.append(public(owned(db,user,row.id)))
        except HTTPException:continue
    return {'items':items}


@router.delete('/{ident}')
def archive(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_agents.services.audit import AiAuditService
    row=owned(db,user,ident,True);row.deleted_at=datetime.now(timezone.utc)
    AiAuditService(db).log(user=user,agent_id=None,module='CROSS',action='agent_builder.archived',input_json={'context_id':ident},output_json={'archived':True},status='success')
    db.commit();return {'archived':True}


@router.post('/messages')
def message(data:Message,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize,_require_ai_rate_limit
    scope=authorize(db,user,data.workspace_id)
    if not data.context_id:
        # Serialize initial retries on PostgreSQL without adding parallel storage.
        db.query(User.id).filter_by(id=user.id).with_for_update().one()
        initial=db.query(AssistantConversation.id).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(AssistantConversation.references['agent_builder'].as_boolean()==True,AssistantConversation.references['initial_request_key'].as_string()==str(data.request_key)).first()
    else:initial=None
    row=owned(db,user,data.context_id or (initial[0] if initial else None),True) if data.context_id or initial else None
    if row and (row.workspace_id!=data.workspace_id or row.references['project_id']!=data.project_id):raise HTTPException(409,'Continue in the original builder workspace/project')
    hashed=digest(data.model_dump(mode='json',exclude={'request_key'}))
    if row:
        previous=db.query(AssistantMessage).filter_by(conversation_id=row.id,request_key=str(data.request_key),tool='agent.builder').first()
        if previous:
            if previous.request_hash!=hashed:raise HTTPException(409,'Request key belongs to a different builder message')
            verify(db,user,previous.security_context,history=True);return previous.result
        if row.references.get('applied_agent_id'):raise HTTPException(409,'This proposal was saved. Start a new builder or edit the saved agent.')
        if data.revision!=row.references['revision']:raise HTTPException(409,'Builder changed; reload the latest proposal')
        if row.references['revision']>=20:raise HTTPException(422,'Start a new builder after twenty follow-ups')
    _require_ai_rate_limit(db,request,user,bucket='agent_builder')
    previous_draft=(row.references if row else {}).get('draft');provider=data.provider
    if provider=='preferred':
        from app.ai_operator.intelligence import select_default
        provider,config=select_default(db,user,scope,data.module,data.workspace_id)
    else:
        from app.ai_operator.provider_scope import resolve_provider
        config=resolve_provider(db,user,provider,data.workspace_id) if provider!='local' else None
    prediction=None
    if provider=='local':
        from app.ai_operator.builder_tensorflow import predict
        prediction=predict(data.text)
        if prediction:prediction={**prediction,'used':False}
        draft=local_draft(data.text,previous_draft,data.module,prediction)
    else:
        from app.ai_operator.providers import generate_json
        from app.ai_agents.services.advanced_security import AiDataRedactionService
        if not config:raise HTTPException(409,'Builder provider is unavailable')
        from app.ai_agents.security_catalog import SUITE
        tools=[{'name':t,'module':v.module,'description':v.description} for t,v in TOOLS.items() if t in SUITE]
        outbound={'task':'Author a private non-executable agent configuration. Retain unchanged prior choices. Ask a question when necessary. Select only listed tool names. Do not invent IDs, configure connections, execute actions or activate schedules. Schedule options: daily, weekly, once, 24-hour time, weekday 0=Monday, expiry 1..365 days. Required business rights are checked separately by the application.',
            'request':data.text,'previous_draft':previous_draft,'templates':templates(),'tools':tools,'timezone':data.timezone}
        prompt=AiDataRedactionService().redact_text(json.dumps(outbound))
        draft=Draft.model_validate(generate_json(db,user,config,prompt=prompt,schema=Draft.model_json_schema(),purpose='agent_builder',output_type=Draft,usage_scope=scope,module='CROSS'))
    selected_provider=data.execution_provider or ((row.references.get('config') or {}).get('provider') if row else None) or 'preferred'
    if re.search(r'(?i)\buse\s+(?:the\s+)?local\b',data.text):selected_provider='local'
    elif re.search(r'(?i)\buse\s+gemini\b',data.text):selected_provider='gemini'
    constraints=constraints_for(data.text,(row.references if row else {}).get('constraints'))
    if constraints.get('tools'):draft.tools=constraints['tools']
    if constraints.get('read_only'):draft.tools=[t for t in draft.tools if t in TOOLS and TOOLS[t].method=='GET']
    if constraints.get('modules'):draft.tools=[t for t in draft.tools if t in TOOLS and TOOLS[t].module in constraints['modules']]
    if not draft.tools:draft.question='The requested scope leaves no supported tools. Which scope or tools should this agent use?'
    if draft.schedule and not draft.run_prompt:draft.question=draft.question or 'What specific work should the agent prepare each time it runs?'
    proposal=None
    if draft.tools:
        modules=sorted({TOOLS[t].module for t in draft.tools if t in TOOLS})
        try:proposal=Config(name=draft.name,instructions=draft.instructions,tools=draft.tools,
            modules=modules,memory=draft.memory,provider=selected_provider,
            workspace_id=data.workspace_id,project_id=data.project_id if 'PMS' in modules else None)
        except ValueError as exc:raise HTTPException(422,'Agent proposal has invalid instructions, memory, provider or tools') from None
        access(db,user,proposal)
    if row is None:
        if db.query(AssistantConversation.id).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(AssistantConversation.references['agent_builder'].as_boolean()==True).count()>=50:raise HTTPException(422,'Archive unused agent designs before adding more')
        row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=data.workspace_id,title='Agent builder: '+draft.name[:140],references={'agent_builder':True,'initial_request_key':str(data.request_key),'scope_key':scope,'project_id':data.project_id,'revision':0})
        db.add(row);db.flush()
    branch=db.info.get('branch_context');revision=row.references['revision']+1
    schedule=schedule_spec(draft.schedule,data.timezone)
    if schedule:schedule['prompt']=draft.run_prompt
    value={'config':proposal.model_dump() if proposal else None,'schedule':schedule,'revision':revision,'branch_id':getattr(branch,'branch_id',None)}
    preview_hash=digest(value)
    row.references={**row.references,**value,'draft':draft.model_dump(mode='json'),'constraints':constraints,'provider':provider,'local_prediction':prediction,'question':draft.question,
        'preview_hash':preview_hash,'draft_grant':seal(db,user,preview_hash),'knowledge':[{'tool':t,'description':TOOLS[t].description} for t in draft.tools if t in TOOLS and TOOLS[t].method=='GET']}
    result=public(row)
    db.add(AssistantMessage(conversation_id=row.id,request_key=str(data.request_key),request_hash=hashed,prompt=data.text,tool='agent.builder',arguments={},proposal=draft.model_dump(mode='json'),result=result,status='answered'))
    db.commit();return result


@router.post('/{ident}/apply')
def apply(ident:int,data:Apply,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator import agent_schedules as schedules
    from app.ai_operator.saved_agents import owned as profile_owned
    row=owned(db,user,ident,True);refs=row.references
    if data.preview_hash!=refs.get('preview_hash') or refs.get('question') or not refs.get('config'):raise HTTPException(409,'Review the latest complete agent proposal')
    value={k:refs[k] for k in ('config','schedule','revision','branch_id')}
    if digest(value)!=data.preview_hash:raise HTTPException(409,'Agent proposal changed')
    verify(db,user,refs['draft_grant'],payload=data.preview_hash,confirmation=not bool(refs.get('applied_agent_id')))
    config=Config.model_validate(refs['config']);access(db,user,config)
    profile=profile_owned(db,user,refs['applied_agent_id']) if refs.get('applied_agent_id') else store(db,user,config)
    row.references={**row.references,'applied_agent_id':profile.id}
    scheduled=None
    if refs.get('schedule'):
        branch=db.info.get('branch_context')
        if getattr(branch,'branch_id',None)!=refs['branch_id']:raise HTTPException(409,'Review the schedule in its original branch')
        key=uuid5(NAMESPACE_URL,f'agent-builder:{row.id}:{data.preview_hash}')
        from app.apps.automation.models import AutomationScheduledJob as Job
        previous=db.query(Job).filter_by(job_type=schedules.KIND,created_by=user.id,organization_id=company(user)).filter(Job.payload_json['ai_request_key'].as_string()==str(key)).first()
        if previous:scheduled=schedules.public(schedules.owned(db,user,previous.id))
        else:
            body=schedules.Schedule(request_key=key,agent_id=profile.id,**refs['schedule'])
            scheduled=schedules.preview(body,db,user)
        row.references={**row.references,'applied_schedule_id':scheduled['id']}
    db.commit()
    return {**public(row),'agent':profile_public(profile),'schedule_preview':scheduled}
