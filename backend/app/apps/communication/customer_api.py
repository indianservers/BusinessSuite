"""Tenant/branch-scoped customer communication administration."""
from datetime import date, datetime, timedelta
from hashlib import sha256
import secrets
import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.access.service import primary_company
from .customer_models import (CustomerRecipient, CustomerBinding, CustomerCommunicationSettings, CustomerAutomation,
    CustomerDelivery, CustomerShipment, CustomerPreferenceToken, CustomerConversationNote)
from . import customer_service as service

router = APIRouter(prefix='/communication/customers', tags=['Customer communication'])
public_router = APIRouter(prefix='/public/customer-preferences', tags=['Customer preferences'])
view = RequirePermission('communication_view')
manage = RequirePermission('communication_email_send')
campaign = RequirePermission('communication_campaigns_send')
admin = RequirePermission('crm_admin')


def serialize(obj):
    return {c.name: (getattr(obj, c.name).isoformat() if isinstance(getattr(obj, c.name), (date, datetime)) else getattr(obj, c.name)) for c in obj.__table__.columns}


def company(user):
    return getattr(user, 'organization_id', None) or primary_company(user)


def branch(db):
    context = db.info.get('branch_context')
    if not context or not context.branch_id or context.branch_id not in context.writable:
        raise HTTPException(403, 'Select a writable branch')
    return context.branch_id


def get(db, model, identity, user):
    row = db.query(model).filter_by(id=identity, organization_id=company(user)).first()
    if not row:
        raise HTTPException(404, 'Record not found in this company and branch')
    return row


def audit(db, user, operation, details):
    from app.branches.service import audit as record
    record(db, user, company(user), 'customer_communication.'+operation, operation, details)


class RecipientInput(BaseModel):
    name: str = Field(min_length=1, max_length=220)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=60)
    crm_contact_id: int | None = Field(default=None, gt=0)
    role: Literal['service', 'billing', 'delivery', 'primary'] = 'service'
    language: str = Field(default='en', min_length=2, max_length=20)
    timezone: str = 'Asia/Kolkata'
    preferred_channel: Literal['email', 'whatsapp'] = 'email'
    birthday: date | None = None
    anniversary: date | None = None
    active: bool = True
    preferences: dict[str, bool] = Field(default_factory=dict)
    consent_source: str = Field(min_length=1, max_length=240)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip() or '\r' in value or '\n' in value:
            raise ValueError('Customer name must be nonempty and contain no line breaks')
        return value.strip()

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Choose a valid IANA timezone')
        return value

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        if value:
            from .services.delivery import validate_email
            try:
                validate_email(value.strip().lower())
            except HTTPException:
                raise ValueError('Enter a valid email address')
            return value.strip().lower()
        return None

    @field_validator('phone')
    @classmethod
    def valid_phone(cls, value):
        if value and not re.fullmatch(r'\+[1-9]\d{7,14}', value):
            raise ValueError('Use an international phone number, for example +919876543210')
        return value

    @field_validator('preferences')
    @classmethod
    def valid_preferences(cls, value):
        if set(value) - {c+'.'+p for c in ['email', 'whatsapp'] for p in ['transactional', 'marketing', 'greeting']}:
            raise ValueError('Unknown communication purpose')
        return value

    @model_validator(mode='after')
    def reachable(self):
        if not self.email and not self.phone:
            raise ValueError('Provide an email address or phone number')
        return self


@router.get('/recipients')
def recipients(search: str = Query('', max_length=160), db: Session = Depends(get_db), user=Depends(view)):
    query = db.query(CustomerRecipient).filter_by(organization_id=company(user))
    if search:
        query = query.filter(CustomerRecipient.name.ilike('%'+search+'%'))
    return {'items': [serialize(r) for r in query.order_by(CustomerRecipient.id.desc()).limit(500)]}


def save_recipient(db, user, data, row=None):
    creating = row is None
    from app.services.email_schedules import permitted
    old_preferences = row.preferences or {} if row else {}
    if any(value and old_preferences.get(key) is not True for key, value in data.preferences.items()) and not (user.is_superuser or permitted(user, 'communication_consents_manage')):
        raise HTTPException(403, 'Consent management permission is required to record a new opt-in')
    if data.crm_contact_id:
        from app.apps.crm.models import CRMContact
        get(db, CRMContact, data.crm_contact_id, user)
    if row is None:
        row = CustomerRecipient(organization_id=company(user), branch_id=branch(db), created_by=user.id)
        db.add(row)
    if service.config(db, company(user)) is None:
        # Company-level lock used to serialize quota reservations across workers.
        from app.core.request_limits import insert_for
        # Trusted singleton provisioning: all values are fixed and the company
        # comes from the verified request context, never a submitted identifier.
        db.connection().execute(insert_for(db, CustomerCommunicationSettings).values(organization_id=company(user),
            paused=False, daily_limit=1000, customer_daily_limit=5, bulk_approval_threshold=50).on_conflict_do_nothing(
                index_elements=['organization_id']))
    history = list(row.consent_history or [])
    history.append({'at': service.now().isoformat(), 'actor': user.id, 'source': data.consent_source, 'preferences': data.preferences})
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    row.consent_at, row.consent_history = service.now(), history[-100:]
    db.flush()
    if row.phone:
        from app.services import whatsapp_workspace as wa
        contact = wa.contact_for(db, company(user), wa.number(row.phone))
        wa.contact_access(db, user, contact) if contact.entity_id else None
        if row.crm_contact_id and not contact.entity_id:
            contact.entity_type, contact.entity_id = 'contact', row.crm_contact_id
        contact.consent = 'opted_in' if any(data.preferences.get('whatsapp.'+p) for p in ['transactional', 'marketing', 'greeting']) else 'opted_out'
        contact.consent_source, contact.consent_at = data.consent_source, service.now()
    if creating:
        for rule in db.query(CustomerAutomation).filter_by(organization_id=company(user), branch_id=row.branch_id, trigger='welcome', status='active'):
            for step, delay in enumerate(rule.steps):
                service.queue_delivery(db, row, key=f'welcome:{rule.id}:{rule.version}:{row.id}:{step}', kind='recipient', identity=row.id,
                    snapshot={}, actor=rule.created_by, rule=rule, due_at=service.now()+timedelta(minutes=delay))
    audit(db, user, 'recipient_preferences', {'recipient_id': row.id, 'preferences': data.preferences})
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.post('/recipients', status_code=201)
def create_recipient(data: RecipientInput, db: Session = Depends(get_db), user=Depends(manage)):
    return save_recipient(db, user, data)


@router.put('/recipients/{identity}')
def update_recipient(identity: int, data: RecipientInput, db: Session = Depends(get_db), user=Depends(manage)):
    return save_recipient(db, user, data, get(db, CustomerRecipient, identity, user))


class BindingInput(BaseModel):
    source_type: Literal['contact', 'order', 'invoice', 'service', 'follow_up', 'contract', 'lead', 'meeting', 'quotation', 'shipment']
    source_id: int = Field(gt=0)


def authorized_source(db, user, kind, identity):
    from app.access.catalog import permission_objects
    from app.access.service import effective_objects
    grants = getattr(user, '_suite_grants', None)
    names = {p.name for p in (effective_objects(db, grants) if grants is not None else permission_objects(user))}
    module = 'srm' if kind in {'order', 'invoice', 'service', 'contract', 'shipment'} else 'crm'
    if kind == 'follow_up' and any(p.startswith('srm_') for p in names):
        module = 'srm'
    if not user.is_superuser and not any(p == module+'_admin' or p.startswith(module+'_') and ('view' in p or 'manage' in p) for p in names):
        raise HTTPException(403, 'Source module access is required')
    if kind == 'contact':
        from app.apps.crm.models import CRMContact
        return get(db, CRMContact, identity, user)
    obj = service.source(db, kind, identity, company(user))
    if not obj:
        raise HTTPException(404, 'Business record not found in this company and branch')
    if kind == 'follow_up':
        from app.shared.follow_ups import visible, FollowUp
        if not visible(db, user).filter(FollowUp.id == identity).first():
            raise HTTPException(404, 'Service follow-up not found')
    if kind == 'invoice':
        from app.apps.srm.services.commercial import invoice_query
        from app.apps.srm.models import SRMInvoice
        if not invoice_query(db, user).filter(SRMInvoice.id == identity).first():
            raise HTTPException(404, 'Invoice not found')
    return obj


@router.get('/recipients/{identity}/bindings')
def bindings(identity: int, db: Session = Depends(get_db), user=Depends(view)):
    get(db, CustomerRecipient, identity, user)
    return {'items': [serialize(r) for r in db.query(CustomerBinding).filter_by(organization_id=company(user), recipient_id=identity)]}


@router.post('/recipients/{identity}/bindings', status_code=201)
def bind(identity: int, data: BindingInput, db: Session = Depends(get_db), user=Depends(manage)):
    recipient = get(db, CustomerRecipient, identity, user)
    authorized_source(db, user, data.source_type, data.source_id)
    if data.source_type == 'contact':
        recipient.crm_contact_id = data.source_id
        if recipient.phone:
            from app.services import whatsapp_workspace as wa
            contact = wa.contact_for(db, company(user), wa.number(recipient.phone))
            if contact.entity_id and (contact.entity_type, contact.entity_id) != ('contact', data.source_id):
                raise HTTPException(409, 'WhatsApp conversation is already linked; review its existing CRM link before changing it')
            contact.entity_type, contact.entity_id = 'contact', data.source_id
    row = db.query(CustomerBinding).filter_by(organization_id=company(user), recipient_id=identity, **data.model_dump()).first()
    if row:
        return serialize(row)
    row = CustomerBinding(organization_id=company(user), branch_id=recipient.branch_id, recipient_id=identity, **data.model_dump())
    db.add(row)
    audit(db, user, 'bind', {'recipient_id': identity, **data.model_dump()})
    db.commit()
    return serialize(row)


@router.delete('/bindings/{identity}')
def unbind(identity: int, db: Session = Depends(get_db), user=Depends(manage)):
    row = get(db, CustomerBinding, identity, user)
    audit(db, user, 'unbind', {'id': identity})
    db.delete(row)
    db.commit()
    return {'deleted': True}


class RuleInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    trigger: str
    purpose: Literal['transactional', 'marketing', 'greeting'] = 'transactional'
    channel: Literal['email', 'whatsapp'] = 'email'
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=10000)
    whatsapp_template: dict | None = None
    conditions: dict = Field(default_factory=dict)
    steps: list[int] = Field(default_factory=lambda: [0], min_length=1, max_length=10)
    quiet_start: int = Field(default=20, ge=0, le=23)
    quiet_end: int = Field(default=8, ge=0, le=23)
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)), min_length=1, max_length=7)
    stop_on_reply: bool = True
    status: Literal['draft', 'active', 'paused'] = 'draft'

    @model_validator(mode='after')
    def valid(self):
        if '\r' in self.subject or '\n' in self.subject:
            raise ValueError('Subject must contain no line breaks')
        if self.trigger not in service.TRIGGERS:
            raise ValueError('Unknown automation trigger')
        if self.trigger in {'birthday', 'anniversary', 'greeting'} and self.purpose != 'greeting':
            raise ValueError('Birthday and anniversary automations require greeting consent')
        if self.trigger == 'campaign' and self.purpose != 'marketing':
            raise ValueError('Campaigns require marketing consent')
        if any(type(v) is not int or v < 0 or v > 525600 for v in self.steps) or sorted(set(self.steps)) != self.steps:
            raise ValueError('Steps must be distinct increasing delays in minutes, between 0 and 525600')
        if any(type(v) is not int or v < 0 or v > 6 for v in self.weekdays):
            raise ValueError('Weekdays must be between 0 (Monday) and 6 (Sunday)')
        if set(self.conditions) - {'statuses', 'roles', 'days_before'}:
            raise ValueError('Unsupported automation condition')
        for field in ['statuses', 'roles']:
            if field in self.conditions and (not isinstance(self.conditions[field], list) or len(self.conditions[field]) > 30 or any(not isinstance(v, str) or len(v) > 80 for v in self.conditions[field])):
                raise ValueError(field+' must be a list of text values')
        days = self.conditions.get('days_before', 0)
        if type(days) is not int or not -365 <= days <= 365:
            raise ValueError('days_before must be between -365 and 365')
        for text in [self.subject, self.body]:
            variables = re.findall(r'\{\{\s*([^{}]+)\s*\}\}', text)
            if any(v.strip() not in service.FIELDS for v in variables):
                raise ValueError('Unsupported template variable')
        if self.channel == 'whatsapp' and self.status == 'active':
            if not self.whatsapp_template or not self.whatsapp_template.get('name') or not isinstance(self.whatsapp_template.get('language'), dict) or not self.whatsapp_template['language'].get('code'):
                raise ValueError('Choose a WhatsApp template and language')
        return self


@router.get('/automations')
def rules(db: Session = Depends(get_db), user=Depends(view)):
    return {'items': [serialize(r) for r in db.query(CustomerAutomation).filter_by(organization_id=company(user)).order_by(CustomerAutomation.id.desc()).limit(500)],
            'triggers': service.TRIGGERS, 'variables': sorted(service.FIELDS)}


def save_rule(db, user, data, row=None):
    from app.services.email_schedules import permitted
    if data.purpose != 'transactional' and not (user.is_superuser or permitted(user, 'communication_campaigns_send')):
        raise HTTPException(403, 'Campaign send permission is required')
    if row is None:
        row = CustomerAutomation(organization_id=company(user), branch_id=branch(db), created_by=user.id, version=1)
        db.add(row)
    else:
        row.version += 1
        # Editing transfers responsibility to the currently authorized owner.
        row.created_by = user.id
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    from .customer_models import CustomerEvent
    from sqlalchemy import func
    row.activation_event_id = db.query(func.max(CustomerEvent.id)).filter_by(organization_id=company(user)).scalar() or 0
    audit(db, user, 'automation', {'id': row.id, 'status': data.status, 'version': row.version})
    db.commit()
    return serialize(row)


@router.post('/automations', status_code=201)
def create_rule(data: RuleInput, db: Session = Depends(get_db), user=Depends(manage)):
    return save_rule(db, user, data)


@router.put('/automations/{identity}')
def update_rule(identity: int, data: RuleInput, db: Session = Depends(get_db), user=Depends(manage)):
    return save_rule(db, user, data, get(db, CustomerAutomation, identity, user))


class PreviewInput(BaseModel):
    recipient_ids: list[int] = Field(default_factory=list, max_length=1000)
    scheduled_at: datetime | None = None
    approve_bulk: bool = False


def audience(db, user, rule, data):
    query = db.query(CustomerRecipient).filter_by(organization_id=company(user), branch_id=rule.branch_id, active=True)
    if data.recipient_ids:
        query = query.filter(CustomerRecipient.id.in_(data.recipient_ids))
    if rule.conditions.get('roles'):
        query = query.filter(CustomerRecipient.role.in_(rule.conditions['roles']))
    eligible, excluded = [], []
    for recipient in query.order_by(CustomerRecipient.id).limit(1000):
        (eligible if service.preference_allowed(db, recipient, rule.channel, rule.purpose) else excluded).append(recipient)
    return eligible, excluded


@router.post('/automations/{identity}/preview')
def preview(identity: int, data: PreviewInput, db: Session = Depends(get_db), user=Depends(view)):
    rule = get(db, CustomerAutomation, identity, user)
    eligible, excluded = audience(db, user, rule, data)
    sample = None
    error = None
    if eligible:
        try:
            context = service.template_values(eligible[0], {})
            sample = {'subject': service.render(rule.subject, context), 'body': service.render(rule.body, context)}
        except ValueError as exc:
            error = str(exc)+'; source event values are available when the event occurs'
    return {'eligible': len(eligible), 'excluded': len(excluded), 'channel': rule.channel,
            'sample': sample, 'sample_error': error, 'usage_estimate': len(eligible)*len(rule.steps),
            'estimated_cost': None, 'cost_note': 'Provider pricing is not configured; usage is a message estimate'}


@router.post('/automations/{identity}/launch')
def launch(identity: int, data: PreviewInput, db: Session = Depends(get_db), user=Depends(campaign)):
    rule = get(db, CustomerAutomation, identity, user)
    if rule.trigger not in {'campaign', 'greeting', 'welcome'} or rule.status != 'active':
        raise HTTPException(409, 'Only active campaign, greeting or welcome rules can be launched manually')
    eligible, excluded = audience(db, user, rule, data)
    settings = service.config(db, company(user))
    if settings and settings.paused:
        raise HTTPException(409, 'Business communications are paused')
    threshold = settings.bulk_approval_threshold if settings else 50
    if len(eligible)*len(rule.steps) > threshold:
        from app.services.email_schedules import permitted
        if not data.approve_bulk or not (user.is_superuser or permitted(user, 'crm_admin')):
            raise HTTPException(409, 'CRM administrator approval is required above the bulk threshold')
    scheduled = data.scheduled_at or service.now()
    if scheduled.tzinfo is None:
        raise HTTPException(422, 'Schedule must include a timezone offset')
    # One launch per rule version; editing intentionally creates a new campaign version.
    queued = 0
    for recipient in eligible:
        for step, delay in enumerate(rule.steps):
            queued += bool(service.queue_delivery(db, recipient, key=f'launch:{rule.id}:{rule.version}:{recipient.id}:{step}',
                kind='campaign', identity=rule.id, snapshot={}, actor=user.id, rule=rule,
                due_at=scheduled+timedelta(minutes=delay)))
    audit(db, user, 'launch', {'rule_id': identity, 'queued': queued, 'excluded': len(excluded), 'bulk_approved': data.approve_bulk})
    db.commit()
    return {'queued': queued, 'excluded': len(excluded)}


@router.get('/deliveries')
def deliveries(status: str | None = None, recipient_id: int | None = None, db: Session = Depends(get_db), user=Depends(view)):
    query = db.query(CustomerDelivery).filter_by(organization_id=company(user))
    if status:
        query = query.filter_by(status=status)
    if recipient_id:
        query = query.filter_by(recipient_id=recipient_id)
    return {'items': [serialize(r) for r in query.order_by(CustomerDelivery.id.desc()).limit(250)]}


@router.post('/deliveries/{identity}/cancel')
def cancel_delivery(identity: int, db: Session = Depends(get_db), user=Depends(manage)):
    row = get(db, CustomerDelivery, identity, user)
    if row.status not in {'queued', 'blocked', 'waiting_provider'}:
        raise HTTPException(409, 'Delivery has already crossed the provider boundary')
    if row.email_outbox_id:
        from app.models.email_outbox import EmailOutbox
        outbox = db.query(EmailOutbox).filter_by(id=row.email_outbox_id, status='queued').with_for_update().first()
        if not outbox:
            raise HTTPException(409, 'Provider processing has started')
        outbox.status = 'cancelled'
    row.status = 'cancelled'
    service.sync_delivery(db, row)
    audit(db, user, 'cancel', {'delivery_id': identity})
    db.commit()
    return serialize(row)


@router.post('/deliveries/{identity}/retry')
def retry_delivery(identity: int, db: Session = Depends(get_db), user=Depends(manage)):
    row = get(db, CustomerDelivery, identity, user)
    if row.status == 'failed' and row.email_outbox_id:
        from app.models.email_outbox import EmailOutbox
        outbox = db.query(EmailOutbox).filter_by(id=row.email_outbox_id, organization_id=company(user), status='failed').with_for_update().first()
        if not outbox or outbox.attempts >= 5:
            raise HTTPException(409, 'Retry limit reached or provider outcome requires reconciliation')
        outbox.status, outbox.error = 'retry_wait', None
        row.status, row.error, row.due_at = 'retry_wait', None, service.now()
        audit(db, user, 'retry_rejected_email', {'delivery_id': identity})
        db.commit()
        return serialize(row)
    if row.status == 'failed' and row.whatsapp_message_id:
        from app.shared.whatsapp_models import WhatsAppMessage
        message = db.get(WhatsAppMessage, row.whatsapp_message_id)
        if not message or message.provider_message_id or row.attempts >= 5:
            raise HTTPException(409, 'Reconcile the provider delivery outcome before retrying')
        row.whatsapp_message_id = None
        row.status, row.error, row.due_at = 'queued', None, service.now()
        audit(db, user, 'retry_rejected_whatsapp', {'delivery_id': identity})
        db.commit()
        return serialize(row)
    if row.status != 'blocked' or row.email_outbox_id or row.whatsapp_message_id:
        raise HTTPException(409, 'Only blocked messages that have not reached a provider may be retried; reconcile uncertain outcomes first')
    row.status, row.error, row.due_at = 'queued', None, service.now()
    audit(db, user, 'retry', {'delivery_id': identity})
    db.commit()
    return serialize(row)


class SettingsInput(BaseModel):
    paused: bool = False
    daily_limit: int = Field(default=1000, ge=1, le=100000)
    customer_daily_limit: int = Field(default=5, ge=1, le=100)
    bulk_approval_threshold: int = Field(default=50, ge=1, le=10000)


@router.get('/settings')
def read_settings(db: Session = Depends(get_db), user=Depends(view)):
    row = service.config(db, company(user))
    return serialize(row) if row else SettingsInput().model_dump()


@router.put('/settings')
def write_settings(data: SettingsInput, db: Session = Depends(get_db), user=Depends(admin)):
    row = service.config(db, company(user))
    if not row:
        row = CustomerCommunicationSettings(organization_id=company(user))
        db.add(row)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    row.updated_by = user.id
    audit(db, user, 'settings', data.model_dump())
    db.commit()
    return serialize(row)


@router.get('/dashboard')
def dashboard(db: Session = Depends(get_db), user=Depends(view)):
    from sqlalchemy import func
    counts = dict(db.query(CustomerDelivery.status, func.count(CustomerDelivery.id)).filter_by(organization_id=company(user)).group_by(CustomerDelivery.status).all())
    from .customer_models import CustomerEmailConnection
    inbox = db.query(CustomerEmailConnection).filter_by(organization_id=company(user), active=True).first()
    return {'statuses': counts, 'recipients': db.query(CustomerRecipient).filter_by(organization_id=company(user)).count(),
            'active_automations': db.query(CustomerAutomation).filter_by(organization_id=company(user), status='active').count(),
            'email_reply_ingestion': bool(inbox and inbox.inbound_secret_ciphertext), 'note': 'Email acceptance is not confirmed delivery. WhatsApp replies and configured email receiver events appear in customer history.'}


class ShipmentInput(BaseModel):
    sales_order_id: int = Field(gt=0)
    reference: str = Field(min_length=1, max_length=120)
    status: Literal['ready', 'dispatched', 'out_for_delivery', 'rescheduled', 'exception', 'delivered', 'failed_delivery', 'returned'] = 'ready'
    carrier: str | None = Field(default=None, max_length=160)
    tracking_url: str | None = Field(default=None, max_length=1000)
    expected_date: date | None = None

    @field_validator('tracking_url')
    @classmethod
    def safe_url(cls, value):
        from urllib.parse import urlsplit
        if value:
            parsed = urlsplit(value)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Tracking link must be an HTTPS URL without credentials')
        return value


@router.get('/shipments')
def shipments(db: Session = Depends(get_db), user=Depends(view)):
    return {'items': [serialize(r) for r in db.query(CustomerShipment).filter_by(organization_id=company(user)).order_by(CustomerShipment.id.desc()).limit(250)]}


def save_shipment(db, user, data, row=None):
    authorized_source(db, user, 'order', data.sales_order_id)
    if row is None:
        row = CustomerShipment(organization_id=company(user), branch_id=branch(db), created_by=user.id)
        db.add(row)
    elif row.sales_order_id != data.sales_order_id:
        raise HTTPException(409, 'Shipment order cannot change')
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    audit(db, user, 'shipment', {'id': row.id, 'status': data.status})
    db.commit()
    return serialize(row)


@router.post('/shipments', status_code=201)
def create_shipment(data: ShipmentInput, db: Session = Depends(get_db), user=Depends(manage)):
    return save_shipment(db, user, data)


@router.put('/shipments/{identity}')
def update_shipment(identity: int, data: ShipmentInput, db: Session = Depends(get_db), user=Depends(manage)):
    return save_shipment(db, user, data, get(db, CustomerShipment, identity, user))


class NoteInput(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    assigned_user_id: int | None = None
    follow_up_at: datetime | None = None


@router.post('/recipients/{identity}/notes', status_code=201)
def add_note(identity: int, data: NoteInput, db: Session = Depends(get_db), user=Depends(manage)):
    recipient = get(db, CustomerRecipient, identity, user)
    if data.assigned_user_id:
        from app.models.user import User
        from app.core.tenant_boundary import company_ids
        assignee = db.get(User, data.assigned_user_id)
        from app.branches.service import access
        if not assignee or not assignee.is_active or company(user) not in company_ids(db, assignee) or recipient.branch_id not in access(db, assignee, company(user))[0]:
            raise HTTPException(422, 'Assignee must belong to this company and branch')
    row = CustomerConversationNote(organization_id=company(user), branch_id=recipient.branch_id,
        recipient_id=identity, created_by=user.id, **data.model_dump())
    db.add(row)
    db.commit()
    return serialize(row)


@router.get('/recipients/{identity}/history')
def history(identity: int, db: Session = Depends(get_db), user=Depends(view)):
    recipient = get(db, CustomerRecipient, identity, user)
    from app.shared.whatsapp_models import WhatsAppContact, WhatsAppMessage
    messages = []
    if recipient.phone:
        contact = db.query(WhatsAppContact).filter_by(organization_id=company(user), recipient=recipient.phone.lstrip('+')).first()
        if contact:
            messages = [serialize(r) for r in db.query(WhatsAppMessage).filter_by(organization_id=company(user), contact_id=contact.id).order_by(WhatsAppMessage.id.desc()).limit(100)]
    from .customer_models import CustomerEmailReply, CustomerEmailConnection
    replies = db.query(CustomerEmailReply).filter_by(organization_id=company(user), recipient_id=identity).order_by(CustomerEmailReply.id.desc()).limit(100).all()
    inbox = db.query(CustomerEmailConnection).filter_by(organization_id=company(user), active=True).first()
    return {'deliveries': [serialize(r) for r in db.query(CustomerDelivery).filter_by(organization_id=company(user), recipient_id=identity).order_by(CustomerDelivery.id.desc()).limit(100)],
            'email_replies': [serialize(r) for r in replies], 'unread_email_count': sum(1 for r in replies if not recipient.last_read_at or service.utc(r.received_at) > service.utc(recipient.last_read_at)),
            'assigned_user_id': recipient.assigned_user_id,
            'whatsapp': messages, 'internal_notes': [serialize(r) for r in db.query(CustomerConversationNote).filter_by(organization_id=company(user), recipient_id=identity).order_by(CustomerConversationNote.id.desc()).limit(100)],
            'email_reply_ingestion': bool(inbox and inbox.inbound_secret_ciphertext)}


class AssignmentInput(BaseModel):
    assigned_user_id: int | None = None


@router.post('/recipients/{identity}/assignment')
def assign(identity: int, data: AssignmentInput, db: Session = Depends(get_db), user=Depends(manage)):
    recipient = get(db, CustomerRecipient, identity, user)
    if data.assigned_user_id:
        from app.models.user import User
        from app.core.tenant_boundary import company_ids
        from app.branches.service import access
        assignee = db.get(User, data.assigned_user_id)
        if not assignee or not assignee.is_active or company(user) not in company_ids(db, assignee) or recipient.branch_id not in access(db, assignee, company(user))[0]:
            raise HTTPException(422, 'Assignee must belong to this company and branch')
    recipient.assigned_user_id = data.assigned_user_id
    audit(db, user, 'assign', {'recipient_id':identity, 'assigned_user_id':data.assigned_user_id})
    db.commit()
    return {'assigned_user_id': data.assigned_user_id}


@router.post('/recipients/{identity}/read')
def mark_read(identity: int, db: Session = Depends(get_db), user=Depends(view)):
    recipient = get(db, CustomerRecipient, identity, user)
    recipient.last_read_at = service.now()
    db.commit()
    return {'read': True}


@router.post('/recipients/{identity}/preference-link')
def preference_link(identity: int, db: Session = Depends(get_db), user=Depends(manage)):
    recipient = get(db, CustomerRecipient, identity, user)
    token = secrets.token_urlsafe(32)
    # Reissuing a link revokes older links.
    for old in db.query(CustomerPreferenceToken).filter_by(recipient_id=identity, organization_id=company(user), revoked=False):
        old.revoked = True
    db.add(CustomerPreferenceToken(digest=sha256(token.encode()).hexdigest(), organization_id=company(user),
        recipient_id=recipient.id, expires_at=service.now()+timedelta(days=30)))
    db.commit()
    from app.core.config import settings
    return {'url': settings.BACKEND_PUBLIC_URL.rstrip('/')+'/api/v1/public/customer-preferences/'+token,
            'expires_in_days': 30}


def public_recipient(db, token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{40,64}', token):
        raise HTTPException(404, 'Preference link is invalid or expired')
    from app.core.request_limits import consume
    if consume(db, [('customer-preferences:'+sha256(token.encode()).hexdigest(), 60, 60)]):
        db.commit()
        raise HTTPException(429, 'Please wait before opening this preference link again')
    row = db.get(CustomerPreferenceToken, sha256(token.encode()).hexdigest())
    if not row or row.revoked or service.utc(row.expires_at) <= service.now():
        raise HTTPException(404, 'Preference link is invalid or expired')
    recipient = db.query(CustomerRecipient).filter_by(id=row.recipient_id, organization_id=row.organization_id).first()
    if not recipient:
        raise HTTPException(404, 'Preference link is invalid or expired')
    return recipient


class EmailConnectionInput(BaseModel):
    host: str = Field(min_length=3, max_length=254, pattern=r'^[A-Za-z0-9.-]+$')
    port: Literal[465, 587] = 587
    username: str = Field(min_length=1, max_length=254)
    password: str | None = Field(default=None, min_length=1, max_length=2000)
    from_email: str = Field(max_length=254)
    from_name: str = Field(min_length=1, max_length=180)
    reply_to: str | None = Field(default=None, max_length=254)
    active: bool = True

    @field_validator('from_email', 'reply_to')
    @classmethod
    def address(cls, value):
        if value:
            RecipientInput.valid_email(value)
        return value

    @field_validator('username', 'from_name')
    @classmethod
    def no_headers(cls, value):
        if '\r' in value or '\n' in value:
            raise ValueError('Line breaks are not allowed')
        return value


@router.get('/email-connection')
def email_connection(db: Session = Depends(get_db), user=Depends(admin)):
    from .customer_models import CustomerEmailConnection
    row = db.query(CustomerEmailConnection).filter_by(organization_id=company(user)).first()
    if not row:
        from app.core.email import email_configured
        return {'configured': email_configured(), 'source': 'suite', 'credentials_configured': False}
    return {key: getattr(row, key) for key in ['host', 'port', 'username', 'from_email', 'from_name', 'reply_to', 'active']} | {'configured': row.active, 'source': 'business', 'credentials_configured': bool(row.password_ciphertext)}


@router.put('/email-connection')
def save_email_connection(data: EmailConnectionInput, db: Session = Depends(get_db), user=Depends(admin)):
    from .customer_models import CustomerEmailConnection
    from app.shared.integrations import protect
    row = db.query(CustomerEmailConnection).filter_by(organization_id=company(user)).first()
    if not row:
        if not data.password:
            raise HTTPException(422, 'SMTP password is required')
        row = CustomerEmailConnection(organization_id=company(user))
        db.add(row)
    for key, value in data.model_dump(exclude={'password'}).items():
        setattr(row, key, value)
    if data.password:
        row.password_ciphertext = protect(data.password)
    row.updated_by = user.id
    audit(db, user, 'email_connection', {'host': data.host, 'active': data.active})
    db.commit()
    return {'configured': data.active, 'source': 'business', 'credentials_configured': True}


@router.post('/email-connection/receiver-secret')
def rotate_receiver_secret(db: Session = Depends(get_db), user=Depends(admin)):
    from .customer_models import CustomerEmailConnection
    from app.shared.integrations import protect
    row = db.query(CustomerEmailConnection).filter_by(organization_id=company(user), active=True).first()
    if not row:
        raise HTTPException(409, 'Configure business SMTP before enabling the email receiver')
    secret = secrets.token_urlsafe(48)
    row.inbound_secret_ciphertext = protect(secret)
    audit(db, user, 'rotate_email_receiver', {'company_id': company(user)})
    db.commit()
    from app.core.config import settings
    return {'secret': secret, 'webhook_url': settings.BACKEND_PUBLIC_URL.rstrip('/')+'/api/v1/integrations/customer-email/'+str(company(user)),
            'instructions': 'Configure your receiving-service adapter to verify sender authentication, then sign timestamp + dot + raw JSON with HMAC-SHA256. This secret is shown once; rotating it revokes the previous secret.'}


@public_router.get('/{token}')
def public_preferences(token: str, db: Session = Depends(get_db)):
    from fastapi.responses import HTMLResponse
    from html import escape
    recipient = public_recipient(db, token)
    # Capability grants withdrawal only; no PII or opt-in controls are exposed.
    return HTMLResponse('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Communication preferences</title></head>'
        '<body><main style="max-width:36rem;margin:4rem auto;font-family:system-ui;padding:1rem"><h1>Communication preferences</h1>'
        '<p>Stop promotional and greeting messages from this business. Service updates remain controlled separately.</p>'
        '<form method="post"><button type="submit">Unsubscribe from promotions and greetings</button></form></main></body></html>',
        headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"})


@public_router.post('/{token}')
def public_unsubscribe(token: str, db: Session = Depends(get_db)):
    from fastapi.responses import HTMLResponse
    recipient = public_recipient(db, token)
    preferences = dict(recipient.preferences or {})
    for channel in ['email', 'whatsapp']:
        for purpose in ['marketing', 'greeting']:
            preferences[channel+'.'+purpose] = False
    recipient.preferences = preferences
    recipient.consent_history = [*(recipient.consent_history or []), {'at': service.now().isoformat(), 'source': 'customer_preference_link', 'preferences': preferences}][-100:]
    recipient.consent_at = service.now()
    db.commit()
    return HTMLResponse('<h1>You are unsubscribed</h1><p>Promotional and greeting messages have been stopped.</p>', headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
