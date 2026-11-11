"""Signed lead notifications wake scoped sync jobs; provider answers are fetched by the worker."""
import hashlib
import hmac
import json
import secrets
from types import SimpleNamespace
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from app.core.deps import get_db, RequirePermission
from app.shared.models import ServicePolicy
from app.apps.power_apps.integrations import vault
from app.apps.power_apps.integrations.marketplace_sync import get_job, manage, view
from app.apps.power_apps.runtime import now

router=APIRouter()


class HookSetup(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=1)
    page_id:str=Field(pattern=r'^[0-9]{1,40}$')
    app_secret:SecretStr=Field(min_length=16,max_length=512)


def callback_url(endpoint):
    from app.core.config import settings
    base=settings.BACKEND_PUBLIC_URL.rstrip('/')
    parsed=urlsplit(base)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(422,'Lead callbacks require BACKEND_PUBLIC_URL with a public HTTPS origin')
    return base+'/api/v1/power-apps/integrations/lead-hooks/'+endpoint


@router.post('/sync/jobs/{ident}/facebook-hook',status_code=201)
def configure(ident:int,data:HookSetup,request:Request,environment:str='development',db=Depends(get_db),user=Depends(manage)):
    view(user);RequirePermission('power_apps_execute')(user)
    job,conn,_,_=get_job(db,user,ident,environment,request,True)
    if job.version!=data.expected_version: raise HTTPException(409,'Sync job changed; refresh before configuring the webhook')
    if conn.connector_id!='facebook_lead_ads': raise HTTPException(422,'Choose a Facebook lead sync job')
    if not job.values_json.get('automatic'): raise HTTPException(422,'Enable automatic sync before configuring notifications')
    endpoint=secrets.token_urlsafe(32)
    url=callback_url(endpoint)
    token=secrets.token_urlsafe(32)
    # The connection and source remain bound to the authorized job, never callback input.
    old=job.values_json.get('notification_endpoint')
    if old:
        previous=db.query(ServicePolicy).filter_by(scope_key='lead-hook:'+old,organization_id=conn.organization_id,kind='lead_hook').with_for_update().first()
        if previous: previous.values_json={**previous.values_json,'enabled':False}
    private={'app_secret':data.app_secret.get_secret_value(),'verify_hash':hashlib.sha256(token.encode()).hexdigest()}
    hook=ServicePolicy(scope_key='lead-hook:'+endpoint,organization_id=conn.organization_id,module_key='crm',kind='lead_hook',updated_by=user.id,
        values_json={'enabled':True,'job_id':job.id,'page_id':data.page_id,'form_id':job.values_json['source']['resource_id'],
            'encrypted_private':vault.CredentialVault.encrypt(private)})
    db.add(hook)
    job.values_json={**job.values_json,'notification_endpoint':endpoint,'notification_url':url,'notification_mode':'facebook_leadgen'}
    job.version+=1
    vault.audit(db,conn,user,'lead_hook_configured',{'job_id':job.id,'page_id':data.page_id})
    db.commit()
    return {'callback_url':url,'verify_token':token,'version':job.version,
        'instructions':'Configure a Page webhook for leadgen in your Meta app, then subscribe that app to this Page. Notifications wake this sync job; scheduled polling remains enabled.'}


@router.delete('/sync/jobs/{ident}/facebook-hook')
def disable(ident:int,request:Request,expected_version:int,environment:str='development',db=Depends(get_db),user=Depends(manage)):
    view(user)
    job,conn,_,_=get_job(db,user,ident,environment,request,True)
    if job.version!=expected_version: raise HTTPException(409,'Sync job changed; refresh before disabling notifications')
    endpoint=job.values_json.get('notification_endpoint')
    if endpoint:
        hook=db.query(ServicePolicy).filter_by(scope_key='lead-hook:'+endpoint,organization_id=conn.organization_id,kind='lead_hook').with_for_update().first()
        if hook: hook.values_json={**hook.values_json,'enabled':False}
    job.values_json={k:v for k,v in job.values_json.items() if not k.startswith('notification_')}
    job.version+=1
    vault.audit(db,conn,user,'lead_hook_disabled',{'job_id':job.id});db.commit()
    return {'disabled':True}


@router.api_route('/lead-hooks/{endpoint}',methods=['GET','POST'])
async def receive(endpoint:str,request:Request,db=Depends(get_db)):
    if len(endpoint)>100: raise HTTPException(404,'Lead notification endpoint not found')
    hook=db.query(ServicePolicy).filter_by(scope_key='lead-hook:'+endpoint,kind='lead_hook').first()
    if not hook or not hook.values_json.get('enabled'): raise HTTPException(404,'Lead notification endpoint not found')
    value=hook.values_json
    private=vault.CredentialVault.decrypt(SimpleNamespace(encrypted_value=value['encrypted_private']))
    if request.method=='GET':
        token=request.query_params.get('hub.verify_token','')
        if request.query_params.get('hub.mode')!='subscribe' or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(),private['verify_hash']):
            raise HTTPException(401,'Invalid verification token')
        challenge=request.query_params.get('hub.challenge','')
        if not challenge or len(challenge)>1024: raise HTTPException(422,'Invalid challenge')
        return PlainTextResponse(challenge,headers={'X-Content-Type-Options':'nosniff'})
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>262144: raise HTTPException(413,'Lead notification exceeds 256 KB')
    expected='sha256='+hmac.new(private['app_secret'].encode(),bytes(body),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get('x-hub-signature-256','').encode(),expected.encode()):
        raise HTTPException(401,'Invalid lead notification signature')
    try:
        payload=json.loads(body)
        if not isinstance(payload,dict) or payload.get('object')!='page' or not isinstance(payload.get('entry'),list): raise ValueError()
        identities=set()
        for entry in payload['entry']:
            if not isinstance(entry,dict) or not isinstance(entry.get('changes',[]),list): raise ValueError()
            if str(entry.get('id'))!=value['page_id']: continue
            for change in entry.get('changes',[]):
                if not isinstance(change,dict): raise ValueError()
                lead=change.get('value',{})
                if change.get('field')!='leadgen': continue
                if not isinstance(lead,dict): raise ValueError()
                if str(lead.get('form_id'))!=value['form_id'] or str(lead.get('page_id',entry['id']))!=value['page_id']: continue
                ident=lead.get('leadgen_id')
                if not isinstance(ident,(str,int)) or not str(ident) or len(str(ident))>200: raise ValueError()
                identities.add(str(ident))
    except (ValueError,TypeError,KeyError):
        raise HTTPException(422,'Invalid Page lead notification') from None
    job=db.query(ServicePolicy).filter_by(id=value['job_id'],organization_id=hook.organization_id,kind='connector_sync').with_for_update().first()
    # Job-first locking matches configure/disable and serializes receipts without
    # a hook→job / job→hook lock-order deadlock.
    db.refresh(hook)
    if not hook.values_json.get('enabled'): raise HTTPException(404,'Lead notification endpoint not found')
    accepted=0
    if job and job.values_json.get('notification_endpoint')==endpoint:
        for ident in identities:
            key='lead-wake:'+endpoint+':'+hashlib.sha256(ident.encode()).hexdigest()
            if db.query(ServicePolicy.id).filter_by(scope_key=key,organization_id=hook.organization_id,kind='lead_wake').first(): continue
            db.add(ServicePolicy(scope_key=key,organization_id=hook.organization_id,module_key='crm',kind='lead_wake',updated_by=hook.updated_by,
                values_json={'job_id':job.id,'received_at':now().isoformat()}))
            accepted+=1
        if accepted:
            job.values_json={**job.values_json,'wake_sequence':int(job.values_json.get('wake_sequence',0))+1,
                'last_notification_at':now().isoformat(),'next_at':now().isoformat()}
            job.version+=1
    db.commit()
    return {'received':True,'new_notifications':accepted}
