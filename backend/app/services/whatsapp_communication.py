"""Workspace adapters; provider sends and scheduled dispatch retain their existing guards."""
from datetime import timezone
from hashlib import sha256
import json

from fastapi import HTTPException
from sqlalchemy import or_

from app.services import whatsapp_workspace as wa
from app.shared.whatsapp_models import WhatsAppContact


def directory(db, user, entries):
    from app.services.whatsapp_hub import context
    result = []
    for entry in entries:
        phone = wa.number(entry.to)
        row = db.query(WhatsAppContact).filter_by(organization_id=wa.organization(user), recipient=phone, erased_at=None).first()
        item = {'to': phone, 'entityType': entry.entityType, 'entityId': entry.entityId, 'contact': None, 'invoices': [], 'financeAvailable': False}
        if row:
            try:
                wa.contact_access(db, user, row)
                item['contact'] = wa.contact_data(row)
                # A shared phone must never supply a different record's invoices.
                if entry.entityId and (row.entity_type, row.entity_id) == (entry.entityType, entry.entityId):
                    detail = context(db, user, row.id)
                    item.update(invoices=detail['invoices'], financeAvailable=detail['canViewFinance'])
            except HTTPException as error:
                if error.status_code not in {403, 404}:
                    raise
                item['unavailable'] = True
        result.append(item)
    return {'items': result}


def schedule(db, user, data):
    from app.apps.communication import customer_service as service
    from app.apps.communication.customer_api import branch
    from app.apps.communication.customer_models import CustomerRecipient, CustomerBinding, CustomerDelivery
    from app.services.email_schedules import permitted
    if not user.is_superuser and not (permitted(user, 'communication_email_send') or permitted(user, 'communication_campaigns_send')):
        raise HTTPException(403, 'Customer communication sending permission is required for scheduled delivery')
    due = data.scheduledAt
    if due.tzinfo is None or due.utcoffset() is None:
        raise HTTPException(422, 'Schedule must include a timezone offset')
    if due.astimezone(timezone.utc) <= wa.now():
        raise HTTPException(422, 'Choose a future delivery time')
    message = data.message
    if not message.template or message.media or message.replyTo:
        raise HTTPException(422, 'Scheduled delivery requires an approved template without a reply or attachment')
    if '{{' in json.dumps(message.template):
        raise HTTPException(422, 'Complete all template fields before scheduling')
    company, branch_id = wa.organization(user), branch(db)
    phone = wa.number(message.to)
    contact = db.query(WhatsAppContact).filter_by(organization_id=company, recipient=phone, erased_at=None).first()
    if not contact:
        raise HTTPException(409, 'Link this recipient in WhatsApp and record opt-in before scheduling')
    wa.contact_access(db, user, contact)
    if contact.consent != 'opted_in':
        raise HTTPException(409, 'This recipient has not opted in to WhatsApp messages')
    if not message.entityId or (contact.entity_type, contact.entity_id) != (message.entityType, message.entityId):
        raise HTTPException(409, 'Scheduled recipients must match their linked CRM record')
    wa.record_access(db, user, message.entityType, message.entityId)
    recipient = db.query(CustomerRecipient).filter(
        CustomerRecipient.organization_id == company, CustomerRecipient.branch_id == branch_id,
        CustomerRecipient.active.is_(True), CustomerRecipient.phone.in_([phone, '+'+phone]),
        or_(CustomerRecipient.crm_contact_id == message.entityId if message.entityType == 'contact' else False,
            CustomerRecipient.id.in_(db.query(CustomerBinding.recipient_id).filter(
                CustomerBinding.organization_id == company, CustomerBinding.branch_id == branch_id,
                CustomerBinding.source_type == message.entityType, CustomerBinding.source_id == message.entityId)))
    ).order_by(CustomerRecipient.id).first()
    if not recipient or not service.preference_allowed(db, recipient, 'whatsapp', data.purpose):
        raise HTTPException(409, 'Register this contact in customer communications with WhatsApp permission for this purpose before scheduling')
    if data.purpose != 'transactional' and not (user.is_superuser or permitted(user, 'communication_campaigns_send')):
        raise HTTPException(403, 'Greeting and marketing messages require campaign sending permission')
    key = f'workspace:{company}:{user.id}:{message.requestId}'
    digest = sha256(json.dumps({'message': message.model_dump(), 'due': due.astimezone(timezone.utc).isoformat(), 'purpose': data.purpose}, sort_keys=True).encode()).hexdigest()
    existing = db.query(CustomerDelivery).filter_by(event_key=key, organization_id=company).first()
    if existing:
        if existing.snapshot.get('workspace_digest') != digest:
            raise HTTPException(409, 'This request ID was already used for a different scheduled message')
        return {'id': existing.id, 'status': existing.status, 'dueAt': existing.due_at}
    from app.services.whatsapp import WhatsAppGraph
    connection = wa.live_connection(db, company)
    available = WhatsAppGraph(wa.connection_token(connection)).request('GET', connection.waba_id+'/message_templates',
        params={'name': message.template['name'], 'fields': 'name,status,language,category', 'limit': 100})
    approved = next((t for t in available.get('data', []) if t.get('name') == message.template['name']
        and t.get('language') == message.template['language']['code'] and t.get('status') == 'APPROVED'), None)
    if not approved:
        raise HTTPException(409, 'Choose a currently approved WhatsApp template before scheduling')
    if approved.get('category') == 'MARKETING' and data.purpose not in {'marketing', 'greeting'}:
        raise HTTPException(422, 'Marketing templates require marketing or greeting permission')
    row = service.queue_delivery(db, recipient, key=key, kind='recipient', identity=recipient.id,
        snapshot={'workspace_digest': digest}, actor=user.id, subject='WhatsApp communication', body='',
        purpose=data.purpose, channel='whatsapp', due_at=due)
    row.whatsapp_template = message.template
    db.commit()
    db.refresh(row)
    return {'id': row.id, 'status': row.status, 'dueAt': row.due_at}
