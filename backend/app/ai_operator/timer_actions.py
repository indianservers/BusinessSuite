"""Owner-bound native timer tools with reviewed transactional checkpoints."""
from uuid import UUID
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import Field,create_model
from app.core.deps import get_db,get_current_user
from app.ai_operator.suite_tools import Strict
from app.ai_operator.service import digest
from app.apps.project_management import timers as native
from app.apps.project_management.models import PMSRunningTimer,PMSTimeLog


class Read(Strict):pass


class Start(Strict):
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    session_key:UUID
    task_id:int|None=Field(default=None,gt=0,strict=True)
    timezone:str=Field(default='UTC',max_length=80)
    description:str=Field(default='',max_length=4000)
    is_billable:bool=Field(default=False,strict=True)


class Stop(Strict):
    source_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    session_key:UUID


MODELS={'start':Start,'stop':Stop,'discard':Stop}
ACTIONS={f'pms.{action}_timer' for action in MODELS}
router=APIRouter(prefix='/suite/pms/timer',tags=['Reviewed personal timers'])


def row_for(db,user,lock=False):
    query=db.query(PMSRunningTimer).filter_by(user_id=user.id).populate_existing()
    if lock:query=query.with_for_update()
    return query.first()


def state(row):return native.output(row) if row else None


def anchor(db,user,pid,workspace=None,write=False):
    from app.apps.project_management.access import get_project_for_action
    project=get_project_for_action(db,pid,user,'log_time' if write else 'browse')
    if workspace is not None and project.workspace_id!=workspace:raise HTTPException(403,'Timer project must match the selected workspace')
    return project


@router.get('/{project_id}')
def read(project_id:int,response:Response,db=Depends(get_db),user=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,None,'PMS');anchor(db,user,project_id)
    row=row_for(db,user)
    if row and row.active and row.project_id!=project_id:raise HTTPException(409,'Your active timer belongs to another project; select its authorized project')
    if row and row.active and row.task_id:
        from app.apps.project_management.access import get_task_project_for_action
        task,_=get_task_project_for_action(db,row.task_id,user,'browse')
        if task.project_id!=project_id:raise HTTPException(409,'Timer task moved; review the native timer')
    value={'id':project_id,'project_id':project_id,'name':'Your native timer','active':bool(row and row.active),
        'source_sha256':digest(state(row)),'scope':'current_user_selected_project'}
    if row and row.active:
        value.update(session_key=row.session_key,task_id=row.task_id,started_at=native.utc(row.started_at).isoformat(),
            timezone=row.timezone,description=row.description[:4000],description_truncated=len(row.description)>4000,is_billable=row.is_billable)
    response.headers['Cache-Control']='private, no-store'
    return value


def checkpoint(run,step):
    value=(run.result or {}).get('timer_checkpoint') or {}
    return value if value.get('step')==run.active_step and value.get('tool')==step.tool and value.get('payload_hash')==digest(step.payload) and value.get('project_id')==step.record_id else None


def preflight(db,user,run,step,lock=False):
    if type(step.record_id) is not int:raise HTTPException(422,'Select an existing timer project')
    project=anchor(db,user,step.record_id,write=True)
    if project.workspace_id!=run.workspace_id:raise HTTPException(403,'Timer project must match the selected workspace')
    action=step.tool.split('.')[1].removesuffix('_timer');value=MODELS[action].model_validate(step.payload)
    if checkpoint(run,step):return value
    row=row_for(db,user,lock)
    if digest(state(row))!=value.source_sha256:raise HTTPException(409,'Timer changed; read it again before review')
    if action=='start':
        if row and row.active:raise HTTPException(409,'Stop or discard your current timer before starting another')
        if row and row.session_key==str(value.session_key):raise HTTPException(409,'Choose a fresh timer session key')
        try:ZoneInfo(value.timezone)
        except (ValueError,ZoneInfoNotFoundError):raise HTTPException(422,'Choose a valid timer timezone') from None
        if value.task_id:
            from app.apps.project_management.access import get_task_project_for_action
            task,_=get_task_project_for_action(db,value.task_id,user,'log_time')
            if task.project_id!=step.record_id:raise HTTPException(422,'Timer task must belong to the selected project')
    elif not row or not row.active or row.project_id!=step.record_id or row.session_key!=str(value.session_key):
        raise HTTPException(409,'Select the current active timer session in this project')
    elif row.task_id:
        from app.apps.project_management.access import get_task_project_for_action
        task,_=get_task_project_for_action(db,row.task_id,user,'log_time')
        if task.project_id!=step.record_id:raise HTTPException(409,'Timer task moved; review the native timer')
    return value


def preview(db,user,run,step):
    value=preflight(db,user,run,step);action=step.tool.split('.')[1].removesuffix('_timer');row=row_for(db,user)
    before=state(row) if row and row.active else None
    after={key:getattr(value,key) for key in ('task_id','timezone','description','is_billable')} if action=='start' else {'active':False}
    effect={'start':'Starts when executed on the server. Running time is not recorded until a reviewed stop.',
        'stop':'Stops when executed on the server; elapsed time rounds up to a whole minute (minimum one), creating one Pending entry. This does not approve a timesheet or post an invoice.',
        'discard':'Stops this session without creating a time entry; unrecorded elapsed time is discarded.'}[action]
    return {'record_id':str(value.session_key),'record_name':'Your native timer','changes':[
        {'field':'timer','before':{**before,'started_at':native.utc(row.started_at).isoformat()} if before else None,'after':after},
        {'field':'effect','before':None,'after':effect}]}


def confirmed(db,user,run,step):
    saved=checkpoint(run,step)
    if not saved:return None
    if digest(state(row_for(db,user)))!=saved['state_hash']:raise HTTPException(409,'Committed timer state changed; reconcile the receipt')
    if step.tool=='pms.stop_timer':
        from app.ai_operator.time_actions import owned,state as log_state
        receipt=saved['receipt'];log=owned(db,user,step.record_id,receipt['id'])
        if digest(log_state(db,log))!=saved['log_state_hash']:raise HTTPException(409,'Recorded timer entry changed; reconcile its receipt')
    return saved['receipt']


def register(action,Model):
    Approved=create_model(action.title()+'ApprovedTimer',__base__=Model,suite_run_id=(int,Field(gt=0)),suite_step=(int,Field(ge=1,le=12)))
    @router.post('/{project_id}/'+action+'-approved')
    def execute(project_id:int,data:Approved,request:Request,db=Depends(get_db),user=Depends(get_current_user)):
        from app.ai_operator.agent_connectors import reviewed_run
        from app.ai_agents.services.audit import AiAuditService
        run,step=reviewed_run(db,user,request,data,Model,action+'_timer')
        if step.record_id!=project_id:raise HTTPException(403,'Timer target differs from the approved project')
        prior=confirmed(db,user,run,step)
        if prior:return prior
        value=preflight(db,user,run,step,True)
        if action=='start':
            result=native.start_timer_operation(native.StartInput(project_id=project_id,**value.model_dump(exclude={'source_sha256'})),db,user,commit=False)
        elif action=='stop':result=native.stop_timer_operation(native.StopInput(session_key=value.session_key),db,user,commit=False)
        else:result=native.discard_timer_operation(native.StopInput(session_key=value.session_key),db,user,commit=False)
        row=row_for(db,user)
        receipt={'id':result['log_id'] if action=='stop' else str(value.session_key),'title':f'Timer {action}',
            'operation':action,'timer_active':row.active,'timer_session_key':row.session_key}
        log_hash=None
        if action=='stop':
            from app.ai_operator.time_actions import state as log_state
            log=db.get(PMSTimeLog,result['log_id']);log_hash=digest(log_state(db,log));receipt['duration_minutes']=log.duration_minutes
        run.result={**(run.result or {}),'timer_checkpoint':{'step':data.suite_step,'tool':step.tool,'project_id':project_id,
            'payload_hash':digest(step.payload),'state_hash':digest(state(row)),'log_state_hash':log_hash,'receipt':receipt}}
        AiAuditService(db).log(user=user,agent_id=None,module='PMS',action='suite.timer.'+action,input_json={'suite_run_id':run.id,'step':data.suite_step},output_json=receipt,status='success')
        db.commit();return receipt


for _action,_model in MODELS.items():register(_action,_model)


def validate_plan(plan):
    if sum(step.tool in ACTIONS for step in plan.steps)>1:raise HTTPException(422,'Read the confirmed timer before preparing another timer action')


def resume_stored(db,user,run,plan_hash):
    from app.ai_operator.suite import Plan,check_tool,finish_step
    from app.ai_operator.saved_agents import enforce
    from app.ai_agents.models import AiActionApproval
    from app.ai_agents.security import verify
    if run.status!='needs_reconciliation' or run.active_step!=len(run.receipts)+1:return False
    step=Plan.model_validate(run.plan).steps[run.active_step-1]
    if step.tool not in ACTIONS:return False
    approval=db.get(AiActionApproval,run.approval_id)
    if run.plan_hash!=plan_hash or digest(run.plan)!=plan_hash or not approval or approval.status!='approved' or approval.approved_by!=user.id:raise HTTPException(409,'Review the unchanged approved timer plan')
    verify(db,user,approval.security_context,payload=approval.proposed_action_json,confirmation=True)
    enforce(db,user,run,[step]);check_tool(db,user,run.workspace_id,step,True)
    receipt=confirmed(db,user,run,step)
    if not receipt:raise HTTPException(409,'Timer outcome requires reconciliation')
    finish_step(db,run,run.active_step,step.tool,receipt);run.error_code=None
    approval.execution_status=run.status;approval.execution_error=None
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module='PMS',action='suite.timer.resumed',input_json={'suite_run_id':run.id},output_json={'timer_receipt':receipt['id'],'policy':'committed-receipt-only'},status='success')
    db.commit();return True

