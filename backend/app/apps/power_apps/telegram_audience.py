"""Server-owned bot purpose, independent of user commands and stored identities."""
from fastapi import HTTPException

PUBLIC_NOTICE = 'This bot is for public enquiries. Use your company’s separate employee bot for company access.'
COMPANY_NOTICE = 'This bot is for verified employees only. Ask your company administrator to link your Telegram ID or generate your own one-time company linking code in BusinessSuite.'
COMPANY_PUBLIC_NOTICE = 'This is the employee bot. Use the separate public bot for customer enquiries and customer account access.'


def audience(trigger):
    value = trigger.config.get('audience', 'shared')
    return value if value in {'public', 'company', 'shared'} else 'public'


def allows(trigger, interface):
    return interface in {'public', 'company'} and audience(trigger) in {'shared', interface}


def require(trigger, interface):
    if not allows(trigger, interface):
        raise HTTPException(403, PUBLIC_NOTICE if audience(trigger) == 'public' else COMPANY_PUBLIC_NOTICE)


def trigger_for(db, resource):
    from app.apps.power_apps.runtime_models import AutomationTrigger
    trigger = db.query(AutomationTrigger).filter_by(resource_id=resource.id, kind='telegram').first()
    if not trigger:
        raise HTTPException(404, 'Telegram listener not found')
    return trigger


def safe_verification_notice(text, telegram_id):
    return text == COMPANY_NOTICE or text == f'Your Telegram user ID is {telegram_id}. Give this numeric ID to your company administrator to link your employee account.'


def change(db, resource, trigger, selected):
    """Invalidate incompatible work rather than transferring identity or history."""
    previous = audience(trigger)
    if previous == selected:
        return
    from app.apps.power_apps.models import TelegramIdentity, TelegramConversation, TelegramLinkChallenge, TelegramActionApproval
    from app.apps.power_apps.runtime_models import AutomationEvent
    from app.apps.power_apps.runtime import now
    disallowed = 'company' if selected == 'public' else 'public' if selected == 'company' else None
    if disallowed:
        for linked in db.query(TelegramIdentity).filter_by(resource_id=resource.id, interface=disallowed, revoked_at=None).all():
            linked.revoked_at = now()
        for challenge in db.query(TelegramLinkChallenge).filter_by(resource_id=resource.id, interface=disallowed, consumed_at=None).all():
            challenge.consumed_at = now()
        threads = db.query(TelegramConversation).filter_by(resource_id=resource.id, interface=disallowed).all()
        ids = [thread.id for thread in threads]
        for thread in threads:
            thread.state, thread.context = {}, {}
            thread.status, thread.assignee_user_id = 'resolved', None
        if ids:
            for item in db.query(TelegramActionApproval).filter(TelegramActionApproval.resource_id == resource.id,
                    TelegramActionApproval.conversation_id.in_(ids), TelegramActionApproval.status.in_(['pending', 'approve_requested', 'reject_requested', 'executing'])).all():
                item.status = 'needs_reconciliation' if item.status == 'executing' else 'failed'
                item.result = {**(item.result or {}), 'error': 'Bot audience changed. This authorization cannot be reused.'}
            for event in db.query(AutomationEvent).filter_by(resource_id=resource.id).filter(AutomationEvent.kind.in_(['telegram_ai_request', 'telegram_stage_review'])).all():
                if event.details.get('conversation_id') in ids or event.details.get('operation', {}).get('conversation_id') in ids:
                    event.details = {**event.details, 'status': 'superseded'}
    trigger.config = {**trigger.config, 'audience': selected}
