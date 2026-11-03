"""Telegram automation setup is exposed only inside Power Apps Automations."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, SecretStr
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.apps.power_apps.contracts import Contract
from app.apps.power_apps.service import organization, validate_environment, scoped
from app.apps.power_apps.models import PowerResource
from app.apps.power_apps.runtime_models import AutomationTrigger as Trigger, AutomationDeployment as Deployment, AutomationEvent as Event
from app.apps.power_apps.runtime import lifecycle
from app.apps.power_apps.integrations import vault
from app.apps.power_apps.integrations.contracts import ConnectionCreate
from app.apps.power_apps.telegram import bot_request, create_workflow, conversation

router = APIRouter(prefix='/power-apps/automations/telegram', tags=['Telegram automations'], dependencies=[Depends(RequirePermission('power_apps_view'))])


class Setup(Contract):
    name: str = Field(default='Telegram customer enquiries', min_length=1, max_length=180)
    token: SecretStr


class Toggle(Contract):
    enabled: bool


class Simulation(Contract):
    messages: list[str] = Field(min_length=1, max_length=20)


@router.post('/simulate')
def simulate(data: Simulation, user=Depends(RequirePermission('power_apps_view'))):
    state, steps = {}, []
    for text in data.messages:
        if len(text) > 4096:
            raise HTTPException(422, 'Messages must be at most 4096 characters')
        state, reply = conversation(text, state)
        steps.append({'message': text, 'reply': reply, 'stage': state['stage']})
    return {'steps': steps, 'enquiry': state if state.get('stage') == 'complete' else None, 'sent': False}


@router.post('/setup', status_code=201)
def setup(data: Setup, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_create'))):
    for permission in ('power_apps_manage_credentials', 'power_apps_execute', 'power_apps_publish'):
        RequirePermission(permission)(user)
    validate_environment(db, user, environment)
    try:
        conn = vault.create(db, user, environment, ConnectionCreate(connector_id='telegram', name=data.name[:160] + ' bot', auth_type='bearer', secrets={'access_token': data.token}, writes_enabled=True))
        bot = bot_request(db, user, conn, 'getMe')
        webhook = bot_request(db, user, conn, 'getWebhookInfo')
        if webhook.get('url'):
            raise HTTPException(409, 'This bot has an existing webhook. Remove that webhook before creating a local polling automation.')
        row = create_workflow(db, user, environment, conn, bot, data.name)
        db.commit()
        return {'resource_id': row.id, 'username': bot.get('username'), 'enabled': True}
    except Exception:
        db.rollback()
        raise


@router.get('/bots')
def bots(environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_view'))):
    validate_environment(db, user, environment)
    visible = scoped(db, PowerResource, user, environment).filter_by(application_id='automations').filter(PowerResource.archived_at.is_(None)).all()
    items = []
    for row in visible:
        trigger = db.query(Trigger).filter_by(resource_id=row.id, kind='telegram').first()
        if not trigger:
            continue
        deployment = db.query(Deployment).filter_by(resource_id=row.id).first()
        events = db.query(Event).filter_by(resource_id=row.id, organization_id=organization(user), environment=environment, kind='telegram_message').order_by(Event.id.desc()).limit(20).all()
        items.append({'resource_id': row.id, 'name': row.name, 'username': trigger.config.get('username'),
                      'enabled': bool(trigger.enabled and deployment and deployment.status == 'active'), 'last_polled': trigger.last_at,
                      'error': trigger.config.get('error'), 'can_manage': row.owner_user_id == user.id or user.is_superuser,
                      'messages': [{'id': event.id, 'run_id': event.run_id, 'created_at': event.created_at, **event.details} for event in events]})
    return {'items': items}


@router.put('/{resource_id}')
def toggle(resource_id: int, data: Toggle, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_publish'))):
    validate_environment(db, user, environment)
    row = scoped(db, PowerResource, user, environment).filter_by(id=resource_id, application_id='automations').first()
    if not row or not (row.owner_user_id == user.id or user.is_superuser) or row.archived_at:
        raise HTTPException(404, 'Telegram automation not found')
    trigger = db.query(Trigger).filter_by(resource_id=row.id, kind='telegram').with_for_update().first()
    if not trigger:
        raise HTTPException(404, 'Telegram listener not found')
    deployment = db.query(Deployment).filter_by(resource_id=row.id).first()
    if data.enabled and deployment.status != 'active':
        lifecycle(db, row, user, 'activate', row.version)
    elif not data.enabled and deployment.status == 'active':
        lifecycle(db, row, user, 'pause', row.version)
    trigger.enabled = data.enabled
    trigger.next_at = None
    db.commit()
    return {'enabled': data.enabled}
