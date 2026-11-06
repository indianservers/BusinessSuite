"""Shared CRM/Sales service commitments, with transactional reminders and history."""
from datetime import datetime, timedelta, timezone
from typing import ClassVar, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, UniqueConstraint, Boolean, or_
from app.db.base_class import Base
from app.core.deps import get_db, get_current_user
from app.apps.srm.services.commercial import tenant, require, customer
from app.models.user import User

class FollowUp(Base):
    __tablename__ = 'service_follow_ups'
    __table_args__ = (UniqueConstraint('organization_id', 'source_key', name='uq_service_follow_source'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey('crm_companies.id'), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('srm_products.id'), index=True)
    order_id = Column(Integer, ForeignKey('srm_sales_orders.id'), index=True)
    order_line_id = Column(Integer, ForeignKey('srm_sales_order_lines.id'), index=True)
    lead_id = Column(Integer, ForeignKey('crm_leads.id'), index=True)
    contact_id = Column(Integer, ForeignKey('crm_contacts.id'), index=True)
    deal_id = Column(Integer, ForeignKey('crm_deals.id'), index=True)
    quotation_id = Column(Integer, ForeignKey('crm_quotations.id'), index=True)
    invoice_id = Column(Integer, ForeignKey('srm_invoices.id'), index=True)
    assigned_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    assigned_team_id = Column(Integer, ForeignKey('crm_teams.id'), index=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String(220), nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    timezone = Column(String(80), nullable=False, default='Asia/Kolkata')
    status = Column(String(30), nullable=False, default='Scheduled', index=True)
    priority = Column(String(20), nullable=False, default='Normal')
    source_key = Column(String(180))
    configuration = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class FollowUpActivity(Base):
    __tablename__ = 'service_follow_up_activities'
    id = Column(Integer, primary_key=True)
    follow_up_id = Column(Integer, ForeignKey('service_follow_ups.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey('users.id'))
    action = Column(String(80), nullable=False)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class FollowUpReminder(Base):
    __tablename__ = 'service_follow_up_reminders'
    __table_args__ = (UniqueConstraint('follow_up_id', 'schedule_key', name='uq_service_reminder_schedule'),)
    id = Column(Integer, primary_key=True)
    follow_up_id = Column(Integer, ForeignKey('service_follow_ups.id', ondelete='CASCADE'), nullable=False, index=True)
    schedule_key = Column(String(150), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    notification_id = Column(Integer, ForeignKey('notifications.id'))
    delivery_status = Column(String(30), nullable=False, default='pending')
    attempt_history = Column(JSON, nullable=False, default=list)
    next_attempt_at = Column(DateTime(timezone=True))

class Schedule(BaseModel):
    event_template: ClassVar[bool] = False
    required: bool = True
    type: Literal['days', 'date', 'recurring'] = 'days'
    reference: Literal['purchase', 'delivery', 'completion'] = 'purchase'
    reference_at: datetime | None = None
    interval_days: int = Field(default=45, ge=1, le=3650)
    due_at: datetime | None = None
    timezone: str = 'Asia/Kolkata'
    reminder_days: int = Field(default=2, ge=0, le=365)
    reminder_minutes: int | None = Field(default=None, ge=0, le=525600)
    assigned_team_id: int | None = Field(default=None, gt=0)
    assigned_user_id: int | None = Field(default=None, gt=0)
    priority: Literal['Low', 'Normal', 'High', 'Urgent'] = 'Normal'
    purpose: Literal['Feedback', 'Renewal', 'Maintenance', 'Payment', 'Upsell', 'General'] = 'General'
    contact_method: Literal['Call', 'WhatsApp', 'Email', 'Visit'] = 'Call'
    notes: str = Field(default='', max_length=10000)
    cancellation_policy: Literal['cancel', 'retain'] = 'cancel'

    @model_validator(mode='after')
    def valid(self):
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError('Unknown time zone')
        for value in (self.reference_at, self.due_at):
            if value is not None and value.utcoffset() is None:
                raise ValueError('Dates must include a time zone offset')
        if self.required and self.type == 'date' and (not self.due_at):
            raise ValueError('Choose a follow-up date')
        if not self.event_template and self.required and self.type != 'date' and (self.reference != 'purchase') and (not self.reference_at):
            raise ValueError('Provide the delivery/completion reference date')
        return self

class ScheduleTemplate(Schedule):
    # A catalog default refers to a future customer's transaction, not today.
    event_template: ClassVar[bool] = True

    @model_validator(mode='after')
    def relative_to_each_customer(self):
        if self.type != 'date':
            self.reference_at = None
        return self


class CreateFollowUp(Schedule):
    lead_id: int | None = Field(default=None, gt=0)
    contact_id: int | None = Field(default=None, gt=0)
    deal_id: int | None = Field(default=None, gt=0)
    quotation_id: int | None = Field(default=None, gt=0)
    invoice_id: int | None = Field(default=None, gt=0)
    customer_id: int = Field(gt=0)
    product_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=220)

class Change(BaseModel):
    action: Literal['reschedule', 'complete', 'cancel', 'comment', 'contact', 'assign', 'missed']
    due_at: datetime | None = None
    assigned_user_id: int | None = None
    notes: str = Field(min_length=1, max_length=10000)
router = APIRouter(prefix='/follow-ups', tags=['Shared follow-ups'])

def access(user, write=False, db=None):
    from app.module_registry import is_app_enabled
    from app.apps.business_os.services.module_service import is_module_enabled
    suffixes = ['manage', 'admin', 'activities_manage'] if write else ['view', 'manage', 'admin', 'activities_view', 'activities_manage']
    grants = getattr(user, '_suite_grants', None)
    modules = [module for module in ('crm', 'srm', 'project_management') if is_app_enabled(module) and (db is None or is_module_enabled(db, module, company_id=tenant(user))) and (user.is_superuser or grants is None or (grants.get(module) or {}).get('enabled'))]
    if not modules:
        raise HTTPException(403, 'CRM, Sales or PMS access is required')
    permissions = [f'{module}_{suffix}' for module in modules if module != 'project_management' for suffix in suffixes]
    if 'project_management' in modules:
        permissions += ['pms_manage_tasks', 'pms_manage_projects', 'pms_admin'] + ([] if write else ['pms_view'])
    require(user, *permissions)


def followup_customer(db, ident, user):
    """Reuse each module's customer scope; a PMS role is not CRM visibility."""
    from app.shared.master_data import owner
    from app.shared.record_360 import module_access
    for source in ('crm', 'srm', 'project_management'):
        try:
            module_access(db, user, source)
            return owner(db, user, 'company', ident, source)
        except HTTPException as exc:
            if exc.status_code not in (403, 404):
                raise
    raise HTTPException(404, 'Customer is unavailable in your scope')

def visible(db, user):
    from app.access.catalog import permission_names
    q = db.query(FollowUp).filter(FollowUp.organization_id == tenant(user))
    if not user.is_superuser and (not {'crm_admin', 'srm_admin'}.intersection(permission_names(user))):
        from app.apps.crm.models import CRMOwner
        teams = db.query(CRMOwner.team_id).filter(CRMOwner.user_id == user.id, CRMOwner.organization_id == tenant(user), CRMOwner.deleted_at.is_(None))
        q = q.filter(or_(FollowUp.assigned_user_id == user.id, FollowUp.created_by == user.id, FollowUp.assigned_team_id.in_(teams)))
    return q

def linked_product(db, user, ident):
    from app.apps.srm.models import SRMProduct
    from app.shared.catalog import restrict_workspaces
    p = restrict_workspaces(db.query(SRMProduct).filter(SRMProduct.id == ident, SRMProduct.organization_id == tenant(user), SRMProduct.deleted_at.is_(None)), SRMProduct, db, user).first()
    if not p:
        raise HTTPException(404, 'Catalogue item unavailable')
    return p

def assignee(db, user, ident):
    value = db.get(User, ident)
    if not ident:
        raise HTTPException(422, 'Choose an employee')
    if not value or not value.is_active or tenant(value) != tenant(user):
        raise HTTPException(422, 'Choose an active employee in your organization')
    return value

def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def effective(row, now=None):
    if row.status in ('Completed', 'Cancelled', 'Missed'):
        return row.status
    now = now or datetime.now(timezone.utc)
    if utc(row.due_at) < now:
        return 'Overdue'
    if utc(row.due_at).astimezone(ZoneInfo(row.timezone)).date() == now.astimezone(ZoneInfo(row.timezone)).date():
        return 'Due'
    return row.status

def status_expression(q):
    from sqlalchemy import case, and_
    now = datetime.now(timezone.utc)
    today_cases = []
    for zone, in q.with_entities(FollowUp.timezone).distinct().all():
        local = now.astimezone(ZoneInfo(zone))
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        today_cases.append((and_(FollowUp.timezone == zone, FollowUp.due_at >= start.astimezone(timezone.utc), FollowUp.due_at < (start + timedelta(days=1)).astimezone(timezone.utc)), 'Due'))
    return case((FollowUp.status.in_(['Completed', 'Cancelled', 'Missed']), FollowUp.status), (FollowUp.due_at < now, 'Overdue'), *today_cases, else_=FollowUp.status)

def audit(db, row, user, action, details):
    db.add(FollowUpActivity(follow_up_id=row.id, actor_id=user.id if user else None, action=action, details=details))
    db.flush()

def output(db, row):
    from app.apps.crm.models import CRMCompany
    c = db.get(CRMCompany, row.customer_id)
    u = db.get(User, row.assigned_user_id)
    last_contact = db.query(FollowUpActivity).filter_by(follow_up_id=row.id, action='contact').order_by(FollowUpActivity.created_at.desc()).first()
    return dict(last_contact=utc(last_contact.created_at).isoformat() if last_contact else None, links={field: getattr(row, field) for field in ('lead_id', 'contact_id', 'deal_id', 'quotation_id', 'invoice_id')}, id=row.id, customer_id=row.customer_id, customer_name=c.name if c else '', phone=getattr(c, 'phone', None), title=row.title, product_id=row.product_id, order_id=row.order_id, assigned_user_id=row.assigned_user_id, assigned_team_id=row.assigned_team_id, assigned_to=u.email if u else '', due_at=utc(row.due_at).isoformat(), timezone=row.timezone, status=effective(row), priority=row.priority, configuration=row.configuration)

def create(db, user, data, order_id=None, source_key=None):
    if not data.required:
        raise HTTPException(422, 'Enable follow-up scheduling')
    if not data.title.strip():
        raise HTTPException(422, 'Enter a title')
    followup_customer(db, data.customer_id, user)
    from app.apps.crm.api.router import _get_resource, _assert_record_visible, _assert_entity_permission
    for field, entity in [('lead_id', 'leads'), ('contact_id', 'contacts'), ('deal_id', 'deals'), ('quotation_id', 'quotations')]:
        ident = getattr(data, field)
        if ident:
            _assert_entity_permission(entity, user, 'view')
            _assert_record_visible(db, _get_resource(entity), ident, tenant(user), user)
    if data.invoice_id:
        require(user, 'srm_view', 'srm_invoice_view', 'srm_manage', 'srm_admin')
        from app.apps.srm.models import SRMInvoice
        from app.apps.srm.services.commercial import record
        linked = record(db, SRMInvoice, data.invoice_id, user)
        if linked.customer_id != data.customer_id:
            raise HTTPException(422, 'Invoice belongs to another customer')
    if data.product_id:
        linked_product(db, user, data.product_id)
    if data.assigned_team_id:
        from app.apps.crm.models import CRMTeam
        team = db.query(CRMTeam).filter_by(id=data.assigned_team_id, organization_id=tenant(user), status='Active').first()
        if not team or team.deleted_at:
            raise HTTPException(422, 'Choose an active team in your organization')
    assigned = data.assigned_user_id or user.id
    assignee(db, user, assigned)
    if source_key:
        existing = db.query(FollowUp).filter_by(organization_id=tenant(user), source_key=source_key).first()
        if existing:
            return existing
    reference = data.reference_at or datetime.now(timezone.utc)
    due = data.due_at if data.type == 'date' else (reference.astimezone(ZoneInfo(data.timezone)) + timedelta(days=data.interval_days)).astimezone(timezone.utc)
    row = FollowUp(organization_id=tenant(user), customer_id=data.customer_id, product_id=data.product_id, order_id=order_id, assigned_user_id=assigned, assigned_team_id=data.assigned_team_id, created_by=user.id, title=data.title.strip(), due_at=due, timezone=data.timezone, priority=data.priority, source_key=source_key, configuration=data.model_dump(mode='json'))
    for field in ('lead_id', 'contact_id', 'deal_id', 'quotation_id', 'invoice_id'):
        setattr(row, field, getattr(data, field))
    db.add(row)
    db.flush()
    audit(db, row, user, 'created', {'due_at': due.isoformat()})
    return row

@router.get('')
def directory(search: str='', status: str='', assigned_user_id: int | None=None, customer_id: int | None=None, page: int=Query(1, ge=1), per_page: int=Query(50, ge=1, le=200), db=Depends(get_db), user=Depends(get_current_user)):
    access(user, db=db)
    q = visible(db, user)
    if customer_id:
        q = q.filter(FollowUp.customer_id == customer_id)
    if assigned_user_id:
        q = q.filter(FollowUp.assigned_user_id == assigned_user_id)
    if search:
        q = q.filter(FollowUp.title.ilike('%' + search + '%'))
    if status:
        q = q.filter(status_expression(q) == status)
    total = q.count()
    rows = q.order_by(FollowUp.due_at, FollowUp.id).offset((page - 1) * per_page).limit(per_page).all()
    return {'items': [output(db, r) for r in rows], 'total': total, 'page': page, 'per_page': per_page}

@router.get('/statistics')
def statistics(db=Depends(get_db), user=Depends(get_current_user)):
    access(user, db=db)
    rows = visible(db, user).all()
    now = datetime.now(timezone.utc)
    counts = {s: sum((effective(r, now) == s for r in rows)) for s in ['Due', 'Overdue', 'Completed', 'Rescheduled', 'Missed']}
    return {'Total': len(rows), **counts, 'Upcoming 7 Days': sum((now <= utc(r.due_at) <= now + timedelta(days=7) and r.status not in ('Completed', 'Cancelled', 'Missed') for r in rows)), 'Conversion Rate': round(100 * counts['Completed'] / len(rows), 1) if rows else 0}

@router.get('/options')
def options(db=Depends(get_db), user=Depends(get_current_user)):
    access(user, db=db)
    from app.apps.crm.models import CRMCompany
    from app.shared.master_data import companies
    from app.shared.record_360 import module_access
    candidate_ids = db.query(CRMCompany.id).filter(CRMCompany.organization_id == tenant(user),CRMCompany.deleted_at.is_(None)).limit(5000)
    customers_by_id = {}
    for source in ('crm','srm','project_management'):
        try:
            module_access(db,user,source)
            for identity,name in companies(db,user,source).filter(CRMCompany.id.in_(candidate_ids)).with_entities(CRMCompany.id,CRMCompany.name):
                customers_by_id[identity]={'id':identity,'name':name}
        except HTTPException as error:
            if error.status_code not in (403,404):raise
    customers = [customers_by_id[identity] for identity in sorted(customers_by_id)]
    from sqlalchemy.orm import joinedload
    from app.models.employee import Employee
    users = [{'id': u.id, 'name': u.email} for u in db.query(User).options(joinedload(User.person),joinedload(User.employee).joinedload(Employee.branch)).filter(User.is_active.is_(True)).all() if tenant(u) == tenant(user)]
    from app.apps.crm.models import CRMTeam
    teams = [{'id': t.id, 'name': t.name} for t in db.query(CRMTeam).filter_by(organization_id=tenant(user), status='Active', deleted_at=None).all()]
    return {'customers': customers, 'employees': users, 'teams': teams}

@router.post('', status_code=201)
def add(data: CreateFollowUp, db=Depends(get_db), user=Depends(get_current_user)):
    access(user, True, db)
    row = create(db, user, data)
    db.commit()
    return output(db, row)

@router.get('/{ident}')
def detail(ident: int, db=Depends(get_db), user=Depends(get_current_user)):
    access(user, db=db)
    row = visible(db, user).filter(FollowUp.id == ident).first()
    if not row:
        raise HTTPException(404, 'Follow-up not found')
    events = db.query(FollowUpActivity).filter_by(follow_up_id=ident).order_by(FollowUpActivity.id.desc()).all()
    return {**output(db, row), 'activities': [{'id': a.id, 'actor_id': a.actor_id, 'actor_name': db.get(User, a.actor_id).email if a.actor_id and db.get(User, a.actor_id) else 'System', 'action': a.action, 'details': a.details, 'created_at': utc(a.created_at).isoformat()} for a in events]}

@router.post('/{ident}/actions')
def change(ident: int, data: Change, db=Depends(get_db), user=Depends(get_current_user)):
    access(user, True, db)
    row = visible(db, user).filter(FollowUp.id == ident).with_for_update().first()
    if not row:
        raise HTTPException(404, 'Follow-up not found')
    before = utc(row.due_at).isoformat()
    if data.action != 'comment' and row.status in ('Completed', 'Cancelled'):
        raise HTTPException(409, 'Follow-up is closed')
    if data.action == 'reschedule':
        if not data.due_at or data.due_at.utcoffset() is None:
            raise HTTPException(422, 'Provide a timezone-aware date')
        row.due_at = data.due_at
        row.status = 'Rescheduled'
    elif data.action == 'assign':
        assignee(db, user, data.assigned_user_id)
        row.assigned_user_id = data.assigned_user_id
    elif data.action == 'complete':
        row.status = 'Completed'
        if row.configuration.get('type') == 'recurring':
            config = {**row.configuration, 'reference_at': utc(row.due_at).isoformat(), 'type': 'recurring', 'assigned_user_id': row.assigned_user_id}
            next_row = create(db, user, CreateFollowUp(**{**config, 'title': row.title, 'customer_id': row.customer_id, 'product_id': row.product_id}), row.order_id, f'recurrence:{row.id}')
            next_row.order_line_id = row.order_line_id
    elif data.action == 'cancel':
        row.status = 'Cancelled'
    elif data.action == 'missed':
        row.status = 'Missed'
    audit(db, row, user, data.action, {'original_due_at': before, 'due_at': utc(row.due_at).isoformat(), 'notes': data.notes, 'assigned_user_id': row.assigned_user_id})
    db.commit()
    return output(db, row)

def create_for_order(db, order, user, event=None):
    is_pos = (order.metadata_json or {}).get('source') == 'pos'
    if order.status == 'cancelled':
        return
    if not is_pos and event is None and order.status not in ('confirmed', 'closed'):
        return
    event = event or ('delivery' if order.status == 'closed' else 'purchase')
    happened_at = datetime.now(timezone.utc)
    for line in order.lines:
        if not line.product_id:
            continue
        p = linked_product(db, user, line.product_id)
        config = (line.metadata_json or {}).get('follow_up', (p.metadata_json or {}).get('follow_up'))
        if not config or not config.get('required'):
            continue
        reference = config.get('reference', 'purchase')
        # POS completes the purchase/service at checkout. Other sales wait for
        # confirmation, delivery (order closure), or service completion.
        if not is_pos and not config.get('reference_at') and config.get('type') != 'date':
            if reference != 'purchase' and reference != event:
                continue
        if not order.customer_id:
            raise HTTPException(422, 'Select a registered customer to schedule product or service follow-ups')
        values = {**config, 'title': f"{p.item_name} · {config.get('purpose', 'General')}", 'customer_id': order.customer_id, 'product_id': p.id}
        if not values.get('reference_at') and values.get('type') != 'date':
            values['reference_at'] = happened_at
        data = CreateFollowUp(**values)
        row = create(db, user, data, order.id, f'order:{order.id}:line:{line.id}')
        row.order_line_id = line.id


def create_for_engagement(db, engagement, user):
    if engagement.status not in ('completed', 'closed') or not engagement.sales_order_id:
        return
    from app.apps.srm.models import SRMSalesOrder
    from app.apps.srm.services.commercial import record
    order = record(db, SRMSalesOrder, engagement.sales_order_id, user)
    create_for_order(db, order, user, event='completion')


def cancel_for_order(db, order_id, user):
    for row in db.query(FollowUp).filter_by(organization_id=tenant(user), order_id=order_id).with_for_update().all():
        if row.status not in ('Completed', 'Cancelled') and row.configuration.get('cancellation_policy', 'cancel') == 'cancel':
            row.status = 'Cancelled'
            audit(db, row, user, 'source_cancelled', {'order_id': order_id})

def dispatch(db):
    from app.models.notification import Notification, NotificationDeliveryLog
    from app.apps.crm.models import CRMQuotation
    from app.apps.srm.models import SRMInvoice
    from app.apps.srm.services.collections import reminder_block_reason
    from sqlalchemy import tuple_
    now = datetime.now(timezone.utc)
    rows = db.query(FollowUp).filter(FollowUp.status.in_(['Scheduled', 'Rescheduled'])).with_for_update(skip_locked=True).all()

    def linked_sources(model, field):
        keys = list({(getattr(row, field), row.organization_id) for row in rows if getattr(row, field)})
        result = {}
        for start in range(0, len(keys), 400):
            for obj in db.query(model).filter(tuple_(model.id, model.organization_id).in_(keys[start:start+400])):
                result[(obj.id, obj.organization_id)] = obj
        return result

    quotations = linked_sources(CRMQuotation, 'quotation_id')
    invoices = linked_sources(SRMInvoice, 'invoice_id')
    for row in rows:
        if row.quotation_id:
            quote = quotations.get((row.quotation_id, row.organization_id))
            if not quote or str(quote.status or '').lower() in {'accepted', 'rejected', 'declined', 'cancelled', 'superseded', 'expired'}:
                continue
        if row.invoice_id:
            invoice = invoices.get((row.invoice_id, row.organization_id))
            if not invoice or reminder_block_reason(invoice, now):
                continue
        due = utc(row.due_at)
        lead = row.configuration.get('reminder_minutes')
        lead = lead if lead is not None else row.configuration.get('reminder_days', 2) * 1440
        if now < due - timedelta(minutes=lead):
            continue
        phase = 'overdue' if now > due else 'reminder'
        preference = db.query(FollowUpPreference).filter_by(organization_id=row.organization_id, user_id=row.assigned_user_id).first()
        if preference and (not preference.in_app or (phase == 'overdue' and (not preference.overdue))):
            continue
        key = f'{due.isoformat()}:{row.assigned_user_id}:{phase}'
        receipt = db.query(FollowUpReminder).filter_by(follow_up_id=row.id, schedule_key=key).first()
        if receipt and (receipt.delivery_status == 'delivered' or (receipt.next_attempt_at and utc(receipt.next_attempt_at) > now)):
            continue
        if receipt is None:
            receipt = FollowUpReminder(follow_up_id=row.id, schedule_key=key, delivery_status='pending', attempt_history=[])
            db.add(receipt)
            db.flush()
        try:
            with db.begin_nested():
                notification = Notification(company_id=row.organization_id, user_id=row.assigned_user_id, title=f'Follow-up {phase}: {row.title}', message=f"Due {due.isoformat()} · {row.configuration.get('notes', '')}", module='crm', event_type='service_follow_up', related_entity_type='follow_up', related_entity_id=row.id, action_url=f'/crm/follow-ups/{row.id}', priority=row.priority.lower(), channels=['in_app'])
                db.add(notification)
                db.flush()
                db.add(NotificationDeliveryLog(notification_id=notification.id, channel='in_app', status='delivered', delivered_at=now))
                db.flush()
            receipt.notification_id = notification.id
            receipt.delivery_status = 'delivered'
            receipt.sent_at = now
            receipt.next_attempt_at = None
            receipt.attempt_history = [*(receipt.attempt_history or []), {'at': now.isoformat(), 'status': 'delivered'}]
        except Exception as error:
            attempts = len(receipt.attempt_history or []) + 1
            receipt.delivery_status = 'retry'
            receipt.next_attempt_at = now + timedelta(minutes=min(60, 2 ** min(attempts, 6)))
            receipt.attempt_history = [*(receipt.attempt_history or []), {'at': now.isoformat(), 'status': 'failed', 'error': type(error).__name__}]
    db.commit()

def start_worker():
    import threading, logging
    stop = threading.Event()

    def loop():
        from app.db.session import SessionLocal
        from app.db.tenant import run_for_company_databases
        def tick():
            with SessionLocal() as db:
                dispatch(db)
                from app.module_registry import is_app_enabled
                if is_app_enabled('crm'):
                    from app.apps.crm.growth import dispatch_relationship_reminders
                    dispatch_relationship_reminders(db)
        while not stop.is_set():
            try:
                run_for_company_databases(tick)
            except Exception:
                logging.getLogger(__name__).exception('Follow-up reminder dispatch failed; retrying next minute')
            stop.wait(60)
    worker = threading.Thread(target=loop, daemon=True, name='follow-up-reminders')
    worker.start()
    return (stop, worker)

@router.get('/grid/query')
def grid_query(state: str=Query('{}', max_length=16000), db=Depends(get_db), user=Depends(get_current_user)):
    from app.shared.data_grid import parse_query, GridField, apply_filters, apply_path, apply_sort, field_for
    from app.apps.crm.models import CRMCompany
    from sqlalchemy import case, and_, func
    access(user, db=db)
    parsed = parse_query(state)
    q = visible(db, user).join(CRMCompany, CRMCompany.id == FollowUp.customer_id).join(User, User.id == FollowUp.assigned_user_id)
    status = status_expression(q)
    fields = {name: GridField(expr, kind) for name, expr, kind in [('id', FollowUp.id, 'id'), ('customer_name', CRMCompany.name, 'text'), ('title', FollowUp.title, 'text'), ('due_at', FollowUp.due_at, 'datetime'), ('assigned_to', User.email, 'text'), ('assigned_user_id', FollowUp.assigned_user_id, 'id'), ('priority', FollowUp.priority, 'text'), ('status', status, 'text'), ('customer_id', FollowUp.customer_id, 'id'), ('order_id', FollowUp.order_id, 'id')]}
    q = apply_filters(q, parsed, fields)
    if parsed.search:
        text = '%' + parsed.search + '%'
        q = q.filter(or_(CRMCompany.name.ilike(text), FollowUp.title.ilike(text), User.email.ilike(text)))
    total = q.count()
    branch = apply_path(q, parsed, fields)
    result = {'total': total, 'page': parsed.page, 'pageSize': parsed.pageSize, 'rows': [], 'groups': [], 'permissions': {'export': True}}
    if len(parsed.path) < len(parsed.grouping):
        name = parsed.grouping[len(parsed.path)]
        field = field_for(fields, name)
        if not field.groupable:
            raise HTTPException(422, 'This column cannot be grouped')
        column = field.expression
        groups = branch.with_entities(column, func.count(FollowUp.id)).group_by(column)
        result['pageTotal'] = groups.count()
        for key, count in groups.order_by(column).offset((parsed.page - 1) * parsed.pageSize).limit(parsed.pageSize).all():
            value = key.isoformat() if isinstance(key, datetime) else key
            result['groups'].append({'field': name, 'value': value, 'label': str(value or 'Not set'), 'count': count, 'aggregates': [], 'path': [p.model_dump() for p in parsed.path] + [{'field': name, 'value': value}]})
    else:
        result['pageTotal'] = branch.count()
        result['rows'] = [output(db, row) for row in apply_sort(branch, parsed, fields, FollowUp.id).offset((parsed.page - 1) * parsed.pageSize).limit(parsed.pageSize).all()]
    return result

class FollowUpAttachment(Base):
    __tablename__ = 'service_follow_up_attachments'
    id = Column(Integer, primary_key=True)
    follow_up_id = Column(Integer, ForeignKey('service_follow_ups.id'), nullable=False, index=True)
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    original_name = Column(String(240), nullable=False)
    storage_path = Column(String(1000), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class FollowUpPreference(Base):
    __tablename__ = 'service_follow_up_preferences'
    __table_args__ = (UniqueConstraint('organization_id', 'user_id', name='uq_service_follow_preference'),)
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    in_app = Column(Boolean, nullable=False, default=True)
    overdue = Column(Boolean, nullable=False, default=True)

class Preferences(BaseModel):
    in_app: bool = True
    overdue: bool = True

@router.get('/preferences/me')
def preferences(db=Depends(get_db), user=Depends(get_current_user)):
    access(user, db=db)
    row = db.query(FollowUpPreference).filter_by(organization_id=tenant(user), user_id=user.id).first()
    return {'in_app': row.in_app if row else True, 'overdue': row.overdue if row else True}

@router.put('/preferences/me')
def save_preferences(data: Preferences, db=Depends(get_db), user=Depends(get_current_user)):
    access(user, db=db)
    row = db.query(FollowUpPreference).filter_by(organization_id=tenant(user), user_id=user.id).first()
    if row is None:
        row = FollowUpPreference(organization_id=tenant(user), user_id=user.id)
        db.add(row)
    row.in_app = data.in_app
    row.overdue = data.overdue
    db.commit()
    return data

@router.get('/{ident}/attachments')
def attachments(ident: int, db=Depends(get_db), user=Depends(get_current_user)):
    detail(ident, db, user)
    return [{'id': a.id, 'name': a.original_name, 'created_at': utc(a.created_at).isoformat()} for a in db.query(FollowUpAttachment).filter_by(follow_up_id=ident).all()]

@router.post('/{ident}/attachments', status_code=201)
def attach(ident: int, file: UploadFile=File(...), db=Depends(get_db), user=Depends(get_current_user)):
    from pathlib import Path
    from uuid import uuid4
    from app.core.config import settings
    from app.core.storage import persist_file
    from app.apps.project_management.api.router import _validate_attachment_upload, _safe_attachment_name, PMS_MAX_ATTACHMENT_BYTES
    access(user, True, db)
    row = visible(db, user).filter_by(id=ident).first()
    if not row:
        raise HTTPException(404, 'Follow-up not found')
    _validate_attachment_upload(file)
    name = _safe_attachment_name(file.filename)
    root = Path(settings.UPLOAD_DIR).resolve() / 'follow-ups' / str(tenant(user))
    root.mkdir(parents=True, exist_ok=True)
    path = root / f'{uuid4().hex}_{name}'
    try:
        size = 0
        with path.open('wb') as output_file:
            while (chunk := file.file.read(1024 * 1024)):
                size += len(chunk)
                if size > PMS_MAX_ATTACHMENT_BYTES:
                    raise HTTPException(413, 'Attachment is too large')
                output_file.write(chunk)
        if size == 0:
            raise HTTPException(422, 'Empty attachments are not allowed')
        persist_file(str(path))
        asset = FollowUpAttachment(follow_up_id=ident, uploaded_by=user.id, original_name=name, storage_path=str(path))
        db.add(asset)
        db.flush()
        audit(db, row, user, 'attachment_added', {'attachment_id': asset.id, 'name': name})
        db.commit()
        return {'id': asset.id, 'name': name}
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

@router.get('/{ident}/attachments/{attachment_id}')
def download_attachment(ident: int, attachment_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    from pathlib import Path
    from app.core.config import settings
    from app.core.storage import FileResponse, upload_exists
    detail(ident, db, user)
    item = db.query(FollowUpAttachment).filter_by(id=attachment_id, follow_up_id=ident).first()
    if not item:
        raise HTTPException(404, 'Attachment not found')
    path = Path(item.storage_path).resolve()
    root = Path(settings.UPLOAD_DIR).resolve() / 'follow-ups' / str(tenant(user))
    if not path.is_relative_to(root) or not upload_exists(str(path)):
        raise HTTPException(404, 'Attachment unavailable')
    return FileResponse(str(path), filename=item.original_name)

@router.get('/link-options/{entity}')
def link_options(entity: str, search: str='', db=Depends(get_db), user=Depends(get_current_user)):
    access(user, db=db)
    if entity not in {'leads', 'contacts', 'deals', 'quotations'}:
        raise HTTPException(422, 'Unsupported record type')
    from app.apps.crm.productivity import rows
    from app.apps.crm.api.router import _get_resource
    q = rows(db, user, entity)
    model = _get_resource(entity).model
    candidates = [getattr(model, k) for k in ('name', 'full_name', 'quote_number') if hasattr(model, k)]
    if search and candidates:
        q = q.filter(or_(*[c.ilike('%' + search + '%') for c in candidates]))
    records = q.order_by(model.id.desc()).limit(100).all()
    return [{'id': r.id, 'name': next((getattr(r, k) for k in ('name', 'full_name', 'quote_number') if getattr(r, k, None)), f'#{r.id}')} for r in records]
