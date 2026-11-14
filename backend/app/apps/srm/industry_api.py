"""Salon and construction operations using canonical CRM, PMS and Sales records."""
from datetime import datetime, date, time, timezone, timedelta
from decimal import Decimal
from uuid import UUID
from typing import Literal
from zoneinfo import ZoneInfo
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.company import Branch
from app.apps.srm.industry_models import IndustryRecord as Record
from app.apps.srm.services.commercial import tenant, require, customer, record, lock_tenant, money, invoice_for
from app.apps.project_management.access import get_project_for_action

router = APIRouter(prefix="/srm/industry", tags=["Salon and construction operations"])
KINDS = {"resource", "appointment", "boq", "measurement", "site_diary", "variation", "subcontract", "material_issue"}
CONSTRUCTION = {"boq", "measurement", "site_diary", "variation", "subcontract", "material_issue"}


def fail(message, code=422):
    raise HTTPException(code, message)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BaseInput(Strict):
    request_id: UUID
    title: str = Field(min_length=1, max_length=220)


class ResourceInput(BaseInput):
    resource_type: Literal["stylist", "chair", "room"]
    user_id: int | None = Field(None, gt=0)
    timezone: str = "Asia/Kolkata"
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5], min_length=1, max_length=7)
    opens: time = time(9)
    closes: time = time(19)

    @model_validator(mode="after")
    def valid(self):
        try:
            ZoneInfo(self.timezone)
        except Exception:
            raise ValueError("Choose a valid timezone")
        if self.opens.utcoffset() is not None or self.closes.utcoffset() is not None:
            raise ValueError('Opening hours must be local times without timezone offsets')
        if any(d not in range(7) for d in self.weekdays) or len(set(self.weekdays)) != len(self.weekdays) or self.closes <= self.opens:
            raise ValueError("Choose valid opening days and hours")
        return self


class AppointmentInput(BaseInput):
    customer_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    resource_ids: list[int] = Field(min_length=1, max_length=10)
    starts_at: datetime
    duration_minutes: int = Field(ge=5, le=720)
    project_id: int | None = Field(None, gt=0)
    create_pms_task: bool = False
    deal_id: int | None = Field(None, gt=0)
    walk_in: bool = False
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode='after')
    def project_for_task(self):
        if self.create_pms_task and not self.project_id:
            raise ValueError('Select a PMS project for the linked delivery task')
        return self

    @field_validator("starts_at")
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError("Appointment time needs a timezone offset")
        return value.astimezone(timezone.utc)


class Reschedule(Strict):
    expected_revision: int = Field(ge=1)
    starts_at: datetime
    duration_minutes: int = Field(ge=5, le=720)
    resource_ids: list[int] = Field(min_length=1, max_length=10)

    _aware = field_validator("starts_at")(AppointmentInput.aware.__func__)


class Transition(Strict):
    expected_revision: int = Field(ge=1)
    status: Literal["checked_in", "in_service", "completed", "cancelled", "no_show", "approved", "rejected"]
    reason: str = Field(default="", max_length=2000)


class BOQInput(BaseInput):
    project_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=60)
    unit: str = Field(min_length=1, max_length=30)
    quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=4)
    unit_rate: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    tax_rate: Decimal = Field(default=0, ge=0, le=100, max_digits=5, decimal_places=2)
    variation_of: int | None = Field(None, gt=0)


class MeasurementInput(BaseInput):
    boq_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=4)
    measured_on: date
    notes: str = Field(default="", max_length=4000)


class DiaryInput(BaseInput):
    project_id: int = Field(gt=0)
    entry_date: date
    work_done: str = Field(min_length=1, max_length=10000)
    workforce: int = Field(default=0, ge=0, le=100000)
    weather: str = Field(default="", max_length=200)
    blockers: str = Field(default="", max_length=4000)
    file_ids: list[int] = Field(default_factory=list, max_length=50)


class SubcontractInput(BaseInput):
    project_id: int = Field(gt=0)
    vendor_id: int = Field(gt=0)
    scope: str = Field(min_length=1, max_length=10000)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    due_date: date


class InvoiceInput(Strict):
    expected_revision: int = Field(ge=1)
    retention_percent: Decimal = Field(default=0, ge=0, le=100, max_digits=5, decimal_places=2)


class MaterialInput(BaseInput):
    project_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    issue_date: date
    notes: str = Field(default='', max_length=4000)


def context(db, user, write=False, finance=False):
    names = ('srm_invoice_create', 'srm_admin') if finance else (('srm_manage', 'srm_admin') if write else ('srm_view', 'srm_manage', 'srm_admin', 'srm_invoice_view', 'srm_invoice_create'))
    require(user, *names)
    from app.module_registry import is_app_enabled
    from app.apps.business_os.services.module_service import assert_module_enabled
    if not all(is_app_enabled(k) for k in ("crm", "srm", "project_management")):
        fail("Enable CRM, PMS and Sales for industry operations", 409)
    assert_module_enabled(db, 'srm', company_id=tenant(user))
    ctx = db.info.get("branch_context")
    branch_id = getattr(ctx, "branch_id", None)
    if not branch_id:
        fail("Select one branch to use industry operations", 409)
    branch = db.query(Branch).filter_by(id=branch_id, company_id=tenant(user), is_active=True).first()
    if not branch:
        fail("Active branch not found", 404)
    if write:
        lock_tenant(db, user)
    return branch_id


@router.get('/capabilities')
def capabilities(project_id: int | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.srm.access import has_any_permission
    from app.apps.project_management.access import can_access_project
    context(db, user)
    manage = has_any_permission(user, {'srm_manage', 'srm_admin'})
    approve = False
    if project_id:
        p = get_project_for_action(db, project_id, user)
        approve = manage and can_access_project(db, p, user, 'approve')
    return {'manage': manage, 'approve': approve, 'self_approve': bool(user.is_superuser), 'invoice': has_any_permission(user, {'srm_invoice_create', 'srm_admin'})}


def query(db, user, branch_id):
    return db.query(Record).filter_by(organization_id=tenant(user), branch_id=branch_id)


def get(db, user, branch_id, ident, kind=None):
    row = query(db, user, branch_id).filter_by(id=ident).with_for_update().first()
    if not row or (kind and row.kind != kind):
        fail("Industry record not found", 404)
    if row.project_id:
        get_project_for_action(db, row.project_id, user)
    return row


def out(row):
    result = {k: getattr(row, k) for k in ("id", "kind", "title", "status", "revision", "customer_id", "project_id", "parent_id", "invoice_id", "stock_movement_id", "data", "created_at", "created_by", "approved_by")}
    result['data'] = {k: v for k, v in row.data.items() if not k.startswith('_')}
    return result


def audit(db, user, row, action):
    from app.apps.srm.api.router import _audit
    _audit(db, user, "industry_" + row.kind, row.id, action, after={"revision": row.revision, "status": row.status, "data": row.data})


def existing(db, user, branch_id, payload, kind):
    row = query(db, user, branch_id).filter_by(request_id=str(payload.request_id)).first()
    if row and (row.kind != kind or row.branch_id != branch_id):
        fail("Request ID already belongs to another operation", 409)
    if row:
        if row.data.get('_request_digest') != digest(payload):
            fail("Request ID was already used with different details", 409)
        return get(db, user, branch_id, row.id, kind)


def digest(payload):
    return hashlib.sha256(json.dumps(payload.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()


def create(db, user, branch, kind, payload, **links):
    row = Record(organization_id=tenant(user), branch_id=branch, kind=kind, title=payload.title,
                 request_id=str(payload.request_id), created_by=user.id, status="draft", revision=1,
                 data={**payload.model_dump(mode="json", exclude={"request_id", "title"}), '_request_digest': digest(payload)}, **links)
    db.add(row)
    db.flush()
    audit(db, user, row, "created")
    return row


def save(db, user, row, action):
    row.revision += 1
    audit(db, user, row, action)
    db.commit()
    return out(row)


def revision(row, expected):
    if row.revision != expected:
        fail("Record changed. Reload before continuing", 409)


def guard_billing_mode(db, user, source_type, *, project_id=None, sales_order=None, engagement=None):
    """An approved BOQ reserves project scope for measured-work billing.

    Generic order/time/milestone invoices must not bill the same contract again.
    Unrelated projects and manual invoices without project/order links are unaffected.
    """
    if source_type == 'industry_measurement':
        return
    from sqlalchemy import inspect
    # A rolling deployment can run native billing before the additive migration.
    # No industry records can exist without this table. Other DB failures propagate.
    if not inspect(db.connection()).has_table('srm_industry_records'):
        return
    from app.apps.srm.commercial_models import ProjectCommercial
    from sqlalchemy import or_
    ids = {project_id} if project_id else set()
    conditions = []
    if sales_order:
        conditions.append(ProjectCommercial.sales_order_id == sales_order.id)
    if engagement:
        conditions.append(ProjectCommercial.engagement_id == engagement.id)
        if engagement.pms_project_id:
            ids.add(engagement.pms_project_id)
    if conditions:
        ids.update(r.project_id for r in db.query(ProjectCommercial).filter(or_(*conditions)).all())
    if ids and db.query(Record.id).filter(Record.organization_id == tenant(user), Record.project_id.in_(ids), Record.kind.in_(['boq', 'variation']), Record.status == 'approved').first():
        fail('This project uses approved BOQ measurement billing. Bill certified measurements in Construction operations to avoid duplicate scope billing.', 409)


def require_clean_billing_start(db, user, project_id):
    from app.apps.srm.commercial_models import ProjectCommercial, InvoiceContext
    from app.apps.srm.models import SRMInvoice, SRMInvoiceDraft
    from sqlalchemy import or_, func
    from app.apps.srm.services.commercial import scoped
    ctx = db.get(ProjectCommercial, project_id)
    conditions = [InvoiceContext.project_id == project_id]
    if ctx and ctx.sales_order_id:
        conditions.append(SRMInvoice.sales_order_id == ctx.sales_order_id)
    if ctx and ctx.engagement_id:
        conditions.append(SRMInvoice.engagement_id == ctx.engagement_id)
    old = db.query(SRMInvoice.id).outerjoin(InvoiceContext, InvoiceContext.invoice_id == SRMInvoice.id).outerjoin(SRMInvoiceDraft, SRMInvoiceDraft.id == SRMInvoice.invoice_draft_id).filter(scoped(SRMInvoice.organization_id, user), func.coalesce(SRMInvoice.status, '') != 'cancelled', or_(*conditions), func.coalesce(SRMInvoiceDraft.source_type, '') != 'industry_measurement').first()
    if old:
        fail('This project already has other billing sources. Reconcile existing billing before approving BOQ measurement billing.', 409)


def project_currency(db, user, project_id):
    from app.apps.srm.commercial_models import ProjectCommercial
    from app.shared.settings import effective
    ctx = db.get(ProjectCommercial, project_id)
    return ctx.currency if ctx else effective(db, tenant(user), 'srm')['values']['currency']


@router.get("/records")
def records(kind: str, project_id: int | None = None, from_at: datetime | None = None, until_at: datetime | None = None, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user)
    if kind not in KINDS:
        fail("Unknown operation", 404)
    q = query(db, user, branch).filter_by(kind=kind)
    from app.apps.project_management.access import accessible_project_query
    from app.apps.project_management.models import PMSProject
    q = q.filter((Record.project_id.is_(None)) | Record.project_id.in_(accessible_project_query(db, user).with_entities(PMSProject.id)))
    if kind in CONSTRUCTION:
        if not project_id:
            fail("Select a project for construction operations")
        get_project_for_action(db, project_id, user)
    if project_id:
        q = q.filter_by(project_id=project_id)
    if from_at:
        q = q.filter(Record.ends_at > from_at)
    if until_at:
        q = q.filter(Record.starts_at < until_at)
    return {"items": [out(r) for r in q.order_by(Record.id.desc()).offset(offset).limit(limit).all()]}


@router.get('/project-options')
def project_options(search: str = Query('', max_length=180), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.project_management.access import accessible_project_query
    from app.apps.project_management.models import PMSProject
    context(db, user)
    q = accessible_project_query(db, user).filter(PMSProject.is_task_collection.is_(False), PMSProject.is_archived.is_(False))
    if search.strip():
        q = q.filter(PMSProject.name.ilike('%' + search.strip().replace('%', r'\%').replace('_', r'\_') + '%', escape='\\'))
    rows = q.order_by(PMSProject.name, PMSProject.id).offset(offset).limit(51).all()
    return {'items': [{'id': r.id, 'name': r.name} for r in rows[:50]], 'has_more': len(rows) > 50}


@router.post("/resources", status_code=201)
def resource(data: ResourceInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, True)
    prior = existing(db, user, branch, data, 'resource')
    if prior:
        return out(prior)
    if query(db, user, branch).filter_by(kind='resource', title=data.title).first():
        fail("A resource with this name already exists in this branch", 409)
    if data.user_id:
        from app.apps.project_management.access import organization_id_for
        staff = db.get(User, data.user_id)
        if not staff or not staff.is_active or organization_id_for(staff) != tenant(user):
            fail("Choose an active staff member from this company")
    row = create(db, user, branch, 'resource', data)
    row.status = 'active'
    db.commit()
    return out(row)


def available(db, user, branch, starts, minutes, resource_ids, ignore=None):
    if len(set(resource_ids)) != len(resource_ids):
        fail("Select each resource once")
    end = starts + timedelta(minutes=minutes)
    resources = [get(db, user, branch, i, 'resource') for i in resource_ids]
    if not any(r.data['resource_type'] == 'stylist' for r in resources):
        fail("Choose a stylist")
    for r in resources:
        local, local_end = starts.astimezone(ZoneInfo(r.data['timezone'])), end.astimezone(ZoneInfo(r.data['timezone']))
        if r.status != 'active' or local.weekday() not in r.data['weekdays'] or local.date() != local_end.date() or local.time().replace(tzinfo=None) < time.fromisoformat(r.data['opens']) or local_end.time().replace(tzinfo=None) > time.fromisoformat(r.data['closes']):
            fail(f"{r.title} is outside opening hours", 409)
    # Tenant writer lock serializes conflict check + insert, including distinct resources
    # that reference the same staff identity. Cancelled/no-show slots are released.
    staff_ids = {r.data.get('user_id') for r in resources} - {None}
    for booked in query(db, user, branch).filter(Record.kind == 'appointment', Record.status.in_(['booked', 'checked_in', 'in_service']), Record.starts_at < end, Record.ends_at > starts).all():
        if booked.id == ignore:
            continue
        old_start = datetime.fromisoformat(booked.data['starts_at'])
        old_end = old_start + timedelta(minutes=booked.data['duration_minutes'])
        if starts < old_end and old_start < end:
            old_resources = [get(db, user, branch, i, 'resource') for i in booked.data['resource_ids']]
            if set(resource_ids).intersection(booked.data['resource_ids']) or staff_ids.intersection({r.data.get('user_id') for r in old_resources}):
                fail("Stylist or resource is already booked at that time", 409)


@router.post("/appointments", status_code=201)
def appointment(data: AppointmentInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.srm.models import SRMProduct
    branch = context(db, user, True)
    prior = existing(db, user, branch, data, 'appointment')
    if prior:
        return out(prior)
    customer(db, data.customer_id, user)
    service = record(db, SRMProduct, data.service_id, user)
    if not service.active or service.product_type.lower() not in {'service', 'services'}:
        fail("Choose an active service from the shared catalog")
    if data.project_id:
        get_project_for_action(db, data.project_id, user, 'manage_tasks')
    if data.deal_id:
        from app.apps.crm.api.router import _assert_record_visible, _get_resource
        from app.apps.crm.models import CRMDeal
        _assert_record_visible(db, _get_resource('deals'), data.deal_id, tenant(user), user)
        deal = record(db, CRMDeal, data.deal_id, user)
        if deal.company_id != data.customer_id:
            fail("CRM deal must belong to the same customer")
    available(db, user, branch, data.starts_at, data.duration_minutes, data.resource_ids)
    row = create(db, user, branch, 'appointment', data, customer_id=data.customer_id, project_id=data.project_id)
    row.starts_at, row.ends_at = data.starts_at, data.starts_at + timedelta(minutes=data.duration_minutes)
    row.data = {**row.data, 'service_name': service.item_name, 'unit_price': str(service.sales_rate), 'tax_rate': str(service.gst_rate), 'currency': service.currency}
    row.status = 'booked'
    if data.create_pms_task:
        from app.apps.project_management.api.router import create_task_operation
        from app.apps.project_management.schemas import PMSTaskCreate
        stylist = next(get(db, user, branch, i, 'resource') for i in data.resource_ids if get(db, user, branch, i, 'resource').data['resource_type'] == 'stylist')
        day = data.starts_at.astimezone(ZoneInfo(stylist.data['timezone'])).date()
        task = create_task_operation(data.project_id, PMSTaskCreate(task_key=f'SALON-{row.id}', title=data.title, description=f'Salon appointment #{row.id}. Service: {service.item_name}. Manage booking, service and billing in /srm/salon.', start_date=day, due_date=day, estimated_hours=Decimal(data.duration_minutes)/60), db, user, commit=False)
        row.data = {**row.data, 'pms_task_id': task.id}
    db.commit()
    return out(row)


@router.put("/appointments/{ident}/schedule")
def reschedule(ident: int, data: Reschedule, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, True)
    row = get(db, user, branch, ident, 'appointment')
    revision(row, data.expected_revision)
    if row.status != 'booked':
        fail("Only booked appointments can be rescheduled", 409)
    available(db, user, branch, data.starts_at, data.duration_minutes, data.resource_ids, row.id)
    row.data = {**row.data, **data.model_dump(mode='json', exclude={'expected_revision'})}
    row.starts_at, row.ends_at = data.starts_at, data.starts_at + timedelta(minutes=data.duration_minutes)
    if row.data.get('pms_task_id'):
        from app.apps.project_management.api.router import update_task_operation
        from app.apps.project_management.schemas import PMSTaskUpdate
        local = data.starts_at.astimezone(ZoneInfo(get(db, user, branch, data.resource_ids[0], 'resource').data['timezone'])).date()
        update_task_operation(row.data['pms_task_id'], PMSTaskUpdate(start_date=local, due_date=local, estimated_hours=Decimal(data.duration_minutes)/60), db, user, commit=False)
    return save(db, user, row, 'rescheduled')


@router.post("/boq", status_code=201)
def boq(data: BOQInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, True)
    kind = 'variation' if data.variation_of else 'boq'
    prior = existing(db, user, branch, data, kind)
    if prior:
        return out(prior)
    get_project_for_action(db, data.project_id, user, 'manage_tasks')
    if data.variation_of:
        parent = get(db, user, branch, data.variation_of)
        if parent.kind not in {'boq', 'variation'} or parent.project_id != data.project_id or parent.status != 'approved':
            fail("Variation must reference an approved item in the same project")
    for item in query(db, user, branch).filter(Record.project_id == data.project_id, Record.kind.in_(['boq', 'variation'])).all():
        if item.data['code'].casefold() == data.code.casefold():
            fail("BOQ code already exists in this project", 409)
    row = create(db, user, branch, kind, data, project_id=data.project_id, parent_id=data.variation_of)
    row.data = {**row.data, 'currency': project_currency(db, user, data.project_id)}
    db.commit()
    return out(row)


@router.post("/measurements", status_code=201)
def measurement(data: MeasurementInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, True)
    prior = existing(db, user, branch, data, 'measurement')
    if prior:
        return out(prior)
    item = get(db, user, branch, data.boq_id)
    if item.kind not in {'boq', 'variation'} or item.status != 'approved':
        fail("Measure an approved BOQ item or variation")
    get_project_for_action(db, item.project_id, user, 'manage_tasks')
    row = create(db, user, branch, 'measurement', data, project_id=item.project_id, parent_id=item.id)
    row.data = {**row.data, 'unit': item.data['unit'], 'unit_rate': item.data['unit_rate'], 'tax_rate': item.data['tax_rate'], 'boq_code': item.data['code'], 'currency': item.data['currency']}
    db.commit()
    return out(row)


@router.post("/site-diaries", status_code=201)
def diary(data: DiaryInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.project_management.models import PMSFileAsset
    branch = context(db, user, True)
    prior = existing(db, user, branch, data, 'site_diary')
    if prior:
        return out(prior)
    get_project_for_action(db, data.project_id, user, 'manage_tasks')
    for ident in data.file_ids:
        asset = db.query(PMSFileAsset).filter_by(id=ident, project_id=data.project_id, deleted_at=None).first()
        if not asset:
            fail("Site photos must be uploaded to this project's Files first")
        if asset.visibility == 'Work Evidence' and asset.uploaded_by_user_id != user.id:
            fail('This project file is private to its uploader', 403)
    row = create(db, user, branch, 'site_diary', data, project_id=data.project_id)
    row.status = 'recorded'
    db.commit()
    return out(row)


@router.post("/subcontracts", status_code=201)
def subcontract(data: SubcontractInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, True)
    prior = existing(db, user, branch, data, 'subcontract')
    if prior:
        return out(prior)
    get_project_for_action(db, data.project_id, user, 'edit_project')
    vendor = customer(db, data.vendor_id, user)
    from app.shared.master_data import relationships
    vendor_roles = {r.lower() for r in relationships(db, vendor, 'company')} | {(vendor.account_type or '').lower()}
    if not vendor_roles.intersection({'vendor', 'supplier'}):
        fail("Choose a vendor from the shared company directory")
    row = create(db, user, branch, 'subcontract', data, project_id=data.project_id)
    row.data = {**row.data, 'currency': project_currency(db, user, data.project_id)}
    db.commit()
    return out(row)


@router.post('/material-issues', status_code=201)
def material_issue(data: MaterialInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.srm.api.router import _product_or_404, _warehouse_or_404, _post_stock_movement, _balance_for_update
    branch = context(db, user, True)
    prior = existing(db, user, branch, data, 'material_issue')
    if prior:
        return out(prior)
    get_project_for_action(db, data.project_id, user, 'manage_tasks')
    product = _product_or_404(db, tenant(user), data.product_id)
    warehouse = _warehouse_or_404(db, tenant(user), data.warehouse_id)
    if not product.active or not product.track_inventory:
        fail('Choose an active stock-tracked item')
    balance = _balance_for_update(db, tenant(user), product, warehouse.id, product.average_cost or Decimal(0))
    rate = balance.average_cost or product.average_cost or Decimal(0)
    if not rate or Decimal(rate) <= 0:
        fail('Record a valued stock receipt before issuing project materials')
    movement = _post_stock_movement(db, tenant(user), product, warehouse.id, 'project_consumption', Decimal(0), data.quantity, rate, data.issue_date, f'PMS-{data.project_id}', data.notes, user)
    row = create(db, user, branch, 'material_issue', data, project_id=data.project_id, stock_movement_id=movement.id)
    row.status = 'issued'
    row.data = {**row.data, 'product_name': product.item_name, 'warehouse_name': warehouse.warehouse_name, 'movement_number': movement.movement_number}
    audit(db, user, row, 'stock_issued')
    db.commit()
    return out(row)


@router.post("/records/{ident}/transition")
def transition(ident: int, data: Transition, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, True)
    row = get(db, user, branch, ident)
    revision(row, data.expected_revision)
    if row.kind == 'appointment':
        allowed = {'booked': {'checked_in', 'cancelled', 'no_show'}, 'checked_in': {'in_service', 'cancelled'}, 'in_service': {'completed'}}
        if data.status not in allowed.get(row.status, set()):
            fail("Invalid appointment transition", 409)
    elif row.kind in {'boq', 'variation', 'measurement', 'subcontract'}:
        get_project_for_action(db, row.project_id, user, 'approve')
        if row.status != 'draft' or data.status not in {'approved', 'rejected'}:
            fail("Only draft records can be approved or rejected", 409)
        if row.created_by == user.id and not user.is_superuser:
            fail("A different project approver must review this record", 403)
        if row.kind in {'boq', 'variation'} and data.status == 'approved':
            require_clean_billing_start(db, user, row.project_id)
        if row.kind == 'measurement' and data.status == 'approved':
            parent = get(db, user, branch, row.parent_id)
            approved = query(db, user, branch).filter_by(kind='measurement', parent_id=parent.id, status='approved').all()
            total = sum((Decimal(r.data['quantity']) for r in approved), Decimal(0)) + Decimal(row.data['quantity'])
            if total > Decimal(parent.data['quantity']):
                fail("Certified quantity exceeds approved BOQ; approve a variation first", 409)
        row.approved_by = user.id
    else:
        fail("This operation does not support transitions", 409)
    if data.status in {'cancelled', 'no_show', 'rejected'} and not data.reason:
        fail("Enter a reason")
    row.status = data.status
    row.data = {**row.data, 'transition_reason': data.reason}
    return save(db, user, row, data.status)


@router.post("/records/{ident}/invoice", status_code=201)
def invoice(ident: int, data: InvoiceInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.srm.api.router import _create_invoice_from_lines, _invoice_payload
    from app.apps.srm.commercial_models import InvoiceContext, ProjectCommercial
    require(user, 'srm_invoice_create', 'srm_admin')
    branch = context(db, user, True, finance=True)
    row = get(db, user, branch, ident)
    if row.invoice_id:
        return _invoice_payload(invoice_for(db, row.invoice_id, user), db)
    revision(row, data.expected_revision)
    if row.kind == 'appointment' and row.status == 'completed':
        if data.retention_percent:
            fail("Retention applies only to construction measurements")
        buyer, seller_id, currency = row.customer_id, tenant(user), row.data['currency']
        qty, rate, tax = Decimal(1), Decimal(row.data['unit_price']), Decimal(row.data['tax_rate'])
    elif row.kind == 'measurement' and row.status == 'approved':
        ctx = db.get(ProjectCommercial, row.project_id)
        if not ctx:
            fail("Link the shared customer and seller in PMS Project Billing first")
        buyer, seller_id, currency = ctx.customer_id, ctx.seller_id, ctx.currency
        if row.data['currency'] != currency:
            fail('Project currency changed after scope approval; reconcile the approved BOQ before billing', 409)
        qty, rate, tax = Decimal(row.data['quantity']), Decimal(row.data['unit_rate']), Decimal(row.data['tax_rate'])
    else:
        fail("Complete the appointment or approve the measurement before invoicing", 409)
    from app.apps.srm.services.commercial import seller
    customer(db, buyer, user)
    seller(db, seller_id, user)
    gross = money(qty * rate)
    inv = _create_invoice_from_lines(db, user, 'industry_' + row.kind, row.id, None, None,
        [{'description': row.title, 'quantity': qty, 'unit_price': rate, 'tax_amount': money(gross * tax / 100)}], currency)
    inv.customer_id = buyer
    db.add(InvoiceContext(invoice_id=inv.id, project_id=row.project_id, seller_id=seller_id,
                          request_id='industry:' + str(row.id), origin='srm'))
    row.invoice_id = inv.id
    row.data = {**row.data, 'retention_percent': str(data.retention_percent), 'retention_amount': str(money(gross * data.retention_percent / 100))}
    save(db, user, row, 'invoice_drafted')
    return _invoice_payload(inv, db)


@router.get("/projects/{project_id}/summary")
def summary(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.srm.models import SRMInventoryMovement
    from app.apps.srm.services.commercial import scoped
    from app.apps.srm.commercial_models import ProjectCommercial
    from app.shared.settings import effective
    branch = context(db, user)
    get_project_for_action(db, project_id, user)
    rows = query(db, user, branch).filter_by(project_id=project_id).all()
    approved = [r for r in rows if r.kind in {'boq', 'variation'} and r.status == 'approved']
    measured = [r for r in rows if r.kind == 'measurement' and r.status == 'approved']
    value = lambda r: Decimal(r.data['quantity']) * Decimal(r.data['unit_rate'])
    movement_ids = [r.stock_movement_id for r in rows if r.stock_movement_id]
    material_cost = sum((m.value for m in db.query(SRMInventoryMovement).filter(SRMInventoryMovement.id.in_(movement_ids), scoped(SRMInventoryMovement.organization_id, user)).all()), Decimal(0)) if movement_ids else Decimal(0)
    ctx = db.get(ProjectCommercial, project_id)
    base_currency = effective(db, tenant(user), 'srm')['values']['currency']
    scope_currency = ctx.currency if ctx else base_currency
    if any(r.data.get('currency', scope_currency) != scope_currency for r in rows if r.kind in {'boq', 'variation', 'measurement', 'subcontract'}):
        fail('Project scope contains another currency. Reconcile commercial currency before combining totals.', 409)
    return {'approved_scope_value': money(sum((value(r) for r in approved), Decimal(0))),
            'certified_value': money(sum((value(r) for r in measured), Decimal(0))),
            'unbilled_certified_value': money(sum((value(r) for r in measured if not r.invoice_id), Decimal(0))),
            'committed_subcontracts': money(sum((Decimal(r.data['amount']) for r in rows if r.kind == 'subcontract' and r.status == 'approved'), Decimal(0))),
            'retention_tracked': money(sum((Decimal(r.data.get('retention_amount', '0')) for r in measured), Decimal(0))),
            'actual_material_cost': money(material_cost),
            'currency': ctx.currency if ctx else base_currency, 'material_cost_currency': base_currency,
            'currency_source': 'PMS Project Billing', 'amount_basis': 'Before tax; retention is tracked within the full invoice receivable, not a discount or payment'}
