"""Reviewed shared context, isolated from private memory and execution consent."""
import hmac
from datetime import datetime,timezone
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field,field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.deps import get_db,get_current_user
from app.models.user import User
from app.shared.models import ServicePolicy
from app.ai_operator.suite_memory import MemoryText,Module,active
from app.ai_operator.suite_tools import Strict
from app.ai_operator.agent_library import Audience,admin,audience_access,audience_check,Confirmation,Revision
from app.ai_agents.security import company,seal,verify,signature
from app.ai_operator.service import digest

router=APIRouter(prefix='/suite/organization-memory',tags=['Approved organization memory'])
KIND='ai_organization_memory'


class Definition(MemoryText):
    title:str=Field(min_length=1,max_length=120)
    module:Module|None=None
    workspace_id:int|None=Field(default=None,gt=0)

    @field_validator('title')
    @classmethod
    def safe_title(cls,value):return MemoryText.safe_text(value)


class Preview(Strict):
    request_key:UUID
    definition:Definition
    audience:Audience
    policy_id:int|None=Field(default=None,gt=0)
    revision:int|None=Field(default=None,ge=1)


def require_admin(db,user):
    from app.ai_operator.suite import authorize
    authorize(db,user,None)
    if not admin(db,user):raise HTTPException(403,'Organization memory publishing requires an organization administrator')


def signed(row):return {'id':row.id,'organization_id':row.organization_id,'module_key':row.module_key,'revision':row.version,'values':{k:v for k,v in row.values_json.items() if k!='signature'}}
def sign(row):row.values_json={**row.values_json,'signature':signature(signed(row))}


def entry(db,user,ident,lock=False):
    q=db.query(ServicePolicy).filter_by(id=ident,organization_id=company(user),kind=KIND).populate_existing()
    row=(q.with_for_update() if lock else q).first()
    if not row:raise HTTPException(404,'Organization memory not found')
    if not hmac.compare_digest(str(row.values_json.get('signature','')),signature(signed(row))):raise HTTPException(409,'Organization memory integrity changed')
    from app.ai_operator.agent_memory import authorize
    authorize(db,user,row.values_json['workspace_id'],row.values_json['module'])
    return row


def visible(db,user,row):
    if admin(db,user):return
    if row.values_json['status']!='active' or not audience_access(db,user,row):raise HTTPException(404,'Organization memory is outside your audience')


def public(db,user,row):
    value=row.values_json;pending=value.get('pending')
    return {'id':row.id,'revision':row.version,'status':value['status'],'definition':value.get('definition'),'audience':value.get('audience'),
        'can_manage':admin(db,user),'expired':bool(value.get('definition')) and not active(value['definition']),
        'pending':{k:v for k,v in pending.items() if k not in ('grant','owner_id','input_hash')} if pending and pending['owner_id']==user.id else None}


def audit(db,user,row,action):
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user,agent_id=None,module='CROSS',action='organization_memory.'+action,input_json={'policy_id':row.id},output_json={'revision':row.version,'status':row.values_json['status']},status='success')


@router.get('')
def listing(workspace_id:int|None=None,module:Module|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_operator.agent_memory import authorize
    authorize(db,user,workspace_id,module);items=[]
    for row in candidates(db,user,workspace_id,module,100):
        try:row=entry(db,user,row.id);visible(db,user,row);items.append(public(db,user,row))
        except HTTPException as error:
            if error.status_code not in (403,404):raise
    return {'items':items,'can_publish':admin(db,user)}


def candidates(db,user,workspace_id,module,limit):
    workspace=ServicePolicy.values_json['workspace_id'].as_integer()
    return db.query(ServicePolicy).filter_by(organization_id=company(user),kind=KIND).filter(
        or_(workspace.is_(None),workspace==workspace_id) if workspace_id else workspace.is_(None),
        ServicePolicy.module_key.in_(['*',module]) if module else ServicePolicy.module_key=='*').order_by(ServicePolicy.id.desc()).limit(limit).all()


@router.post('/preview')
def preview(data:Preview,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_admin(db,user)
    from app.ai_operator.agent_memory import authorize
    authorize(db,user,data.definition.workspace_id,data.definition.module)
    audience_check(db,user,data.audience,data.definition.workspace_id)
    db.query(User.id).filter_by(id=user.id).with_for_update().one()
    key=f'company:{company(user)}:organization-memory:{user.id}:{data.request_key}'
    row=entry(db,user,data.policy_id,True) if data.policy_id else db.query(ServicePolicy).filter_by(scope_key=key,kind=KIND).first()
    if row and not data.policy_id:row=entry(db,user,row.id,True)
    value=data.model_dump(mode='json',exclude={'request_key'});input_hash=digest(value)
    if row:
        pending=row.values_json.get('pending')
        if pending and pending['request_key']==str(data.request_key):
            if pending['input_hash']!=input_hash:raise HTTPException(409,'Review request key conflicts')
            return public(db,user,row)
        if row.values_json.get('last_request_key')==str(data.request_key) and row.values_json.get('last_input_hash')==input_hash:return public(db,user,row)
        if pending:raise HTTPException(409,'Publish or discard the current preview first')
        if row.version!=data.revision or row.values_json['status']=='forgotten':raise HTTPException(409,'Organization memory revision changed')
        if (row.values_json['workspace_id'],row.values_json['module'])!=(data.definition.workspace_id,data.definition.module):raise HTTPException(422,'Create separate memory to change its module or workspace')
    else:
        if db.query(ServicePolicy.id).filter_by(organization_id=company(user),kind=KIND).filter(ServicePolicy.values_json['status'].as_string().notin_(['revoked','forgotten'])).count()>=200:raise HTTPException(422,'Revoke unused organization memories before adding more')
        row=ServicePolicy(scope_key=key,organization_id=company(user),module_key=data.definition.module or '*',kind=KIND,version=1,updated_by=user.id,
            values_json={'workspace_id':data.definition.workspace_id,'module':data.definition.module,'status':'draft','definition':None,'audience':data.audience.model_dump(),'history':[]})
        db.add(row);db.flush()
    review={'definition':value['definition'],'audience':value['audience'],'base_revision':row.version,'proposed_revision':row.version if row.values_json['status']=='draft' else row.version+1}
    hashed=digest(review)
    row.values_json={**row.values_json,'pending':{**review,'preview_hash':hashed,'grant':seal(db,user,hashed),'owner_id':user.id,'request_key':str(data.request_key),'input_hash':input_hash}}
    sign(row);audit(db,user,row,'preview');db.commit();return public(db,user,row)


@router.post('/{ident}/publish')
def publish(ident:int,data:Confirmation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_admin(db,user);row=entry(db,user,ident,True);old=row.values_json;pending=old.get('pending')
    if not pending and old['status']=='active' and old.get('last_published_hash')==data.preview_hash:return public(db,user,row)
    if not pending or pending['preview_hash']!=data.preview_hash:raise HTTPException(409,'Review the latest organization memory')
    review={k:pending[k] for k in ('definition','audience','base_revision','proposed_revision')}
    if digest(review)!=data.preview_hash or pending['base_revision']!=row.version:raise HTTPException(409,'Organization memory review changed')
    verify(db,user,pending['grant'],payload=data.preview_hash,confirmation=True)
    if not active(pending['definition']):raise HTTPException(409,'Proposed organization memory has expired')
    audience_check(db,user,Audience.model_validate(pending['audience']),old['workspace_id'])
    history=old.get('history',[])
    if old['definition']:history=[*history,{'revision':row.version,'definition':old['definition'],'audience':old['audience']}][-20:]
    row.version=pending['proposed_revision'];row.updated_by=user.id
    row.values_json={**old,'status':'active','definition':pending['definition'],'audience':pending['audience'],'pending':None,'history':history,
        'last_published_hash':data.preview_hash,'last_request_key':pending['request_key'],'last_input_hash':pending['input_hash']}
    sign(row);audit(db,user,row,'published');db.commit();return public(db,user,row)


@router.post('/{ident}/discard')
def discard(ident:int,data:Confirmation,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    require_admin(db,user);row=entry(db,user,ident,True);pending=row.values_json.get('pending')
    if not pending or pending['preview_hash']!=data.preview_hash:raise HTTPException(409,'Review changed')
    row.values_json={**row.values_json,'pending':None};sign(row);audit(db,user,row,'discarded');db.commit();return public(db,user,row)


@router.post('/{ident}/revoke')
def revoke(ident:int,data:Revision,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return retire(db,user,ident,data.revision,False)


@router.post('/{ident}/forget')
def forget(ident:int,data:Revision,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return retire(db,user,ident,data.revision,True)


def retire(db,user,ident,revision,erase):
    require_admin(db,user);row=entry(db,user,ident,True)
    if row.version!=revision:raise HTTPException(409,'Organization memory changed')
    if row.values_json['status']=='forgotten':return public(db,user,row)
    row.version+=1;row.updated_by=user.id
    row.values_json={**row.values_json,'status':'forgotten' if erase else 'revoked','pending':None,
        **({'definition':None,'history':[]} if erase else {})}
    sign(row);audit(db,user,row,'forgotten' if erase else 'revoked');db.commit();return public(db,user,row)


@router.get('/{ident}/versions')
def versions(ident:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=entry(db,user,ident);visible(db,user,row)
    history=[h for h in reversed(row.values_json.get('history',[])) if admin(db,user) or audience_access(db,user,row,h['audience'])]
    return {'items':([{'revision':row.version,'definition':row.values_json['definition']}] if row.values_json['definition'] else [])+history}


def collect(db,user,workspace_id,module):
    result=[]
    for candidate in candidates(db,user,workspace_id,module,100):
        row=entry(db,user,candidate.id);value=row.values_json
        if value['status']!='active' or not active(value['definition']) or not audience_access(db,user,row):continue
        result.append({**value['definition'],'id':row.id,'key':f'organization:{row.id}','level':'organization','source':'approved-organization-policy','revision':row.version})
        if len(result)>=10:break
    return result


def revalidate(db,user,run):
    for source in (run.result or {}).get('memory_used',[]):
        if source.get('level')!='organization':continue
        try:
            row=entry(db,user,int(source['key'].split(':')[1]));value=row.values_json
            if row.version!=source['revision'] or value['status']!='active' or not active(value['definition']) or not audience_access(db,user,row):raise ValueError()
        except (HTTPException,ValueError,KeyError):raise HTTPException(409,'An organization policy used in this draft changed or is no longer available. Prepare a fresh review.') from None
