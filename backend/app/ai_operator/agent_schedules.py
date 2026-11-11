"""Durable private agent schedules. Occurrences prepare conversations, never approve writes.

An immutable grant pins the profile/skill/connection revisions, tenant, branch and
initiating session. Recovery reuses the occurrence conversation and request key.
"""
import hmac
import calendar
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from uuid import UUID,uuid4,uuid5,NAMESPACE_URL
from typing import Literal
import httpx
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field,model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.apps.automation.models import AutomationScheduledJob as Job
from app.ai_operator.suite_tools import Strict
from app.ai_operator.reminders import now,utc,next_occurrence
from app.ai_agents.security import company,seal,verify
from app.ai_operator.service import digest
from app.ai_operator.agent_recurrence import Recurrence,next_custom_occurrence

router=APIRouter(prefix='/suite/agents/schedules',tags=['Agent schedules'])
KIND='ai_agent_schedule'


class Schedule(Recurrence):
    request_key:UUID
    agent_id:int=Field(gt=0)
    prompt:str=Field(min_length=1,max_length=6000)
    scheduled_at:datetime
    expires_at:datetime
    timezone:str='Asia/Kolkata'

    @model_validator(mode='after')
    def valid(self):
        from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
        from app.ai_operator.suite_memory import MemoryText
        if not self.prompt.strip():raise ValueError('Describe the work to prepare')
        # Credential-like material is never stored as scheduling instructions.
        MemoryText.safe_text(self.prompt)
        try:ZoneInfo(self.timezone)
        except (ValueError,ZoneInfoNotFoundError):raise ValueError('Choose an IANA timezone') from None
        if self.scheduled_at.utcoffset() is None or self.expires_at.utcoffset() is None:raise ValueError('Use timezone-aware times')
        if self.expires_at<=self.scheduled_at or self.expires_at>now()+timedelta(days=366):raise ValueError('Expiry must follow the first run and be within one year')
        return self


class Activation(Strict):
    preview_hash:str=Field(min_length=64,max_length=64)


def snapshot(db,user,ident):
    from app.ai_operator.saved_agents import owned,public,owned_skill,runtime_access
    row=owned(db,user,ident);runtime_access(db,user,row);profile=public(row)
    from app.apps.power_apps.integrations.vault import connection
    from app.ai_operator.agent_mcp import owned as mcp_owned
    return {'agent_id':ident,'revision':profile['revision'],
        'skills':{str(i):owned_skill(db,user,i).references['revision'] for i in profile['skill_ids']},
        'connections':{str(i):connection(db,user,profile['environment'],i).revision for i in profile['connection_ids']},
        'mcp':{str(i):mcp_owned(db,user,i).references['revision'] for i in profile['mcp_ids']},
        'workspace_id':profile['workspace_id'],'project_id':profile['project_id'],'name':profile['name']}


def owned(db,user,ident,lock=False):
    from app.ai_operator.suite import authorize
    authorize(db,user,None)
    q=db.query(Job).filter_by(id=ident,job_type=KIND,created_by=user.id,organization_id=company(user))
    row=(q.with_for_update().populate_existing() if lock else q).first()
    if not row:raise HTTPException(404,'Agent schedule not found')
    verify(db,user,row.payload_json['security_context'],history=True)
    return row


def public(row):
    data=row.payload_json
    return {'id':row.id,'status':row.status.removeprefix('agent_'),'spec':data['spec'],
        'agent_name':data['snapshot']['name'],'agent_revision':data['snapshot']['revision'],'workspace_id':data['snapshot']['workspace_id'],
        'next_at':utc(row.run_at) if row.run_at and row.status!='agent_paused' else None,'preview_hash':data['preview_hash'],'error':row.last_error,
        'occurrences':data.get('occurrences',[]),'pending':data.get('pending'),
        'paused_at':data.get('paused_at'),'controls':data.get('controls',[]),
        'event_source':{k:data['event_source'][k] for k in ('subscription_id','event','eligible')} if data.get('event_source') else None,
        'execution':'Read and prepare only; every proposed change requires review.'}


@router.post('/preview')
def preview(data:Schedule,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    from app.ai_agents.services.audit import AiAuditService
    authorize(db,user,None)
    if data.scheduled_at<=now():raise HTTPException(422,'Choose a future first run')
    branch=db.info.get('branch_context')
    if not branch or not branch.branch_id:raise HTTPException(422,'Select a concrete branch before scheduling an agent')
    frozen=snapshot(db,user,data.agent_id)
    spec=data.model_dump(mode='json',exclude={'request_key'},exclude_none=True)
    value={'spec':spec,'snapshot':frozen,'branch_id':branch.branch_id};hashed=digest(value)
    previous=db.query(Job).filter_by(job_type=KIND,organization_id=company(user),created_by=user.id).filter(Job.payload_json['ai_request_key'].as_string()==str(data.request_key)).first()
    if previous:
        if previous.payload_json['preview_hash']!=hashed:raise HTTPException(409,'Request key belongs to a different schedule')
        return public(owned(db,user,previous.id))
    if db.query(Job).filter_by(job_type=KIND,created_by=user.id,organization_id=company(user)).filter(Job.status.notin_(['agent_cancelled','agent_complete','agent_expired'])).count()>=50:
        raise HTTPException(422,'Cancel unused schedules before adding more')
    row=Job(job_type=KIND,module_name='ai',record_type='saved_agent',record_id=data.agent_id,
        organization_id=company(user),created_by=user.id,status='agent_preview',run_at=data.scheduled_at,
        payload_json={**value,'preview_hash':hashed,'ai_request_key':str(data.request_key),
            'security_context':seal(db,user,hashed),'occurrences':[]})
    db.add(row)
    try:
        db.flush();AiAuditService(db).log(user=user,agent_id=None,module='CROSS',action='agent_schedule.preview',input_json={'schedule_id':row.id},output_json={'agent_id':data.agent_id},status='success');db.commit()
    except IntegrityError:
        db.rollback()
        previous=db.query(Job).filter_by(job_type=KIND,organization_id=company(user),created_by=user.id).filter(Job.payload_json['ai_request_key'].as_string()==str(data.request_key)).first()
        if not previous or previous.payload_json['preview_hash']!=hashed:raise HTTPException(409,'Conflicting schedule request') from None
        return public(owned(db,user,previous.id))
    return public(row)


def grant(db,user,row,confirmation=False):
    data=row.payload_json
    value={k:data[k] for k in ('spec','snapshot','branch_id')}
    if data.get('event_source'):value['event_source']=data['event_source']
    if not hmac.compare_digest(digest(value),data['preview_hash']):raise HTTPException(409,'Agent schedule changed')
    verify(db,user,data['security_context'],payload=data['preview_hash'],confirmation=confirmation)
    if snapshot(db,user,data['spec']['agent_id'])!=data['snapshot']:raise HTTPException(409,'Agent, skill or connection changed; prepare a new schedule')


@router.post('/{ident}/activate')
def activate(ident:int,data:Activation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,True)
    if row.status!='agent_preview' or not hmac.compare_digest(data.preview_hash,row.payload_json['preview_hash']):raise HTTPException(409,'Reload the unactivated schedule preview')
    grant(db,user,row,True)
    if utc(row.run_at)<=now():raise HTTPException(409,'First run passed; prepare a fresh preview')
    row.status='agent_active';db.commit();return public(row)


@router.get('')
def listing(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,None)
    rows=db.query(Job).filter_by(job_type=KIND,created_by=user.id,organization_id=company(user)).order_by(Job.id.desc()).limit(100)
    return {'items':[public(owned(db,user,r.id)) for r in rows]}


@router.post('/{ident}/cancel')
def cancel(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,True)
    if row.status!='agent_cancelled':
        row.status='agent_cancelled';row.run_at=None
        control(db,user,row,'cancelled',now());db.commit()
    return public(row)


def control(db,user,row,action,instant):
    from app.ai_agents.services.audit import AiAuditService
    row.payload_json={**row.payload_json,'controls':[*row.payload_json.get('controls',[]),{'action':action,'at':instant.isoformat(),'status':row.status}][-30:]}
    AiAuditService(db).log(user=user,agent_id=None,module='CROSS',action='agent_schedule.'+action,
        input_json={'schedule_id':row.id},output_json={'status':row.status},status='success')


@router.post('/{ident}/pause')
def pause(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,True)
    if row.status=='agent_paused':return public(row)
    if row.status not in ('agent_active','agent_waiting','agent_preparing'):raise HTTPException(409,'Only an active schedule can be paused')
    instant=now()
    row.payload_json={**row.payload_json,'paused_status':row.status,'paused_run_at':utc(row.run_at).isoformat() if row.run_at else None,'paused_at':instant.isoformat()}
    # The worker wakes only to expire a paused schedule, never to prepare it.
    row.status='agent_paused';row.run_at=datetime.fromisoformat(row.payload_json['spec']['expires_at'])
    control(db,user,row,'paused',instant);db.commit();return public(row)


@router.post('/{ident}/resume')
def resume(ident:int,data:Activation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,True)
    if row.status!='agent_paused' or not hmac.compare_digest(data.preview_hash,row.payload_json['preview_hash']):raise HTTPException(409,'Review the paused schedule before resuming')
    instant=now()
    if instant>=datetime.fromisoformat(row.payload_json['spec']['expires_at']):
        row.status='agent_expired';row.run_at=None
        control(db,user,row,'expired',instant);db.commit();return public(row)
    grant(db,user,row,True)
    payload=row.payload_json;previous=payload['paused_status']
    if previous=='agent_active':
        previous_at=datetime.fromisoformat(payload['paused_run_at'])
        next_at=previous_at if previous_at>instant else next_agent_occurrence(payload['spec'],instant)
        row.run_at=next_at
        row.status='agent_active' if next_at and next_at<datetime.fromisoformat(payload['spec']['expires_at']) else 'agent_complete'
        if row.status=='agent_complete':row.run_at=None
    else:
        # Recover the same occurrence and deterministic request key. A response
        # from its pre-pause worker must not overwrite the resumed lease.
        pending={**payload['pending'],'claimed_at':(instant-timedelta(minutes=5)).isoformat(),'lease':str(uuid4())}
        payload={**payload,'pending':pending};row.status=previous;row.run_at=instant
    row.payload_json={**payload,'paused_at':None,'paused_status':None,'paused_run_at':None};row.last_error=None
    control(db,user,row,'resumed',instant);db.commit();return public(row)


def next_agent_occurrence(spec,current):
    if spec['frequency']=='custom':return next_custom_occurrence(spec,current)
    if spec['frequency']!='monthly':return next_occurrence(spec,current)
    from zoneinfo import ZoneInfo
    zone=ZoneInfo(spec['timezone'])
    anchor=datetime.fromisoformat(spec['scheduled_at']).astimezone(zone)
    local=current.astimezone(zone)
    for offset in range(14):
        month_index=local.year*12+local.month-1+offset
        year,month=divmod(month_index,12);month+=1
        day=min(anchor.day,calendar.monthrange(year,month)[1])
        candidate=anchor.replace(year=year,month=month,day=day).astimezone(timezone.utc)
        if candidate>current:return candidate
    raise ValueError('No next monthly agent occurrence')


def finish_occurrence(row,run,instant):
    """Advance from now, skipping missed runs instead of generating a backlog."""
    data=row.payload_json;pending=data['pending']
    row.payload_json={**data,'pending':None,'occurrences':[*data.get('occurrences',[]),{**pending,'run_id':run['id'],'status':run['status']}][-30:]}
    next_at=next_agent_occurrence(data['spec'],instant)
    row.run_at=next_at
    row.status='agent_active' if next_at and next_at<datetime.fromisoformat(data['spec']['expires_at']) else 'agent_complete'


def occurrence_run(db,user,pending,agent_id):
    """Follow corrections, not a superseded draft's obsolete terminal status."""
    from app.ai_operator.suite import owned as run_owned
    from app.ai_operator.suite_models import SuiteRun
    run=run_owned(db,user,pending['run_id'])
    for _ in range(100):
        request=(run.result or {}).get('request',{})
        if request.get('conversation_id')!=pending['conversation_id'] or request.get('agent_id')!=agent_id:
            raise HTTPException(409,'Scheduled conversation scope changed')
        if run.status!='superseded':return run
        children=db.query(SuiteRun.id).filter_by(user_id=user.id,scope_key=run.scope_key,workspace_id=run.workspace_id).filter(
            SuiteRun.result['request']['parent_run_id'].as_integer()==run.id,
            SuiteRun.result['request']['conversation_id'].as_integer()==pending['conversation_id']).limit(2).all()
        if len(children)!=1:raise HTTPException(409,'Scheduled follow-up chain needs review')
        run=run_owned(db,user,children[0][0])
    raise HTTPException(409,'Scheduled follow-up chain exceeds the history budget')


async def prepare_agent(app,user_id,session_id,company_id,branch_id,command):
    """Fixed canonical planning endpoint shared by schedules and orchestration."""
    from app.core.security import create_access_token
    token=create_access_token(str(user_id),expires_delta=timedelta(minutes=5),session_id=session_id)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url='http://agent-worker',timeout=150) as client:
        response=await client.post('/api/v1/ai-operator/suite/commands',headers={'Authorization':'Bearer '+token,
            'X-Suite-Organization':str(company_id),'X-Suite-Branch':str(branch_id)},json=command)
    if not response.is_success:raise HTTPException(response.status_code,'Agent planning failed')
    return response.json()


async def dispatch(db,app,instant=None,limit=5):
    """Only explicitly activated schedules. No suite approval or execution here."""
    from app.access.service import activate_run_context,release_run_context,background_scope
    from app.ai_operator.suite_models import SuiteRun
    from app.ai_operator import suite_conversations as chats
    from app.core.security import create_access_token
    instant=instant or now();processed=0
    # One occurrence is in flight per schedule. The deterministic request key
    # recovers a committed plan if a worker dies before recording its receipt.
    candidates=db.query(Job.id).filter(Job.job_type==KIND,Job.status.in_(['agent_active','agent_waiting','agent_preparing','agent_paused']),Job.run_at<=instant).order_by(Job.run_at,Job.id).limit(min(limit,20)).all()
    for (ident,) in candidates:
        row=db.query(Job).filter_by(id=ident,job_type=KIND).with_for_update(skip_locked=True).populate_existing().first()
        if not row or row.status not in ('agent_active','agent_waiting','agent_preparing','agent_paused'):
            db.rollback();continue
        if row.run_at is None or utc(row.run_at)>instant:
            db.rollback();continue
        actor=None;claimed_lease=None
        try:
            data=row.payload_json
            if instant>=datetime.fromisoformat(data['spec']['expires_at']):
                row.status='agent_expired';row.run_at=None;db.commit();continue
            if row.status=='agent_paused':
                db.rollback();continue
            if row.status=='agent_preparing' and datetime.fromisoformat(data['pending']['claimed_at'])>instant-timedelta(minutes=5):
                db.rollback();continue
            actor=db.query(User).filter_by(id=row.created_by,is_active=True).first()
            if not actor:raise HTTPException(403,'Schedule owner unavailable')
            activate_run_context(db,actor,SimpleNamespace(scope_key=f'company:{row.organization_id}'))
            with background_scope(db,actor,'ai','view',branch_id=data['branch_id']):
                grant(db,actor,row)
                actor._suite_session_id=data['security_context']['session_id']
                if row.status=='agent_waiting':
                    run=occurrence_run(db,actor,data['pending'],data['spec']['agent_id'])
                    row.payload_json={**row.payload_json,'pending':{**data['pending'],'run_id':run.id}}
                    if run.status not in ('answered','succeeded','failed','cancelled'):
                        row.run_at=instant+timedelta(minutes=1);db.commit();continue
                    finish_occurrence(row,{'id':run.id,'status':run.status},instant);db.commit();processed+=1;continue
                if row.status=='agent_active':
                    occurrence=utc(row.run_at).isoformat()
                    claimed=db.query(Job).filter_by(id=row.id,status='agent_active',run_at=row.run_at).update({'status':'agent_preparing','run_at':instant+timedelta(minutes=5)},synchronize_session=False)
                    if not claimed:db.rollback();continue
                    conversation=chats.create(db,actor,chats.ConversationInput(title=f"Scheduled: {data['snapshot']['name']}"[:160],workspace_id=data['snapshot']['workspace_id']),commit=False)
                    if data.get('event_source'):
                        from app.ai_operator.assistant_models import AssistantConversation
                        chat=db.get(AssistantConversation,conversation['id']);chat.references={**chat.references,'agent_event_schedule_id':row.id}
                    pending={'occurrence':occurrence,'conversation_id':conversation['id'],'lease':str(uuid4()),
                        'request_key':str(uuid5(NAMESPACE_URL,f'businesssuite:{row.organization_id}:{row.id}:{occurrence}')),'claimed_at':instant.isoformat()}
                    row.status='agent_preparing';row.run_at=instant+timedelta(minutes=5);row.payload_json={**data,'pending':pending};db.commit()
                else:
                    pending={**data['pending'],'claimed_at':instant.isoformat(),'lease':str(uuid4())}
                    claimed=db.query(Job).filter_by(id=row.id,status='agent_preparing',run_at=row.run_at).update({'run_at':instant+timedelta(minutes=5),'payload_json':{**data,'pending':pending}},synchronize_session=False)
                    if not claimed:db.rollback();continue
                    row.run_at=instant+timedelta(minutes=5);row.payload_json={**data,'pending':pending};db.commit()
                if data.get('event_source'):
                    from app.ai_operator.agent_events import recheck_delivery
                    await recheck_delivery(app,db,actor,row)
                claimed_lease=pending['lease']
                prepared=await prepare_agent(app,actor.id,data['security_context']['session_id'],row.organization_id,data['branch_id'],{
                        'request_key':pending['request_key'],'text':data['spec']['prompt'],'agent_id':data['spec']['agent_id'],
                        'provider':'preferred','timezone':data['spec']['timezone'],'workspace_id':data['snapshot']['workspace_id'],
                        'project_id':data['snapshot']['project_id'] or (data.get('event_source') or {}).get('project_id'),'conversation_id':pending['conversation_id']})
                db.expire_all();row=db.query(Job).filter_by(id=ident,job_type=KIND).with_for_update().one()
                if row.status!='agent_preparing' or (row.payload_json.get('pending') or {}).get('lease')!=claimed_lease:
                    db.rollback();continue  # Paused, cancelled or a newer recovery owns this occurrence.
                run=prepared;pending={**row.payload_json['pending'],'run_id':run['id']}
                row.payload_json={**row.payload_json,'pending':pending};row.last_error=None
                if run['status'] in ('answered','succeeded','failed','cancelled'):
                    finish_occurrence(row,run,instant)
                else:row.status='agent_waiting';row.run_at=instant+timedelta(minutes=1)
                from app.services.notifications import create_notification
                from app.schemas.notification import NotificationCreate
                workspace=data['snapshot']['workspace_id']
                href=f"/?bot_conversation={pending['conversation_id']}"+(f'&workspace={workspace}' if workspace else '')
                from app.models.notification import Notification
                if not db.query(Notification.id).filter_by(company_id=row.organization_id,user_id=actor.id,event_type='ai.agent_schedule',related_entity_type='suite_run',related_entity_id=run['id']).first():
                    create_notification(db,NotificationCreate(company_id=row.organization_id,user_id=actor.id,title='Scheduled agent result ready',message='Open the bot conversation to view the answer or review its proposed actions.',module='ai',event_type='ai.agent_schedule',related_entity_type='suite_run',related_entity_id=run['id'],action_url=href),commit=False)
                db.commit();processed+=1
        except Exception:
            db.rollback();row=db.query(Job).filter_by(id=ident,job_type=KIND).with_for_update().first()
            if row and row.status in ('agent_active','agent_waiting','agent_preparing') and (claimed_lease is None or (row.payload_json.get('pending') or {}).get('lease')==claimed_lease):
                row.status='agent_blocked';row.last_error='Owner session, scope, agent revision or planning no longer permits this schedule. Review its conversation and prepare a new schedule.';db.commit()
            else:db.rollback()
        finally:
            if actor:actor.__dict__.pop('_suite_session_id',None)
            release_run_context(db)
    return {'processed':processed}
