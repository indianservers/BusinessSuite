"""Version-bound service stages and explicit human approval of industry intake."""
from datetime import datetime, timedelta

from fastapi import HTTPException
from app.models.notification import Notification
from app.apps.power_apps.models import TelegramConversation
from app.apps.power_apps.runtime_models import AutomationEvent as Event
from app.apps.power_apps.runtime import now, utc, scope_values
from app.apps.power_apps.telegram_experience import configuration
from app.apps.power_apps.telegram_approvals import digest


def current_flow(trigger, thread):
    config = configuration(trigger)
    context = thread.context or {}
    if context.get('workflow_revision') != config.revision:
        raise HTTPException(409, 'The industry workflow changed. Start a fresh service request.')
    flow = next((item for item in config.workflows if item.id == context.get('workflow_id') and item.enabled), None)
    if not flow:
        raise HTTPException(404, 'Industry workflow not found')
    return flow


def pending_review(db, resource, trigger, thread, target, requester, initial=False):
    flow = current_flow(trigger, thread)
    if not flow.approval_user_ids:
        raise HTTPException(422, 'This stage has no authorized reviewers')
    operation = {'conversation_id': thread.id, 'workflow_id': flow.id, 'workflow_revision': configuration(trigger).revision,
        'case_id': thread.context.get('workflow_case_id'), 'from_stage': thread.context.get('service_stage'),
        'stage_revision': thread.context.get('stage_revision', 0), 'target': target, 'initial': initial,
        'intake_hash': digest(thread.context.get('intake_state', {}))}
    row = Event(**scope_values(resource), resource_id=resource.id, kind='telegram_stage_review', details={
        'operation': operation, 'operation_hash': digest(operation), 'requester_id': requester, 'status': 'pending', 'expires_at': (now() + timedelta(minutes=15)).isoformat()})
    db.add(row); db.flush()
    for ident in flow.approval_user_ids:
        db.add(Notification(company_id=resource.organization_id, user_id=ident, title='Telegram service stage needs approval',
            message=f'Conversation #{thread.id}: review entry into {next(stage.label for stage in flow.stages if stage.key == target)}.', module='power_apps', event_type='telegram.stage_review',
            action_url=f'/power-apps/automations/telegram?environment={resource.environment}', channels=['in_app']))
    return row


def submit_initial(db, resource, trigger, thread, state, update_id):
    thread.context = {**(thread.context or {}), 'workflow_case_id': str(update_id), 'stage_revision': 0, 'intake_state': state,
        'stage_approved': not state.get('requires_stage_approval', False)}
    if state.get('requires_stage_approval'):
        review = pending_review(db, resource, trigger, thread, thread.context['service_stage'], resource.owner_user_id, initial=True)
        thread.context = {**thread.context, 'pending_stage_review_id': review.id}
        return review
    return None


def apply_stage(db, resource, trigger, thread, target, actor_id, initial=False):
    flow = current_flow(trigger, thread)
    stage = next((item for item in flow.stages if item.key == target), None)
    if not stage:
        raise HTTPException(422, 'Choose a configured service stage')
    context = dict(thread.context or {})
    if initial:
        from app.apps.power_apps import telegram_operations as operations
        from app.apps.power_apps.runtime_triggers import trigger_identity
        owner = trigger_identity(db, trigger)
        linked = operations.identity(db, resource, thread.telegram_id, thread.interface)
        state = context.get('intake_state', {})
        if not context.get('stage_approved') and trigger.config.get('interfaces', {}).get('create_crm_records') and state.get('workflow_result') not in {'handoff', 'appointment_request'}:
            with db.begin_nested():
                state = operations.create_records(db, resource, trigger, owner, linked, thread, state, int(context['workflow_case_id']))
            requests = [{**item, 'task_id': state.get('task_id'), 'lead_id': state.get('lead_id')} if str(item.get('update_id')) == context['workflow_case_id'] else item for item in context.get('requests', [])]
            context = {**context, 'intake_state': state, 'requests': requests}
    terminal = not stage.next_stages
    if terminal:
        context['requests'] = [{**item, 'service_status': 'completed'} if str(item.get('update_id')) == context.get('workflow_case_id') else item for item in context.get('requests', [])]
    thread.context = {**context, 'service_stage': target, 'stage_revision': context.get('stage_revision', 0) + 1, 'stage_approved': True, 'pending_stage_review_id': None}
    db.add(Event(**scope_values(resource), resource_id=resource.id, kind='telegram_service_stage', details={'conversation_id': thread.id, 'case_id': context.get('workflow_case_id'), 'stage': target, 'actor_id': actor_id, 'revision': thread.context['stage_revision']}))
    return thread.context


def transition(db, resource, trigger, thread, target, expected_revision, actor_id):
    flow = current_flow(trigger, thread)
    context = thread.context or {}
    if context.get('stage_revision', 0) != expected_revision:
        raise HTTPException(409, 'The service stage changed. Reload before continuing.')
    current = next((stage for stage in flow.stages if stage.key == context.get('service_stage')), None)
    if not current or target not in current.next_stages:
        raise HTTPException(409, 'This service stage transition is not allowed')
    if not context.get('stage_approved', True):
        raise HTTPException(409, 'Approve the current intake stage before moving to another stage')
    stage = next(item for item in flow.stages if item.key == target)
    if stage.requires_approval:
        review = pending_review(db, resource, trigger, thread, target, actor_id)
        thread.context = {**context, 'pending_stage_review_id': review.id}
        return {'status': 'awaiting_approval', 'review_id': review.id}
    return {'status': 'completed', 'context': apply_stage(db, resource, trigger, thread, target, actor_id)}


def review(db, resource, trigger, row, actor_id, approved):
    operation = row.details['operation']
    thread = db.query(TelegramConversation).filter_by(id=operation['conversation_id'], resource_id=resource.id, organization_id=resource.organization_id).with_for_update().first()
    if not thread:
        raise HTTPException(404, 'Service conversation not found')
    flow = current_flow(trigger, thread)
    if actor_id not in flow.approval_user_ids:
        raise HTTPException(403, 'You are not an authorized reviewer for this service workflow')
    if row.details['status'] != 'pending':
        return {'status': row.details['status']}
    context = thread.context or {}
    if utc(datetime.fromisoformat(row.details['expires_at'])) <= now() or row.details['operation_hash'] != digest(operation) or operation['stage_revision'] != context.get('stage_revision', 0) or operation['workflow_revision'] != configuration(trigger).revision or operation['case_id'] != context.get('workflow_case_id') or operation['intake_hash'] != digest(context.get('intake_state', {})):
        raise HTTPException(409, 'The review expired or the service request changed. Request a fresh review.')
    if approved:
        apply_stage(db, resource, trigger, thread, operation['target'], actor_id, operation['initial'])
    else:
        thread.context = {**context, 'pending_stage_review_id': None, 'stage_rejected': True}
    row.details = {**row.details, 'status': 'approved' if approved else 'rejected', 'reviewer_id': actor_id, 'reviewed_at': now().isoformat()}
    return {'status': row.details['status']}
