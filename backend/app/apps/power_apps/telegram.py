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
    for existing in db.query(Trigger).filter_by(kind='telegram').all():
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
    message = update.get('message') or {}
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
    previous = db.query(Event).filter_by(resource_id=row.id, organization_id=row.organization_id, environment=row.environment, kind='telegram_message').filter(Event.details['chat_id'].as_string() == chat_id).order_by(Event.id.desc()).first()
    state, reply = conversation(message['text'], previous.details.get('state') if previous else None)
    data = {'update_id': update_id, 'chat_id': chat_id, 'sender': sender.get('first_name', ''), 'text': message['text'][:4096], 'reply': reply}
    run = enqueue(db, row, actor, data, f'telegram:{trigger.config["bot_id"]}:{update_id}', kind='telegram', trigger=trigger)
    db.add(Event(**scope_values(row), resource_id=row.id, run_id=run.id, kind='telegram_message',
                 details={**data, 'state': state, 'enquiry_completed': state.get('stage') == 'complete'}))
    db.flush()
    return run.id


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
                updates = bot_request(db, actor, conn, 'getUpdates', {'offset': trigger.config['offset'], 'limit': 20, 'timeout': 0, 'allowed_updates': ['message']})
                offset = trigger.config['offset']
                for update in sorted(updates, key=lambda item: item['update_id']):
                    if update['update_id'] < offset:
                        continue
                    accept_update(db, row, trigger, actor, update)
                    offset = update['update_id'] + 1
                trigger.config = {**trigger.config, 'offset': offset, 'error': None}
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
