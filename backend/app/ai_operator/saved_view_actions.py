"""Reviewed private PMS task views through the canonical saved-view service."""
import json
import re
from datetime import date
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field,model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_operator.suite_tools import Strict
from app.ai_operator.service import digest

router=APIRouter(prefix='/suite/pms/views',tags=['Reviewed saved views'])


class Filters(Strict):
    status:str=Field(default='',max_length=120)
    priority:Literal['','Low','Medium','High','Urgent','Critical']=''
    search:str=Field(default='',max_length=300)
    assigneeId:str=Field(default='',pattern=r'^(?:[1-9]\d{0,9})?$')
    dueFrom:str=Field(default='',pattern=r'^(?:\d{4}-\d{2}-\d{2})?$')
    dueTo:str=Field(default='',pattern=r'^(?:\d{4}-\d{2}-\d{2})?$')

    @model_validator(mode='after')
    def valid(self):
        for value in (self.dueFrom,self.dueTo):
            if value:date.fromisoformat(value)
        if self.dueFrom and self.dueTo and self.dueFrom>self.dueTo:raise ValueError('The due-date range is reversed')
        return self


class Create(Strict):
    name:str=Field(min_length=1,max_length=140)
    project_id:int=Field(gt=0)
    filters:Filters=Field(default_factory=Filters)

    @model_validator(mode='after')
    def valid(self):
        if not self.name.strip() or re.search(r'[\x00-\x1f]',self.name):raise ValueError('Choose a plain nonempty view name')
        return self


class Approved(Create):
    suite_run_id:int=Field(gt=0)
    suite_step:int=Field(ge=1,le=12)


def preflight(db,user,run,step,index=None):
    if step.tool in {'hrms.create_saved_view','hrms.update_saved_view','hrms.remove_saved_view'}:
        from app.ai_operator.hrms_saved_view_actions import preflight as hrms_preflight
        return hrms_preflight(db,user,run,step,index)
    if step.tool in {'crm.create_saved_view','crm.update_saved_view','crm.remove_saved_view'}:
        from app.ai_operator.crm_saved_view_actions import preflight as crm_preflight
        return crm_preflight(db,user,run,step,index)
    if step.tool in {'pms.update_saved_view','pms.remove_saved_view'}:
        from app.ai_operator.pms_view_changes import preflight as callback
        return callback(db,user,run,step,index)
    from app.apps.project_management.access import get_project_for_action
    from app.apps.project_management.models import PMSSavedFilter
    value=Create.model_validate(step.payload)
    project=get_project_for_action(db,value.project_id,user,'browse')
    if project.workspace_id!=run.workspace_id:raise HTTPException(403,'Saved view project is outside this workspace')
    existing=db.query(PMSSavedFilter).filter_by(project_id=value.project_id,user_id=user.id,name=value.name).first()
    checkpoint=(run.result or {}).get('saved_view_checkpoint') or {}
    if existing and (existing.id!=checkpoint.get('receipt',{}).get('id') or checkpoint.get('payload_hash')!=digest(step.payload)):raise HTTPException(409,'A view with that name already exists; choose another name')
    return value


def confirmed(db,user,run,step):
    if step.tool in {'pms.update_saved_view','pms.remove_saved_view'}:
        from app.ai_operator.pms_view_changes import confirmed as callback
        return callback(db,user,run,step)
    from app.apps.project_management.models import PMSSavedFilter
    value=preflight(db,user,run,step);checkpoint=(run.result or {}).get('saved_view_checkpoint') or {}
    if not checkpoint:return None
    if checkpoint.get('step')!=run.active_step or checkpoint.get('payload_hash')!=digest(step.payload):return None
    receipt=checkpoint['receipt'];row=db.get(PMSSavedFilter,receipt['id'])
    expected={**value.filters.model_dump(),'projectId':str(value.project_id)}
    if not row:raise HTTPException(409,'The created view is unavailable; reconcile its recorded receipt')
    try:unchanged=[json.loads(value or '{}') for value in (row.filters_json,row.query,row.sort_json,row.columns_json)]==[expected,expected,{},{}]
    except (ValueError,TypeError):unchanged=False
    if row.user_id!=user.id or row.project_id!=value.project_id or row.name!=value.name or row.visibility!='private' or row.is_shared or row.is_default or row.entity_type!='task' or row.view_type!='task_list' or not unchanged:
        raise HTTPException(409,'The created view changed; reconcile its recorded receipt')
    return receipt


@router.post('/create-approved')
def create(data:Approved,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.agent_connectors import reviewed_run
    from app.apps.project_management.api.router import create_saved_view_record
    from app.apps.project_management.schemas import PMSSavedFilterCreate
    from app.ai_agents.services.audit import AiAuditService
    run,step=reviewed_run(db,user,request,data,Create,'create_saved_view');value=preflight(db,user,run,step)
    previous=confirmed(db,user,run,step)
    if previous:return previous
    native=PMSSavedFilterCreate(name=value.name,project_id=value.project_id,view_type='task_list',entity_type='task',
        visibility='private',is_shared=False,is_default=False,filters={**value.filters.model_dump(),'projectId':str(value.project_id)})
    from sqlalchemy.exc import IntegrityError
    try:row=create_saved_view_record(native,db,user,commit=False)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'The view changed concurrently; reload and choose a fresh name') from None
    receipt={'id':row['id'],'name':row['name'],'project_id':value.project_id,'visibility':'private','url':f'/pms/tasks/advanced?view={row["id"]}'}
    run.result={**(run.result or {}),'saved_view_checkpoint':{'step':data.suite_step,'payload_hash':digest(step.payload),'receipt':receipt}}
    AiAuditService(db).log(user=user,agent_id=None,module='PMS',action='suite.saved_view.created',input_json={'suite_run_id':run.id,'step':data.suite_step},output_json=receipt,status='success')
    db.commit();return receipt


def resume_stored(db,user,run,plan_hash):
    from app.ai_operator.suite import Plan,check_tool,finish_step
    from app.ai_operator.saved_agents import enforce
    from app.ai_agents.models import AiActionApproval
    from app.ai_agents.security import verify
    if run.status!='needs_reconciliation' or run.active_step!=len(run.receipts)+1:return False
    step=Plan.model_validate(run.plan).steps[run.active_step-1]
    if step.tool not in {'pms.update_saved_view','pms.remove_saved_view','pms.create_saved_view','crm.create_saved_view','hrms.create_saved_view','crm.update_saved_view','hrms.update_saved_view','crm.remove_saved_view','hrms.remove_saved_view'}:return False
    approval=db.get(AiActionApproval,run.approval_id)
    if run.plan_hash!=plan_hash or digest(run.plan)!=plan_hash or not approval or approval.status!='approved' or approval.approved_by!=user.id:raise HTTPException(409,'Review the unchanged approved view plan')
    verify(db,user,approval.security_context,payload=approval.proposed_action_json,confirmation=True)
    enforce(db,user,run,[step]);check_tool(db,user,run.workspace_id,step,True)
    confirm=confirmed
    if step.tool in {'crm.create_saved_view','crm.update_saved_view','crm.remove_saved_view'}:
        from app.ai_operator.crm_saved_view_actions import confirmed as confirm
    if step.tool in {'hrms.create_saved_view','hrms.update_saved_view','hrms.remove_saved_view'}:
        from app.ai_operator.hrms_saved_view_actions import confirmed as confirm
    receipt=confirm(db,user,run,step)
    if not receipt:raise HTTPException(409,'Saved view outcome requires reconciliation')
    index=run.active_step;finish_step(db,run,index,step.tool,receipt);run.error_code=None
    approval.execution_status=run.status;approval.execution_error=None
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module=step.tool.split('.')[0].upper(),action='suite.saved_view.resumed',
        input_json={'suite_run_id':run.id,'step':index},output_json={'view_id':receipt['id'],'policy':'committed-receipt-only'},status='success')
    db.commit();return True


def prepare(data,parent,db=None,user=None):
    from app.ai_operator.suite import Plan,Step
    explicit=re.match(r'(?i)^\s*(CRM|PMS|HRMS)\s*:',data.text)
    prior_module=(parent.result or {}).get('request',{}).get('module') if parent else None
    target=explicit[1].upper() if explicit else data.module or prior_module
    if target=='HRMS':
        from app.ai_operator.hrms_saved_view_actions import prepare as hrms_prepare
        return hrms_prepare(data,parent,db,user)
    if target=='CRM':
        from app.ai_operator.crm_saved_view_actions import prepare as crm_prepare
        return crm_prepare(data,parent,db,user)
    from app.ai_operator.pms_view_changes import prepare as prepare_change
    changed=prepare_change(data,parent,db,user)
    if changed is not None:return changed
    text=re.sub(r'(?i)^\s*PMS\s*:\s*','',data.text).strip()
    match=re.fullmatch(r'(?is)(?:please\s+)?(?:save|create)\s+(?:a\s+)?(?:saved\s+)?(?:task\s+)?(?:view|filter)\s+called\s+([^:]+)(?::\s*(.*))?',text)
    prior=(parent.result or {}).get('saved_view_draft') if parent and parent.status in {'needs_clarification','awaiting_approval'} else None
    if prior and prior.get('module') in {'CRM','HRMS'}:prior=None
    if not prior and parent and parent.status=='awaiting_approval':
        steps=(parent.plan or {}).get('steps',[])
        if len(steps)==1 and steps[0]['tool']=='pms.create_saved_view':prior=steps[0]['payload']
    if not match and not prior:return None,None
    data.module='PMS'
    if re.fullmatch(r'(?i)(?:cancel|stop|discard)[.! ]*',text):return Plan(summary='Saved view request cancelled.',steps=[]),None
    draft={'name':match[1].strip(),'project_id':data.project_id,'filters':{}} if match else json.loads(json.dumps(prior))
    values=match[2] if match else text
    if values:
        for field in values.split(';'):
            key,sep,value=field.strip().partition('=');key=key.strip();value=value.strip()
            if not sep or key not in {'name','project','status','priority','search','assignee','dueFrom','dueTo'}:
                return Plan(summary='Clarify the saved view.',question='Use name=...; project=ID; status=...; priority=High; search=...; assignee=ID; dueFrom=YYYY-MM-DD; dueTo=YYYY-MM-DD. Sharing is not changed.',steps=[]),draft
            if key=='name':draft['name']=value
            elif key=='project':
                if not re.fullmatch(r'[1-9]\d{0,9}',value):return Plan(summary='Choose a project.',question='What is the project ID? Use project=123.',steps=[]),draft
                draft['project_id']=int(value)
            else:draft['filters']['assigneeId' if key=='assignee' else key]=value
    if not draft.get('project_id'):return Plan(summary='Choose a project.',question='Which project should this private task view use? Reply project=123.',steps=[]),draft
    try:value=Create.model_validate(draft)
    except ValueError:return Plan(summary='Clarify the saved view.',question='Check the view name, priority, assignee ID and ISO due-date range, then provide corrected name=value fields.',steps=[]),draft
    data.module='PMS'
    return Plan(summary='Review this private saved task view. It changes no tasks, sharing or defaults.',steps=[Step(tool='pms.create_saved_view',payload=value.model_dump())]),value.model_dump()


def preview(db,user,run,step):
    if step.tool in {'pms.update_saved_view','pms.remove_saved_view'}:
        from app.ai_operator.pms_view_changes import preview as callback
        return callback(db,user,run,step)
    if step.tool.startswith('crm.'):
        from app.ai_operator.crm_saved_view_actions import preview as callback
    elif step.tool.startswith('hrms.'):
        from app.ai_operator.hrms_saved_view_actions import preview as callback
    else:return None
    return callback(db,user,run,step)



def project(db,user,step,index,states):
    if step.tool.startswith('crm.'):
        from app.ai_operator.crm_saved_view_actions import service
    else:
        from app.ai_operator.hrms_saved_view_actions import service
    return service.project(db,user,step,index,states)
