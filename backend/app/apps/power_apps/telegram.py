"""Local Telegram ingress. Definitions, runs, credentials and events stay in Power Apps."""
import json
import re
import secrets
from datetime import timedelta
from urllib.parse import quote
from fastapi import HTTPException
from app.apps.power_apps.models import PowerResource, PowerVersion
from app.apps.power_apps.runtime_models import AutomationTrigger as Trigger, AutomationDeployment as Deployment, AutomationEvent as Event
from app.apps.power_apps.runtime import now, utc, enqueue, scope_values, lifecycle
from app.apps.power_apps.runtime_triggers import trigger_identity
from app.apps.power_apps.service import organization, validate_environment, record_change
from app.apps.power_apps.integrations import vault, adapters
from app.apps.power_apps.integrations.contracts import IntegrationFailure

WELCOME = "Welcome! Choose Sales, Support, or Order status. Send /cancel to reset."


def conversation(text, previous=None):
    """Pure, bounded conversation transition; shared by real ingress and offline testing."""
    state = dict(previous or {})
    text = text.strip()[:4096]
    command = text.casefold().split('@')[0]
    if command in {'/start', '/help', '/cancel'}:
        return {'stage': 'menu'}, WELCOME
    topics = {'sales': 'Sales', 'support': 'Support', 'order status': 'Order status'}
    if command in topics:
        state = {'stage': 'name', 'topic': topics[command]}
        return state, f"{state['topic']} enquiry: what is your name?"
    if state.get('stage') == 'name':
        if not text or len(text) > 180:
            return state, 'Please enter your name (up to 180 characters).'
        state.update(stage='requirement', name=text)
        question = 'Please enter your order number and question.' if state.get('topic') == 'Order status' else 'Please describe your requirement.'
        return state, question
    if state.get('stage') == 'requirement' and text:
        state.update(stage='complete', requirement=text)
        return state, "Thanks! We’ve received your enquiry. Our team will follow up. Send /start for another enquiry."
    return {'stage': 'menu'}, WELCOME


def interface_conversation(text, previous, config, sender_id, company_default=False):
    """Recheck staff access on every message; public commands cannot grant staff access."""
    state = dict(previous or {})
    command = text.strip().casefold().split('@')[0]
    approved = config.get('company_enabled', True) and str(sender_id) in config.get('company_user_ids', [])
    mode = state.get('interface', 'company' if company_default else 'public')
    if command.startswith('/start '):
        command = '/' + command.split(' ', 1)[1]
    if command in {'/company', '/public'}:
        mode, state = command[1:], {}
        command = '/start'
        text = '/start'
    if mode == 'company':
        if not approved:
            return {'stage': 'menu', 'interface': 'public'}, 'Company access requires an approved Telegram user ID. Send /public for customer enquiries.'
        welcome = config.get('company_welcome') or 'Company workspace: choose Create lead, Create task, Internal request or Help. Send /human for a person or /public for customer enquiries.'
        if command in {'/start', '/help', '/cancel', 'help'}:
            return {'stage': 'menu', 'interface': 'company'}, welcome
        if command in {'sales', 'create lead'} or state.get('stage') in {'name', 'requirement'}:
            result, reply = conversation('Sales' if command == 'create lead' else text, state)
            return {**result, 'interface': 'company'}, reply
        if command in {'internal request', 'create task'}:
            return {'stage': 'request', 'interface': 'company'}, 'Describe your internal request. It will be recorded for your company administrator.'
        if state.get('stage') == 'request' and text.strip():
            return {'stage': 'complete', 'interface': 'company', 'topic': 'Internal request', 'name': str(sender_id), 'requirement': text.strip()[:4096]}, 'Internal request recorded. Send /company to return to your workspace.'
        return {'stage': 'menu', 'interface': 'company'}, welcome
    if not config.get('public_enabled', True):
        return {'stage': 'menu', 'interface': 'public'}, 'Public enquiries are currently unavailable.'
    state, reply = conversation(text, state)
    if state.get('stage') == 'menu':
        reply = config.get('public_welcome') or WELCOME
    if command == '/help':
        reply += '\nAsk for products, services or availability. Send /book to book, /followup on for enquiry reminders, /stop to stop reminders, or /human for support.'
    return {**state, 'interface': 'public'}, reply


def bot_request(db, user, conn, method, data=None):
    """Fixed origin, encrypted credential, bounded transport; never expose token URLs."""
    conn = vault.connection(db, user, conn.environment, conn.id)
    if conn.connector_id != 'telegram' or not conn.enabled:
        raise HTTPException(422, 'An enabled Telegram connection is required')
    _, values = vault.credential_values(db, user, conn)
    token = values.get('access_token', '')
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token):
        raise HTTPException(422, 'Invalid Telegram bot token format')
    try:
        response = adapters.HTTP_FACTORY(vault.policy_for(db, conn)).request(
            'POST', f'https://api.telegram.org/bot{quote(token, safe="")}/{method}',
            headers={'Content-Type': 'application/json'}, body=json.dumps(data or {}).encode(), timeout=8,
        )
        value = json.loads(response.body)
        if response.status != 200 or value.get('ok') is not True:
            if response.status == 409:
                raise HTTPException(409, 'Bot has a webhook or another polling listener. Stop that listener before enabling this automation.')
            raise HTTPException(422, 'Telegram rejected the request. Check the saved bot token and bot permissions.')
        return value['result']
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, 'Telegram could not be reached. Check the connection and retry.') from None


def definition(connection_id):
    def node(id, type, label, x, config=None, credential=None):
        value = dict(id=id, type=type, label=label, position={'x': x, 'y': 120}, config=config or {})
        if credential:
            value['credential_reference'] = str(credential)
        return value
    return {'schema_version': 2, 'nodes': [
        node('received', 'telegram_trigger', 'Message received', 80),
        node('enquiry', 'telegram_enquiry', 'Check message & collect enquiry', 400),
        node('reply', 'connector_telegram', 'Reply to the sender', 740, {
            'action': 'send_message', 'confirm_write': True,
            'input': {'chat_id': '{{steps.enquiry.output.chat_id}}', 'text': '{{steps.enquiry.output.text}}'},
        }, connection_id),
    ], 'edges': [dict(id='received_enquiry', source='received', target='enquiry'), dict(id='enquiry_reply', source='enquiry', target='reply')],
        'tags': ['Telegram', 'Customer enquiries']}


def create_workflow(db, user, environment, conn, bot, name):
    validate_environment(db, user, environment)
    # One consumer per bot, even if another connection was created with the same token.
    for existing in db.query(Trigger).filter(Trigger.kind.in_(['telegram', 'connector'])).all():
        if existing.config.get('bot_id') == bot['id']:
            raise HTTPException(409, 'This Telegram bot already has an automation listener. Use its existing workflow.')
    row = PowerResource(organization_id=organization(user), environment=environment, application_id='automations',
                        owner_user_id=user.id, name=name, description='Local Telegram customer enquiry auto-reply',
                        definition=definition(conn.id), version=1, status='draft')
    db.add(row)
    db.flush()
    record_change(db, user, row, 'draft_created')
    db.flush()
    lifecycle(db, row, user, 'validate', 1)
    lifecycle(db, row, user, 'publish', 1, {'identity': 'owner', 'delegated_owner': True, 'concurrency': 1})
    lifecycle(db, row, user, 'activate', 1)
    trigger = Trigger(**scope_values(row), resource_id=row.id, kind='telegram', enabled=True,
                      endpoint=secrets.token_urlsafe(24), config={'connection_id': conn.id, 'bot_id': bot['id'],
                      'username': bot.get('username', ''), 'offset': 0, 'started_at': int(now().timestamp())})
    db.add(trigger)
    db.flush()
    from app.branches.models import BranchOwnership
    ownership = db.query(BranchOwnership).filter_by(resource_table='power_apps_resources', resource_key=str(row.id), company_id=row.organization_id).first()
    if ownership:
        trigger.config = {**trigger.config, 'branch_id': ownership.branch_id}
    return row


def accept_update(db, row, trigger, actor, update):
    from app.apps.power_apps import telegram_dialogue as dialogue
    message = dict(update.get('message') or {})
    callback = update.get('callback_query') or {}
    if callback:
        command_text = dialogue.callback_text(callback.get('data', ''))
        if command_text is None:
            return None
        message = {**(callback.get('message') or {}), 'from': callback.get('from') or {}, 'text': command_text, 'date': int(now().timestamp())}
    attachment = None
    if isinstance(message.get('location'), dict):
        attachment = {'type': 'location', **{key: message['location'].get(key) for key in ['latitude', 'longitude']}}
        message.setdefault('text', '[Shared location]')
    elif isinstance(message.get('document'), dict):
        attachment = {'type': 'document', **{key: message['document'].get(key) for key in ['file_id', 'file_unique_id', 'file_name', 'mime_type', 'file_size']}}
        message.setdefault('text', '[Document received]')
    chat = message.get('chat') or {}
    sender = message.get('from') or {}
    if chat.get('type') != 'private' or sender.get('is_bot') or not isinstance(message.get('text'), str):
        return None
    if message.get('date', 0) < trigger.config.get('started_at', 0):
        return None
    chat_id = str(chat.get('id', ''))
    if not re.fullmatch(r'\d{1,20}', chat_id):
        return None
    update_id = update['update_id']
    # The trigger row lock serializes this check, conversation changes and offset advancement.
    prior = db.query(Event).filter_by(resource_id=row.id, organization_id=row.organization_id, environment=row.environment, kind='telegram_message').filter(Event.details['update_id'].as_integer() == update_id).first()
    if prior:
        return prior.run_id
    from app.apps.power_apps import telegram_operations as operations
    from app.apps.power_apps import telegram_ai
    from app.apps.power_apps.models import TelegramIdentity, TelegramConversation, TelegramMessage
    sender_id = str(sender.get('id') or chat_id)
    if sender_id != chat_id:
        return None
    if db.query(TelegramMessage).filter_by(resource_id=row.id, update_id=update_id).first():
        return None
    text = message['text'].strip()[:4096]
    command = text.casefold().split('@')[0]
    from app.apps.power_apps import telegram_audience as purpose
    bot_audience = purpose.audience(trigger)
    latest = db.query(TelegramConversation).filter_by(resource_id=row.id, chat_id=chat_id).order_by(TelegramConversation.last_at.desc(), TelegramConversation.id.desc()).first()
    mode = bot_audience if bot_audience != 'shared' else latest.interface if latest else 'public'
    if command in {'/company', '/start company'}:
        mode = 'company'
    elif command in {'/public', '/start public'}:
        mode = 'public'
    if bot_audience != 'shared':
        mode = bot_audience
    config = dict(trigger.config.get('interfaces', {}))
    staff = operations.identity(db, row, sender_id, 'company') if bot_audience != 'public' else None
    if staff:
        try:
            operations.staff_member(db, staff, row.organization_id)
        except HTTPException:
            staff = None
    if staff and bot_audience != 'public' and (latest is None or command == '/start') and command not in {'/public', '/start public'}:
        mode = 'company'
    # Numeric allowlists alone no longer grant company access.
    config['company_user_ids'] = [sender_id] if staff else []
    linking = text.split(maxsplit=1) if text.casefold().startswith('/link ') else None
    reply = None
    if linking:
        linked, reply = operations.consume_code(db, row, sender_id, linking[1], sender.get('first_name', ''))
        if linked:
            mode = linked.interface
            if mode == 'company':
                staff = linked
        text = '[Identity linking code redacted]'
    if bot_audience == 'public' and command in {'/company', '/start company'}:
        reply = purpose.PUBLIC_NOTICE
    elif bot_audience == 'company' and command in {'/public', '/start public', '/account', '/orders', '/appointments', '/myrequests', 'support', 'order status'}:
        reply = purpose.COMPANY_PUBLIC_NOTICE
    linked = operations.identity(db, row, sender_id, mode)
    verification_notice = False
    if mode == 'company' and (not staff or not config.get('company_enabled', True)):
        if bot_audience == 'company':
            linked = None
            reply = purpose.COMPANY_NOTICE
            verification_notice = True
        else:
            mode, linked = 'public', operations.identity(db, row, sender_id, 'public')
            reply = 'Link your signed-in BusinessSuite account using a one-time code before opening /company.'
    if command == '/id':
        reply = f'Your Telegram user ID is {sender_id}. Give this numeric ID to your company administrator to link your employee account.'
    if mode == 'public' and not linked:
        linked = db.query(TelegramIdentity).filter_by(resource_id=row.id, telegram_id=sender_id, interface='public').first()
        if linked:
            linked.user_id, linked.employee_id, linked.contact_id, linked.lead_id, linked.customer_id = None, None, None, None, None
            linked.verified_at, linked.revoked_at = None, None
        else:
            linked = TelegramIdentity(organization_id=row.organization_id, environment=row.environment, resource_id=row.id,
                telegram_id=sender_id, interface='public', display_name=sender.get('first_name', '')[:180])
        db.add(linked)
        db.flush()
    thread = operations.get_conversation(db, row, chat_id, sender_id, mode, linked)
    from app.apps.power_apps.telegram_followups import consent as followup_consent
    consent_reply = followup_consent(thread, text)
    if reply is None and consent_reply is not None:
        reply = consent_reply
    old_state = dict(thread.state or {})
    if verification_notice:
        old_state = {}
        thread.state, thread.context = {}, {}
    if linking:
        old_state = {}
        thread.lead_id, thread.task_id = None, None
    text_for_flow = dialogue.canonical(text, old_state.get('stage') in {'name', 'requirement', 'request', 'workflow'})
    command = text_for_flow.casefold().split('@')[0]
    guided = (False, old_state, None, None)
    if reply is None and thread.status not in {'waiting', 'assigned'} and config.get(f'{mode}_enabled', True):
        guided = dialogue.handle(thread, trigger, text_for_flow, old_state, attachment)
    state = old_state
    keyboard = None
    if reply is None and not config.get(f'{mode}_enabled', True):
        reply = 'This interface is currently unavailable.'
    elif reply is None and text.startswith(('/approve ', '/reject ', '/review ')):
        from app.apps.power_apps.telegram_approvals import respond
        try:
            reply, keyboard = respond(db, row, thread, linked, text)
        except HTTPException as error:
            reply = str(error.detail)
        text = '[Action review control redacted]'
    elif reply is None and command in {'/account', '/orders', '/appointments', '/myrequests'}:
        from app.apps.power_apps.telegram_customer import read as customer_read
        try:
            reply = customer_read(db, row, trigger, actor, thread, linked, command)
        except HTTPException:
            reply = 'Your private account information is currently unavailable. Ask the company to review your verified link and access.'
    elif reply is None and command in {'/human', 'human', 'talk to a person'}:
        operations.request_handoff(db, row, thread)
        reply = dialogue.localize('Your conversation is in the human support queue. You can continue sending messages here.', thread)
    elif reply is None and thread.status in {'waiting', 'assigned'}:
        # Record the message and notify the responsible person; leave the bot silent.
        from app.models.notification import Notification
        from app.apps.power_apps.telegram_routing import start_deadline
        start_deadline(thread, trigger)
        db.add(Notification(company_id=row.organization_id, user_id=thread.assignee_user_id or row.owner_user_id,
            title='New Telegram handoff message', message=f'Conversation #{thread.id} has a new message.', module='power_apps',
            action_url=f'/power-apps/automations/telegram?environment={row.environment}', channels=['in_app']))
    elif reply is None and guided[0]:
        _, state, reply, keyboard = guided
    elif reply is None and (text_for_flow.startswith(('/book', '/reschedule ', '/cancelbooking ', '/slot ')) or old_state.get('stage') in {'booking_customer', 'booking_service', 'booking_date', 'booking_slot', 'booking_cancel_reason'}):
        from app.apps.power_apps.telegram_booking import handle as booking_handle
        try:
            _, state, reply, keyboard = booking_handle(db, row, trigger, actor, thread, linked, text_for_flow, old_state)
        except HTTPException as error:
            reply = str(error.detail)
    elif reply is None and telegram_ai.configuration(trigger).enabled and telegram_ai.accepts(text_for_flow, old_state):
        telegram_ai.queue(db, row, thread, text, update_id)
    elif reply is None:
        if command in {'/company', '/public', '/start company', '/start public'}:
            old_state = {}
        state, reply = interface_conversation(text_for_flow, {**old_state, 'interface': mode}, config, sender_id)
        reply = dialogue.localize(reply, thread)
    completed = state.get('stage') == 'complete' and old_state.get('stage') != 'complete'
    if completed and state.get('workflow_id'):
        from app.apps.power_apps.telegram_workflows import submit_initial
        review = submit_initial(db, row, trigger, thread, state, update_id)
        if review:
            reply = 'Your request was received and is waiting for approval by the company’s authorized reviewer.'
    if completed and state.get('workflow_result') == 'handoff':
        operations.request_handoff(db, row, thread, 'Industry workflow requests staff review')
    if completed and (thread.interface == 'public' or config.get('create_crm_records', False)) and state.get('workflow_result') not in {'handoff', 'appointment_request'} and not state.get('requires_stage_approval'):
        try:
            with db.begin_nested():
                state = operations.create_records(db, row, trigger, actor, linked, thread, state, update_id)
            reply = f"Recorded CRM task #{state['task_id']}" + (f" for lead #{state['lead_id']}" if state.get('lead_id') else '') + '. Send /human to speak with the team.'
        except HTTPException:
            operations.request_handoff(db, row, thread, 'CRM intake needs staff review')
            state = {**state, 'crm_error': True}
            reply = 'Your request is saved for staff review. A person will follow up; no CRM creation is being claimed.'
    if state.get('stage') == 'complete' and old_state.get('stage') != 'complete':
        memory = {**(thread.context or {}).get('memory', {}), 'name': state.get('name')}
        requests = list((thread.context or {}).get('requests', []))
        requests.append({'update_id': update_id, 'topic': state.get('topic'), 'requirement': state.get('requirement'), 'task_id': state.get('task_id'), 'lead_id': state.get('lead_id'), 'status': 'received', 'at': now().isoformat()})
        thread.context = {**(thread.context or {}), 'memory': memory, 'requests': requests[-20:]}
    thread.state = state
    if reply and state.get('stage') == 'menu' and keyboard is None:
        keyboard = dialogue.menu(trigger, mode, dialogue.language(thread, text))
    if text.startswith(('/approve ', '/reject ', '/review ')):
        text = '[Action review control redacted]'
    incoming = TelegramMessage(organization_id=row.organization_id, environment=row.environment, resource_id=row.id,
        conversation_id=thread.id, direction='incoming', text=text + ('\n' + json.dumps(attachment, ensure_ascii=False) if attachment else ''), update_id=update_id)
    db.add(incoming)
    private_identity = linked if mode == 'public' and command in {'/account', '/orders', '/appointments', '/myrequests'} and linked and linked.verified_at and not linked.revoked_at else None
    run_id = operations.queue_reply(db, row, trigger, actor, thread, reply, f'telegram:{trigger.config["bot_id"]}:{update_id}', handoff_notice=thread.status in {'waiting', 'assigned'}, reply_markup=keyboard, private_identity=private_identity, private_command=command if private_identity else None, verification_notice=verification_notice) if reply else None
    data = {'update_id': update_id, 'chat_id': chat_id, 'sender': sender.get('first_name', ''), 'text': text, 'reply': reply or '', 'conversation_id': thread.id}
    db.add(Event(**scope_values(row), resource_id=row.id, run_id=run_id, kind='telegram_message',
        details={**data, 'state': state, 'enquiry_completed': state.get('stage') == 'complete'}))
    db.flush()
    return run_id


def poll_tick(db, limit=10):
    ids = [id for id, in db.query(Trigger.id).filter(Trigger.kind == 'telegram', Trigger.enabled.is_(True)).order_by(Trigger.id).limit(limit).all()]
    for id in ids:
        try:
            trigger = db.query(Trigger).filter_by(id=id, enabled=True).with_for_update(skip_locked=True).populate_existing().first()
            if not trigger or trigger.next_at and utc(trigger.next_at) > now():
                db.rollback()
                continue
            state = db.query(Deployment).filter_by(resource_id=trigger.resource_id, status='active').first()
            row = db.get(PowerResource, trigger.resource_id)
            if not state or not row or row.archived_at:
                db.rollback()
                continue
            actor = trigger_identity(db, trigger)
            from app.access.service import background_scope
            with background_scope(db, actor, 'power_apps', 'create', branch_id=trigger.config.get('branch_id')):
                conn = vault.connection(db, actor, trigger.environment, trigger.config['connection_id'])
                if not conn.writes_enabled:
                    raise HTTPException(422, 'Enable sending on this Telegram connection before listening.')
                updates = bot_request(db, actor, conn, 'getUpdates', {'offset': trigger.config['offset'], 'limit': 20, 'timeout': 0, 'allowed_updates': ['message', 'callback_query']})
                offset = trigger.config['offset']
                for update in sorted(updates, key=lambda item: item['update_id']):
                    if update['update_id'] < offset:
                        continue
                    accept_update(db, row, trigger, actor, update)
                    if update.get('callback_query', {}).get('id'):
                        try:
                            bot_request(db, actor, conn, 'answerCallbackQuery', {'callback_query_id': update['callback_query']['id']})
                        except HTTPException:
                            pass
                    offset = update['update_id'] + 1
                trigger.config = {**trigger.config, 'offset': offset, 'error': None}
                from app.apps.power_apps.telegram_routing import tick as handoff_tick
                handoff_tick(db, row, trigger)
                from app.apps.power_apps.telegram_followups import queue_due as followups_due
                followups_due(db, row, trigger, actor)
                trigger.last_at, trigger.next_at = now(), now() + timedelta(seconds=5)
            db.commit()
        except Exception as exc:
            db.rollback()
            trigger = db.query(Trigger).filter_by(id=id).with_for_update().first()
            if trigger:
                # Do not persist exception text: transports can include credential-bearing URLs.
                error = exc.detail if isinstance(exc, HTTPException) else 'Listener failed. Check the bot connection and worker permissions.'
                trigger.config = {**trigger.config, 'error': error}
                trigger.next_at = now() + timedelta(seconds=30)
                db.commit()
