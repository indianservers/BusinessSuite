"""Owned private calendar actions through native services and Suite checkpoints."""
import json
import re
from datetime import date,datetime,timedelta,timezone
from typing import Literal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Depends,HTTPException,Request,Response,Query
from pydantic import Field,create_model,model_validator
from app.core.deps import get_db,get_current_user
from app.ai_operator.suite_tools import Strict
from app.ai_operator.service import digest
from app.apps.project_management import calendar_settings as native
from app.apps.project_management.models import PMSCalendarEvent


class Create(native.EventInput):
    visibility:Literal['private']='private'
    sync_policy_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class Edit(Create):
    event_id:int=Field(gt=0,strict=True)
    revision:int=Field(ge=1,strict=True)
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class Remove(Strict):
    event_id:int=Field(gt=0,strict=True)
    revision:int=Field(ge=1,strict=True)
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    sync_policy_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class Window(Strict):
    start:datetime
    end:datetime
    after_id:int=Field(default=0,ge=0,strict=True)
    @model_validator(mode='after')
    def valid(self):
        if self.start.utcoffset() is None or self.end.utcoffset() is None or not timedelta(0)<self.end-self.start<=timedelta(days=31):
            raise ValueError('Choose an aware date range of at most 31 days')
        return self


class One(Strict):
    event_id:int=Field(gt=0,strict=True)


class Slots(Strict):
    day:date
    minutes:int=Field(default=30,ge=15,le=240,strict=True)
    timezone_name:str=Field(default='UTC',min_length=1,max_length=80)


MODELS={'create':Create,'edit':Edit,'remove':Remove}
ACTIONS={'pms.'+action+'_calendar_event' for action in MODELS}


def no_store(response:Response):response.headers['Cache-Control']='private, no-store'
router=APIRouter(prefix='/suite/pms/calendar',tags=['Reviewed native calendar'],dependencies=[Depends(no_store)])


def policy(db,user):
    from app.apps.crm.models import CRMCalendarIntegration
    from app.apps.crm.calendar_sync_models import CalendarSyncState
    from app.ai_agents.security import company
    from app.core.config import settings
    rows=db.query(CRMCalendarIntegration).filter_by(user_id=user.id,organization_id=company(user),is_active=True,deleted_at=None).order_by(CRMCalendarIntegration.id).all()
    bindings=[];public=[]
    for row in rows:
        if row.provider not in {'google','outlook'} or not (row.access_token_encrypted or row.refresh_token_encrypted):continue
        state=db.get(CalendarSyncState,row.id)
        bindings.append({'id':row.id,'provider':row.provider,'account':state.account_key if state and state.account_key else digest([row.access_token_encrypted,row.refresh_token_encrypted]),'enabled':state.enabled if state else True})
        public.append(f'{row.provider.title()} calendar connection #{row.id}'+(' (sync paused)' if state and not state.enabled else ''))
    sealed={'connections':bindings,'worker_enabled':settings.CALENDAR_SYNC_WORKER_ENABLED and not settings.SERVERLESS}
    return {'sha256':digest(sealed),'connections':public,
        'effect':'Existing calendar sync may propagate changes to these connected accounts. External audience follows provider calendar sharing settings; a native receipt does not confirm provider delivery.' if public else 'Native private calendar only; no connected calendar sync account was found.'}


def owned(db,user,ident,workspace=None,lock=False):
    query=db.query(PMSCalendarEvent).filter_by(id=ident,owner_id=user.id,visibility='private')
    if lock:query=query.populate_existing().with_for_update()
    row=query.first()
    if not row:raise HTTPException(404,'Owned private calendar event not found')
    if row.workspace_id is not None and row.workspace_id!=workspace:raise HTTPException(403,'Use the event original workspace')
    return row


def state(row):return native.event_output(row,type('Owner',(),{'id':row.owner_id})())


def calendar_zone(db,user):
    pref=db.get(native.PMSPlannerPreference,user.id)
    return ZoneInfo(native.Preferences.model_validate(pref.payload).timezone if pref else native.Preferences().timezone)


def calendar_url(row,zone):
    day=native.aware(row.start_at).astimezone(zone).date().isoformat()
    return '/pms/calendar?'+urlencode({'date':day,'view':'Week','q':row.title})


def read(db,user,ident,workspace=None):
    row=owned(db,user,ident,workspace)
    result=native.event_output(row,user);result.pop('owner_id',None)
    return {**result,'source_sha256':digest(state(row)),'sync_policy_sha256':policy(db,user)['sha256'],'calendar_url':calendar_url(row,calendar_zone(db,user))}


@router.get('/policy')
def read_policy(db=Depends(get_db),user=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,None,'PMS')
    return policy(db,user)


@router.get('/slots')
def slots(day:date,minutes:int=Query(30,ge=15,le=240),timezone_name:str=Query('UTC',max_length=80),db=Depends(get_db),user=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,None,'PMS')
    values=native.free_slots(day=day,minutes=minutes,timezone_name=timezone_name,db=db,user=user)
    return {'id':user.id,'name':'Native calendar slot suggestions','day':str(day),'timezone':timezone_name,'minutes':minutes,'slots':values,
        'scope':'caller visible native calendar and configured working hours',
        'limitations':'Not a reservation, attendee availability, HR leave check, or a complete external-calendar free/busy result.'}


@router.get('/event')
def event(event_id:int,workspace_id:int|None=None,db=Depends(get_db),user=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,workspace_id,'PMS')
    return read(db,user,event_id,workspace_id)


@router.get('/events')
def events(start:datetime,end:datetime,after_id:int=Query(0,ge=0),workspace_id:int|None=None,db=Depends(get_db),user=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,workspace_id,'PMS')
    try:window=Window(start=start,end=end,after_id=after_id)
    except ValueError:raise HTTPException(422,'Choose an aware range of at most 31 days') from None
    query=db.query(PMSCalendarEvent).filter_by(owner_id=user.id,visibility='private').filter(
        PMSCalendarEvent.id>window.after_id,PMSCalendarEvent.start_at<window.end,PMSCalendarEvent.end_at>window.start)
    from sqlalchemy import or_
    query=query.filter(or_(PMSCalendarEvent.workspace_id.is_(None),PMSCalendarEvent.workspace_id==workspace_id))
    rows=query.order_by(PMSCalendarEvent.id).limit(26).all();more=len(rows)>25
    sync=policy(db,user);items=[];zone=calendar_zone(db,user)
    for row in rows[:25]:
        value=native.event_output(row,user);value.pop('owner_id',None)
        items.append({**value,'source_sha256':digest(state(row)),'sync_policy_sha256':sync['sha256'],'calendar_url':calendar_url(row,zone)})
    return {'items':items,'has_more':more,'next_after_id':rows[24].id if more else None,'scope':'owned_private_native_events'}


def checkpoint(run,step):
    value=(run.result or {}).get('calendar_checkpoint') or {}
    return value if value.get('step')==run.active_step and value.get('tool')==step.tool and value.get('payload_hash')==digest(step.payload) else None


def preflight(db,user,run,step,lock=False):
    action=step.tool.split('.')[1].removesuffix('_calendar_event');value=MODELS[action].model_validate(step.payload)
    if action=='edit' and not set(native.EventInput.model_fields).issubset(step.payload):
        raise HTTPException(422,'Calendar edits must retain the complete native definition, including unchanged fields')
    if checkpoint(run,step):return value
    if policy(db,user)['sha256']!=value.sync_policy_sha256:raise HTTPException(409,'Calendar connections or sync settings changed; review a fresh action')
    if action!='create':
        row=owned(db,user,value.event_id,run.workspace_id,lock)
        if row.revision!=value.revision or digest(state(row))!=value.source_sha256:raise HTTPException(409,'Calendar event changed; read it again before review')
    if action!='remove':
        native.validate_scope(db,user,value)
        if value.workspace_id is not None and value.workspace_id!=run.workspace_id:raise HTTPException(403,'Calendar event must retain the selected workspace')
        if action=='edit' and value.workspace_id!=row.workspace_id:raise HTTPException(422,'Moving an event between workspaces requires a separate native calendar workflow')
        if value.task_id:
            from app.apps.project_management.models import PMSTask
            from app.apps.project_management.access import get_project_for_action
            task=db.get(PMSTask,value.task_id);project=get_project_for_action(db,task.project_id,user,'browse')
            if project.workspace_id!=run.workspace_id:raise HTTPException(403,'Linked task is outside the selected workspace')
    return value


def preview(db,user,run,step):
    value=preflight(db,user,run,step);action=step.tool.split('.')[1].removesuffix('_calendar_event')
    before=read(db,user,value.event_id,run.workspace_id) if action!='create' else {}
    after={key:getattr(value,key) for key in native.EventInput.model_fields} if action!='remove' else {'event':'Removed from the native calendar'}
    changes=[]
    for key,new in after.items():
        if isinstance(new,datetime):new=new.astimezone(timezone.utc).isoformat()
        old=before.get('title') if key=='event' else before.get(key)
        if old!=new:changes.append({'field':key,'before':old,'after':new})
    if action=='edit' and not changes:raise HTTPException(422,'Choose an event value to change')
    sync=policy(db,user)
    changes.extend([{'field':'audience','before':None,'after':'Owner private native calendar; external calendar sharing is managed by each provider account'},
        {'field':'calendar_sync','before':None,'after':sync['effect']+' '+', '.join(sync['connections'])}])
    return {'record_id':getattr(value,'event_id','New'),'record_name':getattr(value,'title',before.get('title')),'changes':changes}


def confirmed(db,user,run,step):
    saved=checkpoint(run,step)
    if not saved:return None
    receipt=saved['receipt'];row=db.get(PMSCalendarEvent,receipt['id'])
    if step.tool=='pms.remove_calendar_event':
        if row:raise HTTPException(409,'Removed event ID is present; reconcile the recorded receipt')
    else:
        row=owned(db,user,receipt['id'],run.workspace_id)
        if digest(state(row))!=saved['state_hash']:raise HTTPException(409,'Committed event changed; reconcile its recorded receipt')
    return receipt


def register(action,Model):
    Approved=create_model(action.title()+'ApprovedCalendar',__base__=Model,suite_run_id=(int,Field(gt=0)),suite_step=(int,Field(ge=1,le=12)))
    @router.post('/'+action+'-approved')
    def execute(data:Approved,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
        from app.ai_operator.agent_connectors import reviewed_run
        from app.ai_agents.services.audit import AiAuditService
        run,step=reviewed_run(db,user,request,data,Model,action+'_calendar_event')
        prior=confirmed(db,user,run,step)
        if prior:return prior
        value=preflight(db,user,run,step,lock=True)
        fields={key:getattr(value,key) for key in native.EventInput.model_fields} if action!='remove' else {}
        if action=='create':result=native.create_event_operation(native.EventInput(**fields),db,user,commit=False)
        elif action=='edit':result=native.edit_event_operation(value.event_id,native.EventSave(**fields,revision=value.revision),db,user,commit=False)
        else:
            result=native.event_output(owned(db,user,value.event_id,run.workspace_id,True),user)
            native.delete_event_operation(value.event_id,value.revision,db,user,commit=False)
        receipt={'id':result['id'],'title':result['title'],'event_revision':result['revision'],'operation':action,'url':'/pms/calendar'}
        row=db.get(PMSCalendarEvent,result['id']) if action!='remove' else None
        if row:receipt['calendar_url']=calendar_url(row,calendar_zone(db,user))
        run.result={**(run.result or {}),'calendar_checkpoint':{'step':data.suite_step,'tool':step.tool,'payload_hash':digest(step.payload),'state_hash':digest(state(row)) if row else None,'receipt':receipt}}
        AiAuditService(db).log(user=user,agent_id=None,module='PMS',action='suite.calendar.'+action,input_json={'suite_run_id':run.id,'step':data.suite_step},output_json=receipt,status='success')
        db.commit();return receipt


for _action,_model in MODELS.items():register(_action,_model)


def validate_plan(plan):
    targets=[s.payload.get('event_id') for s in plan.steps if s.tool in ACTIONS and s.tool!='pms.create_calendar_event']
    if any(type(value) is not int or value<=0 for value in targets):raise HTTPException(422,'Read an existing event ID and revision before editing or removal')
    if len(targets)!=len(set(targets)):raise HTTPException(422,'Read the confirmed event again before another mutation to the same target')


def resume_stored(db,user,run,plan_hash):
    from app.ai_operator.suite import Plan,check_tool,finish_step
    from app.ai_operator.saved_agents import enforce
    from app.ai_agents.models import AiActionApproval
    from app.ai_agents.security import verify
    if run.status!='needs_reconciliation' or run.active_step!=len(run.receipts)+1:return False
    step=Plan.model_validate(run.plan).steps[run.active_step-1]
    if step.tool not in ACTIONS:return False
    approval=db.get(AiActionApproval,run.approval_id)
    if run.plan_hash!=plan_hash or digest(run.plan)!=plan_hash or not approval or approval.status!='approved' or approval.approved_by!=user.id:raise HTTPException(409,'Review the unchanged approved calendar plan')
    verify(db,user,approval.security_context,payload=approval.proposed_action_json,confirmation=True)
    enforce(db,user,run,[step]);check_tool(db,user,run.workspace_id,step,True)
    receipt=confirmed(db,user,run,step)
    if not receipt:raise HTTPException(409,'Calendar outcome requires reconciliation')
    finish_step(db,run,run.active_step,step.tool,receipt);run.error_code=None
    approval.execution_status=run.status;approval.execution_error=None
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module='PMS',action='suite.calendar.resumed',input_json={'suite_run_id':run.id},output_json={'event_id':receipt['id'],'policy':'committed-receipt-only'},status='success')
    db.commit();return True


def prepare(db,user,data,parent):
    from app.ai_operator.suite import Plan,Step
    text=re.sub(r'(?i)^\s*PMS\s*:\s*','',data.text).strip()
    if data.module not in (None,'PMS') and not re.match(r'(?i)^\s*PMS\s*:',data.text):return None,None
    natural=re.fullmatch(r'(?is)(?:create|schedule|add)\s+(?:a\s+|private\s+)?(meeting|event|focus block)\s+(?:called\s+)?(.+?)\s+(today|tomorrow|\d{4}-\d{2}-\d{2})\s+at\s+(\d{1,2})(?::([0-9]{2}))?\s*(am|pm)?\s+for\s+([1-9][0-9]{0,4})\s*(minutes?|mins?|hours?)[.! ]*',text)
    if natural:
        pending={'_action':'create','title':natural[2].strip(),'timezone':data.timezone,'visibility':'private','workspace_id':data.workspace_id,'kind':'focus' if natural[1].lower()=='focus block' else 'meeting'}
        try:
            zone=ZoneInfo(data.timezone);today=datetime.now(zone).date()
            day=today+timedelta(days=natural[3].lower()=='tomorrow') if natural[3].lower() in {'today','tomorrow'} else date.fromisoformat(natural[3])
            hour=int(natural[4]);minute=int(natural[5] or 0)
            if natural[6]:
                if not 1<=hour<=12:raise ValueError()
                hour=hour%12+(12 if natural[6].lower()=='pm' else 0)
            local=datetime(day.year,day.month,day.day,hour,minute)
            candidates={value.utcoffset():value for fold in (0,1) for value in [local.replace(tzinfo=zone,fold=fold)]
                if value.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)==local}
            if len(candidates)!=1:raise ValueError()
            start=next(iter(candidates.values()));minutes=int(natural[7])*(60 if natural[8].lower().startswith('hour') else 1)
            end=start.astimezone(timezone.utc)+timedelta(minutes=minutes)
            text='Create '+natural[1]+' called '+natural[2].strip()+': start='+start.isoformat()+'; end='+end.isoformat()
        except (ValueError,OverflowError,KeyError):
            return Plan(summary='Clarify the calendar time.',question='Check the local date/time and duration. Ambiguous or nonexistent clock times require explicit start= and end= ISO datetimes with offsets.',steps=[]),pending
    match=re.fullmatch(r'(?is)(create|schedule|add|edit|update|remove|delete)\s+(?:(a|that|this|private)\s+)?(?:calendar\s+)?(?:meeting|event|focus block)(?:\s+(?:called\s+)?([^:]+))?(?::\s*(.*))?',text)
    prior=(parent.result or {}).get('calendar_draft') if parent and parent.status in {'needs_clarification','awaiting_approval'} else None
    if parent and parent.status=='awaiting_approval' and len((parent.plan or {}).get('steps',[]))==1:
        step=parent.plan['steps'][0]
        if step['tool'] in ACTIONS:prior={**step['payload'],'_action':step['tool'].split('.')[1].removesuffix('_calendar_event')}
    if not match and not prior:return None,None
    if data.module not in (None,'PMS') and not re.match(r'(?i)^\s*PMS\s*:',data.text):return None,None
    data.module='PMS'
    if re.fullmatch(r'(?i)(?:cancel|stop|discard)[.! ]*',text):return Plan(summary='Calendar draft cancelled.',steps=[]),None
    action={'schedule':'create','add':'create','update':'edit','delete':'remove'}.get(match[1].lower(),match[1].lower()) if match else prior['_action']
    draft={'_action':action,'timezone':data.timezone,'visibility':'private','workspace_id':data.workspace_id} if match else json.loads(json.dumps(prior))
    selector=match[3].strip() if match and match[3] else None
    if match and action=='create' and selector:draft['title']=selector
    if match and action=='create' and re.search(r'(?i)\bfocus block\b',text):draft['kind']='focus'
    if match and action!='create' and match[2] and match[2].lower() in {'that','this'} and parent and parent.status=='succeeded':
        receipts=[r for r in parent.receipts or [] if r.get('tool') in ACTIONS and r.get('status')=='succeeded']
        if receipts:selector=str(receipts[-1]['record_id'])
    def ask(message):return Plan(summary='Clarify the native private calendar action.',question=message,steps=[]),draft
    if selector and action!='create':draft['_selector']=selector
    values=match[4] if match else text
    if prior and not match:
        renamed=re.fullmatch(r'(?is)rename\s+(?:it|the meeting|the event)\s+to\s+(.+)',text)
        duration=re.fullmatch(r'(?i)make\s+it\s+([1-9][0-9]{0,4})\s+minutes?[.! ]*',text)
        moved=re.fullmatch(r'(?is)(?:move|reschedule)\s+(?:it|the meeting|the event)\s+to\s+(.+)',text)
        if renamed:values='title='+renamed[1].strip()
        elif duration:
            try:
                start=datetime.fromisoformat(draft['start_at'].replace('Z','+00:00'))
                values='end='+(start+timedelta(minutes=int(duration[1]))).isoformat()
            except (KeyError,ValueError,OverflowError):return ask('Provide start= with its timezone offset before changing the duration.')
        elif moved:
            try:
                start=datetime.fromisoformat(moved[1].strip().replace('Z','+00:00'))
                delta=datetime.fromisoformat(draft['end_at'].replace('Z','+00:00'))-datetime.fromisoformat(draft['start_at'].replace('Z','+00:00'))
                values='start='+start.isoformat()+'; end='+(start+delta).isoformat()
            except (KeyError,ValueError,OverflowError):return ask('Use an explicit ISO datetime with an offset, such as Move it to 2026-11-16T11:00+05:30.')
    changes={}
    for part in (values or '').split(';'):
        if not part.strip():continue
        key,sep,value=part.strip().partition('=');value=value.strip()
        if not sep or key not in {'event','title','description','start','end','timezone','kind','meeting_url','task'}:
            return ask('Use event=ID; title=...; start=2026-11-16T10:00+05:30; end=2026-11-16T10:30+05:30; timezone=Asia/Kolkata; kind=meeting or focus. No invitations are sent.')
        key={'start':'start_at','end':'end_at','task':'task_id'}.get(key,key)
        if key=='event':
            if not re.fullmatch(r'[1-9][0-9]*',value):return ask('Reply event=123 using the existing native event ID.')
            draft['_selector']=value;draft.pop('event_id',None)
        elif key=='task_id':
            if value and not re.fullmatch(r'[1-9][0-9]*',value):return ask('Use task=ID or task= to unlink the task.')
            changes[key]=int(value) if value else None
        else:changes[key]=value
    if action!='create' and not draft.get('event_id'):
        target=draft.get('_selector','').lstrip('#')
        if not re.fullmatch(r'[1-9][0-9]*',target):return ask('Which owned private event should change? Reply event=ID. Early field changes will be retained.') if not changes else _pending(draft,changes,ask)
        try:source=read(db,user,int(target),data.workspace_id)
        except HTTPException:return ask('Choose an owned private event in the original conversation workspace.')
        pending=draft.pop('_changes',{})
        draft.update({key:source[key] for key in native.EventInput.model_fields})
        draft.update(event_id=source['id'],revision=source['revision'],source_sha256=source['source_sha256'],sync_policy_sha256=source['sync_policy_sha256'])
        changes={**pending,**changes}
    if action=='remove' and changes:return ask('Removal has no editable fields. Start an edit request to change the event instead.')
    draft.update(changes)
    if action=='create':draft['sync_policy_sha256']=policy(db,user)['sha256']
    if action!='remove' and any(not draft.get(key) for key in ('title','start_at','end_at')):
        return ask('Provide a title, start and end with explicit timezone offsets. Example: start=2026-11-16T10:00+05:30; end=2026-11-16T10:30+05:30.')
    keys=set(MODELS[action].model_fields)
    try:value=MODELS[action].model_validate({key:value for key,value in draft.items() if key in keys})
    except ValueError:return ask('Check the title, explicit time offsets, timezone, positive duration (up to seven days), and HTTPS meeting link.')
    return Plan(summary='Review the native private calendar '+action+'. Existing connected-calendar sync is shown separately; no invitations or provider delivery are confirmed.',steps=[Step(tool='pms.'+action+'_calendar_event',payload=value.model_dump(mode='json'))]),draft


def _pending(draft,changes,ask):
    draft['_changes']={**draft.get('_changes',{}),**changes}
    return ask('Which owned private event should change? Reply event=ID; the proposed fields are retained.')
