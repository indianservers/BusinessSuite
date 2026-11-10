"""Reviewed, expiring reminders on the existing durable scheduler and email outbox."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone, time
from types import SimpleNamespace
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai_operator.suite_tools import Strict
from app.apps.automation.models import AutomationScheduledJob as Job
from app.core.deps import get_db, get_current_user
from app.models.user import User

router = APIRouter(prefix='/suite', tags=['AI reminders'])
MODULES = {'CRM': 'crm', 'PMS': 'project_management', 'HRMS': 'hrms', 'SRM': 'srm'}
ENTITIES = {'CRM': {'task', 'lead', 'deal'}, 'PMS': {'task', 'project'}, 'HRMS': {'leave'}, 'SRM': {'invoice'}}


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class ReminderInput(Strict):
    request_key: UUID
    module: Literal['CRM', 'PMS', 'HRMS', 'SRM']
    entity: Literal['task', 'lead', 'deal', 'project', 'leave', 'invoice']
    record_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=180)
    scheduled_at: datetime
    expires_at: datetime
    timezone: str = Field(default='Asia/Kolkata', max_length=80)
    frequency: Literal['once', 'daily', 'weekly'] = 'once'
    recipient_ids: list[int] = Field(default_factory=list, max_length=20)
    channels: list[Literal['in_app', 'email']] = Field(default_factory=lambda: ['in_app'], min_length=1, max_length=2)
    quiet_start: str | None = Field(default=None, pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    quiet_end: str | None = Field(default=None, pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')

    @model_validator(mode='after')
    def valid(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Choose an IANA timezone') from None
        if self.entity not in ENTITIES[self.module]:
            raise ValueError('Unsupported reminder source')
        if self.scheduled_at.utcoffset() is None or self.expires_at.utcoffset() is None:
            raise ValueError('Use timezone-aware schedule and expiry times')
        if self.expires_at <= self.scheduled_at or self.expires_at > now() + timedelta(days=366):
            raise ValueError('Expiry must follow the first reminder and be within one year')
        if bool(self.quiet_start) != bool(self.quiet_end) or self.quiet_start and self.quiet_start == self.quiet_end:
            raise ValueError('Provide a nonempty quiet-hours interval')
        if any(type(value) is not int or value <= 0 for value in self.recipient_ids):
            raise ValueError('Recipients must be existing user IDs')
        return self


def after_quiet(instant, spec):
    if not spec.get('quiet_start'):
        return instant
    zone = ZoneInfo(spec['timezone']); local = instant.astimezone(zone)
    start, end = time.fromisoformat(spec['quiet_start']), time.fromisoformat(spec['quiet_end'])
    clock = local.time().replace(tzinfo=None)
    overnight = start > end
    inside = start <= clock < end if not overnight else clock >= start or clock < end
    if not inside:
        return instant
    day = local.date() + timedelta(days=1 if overnight and clock >= start else 0)
    # Round-trip through UTC normalizes nonexistent spring-forward wall times.
    candidate = datetime.combine(day, end, tzinfo=zone).astimezone(timezone.utc)
    return candidate if candidate > instant else instant + timedelta(minutes=1)


def next_occurrence(spec, current):
    if spec['frequency'] == 'once':
        return None
    zone = ZoneInfo(spec['timezone']); anchor = datetime.fromisoformat(spec['scheduled_at']).astimezone(zone)
    day = current.astimezone(zone).date()
    for offset in range(9):
        candidate_day = day + timedelta(days=offset)
        if spec['frequency'] == 'weekly' and candidate_day.weekday() != anchor.weekday():
            continue
        candidate = datetime.combine(candidate_day, anchor.time().replace(tzinfo=None), tzinfo=zone).astimezone(timezone.utc)
        if candidate > current:
            return candidate
    raise ValueError('No next reminder occurrence')


def source(db, user, spec):
    from app.access.service import check_background_access
    from app.ai_agents.security import source_record_access, company, scoped
    module = MODULES[spec['module']]
    check_background_access(db, user, module, 'view')
    if spec['module'] == 'CRM' and spec['entity'] == 'task':
        from app.apps.crm.api.router import _get_resource, _assert_record_visible, _base_query, _assert_entity_permission
        with scoped(db, user, 'crm'):
            _assert_entity_permission('tasks', user, 'view')
            resource = _get_resource('tasks')
            _assert_record_visible(db, resource, spec['record_id'], company(user), user)
            record = _base_query(db, resource, company(user)).filter(resource.model.id == spec['record_id']).first()
    else:
        record = source_record_access(db, user, module, spec['entity'], spec['record_id'])
    if isinstance(record, tuple):
        record = record[0]
    return {'status': str(record.get('status', '') if isinstance(record, dict) else getattr(record, 'status', '')),
            'href': f"/pms/{'tasks' if spec['entity'] == 'task' else 'projects'}/{spec['record_id']}" if spec['module'] == 'PMS' else
                    '/leave' if spec['module'] == 'HRMS' else '/srm/invoices' if spec['module'] == 'SRM' else '/crm/' + {'task': 'tasks', 'lead': 'leads', 'deal': 'deals'}[spec['entity']]}


def signature_for(row):
    from app.ai_agents.security import signature
    data = row.payload_json
    return signature({'owner': row.created_by, 'company': row.organization_id, 'branch': data['branch_id'],
                      'spec': data['spec'], 'recipients': data['recipients'], 'href': data['href']})


def email_body(row):
    from app.core.config import settings
    return 'A reviewed reminder is due. Sign in to review the linked record:\n' + settings.FRONTEND_PUBLIC_URL.rstrip('/') + row.payload_json['href']


def owned(db, user, ident, lock=False, kind='ai_reminder'):
    from app.ai_operator.suite import authorize
    from app.ai_agents.security import company
    authorize(db, user, None)
    query = db.query(Job).filter_by(id=ident, job_type=kind, created_by=user.id, organization_id=company(user))
    row = (query.with_for_update().populate_existing() if lock else query).first()
    if not row:
        raise HTTPException(404, 'Assistant schedule not found')
    return row


@contextmanager
def owner_scope(db, row):
    from app.access.service import activate_run_context, release_run_context, background_scope
    from app.ai_operator.suite import authorize
    actor = db.query(User).filter_by(id=row.created_by, is_active=True).populate_existing().first()
    if not actor:
        raise HTTPException(403, 'Owner unavailable')
    activate_run_context(db, actor, SimpleNamespace(scope_key=f'company:{row.organization_id}'))
    try:
        with background_scope(db, actor, row.module_name, 'view', branch_id=row.payload_json['branch_id']):
            authorize(db, actor, None, row.payload_json['spec']['module'])
            yield actor
    finally:
        release_run_context(db)


def recipients(db, actor, spec):
    from app.core.tenant_boundary import company_ids
    from app.ai_agents.security import company, scoped
    result = []
    for identity in sorted(set(spec['recipient_ids'] or [actor.id])):
        person = db.query(User).filter_by(id=identity, is_active=True).first()
        if not person or company(actor) not in company_ids(db, person):
            raise HTTPException(403, 'Recipient is outside the authorized company')
        previous = getattr(person, 'organization_id', None)
        person.organization_id = company(actor)
        try:
            with scoped(db, person, MODULES[spec['module']]):
                source(db, person, spec)
            if 'email' in spec['channels'] and (not person.email or '@' not in person.email):
                raise HTTPException(422, 'Recipient has no verified email identity')
            result.append({'id': person.id, 'email': person.email})
        finally:
            if previous is None:
                person.__dict__.pop('organization_id', None)
            else:
                person.organization_id = previous
    return result


def public(row):
    data = row.payload_json
    return {'id': row.id, 'status': row.status.removeprefix('ai_'), 'spec': data['spec'], 'recipients': data['recipients'],
            'preview_hash': data['preview_hash'], 'next_at': row.run_at, 'error': row.last_error,
            'receipts': data.get('receipts', []), 'email_preview': {'subject': 'BusinessSuite reminder', 'body': email_body(row)}}


@router.post('/reminders/preview')
def preview(data: ReminderInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.suite import authorize, digest
    from app.ai_agents.security import seal, company
    authorize(db, user, None, data.module)
    if data.scheduled_at <= now():
        raise HTTPException(422, 'Choose a future first reminder')
    spec = data.model_dump(mode='json', exclude={'request_key'})
    spec['recipient_ids'] = sorted(set(spec['recipient_ids'] or [user.id]))
    spec['channels'] = sorted(set(spec['channels']))
    current = source(db, user, spec)
    people = recipients(db, user, spec)
    branch = db.info.get('branch_context')
    if not branch or not branch.branch_id:
        raise HTTPException(422, 'Select a concrete branch before preparing reminders')
    fingerprint = digest({'spec': spec, 'branch_id': branch.branch_id, 'recipients': people})
    existing = db.query(Job).filter(Job.created_by == user.id, Job.organization_id == company(user), Job.job_type == 'ai_reminder',
                                    Job.payload_json['ai_request_key'].as_string() == str(data.request_key)).first()
    if existing:
        if existing.payload_json['preview_hash'] != fingerprint:
            raise HTTPException(409, 'Request key belongs to a different reminder')
        return public(existing)
    row = Job(job_type='ai_reminder', module_name=MODULES[data.module], record_type=data.entity, record_id=data.record_id,
              created_by=user.id, organization_id=company(user), status='ai_preview', run_at=data.scheduled_at,
              payload_json={'ai_request_key': str(data.request_key), 'branch_id': branch.branch_id, 'spec': spec, 'recipients': people,
                            'href': current['href'], 'preview_hash': fingerprint, 'security_context': seal(db, user, fingerprint), 'receipts': []})
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.query(Job).filter(Job.created_by == user.id, Job.organization_id == company(user), Job.job_type == 'ai_reminder', Job.payload_json['ai_request_key'].as_string() == str(data.request_key)).first()
        if not row or row.payload_json['preview_hash'] != fingerprint:
            raise HTTPException(409, 'Conflicting reminder request') from None
    return public(row)


class Approval(Strict):
    preview_hash: str = Field(min_length=64, max_length=64)


@router.get('/reminders/{ident}/receipts')
def receipts(ident: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.email_outbox import EmailOutbox
    row = owned(db, user, ident)
    identities = [identity for receipt in row.payload_json.get('receipts', []) for identity in receipt['email_ids']]
    emails = db.query(EmailOutbox).filter(EmailOutbox.id.in_(identities), EmailOutbox.module == 'ai_reminder', EmailOutbox.event_key.like(f'ai-reminder:{row.id}:%')).all() if identities else []
    return {'items': [{'id': email.id, 'status': email.status, 'provider_message_id': email.provider_message_id, 'error': email.error} for email in emails],
            'note': 'Accepted means provider acceptance, not recipient delivery. Unknown outcomes are never automatically resent.'}


class Resolution(Strict):
    decision: Literal['confirmed_sent', 'confirmed_not_sent']
    evidence_reference: str = Field(min_length=3, max_length=300)


@router.post('/reminders/{ident}/receipts/{email_id}/reconcile')
def reconcile_email(ident: int, email_id: int, data: Resolution, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.email_outbox import EmailOutbox
    from app.ai_agents.services.audit import AiAuditService
    row = owned(db, user, ident, True)
    if not any(email_id in receipt['email_ids'] for receipt in row.payload_json.get('receipts', [])):
        raise HTTPException(404, 'Reminder receipt not found')
    email = db.query(EmailOutbox).filter_by(id=email_id, module='ai_reminder', organization_id=row.organization_id).with_for_update().first()
    if not email or email.status != 'reconciliation_required':
        raise HTTPException(409, 'Only uncertain sends can be manually reconciled')
    email.status = 'manually_' + data.decision
    email.error = 'Owner recorded a manual provider check; no message was resent'
    AiAuditService(db).log(user=user, agent_id=None, module=row.payload_json['spec']['module'], action='ai.reminder.reconciled',
        input_json={'reminder_id': row.id, 'email_id': email.id, 'decision': data.decision, 'evidence_reference': data.evidence_reference},
        output_json={'manual': True, 'resent': False}, status='success')
    db.commit()
    return {'id': email.id, 'status': email.status, 'resent': False, 'manual': True}


@router.post('/reminders/{ident}/approve')
def approve(ident: int, data: Approval, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_agents.security import verify
    row = owned(db, user, ident, True)
    if data.preview_hash != row.payload_json['preview_hash']:
        raise HTTPException(409, 'Reminder changed; review the exact preview')
    if row.status == 'ai_active':
        return public(row)
    if row.status != 'ai_preview' or utc(row.run_at) <= now():
        raise HTTPException(409, 'Prepare a new future reminder preview')
    verify(db, user, row.payload_json['security_context'], row.payload_json['preview_hash'], confirmation=True)
    source(db, user, row.payload_json['spec'])
    if recipients(db, user, row.payload_json['spec']) != row.payload_json['recipients']:
        raise HTTPException(409, 'Recipient identities changed; prepare a new preview')
    row.payload_json = {**row.payload_json, 'grant_signature': signature_for(row), 'approved_at': now().isoformat()}
    row.status = 'ai_active'
    db.commit()
    return public(row)


@router.get('/reminders')
def listing(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ai_operator.suite import authorize
    from app.ai_agents.security import company
    authorize(db, user, None)
    rows = db.query(Job).filter_by(job_type='ai_reminder', created_by=user.id, organization_id=company(user)).order_by(Job.id.desc()).limit(100)
    return {'items': [public(row) for row in rows]}


@router.post('/reminders/{ident}/cancel')
def cancel(ident: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.email_outbox import EmailOutbox
    row = owned(db, user, ident, True)
    row.status = 'ai_cancelled'
    db.query(EmailOutbox).filter(EmailOutbox.event_key.like(f'ai-reminder:{ident}:%'), EmailOutbox.status.in_(['queued', 'ai_deferred'])).update({'status': 'suppressed'}, synchronize_session=False)
    db.commit()
    return public(row)


@router.post('/reminders/create-approved')
def create_approved(data:ReminderInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    """Submit a complete schedule through the native preview and grant checks."""
    value=preview(data,db,user)
    return approve(value['id'],Approval(preview_hash=value['preview_hash']),db,user)


def valid_grant(db, row, actor, instant):
    import hmac
    if row.status not in {'ai_active', 'ai_complete'} or not hmac.compare_digest(row.payload_json.get('grant_signature', ''), signature_for(row)):
        raise HTTPException(403, 'Reminder grant is unavailable or modified')
    spec = row.payload_json['spec']
    if instant >= datetime.fromisoformat(spec['expires_at']):
        raise HTTPException(403, 'Reminder expired')
    current = source(db, actor, spec)
    if current['status'].strip().lower() in {'done', 'completed', 'closed', 'cancelled', 'canceled', 'paid', 'rejected'}:
        raise HTTPException(409, 'Linked work is no longer pending')
    if recipients(db, actor, spec) != row.payload_json['recipients']:
        raise HTTPException(403, 'Recipient authorization changed')


@contextmanager
def email_scope(db, outbox):
    identity = int(outbox.event_key.split(':')[1])
    row = db.query(Job).filter_by(id=identity, job_type='ai_reminder', organization_id=outbox.organization_id).with_for_update().first()
    if not row:
        raise HTTPException(403, 'Reminder unavailable')
    with owner_scope(db, row) as actor:
        valid_grant(db, row, actor, now())
        if outbox.recipient_user_id not in row.payload_json['spec']['recipient_ids'] or not any(p['id'] == outbox.recipient_user_id and p['email'] == outbox.recipient for p in row.payload_json['recipients']):
            raise HTTPException(403, 'Email recipient does not match the reviewed reminder')
        if outbox.subject != 'BusinessSuite reminder' or outbox.body != email_body(row) or not any(outbox.id in receipt['email_ids'] and outbox.event_key == f'ai-reminder:{row.id}:{receipt["occurrence"]}:{outbox.recipient_user_id}' for receipt in row.payload_json.get('receipts', [])):
            raise HTTPException(403, 'Email does not match a prepared reminder occurrence')
        instant = now()
        yield after_quiet(instant, row.payload_json['spec']) > instant


def dispatch(db, instant=None, limit=20):
    from app.models.email_outbox import EmailOutbox
    from app.services.email_dispatch import queue_email
    from app.services.notifications import create_notification
    from app.schemas.notification import NotificationCreate
    instant = instant or now(); processed = 0
    # Deferred email is eligible again only after a fresh live authorization check at send time.
    for email in db.query(EmailOutbox).filter_by(status='ai_deferred', module='ai_reminder').limit(limit):
        try:
            with email_scope(db, email) as quiet:
                if not quiet:
                    email.status = 'queued'
        except HTTPException:
            email.status = 'suppressed'
    db.commit()
    for _ in range(min(limit, 50)):
        row = db.query(Job).filter(Job.job_type == 'ai_reminder', Job.status == 'ai_active', Job.run_at <= instant).order_by(Job.run_at, Job.id).with_for_update(skip_locked=True).first()
        if not row:
            break
        try:
            with owner_scope(db, row) as actor:
                spec = row.payload_json['spec']
                valid_grant(db, row, actor, instant)
                allowed_at = after_quiet(instant, spec)
                if allowed_at > instant:
                    row.run_at = allowed_at
                else:
                    occurrence = utc(row.run_at).isoformat()
                    claimed = db.query(Job).filter_by(id=row.id, status='ai_active', run_at=row.run_at).update({'status': 'ai_preparing'}, synchronize_session=False)
                    if not claimed:
                        db.rollback(); continue
                    receipt = {'occurrence': occurrence, 'notification_ids': [], 'email_ids': []}
                    previous = db.info.get('suppress_email_events')
                    db.info['suppress_email_events'] = True
                    try:
                        for person in row.payload_json['recipients']:
                            if 'in_app' in spec['channels']:
                                notification = create_notification(db, NotificationCreate(company_id=row.organization_id, user_id=person['id'], title=spec['title'], message='A reviewed reminder is due. Open the linked record.', module=row.module_name, event_type='ai.reminder', action_url=row.payload_json['href']), commit=False)
                                receipt['notification_ids'].append(notification.id)
                            if 'email' in spec['channels']:
                                email = queue_email(db, recipient=person['email'], user_id=person['id'], organization_id=row.organization_id,
                                    subject='BusinessSuite reminder', body=email_body(row),
                                    module='ai_reminder', event_key=f'ai-reminder:{row.id}:{occurrence}:{person["id"]}')
                                db.flush()
                                if email:
                                    receipt['email_ids'].append(email.id)
                    finally:
                        if previous is None: db.info.pop('suppress_email_events', None)
                        else: db.info['suppress_email_events'] = previous
                    next_at = next_occurrence(spec, instant)
                    row.run_at = next_at
                    row.status = 'ai_active' if next_at and next_at < datetime.fromisoformat(spec['expires_at']) else 'ai_complete'
                    row.payload_json = {**row.payload_json, 'receipts': [*row.payload_json.get('receipts', []), receipt][-20:]}
                    row.last_error = None
        except HTTPException:
            identity = row.id
            db.rollback()  # Notification, outbox and occurrence state are one atomic preparation.
            row = db.query(Job).filter_by(id=identity, job_type='ai_reminder').with_for_update().one()
            row.status = 'ai_blocked'; row.last_error = 'Owner, source, recipient or expiry no longer permits this reminder. Prepare a fresh preview.'
        db.commit(); processed += 1
    return {'processed': processed}
