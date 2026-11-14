"""Fresh reviews for never-dispatched structured PMS work; no replay of receipts."""
from copy import deepcopy
from types import SimpleNamespace
import re
from fastapi import HTTPException
from app.ai_operator.service import digest, validate_plan
from app.ai_operator.models import OperatorRun, OperatorJob, OperatorStep
from app.ai_operator.suite_models import SuiteRun
from app.ai_agents.models import AiActionApproval

SAFE_CHANGES={'status','priority','assignee_user_ids','estimated_hours','story_points'}
STRUCTURED_FIELDS={'update_task':{'tool','task_id','changes','depends_on'},
    'schedule_task':{'tool','task_id','start_date','due_date','depends_on'},
    'move_to_sprint':{'tool','task_id','sprint_id','depends_on'},
    'add_dependency':{'tool','task_id','source_task_id','dependency_type','lag_days','depends_on'}}


def structured_plan(value):
    clean=[]
    for task in value['steps']:
        if task['tool'] not in STRUCTURED_FIELDS or task.get('changes') and set(task['changes'])-SAFE_CHANGES:
            raise HTTPException(409,'Remaining text/content actions require a new explicit request from current sources')
        clean.append({key:deepcopy(item) for key,item in task.items() if key in STRUCTURED_FIELDS[task['tool']]})
    return {'summary':'Review remaining structured task changes','steps':clean}


def prepare(db,user,data):
    match=re.fullmatch(r'(?i)\s*(?:review|prepare)\s+(?:the\s+)?remaining\s+PMS\s+workflow\s*#?\s*([1-9]\d*)[.! ]*',data.text)
    if not match:return None,None
    from app.ai_operator.suite import Plan
    from app.ai_operator.completion_receipts import read
    from app.ai_operator.schemas import TaskPlan
    from app.ai_operator.workload_guard import current
    source=db.query(SuiteRun).filter_by(id=int(match[1]),user_id=user.id).first()
    if not source:raise HTTPException(404,'Workflow not found')
    if source.status!='paused' or source.workspace_id!=data.workspace_id:
        raise HTTPException(409,'Choose a paused PMS workflow in the current workspace')
    safe=read(db,user,source)
    if not safe:raise HTTPException(409,'Confirmed native execution evidence is required')
    pending=[];steps=[];positions={}
    for index,step in enumerate(source.plan['steps'],1):
        progress=safe['workflow_steps'][index-1]
        if progress['status'] in {'succeeded','awaiting_receipt'}:continue
        project_id=step['record_id']
        if data.project_id not in (None,project_id):raise HTTPException(409,'Remaining work must retain the selected project')
        child_id=source.snapshots['pms_children'][str(index)]['id']
        child=db.get(OperatorRun,child_id);approval=db.get(AiActionApproval,child.approval_id) if child else None
        check_never_started(db,child,approval)
        original=TaskPlan.model_validate(step['payload']['plan'])
        payload={'plan':structured_plan(original.model_dump(mode='json',exclude_none=True)),'mode':'atomic'}
        # Validate current task access and collaborator eligibility before any
        # historical intended IDs enter a new visible draft.
        validate_plan(db,user,SimpleNamespace(project_id=project_id,selection=child.selection),TaskPlan.model_validate(payload['plan']))
        if step['payload'].get('workload_guard'):
            payload['workload_guard']=current(db,user,project_id,step['payload']['workload_guard'])
        positions[index]=len(steps)+1
        steps.append({'tool':'pms.task_plan','record_id':project_id,'payload':payload,
            'depends_on':[positions[prior] for prior in step.get('depends_on',[]) if prior in positions]})
        pending.append({'source_step':index,'native_run_id':child.id,'approval_id':approval.id,'plan_hash':child.plan_hash})
    if not steps:raise HTTPException(409,'No never-dispatched task plans remain')
    plan=Plan(summary=f'Review {len(steps)} remaining task plans from workflow #{source.id}. Confirmed native executions will not repeat.',steps=steps)
    data.module='PMS';data.task_ids=[];data.context=[];data.provider='local'
    return plan,{'source_run_id':source.id,'source_plan_hash':source.plan_hash,'pending':pending,
        'confirmed_native_runs':[card['id'] for card in safe['result_cards']],
        'new_plan_hash':digest(plan.model_dump(mode='json',exclude_none=True))}


def check_never_started(db,child,approval):
    if not child or child.status!='awaiting_approval' or not approval or approval.status!='pending' or approval.execution_status!='pending' or approval.approved_at:
        raise HTTPException(409,'Remaining native work may have started; reconcile it before preparing a replacement')
    if (child.result or {}).get('receipts') or db.query(OperatorJob.id).filter_by(run_id=child.id,kind='execute').first() or db.query(OperatorStep.id).filter_by(run_id=child.id,status='succeeded').first():
        raise HTTPException(409,'Native execution evidence prevents duplicate preparation')


def reserve(db,user,new_run,packet):
    """Retire old pending approvals only after new native previews are complete."""
    # prepare() may already have loaded this row. A lock alone does not refresh
    # its identity-map state after waiting for a concurrent source mutation.
    source=db.query(SuiteRun).filter_by(id=packet['source_run_id'],user_id=user.id).with_for_update().populate_existing().first()
    if not source or source.status!='paused' or source.plan_hash!=packet['source_plan_hash'] or digest(source.plan)!=source.plan_hash:
        raise HTTPException(409,'Source workflow changed; prepare a new review')
    if new_run.plan_hash!=packet['new_plan_hash']:raise HTTPException(409,'Remaining task review changed')
    from app.ai_operator.completion_receipts import read
    if not read(db,user,source):raise HTTPException(409,'Source execution evidence changed')
    approvals={row.id:row for row in db.query(AiActionApproval).filter(AiActionApproval.id.in_([p['approval_id'] for p in packet['pending']])).order_by(AiActionApproval.id).with_for_update().populate_existing()}
    children={row.id:row for row in db.query(OperatorRun).filter(OperatorRun.id.in_([p['native_run_id'] for p in packet['pending']])).order_by(OperatorRun.id).with_for_update().populate_existing()}
    for item in packet['pending']:
        child=children.get(item['native_run_id']);approval=approvals.get(item['approval_id'])
        if not child or child.user_id!=user.id or child.plan_hash!=item['plan_hash'] or child.approval_id!=item['approval_id']:
            raise HTTPException(409,'Source native task plan changed')
        check_never_started(db,child,approval)
    for item in packet['pending']:
        child=children[item['native_run_id']];approval=approvals[item['approval_id']]
        child.status='cancelled';approval.status='cancelled';approval.execution_status='cancelled'
        from app.ai_operator.jobs import emit
        emit(db,child,'run.cancelled',reason='remaining_review',replacement_suite_run_id=new_run.id)
    source.status='superseded'
    source.result={**source.result,'remaining_review_id':new_run.id}
    source_approval=db.get(AiActionApproval,source.approval_id)
    if source_approval:source_approval.execution_status='superseded'
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module='PMS',action='suite.remaining_prepared',
        input_json={'source_run_id':source.id,'replacement_run_id':new_run.id,
                    'retired_native_run_ids':[item['native_run_id'] for item in packet['pending']]},
        output_json={'source_status':'superseded','replacement_status':new_run.status},status='success')
