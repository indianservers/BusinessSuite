"""Minimal current-authority receipts; never reopen stale conversation history."""
from app.ai_operator.models import OperatorRun
from app.ai_operator.schemas import TaskPlan
from app.ai_operator.service import context_for, digest
from app.ai_agents.models import AiActionApproval
from app.ai_agents.security import verify_provenance
from app.apps.project_management.access import get_project_for_action
from fastapi import HTTPException


def read(db,user,run):
    from app.ai_operator.suite import authorize
    if run.user_id!=user.id or run.status not in {'succeeded','waiting_pms','paused','queued','executing','needs_reconciliation','cancelled','superseded'}:return None
    steps=(run.plan or {}).get('steps',[])
    if not 1<=len(steps)<=12 or any(step.get('tool')!='pms.task_plan' or type(step.get('record_id')) is not int for step in steps):return None
    verify_provenance(user,run.security_context)
    if digest(run.plan)!=run.plan_hash:return None
    if authorize(db,user,run.workspace_id,'PMS',control=True)!=run.scope_key:return None
    parent_approval=db.get(AiActionApproval,run.approval_id)
    if not parent_approval or parent_approval.user_id!=user.id or parent_approval.status!='approved':return None
    verify_provenance(user,parent_approval.security_context,payload=parent_approval.proposed_action_json)
    if parent_approval.proposed_action_json.get('input',{}).get('suite_run_id')!=run.id or digest(parent_approval.proposed_action_json.get('preview'))!=run.plan_hash:return None
    verified={};cards=[];progress=[];projects=set();remaining=0;offer=True
    stored={}
    for receipt in run.receipts or []:
        position=receipt.get('step')
        if type(position) is not int or not 1<=position<=len(steps) or position in stored:return None
        stored[position]=receipt
    attempts=((run.result or {}).get('checkpoint') or {}).get('attempts') or {}
    for index,step in enumerate(steps,1):
        project=get_project_for_action(db,step['record_id'],user,'manage_tasks')
        if project.workspace_id!=run.workspace_id:return None
        projects.add(project.id)
        prepared=(run.snapshots or {}).get('pms_children',{}).get(str(index),{})
        if prepared.get('kind')!='task':return None
        child=db.query(OperatorRun).filter_by(id=prepared.get('id'),user_id=user.id,project_id=project.id).first()
        if not child or child.plan_hash!=prepared.get('plan_hash'):return None
        verify_provenance(user,child.security_context)
        normalized=TaskPlan.model_validate(step['payload']['plan']).model_dump(mode='json',exclude_none=True)
        if digest(child.plan)!=child.plan_hash or digest(normalized)!=child.plan_hash:return None
        native_approval=db.get(AiActionApproval,child.approval_id)
        if not native_approval or native_approval.user_id!=user.id:return None
        verify_provenance(user,native_approval.security_context,payload=native_approval.proposed_action_json)
        if native_approval.proposed_action_json.get('input',{}).get('run_id')!=child.id or digest(native_approval.proposed_action_json.get('preview'))!=child.plan_hash:return None
        context_for(db,user,project.id,child.selection)
        status='not_confirmed'
        if child.status=='succeeded':
            confirmed=(child.result or {}).get('receipts',[])
            if native_approval.status!='approved' or native_approval.execution_status!='executed' or not (child.result or {}).get('success') or len(confirmed)!=len(normalized['steps']):return None
            status='succeeded' if index in stored else 'awaiting_receipt'
            verified[index]={'step':index,'tool':'pms.task_plan','record_id':project.id,'pms_run_id':child.id,'status':'succeeded'}
            cards.append({'id':f'pms-receipt:{child.id}','kind':'task','title':'Native task execution confirmed',
                'status':'succeeded','record_id':project.id,'href':f'/pms/projects/{project.id}/tasks',
                'body':f'{len(confirmed)} native task steps confirmed for workflow step {index}.'})
        else:
            remaining+=1
            if child.status!='awaiting_approval' or native_approval.status!='pending' or native_approval.execution_status!='pending' or native_approval.approved_at:
                offer=False
            try:
                from app.ai_operator.remaining_tasks import structured_plan
                structured_plan(normalized)
            except HTTPException:offer=False
        if index in stored and (index not in verified or stored[index].get('pms_run_id')!=child.id or stored[index].get('tool')!='pms.task_plan'):return None
        count=attempts.get(str(index),0)
        progress.append({'step':index,'tool':'pms.task_plan','depends_on':step.get('depends_on',[]),
                         'status':status,'attempts':count if type(count) is int and count>=0 else 0})
    if not verified:return None
    if run.status=='succeeded' and (len(verified)!=len(steps) or len(stored)!=len(steps)):return None
    complete=run.status=='succeeded'
    summary=(f'{len(verified)} of {len(steps)} native task executions confirmed. '
             +('Workflow completed. ' if complete else 'Remaining workflow completion is not confirmed. ')
             +'Historical conversation content is restricted; start a fresh conversation for new work.')
    prompt=None
    if run.status=='paused' and remaining and offer and len(projects)==1:
        try:
            from app.ai_operator.suite import check_tool_access
            from app.access.service import check_background_access
            check_tool_access(db,user,run.workspace_id,'pms.task_plan')
            check_background_access(db,user,'ai','create')
            check_background_access(db,user,'project_management','edit')
            prompt=f'Review remaining PMS workflow #{run.id}'
        except HTTPException:pass
    return {'id':run.id,'workspace_id':run.workspace_id,'scope_key':run.scope_key,'status':run.status,
        'command':'PMS task execution','plan_hash':run.plan_hash,'plan':{'summary':summary,'steps':[]},
        'approval_id':None,'active_step':None,'can_resume':False,'workflow_steps':progress,
        'receipts':[verified[index] for index in sorted(stored)],'error_code':None,
        'result':{'history_restricted':True,**({'remaining_review_prompt':prompt} if prompt else {}),
                  'request':{'module':'PMS','project_id':next(iter(projects)) if len(projects)==1 else None}},
        'result_cards':cards,'pms_previews':{},'created_at':run.created_at}
