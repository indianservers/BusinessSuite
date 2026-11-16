"""One opted-in public enquiry reminder, fenced by consent and latest activity.

The worker queues through the normal transactional outbox; this module never
calls Telegram. Delivery must call authorize_delivery again before transport.
"""
import hashlib
import secrets
from datetime import timedelta, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from pydantic import Field, field_validator, model_validator
from app.apps.power_apps.contracts import Contract
from app.apps.power_apps.models import TelegramConversation
from app.apps.power_apps.runtime import now, utc


class FollowupPolicy(Contract):
    enabled: bool = True
    delay_hours: int = Field(default=24, ge=1, le=168)
    timezone: str = 'Asia/Kolkata'
    opens: str = Field(default='09:00', pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    closes: str = Field(default='18:00', pattern=r'^([01]\d|2[0-3]):[0-5]\d$')

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError('Choose a valid follow-up timezone') from error
        return value

    @model_validator(mode='after')
    def valid_window(self):
        if self.opens >= self.closes:
            raise ValueError('Follow-up hours must be a nonempty daytime window')
        return self


def policy(trigger):
    return FollowupPolicy.model_validate(trigger.config.get('followups', {}))


def consent(thread, command):
    """Handle exact explicit consent commands before AI, including during handoff."""
    parts = command.strip().casefold().split()
    value = ' '.join([parts[0].split('@')[0], *parts[1:]]) if parts else ''
    if value not in {'/followup on', '/followup off', '/stop', '/unsubscribe'}:
        return None
    if thread.interface != 'public':
        return 'Enquiry follow-ups are available in the public customer bot.'
    enabled = value == '/followup on'
    thread.context = {**(thread.context or {}), 'followup_consent': {
        'enabled': enabled, 'revision': secrets.token_hex(16), 'changed_at': now().isoformat(),
    }}
    return ('Enquiry follow-ups enabled. We may send one reminder per qualified enquiry after inactivity, during configured business hours. Send /stop to unsubscribe.'
            if enabled else 'Enquiry follow-ups stopped. You can continue chatting here. Send /followup on to opt in again.')


def enquiry_key(thread):
    requests = (thread.context or {}).get('requests', [])
    # Only native qualified enquiries, not greetings, browsing, or appointments.
    latest = requests[-1] if requests else {}
    if not latest.get('lead_id') or not latest.get('task_id') or latest.get('status') != 'received':
        return None
    return str(latest.get('update_id')) if latest.get('update_id') is not None else None


def binding(thread):
    record = (thread.context or {}).get('followup_consent', {})
    packet = f"{thread.id}:{record.get('revision')}:{enquiry_key(thread)}:{utc(thread.last_at).isoformat()}"
    return hashlib.sha256(packet.encode()).hexdigest()


def eligible(thread, settings, instant):
    context = thread.context or {}
    record = context.get('followup_consent', {})
    if (not settings.enabled or thread.interface != 'public' or thread.status in {'waiting', 'assigned', 'resolved'}
            or record.get('enabled') is not True or not enquiry_key(thread)):
        return False
    if context.get('followup_queued_for') == enquiry_key(thread):
        return False
    if instant < utc(thread.last_at) + timedelta(hours=settings.delay_hours):
        return False
    local = instant.astimezone(ZoneInfo(settings.timezone)).time().replace(tzinfo=None)
    return time.fromisoformat(settings.opens) <= local < time.fromisoformat(settings.closes)


def queue_due(db, resource, trigger, owner, limit=20):
    """Caller holds the current bot owner's Power Apps create/branch scope."""
    from app.apps.power_apps.telegram_audience import allows
    from app.apps.power_apps import telegram_operations as operations
    from app.apps.power_apps.runtime_models import AutomationRun
    settings = policy(trigger)
    if not settings.enabled or not allows(trigger, 'public') or not trigger.config.get('interfaces', {}).get('public_enabled', True):
        return 0
    instant = now()
    rows = db.query(TelegramConversation).filter_by(resource_id=resource.id,
        organization_id=resource.organization_id, environment=resource.environment, interface='public').filter(
        TelegramConversation.last_at <= instant - timedelta(hours=settings.delay_hours),
        TelegramConversation.context['followup_consent']['enabled'].as_boolean() == True).order_by(
        TelegramConversation.last_at).with_for_update(skip_locked=True).yield_per(50)
    queued = 0
    for thread in rows:
        if not eligible(thread, settings, instant):
            continue
        key = enquiry_key(thread)
        fence = binding(thread)
        text = 'Would you like help with your enquiry? Reply here or send /human to speak with the team. Send /stop to stop enquiry follow-ups.'
        run_id = operations.queue_reply(db, resource, trigger, owner, thread, text,
            f'telegram-followup:{thread.id}:{key}')
        run = db.get(AutomationRun, run_id)
        run.input_payload = {**run.input_payload, 'telegram_followup_binding': fence}
        thread.context = {**thread.context, 'followup_queued_for': key}
        queued += 1
        if queued >= limit:
            break
    return queued


def authorize_delivery(trigger, thread, payload):
    """Reject queued reminders after unsubscribe, new activity or quiet-hour changes."""
    fence = payload.get('telegram_followup_binding')
    if not fence:
        return
    settings = policy(trigger)
    record = (thread.context or {}).get('followup_consent', {})
    local = now().astimezone(ZoneInfo(settings.timezone)).time().replace(tzinfo=None)
    if (not settings.enabled or thread.interface != 'public' or thread.status in {'waiting', 'assigned', 'resolved'}
            or record.get('enabled') is not True or fence != binding(thread)
            or not time.fromisoformat(settings.opens) <= local < time.fromisoformat(settings.closes)):
        raise HTTPException(403, 'Enquiry follow-up consent, activity or delivery window changed')
