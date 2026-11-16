"""Employee eligibility, explainable handoff routing and response deadlines."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from app.core.deps import RequirePermission
from app.access.service import background_scope
from app.models.notification import Notification
from app.apps.power_apps.models import TelegramIdentity, TelegramConversation
from app.apps.power_apps.runtime import now, scope_values
from app.apps.power_apps.runtime_models import AutomationEvent
from app.apps.power_apps.telegram_experience import configuration


def eligible(db, resource, trigger, user_id):
    from app.apps.power_apps.telegram_operations import member, staff_member
    from app.apps.power_apps.telegram_audience import audience
    # Public-bot staff work in ERP; their customer-facing bot must never infer
    # company authentication from a Telegram identity on any bot.
    linked = None if audience(trigger) == 'public' else db.query(TelegramIdentity).filter_by(resource_id=resource.id, user_id=user_id, interface='company', revoked_at=None).first()
    actor = staff_member(db, linked, resource.organization_id) if linked else member(db, user_id, resource.organization_id)
    with background_scope(db, actor, 'power_apps', 'create', branch_id=trigger.config.get('branch_id')):
        RequirePermission('power_apps_execute')(actor)
    return actor


def public_employee(db, resource, trigger, user_id):
    """Check the published owner's current ERP directory authority and mapping."""
    from app.apps.power_apps.telegram_operations import member
    from app.models.employee import Employee
    from app.models.company import Branch
    owner = member(db, resource.owner_user_id, resource.organization_id)
    branch = trigger.config.get('branch_id')
    with background_scope(db, owner, 'hrms', 'view', branch_id=branch):
        RequirePermission('employee_view')(owner)
        employee = db.query(Employee).join(Branch, Employee.branch_id == Branch.id).filter(
            Employee.user_id == user_id, Employee.branch_id == branch, Employee.deleted_at.is_(None),
            Employee.status.in_(['Active', 'Probation']), Branch.company_id == resource.organization_id,
            Branch.is_active.is_(True),
        ).populate_existing().first()
        if not employee or employee.date_of_exit and employee.date_of_exit <= now().date():
            raise HTTPException(403, 'Routing employee is no longer active in this branch')


def select_agent(db, resource, trigger, thread, instant=None):
    instant = instant or now()
    config = configuration(trigger)
    lang = (thread.context or {}).get('language', 'en')
    skills = {value.casefold() for value in (thread.context or {}).get('required_skills', [])}
    candidates = []
    for agent in config.routing_agents:
        if not agent.available or agent.branch_id != trigger.config.get('branch_id') or lang not in agent.languages or not skills <= {value.casefold() for value in agent.skills}:
            continue
        local = instant.astimezone(ZoneInfo(agent.timezone))
        if local.weekday() not in agent.weekdays or not agent.opens <= local.strftime('%H:%M') < agent.closes:
            continue
        try:
            from app.apps.power_apps.telegram_audience import audience
            if audience(trigger) == 'public':
                public_employee(db, resource, trigger, agent.user_id)
            else:
                link = db.query(TelegramIdentity).filter_by(resource_id=resource.id, user_id=agent.user_id, interface='company', revoked_at=None).first()
                if not link or not link.employee_id:
                    continue
            eligible(db, resource, trigger, agent.user_id)
        except HTTPException:
            continue
        workload = db.query(TelegramConversation).filter_by(resource_id=resource.id, assignee_user_id=agent.user_id).filter(TelegramConversation.status.in_(['waiting', 'assigned']), TelegramConversation.id != thread.id).count()
        if workload >= agent.capacity:
            continue
        candidates.append((workload / agent.capacity, workload, agent.user_id, agent))
    if not candidates:
        eligible(db, resource, trigger, resource.owner_user_id)
        return resource.owner_user_id, {'fallback': True, 'reason': 'No eligible available employee matched branch, language, skills and capacity; the bot owner remains responsible.'}
    _, workload, ident, agent = min(candidates, key=lambda item: item[:3])
    return ident, {'fallback': False, 'reason': 'Matched branch, language, required skills, working hours and available capacity.',
        'language': lang, 'matched_skills': sorted(skills), 'workload': workload, 'capacity': agent.capacity, 'branch_id': agent.branch_id}


def start_deadline(thread, trigger, instant=None):
    instant = instant or now()
    context = dict(thread.context or {})
    if context.get('sla_waiting'):
        return
    settings = configuration(trigger)
    urgent = context.get('qualification', {}).get('priority') == 'Urgent'
    minutes = settings.urgent_handoff_minutes if urgent else settings.handoff_minutes
    thread.context = {**context, 'sla_waiting': True, 'sla_due_at': (instant + timedelta(minutes=minutes)).isoformat(),
        'sla_cycle': context.get('sla_cycle', 0) + 1, 'sla_escalation_level': 0, 'sla_breached': False}


def assign_handoff(db, resource, trigger, thread, instant=None):
    ident, explanation = select_agent(db, resource, trigger, thread, instant)
    thread.assignee_user_id = ident
    thread.status = 'waiting' if explanation['fallback'] else 'assigned'
    thread.context = {**(thread.context or {}), 'routing': explanation}
    start_deadline(thread, trigger, instant)
    db.add(AutomationEvent(**scope_values(resource), resource_id=resource.id, kind='telegram_routed',
        details={'conversation_id': thread.id, 'assignee_user_id': ident, 'explanation': explanation}))
    return ident


def staff_responded(thread, user_id, instant=None):
    thread.context = {**(thread.context or {}), 'sla_waiting': False, 'first_staff_reply_at': (instant or now()).isoformat(), 'last_staff_user_id': user_id}


def pending_deadlines(db, resource):
    """Scan active deadlines in bounded pages without starving newer cases."""
    last_id = 0
    while True:
        batch = db.query(TelegramConversation).filter_by(resource_id=resource.id).filter(
            TelegramConversation.status.in_(['waiting', 'assigned']),
            TelegramConversation.context['sla_waiting'].as_boolean().is_(True),
            TelegramConversation.id > last_id,
        ).order_by(TelegramConversation.id).limit(200).all()
        if not batch:
            return
        for thread in batch:
            yield thread
        last_id = batch[-1].id


def tick(db, resource, trigger, instant=None):
    instant = instant or now()
    settings = configuration(trigger)
    count = 0
    for thread in pending_deadlines(db, resource):
        context = dict(thread.context or {})
        if not context.get('sla_waiting') or not context.get('sla_due_at'):
            continue
        if datetime.fromisoformat(context['sla_due_at']) > instant:
            continue
        level = context.get('sla_escalation_level', 0)
        if level > len(settings.escalation_user_ids):
            continue
        next_id = settings.escalation_user_ids[level] if level < len(settings.escalation_user_ids) else resource.owner_user_id
        try:
            eligible(db, resource, trigger, next_id)
        except HTTPException:
            next_id = resource.owner_user_id
            eligible(db, resource, trigger, next_id)
        thread.assignee_user_id = next_id
        thread.status = 'assigned'
        thread.context = {**context, 'sla_breached': True, 'sla_escalation_level': level + 1,
            'sla_due_at': (instant + timedelta(minutes=settings.handoff_minutes)).isoformat()}
        db.add(Notification(company_id=resource.organization_id, user_id=next_id, title='Telegram response deadline breached',
            message=f'Conversation #{thread.id} needs a staff response. Escalation level {level + 1}.', module='power_apps', event_type='telegram.sla_breach',
            action_url=f'/power-apps/automations/telegram?environment={resource.environment}', channels=['in_app']))
        db.add(AutomationEvent(**scope_values(resource), resource_id=resource.id, kind='telegram_sla_breach',
            details={'conversation_id': thread.id, 'cycle': context.get('sla_cycle'), 'level': level + 1, 'assignee_user_id': next_id}))
        count += 1
    return count
