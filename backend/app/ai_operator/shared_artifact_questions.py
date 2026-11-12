"""Conversation reads of approved publications, never publisher private history."""
import re
from types import SimpleNamespace
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import Field,StrictInt,field_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_operator import artifact_questions as questions,artifact_shares as shares
from app.ai_operator.suite_tools import Strict

router=APIRouter(prefix='/suite/artifact-shares',tags=['Shared artifact questions'])


class Read(Strict):
    share_id:StrictInt=Field(gt=0)
    edition:StrictInt|None=Field(default=None,ge=1)
    position:StrictInt=Field(default=1,ge=1,le=6)
    category_query:str=Field(default='',max_length=100)

    @field_validator('category_query')
    @classmethod
    def valid_query(cls,value):return questions.PanelRead.safe_category(value)


def citation(row,source,position=None):
    ident=f'shared-artifact:{row.id}:e{row.version}'+(f':p{position}' if position else '')
    return {'id':ident,'tool':'suite.shared_artifact','record_id':row.id,'share_id':row.id,'share_edition':row.version,'panel_position':position,
        'label':f"{source['body']['title']} (shared edition {row.version}"+(f', panel {position}' if position else '')+')',
        'href':f'#bot-shared-artifact-{row.id}','coverage':'Approved shared snapshot; underlying assertions are not verified live ERP facts.'}


@router.get('/read/current')
def read_current(request:Request,response:Response,share_id:int,position:int=1,edition:int|None=None,category_query:str='',module:shares.artifacts.Module='CRM',
    workspace_id:int|None=None,agent_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_agents.api import _require_ai_rate_limit
    try:query=Read(share_id=share_id,position=position,edition=edition,category_query=category_query)
    except ValueError:raise HTTPException(422,'Choose a valid shared publication, edition, panel and category filter') from None
    row=shares.entry(db,user,query.share_id);definition=shares.available(db,user,row,query.edition)
    if row.values_json['workspace_id']!=workspace_id or definition['root']['module']!=module:raise HTTPException(403,'Read the publication in its original module/workspace')
    dashboard=definition['root']['body']['kind']=='dashboard'
    if dashboard:
        if position>len(definition['sources']):raise HTTPException(404,'Shared panel not found')
        source=definition['sources'][position-1];label=definition['root']['body']['panels'][position-1]['label']
    else:
        if position!=1:raise HTTPException(404,'This shared artifact has one snapshot')
        source=definition['root'];label='Published snapshot'
    if agent_id:
        from app.ai_operator import saved_agents
        actor=saved_agents.owned(db,user,agent_id);saved_agents.runtime_access(db,user,actor)
        profile=saved_agents.public(actor)
        if actor.workspace_id!=workspace_id or any(m not in profile['modules'] for m in (module,source['module'])):raise HTTPException(403,'Shared source module/workspace is outside this agent scope')
        if profile.get('project_id') and (definition['root']['project_id']!=profile['project_id'] or source['project_id'] not in (None,profile['project_id'])):raise HTTPException(403,'Shared source project is outside this agent scope')
    _require_ai_rate_limit(db,request,user,bucket='artifact_analysis');response.headers['Cache-Control']='no-store'
    return questions.snapshot_result(db,user,shares.item(row,source,position if dashboard else None),
        {'shared_id':row.id,'share_edition':row.version,'panel_position':position,'panel_label':label},citation(row,source,position if dashboard else None),category_query)


def intent(text,parent):
    prior=(parent.result or {}).get('shared_query') if parent else None
    if prior and prior.get('awaiting_share') and re.fullmatch(r'\s*#?[1-9]\d*\s*',text):
        return {'artifact_id':int(text.strip().lstrip('#')),'positions':None,'category_query':''}
    explicit=bool(re.search(r'(?i)\bshared (?:artifact|dashboard|report)|\bshare\s*#?\s*\d+',text))
    if not explicit and not prior:return None
    translated=re.sub(r'(?i)\bshared (?:artifact|dashboard|report)\b|\bshare(?=\s*#?\s*\d+)','dashboard',text)
    shadow=SimpleNamespace(status=parent.status,result={'dashboard_query':prior}) if prior else None
    result=questions.intent(translated,shadow)
    return result if result and (explicit or not result.get('generic')) else None


def prepare(db,user,data,parent,selection):
    if not selection:return None,None
    from app.ai_operator.suite import Plan
    ident=selection.get('artifact_id')
    if not ident:return Plan(summary='Choose an available shared publication.',question='Which shared artifact ID should I read? IDs are listed under Shared artifacts.',steps=[]),{
        'awaiting_share':True,'shared':True,'artifact_id':None,'dashboard_revision':None,'positions':None,'category_query':''}
    if data.artifact_id:raise HTTPException(409,'Choose either a private artifact or a shared publication for this question')
    row=shares.entry(db,user,ident);definition=shares.available(db,user,row,selection.get('dashboard_revision'))
    if row.values_json['workspace_id']!=data.workspace_id:raise HTTPException(409,'Continue in the shared publication workspace')
    data.module=definition['root']['module'];data.project_id=None
    body=definition['root']['body'];panels=body['panels'] if body['kind']=='dashboard' else [{'label':'Published snapshot'}]
    shadow=SimpleNamespace(status=parent.status,result={'dashboard_query':parent.result['shared_query']}) if parent and (parent.result or {}).get('shared_query') else parent
    plan,packet=questions.prepare(data,shadow,{'id':row.id,'kind':'dashboard','revision':row.version,'panels':panels},selection)
    if packet:
        packet={**packet,'shared':True,'project_id':definition['root']['project_id']}
        if not plan.question:
            from app.ai_operator.suite import Step
            data.context=[Step(tool=data.module.lower()+'.shared_artifact',payload={'share_id':row.id,'edition':row.version,'position':p,'category_query':selection['category_query']}) for p in packet['positions']]
    return plan,packet


def lineage(sources,depth=0):
    if depth>10:raise HTTPException(422,'Shared evidence lineage exceeds the supported depth')
    result=[]
    for source in sources:
        ident=source if isinstance(source,str) else str(source.get('id',''))
        match=re.search(r'(?:^|:)(shared-artifact:\d+:e\d+(?::p[1-6])?)$',ident)
        if match:result.append(match[1])
        if isinstance(source,dict):result.extend(lineage(source.get('shared_sources',[]),depth+1))
    result=list(dict.fromkeys(result))
    if len(result)>100:raise HTTPException(422,'Too many shared evidence references; split the workflow')
    return result


def revalidate(db,user,sources):
    for ident in lineage(sources):
        match=re.fullmatch(r'shared-artifact:(\d+):e(\d+)(?::p(\d+))?',ident)
        if match:
            row=shares.entry(db,user,int(match[1]));definition=shares.available(db,user,row,int(match[2]))
            if match[3] and (definition['root']['body']['kind']!='dashboard' or int(match[3])>len(definition['sources'])):raise HTTPException(404,'Shared source panel is unavailable')


def history_packet(run):
    # Previous shared assertions are not fresh evidence. Keep the user's scope
    # request, but never feed the old generated answer back into an LLM.
    if lineage((run.result or {}).get('citations',[])):
        return {'command':run.command,'status':run.status,'receipts':[{k:v for k,v in receipt.items() if k in ('tool','record_id','status','artifact_id','artifact_revision')} for receipt in run.receipts or []],
            'plan':{'summary':'Prior shared answer omitted; retrieve current authorized publication evidence.','steps':[]}}
    return {'command':run.command,'plan':run.plan,'status':run.status,'receipts':run.receipts}
