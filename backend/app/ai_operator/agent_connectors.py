"""Scoped agent bridge to the existing connector vault and operation journal."""
import json
import re
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user,RequirePermission
from app.models.user import User
from app.ai_operator.suite_tools import Strict
from app.ai_operator.saved_agents import owned,public
from app.ai_operator.service import digest

router=APIRouter(prefix='/suite/agents/connectors',tags=['Agent connectors'])


class Action(Strict):
    connection_id:int=Field(gt=0)
    action_id:str=Field(min_length=1,max_length=100)
    input:dict=Field(default_factory=dict)


class Reviewed(Action):
    suite_run_id:int=Field(gt=0)
    suite_step:int=Field(ge=1,le=12)


def connection(db,user,agent_id,connection_id):
    RequirePermission('power_apps_view')(user);RequirePermission('power_apps_execute')(user)
    profile=public(owned(db,user,agent_id))
    if connection_id not in profile['connection_ids']:raise HTTPException(403,'Connector is outside this agent scope')
    from app.apps.power_apps.integrations.vault import connection as resolve
    return resolve(db,user,profile['environment'],connection_id)


@router.get('')
def catalog(response:Response,environment:str='development',db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    RequirePermission('power_apps_view')(user)
    from app.apps.power_apps.integrations.api import connections
    from app.apps.power_apps.integrations.registry import catalog as registry
    rows=connections(environment,db,user)['items']
    from app.ai_operator.agent_connector_status import enrich
    from app.ai_agents.security import company
    safe=enrich(db,user,rows,company(user),environment)
    response.headers['Cache-Control']='no-store'
    return {'connections':safe,'catalog':registry(),'setup_url':'/power-apps/integrations',
        'note':'Available adapters are not connected accounts. OAuth, scopes, credentials, connection health and explicit write opt-in remain in the existing vault.'}


@router.get('/read')
def read(agent_id:int,connection_id:int,action_id:str,input_json:str='{}',db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    conn=connection(db,user,agent_id,connection_id)
    try:
        if len(input_json)>8000:raise ValueError()
        values=json.loads(input_json)
        if not isinstance(values,dict):raise ValueError()
    except (ValueError,TypeError):raise HTTPException(422,'Connector input must be a bounded JSON object') from None
    return invoke(db,user,conn,action_id,values,False,'agent-read:'+digest({'user':user.id,'agent':agent_id,'action':action_id,'input':values}))


def invoke(db,user,conn,action_id,values,confirmed,key):
    from app.apps.power_apps.integrations import service
    from app.apps.power_apps.integrations.contracts import IntegrationFailure
    from app.ai_agents.security import bounded_result
    try:
        permitted(conn,action_id)
        _,_,mutates=service.typed_action(conn,action_id,values,confirmed)
        if not confirmed and mutates:raise HTTPException(403,'Read tools cannot invoke external writes')
        output=service.invoke(db,user,conn,action_id,values,confirmed=confirmed,key=key)
        from app.apps.power_apps.integrations.transport import scrub
        return {'output':bounded_result(db,user,scrub(output)),'connection_id':conn.id,'action_id':action_id}
    except IntegrationFailure as exc:
        # An unknown write outcome must reach suite reconciliation, never replay.
        raise HTTPException(409 if exc.uncertain else 422,'CONNECTOR_'+str(exc.category).upper()[:40]) from None


def permitted(conn,action_id):
    from app.apps.power_apps.integrations.registry import REGISTRY
    manifest=REGISTRY.get(conn.connector_id)
    if not manifest or manifest.category in {'Databases','Webhooks and APIs','AI Services','Payments'}:
        raise HTTPException(403,'This connector requires its native controlled workflow; generic agent execution is unavailable')
    if set(re.split(r'[_ .-]+',action_id.casefold())) & {'delete','purge','drop','permissions','permission','grant','invite','payment','charge','transfer','refund','sql','execute'}:
        raise HTTPException(403,'This connector action is outside the agent safety boundary')


def preflight(db,user,run,step):
    agent_id=run.result['request'].get('agent_id')
    if not agent_id:raise HTTPException(403,'Select an agent with explicit connector bindings')
    conn=connection(db,user,agent_id,step.payload['connection_id']);permitted(conn,step.payload['action_id'])
    from app.apps.power_apps.integrations.service import typed_action
    from app.apps.power_apps.integrations.contracts import IntegrationFailure
    try:typed_action(conn,step.payload['action_id'],step.payload.get('input',{}),True)
    except IntegrationFailure as exc:raise HTTPException(403 if exc.category in ('permission','scope','disabled') else 422,'CONNECTOR_'+str(exc.category).upper()[:40]) from None
    return {'id':conn.id,'revision':conn.revision,'connector_id':conn.connector_id}


def reviewed_run(db,user,request,data,model,suffix):
    from app.core.security import verify_access_token
    from app.ai_operator.suite import owned as run_owned,Plan
    from app.ai_operator.saved_agents import enforce
    from app.ai_agents.models import AiActionApproval
    from app.ai_agents.security import verify
    claims=verify_access_token(request.headers.get('authorization','').partition(' ')[2]) or {}
    if not claims.get('ai_origin'):raise HTTPException(403,'Connector writes require the reviewed agent executor')
    run=run_owned(db,user,data.suite_run_id,True)
    approval=db.get(AiActionApproval,run.approval_id) if run.approval_id else None
    if run.status!='executing' or run.active_step!=data.suite_step or not approval or approval.status!='approved':raise HTTPException(409,'Connector action is not actively approved')
    verify(db,user,approval.security_context,payload=approval.proposed_action_json,history=True)
    if approval.proposed_action_json['input'].get('plan_hash')!=run.plan_hash or digest(run.plan)!=run.plan_hash:raise HTTPException(409,'Connector approval changed')
    step=Plan.model_validate(run.plan).steps[data.suite_step-1];enforce(db,user,run,[step])
    if step.tool not in {f'{m}.{suffix}' for m in ('crm','pms','hrms')}:raise HTTPException(403,'Incorrect connector tool')
    if digest(model.model_validate(step.payload).model_dump())!=digest(data.model_dump(exclude={'suite_run_id','suite_step'})):raise HTTPException(409,'Connector input changed after review')
    return run,step


@router.post('/execute-approved')
def execute(data:Reviewed,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    run,_=reviewed_run(db,user,request,data,Action,'connector_action')
    agent_id=run.result['request'].get('agent_id')
    if not agent_id:raise HTTPException(403,'Select an agent with explicit connector bindings')
    conn=connection(db,user,agent_id,data.connection_id)
    sealed=(run.snapshots or {}).get('connectors',{}).get(str(data.suite_step))
    if sealed!={'id':conn.id,'revision':conn.revision,'connector_id':conn.connector_id}:raise HTTPException(409,'Connector configuration changed since review')
    return invoke(db,user,conn,data.action_id,data.input,True,f'agent:{run.id}:{data.suite_step}')
