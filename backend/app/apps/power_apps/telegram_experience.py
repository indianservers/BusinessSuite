"""Versioned knowledge and industry workflow contracts shared by both bot interfaces."""
import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, HttpUrl, field_validator, model_validator
from app.apps.power_apps.contracts import Contract


def now():
    return datetime.now(timezone.utc)


class KnowledgeFact(Contract):
    id: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,63}$')
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=4000)
    kind: Literal['service', 'price', 'policy', 'document', 'faq'] = 'faq'
    source_url: HttpUrl = Field(max_length=1000)
    source_reference: str = Field(min_length=1, max_length=240)
    interface: Literal['public', 'company', 'both'] = 'public'
    language: Literal['en', 'te', 'hi'] = 'en'
    approved: bool = False
    approved_at: datetime | None = None
    approved_by_user_id: int | None = None
    expires_at: datetime

    @field_validator('expires_at')
    @classmethod
    def aware_expiry(cls, value):
        if value.tzinfo is None:
            raise ValueError('Knowledge expiry requires a timezone')
        return value


class IntakeQuestion(Contract):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label: str = Field(min_length=1, max_length=240)
    translations: dict[Literal['te', 'hi'], str] = Field(default_factory=dict, max_length=2)
    type: Literal['text', 'choice', 'number', 'date', 'location', 'document'] = 'text'
    required: bool = True
    choices: list[str] = Field(default_factory=list, max_length=12)
    minimum: float | None = None
    maximum: float | None = None
    accepted_mime_types: list[Literal['application/pdf', 'image/jpeg', 'image/png', 'text/plain']] = Field(default_factory=list, max_length=4)

    @model_validator(mode='after')
    def valid(self):
        if self.type == 'choice' and not self.choices:
            raise ValueError('Choice questions need options')
        if len(set(self.choices)) != len(self.choices) or any(not item.strip() or len(item) > 100 for item in self.choices):
            raise ValueError('Question choices must be unique nonempty labels of at most 100 characters')
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError('Question minimum cannot exceed maximum')
        if any(not value.strip() or len(value) > 240 for value in self.translations.values()):
            raise ValueError('Question translations must contain 1–240 characters')
        return self


class UrgencyRule(Contract):
    field: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    operator: Literal['equals', 'contains', 'less_than', 'greater_than'] = 'equals'
    value: str = Field(min_length=1, max_length=180)
    priority: Literal['Normal', 'High', 'Urgent']
    reason: str = Field(min_length=1, max_length=240)


class ServiceStage(Contract):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    label: str = Field(min_length=1, max_length=120)
    requires_approval: bool = False
    next_stages: list[str] = Field(default_factory=list, max_length=10)


class IndustryWorkflow(Contract):
    id: str = Field(pattern=r'^[a-z][a-z0-9_-]{0,49}$')
    name: str = Field(min_length=1, max_length=120)
    industry: str = Field(min_length=1, max_length=80)
    interface: Literal['public', 'company', 'both'] = 'public'
    enabled: bool = True
    questions: list[IntakeQuestion] = Field(min_length=1, max_length=25)
    urgency_rules: list[UrgencyRule] = Field(default_factory=list, max_length=20)
    required_skills: list[str] = Field(default_factory=list, max_length=12)
    result: Literal['lead_and_task', 'task', 'handoff', 'appointment_request'] = 'lead_and_task'
    approval_user_ids: list[int] = Field(default_factory=list, max_length=20)
    stages: list[ServiceStage] = Field(default_factory=lambda: [ServiceStage(key='received', label='Received', next_stages=['completed']), ServiceStage(key='completed', label='Completed')], max_length=12)

    @model_validator(mode='after')
    def valid(self):
        keys = [question.key for question in self.questions]
        if len(set(keys)) != len(keys):
            raise ValueError('Question keys must be unique')
        if any(rule.field not in keys for rule in self.urgency_rules):
            raise ValueError('Urgency rules must reference configured questions')
        stages = [stage.key for stage in self.stages]
        if not stages or len(set(stages)) != len(stages):
            raise ValueError('Provide unique service stages')
        if any(target not in stages or target == stage.key for stage in self.stages for target in stage.next_stages):
            raise ValueError('Stage transitions must target another configured stage')
        if any(stage.requires_approval for stage in self.stages) and not self.approval_user_ids:
            raise ValueError('Approval stages require configured reviewers')
        if len(set(self.approval_user_ids)) != len(self.approval_user_ids) or any(value <= 0 for value in self.approval_user_ids):
            raise ValueError('Choose unique positive reviewer user IDs')
        if any(not skill.strip() or len(skill) > 80 for skill in self.required_skills):
            raise ValueError('Skills must contain 1–80 characters')
        return self


class RoutingAgent(Contract):
    user_id: int = Field(gt=0)
    branch_id: int = Field(gt=0)
    skills: list[str] = Field(default_factory=list, max_length=20)
    languages: list[Literal['en', 'te', 'hi']] = Field(default_factory=lambda: ['en'], min_length=1, max_length=3)
    available: bool = True
    capacity: int = Field(default=10, ge=1, le=100)
    timezone: str = 'Asia/Kolkata'
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5], max_length=7)
    opens: str = Field(default='09:00', pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    closes: str = Field(default='18:00', pattern=r'^([01]\d|2[0-3]):[0-5]\d$')

    @model_validator(mode='after')
    def valid(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(self.timezone)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError('Choose a valid timezone')
        if self.opens >= self.closes or any(value not in range(7) for value in self.weekdays):
            raise ValueError('Choose valid working days and opening hours')
        if any(not value.strip() or len(value) > 80 for value in self.skills):
            raise ValueError('Skills must contain 1–80 characters')
        return self


class BookingService(Contract):
    service_id: int = Field(gt=0)
    label: str = Field(min_length=1, max_length=120)
    resource_ids: list[int] = Field(min_length=1, max_length=10)
    duration_minutes: int = Field(default=30, ge=5, le=720)

    @field_validator('resource_ids')
    @classmethod
    def unique_resources(cls, values):
        if len(set(values)) != len(values) or any(value <= 0 for value in values):
            raise ValueError('Choose unique positive resource IDs')
        return values


class ExperienceConfiguration(Contract):
    revision: int = Field(default=0, ge=0)
    knowledge: list[KnowledgeFact] = Field(default_factory=list, max_length=100)
    workflows: list[IndustryWorkflow] = Field(default_factory=list, max_length=25)
    lead_workflow_id: str | None = Field(default=None, max_length=64)
    routing_agents: list[RoutingAgent] = Field(default_factory=list, max_length=100)
    booking_services: list[BookingService] = Field(default_factory=list, max_length=50)
    catalogue_product_ids: list[int] = Field(default_factory=list, max_length=100)
    handoff_minutes: int = Field(default=15, ge=1, le=1440)
    urgent_handoff_minutes: int = Field(default=5, ge=1, le=1440)
    escalation_user_ids: list[int] = Field(default_factory=list, max_length=10)

    @model_validator(mode='after')
    def unique(self):
        for items, field in [(self.knowledge, 'id'), (self.workflows, 'id'), (self.routing_agents, 'user_id'), (self.booking_services, 'service_id')]:
            if len({getattr(item, field) for item in items}) != len(items):
                raise ValueError('Configuration keys must be unique')
        if len(set(self.catalogue_product_ids)) != len(self.catalogue_product_ids) or any(value <= 0 for value in self.catalogue_product_ids):
            raise ValueError('Choose unique positive public catalogue product IDs')
        if len(set(self.escalation_user_ids)) != len(self.escalation_user_ids) or any(value <= 0 for value in self.escalation_user_ids):
            raise ValueError('Choose unique positive escalation user IDs')
        if self.lead_workflow_id and self.lead_workflow_id not in {flow.id for flow in self.workflows}:
            raise ValueError('The lead qualification workflow must exist')
        return self


def configuration(trigger):
    return ExperienceConfiguration.model_validate(trigger.config.get('experience', {}))


def published_knowledge(trigger, interface, instant=None):
    instant = instant or now()
    return [fact for fact in configuration(trigger).knowledge if fact.approved and fact.approved_at and fact.approved_by_user_id and fact.expires_at > instant and fact.interface in {interface, 'both'}]


def knowledge_answer(trigger, interface, text, instant=None):
    """Return an exact approved excerpt with provenance, not an invented fact."""
    if re.match(r'^\s*(?:please\s+)?(?:create|add|set|update|mark|delete|book|reschedule|cancel)\b', text, re.I):
        return None
    words = set(re.findall(r'\w+', text.casefold())) - {'what', 'are', 'the', 'is', 'your', 'our', 'please', 'tell', 'me', 'about', 'a', 'an', 'and', 'do', 'you', 'have'}
    matches = []
    for fact in published_knowledge(trigger, interface, instant):
        title = set(re.findall(r'\w+', fact.title.casefold()))
        score = len(words & title)
        if score:
            matches.append((score, fact.id, fact))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1]))
    fact = matches[0][2]
    excerpt = fact.content[:1500] + ('…' if len(fact.content) > 1500 else '')
    return {'reply': f'{excerpt}\n\nSource: {fact.source_reference} — {fact.source_url}\nValid until: {fact.expires_at.isoformat()}', 'source_ids': [fact.id]}


def qualify(workflow, answers):
    reasons, rank = [], {'Normal': 0, 'High': 1, 'Urgent': 2}
    priority = 'Normal'
    for rule in workflow.urgency_rules:
        value = answers.get(rule.field)
        if isinstance(value, dict):
            value = value.get('value', value.get('text', ''))
        matched = False
        if value is not None:
            if rule.operator == 'equals':
                matched = str(value).casefold() == rule.value.casefold()
            elif rule.operator == 'contains':
                matched = rule.value.casefold() in str(value).casefold()
            else:
                try:
                    matched = float(value) < float(rule.value) if rule.operator == 'less_than' else float(value) > float(rule.value)
                except (ValueError, TypeError):
                    pass
        if matched:
            reasons.append(rule.reason)
            if rank[rule.priority] > rank[priority]:
                priority = rule.priority
    missing = [question.label for question in workflow.questions if question.required and answers.get(question.key) in (None, '', [])]
    return {'qualified': not missing, 'missing': missing, 'priority': priority,
            'reasons': reasons or (['All required intake questions are complete.'] if not missing else ['Required intake information is incomplete.'])}


def save(db, resource, trigger, user, payload):
    from app.apps.power_apps.runtime_models import AutomationEvent
    from app.apps.power_apps.runtime import scope_values
    from app.apps.power_apps.telegram_operations import member
    from app.access.service import background_scope
    from app.core.deps import RequirePermission
    current = configuration(trigger)
    if payload.revision != current.revision:
        raise HTTPException(409, 'Telegram experience changed. Reload before saving.')
    branch = trigger.config.get('branch_id')
    for agent in payload.routing_agents:
        if agent.branch_id != branch:
            raise HTTPException(422, 'Routing agents must use this bot’s branch')
    users = {agent.user_id for agent in payload.routing_agents} | set(payload.escalation_user_ids) | {ident for flow in payload.workflows for ident in flow.approval_user_ids}
    for ident in users:
        actor = member(db, ident, resource.organization_id)
        with background_scope(db, actor, 'power_apps', 'create', branch_id=branch):
            RequirePermission('power_apps_execute')(actor)
    for fact in payload.knowledge:
        if fact.approved and fact.expires_at <= now():
            raise HTTPException(422, f'Approved knowledge "{fact.title}" needs a future expiry')
    if payload.catalogue_product_ids:
        from app.apps.srm.industry_api import context
        from app.apps.srm.models import SRMProduct
        from app.apps.srm.services.commercial import record
        with background_scope(db, user, 'srm', 'view', branch_id=branch):
            context(db, user, appointments=True)
            for ident in payload.catalogue_product_ids:
                product = record(db, SRMProduct, ident, user)
                if not product.active:
                    raise HTTPException(422, 'Public catalogue requires active products')
    if payload.booking_services:
        from app.apps.srm.industry_api import context, get, PROVIDER_TYPES
        from app.apps.srm.models import SRMProduct
        from app.apps.srm.services.commercial import record
        with background_scope(db, user, 'srm', 'create', branch_id=branch):
            selected = context(db, user, True, appointments=True)
            for service in payload.booking_services:
                product = record(db, SRMProduct, service.service_id, user)
                if not product.active or product.product_type.lower() not in {'service', 'services'}:
                    raise HTTPException(422, 'Booking requires an active service')
                resources = [get(db, user, selected, ident, 'resource', lock=False) for ident in service.resource_ids]
                if not any(item.data['resource_type'] in PROVIDER_TYPES for item in resources) or any(item.status != 'active' for item in resources):
                    raise HTTPException(422, 'Booking requires an active provider and active resources')
    revision = current.revision + 1
    values = payload.model_dump(mode='json')
    for fact in values['knowledge']:
        fact['approved_at'] = now().isoformat() if fact['approved'] else None
        fact['approved_by_user_id'] = user.id if fact['approved'] else None
    values['revision'] = revision
    trigger.config = {**trigger.config, 'experience': values}
    db.add(AutomationEvent(**scope_values(resource), resource_id=resource.id, kind='telegram_experience_published',
        details={'revision': revision, 'actor_id': user.id, 'approved_fact_ids': [fact.id for fact in payload.knowledge if fact.approved], 'workflow_ids': [flow.id for flow in payload.workflows]}))
    db.flush()
    return values
