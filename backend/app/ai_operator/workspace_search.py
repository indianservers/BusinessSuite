"""Private file retrieval over existing parsed uploads. No shared document cache."""
import json,math,re
from collections import Counter
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from pydantic import Field,field_validator
from sqlalchemy.orm import Session
from typing import Literal
from starlette.concurrency import run_in_threadpool
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.ai_operator.suite_tools import Strict
from app.ai_operator.local_features import fit_rows,STOP,SYNONYMS
from app.ai_operator import suite_uploads as uploads

router=APIRouter(prefix='/suite/workspace',tags=['Agent workspace knowledge'])

BUSINESS_TERMS={'vacation':'leave','vacations':'leave','holiday':'leave','holidays':'leave',
    'bill':'invoice','bills':'invoice','supplies':'inventory','stock':'inventory',
    'vendor':'supplier','vendors':'supplier','suppliers':'supplier',
    'onboarding':'orientation','joiner':'employee','joiners':'employee',
    'reimbursements':'reimbursement','trip':'travel','trips':'travel',
    'client':'customer','clients':'customer','customers':'customer',
    'prerequisites':'prerequisite','dependencies':'dependency','credentials':'credential'}


def document_features(text):
    words=[SYNONYMS.get(word,word) for word in re.findall(r'[^\W_]+',text.casefold()) if word not in STOP]
    words=[BUSINESS_TERMS.get(word,word) for word in words]
    return Counter([*words,*(' '.join(pair) for pair in zip(words,words[1:]))])


# Only fixed native read endpoints; external connectors are not implicitly
# searched. The same canonical routers and role/row filters run on every search.
SOURCES={'crm.leads','crm.deals','crm.tasks','pms.projects','pms.tasks','hrms.directory','hrms.policies','srm.invoices','srm.inventory','fam.cost_centers','fam.vouchers'}


class KnowledgeQuery(Strict):
    query:str=Field(min_length=1,max_length=500)
    mode:Literal['hybrid','semantic','lexical']='hybrid'
    include_records:bool=True


def module_sources(module,project_id=None,allowed=None):
    return sorted(name for name in SOURCES if name.startswith(module.lower()+'.')
        and (name!='pms.tasks' or project_id) and (allowed is None or name in allowed))


def conversational_query(text,followup=False):
    # An explicit retrieval command, never a catch-all for action requests.
    match=re.fullmatch(r'\s*(?:search|find|look up)\s+(?:(?:my|our|the)\s+)?knowledge\s*(?:for\s*:?|:)\s*(.{1,500})\s*',text,re.I|re.S)
    if not match and followup:match=re.fullmatch(r'\s*(?:what about|and what about|how about|search instead for|now search for)\s+(.{1,500})\s*',text,re.I|re.S)
    if not match or re.search(r'\b(?:then|and)\s+(?:create|send|update|delete|assign|approve)\b',match[1],re.I):return None
    return match[1].strip()


def local_answer(context):
    packets=[p['records'] for p in context if p['tool'].endswith('.search_knowledge')]
    found=[item for packet in packets if isinstance(packet,dict) for item in packet.get('items',[])]
    if not found:return {'summary':'No matching excerpts were found in the selected authorized source samples. This does not establish that no matching business records exist.','steps':[],'source_ids':[]}
    selected=[];lines=['Retrieved source excerpts, not independently verified facts. These are bounded samples; no actions were executed.']
    for item in found[:4]:
        line=f"\n[{item['id']}] {item['label']}: {item['excerpt'][:350]}"
        if sum(map(len,lines))+len(line)>1950:break
        lines.append(line);selected.append(item['id'])
    return {'summary':'\n'.join(lines),'steps':[],'source_ids':selected}


def upload_chunks(db,user,conversation_id):
    files=[file for file in uploads.listing(db,user,conversation_id) if not file.get('media')];chunks=[]
    for file in files:
        row=uploads.owned(db,user,conversation_id,file['id']);text=row.result['text']
        for start in range(0,len(text),900):
            part=text[start:start+1200]
            if part.strip():chunks.append({'text':part,'file':file,'start':start,'end':start+len(part),
                'source':{'id':f'upload:{file["id"]}:{start}','file_id':file['id'],'kind':'upload','label':file['name'],
                    'start':start,'end':start+len(part),'href':f'#bot-attachment-{file["id"]}'}})
    return files,chunks


def rank_chunks(chunks,query,mode):
    if not chunks:return [],{'method':'none','semantic_used':False}
    idf,vectors=fit_rows(chunks,feature_extractor=document_features);counts=document_features(query)
    raw={term:(1+math.log(count))*idf[term] for term,count in counts.items() if term in idf}
    norm=math.sqrt(sum(v*v for v in raw.values())) or 1
    lexical_query={term:value/norm for term,value in raw.items()}
    semantic=None;notice=None
    if mode!='lexical':
        from app.ai_operator.local_embeddings import encode
        try:semantic=encode([query,*[c['text'] for c in chunks]])
        except ValueError:
            if mode=='semantic':raise HTTPException(503,'Server semantic model is unavailable. Try lexical search.') from None
            notice='Semantic model unavailable; results use lexical matching only.'
    results=[]
    for index,(chunk,vector) in enumerate(zip(chunks,vectors),1):
        lexical=sum(value*vector.get(term,0) for term,value in lexical_query.items())
        literal=query.casefold() in chunk['text'].casefold()
        meaning=sum(a*b for a,b in zip(semantic[0],semantic[index])) if semantic else 0
        if mode=='semantic' and meaning<.28:continue
        if mode!='semantic' and not (lexical>0 or literal or meaning>=.28):continue
        score=meaning if mode=='semantic' else .55*meaning+.45*lexical+.25*literal
        results.append({**chunk['source'],'excerpt':chunk['text'],'score':round(score,5),
            'lexical_score':round(lexical,5),'semantic_score':round(meaning,5) if semantic else None})
    results.sort(key=lambda r:(-r['score'],r['id']))
    return results,{'method':'local-minilm-tfidf-hybrid' if semantic and mode=='hybrid' else 'local-minilm-cosine' if semantic else 'tfidf-cosine-and-literal',
        'semantic_used':bool(semantic),'notice':notice}


class Search(Strict):
    conversation_id:int=Field(gt=0)
    query:str=Field(min_length=1,max_length=500)
    limit:int=Field(default=8,ge=1,le=20)

    @field_validator('query')
    @classmethod
    def nonblank_query(cls,value):
        value=value.strip()
        if not value:raise ValueError('Enter a search query.')
        return value


class KnowledgeSearch(Search):
    agent_id:int|None=Field(default=None,gt=0)
    mode:Literal['hybrid','semantic','lexical']='hybrid'
    include_uploads:bool=True
    tools:list[Literal['crm.leads','crm.deals','crm.tasks','pms.projects','pms.tasks','hrms.directory','hrms.policies','srm.invoices','srm.inventory','fam.cost_centers','fam.vouchers']]=Field(default_factory=list,max_length=6)
    project_id:int|None=Field(default=None,gt=0)


@router.get('/conversation-search')
async def conversation_search(request:Request,conversation_id:int=Query(gt=0),
    module:Literal['CRM','PMS','HRMS','SRM','FAM']='CRM',query:str=Query(min_length=1,max_length=500),
    mode:Literal['hybrid','semantic','lexical']='hybrid',include_records:bool=True,project_id:int|None=Query(default=None,gt=0),
    agent_id:int|None=Query(default=None,gt=0),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite_conversations import owned
    from app.ai_operator.suite import Step,check_tool
    chat=owned(db,user,conversation_id)
    check_tool(db,user,chat.workspace_id,Step(tool=f'{module.lower()}.search_knowledge'),False)
    allowed=None
    if agent_id:
        from uuid import uuid4
        from app.ai_operator.suite import Command
        from app.ai_operator.saved_agents import context
        data=Command(request_key=str(uuid4()),text=query,agent_id=agent_id,workspace_id=chat.workspace_id,module=module,project_id=project_id,provider='preferred')
        profile=context(db,user,data,None)
        if f'{module.lower()}.search_knowledge' not in profile['tools']:raise HTTPException(403,'Knowledge search is outside this agent tools')
        allowed=profile['tools'];project_id=data.project_id
    return await knowledge_search(KnowledgeSearch(conversation_id=conversation_id,query=query,mode=mode,
        agent_id=agent_id,project_id=project_id,tools=module_sources(module,project_id,allowed) if include_records else [],limit=4),request,db,user)


@router.get('/search-status')
def search_status(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    from app.ai_operator.local_embeddings import status
    authorize(db,user,None)
    return {'embedding':status(),'sources':sorted(SOURCES),'max_candidates':200,'max_source_calls':6}


@router.post('/search')
async def knowledge_search(data:KnowledgeSearch,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite_conversations import owned
    from app.ai_operator.suite import Step,check_tool,api_call
    from app.ai_operator.suite_tools import validate_payload,minimize_source
    from app.ai_operator.evidence import records,issue_sources
    from app.ai_agents.security import limits,company
    from app.ai_agents.api import _require_ai_rate_limit
    chat=owned(db,user,data.conversation_id)
    _require_ai_rate_limit(db,request,user,bucket='suite_knowledge')
    names=list(dict.fromkeys(data.tools))
    profile=None
    if data.agent_id:
        from app.ai_operator.saved_agents import owned as agent_owned,public as agent_public,runtime_access
        agent=agent_owned(db,user,data.agent_id);runtime_access(db,user,agent);profile=agent_public(agent)
        if profile['workspace_id']!=chat.workspace_id:raise HTTPException(403,'Agent knowledge is outside this conversation workspace')
        if not set(names)<=set(profile['tools']):raise HTTPException(403,'Knowledge sources are outside this agent tools')
        if profile['project_id']:
            if data.project_id and data.project_id!=profile['project_id']:raise HTTPException(403,'Project is outside this agent scope')
            data.project_id=profile['project_id']
    if len(names)>limits(db,company(user))['max_calls']:raise HTTPException(422,'Select fewer knowledge sources within your tool-call budget.')
    steps=[]
    # Validate every selected source before doing any reads.
    for name in names:
        step=Step(tool=name,record_id=data.project_id if name=='pms.tasks' else None)
        tool=check_tool(db,user,chat.workspace_id,step,False)
        if 'per_page' in tool.fields:step.payload={'per_page':50}
        validate_payload(tool,step.payload);steps.append((step,tool))
    files,chunks=upload_chunks(db,user,chat.id) if data.include_uploads else ([],[])
    if profile and data.include_uploads:
        from app.ai_operator.agent_knowledge import chunks as agent_chunks
        bound_files,bound_chunks=agent_chunks(db,user,profile)
        files=list({file['id']:file for file in [*files,*bound_files]}.values())
        chunks=list({part['source']['id']:part for part in [*chunks,*bound_chunks]}.values())
    retrieved_at=datetime.now(timezone.utc).isoformat();coverage=[]
    for step,tool in steps:
        value=await api_call(request.app,request.headers.get('authorization',''),'GET',tool.path.format(record_id=step.record_id),step.payload)
        if step.tool=='pms.projects':value=[p for p in records(value) if p.get('workspace_id')==chat.workspace_id]
        rows=records(minimize_source(step.tool,value))[:50]
        sources=issue_sources([{'tool':step.tool,'record_id':step.record_id,'records':rows}],retrieved_at)
        by_id={s['record_id']:s for s in sources}
        for row in rows:
            if row.get('id') not in by_id:continue
            source={**by_id[row['id']],'id':f'{step.tool}:{row["id"]}','kind':'record'}
            if step.tool=='hrms.directory':source['href']='/hrms/employee-directory'
            elif step.tool.startswith('fam.'):source['href']='/fam/'+step.tool.split('.')[1].replace('_','-')
            text=json.dumps(row,ensure_ascii=False,default=str)[:1200]
            chunks.append({'text':text,'source':source})
        total=value.get('total') if isinstance(value,dict) else None
        coverage.append({'tool':step.tool,'records_searched':len(rows),'limit':50,'complete':isinstance(total,int) and len(rows)>=total})
    # Fair sampling across selected sources instead of letting the first large
    # upload consume every slot. Every source retains its original offsets.
    groups={}
    for chunk in chunks:
        source=chunk['source'];key=source.get('tool') or f'upload:{source["file_id"]}'
        groups.setdefault(key,[]).append(chunk)
    bounded=[]
    while groups and len(bounded)<200:
        for key in list(groups):
            bounded.append(groups[key].pop(0))
            if not groups[key]:del groups[key]
            if len(bounded)>=200:break
    ranked,engine=await run_in_threadpool(rank_chunks,bounded,data.query,data.mode)
    response={'items':ranked[:data.limit],**engine,'files_searched':len(files),'records':coverage,'candidates_searched':len(bounded),
        'candidates_available':len(chunks),'retrieved_at':retrieved_at,
        'coverage':'Bounded current authorized API snapshots, parsed conversation uploads and selected private agent files. Scores rank relevance, not factual confidence. No external accounts or full ERP index searched.'}
    cap=limits(db,company(user))['max_result_bytes']
    limited=False
    while response['items'] and len(json.dumps(response,ensure_ascii=False).encode())>cap:
        response['items'].pop();limited=True
    response['disclosure_limited']=limited
    return response


@router.post('/file-search')
def search(data:Search,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.suite_conversations import owned
    owned(db,user,data.conversation_id)
    files,chunks=upload_chunks(db,user,data.conversation_id)
    if not chunks:return {'items':[],'files_searched':0,'method':'tfidf-cosine-and-literal','coverage':'Current conversation uploads only; no files selected.'}
    idf,vectors=fit_rows(chunks,feature_extractor=document_features);counts=document_features(data.query)
    raw={term:(1+math.log(count))*idf[term] for term,count in counts.items() if term in idf};norm=math.sqrt(sum(v*v for v in raw.values())) or 1
    query={term:value/norm for term,value in raw.items()};ranked=[]
    for chunk,vector in zip(chunks,vectors):
        lexical=bool(data.query.strip().casefold() in chunk['text'].casefold())
        score=sum(value*vector.get(term,0) for term,value in query.items())+.25*lexical
        if score>0:
            file=chunk['file'];ranked.append({'id':f'upload:{file["id"]}:{chunk["start"]}',
                'file_id':file['id'],'label':file['name'],'excerpt':chunk['text'],'score':round(score,5),
                'start':chunk['start'],'end':chunk['end'],'href':f'#bot-attachment-{file["id"]}'})
    ranked.sort(key=lambda r:(-r['score'],r['file_id'],r['start']))
    return {'items':ranked[:data.limit],'files_searched':len(files),'chunks_searched':len(chunks),'retrieved_at':datetime.now(timezone.utc).isoformat(),
        'method':'tfidf-cosine-and-literal','coverage':'Current conversation uploads only. Bounded parsed excerpts; lexical/vector matching, not semantic embeddings or complete ERP search.'}
