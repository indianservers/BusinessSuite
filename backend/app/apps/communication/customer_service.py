"""Customer automation orchestration inside the existing suite email worker."""
from contextlib import contextmanager, ExitStack
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import re
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, update, func, or_, and_
from app.db.base_class import Base
from app.models.user import User
from app.models.email_outbox import EmailOutbox
from .customer_models import (CustomerRecipient, CustomerBinding, CustomerCommunicationSettings,
    CustomerAutomation, CustomerEvent, CustomerDelivery, CustomerShipment)
from .customer_events import SOURCES, values

TERMINAL = {'paid', 'completed', 'complete', 'done', 'closed', 'cancelled', 'canceled', 'rejected', 'archived', 'delivered', 'lost', 'converted'}
FIELDS = {'name', 'reference', 'status', 'due_date', 'amount', 'currency', 'tracking_url'}
TRIGGERS = [kind+'.'+suffix for kind in ['order', 'invoice', 'service', 'follow_up', 'contract', 'lead', 'meeting', 'quotation', 'shipment'] for suffix in ['changed', 'due']] + ['birthday', 'anniversary', 'greeting', 'campaign', 'welcome']


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def source_model(kind):
    table = next((name for name, spec in SOURCES.items() if spec[0] == kind), None)
    return next((m.class_ for m in Base.registry.mappers if m.local_table.name == table), None)


def source(db, kind, identity, company):
    model = source_model(kind)
    if model is None:
        return None
    query = db.query(model).filter(model.id == identity, model.organization_id == company)
    actor = db.info.get('customer_communication_actor')
    if kind == 'follow_up' and actor:
        from app.shared.follow_ups import visible
        query = visible(db, actor).filter(model.id == identity, model.organization_id == company)
    if hasattr(model, 'deleted_at'):
        query = query.filter(model.deleted_at.is_(None))
    return query.first()


def config(db, company):
    return db.get(CustomerCommunicationSettings, company)


def preference_allowed(db, recipient, channel, purpose):
    if not recipient or not recipient.active:
        return False
    preferences = recipient.preferences or {}
    # Positive, purpose-specific permission. Signup never implies marketing permission.
    if preferences.get(channel+'.'+purpose) is not True:
        return False
    if channel == 'email':
        from .models import CommunicationOptOut
        if not recipient.email:
            return False
        # Explicit organization filter: legacy opt-outs use ownership registers.
        from app.models.security_boundary import SecurityResourceOwnership
        opted = db.query(CommunicationOptOut).join(SecurityResourceOwnership,
            (SecurityResourceOwnership.resource_table == CommunicationOptOut.__tablename__) &
            (SecurityResourceOwnership.resource_id == CommunicationOptOut.id)).filter(
                SecurityResourceOwnership.company_id == recipient.organization_id,
                func.lower(CommunicationOptOut.email) == recipient.email.casefold(),
                CommunicationOptOut.channel == 'email').first()
        return not bool(opted)
    return bool(recipient.phone)


def render_payload(value, context):
    if isinstance(value,str):return render(value,context)
    if isinstance(value,list):return [render_payload(v,context) for v in value]
    if isinstance(value,dict):return {k:render_payload(v,context) for k,v in value.items()}
    return value


def template_values(recipient, snapshot):
    return {'name': recipient.name, 'reference': str(snapshot.get('order_number') or snapshot.get('invoice_number') or
        snapshot.get('contract_number') or snapshot.get('engagement_number') or snapshot.get('reference') or snapshot.get('id') or ''),
        'status': str(snapshot.get('status') or ''), 'due_date': str(next((snapshot.get(k) for k in
        ('due_date', 'due_at', 'planned_end_date', 'expiry_date', 'expected_end_date', 'expected_date', 'start_time', 'next_follow_up_at', 'valid_until') if snapshot.get(k)), '')),
        'amount': str(snapshot.get('balance_amount') if snapshot.get('balance_amount') is not None else snapshot.get('total_amount') or ''),
        'currency': str(snapshot.get('currency') or ''), 'tracking_url': str(snapshot.get('tracking_url') or '')}


def render(text, context):
    def replace(match):
        key = match.group(1).strip()
        if key not in FIELDS or not str(context.get(key, '')).strip():
            raise ValueError('Missing template value: '+key)
        return str(context[key])
    result = re.sub(r'\{\{\s*([^{}]+)\s*\}\}', replace, text)
    if '{{' in result or '}}' in result:
        raise ValueError('Unresolved template variable')
    return result


def binding_matches(db, recipient_id, kind, identity, obj, company):
    pairs = [(kind, identity)]
    if getattr(obj, 'sales_order_id', None):
        pairs.append(('order', obj.sales_order_id))
    if getattr(obj, 'order_id', None):
        pairs.append(('order', obj.order_id))
    if getattr(obj, 'contact_id', None):
        pairs.append(('contact', obj.contact_id))
    if getattr(obj, 'crm_contact_id', None):
        pairs.append(('contact', obj.crm_contact_id))
    for binding in db.query(CustomerBinding).filter_by(organization_id=company, recipient_id=recipient_id):
        if (binding.source_type, binding.source_id) in pairs:
            return True
    return False


def bound_recipient_ids(kind, identity, obj, company):
    pairs = [(kind, identity)]
    if getattr(obj, 'sales_order_id', None):
        pairs.append(('order', obj.sales_order_id))
    if getattr(obj, 'order_id', None):
        pairs.append(('order', obj.order_id))
    if getattr(obj, 'contact_id', None):
        pairs.append(('contact', obj.contact_id))
    if getattr(obj, 'crm_contact_id', None):
        pairs.append(('contact', obj.crm_contact_id))
    return select(CustomerBinding.recipient_id).where(CustomerBinding.organization_id == company,
        or_(*(and_(CustomerBinding.source_type == kind, CustomerBinding.source_id == identity) for kind, identity in pairs)))


def queue_delivery(db, recipient, *, key, kind, identity, snapshot, actor, rule=None,
                   subject=None, body=None, purpose='transactional', channel='email', due_at=None, reminder_id=None):
    if any(isinstance(row, CustomerDelivery) and row.event_key == key for row in db.new):
        return None
    if db.query(CustomerDelivery.id).filter_by(event_key=key).first():
        return None
    row = CustomerDelivery(organization_id=recipient.organization_id, branch_id=recipient.branch_id,
        recipient_id=recipient.id, event_key=key, source_type=kind, source_id=identity,
        snapshot=snapshot, created_by=actor, automation_id=rule.id if rule else None,
        rule_version=rule.version if rule else None, purpose=rule.purpose if rule else purpose,
        channel=rule.channel if rule else channel, subject=rule.subject if rule else subject,
        body=rule.body if rule else body, whatsapp_template=rule.whatsapp_template if rule else None,
        status='queued', due_at=due_at or now(), reminder_id=reminder_id)
    db.add(row)
    return row


@contextmanager
def actor_scope(db, actor_id, company, branch, module='communication'):
    """Re-evaluate owner membership and branch grants on every background run."""
    from app.core.tenant_boundary import install, company_ids
    from app.branches.service import context
    from app.branches.boundary import install as install_branch
    db.info.pop('suite_access_policies', None)
    user = db.get(User, actor_id)
    if not user or not user.is_active:
        raise ValueError('Schedule owner no longer has permission')
    if not user.is_superuser and company not in company_ids(db, user):
        raise ValueError('Schedule company membership revoked')
    # Permission objects alone are insufficient when module policies were revoked.
    from app.access.service import check_background_access, policy_for, resolved_grants, effective_objects
    from app.branches.roles import effective_grants
    from app.access.catalog import permission_objects
    old_company = getattr(user, 'organization_id', None)
    user.organization_id = company
    try:
        check_background_access(db, user, module, 'view', branch_id=str(branch))
        policy = policy_for(db, user, company)
        grants = effective_grants(db, user, company, str(branch), resolved_grants(db, policy) if policy else None)
        objects = effective_objects(db, grants, module) if grants is not None else list(permission_objects(user))
        names = {p.name for p in objects}
        required = {'srm_collection_create', 'srm_admin'} if module == 'srm' else {'communication_email_send', 'communication_campaigns_send'}
        if not user.is_superuser and not names.intersection(required):
            raise ValueError('Current branch no longer permits customer sends')
    finally:
        user.organization_id = old_company
    ctx = context(db, user, company, str(branch))
    if branch not in ctx.writable:
        raise ValueError('Schedule branch write access revoked')
    scoped = SimpleNamespace(id=user.id, is_superuser=False) if user.is_superuser else user
    with ExitStack() as stack:
        user.organization_id = company
        stack.callback(lambda: setattr(user, 'organization_id', old_company))
        old_actor = db.info.get('customer_communication_actor')
        db.info['customer_communication_actor'] = user
        stack.callback(lambda: db.info.__setitem__('customer_communication_actor', old_actor))
        stack.callback(install(db, scoped, company, verified_portal=user.is_superuser))
        stack.callback(install_branch(db, user, ctx))
        if grants is not None and not user.is_superuser:
            from app.access.scope import install_scope
            attrs = {key: getattr(user, key, None) for key in ('_suite_grants', '_suite_current_module', '_suite_permission_objects', '_suite_scope_active')}
            def restore():
                for key, value in attrs.items():
                    setattr(user, key, value)
            stack.callback(restore)
            user._suite_grants, user._suite_current_module, user._suite_permission_objects = grants, module, objects
            stack.callback(install_scope(db, user, company, grants))
        yield user


def check_delivery(db, row):
    recipient = db.query(CustomerRecipient).filter_by(id=row.recipient_id, organization_id=row.organization_id, branch_id=row.branch_id).first()
    if not preference_allowed(db, recipient, row.channel, row.purpose):
        return 'blocked', 'Recipient has not permitted this channel and purpose'
    settings = db.query(CustomerCommunicationSettings).filter_by(organization_id=row.organization_id).with_for_update().first()
    if settings and settings.paused:
        return 'defer', 'Business communications are paused'
    rule = db.get(CustomerAutomation, row.automation_id) if row.automation_id else None
    if row.purpose in {'marketing', 'greeting'}:
        from app.services.email_schedules import permitted
        actor = db.info.get('customer_communication_actor') or db.get(User, row.created_by)
        if not actor or not (actor.is_superuser or permitted(actor, 'communication_campaigns_send')):
            return 'blocked', 'Campaign permission was revoked'
    if row.automation_id and (not rule or rule.status != 'active' or rule.version != row.rule_version):
        return 'cancelled', 'Automation paused, changed or removed'
    if row.source_type not in {'recipient', 'campaign'}:
        obj = source(db, row.source_type, row.source_id, row.organization_id)
        if not obj or not binding_matches(db, row.recipient_id, row.source_type, row.source_id, obj, row.organization_id):
            return 'cancelled', 'Source or recipient mapping is no longer available'
        current = values(obj)
        # Delayed status messages must never deliver obsolete facts.
        if current != row.snapshot:
            return 'cancelled', 'Source changed since this message was queued'
        reminder = bool(row.reminder_id or rule and rule.trigger.endswith('.due'))
        if reminder and row.source_type == 'invoice':
            from app.apps.srm.services.collections import reminder_block_reason, collection_on_hold
            reason = reminder_block_reason(obj)
            if recipient.role not in {'billing', 'primary'}:
                return 'blocked', 'Invoice reminders require an authorized billing recipient'
            if collection_on_hold(obj):
                return 'defer', reason
            if reason:
                return 'cancelled', reason
        if reminder and (str(current.get('status', '')).lower() in TERMINAL or row.source_type == 'invoice' and float(current.get('balance_amount') or 0) <= 0):
            return 'cancelled', 'Source is already settled or completed'
    if rule and rule.stop_on_reply and recipient.phone:
        from app.shared.whatsapp_models import WhatsAppContact
        contact = db.query(WhatsAppContact).filter_by(organization_id=row.organization_id, recipient=recipient.phone.lstrip('+')).first()
        if contact and contact.last_inbound_at and utc(contact.last_inbound_at) > utc(row.created_at):
            return 'cancelled', 'Customer replied; follow-up stopped'
    if rule and rule.stop_on_reply:
        from .customer_models import CustomerEmailReply
        if db.query(CustomerEmailReply.id).filter(CustomerEmailReply.organization_id == row.organization_id,
            CustomerEmailReply.recipient_id == recipient.id, CustomerEmailReply.received_at > row.created_at).first():
            return 'cancelled', 'Customer replied by email; follow-up stopped'
    return None, None


def permitted_time(recipient, rule, at):
    local = at.astimezone(ZoneInfo(recipient.timezone))
    if rule and local.weekday() not in rule.weekdays:
        return False
    start, end = (rule.quiet_start, rule.quiet_end) if rule else (20, 8)
    return not (start <= local.hour < end if start < end else local.hour >= start or local.hour < end) if start != end else True


def sync_delivery(db, row):
    if row.email_outbox_id:
        outbox = db.get(EmailOutbox, row.email_outbox_id)
        if outbox:
            row.status = 'waiting_provider' if outbox.status == 'queued' else outbox.status
            row.error = outbox.error
    elif row.whatsapp_message_id:
        from app.shared.whatsapp_models import WhatsAppMessage
        message = db.get(WhatsAppMessage, row.whatsapp_message_id)
        if message:
            row.status = message.status
            row.error = message.error_code
    if row.reminder_id:
        from app.apps.srm.models import SRMCollectionReminder
        reminder = db.get(SRMCollectionReminder, row.reminder_id)
        if reminder:
            reminder.status = row.status
            if row.status in {'accepted', 'sent', 'delivered', 'read'}:
                reminder.sent_at = row.attempted_at


def email_policy(db, outbox):
    """Called under fresh actor/branch scope immediately before provider I/O."""
    row = db.query(CustomerDelivery).filter_by(email_outbox_id=outbox.id, organization_id=outbox.organization_id).first()
    if not row:
        return False
    recipient = db.get(CustomerRecipient, row.recipient_id)
    if not recipient or recipient.email != outbox.recipient:
        row.status, row.error = 'cancelled', 'Recipient address changed after queuing'
        return False
    from .customer_transport import configured
    if not configured(db, row.organization_id):
        row.status, row.error = 'blocked', 'Email connection is unavailable'
        return False
    state, reason = check_delivery(db, row)
    if state:
        outbox.error = reason
        row.error = reason
        row.status = state if state != 'defer' else 'retry_wait'
        if state == 'defer':
            row.due_at = now()+timedelta(minutes=1)
        return False
    return True


def process_events(db, limit=50):
    processed = 0
    for _ in range(limit):
        event = db.query(CustomerEvent).filter_by(status='pending').order_by(CustomerEvent.id).with_for_update(skip_locked=True).first()
        if not event:
            break
        # Retain the lock until all intents and the processed marker commit together.
        rules = db.query(CustomerAutomation).filter_by(organization_id=event.organization_id, branch_id=event.branch_id, status='active', trigger=event.trigger).all()
        for rule in rules:
            if event.id <= (rule.activation_event_id or 0):
                continue
            try:
                with actor_scope(db, rule.created_by, rule.organization_id, rule.branch_id):
                    obj = source(db, event.source_type, event.source_id, event.organization_id)
                    if not obj:
                        continue
                    if str(event.snapshot.get('status', '')).lower() == 'draft':
                        continue
                    if rule.conditions.get('statuses') and event.snapshot.get('status') not in rule.conditions['statuses']:
                        continue
                    for recipient in db.query(CustomerRecipient).filter_by(organization_id=rule.organization_id, branch_id=rule.branch_id, active=True).filter(
                        CustomerRecipient.id.in_(bound_recipient_ids(event.source_type, event.source_id, obj, rule.organization_id))):
                        if rule.conditions.get('roles') and recipient.role not in rule.conditions['roles']:
                            continue
                        for step, delay in enumerate(rule.steps):
                            queue_delivery(db, recipient, key=f'event:{event.event_key}:{rule.id}:{rule.version}:{recipient.id}:{step}',
                                kind=event.source_type, identity=event.source_id, snapshot=event.snapshot,
                                actor=rule.created_by, rule=rule, due_at=now()+timedelta(minutes=delay))
                    db.flush()
            except (ValueError, HTTPException):
                continue
        event.status = 'processed'
        db.commit()
        processed += 1
    return processed


def schedule_due(db, limit=50):
    queued = 0
    rules = db.query(CustomerAutomation).filter(CustomerAutomation.status == 'active', CustomerAutomation.trigger.in_(
        [t for t in TRIGGERS if t.endswith('.due')] + ['birthday', 'anniversary'])).order_by(CustomerAutomation.last_scanned_at.asc().nullsfirst(), CustomerAutomation.id).limit(limit).all()
    for rule in rules:
        try:
            with actor_scope(db, rule.created_by, rule.organization_id, rule.branch_id):
                batch = db.query(CustomerRecipient).filter_by(organization_id=rule.organization_id, branch_id=rule.branch_id, active=True).filter(CustomerRecipient.id > (rule.recipient_cursor or 0)).order_by(CustomerRecipient.id).limit(100).all()
                for recipient in batch:
                    rule.recipient_cursor = recipient.id
                    if rule.conditions.get('roles') and recipient.role not in rule.conditions['roles']:
                        continue
                    local_date = now().astimezone(ZoneInfo(recipient.timezone)).date()
                    if rule.trigger in {'birthday', 'anniversary'}:
                        day = getattr(recipient, rule.trigger)
                        if day and (day.month, day.day) == (local_date.month, local_date.day):
                            queued += bool(queue_delivery(db, recipient, key=f'greeting:{rule.id}:{rule.version}:{recipient.id}:{local_date}', kind='recipient', identity=recipient.id, snapshot={}, actor=rule.created_by, rule=rule))
                        continue
                    kind = rule.trigger.split('.')[0]
                    model = source_model(kind)
                    if model is None:
                        continue
                    field = SOURCES[model.__tablename__][2]
                    if not hasattr(model, field):
                        continue
                    bindings = db.query(CustomerBinding).filter_by(organization_id=rule.organization_id, recipient_id=recipient.id).all()
                    for binding in bindings:
                        query = db.query(model).filter(model.organization_id == rule.organization_id)
                        if binding.source_type == kind:
                            query = query.filter(model.id == binding.source_id)
                        elif binding.source_type == 'order' and hasattr(model, 'sales_order_id'):
                            query = query.filter(model.sales_order_id == binding.source_id)
                        elif binding.source_type == 'order' and hasattr(model, 'order_id'):
                            query = query.filter(model.order_id == binding.source_id)
                        else:
                            continue
                        for obj in query.limit(100):
                            if kind == 'follow_up' and not source(db, kind, obj.id, rule.organization_id):
                                continue
                            if getattr(obj, 'deleted_at', None) or str(getattr(obj, 'status', '')).lower() in TERMINAL | {'draft'}:
                                continue
                            if kind == 'invoice':
                                from app.apps.srm.services.collections import reminder_block_reason
                                if recipient.role not in {'billing', 'primary'} or reminder_block_reason(obj):
                                    continue
                            deadline = getattr(obj, field)
                            deadline = utc(deadline).astimezone(ZoneInfo(recipient.timezone)).date() if isinstance(deadline, datetime) else deadline
                            if not deadline or deadline != local_date + timedelta(days=int(rule.conditions.get('days_before', 0))):
                                continue
                            snapshot = values(obj)
                            if rule.conditions.get('statuses') and snapshot.get('status') not in rule.conditions['statuses']:
                                continue
                            for step, delay in enumerate(rule.steps):
                                queued += bool(queue_delivery(db, recipient, key=f'due:{rule.id}:{rule.version}:{recipient.id}:{obj.id}:{deadline}:{step}',
                                    kind=kind, identity=obj.id, snapshot=snapshot, actor=rule.created_by, rule=rule,
                                    due_at=now()+timedelta(minutes=delay)))
                    if queued >= limit:
                        break
                if len(batch) < 100:
                    rule.recipient_cursor = 0
                rule.last_scanned_at = now()
                db.commit()
        except (ValueError, HTTPException):
            db.rollback()
    return queued


def dispatch(db, row, user):
    recipient = db.get(CustomerRecipient, row.recipient_id)
    state, reason = check_delivery(db, row)
    if state:
        if state == 'defer':
            row.due_at = now()+timedelta(minutes=15)
        else:
            row.status = state
        row.error = reason
        return
    rule = db.get(CustomerAutomation, row.automation_id) if row.automation_id else None
    if not permitted_time(recipient, rule, now()):
        row.due_at = now()+timedelta(minutes=15)
        row.error = 'Waiting for recipient business hours'
        return
    if row.email_outbox_id:
        outbox = db.get(EmailOutbox, row.email_outbox_id)
        if outbox and outbox.status == 'retry_wait':
            outbox.status = 'queued'
        row.status = 'waiting_provider'
        return
    settings = config(db, row.organization_id)
    midnight = now().replace(hour=0, minute=0, second=0, microsecond=0)
    table = CustomerDelivery.__table__
    counts = select(func.count()).select_from(table).where(table.c.organization_id == row.organization_id, table.c.attempted_at >= midnight)
    business_count = db.connection().execute(counts).scalar()
    customer_count = db.connection().execute(counts.where(table.c.recipient_id == recipient.id)).scalar()
    if business_count >= (settings.daily_limit if settings else 1000) or customer_count >= (settings.customer_daily_limit if settings else 5):
        row.due_at = now()+timedelta(hours=1)
        row.error = 'Daily communication limit reached'
        return
    try:
        context = template_values(recipient, row.snapshot)
        subject, body = render(row.subject, context), render(row.body, context)
        if row.channel == 'email':
            from .customer_transport import configured
            from app.services.email_dispatch import queue_email
            if not configured(db, row.organization_id):
                row.status, row.error = 'blocked', 'Configure the business email provider before retrying'
                return
            if row.purpose in {'marketing', 'greeting'}:
                import secrets
                from .customer_models import CustomerPreferenceToken
                from app.core.config import settings as app_settings
                token = secrets.token_urlsafe(32)
                db.add(CustomerPreferenceToken(digest=sha256(token.encode()).hexdigest(), organization_id=row.organization_id,
                    recipient_id=recipient.id, expires_at=now()+timedelta(days=90)))
                body += '\n\nManage preferences / unsubscribe: '+app_settings.BACKEND_PUBLIC_URL.rstrip('/')+'/api/v1/public/customer-preferences/'+token
            outbox = queue_email(db, recipient=recipient.email, subject=subject, body=body, module='customer_communication',
                organization_id=row.organization_id, event_key='customer:'+row.event_key)
            if outbox:
                db.flush()
                row.email_outbox_id = outbox.id
            row.status = 'waiting_provider'
        else:
            from app.services.whatsapp_workspace import send_message
            if not row.whatsapp_template:
                row.status, row.error = 'blocked', 'Select an approved WhatsApp template for automated messages'
                return
            template = render_payload(row.whatsapp_template, context)
            # send_message reserves its own provider idempotency key durably.
            row.status, row.attempted_at = 'reconciliation_required', now()
            row.attempts += 1
            db.commit()
            message = send_message(db, user, SimpleNamespace(to=recipient.phone, body=body, template=template,
                requestId=f'journey-{row.id}-{row.attempts}', entityType=None, entityId=None))
            row.whatsapp_message_id = message.id
            row.status, row.error = message.status, message.error_code
            return
        row.attempted_at = now()
        row.attempts += 1
        row.error = None
    except ValueError as exc:
        row.status, row.error = 'blocked', str(exc)[:240]
    except HTTPException as exc:
        # Provider boundary was not crossed for validation failures.
        if exc.status_code == 429:
            row.status, row.error, row.due_at = 'queued', 'Provider rate limit; retry scheduled', now()+timedelta(minutes=2)
        else:
            row.status, row.error = 'blocked', str(exc.detail)[:240]


def process_customer_communications(db, limit=25):
    events = process_events(db, limit)
    scheduled = schedule_due(db, limit)
    ids = db.query(CustomerDelivery.id).filter(CustomerDelivery.status.in_(['queued', 'retry_wait']), CustomerDelivery.due_at <= now()).order_by(CustomerDelivery.due_at).limit(limit).all()
    for (identity,) in ids:
        row = db.query(CustomerDelivery).filter(CustomerDelivery.id == identity, CustomerDelivery.status.in_(['queued', 'retry_wait'])).with_for_update(skip_locked=True).first()
        if not row:
            continue
        try:
            with actor_scope(db, row.created_by, row.organization_id, row.branch_id, module='srm' if row.reminder_id else 'communication') as user:
                dispatch(db, row, user)
                db.commit()
        except (ValueError, HTTPException) as exc:
            db.rollback()
            row = db.get(CustomerDelivery, identity)
            if row is None:
                raise RuntimeError('Committed delivery disappeared during worker recovery') from exc
            row.status, row.error = 'blocked', 'Owner authorization unavailable; review before retry'
            db.commit()
    # Provider receipts remain authoritative, including out-of-order WA receipts.
    for row in db.query(CustomerDelivery).filter(CustomerDelivery.status.in_(['waiting_provider', 'accepted', 'sent', 'submitting'])).limit(limit):
        sync_delivery(db, row)
    db.commit()
    remind_notes(db, limit)
    return {'events': events, 'scheduled': scheduled, 'processed': len(ids)}


def remind_notes(db, limit):
    from .customer_models import CustomerConversationNote
    from app.models.notification import Notification
    notes = db.query(CustomerConversationNote).filter(CustomerConversationNote.reminded_at.is_(None),
        CustomerConversationNote.follow_up_at <= now()).order_by(CustomerConversationNote.follow_up_at).limit(limit).all()
    for note in notes:
        try:
            with actor_scope(db, note.created_by, note.organization_id, note.branch_id):
                claimed = db.execute(update(CustomerConversationNote).where(CustomerConversationNote.id == note.id,
                    CustomerConversationNote.reminded_at.is_(None)).values(reminded_at=now()), execution_options={'synchronize_session':False}).rowcount
                target = note.assigned_user_id or note.created_by
                from app.branches.service import access
                recipient_user = db.info.get('customer_communication_actor') if target == note.created_by else db.get(User, target)
                if claimed and recipient_user and recipient_user.is_active and note.branch_id in access(db, recipient_user, note.organization_id)[0]:
                    db.add(Notification(company_id=note.organization_id, user_id=target, title='Customer follow-up due',
                        message='A customer conversation needs your follow-up.', module='communication',
                        event_type='customer.followup.due', related_entity_type='customer_recipient', related_entity_id=note.recipient_id,
                        action_url='/crm/communication-hub?section=customers'))
                db.commit()
        except (ValueError, HTTPException):
            db.rollback()
