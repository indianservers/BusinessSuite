"""Custom HTTPS MCP tools through existing vault/egress/journal; no local processes.

Both supported wire eras use fixed endpoints and bounded JSON responses. Every
tool call is a reviewed action, regardless of untrusted remote annotations.
"""
import json,re
from uuid import uuid4
from urllib.parse import urlsplit
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user,RequirePermission
from app.models.user import User
from app.ai_operator.suite_tools import Strict
from app.ai_operator.assistant_models import AssistantConversation
from app.ai_agents.security import company,verify,bounded_result
from app.ai_operator.service import digest

router=APIRouter(prefix='/suite/agents/mcp',tags=['Agent MCP tools'])


class Binding(Strict):
    name:str=Field(min_length=1,max_length=120)
    connection_id:int=Field(gt=0)
    endpoint:str=Field(min_length=1,max_length=2000)
    protocol:Literal['2025-11-25','2026-07-28']='2025-11-25'
    tools:list[str]=Field(default_factory=list,max_length=40)
    environment:Literal['development','staging','production']='development'
    workspace_id:int|None=Field(default=None,gt=0)


class Call(Strict):
    binding_id:int=Field(gt=0)
    tool_name:str=Field(min_length=1,max_length=100)
    arguments:dict=Field(default_factory=dict)


class Reviewed(Call):
    suite_run_id:int=Field(gt=0)
    suite_step:int=Field(ge=1,le=12)


def conn_for(db,user,data):
    RequirePermission('power_apps_view')(user);RequirePermission('power_apps_execute')(user)
    from app.apps.power_apps.integrations import vault
    conn=vault.connection(db,user,data.environment,data.connection_id)
    parts=urlsplit(data.endpoint)
    if conn.connector_id!='http' or parts.scheme!='https' or parts.username or parts.password or parts.query or parts.fragment:
        raise HTTPException(422,'Use an authorized HTTPS HTTP-vault connection, without credentials in its endpoint URL')
    if not conn.enabled or not conn.writes_enabled:raise HTTPException(403,'MCP HTTP POST requires explicit connection write opt-in')
    vault.policy_for(db,conn).resolve(data.endpoint)
    return conn


def rpc(db,user,conn,data,method,params,key,session=None,notification=False):
    from app.apps.power_apps.integrations.service import invoke
    from app.apps.power_apps.integrations.contracts import IntegrationFailure
    headers={'Accept':'application/json, text/event-stream','MCP-Protocol-Version':data.protocol}
    if session:headers['Mcp-Session-Id']=session
    if data.protocol=='2026-07-28':
        headers['Mcp-Method']=method
        if method=='tools/call':headers['Mcp-Name']=params['name']
        params={**params,'_meta':{'io.modelcontextprotocol/protocolVersion':data.protocol,'io.modelcontextprotocol/clientCapabilities':{},'io.modelcontextprotocol/clientInfo':{'name':'BusinessSuite','version':'4'}}}
    ident=digest({'key':key,'method':method})[:24]
    body={'jsonrpc':'2.0','method':method,'params':params}
    if not notification:body['id']=ident
    try:
        out=invoke(db,user,conn,'request',{'url':data.endpoint,'method':'POST','headers':headers,'body':body,'timeout_seconds':15},confirmed=True,key='mcp:'+key+':'+method)
    except IntegrationFailure as exc:raise HTTPException(409 if exc.uncertain else 422,'MCP_'+str(exc.category).upper()[:40]) from None
    if notification:return {},None
    value=out.get('body')
    if isinstance(value,str):
        messages=[]
        for block in value.replace('\r\n','\n').split('\n\n'):
            lines=[line[5:].lstrip() for line in block.splitlines() if line.startswith('data:')]
            if lines:
                try:messages.append(json.loads('\n'.join(lines)))
                except ValueError:continue
        value=next((m for m in messages if isinstance(m,dict) and m.get('id')==ident),None)
    if not isinstance(value,dict) or value.get('id')!=ident or value.get('jsonrpc')!='2.0' or 'error' in value or 'result' not in value:
        raise HTTPException(422,'MCP response was invalid, unsupported, or requested an additional interaction')
    result=value['result']
    if not isinstance(result,dict) or result.get('inputRequests'):raise HTTPException(422,'MCP interactive requests require a separate explicit user workflow')
    return result,out.get('headers',{}).get('mcp-session-id')


def session(db,user,conn,data,key):
    if data.protocol!='2025-11-25':return None
    value,ident=rpc(db,user,conn,data,'initialize',{'protocolVersion':data.protocol,'capabilities':{},'clientInfo':{'name':'BusinessSuite','version':'4'}},key)
    if value.get('protocolVersion')!=data.protocol:raise HTTPException(422,'MCP server negotiated an unsupported protocol; select a supported version')
    rpc(db,user,conn,data,'notifications/initialized',{},key,ident,True)
    return ident


def discover(db,user,data):
    conn=conn_for(db,user,data);key=str(uuid4());sid=session(db,user,conn,data,key)
    result,_=rpc(db,user,conn,data,'tools/list',{},key,sid)
    tools=result.get('tools',[])
    if not isinstance(tools,list) or len(tools)>200 or result.get('nextCursor'):raise HTTPException(422,'Select a bounded MCP tool catalog; paginated discovery is not enabled')
    from jsonschema import Draft202012Validator
    selected=[]
    for tool in tools:
        if not isinstance(tool,dict) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',str(tool.get('name',''))):raise HTTPException(422,'MCP tool name is invalid')
        schema=tool.get('inputSchema',{});safe_schema(schema)
        try:Draft202012Validator.check_schema(schema)
        except Exception:raise HTTPException(422,'MCP tool schema is invalid') from None
        selected.append({'name':tool['name'],'description':str(tool.get('description',''))[:1000],'inputSchema':schema})
    if len(json.dumps(selected))>128000:raise HTTPException(422,'MCP tool metadata exceeds the discovery budget')
    return conn,selected


def safe_schema(value,depth=0):
    if depth>20:raise HTTPException(422,'MCP schema nesting exceeds the validation budget')
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('$ref','$dynamicRef') and (not isinstance(item,str) or not item.startswith('#')):raise HTTPException(422,'Remote schema references are not permitted')
            if key in ('pattern','patternProperties'):raise HTTPException(422,'MCP regex schemas need a dedicated bounded adapter')
            safe_schema(item,depth+1)
    elif isinstance(value,list):
        for item in value:safe_schema(item,depth+1)


@router.post('/discover')
def inspect(data:Binding,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    authorize(db,user,data.workspace_id);_,tools=discover(db,user,data)
    return {'tools':tools,'policy':'Remote text and annotations never grant authority. Calls require review. Credentials, egress and ownership remain in the existing vault.'}


def owned(db,user,ident):
    row=db.query(AssistantConversation).filter_by(id=ident,user_id=user.id,organization_id=company(user),deleted_at=None).first()
    if not row or not row.references.get('mcp_binding'):raise HTTPException(404,'MCP binding not found')
    verify(db,user,row.security_context,history=True)
    from app.ai_operator.suite import authorize
    if authorize(db,user,row.workspace_id)!=row.references['scope_key']:raise HTTPException(403,'MCP workspace changed')
    conn=conn_for(db,user,Binding.model_validate(row.references['config']))
    if conn.revision!=row.references['connection_revision']:raise HTTPException(409,'MCP connection changed; rediscover and bind its tools again')
    return row


def public(row):
    return {'id':row.id,'name':row.title,'workspace_id':row.workspace_id,'environment':row.references['config']['environment'],
            'tools':row.references['tools'],'revision':row.references['revision']}


@router.post('')
def create(data:Binding,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    scope=authorize(db,user,data.workspace_id);conn,tools=discover(db,user,data)
    chosen=[t for t in tools if t['name'] in data.tools]
    if not chosen or len(chosen)!=len(set(data.tools)):raise HTTPException(422,'Explicitly select existing MCP tools before binding')
    row=AssistantConversation(user_id=user.id,organization_id=company(user),workspace_id=data.workspace_id,title=data.name,
        references={'mcp_binding':True,'scope_key':scope,'revision':1,'config':data.model_dump(),'tools':chosen,'connection_revision':conn.revision})
    db.add(row);db.flush()
    from app.ai_operator.saved_agents import audit
    audit(db,user,row,'mcp_bound');db.commit();return public(row)


@router.get('')
def listing(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    scope=authorize(db,user,workspace_id);items=[]
    for row in db.query(AssistantConversation).filter_by(user_id=user.id,organization_id=company(user),workspace_id=workspace_id,deleted_at=None).filter(AssistantConversation.references['mcp_binding'].as_boolean()==True,AssistantConversation.references['scope_key'].as_string()==scope).limit(30):
        try:items.append(public(owned(db,user,row.id)))
        except HTTPException:continue
    return {'items':items}


def preflight(db,user,run,step):
    from app.ai_operator.saved_agents import owned as agent_owned,public as agent_public
    agent=agent_public(agent_owned(db,user,run.result['request'].get('agent_id')))
    data=Call.model_validate(step.payload)
    if data.binding_id not in agent['mcp_ids']:raise HTTPException(403,'MCP tool is outside this agent scope')
    row=owned(db,user,data.binding_id)
    tool=next((t for t in row.references['tools'] if t['name']==data.tool_name),None)
    if not tool:raise HTTPException(403,'MCP tool was not explicitly enabled')
    if set(re.split(r'[_ .:-]+',data.tool_name.casefold())) & {'delete','purge','drop','execute','code','sql','shell','command','grant','permissions','payment','transfer','refund','invite'}:raise HTTPException(403,'MCP tool is outside the agent safety boundary')
    from jsonschema import Draft202012Validator
    try:Draft202012Validator(tool['inputSchema']).validate(data.arguments)
    except Exception:raise HTTPException(422,'MCP arguments do not match the bound tool schema') from None
    return row


@router.post('/execute-approved')
def execute(data:Reviewed,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.agent_connectors import reviewed_run
    run,step=reviewed_run(db,user,request,data,Call,'mcp_action')
    row=preflight(db,user,run,step)
    if (run.snapshots or {}).get('mcp',{}).get(str(data.suite_step))!={'id':row.id,'revision':row.references['revision']}:
        raise HTTPException(409,'MCP tool binding changed after review')
    config=Binding.model_validate(row.references['config']);conn=conn_for(db,user,config)
    key=f'agent-{run.id}-{data.suite_step}';sid=session(db,user,conn,config,key)
    output,_=rpc(db,user,conn,config,'tools/call',{'name':data.tool_name,'arguments':data.arguments},key,sid)
    if output.get('isError'):raise HTTPException(422,'MCP tool reported a failure; review its operation before retrying')
    from app.apps.power_apps.integrations.transport import scrub
    return {'binding_id':row.id,'tool_name':data.tool_name,'output':bounded_result(db,user,scrub(output))}
