"""Reviewed personal manual time entries using canonical PMS operations."""
from datetime import date
import re
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import Field,create_model
from app.core.deps import get_db,get_current_user
from app.ai_operator.suite_tools import Strict
from app.ai_operator.service import digest
from app.apps.project_management.models import PMSTimeLog,PMSTimesheet
from app.apps.project_management.schemas import PMSTimeLogCreate,PMSTimeLogUpdate,PMSTimeLogResponse


class Create(Strict):
    log_date:date
    duration_minutes:int=Field(gt=0,le=1440,strict=True)
    description:str=Field(default='',max_length=4000)
    is_billable:bool=Field(default=False,strict=True)
    task_id:int|None=Field(default=None,gt=0,strict=True)


class Edit(Create):
    log_id:int=Field(gt=0,strict=True)
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class Remove(Strict):
    log_id:int=Field(gt=0,strict=True)
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')


class Read(Strict):
    log_id:int=Field(gt=0,strict=True)


MODELS={'create':Create,'edit':Edit,'remove':Remove}
ACTIONS={f'pms.{action}_time_log' for action in MODELS}
router=APIRouter(prefix='/suite/pms/time',tags=['Reviewed personal time entries'])


def project(db,user,pid,workspace=None,write=False):
    from app.apps.project_management.access import get_project_for_action
    row=get_project_for_action(db,pid,user,'log_time' if write else 'browse')
    if workspace is not None and row.workspace_id!=workspace:raise HTTPException(403,'Time project must match the selected workspace')
    return row


def owned(db,user,pid,ident,lock=False):
    query=db.query(PMSTimeLog).filter_by(id=ident,project_id=pid,user_id=user.id)
    if lock:query=query.with_for_update().populate_existing()
    row=query.first()
    if not row:raise HTTPException(404,'Owned time entry not found in this project')
    return row


def state(db,row,lock=False):
    sheet=None
    if row.timesheet_id:
        query=db.query(PMSTimesheet).filter_by(id=row.timesheet_id)
        if lock:query=query.with_for_update().populate_existing()
        sheet=query.first()
    return {**PMSTimeLogResponse.model_validate(row).model_dump(mode='json'),
        'timesheet_status':sheet.status if sheet else None}


@router.get('/{project_id}')
def read(project_id:int,log_id:int,response:Response,db=Depends(get_db),user=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,None,'PMS');project(db,user,project_id)
    value=state(db,owned(db,user,project_id,log_id));response.headers['Cache-Control']='private, no-store'
    return {**value,'source_sha256':digest(value),'name':f"Time entry {log_id}"}


def checkpoint(run,step):
    value=(run.result or {}).get('time_checkpoint') or {}
    return value if value.get('step')==run.active_step and value.get('tool')==step.tool and value.get('payload_hash')==digest(step.payload) and value.get('project_id')==step.record_id else None


def preflight(db,user,run,step,lock=False):
    if type(step.record_id) is not int:raise HTTPException(422,'Select an existing project for time logging')
    project(db,user,step.record_id,write=True)
    from app.apps.project_management.access import get_project_for_action,get_task_project_for_action
    anchor=get_project_for_action(db,step.record_id,user,'log_time')
    if anchor.workspace_id!=run.workspace_id:raise HTTPException(403,'Time project must match the selected workspace')
    action=step.tool.split('.')[1].removesuffix('_time_log');value=MODELS[action].model_validate(step.payload)
    if checkpoint(run,step):return value
    if action!='create':
        row=owned(db,user,step.record_id,value.log_id,lock);before=state(db,row,lock)
        if digest(before)!=value.source_sha256:raise HTTPException(409,'Time entry changed; read it again before review')
        if before['timesheet_status'] not in {None,'draft','rejected'} or row.approval_status!='Pending':
            raise HTTPException(409,'Use the native approval workflow for submitted or reviewed time')
        if row.start_time is not None or row.end_time is not None:raise HTTPException(422,'Use the native time editor for clocked entries')
    if action!='remove' and value.task_id:
        task,_=get_task_project_for_action(db,value.task_id,user,'log_time')
        if task.project_id!=step.record_id:raise HTTPException(422,'Task must belong to the selected time project')
    if action=='edit' and not set(Create.model_fields).issubset(step.payload):
        raise HTTPException(422,'Time edits must include the full manual entry definition')
    return value


def preview(db,user,run,step):
    value=preflight(db,user,run,step);action=step.tool.split('.')[1].removesuffix('_time_log')
    before=state(db,owned(db,user,step.record_id,value.log_id)) if action!='create' else {}
    after={key:getattr(value,key) for key in Create.model_fields} if action!='remove' else {'entry':'Removed'}
    after={key:str(new) if isinstance(new,date) else new for key,new in after.items()}
    changes=[{'field':key,'before':before.get(key),'after':new} for key,new in after.items() if before.get(key)!=new]
    changes.extend([{'field':'owner','before':None,'after':'Current user only'},
        {'field':'approval_status','before':before.get('approval_status'),'after':'Pending; this does not approve a timesheet or invoice the customer'}])
    return {'record_id':getattr(value,'log_id','New'),'record_name':'Personal manual time entry','changes':changes}


def confirmed(db,user,run,step):
    saved=checkpoint(run,step)
    if not saved:return None
    receipt=saved['receipt']
    if step.tool=='pms.remove_time_log':
        if db.get(PMSTimeLog,receipt['id']):raise HTTPException(409,'Removed time ID exists; reconcile the receipt')
    elif digest(state(db,owned(db,user,step.record_id,receipt['id'])))!=saved['state_hash']:
        raise HTTPException(409,'Committed time entry changed; reconcile its receipt')
    return receipt


def register(action,Model):
    Approved=create_model(action.title()+'ApprovedTime',__base__=Model,suite_run_id=(int,Field(gt=0)),suite_step=(int,Field(ge=1,le=12)))
    @router.post('/{project_id}/'+action+'-approved')
    def execute(project_id:int,data:Approved,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
        from app.ai_operator.agent_connectors import reviewed_run
        from app.apps.project_management.api.router import create_time_log_operation,update_time_log_operation,delete_time_log_operation
        from app.ai_agents.services.audit import AiAuditService
        run,step=reviewed_run(db,user,request,data,Model,action+'_time_log')
        if step.record_id!=project_id:raise HTTPException(403,'Time project differs from the approved target')
        prior=confirmed(db,user,run,step)
        if prior:return prior
        value=preflight(db,user,run,step,True)
        fields={key:getattr(value,key) for key in Create.model_fields} if action!='remove' else {}
        if action=='create':row=create_time_log_operation(PMSTimeLogCreate(project_id=project_id,**fields),db,user,commit=False)
        elif action=='edit':row=update_time_log_operation(value.log_id,PMSTimeLogUpdate(**fields),db,user,commit=False)
        else:
            row=owned(db,user,project_id,value.log_id,True)
            delete_time_log_operation(value.log_id,db,user,commit=False)
        receipt={'id':row.id,'title':f'Time entry {row.id}','operation':action,'url':'/pms/time-tracking'}
        run.result={**(run.result or {}),'time_checkpoint':{'step':data.suite_step,'tool':step.tool,'project_id':project_id,
            'payload_hash':digest(step.payload),'state_hash':digest(state(db,row)) if action!='remove' else None,'receipt':receipt}}
        AiAuditService(db).log(user=user,agent_id=None,module='PMS',action='suite.time.'+action,input_json={'suite_run_id':run.id,'step':data.suite_step},output_json=receipt,status='success')
        db.commit();return receipt


for _action,_model in MODELS.items():register(_action,_model)


def validate_plan(plan):
    targets=[(step.record_id,step.payload.get("log_id")) for step in plan.steps if step.tool in ACTIONS and step.tool!="pms.create_time_log"]
    if any(type(ident) is not int or ident<=0 for _,ident in targets):raise HTTPException(422,"Read an existing time entry before mutation")
    if len(targets)!=len(set(targets)):raise HTTPException(422,"Read the confirmed time entry before another change to the same target")


def resume_stored(db,user,run,plan_hash):
    from app.ai_operator.suite import Plan,check_tool,finish_step
    from app.ai_operator.saved_agents import enforce
    from app.ai_agents.models import AiActionApproval
    from app.ai_agents.security import verify
    if run.status!='needs_reconciliation' or run.active_step!=len(run.receipts)+1:return False
    step=Plan.model_validate(run.plan).steps[run.active_step-1]
    if step.tool not in ACTIONS:return False
    approval=db.get(AiActionApproval,run.approval_id)
    if run.plan_hash!=plan_hash or digest(run.plan)!=plan_hash or not approval or approval.status!='approved' or approval.approved_by!=user.id:raise HTTPException(409,'Review the unchanged approved time plan')
    verify(db,user,approval.security_context,payload=approval.proposed_action_json,confirmation=True)
    enforce(db,user,run,[step]);check_tool(db,user,run.workspace_id,step,True)
    receipt=confirmed(db,user,run,step)
    if not receipt:raise HTTPException(409,'Time outcome requires reconciliation')
    finish_step(db,run,run.active_step,step.tool,receipt);run.error_code=None
    approval.execution_status=run.status;approval.execution_error=None
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module='PMS',action='suite.time.resumed',input_json={'suite_run_id':run.id},output_json={'log_id':receipt['id'],'policy':'committed-receipt-only'},status='success')
    db.commit();return True


def prepare_create(data,parent):
    from app.ai_operator.suite import Plan,Step
    text=re.sub(r'(?i)^\s*PMS\s*:\s*','',data.text).strip()
    if data.module not in (None,'PMS') and not re.match(r'(?i)^\s*PMS\s*:',data.text):return None,None
    match=re.fullmatch(r'(?is)(?:log|record|add)\s+(?:([0-9]{1,6})\s+(minutes?|mins?|hours?)(?:\s+of work)?(?:\s+(today|yesterday|\d{4}-\d{2}-\d{2}))?(?:\s+(?:on|for)\s+task\s+#?([1-9][0-9]{0,17}))?|time)(?:\s*:\s*(.*))?',text)
    prior=(parent.result or {}).get('time_draft') if parent else None
    if not prior and parent and parent.status=='awaiting_approval':
        steps=(parent.plan or {}).get('steps',[])
        if len(steps)==1 and steps[0]['tool']=='pms.create_time_log':
            prior={**steps[0]['payload'],'project_id':steps[0]['record_id']}
    correction=re.fullmatch(r'(?i)make it\s+([0-9]{1,6})\s+(minutes?|mins?|hours?)[.! ]*',text) if prior else None
    follow=bool(prior and (correction or re.match(r'(?i)^(?:project|date|minutes|description|billable|task)=',text)))
    if not match and not follow:return None,None
    if follow and (parent.status not in {'needs_clarification','awaiting_approval'} or parent.receipts):
        raise HTTPException(409,'The time entry was already processed; read it before preparing a separate edit')
    if parent and parent.status=='awaiting_approval' and not prior:raise HTTPException(409,'Finish or cancel the pending action before logging time')
    data.module='PMS'
    try:today=datetime.now(ZoneInfo(data.timezone)).date()
    except (ValueError,ZoneInfoNotFoundError):raise HTTPException(422,'Choose a valid time zone') from None
    draft=dict(prior) if follow else {'project_id':data.project_id,'log_date':str(today),'description':'','is_billable':False,'task_id':data.task_ids[0] if len(data.task_ids)==1 else None}
    if parent and parent.status=='awaiting_approval' and follow:
        steps=(parent.plan or {}).get('steps',[])
        if len(steps)!=1 or steps[0]['tool']!='pms.create_time_log':raise HTTPException(409,'Keep the pending time action target')
        draft={**draft,**steps[0]['payload']}
    if match and match[1]:
        draft['duration_minutes']=int(match[1])*(60 if match[2].lower().startswith('hour') else 1)
        if match[3]:draft['log_date']=str(today-timedelta(days=1)) if match[3].lower()=='yesterday' else str(today) if match[3].lower()=='today' else match[3]
        if match[4]:draft['task_id']=int(match[4])
    if correction:draft['duration_minutes']=int(correction[1])*(60 if correction[2].lower().startswith('hour') else 1)
    def ask(question):return Plan(summary='Clarify a personal manual time entry.',question=question,steps=[]),draft
    for part in ((match[5] if match else text if follow and not correction else '') or '').split(';'):
        if not part.strip():continue
        key,sep,value=part.strip().partition('=');value=value.strip()
        if not sep or key not in {'project','date','minutes','description','billable','task'}:return ask('Use project=ID; date=YYYY-MM-DD; minutes=45; description=work; billable=true/false; task=ID or none.')
        field={'project':'project_id','date':'log_date','minutes':'duration_minutes','billable':'is_billable','task':'task_id'}.get(key,key)
        if key in {'project','minutes','task'}:
            if key=='task' and value.lower()=='none':draft[field]=None;continue
            if not re.fullmatch(r'[0-9]{1,18}',value):return ask('Use numeric project/task IDs and minutes.')
            draft[field]=int(value)
        elif key=='billable':
            if value.lower() not in {'true','false'}:return ask('Choose billable=true or billable=false.')
            draft[field]=value.lower()=='true'
        else:draft[field]=value
    if not draft.get('project_id'):return ask('Which project should receive your time entry? Reply project=123.')
    if not draft.get('duration_minutes'):return ask('How many minutes did you work? Reply minutes=45.')
    try:value=Create.model_validate({key:val for key,val in draft.items() if key!='project_id'})
    except ValueError:return ask('Choose a valid date, 1..1440 minutes, and a valid task or none.')
    data.project_id=draft['project_id']
    return Plan(summary='Review your manual time entry. It remains Pending and does not approve a timesheet or post an invoice.',steps=[Step(tool='pms.create_time_log',record_id=draft['project_id'],payload=value.model_dump(mode='json'))]),draft


def prepare(db,user,data,parent):
    from app.ai_operator.suite import Plan,Step
    text=re.sub(r'(?i)^\s*PMS\s*:\s*','',data.text).strip()
    if data.module not in (None,'PMS') and not re.match(r'(?i)^\s*PMS\s*:',data.text):return None,None
    match=re.fullmatch(r'(?is)(edit|update|change|remove|delete)\s+(?:(that|this)\s+)?time\s+entry(?:\s+#?([1-9][0-9]{0,17}))?(?:\s+to\s+([0-9]{1,6})\s+(minutes?|mins?|hours?))?(?:\s*:\s*(.*))?[.! ]*',text)
    prior=(parent.result or {}).get('time_draft') if parent else None
    if not prior and parent and parent.status=='awaiting_approval':
        steps=(parent.plan or {}).get('steps',[])
        if len(steps)==1 and steps[0]['tool'] in {'pms.edit_time_log','pms.remove_time_log'}:
            step=steps[0];payload=step['payload']
            prior={'_action':'edit' if step['tool']=='pms.edit_time_log' else 'remove',
                '_log_id':payload['log_id'],'_source_sha256':payload['source_sha256'],'project_id':step['record_id'],
                '_changes':{key:payload[key] for key in Create.model_fields} if step['tool']=='pms.edit_time_log' else {}}
    existing=bool(prior and prior.get('_action') in {'edit','remove'})
    correction=re.fullmatch(r'(?i)make it\s+([0-9]{1,6})\s+(minutes?|mins?|hours?)[.! ]*',text) if existing else None
    follow=bool(existing and (correction or re.match(r'(?i)^(?:log|date|minutes|description|billable|task)=',text)))
    if not match and not follow:return prepare_create(data,parent)
    if follow and (parent.status not in {'needs_clarification','awaiting_approval'} or parent.receipts):
        raise HTTPException(409,'Read the processed entry before preparing a fresh time correction')
    if parent and parent.status=='awaiting_approval' and not follow:
        raise HTTPException(409,'Finish or cancel the pending action before changing a time entry')
    draft=dict(prior) if follow else {'_action':'remove' if match[1].lower() in {'remove','delete'} else 'edit','_changes':{}}
    draft['_changes']=dict(draft.get('_changes',{}));data.module='PMS'
    if follow and parent.status=='awaiting_approval' and draft['_action']=='edit':
        steps=(parent.plan or {}).get('steps',[])
        if len(steps)==1 and steps[0]['tool']=='pms.edit_time_log':
            draft['_changes']={key:steps[0]['payload'][key] for key in Create.model_fields}
    def ask(question):return Plan(summary='Clarify the existing personal time entry.',question=question,steps=[]),draft
    if match:
        if match[3]:draft['_log_id']=int(match[3])
        elif match[2] and parent:
            targets=[receipt.get('record_id') for receipt in parent.receipts or [] if receipt.get('tool') in {'pms.create_time_log','pms.edit_time_log'} and receipt.get('status')=='succeeded']
            if len(targets)==1:draft['_log_id']=targets[0]
        if match[4]:draft['_changes']['duration_minutes']=int(match[4])*(60 if match[5].lower().startswith('hour') else 1)
    if correction:draft['_changes']['duration_minutes']=int(correction[1])*(60 if correction[2].lower().startswith('hour') else 1)
    for part in ((match[6] if match else text if not correction else '') or '').split(';'):
        if not part.strip():continue
        key,sep,value=part.strip().partition('=');key=key.lower();value=value.strip()
        if not sep or key not in {'log','date','minutes','description','billable','task'}:return ask('Use log=ID; date=YYYY-MM-DD; minutes=60; description=work; billable=true/false; task=ID or none.')
        field={'date':'log_date','minutes':'duration_minutes','billable':'is_billable','task':'task_id'}.get(key,key)
        if key=='log':
            if not re.fullmatch(r'[1-9][0-9]{0,17}',value):return ask('Choose a valid time entry ID.')
            if draft.get('_log_id') and int(value)!=draft['_log_id']:raise HTTPException(409,'Start a fresh request to select another time entry')
            draft['_log_id']=int(value)
        elif key in {'minutes','task'}:
            if key=='task' and value.lower()=='none':draft['_changes'][field]=None;continue
            if not re.fullmatch(r'[0-9]{1,18}',value):return ask('Use numeric minutes and task IDs.')
            draft['_changes'][field]=int(value)
        elif key=='billable':
            if value.lower() not in {'true','false'}:return ask('Choose billable=true or billable=false.')
            draft['_changes'][field]=value.lower()=='true'
        else:draft['_changes'][field]=value
    if not draft.get('_log_id'):return ask('Which time entry should change? Reply log=123. No entry is selected from an ambiguous conversation.')
    if draft['_action']=='remove' and draft['_changes']:return ask('Removal accepts only the time entry ID. Start a separate edit to change its fields.')
    row=db.query(PMSTimeLog).filter_by(id=draft['_log_id'],user_id=user.id).first()
    if not row:raise HTTPException(404,'Owned time entry not found')
    anchor=project(db,user,row.project_id,write=True)
    if anchor.workspace_id!=data.workspace_id:raise HTTPException(403,'Time entry must match the selected workspace')
    if data.project_id is not None and data.project_id!=row.project_id:raise HTTPException(409,'Select the time entry project before continuing')
    before=state(db,row);source=digest(before)
    expected=draft.get('_source_sha256')
    if parent and parent.status=='awaiting_approval' and follow:
        steps=(parent.plan or {}).get('steps',[])
        if len(steps)!=1 or steps[0]['tool']!=f"pms.{draft['_action']}_time_log" or steps[0]['payload'].get('log_id')!=row.id:
            raise HTTPException(409,'Keep the pending time entry target')
        expected=steps[0]['payload']['source_sha256']
        if draft['_action']=='edit':draft['_changes']={**{key:steps[0]['payload'][key] for key in Create.model_fields},**draft['_changes']}
    if expected and expected!=source:raise HTTPException(409,'Time entry changed; start a fresh review from current data')
    draft.update(project_id=row.project_id,_source_sha256=source)
    payload={'log_id':row.id,'source_sha256':source}
    if draft['_action']=='edit':
        if not draft['_changes']:return ask('What should change? Reply minutes=60, description=work, date=YYYY-MM-DD, billable=true/false or task=ID.')
        payload={**{key:before[key] for key in Create.model_fields},**draft['_changes'],**payload}
        if payload.get('description') is None:payload['description']=''
        try:payload=Edit.model_validate(payload).model_dump(mode='json')
        except ValueError:return ask('Choose a valid date, 1..1440 minutes, and valid manual time values.')
    data.project_id=row.project_id
    return Plan(summary=f"Review {draft['_action']} of your existing manual time entry. No timesheet is approved and no invoice is posted.",steps=[Step(tool=f"pms.{draft['_action']}_time_log",record_id=row.project_id,payload=payload)]),draft

