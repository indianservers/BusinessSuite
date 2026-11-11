"""Private multi-agent DAGs on SuiteRun checkpoints and canonical reviewed runs.

Starting a workflow grants preparation, not approval of future business actions.
Each agent retains its own tool/module restrictions and a persistent conversation.
"""
import re
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID,uuid5,NAMESPACE_URL
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field,StrictInt,model_validator
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_operator.suite_models import SuiteRun
from app.ai_operator.suite_tools import Strict
from app.ai_operator.agent_schedules import snapshot,occurrence_run,prepare_agent,now,utc
from app.ai_operator.service import digest
from app.ai_agents.security import seal,verify,company

router=APIRouter(prefix='/suite/agents/workflows',tags=['Multi-agent workflows'])
VARIABLE=re.compile(r'\{\{step\.([1-9]\d*)\.(record_id|artifact_id|run_id|conversation_id)\}\}')
TERMINAL={'answered','succeeded','cancelled','failed'}


class Node(Strict):
    agent_id:int=Field(gt=0)
    instructions:str=Field(min_length=1,max_length=6000)
    depends_on:list[StrictInt]=Field(default_factory=list,max_length=7)


class Workflow(Strict):
    request_key:UUID
    name:str=Field(min_length=1,max_length=120)
    workspace_id:int|None=Field(default=None,gt=0)
    nodes:list[Node]=Field(min_length=1,max_length=8)
    timezone:str='Asia/Kolkata'

    @model_validator(mode='after')
    def valid(self):
        from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
        from app.ai_operator.suite_memory import MemoryText
        if not self.name.strip():raise ValueError('Name the workflow')
        try:ZoneInfo(self.timezone)
        except (ValueError,ZoneInfoNotFoundError):raise ValueError('Choose an IANA timezone') from None
        for index,node in enumerate(self.nodes,1):
            MemoryText.safe_text(node.instructions)
            if len(set(node.depends_on))!=len(node.depends_on) or any(not 1<=n<index for n in node.depends_on):raise ValueError('Dependencies must be unique earlier steps')
            for match in VARIABLE.finditer(node.instructions):
                if int(match[1]) not in node.depends_on:raise ValueError('Variables require an explicit earlier dependency')
            if '{{' in VARIABLE.sub('',node.instructions) or '}}' in VARIABLE.sub('',node.instructions):raise ValueError('Use supported step ID variables')
        return self


class Confirmation(Strict):
    preview_hash:str=Field(min_length=64,max_length=64)


class PlanningRetry(Strict):
    request_key:UUID


def owned(db,user,ident,lock=False):
    from app.ai_operator.suite import owned as run_owned
    run=run_owned(db,user,ident,lock)
    if not (run.result or {}).get('agent_workflow'):raise HTTPException(404,'Agent workflow not found')
    return run


def public(run):
    data=run.result
    return {'id':run.id,'name':run.command,'workspace_id':run.workspace_id,'status':run.status.removeprefix('workflow_'),
        'preview_hash':run.request_hash,'spec':data['spec'],'agents':data['agents'],'nodes':data['nodes'],
        'error':run.error_code,'issue':data.get('issue'),'cancel_errors':data.get('cancel_errors',[]),'created_at':run.created_at,'execution':'Agents prepare independently; each action draft requires review.'}


def audit(db,user,run,action):
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module='CROSS',action='agent_workflow.'+action,
        input_json={'workflow_id':run.id},output_json={'status':run.status},status='success')


def grant(db,user,run,confirmation=False):
    data=run.result;value={'spec':data['spec'],'agents':data['agents'],'branch_id':run.snapshots['branch_id']}
    if digest(value)!=run.request_hash:raise HTTPException(409,'Workflow definition changed')
    verify(db,user,run.snapshots['workflow_grant'],payload=run.request_hash,confirmation=confirmation)
    for ident,frozen in data['agents'].items():
        if snapshot(db,user,int(ident))!=frozen:raise HTTPException(409,'Workflow agent, skill or connection changed; prepare a new workflow')


@router.post('/preview')
def preview(data:Workflow,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    scope=authorize(db,user,data.workspace_id)
    branch=db.info.get('branch_context')
    if not branch or not branch.branch_id:raise HTTPException(422,'Select a concrete branch')
    agents={str(n.agent_id):snapshot(db,user,n.agent_id) for n in data.nodes}
    if any(a['workspace_id']!=data.workspace_id for a in agents.values()):raise HTTPException(403,'All workflow agents must belong to this workspace')
    spec=data.model_dump(mode='json',exclude={'request_key'});hashed=digest({'spec':spec,'agents':agents,'branch_id':branch.branch_id})
    key='agent-workflow:'+str(data.request_key)
    previous=db.query(SuiteRun.id).filter_by(user_id=user.id,request_key=key).first()
    if previous:
        run=owned(db,user,previous[0])
        if run.request_hash!=hashed:raise HTTPException(409,'Request key belongs to another workflow')
        return public(run)
    if db.query(SuiteRun.id).filter_by(user_id=user.id,scope_key=scope).filter(SuiteRun.status.like('workflow_%'),SuiteRun.status.notin_(['workflow_succeeded','workflow_cancelled'])).count()>=30:
        raise HTTPException(422,'Stop unused workflows before adding more')
    run=SuiteRun(user_id=user.id,session_id=getattr(user,'_suite_session_id',None),workspace_id=data.workspace_id,scope_key=scope,
        request_key=key,request_hash=hashed,command=data.name,status='workflow_preview',receipts=[],
        result={'agent_workflow':True,'spec':spec,'agents':agents,'nodes':[{'step':i,'state':'pending'} for i in range(1,len(data.nodes)+1)]},
        snapshots={'branch_id':branch.branch_id,'workflow_grant':seal(db,user,hashed)})
    db.add(run)
    try:db.flush();audit(db,user,run,'preview');db.commit()
    except IntegrityError:
        db.rollback();previous=db.query(SuiteRun.id).filter_by(user_id=user.id,request_key=key).first()
        if not previous:raise HTTPException(409,'Conflicting workflow request') from None
        run=owned(db,user,previous[0])
        if run.request_hash!=hashed:raise HTTPException(409,'Conflicting workflow request') from None
    return public(run)


@router.post('/{ident}/start')
def start(ident:int,data:Confirmation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    run=owned(db,user,ident,True)
    if run.status!='workflow_preview' or run.request_hash!=data.preview_hash:raise HTTPException(409,'Reload the workflow preview')
    grant(db,user,run,True);run.status='workflow_active';audit(db,user,run,'started');db.commit();return public(run)


@router.get('')
def listing(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    scope=authorize(db,user,workspace_id)
    rows=db.query(SuiteRun.id).filter_by(user_id=user.id,scope_key=scope,workspace_id=workspace_id).filter(SuiteRun.result['agent_workflow'].as_boolean()==True).order_by(SuiteRun.id.desc()).limit(50)
    return {'items':[public(owned(db,user,r[0])) for r in rows]}


@router.get('/{ident}')
def get(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):return public(owned(db,user,ident))


@router.post('/{ident}/resume')
def resume(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    run=owned(db,user,ident,True)
    if run.status not in ('workflow_paused','workflow_waiting','workflow_blocked'):raise HTTPException(409,'Workflow is not waiting or paused')
    grant(db,user,run);run.status='workflow_active';run.lease_until=None;run.error_code=None;audit(db,user,run,'resumed');db.commit();return public(run)


@router.post('/{ident}/steps/{position}/retry-planning')
async def retry_planning(ident:int,position:int,data:PlanningRetry,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import api_call
    from app.ai_agents.models import AiActionApproval
    run=owned(db,user,ident,True);grant(db,user,run)
    if run.status in ('workflow_preview','workflow_succeeded','workflow_cancelled'):raise HTTPException(409,'Workflow is not awaiting recovery')
    nodes=[dict(n) for n in run.result['nodes']]
    if not 1<=position<=len(nodes):raise HTTPException(404,'Workflow step not found')
    node=nodes[position-1];key=str(data.request_key)
    if key in node.get('retry_requests',{}):return public(run)
    if not node.get('run_id') or len(node.get('retry_requests',{}))>=3:raise HTTPException(409,'Step cannot retry planning again')
    child=occurrence_run(db,user,node,run.result['spec']['nodes'][position-1]['agent_id'])
    approval=db.get(AiActionApproval,child.approval_id) if child.approval_id else None
    if child.status!='failed' or child.receipts or approval and approval.status=='approved':raise HTTPException(409,'Use the existing child review or resume; completed or uncertain writes cannot be replanned')
    response=await api_call(request.app,request.headers.get('authorization',''),'POST',f'/ai-operator/suite/runs/{child.id}/retry-planning',{'request_key':key,'provider':'original'})
    run=owned(db,user,ident,True)
    if run.status=='workflow_cancelled':raise HTTPException(409,'Workflow was stopped during planning; inspect the child conversation')
    nodes=[dict(n) for n in run.result['nodes']];node=nodes[position-1]
    node.update(run_id=response['id'],run_status=response['status'],state='running',retry_requests={**node.get('retry_requests',{}),key:response['id']})
    run.result={**run.result,'nodes':nodes};run.status='workflow_active';run.lease_until=None;run.error_code=None;audit(db,user,run,'planning_retried');db.commit();return public(run)


@router.post('/{ident}/stop')
async def stop(ident:int,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import api_call
    run=owned(db,user,ident,True)
    if run.status=='workflow_succeeded':return public(run)
    run.status='workflow_cancelled';run.lease_until=None;db.commit();errors=[];updates={}
    for node,spec in zip(run.result['nodes'],run.result['spec']['nodes']):
        if not node.get('run_id'):continue
        try:
            child=occurrence_run(db,user,node,spec['agent_id'])
            if child.status not in TERMINAL:
                response=await api_call(request.app,request.headers.get('authorization',''),'POST',f'/ai-operator/suite/runs/{child.id}/cancel')
                status=response['status']
            else:status=child.status
            updates[node['step']]={'run_id':child.id,'run_status':status,'state':'done' if status in ('answered','succeeded') else 'stopped'}
        except HTTPException:errors.append(node['step'])
    run=owned(db,user,ident,True);run.result={**run.result,'cancel_errors':errors,'nodes':[{**n,**updates.get(n['step'],{})} for n in run.result['nodes']]};audit(db,user,run,'stopped');db.commit()
    return {**public(run),'cancel_errors':errors}


def instructions(db,user,spec,nodes):
    """Only canonical IDs cross the handoff boundary; source facts are read afresh."""
    def substitute(match):
        node=nodes[int(match[1])-1];field=match[2]
        if node['state']!='done':raise HTTPException(409,'Dependency is not complete')
        if field in ('run_id','conversation_id'):return str(node[field])
        from app.ai_operator.suite import owned as run_owned
        child=run_owned(db,user,node['run_id'])
        values={r[field] for r in child.receipts or [] if r.get('status')=='succeeded' and type(r.get(field)) is int}
        if len(values)!=1:raise HTTPException(422,'Dependency does not have one unambiguous output ID')
        return str(next(iter(values)))
    return VARIABLE.sub(substitute,spec['instructions'])


async def dispatch(db,app,instant=None,limit=5):
    from app.access.service import activate_run_context,release_run_context,background_scope
    from app.ai_operator import suite_conversations as chats
    instant=instant or now();processed=0
    ids=db.query(SuiteRun.id).filter(SuiteRun.status.in_(['workflow_active','workflow_running','workflow_waiting','workflow_paused']),
        or_(SuiteRun.lease_until==None,SuiteRun.lease_until<=instant)).order_by(SuiteRun.id).limit(min(limit,20)).all()
    for (ident,) in ids:
        run=db.query(SuiteRun).filter_by(id=ident).with_for_update(skip_locked=True).first()
        if not run or not run.result or not run.result.get('agent_workflow'):continue
        if run.status not in ('workflow_active','workflow_running','workflow_waiting','workflow_paused') or run.lease_until and utc(run.lease_until)>instant:
            db.rollback();continue
        previous_status=run.status;old_lease=run.lease_until
        claim_until=instant+timedelta(minutes=5)
        claimed=db.query(SuiteRun).filter_by(id=ident,status=previous_status,lease_until=old_lease).update({'status':'workflow_running','lease_until':claim_until},synchronize_session=False)
        if not claimed:db.rollback();continue
        run.status='workflow_running';run.lease_until=instant+timedelta(minutes=5);db.commit();actor=None
        try:
            actor=db.query(User).filter_by(id=run.user_id,is_active=True).first()
            if not actor:raise HTTPException(403,'Workflow owner unavailable')
            activate_run_context(db,actor,run)
            with background_scope(db,actor,'ai','view',branch_id=run.snapshots['branch_id']):
                grant(db,actor,run);actor._suite_session_id=run.session_id
                data=run.result;nodes=[dict(n) for n in data['nodes']];specs=data['spec']['nodes']
                for node,spec in zip(nodes,specs):
                    if not node.get('run_id') or node['state']=='done':continue
                    child=occurrence_run(db,actor,node,spec['agent_id']);node['run_id']=child.id
                    node['state']='done' if child.status in ('answered','succeeded') else 'failed' if child.status in ('failed','cancelled') else 'review' if child.status in ('needs_clarification','awaiting_approval') else 'running'
                    node['run_status']=child.status
                if any(n['state']=='failed' or n.get('run_status') in ('paused','needs_reconciliation') for n in nodes):
                    run.status='workflow_paused';run.error_code='AGENT_STEP_NEEDS_REVIEW';run.lease_until=instant+timedelta(minutes=1)
                    run.result={**data,'nodes':nodes};db.commit();continue
                if all(n['state']=='done' for n in nodes):
                    run.status='workflow_succeeded';run.lease_until=None;run.error_code=None;run.result={**data,'nodes':nodes};db.commit();processed+=1;continue
                target=next((n for n,s in zip(nodes,specs) if n['state'] in ('pending','planning') and all(nodes[d-1]['state']=='done' for d in s['depends_on'])),None)
                if not target:
                    run.status='workflow_waiting';run.lease_until=instant+timedelta(seconds=10);run.result={**data,'nodes':nodes};db.commit();continue
                index=target['step'];spec=specs[index-1];frozen=data['agents'][str(spec['agent_id'])]
                prompt=instructions(db,actor,spec,nodes)
                if not target.get('conversation_id'):
                    chat=chats.create(db,actor,chats.ConversationInput(title=f"{run.command}: {index}. {frozen['name']}"[:160],workspace_id=run.workspace_id),commit=False)
                    target.update(conversation_id=chat['id'],request_key=str(uuid5(NAMESPACE_URL,f'agent-workflow:{run.id}:{index}')))
                target['state']='planning';run.result={**data,'nodes':nodes};db.commit()
                prepared=await prepare_agent(app,actor.id,run.session_id,company(actor),run.snapshots['branch_id'],{
                    'request_key':target['request_key'],'text':prompt,'agent_id':spec['agent_id'],'provider':'preferred',
                    'timezone':data['spec']['timezone'],'workspace_id':run.workspace_id,'project_id':frozen['project_id'],'conversation_id':target['conversation_id']})
                db.expire_all();run=db.query(SuiteRun).filter_by(id=ident).with_for_update().one()
                if run.status!='workflow_cancelled' and (run.status!='workflow_running' or not run.lease_until or utc(run.lease_until)!=utc(claim_until)):
                    db.rollback();continue  # A newer worker owns this checkpoint.
                nodes=[dict(n) for n in run.result['nodes']];target=nodes[index-1];target.update(run_id=prepared['id'],run_status=prepared['status'],state='running')
                run.result={**run.result,'nodes':nodes}
                if run.status=='workflow_cancelled':
                    from app.core.security import create_access_token
                    from app.ai_operator.suite import api_call
                    token=create_access_token(str(actor.id),session_id=run.session_id,expires_delta=timedelta(minutes=1))
                    try:
                        if prepared['status'] not in TERMINAL:
                            await api_call(app,'Bearer '+token,'POST',f'/ai-operator/suite/runs/{prepared["id"]}/cancel')
                        target.update(state='done' if prepared['status'] in ('answered','succeeded') else 'failed',run_status=prepared['status'] if prepared['status'] in TERMINAL else 'cancelled')
                        run.result={**run.result,'nodes':nodes};run.error_code=None
                    except HTTPException:
                        run.result={**run.result,'cancel_errors':sorted(set([*run.result.get('cancel_errors',[]),index]))}
                        run.error_code='CHILD_CANCELLATION_NEEDS_REVIEW'
                else:run.status='workflow_active';run.lease_until=None
                db.commit();processed+=1
        except Exception as exc:
            db.rollback();run=db.query(SuiteRun).filter_by(id=ident).with_for_update().first()
            if run and run.status!='workflow_cancelled':
                run.status='workflow_blocked';run.error_code=f'WORKFLOW_HTTP_{exc.status_code}' if isinstance(exc,HTTPException) else 'WORKFLOW_SCOPE_OR_PLANNING_CHANGED'
                run.result={**run.result,'issue':str(exc.detail)[:300] if isinstance(exc,HTTPException) else 'Workflow preparation stopped. Review its scope and child conversations before resuming.'}
                run.lease_until=None;db.commit()
        finally:
            if actor:actor.__dict__.pop('_suite_session_id',None)
            release_run_context(db)
    return {'processed':processed}
