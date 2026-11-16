"""Telegram automation setup is exposed only inside Power Apps Automations."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, SecretStr
from typing import Literal
from app.apps.power_apps.telegram_defaults import DEFAULT_BOT_TOKEN
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.apps.power_apps.contracts import Contract
from app.apps.power_apps.service import organization, validate_environment, scoped
from app.apps.power_apps.models import PowerResource
from app.apps.power_apps.runtime_models import AutomationTrigger as Trigger, AutomationDeployment as Deployment, AutomationEvent as Event
from app.apps.power_apps.runtime import lifecycle
from app.apps.power_apps.integrations import vault
from app.apps.power_apps.integrations.contracts import ConnectionCreate
from app.apps.power_apps.telegram import bot_request, create_workflow, conversation, interface_conversation
from app.apps.power_apps.telegram_ai import AIConfiguration
from app.apps.power_apps.telegram_experience import ExperienceConfiguration
from app.apps.power_apps import telegram_audience as purpose

router = APIRouter(prefix='/power-apps/automations/telegram', tags=['Telegram automations'], dependencies=[Depends(RequirePermission('power_apps_view'))])


@router.get('/{resource_id}/experience')
def get_experience(resource_id: int, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_view'))):
    from app.apps.power_apps.telegram_experience import configuration
    _, trigger = bot_access(db, user, resource_id, environment, manage=True)
    return {'configuration': configuration(trigger).model_dump(mode='json')}


@router.put('/{resource_id}/experience')
def update_experience(resource_id: int, data: ExperienceConfiguration, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_publish'))):
    from app.apps.power_apps.telegram_experience import save
    row, trigger = bot_access(db, user, resource_id, environment, manage=True)
    result = save(db, row, trigger, user, data)
    db.commit()
    return {'configuration': result}


@router.get('/{resource_id}/experience-options')
def experience_options(resource_id: int, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_view'))):
    from app.access.service import background_scope
    row, trigger = bot_access(db, user, resource_id, environment, manage=True)
    values = {'branch_id': trigger.config.get('branch_id'), 'owner_user_id': row.owner_user_id, 'employees': [], 'services': [], 'resources': [], 'booking_error': None}
    try:
        RequirePermission('employee_view', 'employee_update')(user)
        values['employees'] = employee_roster(db, user, row)
    except HTTPException:
        pass
    try:
        from app.apps.srm.industry_api import context, query
        from app.apps.srm.models import SRMProduct
        from app.apps.srm.services.commercial import record
        with background_scope(db, user, 'srm', 'view', branch_id=trigger.config.get('branch_id')):
            branch = context(db, user, appointments=True)
            values['resources'] = [{'id': item.id, 'name': item.title, 'type': item.data['resource_type']} for item in query(db, user, branch).filter_by(kind='resource', status='active').limit(200).all()]
            for item in db.query(SRMProduct).filter(SRMProduct.active.is_(True), SRMProduct.product_type.in_(['service', 'services', 'Service', 'Services'])).limit(200).all():
                try:
                    record(db, SRMProduct, item.id, user)
                    values['services'].append({'id': item.id, 'name': item.item_name})
                except HTTPException:
                    continue
    except HTTPException:
        values['booking_error'] = 'Sales appointment access and an active bot branch are required to configure booking.'
    return values


class Setup(Contract):
    name: str = Field(default='Telegram customer enquiries', min_length=1, max_length=180)
    token: SecretStr | None = None
    audience: Literal['public', 'company'] = 'public'


class BotConfiguration(Contract):
    audience: Literal['public', 'company', 'shared'] = 'shared'
    public_enabled: bool = True
    company_enabled: bool = True
    create_crm_records: bool = False
    company_user_ids: list[str] = Field(default_factory=list, max_length=100)
    public_welcome: str = Field(default="Welcome! Choose Sales, Support, or Order status. Send /cancel to reset.", min_length=1, max_length=2000)
    company_welcome: str = Field(default="Company workspace: choose Create lead, Create task, Internal request or Help. Send /human for a person or /public for customer enquiries.", min_length=1, max_length=2000)


class Toggle(Contract):
    enabled: bool


class Simulation(Contract):
    messages: list[str] = Field(min_length=1, max_length=20)
    interface: Literal["public", "company"] = "public"


@router.post('/simulate')
def simulate(data: Simulation, user=Depends(RequirePermission('power_apps_view'))):
    state, steps = {}, []
    for text in data.messages:
        if len(text) > 4096:
            raise HTTPException(422, 'Messages must be at most 4096 characters')
        state, reply = conversation(text, state) if data.interface == 'public' else interface_conversation(text, state, {'company_enabled': True, 'company_user_ids': ['1']}, '1', company_default=True)
        steps.append({'message': text, 'reply': reply, 'stage': state['stage']})
    return {'steps': steps, 'enquiry': state if state.get('stage') == 'complete' else None, 'sent': False}


@router.post('/setup', status_code=201)
def setup(data: Setup, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_create'))):
    for permission in ('power_apps_manage_credentials', 'power_apps_execute', 'power_apps_publish'):
        RequirePermission(permission)(user)
    validate_environment(db, user, environment)
    if data.audience == 'company' and (not data.token or not data.token.get_secret_value().strip()):
        raise HTTPException(422, 'Enter a separate employee bot token. The public bootstrap token cannot be used for a company bot.')
    if data.audience == 'company' and DEFAULT_BOT_TOKEN and data.token.get_secret_value().strip() == DEFAULT_BOT_TOKEN:
        raise HTTPException(422, 'Create a separate employee bot and enter its token. The public bootstrap bot cannot be used for employee access.')
    if not data.token and not DEFAULT_BOT_TOKEN:
        raise HTTPException(422, "Enter a bot token or configure the server bootstrap token.")
    try:
        conn = vault.create(db, user, environment, ConnectionCreate(connector_id='telegram', name=data.name[:160] + ' bot', auth_type='bearer', secrets={'access_token': data.token or SecretStr(DEFAULT_BOT_TOKEN)}, writes_enabled=True))
        bot = bot_request(db, user, conn, 'getMe')
        webhook = bot_request(db, user, conn, 'getWebhookInfo')
        if webhook.get('url'):
            raise HTTPException(409, 'This bot has an existing webhook. Remove that webhook before creating a local polling automation.')
        row = create_workflow(db, user, environment, conn, bot, data.name)
        trigger = db.query(Trigger).filter_by(resource_id=row.id, kind='telegram').one()
        interfaces = BotConfiguration().model_dump(exclude={'audience'})
        interfaces['create_crm_records'] = data.audience == 'public'
        interfaces['public_enabled'], interfaces['company_enabled'] = data.audience == 'public', data.audience == 'company'
        if data.audience == 'company':
            interfaces['company_welcome'] = 'Company workspace: choose Create lead, Create task, Internal request or Help. Send /human for a person.'
        trigger.config = {**trigger.config, 'audience': data.audience, 'interfaces': interfaces,
            'company_token_verified': data.audience == 'company'}
        db.commit()
        return {'resource_id': row.id, 'username': bot.get('username'), 'enabled': True, 'audience': data.audience}
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
        events = [event for event in events if purpose.audience(trigger) == 'shared' or event.details.get('state', {}).get('interface') == purpose.audience(trigger)]
        items.append({'resource_id': row.id, 'name': row.name, 'username': trigger.config.get('username'),
                      'enabled': bool(trigger.enabled and deployment and deployment.status == 'active'), 'last_polled': trigger.last_at,
                      'error': trigger.config.get('error'), 'can_manage': row.owner_user_id == user.id or user.is_superuser,
                      'audience': purpose.audience(trigger),
                      'configuration': {**trigger.config.get('interfaces', BotConfiguration().model_dump(exclude={'audience'})), 'audience': purpose.audience(trigger)},
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


@router.put('/{resource_id}/configuration')
def configure(resource_id: int, data: BotConfiguration, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_publish'))):
    import re
    validate_environment(db, user, environment)
    row = scoped(db, PowerResource, user, environment).filter_by(id=resource_id, application_id='automations').first()
    if not row or row.archived_at or not (row.owner_user_id == user.id or user.is_superuser):
        raise HTTPException(404, 'Telegram automation not found')
    if any(not re.fullmatch(r'[1-9]\d{0,19}', value) for value in data.company_user_ids):
        raise HTTPException(422, 'Company user IDs must be positive numeric Telegram user IDs')
    trigger = db.query(Trigger).filter_by(resource_id=row.id, kind='telegram').with_for_update().first()
    if not trigger:
        raise HTTPException(404, 'Telegram listener not found')
    if data.create_crm_records:
        from app.access.service import background_scope
        from app.apps.crm.api import router as crm
        if not trigger.config.get('branch_id'):
            raise HTTPException(422, 'This bot needs a branch before CRM creation can be enabled')
        with background_scope(db, user, 'crm', 'create', branch_id=trigger.config['branch_id']):
            crm._assert_entity_permission('leads', user, 'manage')
            crm._assert_entity_permission('tasks', user, 'manage')
    selected = data.audience if 'audience' in data.model_fields_set else purpose.audience(trigger)
    if selected == 'shared' and purpose.audience(trigger) != 'shared':
        raise HTTPException(422, 'Shared access is supported only by legacy bots. Choose public or company.')
    if selected == 'company' and purpose.audience(trigger) != 'company' and trigger.config.get('company_token_verified') is not True:
        raise HTTPException(422, 'Connect a separate employee bot using its own token. A public or legacy bot cannot be promoted to company access here.')
    config = data.model_dump(exclude={'audience'})
    if selected == 'public':
        config['create_crm_records'] = True
    if selected != 'shared':
        config['public_enabled'] = selected == 'public' and config['public_enabled']
        config['company_enabled'] = selected == 'company' and config['company_enabled']
    config['company_user_ids'] = list(dict.fromkeys(config['company_user_ids']))
    purpose.change(db, row, trigger, selected)
    trigger.config = {**trigger.config, 'interfaces': config}
    db.commit()
    return {'configuration': {**config, 'audience': selected}}


def bot_access(db, user, resource_id, environment, manage=False):
    validate_environment(db, user, environment)
    row = scoped(db, PowerResource, user, environment).filter_by(id=resource_id, application_id='automations').first()
    if not row or row.archived_at or manage and not (row.owner_user_id == user.id or user.is_superuser):
        raise HTTPException(404, 'Telegram bot not found')
    trigger = db.query(Trigger).filter_by(resource_id=row.id, kind='telegram').with_for_update().first()
    if not trigger:
        raise HTTPException(404, 'Telegram listener not found')
    return row, trigger


class LinkCode(Contract):
    interface: Literal['company', 'public'] = 'company'
    contact_id: int | None = Field(default=None, gt=0)
    lead_id: int | None = Field(default=None, gt=0)
    customer_id: int | None = Field(default=None, gt=0)


class EmployeeLink(Contract):
    employee_id: int = Field(gt=0)
    telegram_user_id: str = Field(pattern=r'^[1-9]\d{0,19}$')


class HandoffChange(Contract):
    action: Literal['claim', 'assign', 'resolve', 'resume']
    assignee_user_id: int | None = Field(default=None, gt=0)


class StageChange(Contract):
    target: str = Field(min_length=1, max_length=40)
    expected_revision: int = Field(ge=0)


class StageReview(Contract):
    approved: bool


class StaffReply(Contract):
    text: str = Field(min_length=1, max_length=4096)
    client_key: str = Field(min_length=16, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    draft_id: int | None = Field(default=None, gt=0)


@router.get('/{resource_id}/ai-configuration')
def ai_configuration(resource_id: int, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_view'))):
    from app.apps.power_apps.telegram_ai import configuration
    from app.ai_operator.local_tensorflow import status, runtime_scope
    row, trigger = bot_access(db, user, resource_id, environment)
    return {'configuration': configuration(trigger).model_dump(), 'local_model': status(runtime_scope(db, user)),
            'engine': 'actionbot', 'company_mode': 'permission-scoped planning and native reads', 'public_mode': 'approved information and enquiry intake; no business tools'}


@router.put('/{resource_id}/ai-configuration')
def configure_ai(resource_id: int, data: AIConfiguration, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_publish'))):
    from app.ai_operator.provider_scope import resolve_provider
    from app.access.service import background_scope
    from app.ai_agents.api import _require_ai_access
    row, trigger = bot_access(db, user, resource_id, environment, manage=True)
    if data.enabled:
        with background_scope(db, user, 'ai', 'view', branch_id=trigger.config.get('branch_id')):
            _require_ai_access(user)
            if data.provider not in {'local', 'preferred'}:
                model = resolve_provider(db, user, data.provider)
                if not model or not model.enabled or not model.data_sharing_allowed:
                    raise HTTPException(422, 'Enable the selected model and its data-sharing setting in ActionBot first')
    trigger.config = {**trigger.config, 'ai': data.model_dump()}
    db.commit()
    return {'configuration': data.model_dump()}


@router.get('/{resource_id}/employee-options')
def employee_options(resource_id: int, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('employee_view', 'employee_update'))):
    row, trigger = bot_access(db, user, resource_id, environment, manage=True)
    purpose.require(trigger, 'company')
    return {'items': employee_roster(db, user, row)}


def employee_roster(db, user, row):
    """Authorized ERP roster for routing, independently of Telegram login links."""
    from app.models.employee import Employee
    from app.models.company import Branch
    RequirePermission('employee_view', 'employee_update')(user)
    from app.access.service import check_background_access
    check_background_access(db, user, 'hrms', 'view')
    records = db.query(Employee).join(Branch, Employee.branch_id == Branch.id).filter(
        Branch.company_id == row.organization_id, Employee.deleted_at.is_(None), Employee.user_id.is_not(None),
        Employee.status.in_(['Active', 'Probation', 'On Leave'])).order_by(Employee.first_name, Employee.id).limit(200).all()
    return [{'id': item.id, 'employee_code': item.employee_id, 'name': f'{item.first_name} {item.last_name}', 'user_id': item.user_id} for item in records]


@router.post('/{resource_id}/link-code')
def link_code(resource_id: int, data: LinkCode, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_view'))):
    from app.apps.power_apps.telegram_operations import issue_code
    row, _ = bot_access(db, user, resource_id, environment, manage=data.interface == 'public')
    if data.interface == 'public':
        RequirePermission('power_apps_publish')(user)
    token = issue_code(db, row, user, data.interface, data.contact_id, data.lead_id, data.customer_id)
    db.commit()
    return {'command': '/link ' + token, 'expires_in_seconds': 600}


@router.post('/{resource_id}/employee-links', status_code=201)
def link_employee(resource_id: int, data: EmployeeLink, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_publish'))):
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.apps.power_apps.models import TelegramIdentity
    from app.apps.power_apps.telegram_operations import staff_member
    from app.apps.power_apps.runtime import now, scope_values
    RequirePermission('employee_update')(user)
    row, trigger = bot_access(db, user, resource_id, environment, manage=True)
    purpose.require(trigger, 'company')
    from app.access.service import check_background_access
    check_background_access(db, user, 'hrms', 'edit', branch_id=trigger.config.get('branch_id'))
    employee = db.query(Employee).join(Branch, Employee.branch_id == Branch.id).filter(
        Employee.id == data.employee_id, Employee.deleted_at.is_(None), Branch.company_id == row.organization_id).first()
    if not employee or not employee.user_id:
        raise HTTPException(422, 'Choose an employee in this company with a linked BusinessSuite user account')
    linked = db.query(TelegramIdentity).filter_by(resource_id=row.id, telegram_id=data.telegram_user_id, interface='company').first()
    if linked and linked.revoked_at is None and linked.user_id != employee.user_id:
        raise HTTPException(409, 'This Telegram ID belongs to another employee link. Revoke that link first.')
    duplicate = db.query(TelegramIdentity).filter_by(resource_id=row.id, user_id=employee.user_id, interface='company', revoked_at=None).filter(TelegramIdentity.telegram_id != data.telegram_user_id).first()
    if duplicate:
        raise HTTPException(409, 'Employee already has a Telegram link. Revoke the old link first.')
    linked = linked or TelegramIdentity(organization_id=row.organization_id, environment=environment, resource_id=row.id, telegram_id=data.telegram_user_id, interface='company')
    linked.user_id, linked.employee_id = employee.user_id, employee.id
    linked.display_name = f'{employee.first_name} {employee.last_name}'[:180]
    linked.verified_at, linked.revoked_at = now(), None
    staff_member(db, linked, row.organization_id)
    db.add(linked)
    db.flush()
    db.add(Event(**scope_values(row), resource_id=row.id, kind='telegram_identity_linked', details={'identity_id': linked.id, 'employee_id': employee.id, 'actor_id': user.id}))
    db.commit()
    return {'identity_id': linked.id, 'employee_id': employee.id, 'automatic_authorization': True}


@router.delete('/{resource_id}/identities/{identity_id}')
def revoke_identity(resource_id: int, identity_id: int, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_publish'))):
    from app.apps.power_apps.models import TelegramIdentity, TelegramConversation
    from app.apps.power_apps.runtime import now, scope_values
    row, _ = bot_access(db, user, resource_id, environment, manage=True)
    linked = db.query(TelegramIdentity).filter_by(id=identity_id, resource_id=row.id, organization_id=row.organization_id).first()
    if not linked:
        raise HTTPException(404, 'Identity not found')
    linked.revoked_at = now()
    for thread in db.query(TelegramConversation).filter_by(resource_id=row.id, identity_id=linked.id).all():
        thread.state = {}
        thread.context = {}
        thread.status, thread.assignee_user_id = 'bot', None
        thread.lead_id, thread.task_id = None, None
    db.add(Event(**scope_values(row), resource_id=row.id, kind='telegram_identity_revoked', details={'identity_id': linked.id, 'actor_id': user.id}))
    db.commit()
    return {'revoked': True}


@router.get('/{resource_id}/operations')
def operations(resource_id: int, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_view'))):
    from app.apps.power_apps.models import TelegramIdentity, TelegramConversation, TelegramMessage, PowerExecution
    row, trigger = bot_access(db, user, resource_id, environment)
    from app.apps.power_apps.telegram_experience import configuration as experience_configuration
    experience = experience_configuration(trigger)
    manager = row.owner_user_id == user.id or user.is_superuser
    query = db.query(TelegramConversation).filter_by(resource_id=row.id, organization_id=row.organization_id, environment=environment)
    if purpose.audience(trigger) != 'shared':
        query = query.filter_by(interface=purpose.audience(trigger))
    threads = query.order_by(TelegramConversation.last_at.desc()).limit(50).all()
    items = []
    for thread in threads:
        messages = db.query(TelegramMessage).filter_by(conversation_id=thread.id).order_by(TelegramMessage.id.desc()).limit(50).all()
        items.append({'id': thread.id, 'interface': thread.interface, 'chat_id': thread.chat_id, 'status': thread.status,
            'assignee_user_id': thread.assignee_user_id, 'lead_id': thread.lead_id, 'task_id': thread.task_id,
            'context': thread.context,
            'service_stages': [stage.model_dump() for flow in experience.workflows if flow.id == (thread.context or {}).get('workflow_id') for stage in flow.stages],
            'messages': [{'id': message.id, 'direction': message.direction, 'text': message.text, 'created_at': message.created_at,
                'run_id': message.run_id, 'delivery_status': db.get(PowerExecution, message.run_id).status if message.run_id and db.get(PowerExecution, message.run_id) else None} for message in reversed(messages)]})
    links = db.query(TelegramIdentity).filter_by(resource_id=row.id, revoked_at=None)
    if purpose.audience(trigger) != 'shared':
        links = links.filter_by(interface=purpose.audience(trigger))
    linked = links.order_by(TelegramIdentity.id.desc()).limit(200).all() if manager else []
    reviews = db.query(Event).filter_by(resource_id=row.id, kind='telegram_stage_review').filter(Event.details['status'].as_string() == 'pending').order_by(Event.id.desc()).limit(50).all()
    visible_ids = {thread.id for thread in threads}
    reviews = [item for item in reviews if item.details.get('conversation_id') in visible_ids or item.details.get('operation', {}).get('conversation_id') in visible_ids]
    return {'audience': purpose.audience(trigger), 'conversations': items, 'stage_reviews': [{'id': item.id, **item.details, 'can_review': any(flow.id == item.details['operation']['workflow_id'] and user.id in flow.approval_user_ids for flow in experience.workflows)} for item in reviews], 'identities': [{'id': link.id, 'interface': link.interface, 'telegram_user_id': link.telegram_id,
        'user_id': link.user_id, 'employee_id': link.employee_id, 'contact_id': link.contact_id, 'lead_id': link.lead_id, 'customer_id': link.customer_id,
        'name': link.display_name, 'verified': bool(link.verified_at)} for link in linked], 'can_manage': manager, 'current_user_id': user.id}


@router.put('/{resource_id}/conversations/{conversation_id}')
def handoff(resource_id: int, conversation_id: int, data: HandoffChange, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_execute'))):
    from app.apps.power_apps.models import TelegramConversation, TelegramMessage
    from app.apps.power_apps.telegram_operations import member
    from app.apps.power_apps.runtime import now, scope_values
    from app.access.service import background_scope
    row, trigger = bot_access(db, user, resource_id, environment)
    thread = db.query(TelegramConversation).filter_by(id=conversation_id, resource_id=row.id, organization_id=row.organization_id).with_for_update().first()
    if not thread:
        raise HTTPException(404, 'Conversation not found')
    purpose.require(trigger, thread.interface)
    manager = row.owner_user_id == user.id or user.is_superuser
    if not manager and thread.assignee_user_id not in {None, user.id}:
        raise HTTPException(403, 'This conversation is assigned to another person')
    if data.action == 'assign' and not manager:
        raise HTTPException(403, 'Only the bot owner can assign another person')
    if data.action in {'assign', 'claim'}:
        target = data.assignee_user_id if data.action == 'assign' else user.id
        if not target:
            raise HTTPException(422, 'Choose an assignee')
        assignee = member(db, target, row.organization_id)
        with background_scope(db, assignee, 'power_apps', 'create', branch_id=trigger.config.get('branch_id')):
            RequirePermission('power_apps_execute')(assignee)
        thread.status, thread.assignee_user_id = 'assigned', target
    else:
        thread.status, thread.assignee_user_id, thread.state = ('resolved' if data.action == 'resolve' else 'bot'), None, {}
    thread.last_at = now()
    db.add(TelegramMessage(conversation_id=thread.id, organization_id=row.organization_id, environment=environment, resource_id=row.id,
        direction='system', text=f'{data.action} by user #{user.id}', created_by_user_id=user.id))
    db.add(Event(**scope_values(row), resource_id=row.id, kind='telegram_handoff', details={'conversation_id': thread.id, 'action': data.action, 'actor_id': user.id, 'assignee_id': thread.assignee_user_id}))
    db.commit()
    return {'status': thread.status, 'assignee_user_id': thread.assignee_user_id}


@router.post('/{resource_id}/conversations/{conversation_id}/reply', status_code=202)
def reply(resource_id: int, conversation_id: int, data: StaffReply, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_execute'))):
    from app.apps.power_apps.models import TelegramConversation, TelegramMessage
    from app.apps.power_apps.telegram_operations import queue_reply, identity, staff_member
    from app.apps.power_apps.runtime_triggers import trigger_identity
    from app.access.service import background_scope
    row, trigger = bot_access(db, user, resource_id, environment)
    thread = db.query(TelegramConversation).filter_by(id=conversation_id, resource_id=row.id, organization_id=row.organization_id).with_for_update().first()
    if not thread:
        raise HTTPException(404, 'Conversation not found')
    purpose.require(trigger, thread.interface)
    if thread.status != 'assigned' or thread.assignee_user_id != user.id:
        raise HTTPException(409, 'Claim this conversation before replying')
    config = trigger.config.get('interfaces', {})
    if not trigger.enabled or not config.get(f'{thread.interface}_enabled', True):
        raise HTTPException(409, 'Enable this bot and interface before replying')
    if thread.interface == 'company':
        linked = identity(db, row, thread.telegram_id, 'company')
        if not linked:
            raise HTTPException(403, 'Employee Telegram authorization was revoked')
        staff_member(db, linked, row.organization_id)
    existing = db.query(TelegramMessage).filter_by(conversation_id=thread.id, client_key=data.client_key).first()
    if existing:
        if existing.text != data.text:
            raise HTTPException(409, 'This reply key has already been used for another message')
        return {'run_id': existing.run_id, 'status': 'queued'}
    if data.draft_id:
        from app.apps.power_apps.telegram_reply_drafts import use
        use(db, row, trigger, thread, user, data.draft_id, data.text)
    owner = trigger_identity(db, trigger)
    with background_scope(db, owner, 'power_apps', 'create', branch_id=trigger.config.get('branch_id')):
        run_id = queue_reply(db, row, trigger, owner, thread, data.text, f'telegram-staff:{thread.id}:{data.client_key}', created_by=user.id)
    # Use the client-provided key for exact retry matching, independent of queue key formatting.
    message = db.query(TelegramMessage).filter_by(conversation_id=thread.id, run_id=run_id).one()
    message.client_key = data.client_key
    db.commit()
    return {'run_id': run_id, 'status': 'queued'}


@router.post('/{resource_id}/conversations/{conversation_id}/draft')
def draft_reply(resource_id: int, conversation_id: int, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_execute'))):
    from app.apps.power_apps.models import TelegramConversation
    from app.apps.power_apps.telegram_reply_drafts import generate
    row, trigger = bot_access(db, user, resource_id, environment)
    thread = db.query(TelegramConversation).filter_by(id=conversation_id, resource_id=row.id, organization_id=row.organization_id).first()
    if not thread:
        raise HTTPException(404, 'Conversation not found')
    purpose.require(trigger, thread.interface)
    if thread.status != 'assigned' or thread.assignee_user_id != user.id:
        raise HTTPException(409, 'Claim this conversation before drafting a reply')
    db.commit()  # Do not hold the polling/configuration lock during model generation.
    result = generate(db, row, trigger, thread, user)
    db.commit()
    return result


@router.post('/{resource_id}/conversations/{conversation_id}/stage')
def change_stage(resource_id: int, conversation_id: int, data: StageChange, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_execute'))):
    from app.apps.power_apps.models import TelegramConversation
    from app.apps.power_apps.telegram_workflows import transition
    row, trigger = bot_access(db, user, resource_id, environment)
    thread = db.query(TelegramConversation).filter_by(id=conversation_id, resource_id=row.id, organization_id=row.organization_id).with_for_update().first()
    if not thread:
        raise HTTPException(404, 'Service conversation not found')
    purpose.require(trigger, thread.interface)
    result = transition(db, row, trigger, thread, data.target, data.expected_revision, user.id)
    db.commit()
    return result


@router.post('/{resource_id}/stage-reviews/{review_id}')
def review_stage(resource_id: int, review_id: int, data: StageReview, environment: str = 'development', db: Session = Depends(get_db), user=Depends(RequirePermission('power_apps_execute'))):
    from app.apps.power_apps.telegram_workflows import review
    row, trigger = bot_access(db, user, resource_id, environment)
    item = db.query(Event).filter_by(id=review_id, resource_id=row.id, organization_id=row.organization_id, environment=environment, kind='telegram_stage_review').with_for_update().first()
    if not item:
        raise HTTPException(404, 'Service stage review not found')
    from app.apps.power_apps.models import TelegramConversation
    thread = db.query(TelegramConversation).filter_by(id=item.details['operation']['conversation_id'], resource_id=row.id).first()
    if not thread:
        raise HTTPException(404, 'Service conversation not found')
    purpose.require(trigger, thread.interface)
    result = review(db, row, trigger, item, user.id, data.approved)
    db.commit()
    return result
