"""Deployment-scoped Meta webhook and authenticated connection status."""
import hashlib
import hmac
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from pydantic import BaseModel, Field, SecretStr, model_validator
from typing import Literal
from datetime import timedelta
import secrets
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_db, RequirePermission
from app.apps.crm.models import CRMMessage

router = APIRouter(prefix="/integrations/whatsapp", tags=["WhatsApp Cloud"])


@router.get("/status")
def connection_status(db: Session = Depends(get_db), user=Depends(RequirePermission("crm_view", "crm_manage", "crm_admin"))):
    from app.services import whatsapp_workspace as wa
    row = wa.connection_for(db, wa.organization(user))
    active = row is not None and row.status == 'connected'
    deployment = row is None and wa.environment_available(wa.organization(user))
    return {
        "provider": 'meta' if active or deployment else 'none',
        "configured": active or deployment,
        "connection": wa.connection_data(row) if row else None,
        "canAdmin": wa.admin(user),
        "onboardingConfigured": bool(settings.CRM_WHATSAPP_APP_ID and settings.CRM_WHATSAPP_EMBEDDED_CONFIG_ID and settings.CRM_WHATSAPP_APP_SECRET),
        "webhookConfigured": bool(settings.CRM_WHATSAPP_VERIFY_TOKEN and settings.CRM_WHATSAPP_APP_SECRET),
        "webhookPath": "/api/v1/integrations/whatsapp/webhook",
    }


@router.get("/webhook", response_class=PlainTextResponse)
def verify(request: Request):
    query = request.query_params
    expected = settings.CRM_WHATSAPP_VERIFY_TOKEN
    if not expected:
        raise HTTPException(503, "WhatsApp webhook verification is not configured")
    if query.get("hub.mode") != "subscribe" or not hmac.compare_digest(query.get("hub.verify_token", "").encode(), expected.encode()):
        raise HTTPException(403, "Invalid webhook verification")
    challenge = query.get("hub.challenge")
    if not challenge:
        raise HTTPException(400, "Missing challenge")
    return challenge


def apply_statuses(db, payload):
    rank = {"accepted": 0, "sent": 1, "delivered": 2, "read": 3}
    updated = 0
    if payload.get("object") != "whatsapp_business_account":
        return updated
    for entry in payload.get("entry", []):
        if str(entry.get("id")) != settings.CRM_WHATSAPP_BUSINESS_ACCOUNT_ID:
            continue
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if str(value.get("metadata", {}).get("phone_number_id")) != settings.CRM_WHATSAPP_PHONE_NUMBER_ID:
                continue
            for event in value.get("statuses", []):
                state = event.get("status")
                if state not in {*rank, "failed"} or not event.get("id"):
                    continue
                rows = db.query(CRMMessage).filter(
                    CRMMessage.organization_id == settings.CRM_WHATSAPP_ORGANIZATION_ID,
                    CRMMessage.channel == "whatsapp", CRMMessage.provider == "meta",
                    CRMMessage.provider_message_id == event["id"], CRMMessage.deleted_at.is_(None),
                ).with_for_update().all()
                for row in rows:
                    if state == "failed":
                        if row.status in {"accepted", "sent"}:
                            row.status = "failed"
                            row.failure_reason = "Meta reported delivery failure"
                    elif rank[state] > rank.get(row.status, -1):
                        row.status = state
                        row.failure_reason = None
                    updated += 1
    return updated


@router.post("/webhook")
async def receive(request: Request, db: Session = Depends(get_db)):
    if not settings.CRM_WHATSAPP_APP_SECRET:
        raise HTTPException(503, "WhatsApp webhook is not configured")
    body = await request.body()
    expected = "sha256=" + hmac.new(settings.CRM_WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected.encode(), request.headers.get("x-hub-signature-256", "").encode()):
        raise HTTPException(403, "Invalid webhook signature")
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError()
        apply_statuses(db, payload)
        from app.services.whatsapp_workspace import ingest
        ingest(db, payload)
    except (ValueError, TypeError, AttributeError):
        db.rollback()
        raise HTTPException(400, "Invalid webhook payload") from None
    db.commit()
    return {"status": "received"}


class ConnectionInput(BaseModel):
    wabaId: str = Field(pattern=r'^\d{3,100}$')
    phoneNumberId: str = Field(pattern=r'^\d{3,100}$')
    accessToken: SecretStr = Field(min_length=40, max_length=5000)
    registrationPin: SecretStr | None = None


class CompleteOnboarding(BaseModel):
    state: str = Field(min_length=20, max_length=200)
    code: SecretStr = Field(min_length=5, max_length=10000)
    wabaId: str = Field(pattern=r'^\d{3,100}$')
    phoneNumberId: str = Field(pattern=r'^\d{3,100}$')
    registrationPin: SecretStr | None = None


class SendInput(BaseModel):
    requestId: str = Field(min_length=10, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    to: str = Field(min_length=7, max_length=30)
    body: str = Field(default='', max_length=4096)
    template: dict | None = None
    entityType: Literal['lead','contact','deal'] | None = None
    entityId: int | None = Field(default=None, gt=0)

    @model_validator(mode='after')
    def validate_message(self):
        import re
        if bool(self.entityType) != bool(self.entityId):
            raise ValueError('Provide both CRM record type and ID')
        if self.template:
            if set(self.template)-{'name','language','components'} or not re.fullmatch(r'[a-z0-9_]{1,512}', str(self.template.get('name',''))):
                raise ValueError('Choose a valid Meta template name')
            language = self.template.get('language')
            if not isinstance(language, dict) or not re.fullmatch(r'[A-Za-z_]{2,15}', str(language.get('code',''))):
                raise ValueError('Choose a valid template language')
            if 'components' in self.template and not isinstance(self.template['components'], list):
                raise ValueError('Template components must be a list')
        return self


class ConsentInput(BaseModel):
    to: str
    status: Literal['opted_in','opted_out']
    source: str = Field(min_length=3, max_length=250)
    entityType: Literal['lead','contact','deal'] | None = None
    entityId: int | None = Field(default=None, gt=0)

    @model_validator(mode='after')
    def valid_consent(self):
        self.source = self.source.strip()
        if len(self.source) < 3 or bool(self.entityType) != bool(self.entityId):
            raise ValueError('Supply consent evidence and both CRM record fields when linking a record')
        return self


class TemplateInput(BaseModel):
    name: str = Field(pattern=r'^[a-z0-9_]{1,512}$')
    language: str = Field(pattern=r'^[A-Za-z_]{2,15}$')
    category: Literal['UTILITY','MARKETING']
    body: str = Field(min_length=1, max_length=1024)
    sampleValues: list[str] = Field(default_factory=list, max_length=20)


def pin_value(value):
    import re
    pin = value.get_secret_value() if value else None
    if pin and not re.fullmatch(r'\d{6}', pin):
        raise HTTPException(422, 'WhatsApp registration PIN must contain six digits')
    return pin


def provider_error(error):
    from app.services.whatsapp import MetaError
    if isinstance(error, MetaError):
        raise HTTPException(502, str(error)) from None
    raise error


@router.get('/profile')
def business_profile(db: Session = Depends(get_db), user=Depends(RequirePermission('crm_view','crm_manage','crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.services.whatsapp import WhatsAppGraph
    row = wa.live_connection(db,wa.organization(user))
    try:
        result = WhatsAppGraph(wa.connection_token(row)).request('GET',row.phone_number_id+'/whatsapp_business_profile',params={'fields':'profile_picture_url,about,description,address,email,websites,vertical'})
    except RuntimeError as error: provider_error(error)
    db.commit()
    profile = (result.get('data') or [{}])[0]
    return {key:profile.get(key) for key in ['profile_picture_url','about','description','address','email','websites','vertical']}


@router.post('/profile/picture')
async def update_profile_picture(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    from io import BytesIO
    from PIL import Image, UnidentifiedImageError
    from app.services import whatsapp_workspace as wa
    from app.services.whatsapp import WhatsAppGraph
    content = await file.read(2*1024*1024+1)
    await file.close()
    if len(content)>2*1024*1024:
        raise HTTPException(422,'Use a JPEG profile photo no larger than 2 MB')
    try:
        with Image.open(BytesIO(content)) as picture:
            if picture.format!='JPEG' or picture.width!=picture.height or not 192<=picture.width<=4096:
                raise ValueError()
            picture.verify()
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):
        raise HTTPException(422,'Use a square JPEG image between 192 and 4096 pixels') from None
    row = wa.live_connection(db,wa.organization(user))
    graph = WhatsAppGraph(wa.connection_token(row))
    try:
        handle=graph.upload_profile_jpeg(content)
        graph.request('POST',row.phone_number_id+'/whatsapp_business_profile',payload={'messaging_product':'whatsapp','profile_picture_handle':handle})
    except RuntimeError as error: provider_error(error)
    from app.access.service import audit
    audit(db,user,wa.organization(user),'whatsapp.profile_picture_updated','WhatsApp profile photo submitted to Meta',after={'connection_id':row.id})
    db.commit()
    return business_profile(db,user)


@router.post('/connection')
def connect(data: ConnectionInput, db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    from app.services import whatsapp_workspace as wa
    try:
        return wa.connection_data(wa.save_connection(db, user, data.accessToken.get_secret_value(), data.wabaId, data.phoneNumberId, 'manual', pin_value(data.registrationPin)))
    except RuntimeError as error:
        provider_error(error)


@router.post('/connection/environment')
def use_environment(db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    from app.services import whatsapp_workspace as wa
    if not wa.environment_available(wa.organization(user)):
        raise HTTPException(409, 'No deployment sender is assigned to this organization')
    try:
        return wa.connection_data(wa.save_connection(db, user, settings.CRM_WHATSAPP_ACCESS_TOKEN, settings.CRM_WHATSAPP_BUSINESS_ACCOUNT_ID, settings.CRM_WHATSAPP_PHONE_NUMBER_ID, 'environment'))
    except RuntimeError as error:
        provider_error(error)


@router.delete('/connection')
def disconnect(db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.shared.whatsapp_models import WhatsAppConnection, WhatsAppOnboarding
    row = wa.connection_for(db, wa.organization(user), bootstrap=True)
    if not row:
        return {'status':'disconnected'}
    # Subscriptions belong to the entire WABA, which may contain other senders.
    # A tenant disconnect must never remove another sender's provider subscription.
    remote = False
    row.token_ciphertext, row.routing_key, row.status, row.subscribed = None, None, 'disconnected', False
    for attempt in db.query(WhatsAppOnboarding).filter_by(organization_id=wa.organization(user), consumed_at=None).all():
        attempt.consumed_at = wa.now()
    from app.access.service import audit
    audit(db, user, wa.organization(user), 'whatsapp.disconnected', 'WhatsApp account disconnected', after={'connection_id':row.id,'providerUnsubscribed':remote})
    db.commit()
    return {'status':'disconnected','providerUnsubscribed':remote,'note':None if remote else 'Disconnected locally. Remove the app in Meta to finish revoking provider access.'}


@router.post('/onboarding/start')
def start_onboarding(db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.shared.whatsapp_models import WhatsAppOnboarding
    if not settings.CRM_WHATSAPP_APP_ID or not settings.CRM_WHATSAPP_EMBEDDED_CONFIG_ID or not settings.CRM_WHATSAPP_APP_SECRET:
        raise HTTPException(503, 'Meta Embedded Signup is not configured for this deployment')
    attempts = db.query(WhatsAppOnboarding).filter(WhatsAppOnboarding.organization_id == wa.organization(user), WhatsAppOnboarding.actor_id == user.id, WhatsAppOnboarding.expires_at > wa.now()).all()
    if len(attempts) >= 10:
        raise HTTPException(429, 'Too many onboarding attempts; wait ten minutes')
    state = secrets.token_urlsafe(32)
    db.add(WhatsAppOnboarding(organization_id=wa.organization(user), actor_id=user.id, state_digest=hashlib.sha256(state.encode()).hexdigest(), expires_at=wa.now()+timedelta(minutes=10)))
    db.commit()
    return {'state':state,'appId':settings.CRM_WHATSAPP_APP_ID,'configId':settings.CRM_WHATSAPP_EMBEDDED_CONFIG_ID,'apiVersion':settings.CRM_WHATSAPP_API_VERSION,'version':'v4'}


@router.post('/onboarding/complete')
def complete_onboarding(data: CompleteOnboarding, db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.shared.whatsapp_models import WhatsAppOnboarding
    from app.services.whatsapp import WhatsAppGraph
    attempt = db.query(WhatsAppOnboarding).filter_by(organization_id=wa.organization(user), actor_id=user.id, state_digest=hashlib.sha256(data.state.encode()).hexdigest(), consumed_at=None).with_for_update().first()
    if not attempt or wa.utc(attempt.expires_at) <= wa.now():
        raise HTTPException(409, 'This signup session expired or was already used; restart Connect WhatsApp')
    pin = pin_value(data.registrationPin)
    attempt.consumed_at = wa.now()
    db.commit()  # A one-use code is never automatically replayed after an uncertain exchange.
    try:
        result = WhatsAppGraph('').request('GET','oauth/access_token', params={'client_id':settings.CRM_WHATSAPP_APP_ID,'client_secret':settings.CRM_WHATSAPP_APP_SECRET,'code':data.code.get_secret_value()})
        token = result.get('access_token')
        if not isinstance(token, str) or len(token)<40:
            raise HTTPException(502, 'Meta did not return a usable account token; restart signup')
        return wa.connection_data(wa.save_connection(db, user, token, data.wabaId, data.phoneNumberId, 'embedded_signup', pin))
    except RuntimeError as error:
        provider_error(error)


@router.get('/templates')
def templates(db: Session = Depends(get_db), user=Depends(RequirePermission('crm_view','crm_manage','crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.services.whatsapp import WhatsAppGraph
    row = wa.live_connection(db, wa.organization(user))
    try:
        result = WhatsAppGraph(wa.connection_token(row)).request('GET',row.waba_id+'/message_templates',params={'fields':'id,name,status,language,category,components','limit':100})
    except RuntimeError as error:
        provider_error(error)
    db.commit()
    return {'items':result.get('data',[]),'hasMore':bool(result.get('paging',{}).get('next'))}


@router.post('/templates', status_code=201)
def create_template(data: TemplateInput, db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    import re
    from app.services import whatsapp_workspace as wa
    from app.services.whatsapp import WhatsAppGraph
    row = wa.live_connection(db, wa.organization(user))
    parameters = sorted(set(int(p) for p in re.findall(r'\{\{(\d+)\}\}', data.body)))
    if re.search(r'\{\{(?!\d+\}\})', data.body) or parameters != list(range(1,len(parameters)+1)) or len(data.sampleValues) != len(parameters):
        raise HTTPException(422, 'Supply one sample value for each sequential body placeholder {{1}}, {{2}}, …')
    component = {'type':'BODY','text':data.body}
    if parameters: component['example'] = {'body_text':[data.sampleValues]}
    try:
        result = WhatsAppGraph(wa.connection_token(row)).request('POST',row.waba_id+'/message_templates',payload={'name':data.name,'language':data.language,'category':data.category,'components':[component]})
    except RuntimeError as error:
        provider_error(error)
    from app.access.service import audit
    audit(db, user, wa.organization(user), 'whatsapp.template_created', 'Template submitted to Meta', after={'name':data.name,'language':data.language})
    db.commit()
    return result


@router.post('/messages', status_code=201)
def send(data: SendInput, db: Session = Depends(get_db), user=Depends(RequirePermission('crm_manage','crm_admin'))):
    from app.services import whatsapp_workspace as wa
    try:
        return wa.message_data(wa.send_message(db, user, data))
    except RuntimeError as error:
        provider_error(error)


@router.get('/messages/by-request/{request_id}')
def message_by_request(request_id: str, db: Session = Depends(get_db), user=Depends(RequirePermission('crm_view','crm_manage','crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.shared.whatsapp_models import WhatsAppMessage, WhatsAppContact
    row=db.query(WhatsAppMessage).filter_by(organization_id=wa.organization(user),idempotency_key=request_id,direction='outbound').first()
    if not row: raise HTTPException(404,'No recorded send found for this request')
    contact=db.query(WhatsAppContact).filter_by(id=row.contact_id,organization_id=wa.organization(user),erased_at=None).first()
    if not contact: raise HTTPException(404,'Conversation not found')
    wa.contact_access(db,user,contact)
    return wa.message_data(row)


@router.get('/messages')
def outbound_messages(before: int | None = Query(None,gt=0), limit: int = Query(50,ge=1,le=100), db: Session = Depends(get_db), user=Depends(RequirePermission('crm_view','crm_manage','crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.shared.whatsapp_models import WhatsAppMessage, WhatsAppContact
    company=wa.organization(user)
    query=db.query(WhatsAppMessage).filter_by(organization_id=company,direction='outbound')
    if before:query=query.filter(WhatsAppMessage.id<before)
    rows=query.order_by(WhatsAppMessage.id.desc()).limit(limit).all()
    items=[]
    for row in rows:
        contact=db.query(WhatsAppContact).filter_by(id=row.contact_id,organization_id=company,erased_at=None).first()
        if not contact:continue
        try:wa.contact_access(db,user,contact)
        except HTTPException as error:
            if error.status_code in {403,404}:continue
            raise
        items.append({**wa.message_data(row),'recipient':contact.recipient,'name':contact.name})
    return {'items':items,'nextBefore':rows[-1].id if len(rows)==limit else None}


@router.post('/consent')
def consent(data: ConsentInput, db: Session = Depends(get_db), user=Depends(RequirePermission('crm_manage','crm_admin'))):
    from app.services import whatsapp_workspace as wa
    row = wa.contact_for(db, wa.organization(user), wa.number(data.to))
    if data.entityType and data.entityId:
        wa.record_access(db, user, data.entityType, data.entityId)
        if not row.entity_id: row.entity_type, row.entity_id = data.entityType, data.entityId
    wa.contact_access(db, user, row)
    row.consent, row.consent_source, row.consent_at = data.status, data.source.strip(), wa.now()
    from app.access.service import audit
    audit(db, user, wa.organization(user), 'whatsapp.consent_changed', 'Recipient consent updated', after={'contact_id':row.id,'status':data.status})
    db.commit()
    return wa.contact_data(row)


@router.get('/conversations')
def conversations(before: int | None = Query(None, gt=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), user=Depends(RequirePermission('crm_view','crm_manage','crm_admin')), search: str = Query('', max_length=100), linked: bool | None = Query(None)):
    from app.services import whatsapp_workspace as wa
    from app.shared.whatsapp_models import WhatsAppContact, WhatsAppMessage
    from sqlalchemy import or_, func
    query = db.query(WhatsAppContact).filter_by(organization_id=wa.organization(user), erased_at=None)
    if search.strip():
        term=search.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        query=query.filter(or_(WhatsAppContact.name.ilike('%'+term+'%',escape='\\'),WhatsAppContact.recipient.ilike('%'+term.replace('+','').replace(' ','')+'%',escape='\\')))
    if linked is not None:
        query=query.filter(WhatsAppContact.entity_id.is_not(None) if linked else WhatsAppContact.entity_id.is_(None))
    if before: query = query.filter(WhatsAppContact.id < before)
    rows = query.order_by(WhatsAppContact.id.desc()).limit(limit).all()
    items = []
    for row in rows:
        try:
            wa.contact_access(db, user, row)
            items.append(wa.contact_data(row))
        except HTTPException as error:
            if error.status_code not in {403,404}: raise
    # One bounded query for previews, after record visibility has been checked.
    # Never fetch a preview for a contact omitted by company/branch/CRM access.
    if items:
        latest=db.query(func.max(WhatsAppMessage.id).label('id')).filter(WhatsAppMessage.organization_id==wa.organization(user),WhatsAppMessage.contact_id.in_([item['id'] for item in items])).group_by(WhatsAppMessage.contact_id).subquery()
        messages={message.contact_id:message for message in db.query(WhatsAppMessage).join(latest,WhatsAppMessage.id==latest.c.id).all()}
        for item in items:
            message=messages.get(item['id'])
            item['lastMessage']={'body':message.body[:180],'direction':message.direction,'status':message.status,'createdAt':message.created_at} if message else None
    return {'items':items,'nextBefore':rows[-1].id if len(rows)==limit else None}


@router.get('/conversations/{contact_id}/messages')
def history(contact_id: int, before: int | None = Query(None, gt=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), user=Depends(RequirePermission('crm_view','crm_manage','crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.shared.whatsapp_models import WhatsAppContact, WhatsAppMessage
    contact = db.query(WhatsAppContact).filter_by(id=contact_id, organization_id=wa.organization(user), erased_at=None).first()
    if not contact: raise HTTPException(404, 'Conversation not found')
    wa.contact_access(db, user, contact)
    query = db.query(WhatsAppMessage).filter_by(organization_id=wa.organization(user), contact_id=contact_id)
    if before: query = query.filter(WhatsAppMessage.id < before)
    rows = query.order_by(WhatsAppMessage.id.desc()).limit(limit).all()
    return {'contact':wa.contact_data(contact),'items':[wa.message_data(r) for r in reversed(rows)],'nextBefore':rows[-1].id if len(rows)==limit else None}


class LinkInput(BaseModel):
    entityType: Literal['lead','contact','deal']
    entityId: int = Field(gt=0)


class RegistrationInput(BaseModel):
    pin: SecretStr


@router.post('/connection/inbound-branch')
def configure_inbound_branch(db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    from app.services import whatsapp_workspace as wa
    context = db.info.get('branch_context')
    if not context or not context.branch_id or context.branch_id not in context.writable:
        raise HTTPException(409, 'Select a writable destination branch in the top bar first')
    row = wa.live_connection(db, wa.organization(user))
    row.inbound_branch_id = context.branch_id
    from app.access.service import audit
    audit(db,user,wa.organization(user),'whatsapp.inbound_branch','Inbound conversation branch configured',after={'connection_id':row.id,'branch_id':context.branch_id})
    db.commit()
    return wa.connection_data(row)


@router.post('/connection/check')
def check_connection(db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.services.whatsapp import WhatsAppGraph
    row = wa.connection_for(db, wa.organization(user), bootstrap=True)
    if not row or row.status == 'disconnected': raise HTTPException(409, 'Connect WhatsApp first')
    try:
        details = wa.verify_assets(wa.connection_token(row), row.waba_id, row.phone_number_id)
        row.display_number, row.business_name = details.get('display_phone_number'), details.get('verified_name')
        row.status = 'connected' if details.get('status') == 'CONNECTED' else 'registration_required'
        row.verified_at = wa.now()
        db.commit()
        return wa.connection_data(row)
    except RuntimeError as error:
        provider_error(error)


@router.post('/connection/register')
def register_phone(data: RegistrationInput, db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.services.whatsapp import WhatsAppGraph
    row = wa.connection_for(db, wa.organization(user))
    if not row or row.status == 'disconnected': raise HTTPException(409, 'Connect WhatsApp first')
    try:
        WhatsAppGraph(wa.connection_token(row)).request('POST',row.phone_number_id+'/register',payload={'messaging_product':'whatsapp','pin':pin_value(data.pin)})
        return check_connection(db, user)
    except RuntimeError as error:
        provider_error(error)


@router.post('/conversations/{contact_id}/link')
def link_conversation(contact_id: int, data: LinkInput, db: Session = Depends(get_db), user=Depends(RequirePermission('crm_admin'))):
    from app.services import whatsapp_workspace as wa
    from app.shared.whatsapp_models import WhatsAppContact
    row = db.query(WhatsAppContact).filter_by(id=contact_id, organization_id=wa.organization(user), erased_at=None).first()
    if not row: raise HTTPException(404, 'Conversation not found')
    record = wa.record_access(db, user, data.entityType, data.entityId)
    from app.branches.models import BranchOwnership
    from sqlalchemy import select
    ownership = BranchOwnership.__table__
    branch = db.connection().execute(select(ownership.c.branch_id).where(ownership.c.resource_table == record.__tablename__, ownership.c.resource_key == str(record.id), ownership.c.company_id == wa.organization(user))).scalar()
    context = db.info.get('branch_context')
    if context and (not branch or branch not in context.writable):
        raise HTTPException(403, 'The linked CRM record requires a writable branch')
    existing_branch = wa.branch_ownership(db,row)
    if existing_branch and branch and existing_branch != branch:
        raise HTTPException(409, 'Choose a CRM record in the conversation’s existing branch')
    if branch and not wa.branch_ownership(db,row):
        wa.stamp_inbound(db,row,branch)
        from app.shared.whatsapp_models import WhatsAppMessage
        for message in db.query(WhatsAppMessage).filter_by(contact_id=row.id,organization_id=wa.organization(user)).all():
            wa.stamp_inbound(db,message,branch)
    row.entity_type, row.entity_id = data.entityType, data.entityId
    db.commit()
    return wa.contact_data(row)
