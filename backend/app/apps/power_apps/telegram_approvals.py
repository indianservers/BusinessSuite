"""Exact, expiring, identity-bound action review inside Telegram."""
import hashlib
import json
import secrets
from datetime import timedelta

from fastapi import HTTPException
from app.access.service import background_scope
from app.apps.power_apps.models import TelegramActionApproval as Approval, TelegramIdentity, TelegramConversation, PowerResource
from app.apps.power_apps.runtime_models import AutomationTrigger as Trigger
from app.apps.power_apps.runtime import now, utc
from app.apps.power_apps import telegram_operations as operations


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str).encode()).hexdigest()


def binding(linked):
    return {'identity_id': linked.id, 'user_id': linked.user_id, 'verified_at': utc(linked.verified_at).isoformat() if linked.verified_at else None}


def markup(token, page, count):
    actions = [{'text': 'Approve', 'callback_data': f'approve:{token}'}] if page == count - 1 else [{'text': 'Next details', 'callback_data': f'review:{token}:{page + 1}'}]
    return {'inline_keyboard': [actions + [{'text': 'Reject', 'callback_data': f'reject:{token}'}]]}


def page_text(approval, page):
    chunks = approval.operation['_preview']
    return f'Review {page + 1}/{len(chunks)} · expires {utc(approval.expires_at).isoformat()}\n\n{chunks[page]}\n\nNo change is executed until you approve the final page.'


def issue(db, resource, thread, linked, kind, operation, preview, minutes=15):
    from app.apps.power_apps.telegram_audience import require, trigger_for
    require(trigger_for(db, resource), thread.interface)
    if kind == 'suite':
        require(trigger_for(db, resource), 'company')
    if not linked or linked.revoked_at or not linked.verified_at:
        raise HTTPException(403, 'Verify this Telegram identity before approving business actions')
    if kind == 'suite' and (thread.interface != 'company' or not linked.user_id):
        raise HTTPException(403, 'Only linked employees can review ActionBot business actions')
    if kind == 'suite':
        from app.ai_operator import suite
        from app.apps.power_apps.runtime_models import AutomationTrigger
        trigger = db.query(AutomationTrigger).filter_by(resource_id=resource.id, kind='telegram').one()
        user = operations.staff_member(db, linked, resource.organization_id)
        with background_scope(db, user, 'ai', 'view', branch_id=trigger.config.get('branch_id')):
            run = suite.owned(db, user, operation['suite_run_id'])
            if run.status != 'awaiting_approval' or run.plan_hash != operation['plan_hash'] or suite.digest(run.plan) != operation['plan_hash']:
                raise HTTPException(409, 'The ActionBot proposal changed; prepare a fresh review')
    chunks = [preview[index:index + 3200] for index in range(0, len(preview), 3200)] or ['No operation details']
    if len(chunks) > 64:
        raise HTTPException(422, 'This action is too large for Telegram review; use BusinessSuite')
    payload = {**operation, '_binding': binding(linked), '_preview': chunks}
    token = secrets.token_hex(16)
    row = Approval(resource_id=resource.id, organization_id=resource.organization_id, environment=resource.environment,
        conversation_id=thread.id, identity_id=linked.id, token_hash=hashlib.sha256(token.encode()).hexdigest(), kind=kind,
        operation=payload, operation_hash=digest(payload), status='pending', result={'viewed_page': 0}, expires_at=now() + timedelta(minutes=minutes))
    db.add(row); db.flush()
    return row, page_text(row, 0), markup(token, 0, len(chunks))


def validate(db, resource, thread, linked, approval):
    from app.apps.power_apps.telegram_audience import require, trigger_for
    trigger = trigger_for(db, resource)
    require(trigger, thread.interface)
    if approval.kind == 'suite':
        require(trigger, 'company')
    if approval.resource_id != resource.id or approval.conversation_id != thread.id or approval.organization_id != resource.organization_id or approval.environment != resource.environment:
        raise HTTPException(403, 'This review belongs to another conversation')
    if not linked or linked.revoked_at or not linked.verified_at or approval.identity_id != linked.id or approval.operation.get('_binding') != binding(linked):
        raise HTTPException(403, 'The Telegram identity changed; request a fresh review')
    if approval.operation_hash != digest(approval.operation):
        raise HTTPException(409, 'The proposed action changed; request a fresh review')
    if utc(approval.expires_at) <= now():
        raise HTTPException(409, 'This review expired; request a fresh proposal')
    if thread.interface == 'company':
        operations.staff_member(db, linked, resource.organization_id)


def respond(db, resource, thread, linked, text):
    parts = text.split()
    if len(parts) not in {2, 3} or len(parts[1]) != 32:
        raise HTTPException(422, 'Use the buttons on the current action review')
    token = parts[1]
    row = db.query(Approval).filter_by(resource_id=resource.id, token_hash=hashlib.sha256(token.encode()).hexdigest()).with_for_update().first()
    if not row:
        raise HTTPException(404, 'This action review is unavailable')
    validate(db, resource, thread, linked, row)
    action = parts[0]
    if row.status != 'pending':
        return f'This review is already {row.status.replace("_", " ")}.', None
    if action == '/review':
        try:
            page = int(parts[2])
        except (IndexError, ValueError):
            raise HTTPException(422, 'Use the next-details button')
        if not 0 <= page < len(row.operation['_preview']) or page > row.result['viewed_page'] + 1:
            raise HTTPException(409, 'Review the operation pages in order')
        row.result = {**row.result, 'viewed_page': max(page, row.result['viewed_page'])}
        return page_text(row, page), markup(token, page, len(row.operation['_preview']))
    if action == '/approve':
        if thread.status in {'waiting', 'assigned'}:
            raise HTTPException(409, 'Return the conversation to the bot before approving an action')
        if row.result['viewed_page'] != len(row.operation['_preview']) - 1:
            raise HTTPException(409, 'Review all operation details before approving')
        row.status = 'approve_requested'
        return 'Approval received. Current permissions and the exact proposed action will be checked again before execution.', None
    if action == '/reject':
        row.status = 'reject_requested'
        return 'Rejection received. This proposal will not be executed.', None
    raise HTTPException(422, 'Unsupported action review control')


def validate_origin(db, user, run):
    origin = (run.result or {}).get('telegram_origin')
    if not origin:
        return None
    resource = db.get(PowerResource, origin['resource_id'])
    trigger = db.query(Trigger).filter_by(resource_id=origin['resource_id'], kind='telegram', enabled=True).first()
    thread = db.get(TelegramConversation, origin['conversation_id'])
    linked = db.query(TelegramIdentity).filter_by(id=origin['identity_id'], resource_id=origin['resource_id'], revoked_at=None).first()
    if not resource or not trigger or not thread or not linked or linked.user_id != user.id or resource.organization_id != user.organization_id or binding(linked) != origin['binding']:
        raise HTTPException(403, 'Telegram execution authorization was revoked')
    from app.apps.power_apps.telegram_audience import require
    require(trigger, 'company')
    if thread.interface != 'company':
        raise HTTPException(403, 'Company action origin is unavailable')
    operations.staff_member(db, linked, resource.organization_id)
    review = db.get(Approval, origin.get('approval_id')) if origin.get('approval_id') else None
    if not review or review.status not in {'approve_requested', 'executing'} or utc(review.expires_at) <= now() or review.operation_hash != digest(review.operation) or review.operation.get('plan_hash') != run.plan_hash:
        raise HTTPException(403, 'The Telegram approval is no longer valid')
    if thread.status in {'waiting', 'assigned'}:
        raise HTTPException(403, 'Telegram action execution paused for human handoff')
    if not trigger.config.get('interfaces', {}).get('company_enabled', True):
        raise HTTPException(403, 'Company Telegram access is disabled')
    return trigger.config.get('branch_id')


async def dispatch(db, app, limit=5):
    ids = db.query(Approval.id).filter(Approval.status.in_(['approve_requested', 'reject_requested', 'executing'])).order_by(Approval.id).limit(limit).all()
    for (ident,) in ids:
        row = db.query(Approval).filter_by(id=ident).with_for_update(skip_locked=True).populate_existing().first()
        if not row or row.status not in {'approve_requested', 'reject_requested', 'executing'}:
            db.rollback(); continue
        try:
            from app.apps.power_apps.runtime_triggers import trigger_identity
            resource = db.get(PowerResource, row.resource_id)
            trigger = db.query(Trigger).filter_by(resource_id=row.resource_id, kind='telegram', enabled=True).first()
            if not resource or not trigger:
                raise HTTPException(403, 'Telegram bot was disabled')
            owner = trigger_identity(db, trigger)
            with background_scope(db, owner, 'power_apps', 'create', branch_id=trigger.config.get('branch_id')):
                thread = db.get(TelegramConversation, row.conversation_id)
                linked = db.get(TelegramIdentity, row.identity_id)
                validate(db, resource, thread, linked, row)
                if row.status != 'reject_requested' and thread.status in {'waiting', 'assigned'}:
                    raise HTTPException(409, 'Action execution is paused for human handoff')
            next_status, next_result = row.status, dict(row.result or {})
            if row.kind == 'suite':
                from app.ai_operator import suite
                user = operations.staff_member(db, linked, resource.organization_id)
                # Employee-private run/session records use the employee's
                # boundary alone. Bot-owned review/outbox writes follow below.
                with background_scope(db, user, 'ai', 'view', branch_id=trigger.config.get('branch_id')):
                    run = suite.owned(db, user, row.operation['suite_run_id'], True)
                    if run.plan_hash != row.operation['plan_hash'] or suite.digest(run.plan) != row.operation['plan_hash']:
                        raise HTTPException(409, 'The ActionBot plan changed')
                    if row.status == 'reject_requested':
                        from fastapi import Request
                        await suite.cancel(run.id, Request({'type': 'http', 'app': app, 'headers': []}), db, user)
                        next_status = 'rejected'
                    elif row.status == 'approve_requested':
                        run.result = {**(run.result or {}), 'telegram_origin': {'resource_id': resource.id, 'conversation_id': thread.id, 'identity_id': linked.id, 'approval_id': row.id, 'binding': binding(linked)}}
                        # Flush before approve's populate_existing reload. Its
                        # queued commit must include provenance atomically.
                        db.flush()
                        suite.approve(run.id, suite.Approval(plan_hash=row.operation['plan_hash']), db, user)
                        next_status = 'executing'
                    elif run.status in {'succeeded', 'failed', 'cancelled', 'needs_reconciliation', 'paused'}:
                        next_status = 'approved' if run.status == 'succeeded' else run.status
                        next_result = {**next_result, 'suite_run_id': run.id, 'execution_status': run.status, 'receipts': run.receipts}
            with background_scope(db, owner, 'power_apps', 'create', branch_id=trigger.config.get('branch_id')):
                row.status, row.result = next_status, next_result
                if row.kind != 'suite':
                    from app.apps.power_apps.telegram_booking import execute_approval
                    result = execute_approval(db, resource, trigger, owner, thread, linked, row)
                    row.result, row.status = {**row.result, **result}, 'rejected' if row.status == 'reject_requested' else 'approved'
                if row.status not in {'executing', 'approve_requested'}:
                    reply = 'Action completed.' if row.status == 'approved' else 'Proposal rejected.' if row.status == 'rejected' else 'The action needs attention. No successful change is being claimed.'
                    if row.status == 'approved' and row.kind == 'booking':
                        action = row.operation['action']
                        label = 'cancelled' if action == 'cancel' else 'rescheduled' if action == 'reschedule' else 'confirmed'
                        reply = f"Appointment #{row.result['appointment_id']} {label}." + (f"\nTime: {row.operation['starts_at']}\nDuration: {row.operation['duration_minutes']} minutes" if action != 'cancel' else '')
                    operations.queue_reply(db, resource, trigger, owner, thread, reply, f'telegram-approval-result:{row.id}')
                db.commit()
        except Exception:
            db.rollback()
            row = db.query(Approval).filter_by(id=ident).with_for_update().first()
            if row:
                uncertain = row.status == 'executing'
                row.status = 'needs_reconciliation' if uncertain else 'failed'
                row.result = {**row.result, 'error': 'Execution may have started. Review the canonical ActionBot receipts before retrying.' if uncertain else 'Current authorization or the operation changed. Request a fresh review.'}
                db.commit()
                try:
                    from app.apps.power_apps.runtime_triggers import trigger_identity
                    resource = db.get(PowerResource, row.resource_id)
                    trigger = db.query(Trigger).filter_by(resource_id=row.resource_id, kind='telegram', enabled=True).first()
                    owner = trigger_identity(db, trigger)
                    with background_scope(db, owner, 'power_apps', 'create', branch_id=trigger.config.get('branch_id')):
                        thread = db.get(TelegramConversation, row.conversation_id)
                        notice = 'Execution may have started, but its final result needs staff review. Check ActionBot receipts before retrying.' if uncertain else 'This action could not be completed. The slot, request or current permissions may have changed. Please choose again or contact the team.'
                        operations.queue_reply(db, resource, trigger, owner, thread, notice, f'telegram-approval-failed:{row.id}', handoff_notice=True)
                        db.commit()
                except Exception:
                    db.rollback()
