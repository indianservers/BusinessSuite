"""Transactional identity, CRM intake, and human handoff for a shared Telegram bot."""
import hashlib
import json
import secrets
from datetime import timedelta

from fastapi import HTTPException
from app.models.user import User
from app.models.notification import Notification
from app.apps.power_apps.models import TelegramIdentity as Identity, TelegramLinkChallenge as Challenge, TelegramConversation as Conversation, TelegramMessage as Message
from app.apps.power_apps.runtime import now, utc, enqueue, scope_values
from app.access.service import background_scope
from app.core.tenant_boundary import company_ids


def member(db, user_id, company):
    user = db.query(User).filter_by(id=user_id).populate_existing().first()
    if not user or not user.is_active or company not in company_ids(db, user):
        raise HTTPException(403, 'Linked account is inactive or company membership was revoked')
    user.organization_id = company
    db.expire(user, ['role'])
    user._suite_permission_objects = None
    return user


def staff_member(db, linked, company):
    user = member(db, linked.user_id, company)
    if linked.employee_id:
        from app.models.employee import Employee
        from app.models.company import Branch
        employee = db.query(Employee).join(Branch, Employee.branch_id == Branch.id).filter(
            Employee.id == linked.employee_id, Employee.user_id == user.id, Employee.deleted_at.is_(None),
            Branch.company_id == company, Branch.is_active.is_(True)).populate_existing().first()
        if not employee or employee.status not in {'Active', 'Probation', 'On Leave'} or employee.date_of_exit and employee.date_of_exit <= now().date():
            raise HTTPException(403, 'Linked employee is no longer active in this company')
    return user


def identity(db, resource, sender_id, interface):
    return db.query(Identity).filter_by(resource_id=resource.id, organization_id=resource.organization_id,
        environment=resource.environment, telegram_id=sender_id, interface=interface, revoked_at=None).first()


def issue_code(db, resource, actor, interface, contact_id=None, lead_id=None, customer_id=None):
    if interface == 'company':
        member(db, actor.id, resource.organization_id)
        if contact_id or lead_id or customer_id:
            raise HTTPException(422, 'Company linking always links your own signed-in account')
    elif sum(bool(value) for value in (contact_id, lead_id, customer_id)) != 1:
        raise HTTPException(422, 'Choose exactly one CRM contact, lead or customer account for public linking')
    else:
        from app.apps.crm.api import router as crm
        entity, record_id = ('contacts', contact_id) if contact_id else ('leads', lead_id) if lead_id else ('companies', customer_id)
        with background_scope(db, actor, 'crm', 'view'):
            crm._assert_entity_permission(entity, actor, 'manage')
            crm._assert_record_visible(db, crm._get_resource(entity), record_id, resource.organization_id, actor)
    # A newly issued code supersedes earlier unused codes for the same target.
    for old in db.query(Challenge).filter_by(resource_id=resource.id, interface=interface,
            user_id=actor.id if interface == 'company' else None, contact_id=contact_id, lead_id=lead_id, customer_id=customer_id, consumed_at=None).all():
        old.consumed_at = now()
    token = secrets.token_urlsafe(24)
    db.add(Challenge(organization_id=resource.organization_id, environment=resource.environment,
        resource_id=resource.id, token_hash=hashlib.sha256(token.encode()).hexdigest(), interface=interface,
        user_id=actor.id if interface == 'company' else None, contact_id=contact_id, lead_id=lead_id, customer_id=customer_id,
        created_by_user_id=actor.id, expires_at=now() + timedelta(minutes=10)))
    db.flush()
    return token


def consume_code(db, resource, sender_id, token, display_name):
    challenge = db.query(Challenge).filter_by(resource_id=resource.id, organization_id=resource.organization_id,
        environment=resource.environment, token_hash=hashlib.sha256(token.encode()).hexdigest(), consumed_at=None).with_for_update().first()
    if not challenge or utc(challenge.expires_at) <= now():
        return None, 'This linking code is invalid or expired. Generate a new code in BusinessSuite.'
    if challenge.interface == 'company':
        try:
            member(db, challenge.user_id, resource.organization_id)
        except HTTPException:
            return None, 'This account can no longer be linked. Contact your company administrator.'
    else:
        try:
            from app.apps.crm.api import router as crm
            issuer = member(db, challenge.created_by_user_id, resource.organization_id)
            entity, record_id = ('contacts', challenge.contact_id) if challenge.contact_id else ('leads', challenge.lead_id) if challenge.lead_id else ('companies', challenge.customer_id)
            with background_scope(db, issuer, 'crm', 'view'):
                crm._assert_entity_permission(entity, issuer, 'manage')
                crm._assert_record_visible(db, crm._get_resource(entity), record_id, resource.organization_id, issuer)
        except HTTPException:
            return None, 'This customer link is no longer available. Ask your company contact for a new code.'
    existing = db.query(Identity).filter_by(resource_id=resource.id, telegram_id=sender_id, interface=challenge.interface).first()
    # Never silently rebind an active identity or link one account to multiple Telegram accounts.
    targets = {'user_id': challenge.user_id, 'contact_id': challenge.contact_id, 'lead_id': challenge.lead_id, 'customer_id': challenge.customer_id}
    if existing and existing.revoked_at is None and existing.verified_at and any(getattr(existing, key) != value for key, value in targets.items()):
        return None, 'This Telegram account is already linked. Revoke its existing link in BusinessSuite first.'
    query = db.query(Identity).filter_by(resource_id=resource.id, interface=challenge.interface, revoked_at=None, **targets)
    if query.filter(Identity.telegram_id != sender_id).first():
        return None, 'This BusinessSuite identity is already linked to another Telegram account. Revoke the old link first.'
    linked = existing or Identity(organization_id=resource.organization_id, environment=resource.environment,
        resource_id=resource.id, telegram_id=sender_id, interface=challenge.interface)
    for key, value in targets.items():
        setattr(linked, key, value)
    linked.display_name, linked.verified_at, linked.revoked_at = display_name[:180], now(), None
    db.add(linked)
    challenge.consumed_at = now()
    db.flush()
    return linked, f'Your {challenge.interface} identity is linked. Send /{challenge.interface} to continue.'


def get_conversation(db, resource, chat_id, sender_id, interface, linked):
    row = db.query(Conversation).filter_by(resource_id=resource.id, organization_id=resource.organization_id,
        environment=resource.environment, chat_id=chat_id, interface=interface).with_for_update().first()
    if not row:
        row = Conversation(organization_id=resource.organization_id, environment=resource.environment,
            resource_id=resource.id, chat_id=chat_id, telegram_id=sender_id, interface=interface, state={}, status='bot')
        db.add(row)
        db.flush()
    row.identity_id = linked.id if linked else None
    row.last_at = now()
    return row


def request_handoff(db, resource, conversation, reason='Requested a human'):
    if conversation.status in {'waiting', 'assigned'}:
        return
    from app.apps.power_apps.runtime_models import AutomationTrigger
    from app.apps.power_apps.telegram_routing import assign_handoff
    trigger = db.query(AutomationTrigger).filter_by(resource_id=resource.id, kind='telegram').one()
    target = assign_handoff(db, resource, trigger, conversation)
    db.add(Notification(company_id=resource.organization_id, user_id=target,
        title='Telegram conversation needs a person', message=f'{conversation.interface.title()} conversation #{conversation.id}: {reason[:250]}',
        module='power_apps', event_type='telegram.handoff', related_entity_type='telegram_conversation', related_entity_id=conversation.id,
        action_url=f'/power-apps/automations/telegram?environment={resource.environment}', channels=['in_app']))


def create_records(db, resource, trigger, owner, linked, conversation, state, update_id):
    """Native CRM validation and audit; all writes share the ingress transaction."""
    from app.apps.crm.api import router as crm
    actor = staff_member(db, linked, resource.organization_id) if conversation.interface == 'company' else owner
    branch_id = trigger.config.get('branch_id')
    if not branch_id:
        raise HTTPException(422, 'Choose a branch for this bot before enabling CRM creation')
    lead_id = linked.lead_id if linked and conversation.interface == 'public' else None
    with background_scope(db, actor, 'crm', 'create', branch_id=branch_id):
        topic, requirement = state.get('topic', 'Request'), state.get('requirement', '')
        if topic == 'Sales':
            # A public identity's existing lead is reused; separate employee-created leads remain separate.
            if lead_id:
                crm._assert_entity_permission('leads', actor, 'view')
                crm._assert_record_visible(db, crm._get_resource('leads'), lead_id, resource.organization_id, actor)
            else:
                name = state.get('name') or linked.display_name or 'Telegram enquiry'
                lead = crm.create_record_operation('leads', crm.CRMRecordPayload(**{
                    'full_name': name, 'first_name': name.split()[0][:100],
                    'source': 'Telegram', 'notes': requirement, 'branch_id': branch_id,
                }), db, actor, commit=False)
                lead_id = lead['id']
        result = crm.create_record_operation('tasks', crm.CRMRecordPayload(
            title=f'Telegram {topic}: {requirement[:140]}', description=requirement,
            lead_id=lead_id,
            contact_id=linked.contact_id if linked and conversation.interface == 'public' else None,
            company_id=linked.customer_id if linked and conversation.interface == 'public' else None,
            branch_id=branch_id, priority='High' if state.get('qualification', {}).get('priority') in {'High', 'Urgent'} else 'Medium', status='To Do',
            task_details={'telegram': {'workflow_id': state.get('workflow_id'), 'qualification': state.get('qualification'), 'answers': state.get('answers')}},
        ), db, actor, commit=False)
    if linked and conversation.interface == 'public' and topic == 'Sales':
        linked.lead_id = lead_id
    conversation.lead_id, conversation.task_id = lead_id, result['id']
    return {**state, 'lead_id': lead_id, 'task_id': result['id']}


def private_binding(linked):
    """Bind queued private text to the exact verification and account targets."""
    values = {key: getattr(linked, key) for key in ('id', 'telegram_id', 'interface', 'contact_id', 'lead_id', 'customer_id')}
    values['verified_at'] = utc(linked.verified_at).isoformat() if linked.verified_at else None
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def queue_reply(db, resource, trigger, owner, conversation, text, key, created_by=None, handoff_notice=False, reply_markup=None, private_identity=None, private_command=None):
    linked = db.get(Identity, conversation.identity_id) if conversation.identity_id else None
    payload = {'chat_id': conversation.chat_id, 'reply': text, 'text': '[Staff reply]' if created_by else '[Bot reply]',
        'telegram_conversation_id': conversation.id, 'telegram_staff_id': created_by, 'telegram_handoff_notice': handoff_notice,
        'telegram_linked_user_id': linked.user_id if linked else None}
    if private_identity is not None:
        from app.apps.power_apps.telegram_customer import COMMANDS
        if conversation.interface != 'public' or not private_identity.verified_at or private_identity.revoked_at or private_identity.id != conversation.identity_id:
            raise HTTPException(403, 'Verified customer delivery context is unavailable')
        if private_command not in COMMANDS:
            raise HTTPException(403, 'Private customer delivery command is unavailable')
        payload['telegram_private_identity_id'] = private_identity.id
        payload['telegram_private_binding'] = private_binding(private_identity)
        payload['telegram_private_command'] = private_command
    if reply_markup:
        payload['reply_markup_json'] = json.dumps(reply_markup, ensure_ascii=False)
    run = enqueue(db, resource, owner, payload, key, kind='telegram', trigger=trigger)
    db.add(Message(organization_id=resource.organization_id, environment=resource.environment, resource_id=resource.id,
        conversation_id=conversation.id, direction='outgoing', text=text, run_id=run.id, created_by_user_id=created_by,
        client_key=key[-80:] if created_by else None))
    db.flush()
    return run.id


def authorize_delivery(db, run, request, resource_id=None):
    """Recheck identity and handoff after queuing, immediately before a provider send."""
    from app.apps.power_apps.runtime_models import AutomationTrigger
    thread_id = run.input_payload.get('telegram_conversation_id')
    if not thread_id:
        return
    resource_id = resource_id or run.resource_id
    thread = db.query(Conversation).filter_by(id=thread_id, resource_id=resource_id,
        organization_id=run.organization_id, environment=run.environment).populate_existing().first()
    trigger = db.query(AutomationTrigger).filter_by(resource_id=resource_id, kind='telegram', enabled=True).populate_existing().first()
    if not thread or not trigger or str(request.get('chat_id')) != thread.chat_id:
        raise HTTPException(403, 'Telegram delivery context is unavailable')
    if not trigger.config.get('interfaces', {}).get(f'{thread.interface}_enabled', True):
        raise HTTPException(403, 'Telegram interface is disabled')
    if run.input_payload.get('telegram_private_binding'):
        linked = db.query(Identity).filter_by(id=thread.identity_id, resource_id=resource_id,
            organization_id=run.organization_id, environment=run.environment, telegram_id=thread.telegram_id,
            interface='public', revoked_at=None).populate_existing().first()
        if (not linked or not linked.verified_at or linked.id != run.input_payload.get('telegram_private_identity_id')
                or private_binding(linked) != run.input_payload['telegram_private_binding']):
            raise HTTPException(403, 'Customer identity changed before private information delivery')
        from app.apps.power_apps.models import PowerResource
        from app.apps.power_apps.telegram_customer import COMMANDS, read
        resource = db.get(PowerResource, resource_id)
        command = run.input_payload.get('telegram_private_command')
        if not resource or command not in COMMANDS:
            raise HTTPException(403, 'Private customer delivery source is unavailable')
        # Native read paths recheck the owner's current module rights and source
        # visibility immediately before transport; the queued text grants no rights.
        read(db, resource, trigger, member(db, resource.owner_user_id, run.organization_id), thread, linked, command)
    if thread.interface == 'company':
        linked = db.query(Identity).filter_by(id=thread.identity_id, resource_id=resource_id, revoked_at=None).populate_existing().first()
        if not linked or linked.user_id != run.input_payload.get('telegram_linked_user_id'):
            raise HTTPException(403, 'Company identity was revoked')
        staff_member(db, linked, run.organization_id)
    staff_id = run.input_payload.get('telegram_staff_id')
    if staff_id:
        staff = member(db, staff_id, run.organization_id)
        if thread.status != 'assigned' or thread.assignee_user_id != staff_id:
            raise HTTPException(403, 'Conversation assignment changed')
        from app.core.deps import RequirePermission
        with background_scope(db, staff, 'power_apps', 'create', branch_id=trigger.config.get('branch_id')):
            RequirePermission('power_apps_execute')(staff)
    elif thread.status in {'waiting', 'assigned'} and not run.input_payload.get('telegram_handoff_notice'):
        raise HTTPException(403, 'Automatic reply paused for human handoff')
