"""Reviewed artifact snapshots in the existing signed organization policy store.

Only the owner reads private sources before publishing a reviewed snapshot.
Image readers access explicit publication copies, never private source history.
"""
import hmac
import json
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from fastapi.responses import Response
from pydantic import Field,StrictInt,model_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.shared.models import ServicePolicy
from app.ai_operator import artifacts
from app.ai_operator.agent_library import Audience,Confirmation,Revision,admin,require_admin,audience_access,audience_check
from app.ai_operator.suite_tools import Strict
from app.ai_operator.service import digest
from app.ai_agents.security import company,signature,seal,verify,fingerprint
from app.ai_agents.services.audit import AiAuditService

router=APIRouter(prefix='/suite/artifact-shares',tags=['Reviewed shared artifacts'])
KIND='ai_artifact_share'


class ShareAudience(Audience):
    member_ids:list[StrictInt]=Field(default_factory=list,max_length=100)
    team_ids:list[StrictInt]=Field(default_factory=list,max_length=50)


class Preview(Strict):
    request_key:UUID
    source_id:StrictInt=Field(gt=0)
    source_revision:StrictInt=Field(ge=1,le=100)
    audience:ShareAudience
    share_id:StrictInt|None=Field(default=None,gt=0)
    revision:StrictInt|None=Field(default=None,ge=1)

    @model_validator(mode='after')
    def paired(self):
        if bool(self.share_id)!=bool(self.revision):raise ValueError('Choose the share and its current edition together')
        return self


def signed(row):
    return {'id':row.id,'organization_id':row.organization_id,'scope_key':row.scope_key,'revision':row.version,
        'values':{k:v for k,v in row.values_json.items() if k!='signature'}}


def sign(row):row.values_json={**row.values_json,'signature':signature(signed(row))}


def entry(db,user,ident,lock=False):
    query=db.query(ServicePolicy).filter_by(id=ident,organization_id=company(user),kind=KIND).populate_existing()
    row=(query.with_for_update() if lock else query).first()
    if not row:raise HTTPException(404,'Shared artifact not found')
    if not hmac.compare_digest(str(row.values_json.get('signature','')),signature(signed(row))):raise HTTPException(409,'Shared artifact integrity changed')
    from app.ai_operator.suite import authorize
    authorize(db,user,row.values_json['workspace_id'])
    return row


def manager(db,user,row):return row.values_json['source_owner']==user.id and admin(db,user)


def manage(db,user,row):
    require_admin(db,user)
    if not manager(db,user,row):raise HTTPException(404,'Shared artifact management is private to its publisher')


def bundle(db,user,ident,revision):
    root=artifacts.public(db,user,artifacts.owned(db,user,ident),revision)
    from app.ai_operator.artifact_dashboards import resolve
    def snapshot(value):
        return {'source_id':value['id'],'source_revision':value['revision'],'module':value['module'],'project_id':value['project_id'],
            'body':artifacts.Body.model_validate({k:v for k,v in value.items() if k in artifacts.Body.model_fields}).model_dump(mode='json')}
    result={'workspace_id':root['workspace_id'],'root':snapshot(root),'sources':[]}
    if root['kind']=='dashboard':result['sources']=[snapshot(resolve(db,user,root['workspace_id'],panel)) for panel in root['panels']]
    if len(json.dumps(result,ensure_ascii=False).encode())>240000:raise HTTPException(422,'Shared snapshot exceeds 240 KB; split the dashboard')
    return result


def resources(definition):return [definition['root'],*definition['sources']]


def available(db,user,row,revision=None,export=False):
    value=row.values_json
    if value['status']!='active' or not audience_access(db,user,row):raise HTTPException(404,'Shared artifact is not available to your current audience')
    if revision is not None and revision!=row.version:raise HTTPException(409,'Shared artifact edition changed; reload before continuing')
    owner=db.get(User,value['source_owner'])
    try:
        if not owner or fingerprint(db,owner,row.organization_id)!=value['owner_fingerprint']:raise ValueError()
    except (HTTPException,ValueError):raise HTTPException(404,'Shared artifact publisher access changed; a fresh publication is required') from None
    # Only test liveness of the exact reviewed source IDs. Never fetch another
    # user's conversation content or disable the private-history ORM filter.
    from app.ai_operator.assistant_models import AssistantConversation
    table=AssistantConversation.__table__;ids={s['source_id'] for s in resources(value['definition'])}
    live=set(db.connection().execute(select(table.c.id).where(table.c.id.in_(ids),table.c.user_id==value['source_owner'],
        table.c.organization_id==row.organization_id,table.c.deleted_at.is_(None),table.c.references['suite_artifact'].as_boolean()==True)).scalars())
    if live!=ids:raise HTTPException(404,'A published source is no longer available')
    for source in resources(value['definition']):
        artifacts.access(db,user,value['workspace_id'],source['module'])
        if source['project_id']:
            from app.apps.project_management.access import get_project_for_action
            project=get_project_for_action(db,source['project_id'],user,'browse')
            if project.workspace_id!=value['workspace_id']:raise HTTPException(403,'Shared source project is outside its workspace')
        if export:
            from app.access.service import check_background_access
            from app.ai_operator.suite import MODULES
            check_background_access(db,user,MODULES[source['module']],'export')
    return value['definition']


def metadata(db,user,row):
    value=row.values_json;definition=value.get('definition');pending=value.get('pending') if manager(db,user,row) else None
    if pending:
        try:
            root=pending['definition']['root']
            if bundle(db,user,root['source_id'],root['source_revision'])!=pending['definition']:pending=None
        except HTTPException:pending=None
    root=definition['root'] if definition else pending['definition']['root'] if pending else None
    return {'id':row.id,'revision':row.version,'status':value['status'],'workspace_id':value['workspace_id'],
        'title':root['body']['title'] if root else 'Unpublished artifact share' if value['status']=='draft' else 'Revoked shared artifact','kind':root['body']['kind'] if root else None,
        'module':root['module'] if root else None,'source_revision':root['source_revision'] if root else None,
        'can_manage':manager(db,user,row),'can_revoke':admin(db,user),'definition_hash':digest(definition) if definition else None,
        'audience':value['audience'] if manager(db,user,row) else None,
        'pending':{**{k:v for k,v in pending.items() if k not in ('grant','input_hash','request_key','assets')},
            'image_positions':list((pending.get('assets') or {}).keys())} if pending else None,
        'history':value.get('history',[]) if manager(db,user,row) else []}


def audit(db,user,row,action):
    AiAuditService(db).log(user=user,agent_id=None,module='CROSS',action='artifact_share.'+action,
        input_json={'share_id':row.id},output_json={'revision':row.version,'status':row.values_json['status']},status='success')


def authorized_publications(db,user,workspace_id,all_pages=False):
    """Read current grants in bounded keyset pages, without private history."""
    from app.ai_operator.suite import authorize
    authorize(db,user,workspace_id)
    query=db.query(ServicePolicy.id).filter_by(kind=KIND,organization_id=company(user)).filter(
        ServicePolicy.values_json['status'].as_string()=='active',
        ServicePolicy.values_json['workspace_id'].as_integer()==workspace_id if workspace_id is not None else ServicePolicy.values_json['workspace_id'].as_integer().is_(None))
    cursor=None
    while True:
        page=(query.filter(ServicePolicy.id<cursor) if cursor is not None else query).order_by(ServicePolicy.id.desc()).limit(200).all()
        for (ident,) in page:
            try:
                row=entry(db,user,ident)
                definition=available(db,user,row)
                yield row,definition
            except HTTPException as error:
                if error.status_code not in (403,404):raise
        if not all_pages or len(page)<200:return
        cursor=page[-1][0]


@router.get('')
def listing(workspace_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    items=[metadata(db,user,row) for row,_ in authorized_publications(db,user,workspace_id)]
    return {'items':items,'can_publish':admin(db,user)}


@router.get('/source/{ident}')
def source_shares(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    artifacts.owned(db,user,ident)
    rows=db.query(ServicePolicy.id).filter_by(kind=KIND,organization_id=company(user)).filter(
        ServicePolicy.values_json['source_owner'].as_integer()==user.id,ServicePolicy.values_json['source_id'].as_integer()==ident).order_by(
            (ServicePolicy.values_json['status'].as_string()=='active').desc(),ServicePolicy.id.desc()).limit(200)
    return {'items':[metadata(db,user,entry(db,user,i)) for (i,) in rows],'can_publish':admin(db,user)}


@router.post('/preview')
def preview(data:Preview,request:Request,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_admin(db,user);definition=bundle(db,user,data.source_id,data.source_revision)
    from app.ai_operator.artifact_share_images import positions
    if positions(definition):
        from app.ai_agents.api import _require_ai_rate_limit
        _require_ai_rate_limit(db,request,user,bucket='artifact_media')
    audience_check(db,user,data.audience,definition['workspace_id'])
    key=f'company:{company(user)}:artifact-share:{user.id}:{data.request_key}';input_hash=digest(data.model_dump(mode='json',exclude={'request_key'}))
    row=entry(db,user,data.share_id,True) if data.share_id else db.query(ServicePolicy).filter_by(scope_key=key,kind=KIND,organization_id=company(user)).with_for_update().first()
    if row:
        manage(db,user,row);value=row.values_json;pending=value.get('pending')
        if pending and pending['request_key']==str(data.request_key):
            if pending['input_hash']!=input_hash:raise HTTPException(409,'Share request key conflicts')
            return metadata(db,user,row)
        if pending:raise HTTPException(409,'Publish or discard the pending share preview first')
        if data.revision!=row.version or value['source_id']!=data.source_id or value['workspace_id']!=definition['workspace_id']:raise HTTPException(409,'Share edition or source changed')
    else:
        if data.share_id:raise HTTPException(404,'Shared artifact not found')
        if db.query(ServicePolicy.id).filter_by(kind=KIND,organization_id=company(user)).filter(ServicePolicy.values_json['status'].as_string()!='revoked').count()>=200:raise HTTPException(422,'Revoke unused shares before adding more')
        row=ServicePolicy(scope_key=key,organization_id=company(user),module_key='ai',kind=KIND,version=1,updated_by=user.id,
            values_json={'source_owner':user.id,'source_id':data.source_id,'workspace_id':definition['workspace_id'],
                'status':'draft','definition':None,'audience':data.audience.model_dump(),'history':[]})
        db.add(row)
        try:db.flush()
        except IntegrityError:
            db.rollback();existing=db.query(ServicePolicy).filter_by(scope_key=key,organization_id=company(user),kind=KIND).first()
            if not existing:raise HTTPException(409,'Conflicting artifact share request') from None
            existing=entry(db,user,existing.id);manage(db,user,existing)
            if (existing.values_json.get('pending') or {}).get('input_hash')!=input_hash:raise HTTPException(409,'Conflicting artifact share request') from None
            return metadata(db,user,existing)
    review={'definition':definition,'audience':data.audience.model_dump(),'base_revision':row.version,
        'proposed_revision':row.version if row.values_json['status']=='draft' else row.version+1}
    from app.ai_operator.artifact_share_images import stage
    assets=stage(db,user,row,definition,review['proposed_revision'])
    if assets:review['assets']=assets
    hashed=digest(review)
    row.values_json={**row.values_json,'pending':{**review,'preview_hash':hashed,'grant':seal(db,user,hashed),
        'request_key':str(data.request_key),'input_hash':input_hash}}
    sign(row);audit(db,user,row,'preview');db.commit();return metadata(db,user,row)


@router.post('/{ident}/publish')
def publish(ident:int,data:Confirmation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident,True);manage(db,user,row);value=row.values_json;pending=value.get('pending')
    if not pending and value['status']=='active' and value.get('last_published_hash')==data.preview_hash:
        root=value['definition']['root'];bundle(db,user,root['source_id'],root['source_revision'])
        from app.ai_operator.artifact_share_images import positions,load
        for position in positions(value['definition']):load(db,row,value['definition'],value.get('assets') or {},row.version,int(position))
        return metadata(db,user,row)
    if not pending or pending['preview_hash']!=data.preview_hash:raise HTTPException(409,'Review the current artifact share preview')
    review={k:pending[k] for k in ('definition','audience','base_revision','proposed_revision')}
    if pending.get('assets'):review['assets']=pending['assets']
    if digest(review)!=data.preview_hash or pending['base_revision']!=row.version:raise HTTPException(409,'Artifact share review changed')
    verify(db,user,pending['grant'],payload=data.preview_hash,confirmation=True)
    root=pending['definition']['root'];current=bundle(db,user,root['source_id'],root['source_revision'])
    if current!=pending['definition']:raise HTTPException(409,'Pinned source snapshot changed; prepare a fresh share review')
    audience_check(db,user,Audience.model_validate(pending['audience']),value['workspace_id'])
    from app.ai_operator.artifact_share_images import positions,load,transition
    for position in positions(current):load(db,row,current,pending.get('assets') or {},pending['proposed_revision'],int(position),staged=True)
    transition(db,row,value.get('assets') or {},'retired')
    transition(db,row,pending.get('assets') or {},'published')
    history=value.get('history',[])
    if value['definition']:history=[*history,{'revision':row.version,'title':value['definition']['root']['body']['title'],
        'source_revision':value['definition']['root']['source_revision'],'definition_hash':digest(value['definition'])}][-20:]
    row.version=pending['proposed_revision'];row.updated_by=user.id
    row.values_json={**value,'status':'active','definition':current,'audience':pending['audience'],'pending':None,'history':history,
        'owner_fingerprint':fingerprint(db,user,company(user)),'last_published_hash':data.preview_hash,
        'assets':pending.get('assets') or {}}
    sign(row);audit(db,user,row,'published');db.commit();return metadata(db,user,row)


@router.post('/{ident}/discard')
def discard(ident:int,data:Confirmation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident,True);manage(db,user,row);pending=row.values_json.get('pending')
    if not pending or pending['preview_hash']!=data.preview_hash:raise HTTPException(409,'Artifact share review changed')
    from app.ai_operator.artifact_share_images import transition
    transition(db,row,pending.get('assets') or {},'retired')
    row.values_json={**row.values_json,'pending':None};sign(row);audit(db,user,row,'preview_discarded');db.commit()
    return {'id':row.id,'revision':row.version,'status':row.values_json['status'],'pending':None}


def retire(db,user,row,action):
    from app.ai_operator.artifact_share_images import transition
    transition(db,row,row.values_json.get('assets') or {},'retired')
    transition(db,row,(row.values_json.get('pending') or {}).get('assets') or {},'retired')
    row.version+=1;row.updated_by=user.id
    row.values_json={**row.values_json,'status':'revoked','definition':None,'pending':None,'history':[],'last_published_hash':None,'assets':{}}
    sign(row);audit(db,user,row,action)


@router.post('/{ident}/revoke')
def revoke(ident:int,data:Revision,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident,True);require_admin(db,user)
    if row.values_json['status']=='revoked' and data.revision==row.version-1:return metadata(db,user,row)
    if row.version!=data.revision:raise HTTPException(409,'Shared artifact edition changed')
    if row.values_json['status']!='revoked':retire(db,user,row,'revoked');db.commit()
    return metadata(db,user,row)


def archive_source(db,user,ident):
    rows=db.query(ServicePolicy).filter_by(kind=KIND,organization_id=company(user)).filter(
        ServicePolicy.values_json['source_owner'].as_integer()==user.id,ServicePolicy.values_json['status'].as_string()!='revoked').order_by(ServicePolicy.id).with_for_update().all()
    for candidate in rows:
        row=entry(db,user,candidate.id);definitions=[d for d in (row.values_json.get('definition'),(row.values_json.get('pending') or {}).get('definition')) if d]
        if any(s['source_id']==ident for definition in definitions for s in resources(definition)):retire(db,user,row,'source_archived')


def item(row,source,position=None):
    body=source['body']
    public_id=f'share-{row.id}'+(f'-panel-{position}' if position else '')
    value={**body,'id':public_id,'module':source['module'],'revision':source['source_revision'],'current_revision':source['source_revision'],
        'provenance':{'citations':[],'note':f'Reviewed shared snapshot / share #{row.id} edition {row.version}. Content is not independently verified. Private citations and conversation history are excluded.'}}
    if body['kind']=='dashboard':
        value['panels']=[{**p,'artifact_id':i} for i,p in enumerate(body['panels'],1)]
        value['image_panel_positions']=[int(key) for key in (row.values_json.get('assets') or {}) if key!='0']
    if body['kind']=='image':value['provenance']['note']+=' Text retrieval includes only the saved caption and metadata; pixels are served through the authorized image endpoint.'
    return value


@router.get('/{ident}/content')
def content(ident:int,response:Response,revision:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident);definition=available(db,user,row,revision);response.headers['Cache-Control']='no-store'
    return {'share_id':row.id,'revision':row.version,'item':item(row,definition['root'])}


@router.get('/{ident}/panels/{position}')
def panel(ident:int,position:int,response:Response,revision:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident);definition=available(db,user,row,revision)
    if definition['root']['body']['kind']!='dashboard' or not 1<=position<=len(definition['sources']):raise HTTPException(404,'Shared panel not found')
    response.headers['Cache-Control']='no-store'
    return {'share_id':row.id,'revision':row.version,'item':item(row,definition['sources'][position-1],position)}


@router.get('/{ident}/analysis')
def analysis(ident:int,request:Request,response:Response,position:int|None=Query(default=None,ge=1,le=6),revision:int|None=None,
    category_query:str=Query(default='',max_length=100),series_key:str|None=Query(default=None,max_length=64),
    order:Literal['input','category','value_desc']|None=None,limit:int|None=Query(default=None,ge=1,le=50),chart_kind:Literal['bar','line','pie']|None=None,
    db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident);definition=available(db,user,row,revision)
    source=definition['root']
    if position:
        if source['body']['kind']!='dashboard' or position>len(definition['sources']):raise HTTPException(404,'Shared panel not found')
        source=definition['sources'][position-1]
    from app.ai_operator.artifact_analysis import compute
    from app.ai_agents.api import _require_ai_rate_limit
    _require_ai_rate_limit(db,request,user,bucket='artifact_analysis');response.headers['Cache-Control']='no-store'
    return compute(source['body'],{'state':'shared','share_id':ident,'revision':row.version,'source_revision':source['source_revision']},db,user,
        category_query=category_query,series_key=series_key,order=order,limit=limit,chart_kind=chart_kind)


def image_response(content):
    return Response(content,media_type='image/png',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff',
        'Content-Security-Policy':"default-src 'none'; sandbox",'Content-Disposition':'inline'})


@router.get('/{ident}/preview-image')
def preview_image(ident:int,request:Request,preview_hash:str=Query(pattern=r'^[a-f0-9]{64}$'),position:int=Query(default=0,ge=0,le=6),
    db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident);manage(db,user,row)
    pending=metadata(db,user,row).get('pending')
    if not pending or pending['preview_hash']!=preview_hash:raise HTTPException(409,'Review the current image publication preview')
    from app.ai_agents.api import _require_ai_rate_limit
    from app.ai_operator.artifact_share_images import load
    _require_ai_rate_limit(db,request,user,bucket='artifact_media')
    original=row.values_json['pending']
    return image_response(load(db,row,original['definition'],original.get('assets') or {},original['proposed_revision'],position,staged=True))


@router.get('/{ident}/image')
def image(ident:int,request:Request,revision:int|None=None,position:int=Query(default=0,ge=0,le=6),
    db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident);definition=available(db,user,row,revision)
    from app.ai_agents.api import _require_ai_rate_limit
    from app.ai_operator.artifact_share_images import load
    _require_ai_rate_limit(db,request,user,bucket='artifact_media')
    return image_response(load(db,row,definition,row.values_json.get('assets') or {},row.version,position))


@router.get('/{ident}/download')
def download(ident:int,request:Request,revision:int|None=None,position:int|None=Query(default=None,ge=1,le=6),format:Literal['md','csv','docx','xlsx','pdf','pptx','png']='md',db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident);definition=available(db,user,row,revision,True)
    from app.ai_agents.api import _require_ai_rate_limit
    _require_ai_rate_limit(db,request,user,bucket='artifact_exports')
    source=definition['root']
    if position:
        if source['body']['kind']!='dashboard' or position>len(definition['sources']):raise HTTPException(404,'Shared image panel not found')
        source=definition['sources'][position-1]
        if source['body']['kind']!='image' or format!='png':raise HTTPException(422,'Panel downloads currently require an image and PNG format')
    root=item(row,source,position);sources=[item(row,s,i) for i,s in enumerate(definition['sources'],1)] if root['kind']=='dashboard' else None
    source_media={}
    if sources and format in ('docx','pdf','xlsx'):
        from app.ai_operator.artifact_share_images import load
        for index,source_item in enumerate(sources,1):
            if source_item['kind']=='image':source_media[index]=load(db,row,definition,row.values_json.get('assets') or {},row.version,index)
    pixels=None
    if root['kind']=='image':
        from app.ai_operator.artifact_share_images import load
        pixels=load(db,row,definition,row.values_json.get('assets') or {},row.version,position or 0)
    value,mime=artifacts.render_download(root,format,sources,media_content=pixels,source_media=source_media)
    audit(db,user,row,'exported');db.commit()
    suffix=f'-panel-{position}' if position else ''
    return Response(value,media_type=mime,headers={'Content-Disposition':f'attachment; filename="shared-artifact-{row.id}-edition-{row.version}{suffix}.{format}"',
        'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
