"""Private multi-agent DAGs on SuiteRun checkpoints and canonical reviewed runs.

Starting a workflow grants preparation, not approval of future business actions.
Each agent retains its own tool/module restrictions and a persistent conversation.
"""
import asyncio,re
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
    parallel_limit:int=Field(default=2,ge=1,le=3)

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
        'planning_wave':data.get('planning_wave'),
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
        if 'parallel_limit' not in data.model_fields_set and 'parallel_limit' not in run.result['spec']:
            hashed=digest({'spec':{k:v for k,v in spec.items() if k!='parallel_limit'},'agents':agents,'branch_id':branch.branch_id})
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


@router.get('/{ident}/results')
def results(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    """Fresh private aggregation, never a cached claim of completed work."""
    run=owned(db,user,ident);items=[]
    from app.ai_operator.suite_conversations import owned as chat_owned
    from app.ai_agents.security import limits
    for node,spec in zip(run.result['nodes'],run.result['spec']['nodes']):
        item={'step':node['step'],'agent_name':run.result['agents'][str(spec['agent_id'])]['name'],
            'status':'not_started','summary':'No agent run has been prepared.','citations':[],'receipts':[]}
        if node.get('run_id'):
            chat_owned(db,user,node['conversation_id'])
            child=occurrence_run(db,user,node,spec['agent_id'])
            receipts=[{k:v for k,v in receipt.items() if k in {'step','tool','status','record_id','artifact_id','artifact_revision'}} for receipt in child.receipts or []]
            item.update(status=child.status,run_id=child.id,conversation_id=node['conversation_id'],
                summary=(child.plan or {}).get('summary','No answer was produced.')[:900],
                citations=(child.result or {}).get('citations',[])[:8],receipts=receipts[:12])
            if child.status=='succeeded':item['summary']=f'{sum(r.get("status")=="succeeded" for r in receipts)} action receipts confirmed. Open the conversation for the reviewed changes.'
        items.append(item)
    completed=sum(i['status'] in ('answered','succeeded') for i in items)
    summary=f'{completed}/{len(items)} specialist steps completed. '
    if run.status=='workflow_cancelled':summary+='Workflow stopped; completed receipts remain recorded.'
    elif completed<len(items):summary+='The remaining steps are pending, need review or require recovery.'
    else:summary+='Read the combined answers and confirmed receipts below; source coverage remains that of each specialist.'
    response={'workflow_id':run.id,'name':run.command,'status':run.status.removeprefix('workflow_'),'complete':completed==len(items) and run.status=='workflow_succeeded',
        'summary':summary,'items':items,'aggregation':'Server-authorized specialist answers and confirmed receipts; no additional model synthesis.'}
    # Keep every step and status, reducing detail instead of silently omitting a
    # specialist from the combined result when a disclosure budget is small.
    import json
    cap=limits(db,company(user))['max_result_bytes']
    if len(json.dumps(response,default=str).encode())>cap:
        response['disclosure_limited']=True
        for item in items:item.update(summary=item['summary'][:300],citations=item['citations'][:2],receipts=item['receipts'][:2])
    if len(json.dumps(response,default=str).encode())>cap:raise HTTPException(422,'Combined results exceed the disclosure limit; open the individual specialist conversations')
    return response


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
        try:
            update=await stop_child(request.app,request.headers.get('authorization',''),db,user,node,spec)
            if update:
                updates[node['step']]=update
                if update['run_status'] not in TERMINAL:errors.append(node['step'])
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


def discover_child(db,user,node,spec):
    if not node.get('request_key'):return None
    from app.ai_operator.suite import owned as run_owned
    value=db.query(SuiteRun.id).filter_by(user_id=user.id,request_key=node['request_key']).first()
    if not value:return None
    child=run_owned(db,user,value[0]);request=(child.result or {}).get('request',{})
    if request.get('conversation_id')!=node.get('conversation_id') or request.get('agent_id')!=spec['agent_id']:raise HTTPException(409,'Recovered child scope changed')
    return child


async def stop_child(app,authorization,db,user,node,spec):
    from app.ai_operator.suite import api_call
    if not node.get('run_id'):
        found=discover_child(db,user,node,spec)
        if not found:return None
        node={**node,'run_id':found.id}
    child=occurrence_run(db,user,node,spec['agent_id'])
    status=child.status
    if status not in TERMINAL:
        result=await api_call(app,authorization,'POST',f'/ai-operator/suite/runs/{child.id}/cancel')
        status=result['status']
    return {'run_id':child.id,'run_status':status,'state':'done' if status in ('answered','succeeded') else 'stopped' if status in TERMINAL else 'stopping'}


def handoff_context(db,user,data,parent=None):
    """Approved dependency answers are data, never agent instructions or grants."""
    if not data.workflow_id:return []
    flow=owned(db,user,data.workflow_id);grant(db,user,flow)
    if flow.status in ('workflow_preview','workflow_succeeded','workflow_cancelled'):raise HTTPException(409,'Workflow is not preparing this step')
    if not 1<=data.workflow_step<=len(flow.result['spec']['nodes']):raise HTTPException(404,'Workflow step not found')
    node=flow.result['nodes'][data.workflow_step-1];spec=flow.result['spec']['nodes'][data.workflow_step-1]
    if node.get('conversation_id')!=data.conversation_id or spec['agent_id']!=data.agent_id or flow.workspace_id!=data.workspace_id:
        raise HTTPException(403,'Workflow step does not match this agent conversation')
    branch=db.info.get('branch_context')
    if getattr(branch,'branch_id',None)!=flow.snapshots['branch_id']:raise HTTPException(403,'Workflow branch changed')
    prior=(parent.result or {}).get('request',{}) if parent else {}
    correction=bool(parent and parent.status in ('needs_clarification','awaiting_approval','failed') and prior.get('workflow_id')==flow.id and prior.get('workflow_step')==data.workflow_step)
    if not correction and data.text!=instructions(db,user,spec,flow.result['nodes']):raise HTTPException(409,'Workflow instructions changed; use its existing conversation review')
    from app.ai_operator.suite_conversations import owned as chat_owned
    packets=[]
    for position in spec['depends_on']:
        source_node=flow.result['nodes'][position-1];source_spec=flow.result['spec']['nodes'][position-1]
        if source_node['state']!='done' or not source_node.get('run_id'):raise HTTPException(409,'Workflow dependency is not complete')
        chat_owned(db,user,source_node['conversation_id'])
        child=occurrence_run(db,user,source_node,source_spec['agent_id'])
        if child.status not in ('answered','succeeded'):raise HTTPException(409,'Workflow dependency needs review')
        from app.ai_operator.shared_artifact_questions import revalidate,lineage
        shared_sources=lineage((child.result or {}).get('citations',[]))
        revalidate(db,user,shared_sources)
        from app.ai_operator import event_messages
        message_sources=event_messages.lineage((child.result or {}).get('citations',[]))
        event_messages.revalidate(db,user,message_sources)
        prefix=f'w{flow.id}:step{position}:'
        source={'id':prefix+'answer','kind':'agent_answer','tool':'agent.workflow_answer','record_id':child.id,
            'label':flow.result['agents'][str(source_spec['agent_id'])]['name']+' answer',
            'href':f'/?bot_conversation={source_node["conversation_id"]}'+(f'&workspace={flow.workspace_id}' if flow.workspace_id else ''),
            'retrieved_at':now().isoformat(),'shared_sources':shared_sources,'event_message_sources':message_sources}
        citations=[{**c,'id':prefix+c['id']} for c in (child.result or {}).get('citations',[])[:5]]
        receipts=[{k:v for k,v in r.items() if k in {'step','tool','status','record_id','artifact_id','artifact_revision'}} for r in child.receipts or [] if r.get('status')=='succeeded'][:6]
        answer=(child.plan or {}).get('summary','')[:1000]
        if child.status=='succeeded':answer=f'{len(receipts)} confirmed action receipts in this bounded handoff. Original reviewed proposal: '+answer[:800]
        packets.append({'step':position,'run_id':child.id,'agent_name':flow.result['agents'][str(source_spec['agent_id'])]['name'],
            'status':child.status,'answer':answer,'receipts':receipts,
            'sources':[source,*citations],'trust':'Prior specialist assertion, not independently verified fact. Receipts confirm only the listed actions. Re-read current business facts through authorized tools when required.'})
    from app.ai_agents.security import bounded_result
    bounded=bounded_result(db,user,packets)
    if isinstance(bounded,dict) and bounded.get('truncated'):raise HTTPException(422,'Dependency results exceed the disclosure budget; narrow this workflow')
    return bounded


def local_handoff_answer(packets):
    lines=['Specialist dependency answers (bounded, not independently verified facts):'];ids=[]
    for packet in packets:
        line=f"Step {packet['step']} · {packet['agent_name']}: {packet['answer'][:450]}"
        if sum(map(len,lines))+len(line)>1900:break
        lines.append(line);ids.append(packet['sources'][0]['id'])
    return {'summary':'\n'.join(lines),'steps':[],'source_ids':ids}


async def dispatch(db,app,instant=None,limit=5,workflow_id=None):
    from app.access.service import activate_run_context,release_run_context,background_scope
    from app.ai_operator import suite_conversations as chats
    instant=instant or now();processed=0
    candidates=db.query(SuiteRun.id).filter(SuiteRun.status.in_(['workflow_active','workflow_running','workflow_waiting','workflow_paused']),
        or_(SuiteRun.lease_until==None,SuiteRun.lease_until<=instant))
    if workflow_id is not None:candidates=candidates.filter(SuiteRun.id==workflow_id)
    ids=candidates.order_by(SuiteRun.id).limit(min(limit,20)).all()
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
                ready=[n for n,s in zip(nodes,specs) if n['state'] in ('pending','planning') and all(nodes[d-1]['state']=='done' for d in s['depends_on'])][:data['spec'].get('parallel_limit',1)]
                if not ready:
                    run.status='workflow_waiting';run.lease_until=instant+timedelta(seconds=10);run.result={**data,'nodes':nodes};db.commit();continue
                commands=[]
                for target in ready:
                    index=target['step'];spec=specs[index-1];frozen=data['agents'][str(spec['agent_id'])]
                    prompt=instructions(db,actor,spec,nodes)
                    if not target.get('conversation_id'):
                        chat=chats.create(db,actor,chats.ConversationInput(title=f"{run.command}: {index}. {frozen['name']}"[:160],workspace_id=run.workspace_id),commit=False)
                        target.update(conversation_id=chat['id'],request_key=str(uuid5(NAMESPACE_URL,f'agent-workflow:{run.id}:{index}')))
                    target['state']='planning';target.pop('planning_error',None)
                    commands.append({'request_key':target['request_key'],'text':prompt,'agent_id':spec['agent_id'],'provider':'preferred',
                        'timezone':data['spec']['timezone'],'workspace_id':run.workspace_id,'project_id':frozen['project_id'],'conversation_id':target['conversation_id'],
                        'workflow_id':run.id,'workflow_step':index})
                run.result={**data,'nodes':nodes,'planning_wave':{'steps':[n['step'] for n in ready],'concurrency':len(ready)}};db.commit()
                # No worker Session or ORM instances are used by concurrent
                # calls. Each canonical request obtains its own request session.
                user_id,session_id,company_id,branch_id=actor.id,run.session_id,company(actor),run.snapshots['branch_id']
                prepared=await asyncio.gather(*(prepare_agent(app,user_id,session_id,company_id,branch_id,c) for c in commands),return_exceptions=True)
                db.expire_all();run=db.query(SuiteRun).filter_by(id=ident).with_for_update().one()
                if run.status!='workflow_cancelled' and (run.status!='workflow_running' or not run.lease_until or utc(run.lease_until)!=utc(claim_until)):
                    db.rollback();continue  # A newer worker owns this checkpoint.
                nodes=[dict(n) for n in run.result['nodes']];failed=False
                for command,response in zip(commands,prepared):
                    target=nodes[command['workflow_step']-1]
                    if isinstance(response,BaseException):
                        if run.status=='workflow_cancelled':
                            recovered=discover_child(db,actor,target,specs[command['workflow_step']-1])
                            if recovered:response={'id':recovered.id,'status':recovered.status}
                    if isinstance(response,BaseException):
                        failed=True;target['planning_error']=f'PLANNING_HTTP_{response.status_code}' if isinstance(response,HTTPException) else 'PLANNING_RESPONSE_UNAVAILABLE'
                        continue  # Recovery reuses this exact conversation/key.
                    target.update(run_id=response['id'],run_status=response['status'],state='running')
                    if run.status=='workflow_cancelled':
                        from app.core.security import create_access_token
                        from app.ai_operator.suite import api_call
                        token=create_access_token(str(user_id),session_id=session_id,expires_delta=timedelta(minutes=1))
                        try:
                            update=await stop_child(app,'Bearer '+token,db,actor,target,specs[command['workflow_step']-1])
                            if update:
                                target.update(update)
                                if update['run_status'] not in TERMINAL:
                                    run.result={**run.result,'cancel_errors':sorted(set([*run.result.get('cancel_errors',[]),target['step']]))}
                        except HTTPException:
                            run.result={**run.result,'cancel_errors':sorted(set([*run.result.get('cancel_errors',[]),target['step']]))}
                            run.error_code='CHILD_CANCELLATION_NEEDS_REVIEW'
                run.result={**run.result,'nodes':nodes}
                if run.status!='workflow_cancelled':
                    run.status='workflow_blocked' if failed else 'workflow_active';run.lease_until=None
                    run.error_code='WORKFLOW_PLANNING_RESPONSE_UNAVAILABLE' if failed else None
                    if failed:run.result={**run.result,'issue':'A planning response was unavailable. Completed child plans are retained. Resume to recover the same request keys; no action was approved.'}
                db.commit();processed+=1

        except Exception as exc:
            db.rollback();run=db.query(SuiteRun).filter_by(id=ident).with_for_update().first()
            if run and run.status=='workflow_running' and run.lease_until and utc(run.lease_until)==utc(claim_until):
                run.status='workflow_blocked';run.error_code=f'WORKFLOW_HTTP_{exc.status_code}' if isinstance(exc,HTTPException) else 'WORKFLOW_SCOPE_OR_PLANNING_CHANGED'
                run.result={**run.result,'issue':str(exc.detail)[:300] if isinstance(exc,HTTPException) else 'Workflow preparation stopped. Review its scope and child conversations before resuming.'}
                run.lease_until=None;db.commit()
        finally:
            if actor:actor.__dict__.pop('_suite_session_id',None)
            release_run_context(db)
    return {'processed':processed}
