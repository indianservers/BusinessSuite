"""Private conversational workflow design; dispatch stays in agent_workflows.

Model output selects existing agents only. It cannot start workflows, approve
children, create connections or change the selected agents' capabilities.
"""
import json,re
from datetime import datetime,timezone
from uuid import UUID,uuid5,NAMESPACE_URL
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_operator.assistant_models import AssistantConversation,AssistantMessage
from app.ai_operator.suite_tools import Strict
from app.ai_operator.intelligence import Provider
from app.ai_operator.agent_workflows import Workflow,Node,Confirmation
from app.ai_operator.agent_schedules import snapshot
from app.ai_operator.service import digest
from app.ai_agents.security import company,verify,seal

router=APIRouter(prefix='/suite/agents/coordinator',tags=['Conversational specialist coordinator'])


class Draft(Strict):
    name:str=Field(min_length=1,max_length=120)
    nodes:list[Node]=Field(default_factory=list,max_length=8)
    question:str|None=Field(default=None,max_length=1200)


class Message(Strict):
    request_key:UUID
    text:str=Field(min_length=1,max_length=4000)
    context_id:int|None=Field(default=None,gt=0)
    revision:int|None=Field(default=None,ge=1)
    workspace_id:int|None=Field(default=None,gt=0)
    provider:Provider='preferred'
    timezone:str='Asia/Kolkata'


def owned(db,user,ident,lock=False):
    from app.ai_operator.suite import authorize
    q=db.query(AssistantConversation).filter_by(id=ident,user_id=user.id,organization_id=company(user),deleted_at=None)
    row=(q.with_for_update().populate_existing() if lock else q).first()
    if not row or not row.references.get('agent_coordinator'):raise HTTPException(404,'Coordinator design not found')
    verify(db,user,row.security_context,history=True)
    if authorize(db,user,row.workspace_id)!=row.references['scope_key']:raise HTTPException(403,'Coordinator scope changed')
    return row


def public(row):
    refs=row.references
    return {'context_id':row.id,'workspace_id':row.workspace_id,'revision':refs['revision'],
        'draft':refs['draft'],'preview_hash':refs['preview_hash'],'agents':refs['agents'],
        'provider':refs['provider'],'workflow_id':refs.get('workflow_id'),
        'execution':'A design only. Creating the workflow prepares an inactive preview; starting and each proposed action require separate review.'}


def local_draft(text,previous,agents):
    # Precise named-agent composition, not an invented general reasoning model.
    if previous and (rename:=re.fullmatch(r'\s*(?:call|name) it\s+(.{1,120})\s*',text,re.I)):
        return Draft.model_validate({**previous,'name':rename[1].strip()})
    parts=re.split(r'(\s+then\s+|\s*;\s*)',text,flags=re.I);clauses=parts[::2]
    if len(clauses)>8:return Draft(name='Specialist workflow',question='Use at most eight specialist steps in one workflow.')
    nodes=[]
    for index,clause in enumerate(clauses):
        matched=[a for a in agents if re.search(r'(?<!\w)'+re.escape(a['name'])+r'(?!\w)',clause,re.I)]
        if len(matched)!=1:return Draft(name='Specialist workflow',question='Name one saved agent per step, separated by “then” or semicolons. Example: “Project Coordinator: review delivery risks; HR Assistant: review team availability”. Semicolons create independent steps; “then” adds dependencies. Choose connected intelligence for broader planning.')
        prefix=re.match(r'^\s*'+re.escape(matched[0]['name'])+r'\s*:\s*(.+)$',clause,re.I|re.S)
        instruction=prefix[1].strip() if prefix else clause.strip()
        nodes.append(Node(agent_id=matched[0]['id'],instructions=instruction,depends_on=[len(nodes)] if index and parts[index*2-1].strip().lower()=='then' else []))
    return Draft(name='Specialist workflow',nodes=nodes)


@router.get('')
def listing(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    scope=authorize(db,user,workspace_id)
    rows=db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=workspace_id,deleted_at=None).filter(
        AssistantConversation.references['agent_coordinator'].as_boolean()==True,AssistantConversation.references['scope_key'].as_string()==scope).order_by(AssistantConversation.id.desc()).limit(30)
    return {'items':[public(owned(db,user,r.id)) for r in rows]}


@router.get('/{ident}')
def get(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident);messages=[]
    for m in db.query(AssistantMessage).filter_by(conversation_id=ident,tool='agent.coordinator').order_by(AssistantMessage.id).limit(20):
        verify(db,user,m.security_context,history=True);messages.append({'text':m.prompt,'draft':m.proposal})
    return {**public(row),'messages':messages}


@router.delete('/{ident}')
def archive(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=owned(db,user,ident,True);row.deleted_at=datetime.now(timezone.utc);db.commit();return {'archived':True}


@router.post('/messages')
def message(data:Message,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize,_require_ai_rate_limit
    from app.ai_operator.suite_memory import MemoryText
    from app.ai_operator.saved_agents import listing as profiles
    scope=authorize(db,user,data.workspace_id)
    try:MemoryText.safe_text(data.text)
    except ValueError:raise HTTPException(422,'Describe the work without credentials or sensitive personal records') from None
    if not data.context_id:
        db.query(User.id).filter_by(id=user.id).with_for_update().one()
        prior=db.query(AssistantConversation.id).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(
            AssistantConversation.references['agent_coordinator'].as_boolean()==True,AssistantConversation.references['initial_request_key'].as_string()==str(data.request_key)).first()
    else:prior=None
    row=owned(db,user,data.context_id or (prior[0] if prior else None),True) if data.context_id or prior else None
    hashed=digest(data.model_dump(mode='json',exclude={'request_key'}))
    if row:
        if row.workspace_id!=data.workspace_id:raise HTTPException(409,'Continue in the original workspace')
        previous=db.query(AssistantMessage).filter_by(conversation_id=row.id,request_key=str(data.request_key),tool='agent.coordinator').first()
        if previous:
            if previous.request_hash!=hashed:raise HTTPException(409,'Request key belongs to another coordinator message')
            verify(db,user,previous.security_context,history=True);return previous.result
        if row.references.get('workflow_id'):raise HTTPException(409,'This design was applied; start a new design')
        if data.revision!=row.references['revision']:raise HTTPException(409,'Coordinator changed; reload before continuing')
        if data.revision>=20:raise HTTPException(422,'Start a new coordinator design after twenty follow-ups')
    _require_ai_rate_limit(db,request,user,bucket='agent_coordinator')
    agents=profiles(data.workspace_id,db,user)['items'][:30]
    provider=data.provider;config=None
    if provider=='preferred':
        from app.ai_operator.intelligence import select_default
        provider,config=select_default(db,user,scope,None,data.workspace_id)
    elif provider!='local':
        from app.ai_operator.provider_scope import resolve_provider
        config=resolve_provider(db,user,provider,data.workspace_id)
    prior_draft=row.references['draft'] if row else None
    if not agents:draft=Draft(name='Specialist workflow',question='Save the specialist agents in this workspace first, then describe the jobs to delegate.')
    elif provider=='local':draft=local_draft(data.text,prior_draft,agents)
    else:
        from app.ai_operator.providers import generate_json
        from app.ai_agents.services.advanced_security import AiDataRedactionService
        if not config:raise HTTPException(409,'Coordinator provider is unavailable')
        available=[{k:a[k] for k in ('id','name','modules','tools','project_id')}|{'instructions':a['instructions'][:500]} for a in agents]
        prompt=AiDataRedactionService().redact_text(json.dumps({'request':data.text,'previous_draft':prior_draft,'agents':available,
            'rules':'Select only supplied existing agents. Do not invent agents or record IDs. Design up to eight steps using each selected agent capabilities. Independent reviews can have depends_on=[]; ordered steps depend on earlier step numbers. Preserve unchanged prior choices. Ask a question and return no nodes when scope or required specialist capability is missing. Instructions are executable requests only after native review, never completion claims. No activation, approvals, connector setup or permission changes. Never embed credentials. Approved output IDs may use {{step.1.record_id}} or {{step.1.artifact_id}} with that dependency. Results are bounded; do not promise all-company coverage.'}))
        draft=Draft.model_validate(generate_json(db,user,config,prompt=prompt,schema=Draft.model_json_schema(),purpose='agent_coordinator',output_type=Draft,usage_scope=scope,module='CROSS'))
    if draft.question:draft.nodes=[]
    elif not draft.nodes:raise HTTPException(422,'Coordinator must prepare steps or ask a follow-up')
    # Provider telemetry commits on the same session. Reacquire the design lock
    # after inference so concurrent follow-ups cannot overwrite a newer revision.
    if row is not None:
        row=owned(db,user,row.id,True)
        if row.references.get('workflow_id') or data.revision!=row.references['revision']:raise HTTPException(409,'Coordinator changed while planning; reload the latest design')
    else:
        db.query(User.id).filter_by(id=user.id).with_for_update().one()
        existing=db.query(AssistantConversation.id).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(
            AssistantConversation.references['agent_coordinator'].as_boolean()==True,AssistantConversation.references['initial_request_key'].as_string()==str(data.request_key)).first()
        if existing:
            prior_row=owned(db,user,existing[0],True)
            prior_message=db.query(AssistantMessage).filter_by(conversation_id=prior_row.id,request_key=str(data.request_key),tool='agent.coordinator').first()
            if not prior_message or prior_message.request_hash!=hashed:raise HTTPException(409,'Concurrent coordinator request conflicts with this message')
            verify(db,user,prior_message.security_context,history=True);return prior_message.result
    ids={a['id'] for a in agents}
    if any(n.agent_id not in ids for n in draft.nodes):raise HTTPException(422,'Coordinator selected an unavailable specialist')
    branch=db.info.get('branch_context')
    if not getattr(branch,'branch_id',None):raise HTTPException(422,'Select a concrete branch')
    frozen={str(n.agent_id):snapshot(db,user,n.agent_id) for n in draft.nodes}
    if any(frozen[str(a['id'])]['revision']!=a['revision'] for a in agents if str(a['id']) in frozen):raise HTTPException(409,'A specialist changed while planning; prepare the design again')
    spec=None
    if draft.nodes:
        try:spec=Workflow(request_key=data.request_key,name=draft.name,workspace_id=data.workspace_id,nodes=draft.nodes,timezone=data.timezone).model_dump(mode='json',exclude={'request_key'})
        except ValueError:raise HTTPException(422,'Coordinator proposed an invalid dependency graph or scope') from None
    if row is None:
        if db.query(AssistantConversation.id).filter_by(user_id=user.id,organization_id=company(user),deleted_at=None).filter(AssistantConversation.references['agent_coordinator'].as_boolean()==True).count()>=50:raise HTTPException(422,'Archive unused coordinator designs first')
        row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=data.workspace_id,title='Coordinator: '+draft.name,
            references={'agent_coordinator':True,'scope_key':scope,'revision':0,'initial_request_key':str(data.request_key)})
        db.add(row);db.flush()
    revision=row.references['revision']+1
    value={'spec':spec,'agents':frozen,'revision':revision,'branch_id':branch.branch_id}
    hashed_preview=digest(value)
    row.references={**row.references,**value,'draft':draft.model_dump(mode='json'),'provider':provider,'preview_hash':hashed_preview,'design_grant':seal(db,user,hashed_preview)}
    result=public(row)
    db.add(AssistantMessage(conversation_id=row.id,request_key=str(data.request_key),request_hash=hashed,prompt=data.text,tool='agent.coordinator',arguments={},proposal=draft.model_dump(mode='json'),result=result,status='answered'))
    db.commit();return result


@router.post('/{ident}/apply')
def apply(ident:int,data:Confirmation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator import agent_workflows as flows
    row=owned(db,user,ident,True);refs=row.references
    if data.preview_hash!=refs['preview_hash'] or refs['draft'].get('question') or not refs.get('spec'):raise HTTPException(409,'Review the latest complete coordinator design')
    if digest({k:refs[k] for k in ('spec','agents','revision','branch_id')})!=data.preview_hash:raise HTTPException(409,'Coordinator design changed')
    verify(db,user,refs['design_grant'],payload=data.preview_hash,confirmation=not bool(refs.get('workflow_id')))
    branch=db.info.get('branch_context')
    if getattr(branch,'branch_id',None)!=refs['branch_id']:raise HTTPException(409,'Review in the original branch')
    if any(snapshot(db,user,int(i))!=frozen for i,frozen in refs['agents'].items()):raise HTTPException(409,'A specialist changed; prepare a new coordinator revision')
    key=uuid5(NAMESPACE_URL,f'agent-coordinator:{row.id}:{data.preview_hash}')
    flow=flows.preview(Workflow(request_key=key,**refs['spec']),db,user)
    row.references={**row.references,'workflow_id':flow['id']};db.commit()
    return {**public(row),'workflow_preview':flow}
