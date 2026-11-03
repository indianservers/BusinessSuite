"""Tenant-safe WhatsApp onboarding, consent, durable sends, and webhook ingestion."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import secrets
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.services.whatsapp import WhatsAppGraph, MetaWhatsAppProvider, MetaError
from app.shared.integrations import protect, reveal
from app.shared.whatsapp_models import WhatsAppConnection, WhatsAppContact, WhatsAppMessage, WhatsAppReceipt


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def organization(user):
    from app.apps.srm.services.commercial import tenant
    return tenant(user)


def admin(user):
    from app.access.catalog import permission_names
    return bool(user.is_superuser or 'crm_admin' in permission_names(user))


def number(value):
    result = re.sub(r'[\s()+-]', '', str(value))
    if not re.fullmatch(r'[1-9]\d{6,14}', result):
        raise HTTPException(422, 'Enter a full international WhatsApp number including country code')
    return result


def record_access(db, user, entity, entity_id):
    if entity not in {'lead', 'contact', 'deal'} or not entity_id:
        raise HTTPException(422, 'Choose a lead, contact or deal')
    from app.apps.crm.api.router import _get_record, _get_resource, _assert_record_visible
    resource = _get_resource({'lead':'leads','contact':'contacts','deal':'deals'}[entity])
    record = _get_record(db, resource, entity_id, organization(user))
    _assert_record_visible(db, resource, entity_id, organization(user), user)
    return record


def contact_access(db, user, contact):
    if contact.organization_id != organization(user):
        raise HTTPException(404, 'Conversation not found')
    if contact.entity_type and contact.entity_id:
        record_access(db, user, contact.entity_type, contact.entity_id)
    elif not admin(user):
        raise HTTPException(403, 'An administrator must link this conversation to a CRM record first')


def contact_for(db, company, recipient):
    row = db.query(WhatsAppContact).filter_by(organization_id=company, recipient=recipient).with_for_update().first()
    if row:
        return row
    try:
        with db.begin_nested():
            row = WhatsAppContact(organization_id=company, recipient=recipient, consent='unknown')
            db.add(row)
            db.flush()
        return row
    except IntegrityError:
        row = db.query(WhatsAppContact).filter_by(organization_id=company, recipient=recipient).with_for_update().first()
        if not row:
            raise HTTPException(409, 'Recipient is outside the selected branch; choose its authorized branch') from None
        return row


def branch_ownership(db, row):
    from sqlalchemy import select
    from app.branches.models import BranchOwnership
    table = BranchOwnership.__table__
    return db.connection().execute(select(table.c.branch_id).where(table.c.resource_table == row.__tablename__, table.c.resource_key == str(row.id), table.c.company_id == row.organization_id)).scalar()


def stamp_inbound(db, row, branch):
    """Trusted HMAC ingestion has no user session; retain normal branch ownership."""
    if not branch or branch_ownership(db, row): return
    from app.branches.models import BranchOwnership
    from app.models.company import Branch
    from app.branches.models import BranchLifecycle
    from sqlalchemy import select
    table = BranchOwnership.__table__
    if not db.connection().execute(select(Branch.id).where(Branch.id == branch, Branch.company_id == row.organization_id, Branch.is_active.is_(True), ~Branch.id.in_(select(BranchLifecycle.branch_id).where(BranchLifecycle.deleted_at.is_not(None))))).first():
        return  # Retain unresolved privately; never guess another branch.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    db.connection().execute(insert(table).values(resource_table=row.__tablename__,resource_key=str(row.id),company_id=row.organization_id,branch_id=branch,source='whatsapp_signed_webhook').on_conflict_do_nothing())


def environment_available(company):
    return (settings.CRM_WHATSAPP_PROVIDER in {'meta','meta_cloud','cloud_api'} and company == settings.CRM_WHATSAPP_ORGANIZATION_ID
            and bool(settings.CRM_WHATSAPP_ACCESS_TOKEN and settings.CRM_WHATSAPP_PHONE_NUMBER_ID and settings.CRM_WHATSAPP_BUSINESS_ACCOUNT_ID))


def connection_for(db, company, *, bootstrap=False):
    row = db.query(WhatsAppConnection).filter_by(organization_id=company).first()
    if row is None and bootstrap and environment_available(company):
        try:
            with db.begin_nested():
                row = WhatsAppConnection(organization_id=company, waba_id=settings.CRM_WHATSAPP_BUSINESS_ACCOUNT_ID,
                    phone_number_id=settings.CRM_WHATSAPP_PHONE_NUMBER_ID, routing_key=settings.CRM_WHATSAPP_PHONE_NUMBER_ID,
                    source='environment', status='connected', subscribed=True)
                db.add(row)
                db.flush()
        except IntegrityError:
            row = db.query(WhatsAppConnection).filter_by(organization_id=company).first()
    return row


def live_connection(db, company):
    row = connection_for(db, company, bootstrap=True)
    if row is None or row.status != 'connected':
        raise HTTPException(409, 'Connect this organization’s WhatsApp account first')
    return row


def connection_token(row):
    if row.status not in {'connected','registration_required'}:
        raise HTTPException(409, 'WhatsApp account is disconnected')
    if row.source == 'environment':
        if not environment_available(row.organization_id) or row.phone_number_id != settings.CRM_WHATSAPP_PHONE_NUMBER_ID or row.waba_id != settings.CRM_WHATSAPP_BUSINESS_ACCOUNT_ID:
            raise HTTPException(409, 'Deployment account changed; reconnect WhatsApp')
        return settings.CRM_WHATSAPP_ACCESS_TOKEN
    return reveal(row.token_ciphertext)


def connection_data(row):
    return {'id':row.id, 'wabaId':row.waba_id, 'phoneNumberId':row.phone_number_id,
        'displayNumber':row.display_number, 'businessName':row.business_name, 'source':row.source,
        'status':row.status, 'subscribed':row.subscribed, 'verifiedAt':row.verified_at, 'inboundBranchId':row.inbound_branch_id}


def verify_assets(token, waba, phone):
    if not waba.isdecimal() or not phone.isdecimal():
        raise HTTPException(422, 'Use numeric Meta account and phone-number IDs')
    graph = WhatsAppGraph(token)
    if settings.CRM_WHATSAPP_APP_ID and settings.CRM_WHATSAPP_APP_SECRET:
        info = WhatsAppGraph(settings.CRM_WHATSAPP_APP_ID+'|'+settings.CRM_WHATSAPP_APP_SECRET).request('GET', 'debug_token', params={'input_token':token}).get('data', {})
        if not info.get('is_valid') or str(info.get('app_id')) != settings.CRM_WHATSAPP_APP_ID or not {'whatsapp_business_messaging','whatsapp_business_management'} <= set(info.get('scopes', [])):
            raise HTTPException(422, 'The token must belong to this Meta app and grant both WhatsApp permissions')
    after = None
    for _ in range(10):
        params = {'fields':'id,display_phone_number,verified_name,status', 'limit':100}
        if after: params['after'] = after
        result = graph.request('GET', waba+'/phone_numbers', params=params)
        for item in result.get('data', []):
            if str(item.get('id')) == phone:
                return item
        paging = result.get('paging', {})
        after = paging.get('cursors', {}).get('after') if paging.get('next') else None
        if not after: break
    raise HTTPException(422, 'This sender does not belong to the authorized WhatsApp account')


def save_connection(db, user, token, waba, phone, source='embedded_signup', registration_pin=None):
    company = organization(user)
    other = db.query(WhatsAppConnection).filter(WhatsAppConnection.routing_key == phone, WhatsAppConnection.organization_id != company).first()
    if other:
        raise HTTPException(409, 'That sender is already connected to another organization')
    details = verify_assets(token, waba, phone)
    if registration_pin and details.get('status') != 'CONNECTED':
        WhatsAppGraph(token).request('POST', phone+'/register', payload={'messaging_product':'whatsapp','pin':registration_pin})
        details = verify_assets(token, waba, phone)
    # Only the WABA whose ownership has just been checked is subscribed.
    WhatsAppGraph(token).request('POST', waba+'/subscribed_apps', payload={})
    row = connection_for(db, company)
    if row is None:
        row = WhatsAppConnection(organization_id=company, created_by=user.id)
        db.add(row)
    if row.phone_number_id and row.phone_number_id != phone:
        # A different sender does not inherit the previous sender's service windows.
        for contact in db.query(WhatsAppContact).filter_by(organization_id=company).all():
            contact.last_inbound_at = None
    row.waba_id, row.phone_number_id, row.routing_key = waba, phone, phone
    row.display_number, row.business_name = details.get('display_phone_number'), details.get('verified_name')
    row.token_ciphertext = None if source == 'environment' else protect(token)
    row.source, row.status, row.subscribed, row.verified_at = source, ('connected' if details.get('status') == 'CONNECTED' else 'registration_required'), True, now()
    context = db.info.get('branch_context')
    if context and context.branch_id in context.writable:
        row.inbound_branch_id = context.branch_id
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Sender connection changed; refresh and try again') from None
    from app.access.service import audit
    audit(db, user, company, 'whatsapp.connected', 'Authorized WhatsApp account connected', after={'connection_id':row.id,'source':source})
    db.commit()
    return row


def service_window(contact):
    inbound = utc(contact.last_inbound_at)
    return bool(inbound and now()-timedelta(hours=24) < inbound <= now())


def contact_data(row):
    inbound = utc(row.last_inbound_at)
    return {'id':row.id,'recipient':row.recipient,'name':row.name,'entityType':row.entity_type,'entityId':row.entity_id,
        'consent':row.consent,'consentSource':row.consent_source,'consentAt':row.consent_at,
        'serviceWindowOpen':service_window(row), 'serviceWindowEndsAt':(inbound+timedelta(hours=24)).isoformat() if inbound else None,
        'lastMessageAt':row.last_message_at}


def message_data(row):
    return {'id':row.id,'contactId':row.contact_id,'direction':row.direction,'kind':row.kind,'body':row.body,
        'template':row.template_json,'status':row.status,'errorCode':row.error_code,'createdAt':row.created_at,
        'providerMessageId':row.provider_message_id,'crmMessageId':row.crm_message_id}


def update_status(db, row, state, error_code=None):
    rank = {'reserved':-2,'submitting':-1,'reconciliation_required':-1,'accepted':0,'sent':1,'delivered':2,'read':3}
    current = rank.get(row.status, -1)
    if state == 'failed' and current < 2:
        row.status, row.error_code = 'failed', error_code
    elif state in rank and rank[state] > current:
        row.status, row.error_code = state, None
    if row.crm_message_id:
        from app.apps.crm.models import CRMMessage
        legacy = db.get(CRMMessage, row.crm_message_id)
        if legacy and legacy.organization_id == row.organization_id:
            legacy.status = row.status
            legacy.provider_message_id = row.provider_message_id
            legacy.failure_reason = ('Meta error '+str(row.error_code)) if row.error_code else None
            if row.status in {'sent','delivered','read'} and not legacy.sent_at:
                legacy.sent_at = now()


def send_message(db, user, data):
    company, recipient = organization(user), number(data.to)
    connection = live_connection(db, company)
    connection = db.query(WhatsAppConnection).filter_by(id=connection.id, organization_id=company).with_for_update().one()
    if connection.status != 'connected':
        raise HTTPException(409, 'WhatsApp account is disconnected')
    contact = contact_for(db, company, recipient)
    if data.entityType and data.entityId:
        record_access(db, user, data.entityType, data.entityId)
        if not contact.entity_id:
            contact.entity_type, contact.entity_id = data.entityType, data.entityId
    contact_access(db, user, contact)
    template = data.template
    body = data.body.strip()
    if not template and not body:
        raise HTTPException(422, 'Enter a message or choose an approved template')
    payload_digest = hashlib.sha256(json.dumps({'to':recipient,'body':body,'template':template,'entityType':data.entityType,'entityId':data.entityId}, sort_keys=True).encode()).hexdigest()
    existing = db.query(WhatsAppMessage).filter_by(organization_id=company, idempotency_key=data.requestId).first()
    if existing:
        if existing.payload_digest != payload_digest:
            raise HTTPException(409, 'Request ID has already been used for a different message')
        return existing
    if contact.consent == 'opted_out':
        raise HTTPException(409, 'This recipient opted out; sending is blocked')
    if template:
        if contact.consent != 'opted_in':
            raise HTTPException(409, 'Record the recipient’s opt-in before sending a template')
        approved = WhatsAppGraph(connection_token(connection)).request('GET', connection.waba_id+'/message_templates', params={'name':template['name'],'fields':'name,status,language','limit':100})
        if not any(t.get('name') == template['name'] and t.get('status') == 'APPROVED' and t.get('language') == template['language']['code'] for t in approved.get('data', [])):
            raise HTTPException(409, 'Choose an approved Meta template and matching language')
    elif not service_window(contact):
        raise HTTPException(409, 'The 24-hour reply window is closed. Use an approved template with opt-in')
    if db.query(WhatsAppMessage.id).filter(WhatsAppMessage.organization_id == company, WhatsAppMessage.direction == 'outbound', WhatsAppMessage.created_at >= now()-timedelta(minutes=1)).count() >= 30:
        raise HTTPException(429, 'Organization WhatsApp limit reached; wait one minute', headers={'Retry-After':'60'})
    row = WhatsAppMessage(organization_id=company, connection_id=connection.id, contact_id=contact.id,
        direction='outbound', kind='template' if template else 'text', body=body or 'Template: '+template['name'], template_json=template,
        status='submitting', idempotency_key=data.requestId, payload_digest=payload_digest, actor_id=user.id)
    if data.entityType and data.entityId:
        from app.apps.crm.models import CRMMessage
        legacy = CRMMessage(organization_id=company, entity_type=data.entityType, entity_id=data.entityId, channel='whatsapp',
            to='+'+recipient, body=row.body, status='submitting', provider='meta', sent_by_user_id=user.id, created_by_user_id=user.id)
        db.add(legacy)
        db.flush()
        row.crm_message_id = legacy.id
    db.add(row)
    contact.last_message_at = now()
    try:
        db.commit()  # Durable reservation BEFORE crossing the provider boundary.
    except IntegrityError:
        db.rollback()
        existing = db.query(WhatsAppMessage).filter_by(organization_id=company, idempotency_key=data.requestId).first()
        if existing and existing.payload_digest == payload_digest:
            return existing
        raise HTTPException(409, 'Request already reserved; refresh its status') from None
    try:
        state, provider_id = MetaWhatsAppProvider(connection_token(connection), connection.phone_number_id).send(to=recipient, body=body, template=template)
        row.provider_message_id = provider_id
        update_status(db, row, state)
        # Preserve delivery events that raced the provider response/local commit.
        # Exact message-scoped receipt lookup: a receipt may precede its sender
        # response, so its branch ownership cannot always be known on arrival.
        table = WhatsAppReceipt.__table__
        for receipt in db.connection().execute(table.select().where(table.c.organization_id == company, table.c.connection_id == connection.id, table.c.provider_message_id == provider_id).order_by(table.c.id)).mappings():
            update_status(db, row, receipt['status'], receipt['error_code'])
    except MetaError as error:
        row.status = 'reconciliation_required' if error.uncertain else 'failed'
        row.error_code = error.code or ('uncertain' if error.uncertain else 'provider_error')
        update_status(db, row, row.status, row.error_code)
    db.commit()
    db.refresh(row)
    return row


def ingest(db, payload):
    if payload.get('object') != 'whatsapp_business_account':
        return
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            phone = str(value.get('metadata', {}).get('phone_number_id', ''))
            connection = db.query(WhatsAppConnection).filter_by(routing_key=phone, waba_id=str(entry.get('id')), status='connected').first()
            if not connection and phone == settings.CRM_WHATSAPP_PHONE_NUMBER_ID and str(entry.get('id')) == settings.CRM_WHATSAPP_BUSINESS_ACCOUNT_ID and settings.CRM_WHATSAPP_ORGANIZATION_ID:
                connection = connection_for(db, settings.CRM_WHATSAPP_ORGANIZATION_ID, bootstrap=True)
            if not connection or connection.status != 'connected' or connection.routing_key != phone or connection.waba_id != str(entry.get('id')):
                continue
            company = connection.organization_id
            for event in value.get('statuses', []):
                state, provider_id = event.get('status'), str(event.get('id', ''))[:200]
                if state not in {'sent','delivered','read','failed'} or not provider_id:
                    continue
                error_code = str((event.get('errors') or [{}])[0].get('code', ''))[:40] or None
                if not db.query(WhatsAppReceipt.id).filter_by(connection_id=connection.id, provider_message_id=provider_id, status=state).first():
                    try:
                        with db.begin_nested():
                            db.add(WhatsAppReceipt(organization_id=company, connection_id=connection.id, provider_message_id=provider_id, status=state, error_code=error_code))
                            db.flush()
                    except IntegrityError:
                        pass
                for row in db.query(WhatsAppMessage).filter_by(connection_id=connection.id, provider_message_id=provider_id).with_for_update().all():
                    update_status(db, row, state, error_code)
            for event in value.get('messages', []):
                provider_id = str(event.get('id', ''))[:200]
                if not provider_id or db.query(WhatsAppMessage.id).filter_by(connection_id=connection.id, provider_message_id=provider_id).first():
                    continue
                try:
                    recipient = number(event.get('from', ''))
                except HTTPException:
                    continue
                contact = contact_for(db, company, recipient)
                stamp_inbound(db, contact, connection.inbound_branch_id)
                branch = branch_ownership(db, contact)
                kind = str(event.get('type', 'unknown'))[:30]
                body = str(event.get('text', {}).get('body', ''))[:10000] if kind == 'text' else '['+kind+' message]'
                try:
                    with db.begin_nested():
                        message = WhatsAppMessage(organization_id=company, connection_id=connection.id, contact_id=contact.id,
                            direction='inbound', kind=kind, body=body, status='received', provider_message_id=provider_id)
                        db.add(message)
                        db.flush()
                        stamp_inbound(db, message, branch)
                except IntegrityError:
                    continue
                timestamp = None
                try:
                    timestamp = min(datetime.fromtimestamp(int(event.get('timestamp')), timezone.utc), now())
                except (ValueError, TypeError, OverflowError, OSError):
                    pass
                if timestamp and (not contact.last_inbound_at or timestamp > utc(contact.last_inbound_at)):
                    contact.last_inbound_at = timestamp
                contact.last_message_at = now()
                profiles = value.get('contacts') or []
                profile = next((p.get('profile', {}) for p in profiles if str(p.get('wa_id')) == recipient), {})
                if not contact.name and profile.get('name'):
                    contact.name = str(profile['name'])[:250]
                keyword = body.strip().upper()
                if keyword in {'STOP','UNSUBSCRIBE','CANCEL','END','QUIT'}:
                    contact.consent, contact.consent_source, contact.consent_at = 'opted_out', 'Customer opt-out keyword', now()
                elif keyword in {'START','SUBSCRIBE'}:
                    contact.consent, contact.consent_source, contact.consent_at = 'opted_in', 'Customer opt-in keyword', now()
