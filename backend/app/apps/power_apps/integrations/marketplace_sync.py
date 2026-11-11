"""Resumable connector sync reuses service policies and native import receipts."""
import hashlib
import json
from datetime import timedelta, datetime, timezone
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field,ConfigDict
from app.core.deps import get_db,RequirePermission
from app.shared.models import ServicePolicy
from app.shared.import_models import ImportBatch
from app.shared import import_service as imports
from app.apps.power_apps.integrations import vault,service
from app.apps.power_apps.integrations.marketplace_actions import TARGETS
from app.apps.power_apps.integrations.contracts import IntegrationFailure
from app.apps.power_apps.runtime import now,utc,safe_data

router=APIRouter(prefix='/sync',tags=['Connector sync'])
def checked(call,*args,**kwargs):
    try: return call(*args,**kwargs)
    except IntegrationFailure as error:
        raise HTTPException(409 if error.uncertain else 422,{'category':error.category,'message':str(error),'uncertain':error.uncertain,'retryable':error.retryable,'retry_after':error.retry_after}) from None


view=RequirePermission('power_apps_view')
manage=RequirePermission('power_apps_manage_credentials')


@router.get('/catalog')
def sync_catalog(user=Depends(view)):
    return {'targets':{key:{'module':module,'entity':entity} for key,(module,entity) in TARGETS.items()}}


@router.get('/sources/{kind}')
def source_options(kind:str,db=Depends(get_db),user=Depends(view)):
    if kind in {'leads','contacts','activities'}:
        from app.apps.crm.productivity import rows
        records=rows(db,user,kind).limit(200).all()
        return {'items':[{'id':r.id,'label':getattr(r,'full_name',None) or r.subject} for r in records]}
    if kind=='tasks':
        from app.apps.project_management.models import PMSTask
        from app.apps.project_management.access import get_task_project_for_action
        choices=[]
        for row in db.query(PMSTask).order_by(PMSTask.id.desc()).limit(200):
            try: get_task_project_for_action(db,row.id,user,'browse')
            except HTTPException: continue
            choices.append({'id':row.id,'label':row.title})
        return {'items':choices}
    raise HTTPException(422,'Choose leads, contacts, activities or tasks')


class JobInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    connection_id:int=Field(gt=0)
    name:str=Field(min_length=1,max_length=150)
    source:dict=Field(default_factory=dict)
    constants:dict[str,str]=Field(default_factory=dict)
    mapping:dict[str,str]=Field(default_factory=dict)
    automatic:bool=False
    apply_new_records:bool=False
    allow_credit_usage:bool=False
    interval_minutes:int=Field(default=15,ge=5,le=1440)


class JobState(BaseModel):
    expected_version:int=Field(ge=1)
    enabled:bool
    automatic:bool


class ReviewedRetry(BaseModel):
    expected_version:int=Field(ge=1)
    confirmed:bool=False


class WorkflowInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    connection_id:int=Field(gt=0)
    action_id:str=Field(max_length=80)
    source_kind:str=Field(pattern='^(leads|contacts|activities|tasks)$')
    source_id:int=Field(gt=0)
    settings:dict[str,str]=Field(default_factory=dict)
    expected_hash:str|None=None
    confirmed:bool=False
    request_id:str=Field(min_length=8,max_length=80,pattern=r'^[A-Za-z0-9_.:-]+$')


def workflow_payload(db,user,conn,data):
    allowed={'upsert_contact':'contacts','create_contact':'contacts','enrich_person':'contacts','create_draft':'contacts','create_ticket':'activities','create_card':'tasks'}
    expected=allowed.get(data.action_id)
    if expected!=data.source_kind and not (expected=='contacts' and data.source_kind=='leads'):
        raise HTTPException(422,'Choose the native record type for this workflow')
    if data.source_kind=='tasks':
        from app.apps.project_management.access import get_task_project_for_action
        record,_=get_task_project_for_action(db,data.source_id,user,'browse')
    else:
        from app.apps.crm.productivity import rows
        from app.apps.crm.api.router import _get_resource
        model=_get_resource(data.source_kind).model
        record=rows(db,user,data.source_kind).filter(model.id==data.source_id).first()
        if not record: raise HTTPException(404,'Native source record not found')
    fingerprint=imports.digest(imports.snapshot(record))
    if data.expected_hash is not None and data.expected_hash!=fingerprint: raise HTTPException(409,'Native record changed; preview the workflow again')
    derived={}
    if data.source_kind in {'leads','contacts'}:
        name=record.full_name or ''
        parts=name.split(maxsplit=1)
        derived={'email':record.email or '', 'first_name':getattr(record,'first_name',None) or (parts[0] if parts else ''),
            'last_name':getattr(record,'last_name',None) or (parts[1] if len(parts)>1 else ''), 'name':name}
    elif data.source_kind=='activities': derived={'title':record.subject,'text':record.body or record.description or ''}
    else: derived={'title':record.title,'text':record.description or ''}
    from app.apps.power_apps.integrations.registry import get_action
    spec=get_action(conn.connector_id,data.action_id)
    if not spec.mutates: raise HTTPException(422,'Choose a write workflow')
    fields=set(spec.input_schema.get('properties',{}))
    if set(data.settings)-fields or set(data.settings)&set(derived): raise HTTPException(422,'Native source fields cannot be overridden by workflow settings')
    payload={**{k:v for k,v in derived.items() if k in fields},**data.settings}
    # Validation does not dispatch; confirmation is checked on the execute route.
    from app.apps.power_apps.integrations.registry import INPUTS
    try: INPUTS[conn.connector_id,data.action_id].model_validate(payload)
    except ValueError: raise HTTPException(422,'Complete the workflow settings and required native fields') from None
    return payload,fingerprint


@router.post('/workflow/preview')
def preview_workflow(data:WorkflowInput,environment:str='development',db=Depends(get_db),user=Depends(view)):
    conn=vault.connection(db,user,environment,data.connection_id)
    payload,fingerprint=workflow_payload(db,user,conn,data)
    return {'payload':payload,'source_hash':fingerprint,'action_id':data.action_id}


@router.post('/workflow/execute')
def execute_workflow(data:WorkflowInput,environment:str='development',db=Depends(get_db),user=Depends(manage)):
    view(user);RequirePermission('power_apps_execute')(user)
    if not data.confirmed or not data.expected_hash: raise HTTPException(422,'Preview the native record and explicitly confirm the external write')
    conn=vault.connection(db,user,environment,data.connection_id)
    payload,fingerprint=workflow_payload(db,user,conn,data)
    output=checked(service.invoke,db,user,conn,data.action_id,payload,confirmed=True,key='native-workflow:'+data.request_id)
    vault.audit(db,conn,user,'native_workflow',{'action':data.action_id,'source_kind':data.source_kind,'source_id':data.source_id,'source_hash':fingerprint})
    db.commit();return {'output':output}


def public(row):
    values = {k:v for k,v in row.values_json.items() if k not in {'lease','lease_until'}}
    health = 'paused' if not values.get('enabled') else (
        'attention' if values.get('retryable') is False and values.get('state') == 'error' else
        'retrying' if values.get('state') == 'error' else
        'running' if row.values_json.get('lease_until') and utc(datetime.fromisoformat(row.values_json['lease_until'])) > now() else
        'healthy' if values.get('last_success_at') else 'pending')
    return {'id':row.id,'version':row.version,**values,'health':health}


def failure_details(error, failures, provider):
    """Persist only controlled messages, never provider payloads or credentials."""
    detail = error.detail if isinstance(error, HTTPException) else None
    category = error.category if isinstance(error, IntegrationFailure) else (
        str(detail.get('category', 'request')) if isinstance(detail, dict) else
        'permission' if isinstance(error, HTTPException) and error.status_code in {401,403} else
        'schema' if isinstance(error, HTTPException) and error.status_code in {404,422} else 'internal')
    uncertain = error.uncertain if isinstance(error, IntegrationFailure) else bool(isinstance(detail,dict) and detail.get('uncertain'))
    retryable = error.retryable if isinstance(error, IntegrationFailure) else bool(isinstance(detail,dict) and detail.get('retryable'))
    # A credit-consuming request needs explicit review before a fresh attempt.
    retryable = bool(retryable and not uncertain and provider != 'surfe' and failures < 8)
    messages = {
        'auth': 'Reconnect the provider account and verify lead access.',
        'authentication': 'Reconnect the provider account and verify lead access.',
        'permission': 'Check provider access and native module permissions.',
        'scope': 'Reconnect with the required provider permissions.',
        'schema': 'Review the resource selection and field mapping.',
        'disabled': 'Enable the connection before retrying.',
        'rate_limit': 'Provider rate limit reached. Sync will retry after backoff.',
        'network': 'Provider connection failed. Sync will retry after backoff.',
        'response': 'The provider response could not be imported. Review the connection and resource.',
        'server': 'The provider is unavailable. Sync will retry after backoff.',
        'remote': 'The provider rejected the request. Review its status in the request journal.',
    }
    message = messages.get(category, 'Sync failed. Review the connection, resource and import permissions.')
    if category=='remote' and retryable: message = 'The provider is unavailable. Sync will retry after backoff.'
    if uncertain or provider == 'surfe': message = 'Review the previous provider request before another attempt; it may have completed or consumed credits.'
    if failures >= 8: message = 'Automatic retries stopped after repeated failures. Review the connection and retry manually.'
    requested = error.retry_after if isinstance(error,IntegrationFailure) else (detail.get('retry_after',0) if isinstance(detail,dict) else 0)
    delay = min(86400,max(60 * 2 ** min(failures - 1, 10), int(requested or 0)))
    return {'error_category':category,'retryable':retryable,'uncertain':uncertain,
            'consecutive_failures':failures,'last_error':message,'last_failure_at':now().isoformat(),
            'next_at':(now()+timedelta(seconds=delay)).isoformat()}


def get_job(db,user,ident,environment,request,lock=False):
    row=db.query(ServicePolicy).filter_by(id=ident,kind='connector_sync',updated_by=user.id).first()
    if not row: raise HTTPException(404,'Sync job not found')
    values=row.values_json
    conn=vault.connection(db,user,environment,values['connection_id'])
    if row.organization_id!=conn.organization_id or values['environment']!=environment: raise HTTPException(404,'Sync job not found')
    spec=imports.spec_or_404(values['module'],values['entity'])
    ctx=imports.authorize(db,user,spec,request)
    if ctx.branch_id!=values['branch_id']: raise HTTPException(404,'Sync job not found in this branch')
    if lock: db.refresh(row,with_for_update=True)
    return row,conn,spec,ctx


@router.get('/jobs')
def jobs(request:Request,environment:str='development',db=Depends(get_db),user=Depends(view)):
    rows=db.query(ServicePolicy).filter_by(kind='connector_sync',updated_by=user.id).order_by(ServicePolicy.id.desc()).all()
    items=[]
    for row in rows:
        try: get_job(db,user,row.id,environment,request)
        except HTTPException: continue
        items.append(public(row))
    return {'items':items}


@router.post('/jobs',status_code=201)
def create(data:JobInput,request:Request,environment:str='development',db=Depends(get_db),user=Depends(manage)):
    view(user);RequirePermission('power_apps_execute')(user)
    conn=vault.connection(db,user,environment,data.connection_id,manage=True)
    if conn.connector_id not in TARGETS: raise HTTPException(422,'This provider has no native sync workflow')
    module,entity=TARGETS[conn.connector_id]
    spec=imports.spec_or_404(module,entity);ctx=imports.authorize(db,user,spec,request)
    source={**data.source,'cursor':'0'}
    checked(service.typed_action,conn,'sync_page',source,data.allow_credit_usage)
    safe_data(data.model_dump())
    if len(json.dumps(data.model_dump()))>16000: raise HTTPException(422,'Sync settings exceed 16 KB')
    fields={f['key'] for f in spec.fields}
    if set(data.constants)-fields or set(data.mapping)-fields: raise HTTPException(422,'Unknown native import field')
    digest=hashlib.sha256(json.dumps([conn.id,ctx.branch_id,source],sort_keys=True).encode()).hexdigest()
    key=f'connector-sync:{conn.organization_id}:{user.id}:{digest}'
    from app.apps.srm.services.commercial import lock_tenant
    lock_tenant(db,user)
    if db.query(ServicePolicy).filter_by(scope_key=key).first(): raise HTTPException(409,'Reuse the existing sync job for this provider resource')
    values={**data.model_dump(),'source':source,'provider':conn.connector_id,'environment':environment,
        'module':module,'entity':entity,'branch_id':ctx.branch_id,'enabled':True,'cursor':'0',
        'cycle':str(uuid4()),'state':'ready','next_at':now().isoformat(),'last_error':None,'pages':0,'changed':0,'batches':[]}
    row=ServicePolicy(scope_key=key,organization_id=conn.organization_id,module_key=module,kind='connector_sync',values_json=values,updated_by=user.id)
    db.add(row);db.flush();vault.audit(db,conn,user,'sync_created',{'job_id':row.id,'target':module+':'+entity});db.commit()
    return public(row)


@router.put('/jobs/{ident}')
def status(ident:int,data:JobState,request:Request,environment:str='development',db=Depends(get_db),user=Depends(manage)):
    view(user)
    row,conn,_,_=get_job(db,user,ident,environment,request,True)
    if row.version!=data.expected_version: raise HTTPException(409,'Sync job changed; refresh before updating')
    row.values_json={**row.values_json,'enabled':data.enabled,'automatic':data.automatic};row.version+=1
    vault.audit(db,conn,user,'sync_status',{'job_id':row.id,'enabled':data.enabled,'automatic':data.automatic});db.commit()
    return public(row)


@router.post('/jobs/{ident}/reviewed-retry')
def reviewed_retry(ident:int,data:ReviewedRetry,request:Request,environment:str='development',db=Depends(get_db),user=Depends(manage)):
    view(user);RequirePermission('power_apps_execute')(user)
    row,conn,_,_=get_job(db,user,ident,environment,request,True)
    if row.version!=data.expected_version: raise HTTPException(409,'Sync job changed; refresh before retrying')
    if not data.confirmed or row.values_json['state']!='error' or conn.connector_id!='surfe':
        raise HTTPException(422,'Review the previous enrichment request and confirm a new credit-consuming attempt')
    if row.values_json.get('lease'): raise HTTPException(409,'Wait for the active sync to finish')
    row.values_json={**row.values_json,'cycle':str(uuid4()),'last_error':None,'state':'ready'};row.version+=1
    vault.audit(db,conn,user,'sync_retry_reviewed',{'job_id':ident});db.commit()
    return run_page(db,user,ident,environment,request)


@router.post('/jobs/{ident}/run')
def run(ident:int,request:Request,environment:str='development',db=Depends(get_db),user=Depends(manage)):
    view(user);RequirePermission('power_apps_execute')(user)
    return run_page(db,user,ident,environment,request)


def run_page(db,user,ident,environment,request):
    row,conn,spec,ctx=get_job(db,user,ident,environment,request,True)
    values=dict(row.values_json)
    if not values['enabled']: raise HTTPException(409,'Sync job is paused')
    if values.get('lease_until') and utc(datetime.fromisoformat(values['lease_until']))>now(): raise HTTPException(409,'Sync is already running')
    if values['state']=='idle':
        values.update(cursor='0',cycle=str(uuid4()),state='ready',pages=0,changed=0)
    lease=str(uuid4());expected=row.version
    values.update(lease=lease,lease_until=(now()+timedelta(minutes=5)).isoformat())
    claimed=db.query(ServicePolicy).filter_by(id=row.id,version=expected).update({'values_json':values,'version':expected+1},synchronize_session=False)
    if not claimed: db.rollback();raise HTTPException(409,'Sync job changed; retry')
    db.commit()
    try:
        args={**values['source'],'cursor':values['cursor']}
        result=checked(service.invoke,db,user,conn,'sync_page',args,confirmed=values.get('allow_credit_usage',False),key='sync:'+str(ident)+':'+values['cycle']+':'+hashlib.sha256(values['cursor'].encode()).hexdigest()[:24])
        page=result['data']
        row,conn,spec,ctx=get_job(db,user,ident,environment,request,True)
        if row.values_json.get('lease')!=lease or not row.values_json['enabled']: raise HTTPException(409,'Sync was paused or changed while reading the provider')
        records=page['records'];changed=[];markers=[]
        for record in records:
            fingerprint=imports.digest(record)
            marker_key=f'connector-record:{ident}:'+hashlib.sha256(record['external_id'].encode()).hexdigest()
            marker=db.query(ServicePolicy).filter_by(scope_key=marker_key,organization_id=conn.organization_id,kind='connector_record').first()
            if marker and marker.values_json.get('fingerprint')==fingerprint: continue
            changed.append(record);markers.append((marker,marker_key,fingerprint))
        batch=None
        if changed:
            headers=sorted({k for record in changed for k in record})
            table={'headers':headers,'rows':[[record.get(k,'') for k in headers] for record in changed],
                'rowNumbers':list(range(2,len(changed)+2)),'total':len(changed),'headerRow':1,'sheet':'','sheets':[]}
            batch=ImportBatch(id=str(uuid4()),organization_id=ctx.company_id,branch_id=ctx.branch_id,module=spec.module,entity=spec.key,
                filename=values['provider']+' sync '+str(ident),source='connector_sync',created_by=user.id,status='uploaded',table_json=table)
            db.add(batch);db.flush()
            mapping=values['mapping'] or {f['key']:f['key'] for f in spec.fields if f['key'] in headers and f['key'] not in values['constants']}
            options={'duplicates':'skip','trim':True,'email_case':True,'numbers':True,'constants':values['constants'],'edits':{}}
            try:
                preview=imports.preview(db,batch,spec,mapping,options,ctx,user)
            except HTTPException as error:
                if error.status_code!=422: raise
                batch.preview_json={'can_import':False,'mapping_error':str(error.detail),'rows':[],'counts':{},'total':len(changed)}
                batch.mapping_json=mapping;batch.options_json=options
            else:
                if values['apply_new_records'] and preview['can_import']:
                    imports.commit(db,batch,spec,ctx,user)
            for marker,key,fingerprint in markers:
                if not marker:
                    marker=ServicePolicy(scope_key=key,organization_id=conn.organization_id,module_key=spec.module,kind='connector_record',updated_by=user.id)
                    db.add(marker)
                marker.values_json={'fingerprint':fingerprint,'batch_id':batch.id}
        next_cursor=page['next_cursor']
        rescan=int(row.values_json.get('wake_sequence',0))>int(values.get('wake_sequence',0))
        history=[*values['batches'],*([batch.id] if batch else [])][-100:]
        row.values_json={**row.values_json,'lease':None,'lease_until':None,'cursor':next_cursor or '0','state':'idle' if next_cursor is None else 'in_progress',
            'last_error':None,'error_category':None,'retryable':None,'uncertain':False,'consecutive_failures':0,
            'last_success_at':now().isoformat(),'next_at':(now()+timedelta(minutes=0 if rescan else values['interval_minutes'] if next_cursor is None else 1)).isoformat(),
            'pages':values['pages']+1,'changed':values['changed']+len(changed),'batches':history}
        row.version+=1
        vault.audit(db,conn,user,'sync_page_completed',{'job_id':ident,'changed':len(changed),'batch_id':batch.id if batch else None,'complete':next_cursor is None})
        db.commit();return public(row)
    except Exception as error:
        db.rollback()
        current=db.query(ServicePolicy).filter_by(id=ident,organization_id=conn.organization_id,kind='connector_sync').with_for_update().first()
        if current and current.values_json.get('lease')==lease:
            failures=int(current.values_json.get('consecutive_failures',0))+1
            current.values_json={**current.values_json,'lease':None,'lease_until':None,'state':'error',
                **failure_details(error,failures,conn.connector_id)};current.version+=1;db.commit()
        raise


def dispatch_due(db):
    from types import SimpleNamespace
    from app.models.user import User
    from app.access.service import activate_run_context,release_run_context,background_scope
    # Keyset batches avoid starvation without holding a server-side cursor across
    # run_page's commits (PostgreSQL closes those cursors on commit).
    upper=db.query(ServicePolicy.id).filter_by(kind='connector_sync').order_by(ServicePolicy.id.desc()).first()
    def candidates():
        last=0
        while upper:
            batch=db.query(ServicePolicy).filter(ServicePolicy.kind=='connector_sync',ServicePolicy.id>last,
                ServicePolicy.id<=upper[0]).order_by(ServicePolicy.id).limit(100).all()
            if not batch: break
            last=batch[-1].id
            yield from batch
    rows=candidates()
    succeeded=failed=0
    for job in rows:
        value=job.values_json
        if not value.get('enabled') or not value.get('automatic') or utc(datetime.fromisoformat(value['next_at']))>now(): continue
        if value.get('state')=='error' and value.get('retryable') is False: continue
        if value.get('lease_until') and utc(datetime.fromisoformat(value['lease_until']))>now(): continue
        user=db.get(User,job.updated_by)
        if not user or not user.is_active: continue
        try:
            activate_run_context(db,user,SimpleNamespace(scope_key=f'company:{job.organization_id}'))
            with background_scope(db,user,value['module'],'create',branch_id=value['branch_id']):
                manage(user);view(user);RequirePermission('power_apps_execute')(user)
                request=Request({'type':'http','headers':[(b'x-suite-branch',str(value['branch_id']).encode())]})
                run_page(db,user,job.id,value['environment'],request);succeeded+=1
        except Exception:
            db.rollback();failed+=1
        finally: release_run_context(db)
    return {'completed_pages':succeeded,'failed_jobs':failed}
