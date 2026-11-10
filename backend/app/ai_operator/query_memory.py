"""Capture authorized NLP requests once; export only deliberately curated examples."""
import hashlib
import hmac
import json
import re
from datetime import datetime,timezone
from typing import Literal

from fastapi import APIRouter,Depends,HTTPException,Query,Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import Field,model_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.deps import get_current_user,get_db
from app.models.user import User
from app.ai_operator.query_models import NlpQuery
from app.ai_operator.suite_tools import Strict
from app.ai_operator.local_corpus import FAMILIES

def platform_review_only():
    raise HTTPException(403, 'Training review is available only in the platform administrator portal')

router=APIRouter(prefix='/suite/nlp-queries',tags=['NLP query learning'],dependencies=[Depends(platform_review_only)])
SCOPES={'CRM':'CRM','PMS':'PMS','Sales':'SRM','HRMS':'HRMS'}


def sanitize(text):
    from app.ai_agents.services.advanced_security import AiDataRedactionService
    text=AiDataRedactionService.__new__(AiDataRedactionService).redact_text(text)
    text=re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----','[credential]',text,flags=re.S)
    text=re.sub(r'(?i)\b(?:bearer\s+)[A-Za-z0-9._~-]+','[credential]',text)
    text=re.sub(r'\b(?:AIza[A-Za-z0-9_-]{20,}|AQ\.[A-Za-z0-9_-]{20,})\b','[credential]',text)
    text=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[email]',text)
    text=re.sub(r'https?://\S+','[url]',text)
    text=re.sub(r'(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)','[number]',text)
    # Message text, titles and note payloads are not needed for intent training.
    text=re.sub(r'"[^"\n]*"|“[^”\n]*”','"value"',text)
    text=re.sub(r'(?i)(\b(?:task|lead|deal|invoice|request)\s*#\s*)\d+',r'\g<1>1',text)
    # Preserve a module prefix; replace free-form colon payloads after it.
    prefix=re.match(r'^\s*(?:CRM|PMS|Sales|SRM|HRMS|HR)\s*:\s*',text,re.I)
    start=prefix.end() if prefix else 0
    colon=text.find(':',start)
    if colon>=0:text=text[:colon+1]+' value'
    return re.sub(r'\s+',' ',text).strip()[:6000]


def branch_id(db):
    return getattr(db.info.get('branch_context'),'branch_id',None)


def capture(db,user,data):
    if data.local_plan is not None:return None  # Generated forms are not user NLP.
    from app.ai_agents.security import company
    from app.core.config import settings
    text=sanitize(data.text); normalized=text.casefold()
    key=hashlib.sha256(data.request_key.encode()).hexdigest()
    submission=hmac.new(settings.SECRET_KEY.encode(),json.dumps(data.model_dump(mode='json',exclude={'request_key'}),sort_keys=True).encode(),hashlib.sha256).hexdigest()
    row=db.query(NlpQuery).filter_by(user_id=user.id,request_key_hash=key,company_id=company(user),branch_id=branch_id(db)).first()
    if row:
        if row.submission_hash!=submission:raise HTTPException(409,'Request key already belongs to another query')
        return row
    row=NlpQuery(company_id=company(user),branch_id=branch_id(db),user_id=user.id,workspace_id=data.workspace_id,
        project_id=data.project_id,request_key_hash=key,submission_hash=submission,query_text=text,normalized_query=normalized,
        query_hash=hashlib.sha256(normalized.encode()).hexdigest(),module=data.module or 'CROSS',provider=data.provider,input_mode=data.input_mode)
    db.add(row)
    try:db.commit()
    except IntegrityError:
        db.rollback()
        row=db.query(NlpQuery).filter_by(user_id=user.id,request_key_hash=key,company_id=company(user),branch_id=branch_id(db)).first()
        if not row:raise HTTPException(409,'Request key already belongs to another query scope') from None
        if row.submission_hash!=submission:raise HTTPException(409,'Request key already belongs to another query') from None
    return row


def outcome(db,row,result=None,error=None):
    if row is None or row.review_status=='deleted':return
    if result:
        local=(result.get('result') or {}).get('local_nlp') or {}
        request=(result.get('result') or {}).get('request') or {}
        row.suite_run_id=result['id'];row.outcome=result['status'];row.error_code=result.get('error_code')
        row.module=request.get('module') or row.module
        row.project_id=request.get('project_id');row.workspace_id=result.get('workspace_id')
        row.predicted_intent=local.get('intent');row.confidence=local.get('confidence')
        if local:
            release=local.get('release') or {}
            row.model_version=(local.get('version','')+' / '+str((local.get('neural_prediction') or {}).get('engine') or local.get('model',''))+(f" / run:{release['job_id']}" if release.get('job_id') else ''))[:160]
        else:
            from app.ai_operator.models import OperatorApiLog
            log=db.query(OperatorApiLog).filter_by(suite_run_id=result['id'],user_id=row.user_id).order_by(OperatorApiLog.id.desc()).first()
            row.model_version=f'{log.provider}/{log.model}'[:160] if log else None
    else:
        row.outcome='rejected' if isinstance(error,HTTPException) else 'error'
        row.error_code=f'HTTP_{error.status_code}' if isinstance(error,HTTPException) else 'INTERNAL_ERROR'
    db.commit()


def access(db,user,workspace_id,module=None,all_users=False):
    from app.ai_operator.suite import authorize,MODULES
    from app.ai_agents.security import company
    from app.access.service import check_background_access
    authorize(db,user,workspace_id)
    if module and module!='CROSS':
        if module not in MODULES:raise HTTPException(422,'Unknown module')
        authorize(db,user,workspace_id,module);check_background_access(db,user,MODULES[module],'view')
    if all_users:
        from app.ai_agents.api import _require_ai_admin
        _require_ai_admin(user)
        if not module or module=='CROSS':raise HTTPException(422,'Select one module to review other users’ queries')
        grant=(getattr(user,'_suite_grants',{}) or {}).get(MODULES[module],{})
        if not user.is_superuser and grant.get('scope') not in {'all','company','organization'}:
            raise HTTPException(403,'Company-wide module visibility is required for shared query review')
    query=db.query(NlpQuery).filter_by(company_id=company(user),branch_id=branch_id(db),workspace_id=workspace_id)
    if not all_users:query=query.filter_by(user_id=user.id)
    if module:query=query.filter_by(module=module)
    return query


def visible(db,user,row):
    access(db,user,row.workspace_id,row.module if row.module!='CROSS' else None)
    # Project membership can be withdrawn independently of company/branch access.
    if row.project_id and row.suite_run_id:
        from app.ai_agents.security import scoped
        from app.apps.project_management.access import get_project_for_action
        with scoped(db,user,'project_management'):get_project_for_action(db,row.project_id,user,'browse')


def public(row):
    return {key:getattr(row,key) for key in ('id','user_id','suite_run_id','module','provider','input_mode','query_text','predicted_intent',
        'confidence','model_version','outcome','error_code','review_status','reviewed_module','reviewed_intent','training_text','privacy_reviewed','revision','created_at','reviewed_at')}


def private(data,**headers):
    return JSONResponse(jsonable_encoder(data),headers={'Cache-Control':'private, no-store',**headers})


@router.get('')
def listing(workspace_id:int|None=Query(None,gt=0),module:Literal['CRM','PMS','SRM','HRMS','FAM','CROSS']|None=None,
            review_status:Literal['pending','approved','rejected']|None=None,all_users:bool=False,after_id:int=Query(0,ge=0),
            limit:int=Query(30,ge=1,le=100),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    query=access(db,user,workspace_id,module,all_users).filter(NlpQuery.id>after_id)
    query=query.filter(NlpQuery.review_status!='deleted')
    if review_status:query=query.filter_by(review_status=review_status)
    rows=query.order_by(NlpQuery.id).limit(limit+1).all()
    result=[]
    for row in rows[:limit]:
        try:visible(db,user,row);result.append(public(row))
        except HTTPException:pass
    from app.ai_agents.api import _is_ai_admin
    return private({'items':result,'can_review':_is_ai_admin(user),'next_cursor':rows[min(limit,len(rows))-1].id if rows else after_id,'has_more':len(rows)>limit,
        'intents':{module:list(intents) for module,intents in FAMILIES.items()},'note':'Redacted submissions. Predicted intent is not a training label; approval requires curated text and privacy review.'})


class Review(Strict):
    revision:int=Field(ge=1)
    decision:Literal['approved','rejected','pending']
    module:Literal['CRM','PMS','Sales','HRMS']|None=None
    intent:str|None=Field(default=None,max_length=80)
    training_text:str|None=Field(default=None,min_length=3,max_length=6000)
    privacy_reviewed:bool=False

    @model_validator(mode='after')
    def label(self):
        if self.decision=='approved' and (not self.module or self.intent not in FAMILIES[self.module] or not self.training_text or not self.privacy_reviewed):
            raise ValueError('Approval requires a supported module/intent, curated text and explicit privacy review')
        return self


@router.put('/{ident}')
def review(ident:int,data:Review,workspace_id:int|None=Query(None,gt=0),module:Literal['CRM','PMS','SRM','HRMS','FAM','CROSS']|None=None,
           all_users:bool=False,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_agents.api import _require_ai_admin
    from app.ai_agents.services.audit import AiAuditService
    _require_ai_admin(user)
    row=access(db,user,workspace_id,module,all_users).filter_by(id=ident).with_for_update().first()
    if not row:raise HTTPException(404,'NLP query not found in this scope')
    visible(db,user,row)
    if row.review_status=='deleted':raise HTTPException(404,'NLP query not found in this scope')
    if row.revision!=data.revision:raise HTTPException(409,'Query review changed; reload before editing')
    if data.decision=='approved':
        access(db,user,workspace_id,SCOPES[data.module])
        text=sanitize(data.training_text)
        if not text or len(text)<3:raise HTTPException(422,'Curated training text is empty after redaction')
        row.training_text=text;row.reviewed_module=data.module;row.reviewed_intent=data.intent
    else:row.training_text=None;row.reviewed_module=None;row.reviewed_intent=None
    row.review_status=data.decision;row.reviewed_by=user.id;row.reviewed_at=datetime.now(timezone.utc);row.revision+=1
    row.privacy_reviewed=data.decision=='approved' and data.privacy_reviewed
    AiAuditService(db).log(user=user,agent_id=None,module=row.module,action='nlp.query.review',input_json={'query_id':row.id,'decision':data.decision},output_json={'revision':row.revision},status='success')
    db.commit();return private(public(row))


@router.delete('/{ident}')
def delete(ident:int,workspace_id:int|None=Query(None,gt=0),module:Literal['CRM','PMS','SRM','HRMS','FAM','CROSS']|None=None,
           all_users:bool=False,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_agents.services.audit import AiAuditService
    row=access(db,user,workspace_id,module,all_users).filter_by(id=ident).with_for_update().first()
    if not row:raise HTTPException(404,'NLP query not found in this scope')
    visible(db,user,row)
    AiAuditService(db).log(user=user,agent_id=None,module=row.module,action='nlp.query.delete',input_json={'query_id':row.id},output_json={},status='success')
    row.query_text='';row.normalized_query='';row.query_hash=hashlib.sha256(b'').hexdigest();row.training_text=None
    row.reviewed_module=None;row.reviewed_intent=None;row.predicted_intent=None;row.confidence=None;row.model_version=None
    row.review_status='deleted';row.outcome='deleted';row.revision+=1
    row.privacy_reviewed=False
    db.commit();return private({'deleted':True,'note':'Erases this training copy and prevents retry resurrection; original assistant history has its own retention.'})


@router.get('/training/export')
def export(workspace_id:int|None=Query(None,gt=0),module:Literal['CRM','PMS','SRM','HRMS','FAM','CROSS']|None=None,
           all_users:bool=False,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.ai_agents.api import _require_ai_admin
    from app.ai_agents.security import company
    from app.ai_agents.services.audit import AiAuditService
    _require_ai_admin(user)
    rows=access(db,user,workspace_id,module,all_users).filter_by(review_status='approved',privacy_reviewed=True).order_by(NlpQuery.id).limit(2001).all()
    if len(rows)>2000:raise HTTPException(413,'Narrow the export; it exceeds 2000 approved examples')
    result=[];seen={}
    for row in rows:
        try:visible(db,user,row);access(db,user,workspace_id,SCOPES[row.reviewed_module])
        except (HTTPException,KeyError):continue
        text=sanitize(row.training_text or '')
        key=(row.reviewed_module,text.casefold())
        if key in seen:
            if seen[key]!=row.reviewed_intent:raise HTTPException(409,'Conflicting labels for the same training text; resolve the reviews first')
            continue
        seen[key]=row.reviewed_intent
        if row.reviewed_intent in FAMILIES[row.reviewed_module]:result.append({'module':row.reviewed_module,'intent':row.reviewed_intent,'text':text})
    AiAuditService(db).log(user=user,agent_id=None,module=module or 'CROSS',action='nlp.query.export',input_json={'all_users':all_users},output_json={'examples':len(result)},status='success')
    db.commit()
    return private({'format':'reviewed-nlp-queries-v1','training_scope':{'company_id':company(user),'branch_id':branch_id(db),'workspace_id':workspace_id},
        'examples':result,'note':'Approved curated examples only. Training is an explicit offline step; this export does not deploy a model.'},
        **{'Content-Disposition':'attachment; filename="reviewed-nlp-queries.json"'})
