"""Google Ads lead form ingestion through the scoped import and review workflow."""
import hashlib
import hmac
import json
import secrets
from types import SimpleNamespace
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from app.core.deps import get_db,RequirePermission
from app.shared.models import ServicePolicy
from app.shared.import_models import ImportBatch
from app.shared import import_service as imports
from app.apps.power_apps.integrations import vault
from app.apps.power_apps.integrations.marketplace_sync import view,manage
from app.apps.power_apps.integrations.lead_hooks import callback_url
from app.apps.power_apps.runtime import now

router=APIRouter()


class FormSetup(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=150)
    form_id:str=Field(pattern=r'^[0-9]{1,40}$')
    apply_new_records:bool=False
    phone_country_code:str=Field(default='',max_length=5)


def owned(db,user,ident,request,lock=False):
    query=db.query(ServicePolicy).filter_by(id=ident,kind='google_lead_form',updated_by=user.id)
    if lock: query=query.with_for_update()
    row=query.first()
    if not row: raise HTTPException(404,'Lead form not found')
    spec=imports.spec_or_404('crm','leads');ctx=imports.authorize(db,user,spec,request)
    if row.organization_id!=ctx.company_id or row.values_json['branch_id']!=ctx.branch_id:
        raise HTTPException(404,'Lead form not found in this branch')
    return row,spec,ctx


def public(row):
    return {'id':row.id,'version':row.version,**{k:v for k,v in row.values_json.items() if k!='key_hash'}}


@router.post('/sync/lead-forms',status_code=201)
def create(data:FormSetup,request:Request,db=Depends(get_db),user=Depends(manage)):
    view(user);RequirePermission('power_apps_execute')(user)
    spec=imports.spec_or_404('crm','leads');ctx=imports.authorize(db,user,spec,request)
    if data.phone_country_code:
        from app.core.input_validation import calling_code
        try: calling_code(data.phone_country_code)
        except ValueError as error: raise HTTPException(422,str(error)) from None
    endpoint=secrets.token_urlsafe(32);key=secrets.token_urlsafe(32)
    url=callback_url(endpoint).replace('/lead-hooks/','/lead-form-hooks/')
    row=ServicePolicy(scope_key='google-lead-form:'+endpoint,organization_id=ctx.company_id,module_key='crm',kind='google_lead_form',updated_by=user.id,
        values_json={**data.model_dump(),'branch_id':ctx.branch_id,'enabled':True,'callback_url':url,
            'key_hash':hashlib.sha256(key.encode()).hexdigest(),'received':0})
    db.add(row);db.commit()
    return {**public(row),'google_key':key}


@router.get('/sync/lead-forms')
def forms(request:Request,db=Depends(get_db),user=Depends(view)):
    items=[]
    for row in db.query(ServicePolicy).filter_by(kind='google_lead_form',updated_by=user.id).order_by(ServicePolicy.id.desc()).all():
        try: owned(db,user,row.id,request)
        except HTTPException: continue
        recent=db.query(ServicePolicy).filter(ServicePolicy.kind=='google_lead_submission',ServicePolicy.organization_id==row.organization_id,
            ServicePolicy.values_json['form_config_id'].as_integer()==row.id).order_by(ServicePolicy.id.desc()).limit(10).all()
        items.append({**public(row),'recent':[{'id':r.id,'state':r.values_json['state'],'batch_id':r.values_json.get('batch_id'),
            'last_error':r.values_json.get('last_error')} for r in recent]})
    return {'items':items}


class FormState(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=1)
    enabled:bool


@router.put('/sync/lead-forms/{ident}')
def status(ident:int,data:FormState,request:Request,db=Depends(get_db),user=Depends(manage)):
    view(user);row,_,_=owned(db,user,ident,request,True)
    if row.version!=data.expected_version: raise HTTPException(409,'Lead form changed; refresh before updating')
    row.values_json={**row.values_json,'enabled':data.enabled};row.version+=1;db.commit()
    return public(row)


def normalize(payload,default_code):
    columns=payload.get('user_column_data')
    if not isinstance(columns,list) or len(columns)>200: raise HTTPException(422,'Invalid lead form answers')
    values={}
    for column in columns:
        if not isinstance(column,dict) or not isinstance(column.get('column_id'),str) or not isinstance(column.get('string_value'),str):
            raise HTTPException(422,'Invalid lead form answer')
        values[column['column_id']]=column['string_value'][:10000]
    name=values.get('FULL_NAME') or ' '.join(values.get(k,'') for k in ('FIRST_NAME','LAST_NAME')).strip()
    record={'full_name':name,'email':values.get('EMAIL',''),'phone':values.get('PHONE_NUMBER',''),
        'company_name':values.get('COMPANY_NAME',''),'job_title':values.get('JOB_TITLE',''),'source':'google_ads'}
    if record['phone'].strip().startswith('+'):
        import phonenumbers
        try:
            parsed=phonenumbers.parse(record['phone'],None)
            if phonenumbers.is_valid_number(parsed):record['phone_country_code']='+'+str(parsed.country_code)
        except phonenumbers.NumberParseException: pass
    elif default_code: record['phone_country_code']=default_code
    notes=[f'Google lead ID: {payload["lead_id"]}']
    notes.extend(f'{field}: {payload[field]}' for field in ('form_id','campaign_id','adgroup_id','creative_id','asset_group_id','gcl_id','lead_submit_time') if payload.get(field) is not None)
    notes.extend(f'{key}: {value}' for key,value in values.items() if key not in {'FULL_NAME','FIRST_NAME','LAST_NAME','EMAIL','PHONE_NUMBER','COMPANY_NAME','JOB_TITLE'})
    record['notes']='\n'.join(notes)[:10000]
    from app.core.rich_text import sanitize_tree
    return sanitize_tree(record)


@router.post('/lead-form-hooks/{endpoint}')
async def receive(endpoint:str,request:Request,db=Depends(get_db)):
    if len(endpoint)>100: raise HTTPException(404,'Lead form not found')
    form=db.query(ServicePolicy).filter_by(scope_key='google-lead-form:'+endpoint,kind='google_lead_form').with_for_update().first()
    if not form or not form.values_json.get('enabled'): raise HTTPException(404,'Lead form not found')
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>262144: raise HTTPException(413,'Lead form exceeds 256 KB')
    try:
        payload=json.loads(body)
        if not isinstance(payload,dict): raise ValueError()
    except (ValueError,TypeError): raise HTTPException(422,'Invalid lead form payload') from None
    # Google documents a capitalized key in some test-payload examples.
    key=payload.get('google_key',payload.get('Google_key',''))
    if not isinstance(key,str) or not hmac.compare_digest(hashlib.sha256(key.encode()).hexdigest(),form.values_json['key_hash']):
        raise HTTPException(401,'Invalid Google lead form key')
    if str(payload.get('form_id'))!=form.values_json['form_id']: raise HTTPException(422,'Lead belongs to another form')
    if 'is_test' in payload and not isinstance(payload['is_test'],bool): raise HTTPException(422,'Invalid test-lead flag')
    ident=payload.get('lead_id')
    if not isinstance(ident,str) or not ident or len(ident)>1000: raise HTTPException(422,'Lead ID is required')
    if payload.get('is_test') is True:
        form.values_json={**form.values_json,'last_test_at':now().isoformat()};form.version+=1;db.commit()
        return {'received':True,'test':True,'imported':False}
    record=normalize(payload,form.values_json.get('phone_country_code',''))
    scope='google-lead:'+endpoint+':'+hashlib.sha256(ident.encode()).hexdigest()
    if db.query(ServicePolicy.id).filter_by(scope_key=scope,organization_id=form.organization_id,kind='google_lead_submission').first():
        return {'received':True,'duplicate':True}
    db.add(ServicePolicy(scope_key=scope,organization_id=form.organization_id,module_key='crm',kind='google_lead_submission',updated_by=form.updated_by,
        values_json={'form_config_id':form.id,'state':'pending','next_at':now().isoformat(),'encrypted_payload':vault.CredentialVault.encrypt(record)}))
    form.values_json={**form.values_json,'received':int(form.values_json.get('received',0))+1,'last_received_at':now().isoformat()};form.version+=1
    db.commit()
    return {'received':True,'queued':True}


def dispatch_due(db):
    from sqlalchemy.orm import aliased
    from app.models.user import User
    from app.access.service import activate_run_context,release_run_context,background_scope
    source=aliased(ServicePolicy)
    ids=db.query(ServicePolicy.id).join(source,ServicePolicy.values_json['form_config_id'].as_integer()==source.id).filter(
        source.kind=='google_lead_form',source.values_json['enabled'].as_boolean().is_(True),ServicePolicy.kind=='google_lead_submission',
        ServicePolicy.values_json['state'].as_string().in_(['pending','retrying']),
        ServicePolicy.values_json['next_at'].as_string()<=now().isoformat()).order_by(ServicePolicy.id).limit(100).all()
    completed=failed=0
    for (ident,) in ids:
        try:
            row=db.query(ServicePolicy).filter_by(id=ident,kind='google_lead_submission').with_for_update().populate_existing().one()
            if row.values_json['state'] not in {'pending','retrying'}:
                db.rollback();continue
            form=db.get(ServicePolicy,row.values_json['form_config_id'])
            if not form or not form.values_json.get('enabled'):
                db.rollback();continue
            user=db.get(User,row.updated_by)
            if not user or not user.is_active: raise HTTPException(403,'Lead form owner is inactive')
            activate_run_context(db,user,SimpleNamespace(scope_key=f'company:{row.organization_id}'))
            with background_scope(db,user,'crm','create',branch_id=form.values_json['branch_id']):
                manage(user);view(user);RequirePermission('power_apps_execute')(user)
                request=Request({'type':'http','headers':[(b'x-suite-branch',str(form.values_json['branch_id']).encode())]})
                spec=imports.spec_or_404('crm','leads');ctx=imports.authorize(db,user,spec,request)
                if ctx.company_id!=row.organization_id: raise HTTPException(403,'Lead form authority changed')
                record=vault.CredentialVault.decrypt(SimpleNamespace(encrypted_value=row.values_json['encrypted_payload']))
                headers=sorted(record)
                batch=ImportBatch(id=str(uuid4()),organization_id=ctx.company_id,branch_id=ctx.branch_id,module='crm',entity='leads',
                    filename=form.values_json['name'],source='google_lead_form',created_by=user.id,status='uploaded',
                    table_json={'headers':headers,'rows':[[record[k] for k in headers]],'rowNumbers':[2],'total':1,'headerRow':1,'sheet':'','sheets':[]})
                db.add(batch);db.flush()
                mapping={f['key']:f['key'] for f in spec.fields if f['key'] in headers}
                preview=imports.preview(db,batch,spec,mapping,{'duplicates':'skip','trim':True,'email_case':True,'numbers':True,'constants':{},'edits':{}},ctx,user)
                if form.values_json.get('apply_new_records') and preview['can_import']: imports.commit(db,batch,spec,ctx,user)
                row.values_json={**row.values_json,'state':'imported' if batch.status=='imported' else 'review','batch_id':batch.id,'encrypted_payload':None,'last_error':None}
                row.version+=1;db.commit();completed+=1
        except Exception:
            db.rollback()
            row=db.query(ServicePolicy).filter_by(id=ident,kind='google_lead_submission').with_for_update().first()
            if row and row.values_json['state'] in {'pending','retrying'}:
                row.values_json={**row.values_json,'state':'attention','last_error':'Import needs attention. Restore the owner’s CRM permissions and retry from the lead form workspace.'}
                row.version+=1;db.commit()
            failed+=1
        finally: release_run_context(db)
    return {'completed':completed,'failed':failed}


@router.post('/sync/lead-forms/{ident}/retry')
def retry(ident:int,request:Request,db=Depends(get_db),user=Depends(manage)):
    view(user);RequirePermission('power_apps_execute')(user)
    form,_,_=owned(db,user,ident,request,True)
    if not form.values_json.get('enabled'): raise HTTPException(409,'Enable the lead form first')
    rows=db.query(ServicePolicy).filter(ServicePolicy.kind=='google_lead_submission',ServicePolicy.organization_id==form.organization_id,
        ServicePolicy.values_json['form_config_id'].as_integer()==form.id,ServicePolicy.values_json['state'].as_string()=='attention').with_for_update().limit(100).all()
    for row in rows:
        row.values_json={**row.values_json,'state':'pending','last_error':None,'next_at':now().isoformat()};row.version+=1
    db.commit();return {'queued':len(rows)}
