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
from app.apps.srm.payments import PaymentInput as MeasurementPaymentInput
from app.apps.srm.services.commercial import tenant, require, customer, record, lock_tenant, money, invoice_for
from app.apps.project_management.access import get_project_for_action as _native_project_for_action
from app.business_packs.operations import require as require_pack_operation, for_record_read, for_transition

router = APIRouter(prefix="/srm/industry", tags=["Salon and construction operations"])
CONSTRUCTION = {"boq", "measurement", "site_diary", "variation", "subcontract", "material_issue",
                "work_package", "planning_baseline", "payment_certificate", "handover"}
KINDS = {"resource", "appointment"} | CONSTRUCTION


def get_project_for_action(db, project_id, user, action='browse'):
    selected = db.info.get('business_pack_scope')
    if selected is not None and selected.pack_key == 'construction':
        from app.business_packs.construction import project_for_action
        return project_for_action(db, user, project_id, action)
    return _native_project_for_action(db, project_id, user, action)


def fail(message, code=422):
    raise HTTPException(code, message)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BaseInput(Strict):
    request_id: UUID
    title: str = Field(min_length=1, max_length=220)


class ResourceInput(BaseInput):
    resource_type: Literal["provider", "doctor", "stylist", "consultant", "technician", "employee", "chair", "room", "equipment", "location"]
    user_id: int | None = Field(None, gt=0)
    employee_id: int | None = Field(None, gt=0)
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
    work_package_id: int | None = Field(None, gt=0)
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


def context(db, user, write=False, finance=False, appointments=False):
    names = ('srm_invoice_create', 'srm_admin') if finance else (('srm_manage', 'srm_admin') if write else ('srm_view', 'srm_manage', 'srm_admin', 'srm_invoice_view', 'srm_invoice_create'))
    require(user, *names)
    from app.module_registry import is_app_enabled
    from app.apps.business_os.services.module_service import assert_module_enabled
    if not all(is_app_enabled(k) for k in (("srm",) if appointments else ("crm", "srm", "project_management"))):
        fail("Enable Sales for appointments" if appointments else "Enable CRM, PMS and Sales for industry operations", 409)
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
    from app.module_registry import is_app_enabled
    from app.apps.srm.access import has_any_permission
    from app.apps.project_management.access import can_access_project
    branch_id=context(db, user, appointments=not project_id)
    manage = has_any_permission(user, {'srm_manage', 'srm_admin'})
    approve = False
    if project_id:
        p = get_project_for_action(db, project_id, user)
        selected = db.info.get('business_pack_scope')
        if selected is not None and selected.pack_key == 'construction':
            try:
                get_project_for_action(db, project_id, user, 'approve')
                approve = manage
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise
        else:
            approve = manage and can_access_project(db, p, user, 'approve')
    result = {'manage': manage, 'approve': approve, 'self_approve': bool(user.is_superuser), 'invoice': has_any_permission(user, {'srm_invoice_create', 'srm_admin'}), 'projects_enabled': is_app_enabled('project_management'), 'crm_enabled': is_app_enabled('crm'), 'billing': has_any_permission(user, {'srm_collection_view', 'srm_collection_create', 'srm_invoice_view', 'srm_invoice_create', 'srm_admin'}), 'collect': has_any_permission(user, {'srm_collection_create', 'srm_admin'}), 'approve_invoice': has_any_permission(user, {'srm_invoice_approve', 'srm_admin'})}
    from app.business_packs.operations import capabilities as pack_capabilities
    allowed = pack_capabilities(db, user)
    if allowed is not None:
        prepares = bool(allowed & {'billing.prepare', 'checkout.create'})
        reviews = bool(allowed & {'boq.approve', 'variations.approve', 'measurements.certify', 'subcontracts.manage'})
        result.update(
            manage=manage and bool(allowed & {'providers.manage', 'settings.manage', 'appointments.schedule', 'reservations.schedule', 'boq.prepare', 'variations.prepare', 'measurements.prepare', 'diary.record', 'subcontracts.manage', 'materials.request'}),
            approve=approve and reviews, self_approve=bool(user.is_superuser) and reviews,
            invoice=result['invoice'] and prepares,
            billing=result['billing'] and bool(allowed & {'billing.view', 'billing.prepare', 'checkout.view', 'checkout.create', 'payments.record'}),
            collect=result['collect'] and 'payments.record' in allowed,
            approve_invoice=result['approve_invoice'] and prepares,
        )
        result['appointment_actions'] = [action for action, cap in (
            ('schedule', 'appointments.schedule'), ('check_in', 'appointments.check_in'),
            ('cancel', 'appointments.cancel'), ('no_show', 'appointments.no_show'),
            ('start', 'visits.start'), ('complete', 'visits.complete')) if manage and cap in allowed]
    from app.apps.srm.service_checkout import checkout_capabilities
    result.update(checkout_capabilities(db, user))
    scope=db.info.get('business_pack_scope')
    if scope is not None and scope.pack_key == 'construction':
        result['self_approve'] = False
        from app.access.service import check_background_access
        def ceiling(module, action):
            try:
                check_background_access(db, user, module, action, administrative_read=False, stamp=False)
                return True
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise
                return False
        def project_action(action):
            if not project_id:
                return False
            try:
                get_project_for_action(db, project_id, user, action)
                return True
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise
                return False
        from app.business_packs.catalog_management import _module_grant
        from app.apps.project_management.access import PMS_GLOBAL_MANAGE_PROJECTS
        from app.business_packs.construction_definition import _workspace
        from app.business_packs.construction import _source
        native_pms = _module_grant(db, user, scope, 'project_management')
        global_projects = bool(user.is_superuser or PMS_GLOBAL_MANAGE_PROJECTS.intersection(native_pms.get('permissions', ())))
        workspace_ready = False
        if project_id:
            try:
                _, workspace_id = _source(db, user, project_id)
                if workspace_id is not None:
                    _workspace(db, user, scope, workspace_id)
                    workspace_ready = True
            except HTTPException as exc:
                if exc.status_code not in {403, 404}:
                    raise
        native_write = ceiling('srm', 'create')
        task_write = project_action('manage_tasks')
        native_approve = project_action('approve')
        result.update(
            workspace_ready=workspace_ready,
            workspace_setup_manage='settings.manage' in allowed and scope.writable and manage and global_projects and native_write and ceiling('project_management', 'create'),
            planning_manage=workspace_ready and 'boq.prepare' in allowed and task_write and native_write
                and ceiling('project_management', 'create') and ceiling('project_management', 'edit'),
            sites_create='settings.manage' in allowed and scope.writable and manage and global_projects and native_write and ceiling('project_management', 'create'),
            wbs_define=workspace_ready and 'boq.prepare' in allowed and task_write and native_write and ceiling('project_management', 'create'),
            actuals_task_manage=workspace_ready and 'diary.record' in allowed and task_write and native_write and ceiling('project_management', 'edit'),
            actuals_cost_manage=workspace_ready and 'billing.prepare' in allowed and result['invoice'] and project_action('edit_project') and native_write and ceiling('project_management', 'edit'),
            cost_budget_manage=workspace_ready and 'boq.prepare' in allowed and manage and project_action('edit_project') and native_write and ceiling('project_management', 'edit'),
            commercial_manage='billing.prepare' in allowed and has_any_permission(user, {'pms_manage_projects', 'pms_admin', 'srm_manage', 'srm_admin'}) and project_action('edit_project') and native_write and ceiling('project_management', 'edit'),
            planning_approve=workspace_ready and 'boq.approve' in allowed and native_approve and native_write,
            handover_prepare='diary.record' in allowed and task_write and native_write,
            certificate_prepare='billing.prepare' in allowed and result['invoice'] and native_write,
            delivery_approve=bool(allowed & {'boq.approve', 'billing.prepare'}) and native_approve and native_write,
            measurements_certify='measurements.certify' in allowed and native_approve and native_write,
            reports='sites.view' in allowed and ceiling('srm', 'view'),
        )
    result['operational_scope']={'realm':'pack' if scope is not None else 'legacy','user_id':user.id,'company_id':tenant(user),'branch_id':branch_id,
        **{key:getattr(scope,key,None) for key in ('context_id','pack_key','pack_version','context_revision','grant_revision','activation_revision')}}
    return result


def query(db, user, branch_id):
    return db.query(Record).filter_by(organization_id=tenant(user), branch_id=branch_id)


def get(db, user, branch_id, ident, kind=None, *, lock=True):
    selected = db.info.get('business_pack_scope')
    if selected is not None and selected.pack_key == 'construction':
        from app.business_packs.construction import authorize_record_project
        authorize_record_project(db, user, ident)
    scoped = query(db, user, branch_id).filter_by(id=ident)
    row = (scoped.with_for_update() if lock else scoped).first()
    if not row or (kind and row.kind != kind):
        fail("Industry record not found", 404)
    if row.project_id:
        get_project_for_action(db, row.project_id, user)
    return row


def out(row, db=None, actor=None):
    result = {k: getattr(row, k) for k in ("id", "kind", "title", "status", "revision", "customer_id", "project_id", "parent_id", "invoice_id", "stock_movement_id", "data", "created_at", "created_by", "approved_by")}
    result['data'] = {k: v for k, v in row.data.items() if not k.startswith('_')}
    if db is not None and actor is not None:
        from app.business_packs.industry_assignment import clinical_payload
        return clinical_payload(db, actor, row, result)
    return result


def audit(db, user, row, action):
    from app.apps.srm.api.router import _audit
    _audit(db, user, "industry_" + row.kind, row.id, action, after={"revision": row.revision, "status": row.status, "data": row.data})


def existing(db, user, branch_id, payload, kind):
    selected = db.info.get('business_pack_scope')
    if selected is not None and selected.pack_key == 'construction' and kind in CONSTRUCTION:
        from app.business_packs.construction import authorize_retry_project
        authorize_retry_project(db, user, payload.request_id)
    row = query(db, user, branch_id).filter_by(request_id=str(payload.request_id)).first()
    if row and (row.kind != kind or row.branch_id != branch_id):
        fail("Request ID already belongs to another operation", 409)
    if row:
        if row.data.get('_request_digest') != digest(payload):
            fail("Request ID was already used with different details", 409)
        return get(db, user, branch_id, row.id, kind)


def digest(payload):
    values = payload.model_dump(mode='json')
    # Preserve retry identities for resources created before HRMS linking existed.
    if isinstance(payload, ResourceInput) and values.get('employee_id') is None:
        values.pop('employee_id', None)
    if isinstance(payload, MeasurementInput) and values.get('work_package_id') is None:
        values.pop('work_package_id', None)
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def create(db, user, branch, kind, payload, *, record_data=None, **links):
    row = Record(organization_id=tenant(user), branch_id=branch, kind=kind, title=payload.title,
                 request_id=str(payload.request_id), created_by=user.id, status="draft", revision=1,
                 data={**payload.model_dump(mode="json", exclude={"request_id", "title"}), **(record_data or {}), '_request_digest': digest(payload)}, **links)
    db.add(row)
    db.flush()
    audit(db, user, row, "created")
    return row


def save(db, user, row, action):
    row.revision += 1
    audit(db, user, row, action)
    db.commit()
    return out(row, db, user)


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
    if db.info.get('business_pack_scope') is not None:
        from app.business_packs.industry_billing_guard import reserved_billing
        if reserved_billing(db,user,sales_order=sales_order,engagement=engagement,project_id=project_id):
            fail('This source has approved measurement billing reserved. Reconcile its billing before continuing.',409)
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
    selected = db.info.get('business_pack_scope')
    if selected is not None and selected.pack_key == 'construction':
        from app.business_packs.construction import require_clean_billing_start as selected_check
        return selected_check(db, user, project_id)
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
    selected = db.info.get('business_pack_scope')
    if selected is not None and selected.pack_key == 'construction':
        return get_project_for_action(db, project_id, user).currency
    from app.apps.srm.commercial_models import ProjectCommercial
    from app.shared.settings import effective
    ctx = db.get(ProjectCommercial, project_id)
    return ctx.currency if ctx else effective(db, tenant(user), 'srm')['values']['currency']


@router.get("/records")
def records(kind: str, project_id: int | None = None, from_at: datetime | None = None, until_at: datetime | None = None, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200), include_files: bool = False, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, appointments=kind in {'appointment', 'resource'})
    for_record_read(db, user, kind)
    if kind not in KINDS:
        fail("Unknown operation", 404)
    q = query(db, user, branch).filter_by(kind=kind)
    from app.apps.project_management.access import accessible_project_query
    from app.apps.project_management.models import PMSProject
    from app.module_registry import is_app_enabled
    from app.business_packs.industry_assignment import current_scope, ASSIGNED_ROLES
    selected = current_scope(db, user, tenant(user))
    clinical = selected is not None and (selected.pack_key, selected.role) in ASSIGNED_ROLES
    construction_scope = selected is not None and selected.pack_key == 'construction' and kind in CONSTRUCTION
    if construction_scope:
        if not project_id:
            fail("Select a project for construction operations")
        get_project_for_action(db, project_id, user)
        q = q.filter(Record.project_id == project_id)
    elif is_app_enabled('project_management') and not clinical:
        q = q.filter((Record.project_id.is_(None)) | Record.project_id.in_(accessible_project_query(db, user).with_entities(PMSProject.id)))
    else:
        q = q.filter(Record.project_id.is_(None))
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
    result = {"items": [out(r, db, user) for r in q.order_by(Record.id.desc()).offset(offset).limit(limit).all()]}
    if include_files:
        if not construction_scope or kind != 'site_diary':
            fail('Project file choices require the selected Construction site diary', 403)
        from app.business_packs.construction import project_files
        result['project_files'] = project_files(db, user, project_id, offset=offset, limit=limit)
    return result


@router.get('/material-warehouse-options')
def material_warehouse_options(search: str = Query('', max_length=180), offset: int = Query(0, ge=0, le=100000), db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.business_packs.construction_warehouse_options import options
    return options(db, user, search, offset)


@router.get('/project-options')
def project_options(search: str = Query('', max_length=180), offset: int = Query(0, ge=0), files_project_id: int | None = Query(None, gt=0), db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_pack_operation(db, user, 'sites.view')
    selected = db.info.get('business_pack_scope')
    if files_project_id is not None and (selected is None or selected.pack_key != 'construction'):
        fail('Construction file projects require the selected Construction context', 403)
    if selected is not None and selected.pack_key == 'construction':
        context(db, user)
        if files_project_id is not None:
            project = get_project_for_action(db, files_project_id, user)
            can_upload = False
            from app.business_packs.operations import capabilities as selected_capabilities
            if 'diary.record' in selected_capabilities(db, user):
                try:
                    get_project_for_action(db, files_project_id, user, 'upload')
                    from app.access.service import check_background_access
                    check_background_access(db, user, 'project_management', 'create', administrative_read=False, stamp=False)
                    can_upload = True
                except HTTPException as exc:
                    if exc.status_code != 403:
                        raise
            return {'items': [{'id': project.id, 'name': project.name, 'can_upload_files': can_upload}], 'has_more': False}
        from app.business_packs.construction import project_options as selected_options
        return selected_options(db, user, search, offset)
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
    branch = context(db, user, True, appointments=True)
    require_pack_operation(db, user, 'providers.manage', 'settings.manage')
    prior = existing(db, user, branch, data, 'resource')
    if prior:
        return out(prior)
    if query(db, user, branch).filter_by(kind='resource', title=data.title).first():
        fail("A resource with this name already exists in this branch", 409)
    employee = None
    if data.employee_id:
        if data.resource_type not in PROVIDER_TYPES:
            fail('Only providers can be linked to HRMS employees')
        employee = provider_employee(db, user, branch, data.employee_id)
        if data.user_id and employee.user_id != data.user_id:
            fail('The staff account must match the selected HRMS employee')
    if data.user_id:
        from app.shared.form_defaults import reference_queries
        staff, _ = reference_queries(db, tenant(user))['users']
        if not staff.filter(User.id == data.user_id).first():
            fail("Choose an active staff member from this company")
    row = create(db, user, branch, 'resource', data)
    if employee:
        row.data = {**row.data, 'user_id': employee.user_id}
    row.status = 'active'
    db.commit()
    return out(row)


@router.get('/staff-options')
def staff_options(search: str = Query('', max_length=180), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_pack_operation(db, user, 'providers.manage', 'settings.manage', 'appointments.schedule', 'reservations.schedule')
    context(db, user, appointments=True)
    require(user, 'srm_manage', 'srm_admin')
    from app.shared.form_defaults import reference_queries
    staff, _ = reference_queries(db, tenant(user))['users']
    if search.strip():
        staff = staff.filter(User.email.ilike('%' + search.strip().replace('%', r'\%').replace('_', r'\_') + '%', escape='\\'))
    rows = staff.order_by(User.email, User.id).offset(offset).limit(51).all()
    return {'items': [{'id': row.id, 'name': row.email} for row in rows[:50]], 'has_more': len(rows) > 50}


PROVIDER_TYPES = {'provider', 'doctor', 'stylist', 'consultant', 'technician', 'employee'}


def employee_query(db, user, branch):
    from app.models.employee import Employee
    return db.query(Employee).join(Branch, Employee.branch_id == Branch.id).filter(
        Branch.company_id == tenant(user), Branch.id == branch,
        Employee.deleted_at.is_(None), Employee.status.in_(['Active', 'Probation', 'On Leave']))


def provider_employee(db, user, branch, employee_id):
    from app.models.employee import Employee
    employee = employee_query(db, user, branch).filter(Employee.id == employee_id).first()
    if not employee:
        fail('Choose an active HRMS employee from this branch')
    return employee


@router.get('/employee-options')
def employee_options(search: str = Query('', max_length=180), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_pack_operation(db, user, 'providers.manage', 'settings.manage', 'appointments.schedule', 'reservations.schedule')
    from sqlalchemy import or_
    from app.models.employee import Employee
    context_branch = context(db, user, appointments=True)
    require(user, 'srm_manage', 'srm_admin')
    q = employee_query(db, user, context_branch)
    if search.strip():
        match = '%' + search.strip().replace('%', r'\%').replace('_', r'\_') + '%'
        q = q.filter(or_(Employee.first_name.ilike(match, escape='\\'), Employee.last_name.ilike(match, escape='\\'), Employee.employee_id.ilike(match, escape='\\')))
    rows = q.with_entities(Employee.id, Employee.first_name, Employee.last_name, Employee.employee_id).order_by(Employee.first_name, Employee.last_name, Employee.id).offset(offset).limit(51).all()
    return {'items': [{'id': row.id, 'name': f'{row.first_name} {row.last_name}'.strip(), 'code': row.employee_id} for row in rows[:50]], 'has_more': len(rows) > 50}


def available(db, user, branch, starts, minutes, resource_ids, ignore=None, *, lock=True):
    if len(set(resource_ids)) != len(resource_ids):
        fail("Select each resource once")
    end = starts + timedelta(minutes=minutes)
    resources = [get(db, user, branch, i, 'resource', lock=lock) for i in resource_ids]
    if not any(r.data['resource_type'] in PROVIDER_TYPES for r in resources):
        from app.shared.business_profile import term
        fail(f"Choose a {term(db, tenant(user), 'provider', branch_id=branch).lower()}")
    for r in resources:
        local, local_end = starts.astimezone(ZoneInfo(r.data['timezone'])), end.astimezone(ZoneInfo(r.data['timezone']))
        if r.data.get('employee_id'):
            employee = provider_employee(db, user, branch, r.data['employee_id'])
            if employee.date_of_exit and employee.date_of_exit <= local.date():
                fail(f'{r.title} is no longer available', 409)
            from app.business_packs.availability import employee_leave_conflict
            if employee_leave_conflict(db, tenant(user), employee.id, local.date(), local_end.date()):
                fail(f'{r.title} has approved leave at that time', 409)
        if r.status != 'active' or local.weekday() not in r.data['weekdays'] or local.date() != local_end.date() or local.time().replace(tzinfo=None) < time.fromisoformat(r.data['opens']) or local_end.time().replace(tzinfo=None) > time.fromisoformat(r.data['closes']):
            fail(f"{r.title} is outside opening hours", 409)
    # Tenant writer lock serializes conflict check + insert, including distinct resources
    # that reference the same staff identity. Cancelled/no-show slots are released.
    from app.business_packs.availability import appointment_conflict
    if appointment_conflict(db, tenant(user), starts, end, resource_ids=resource_ids, ignore_appointment_id=ignore):
        fail("Provider or resource is already booked at that time", 409)


@router.post("/appointments", status_code=201)
def appointment(data: AppointmentInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return appointment_operation(data, db, user)


def appointment_operation(data, db, user, *, commit=True):
    from app.apps.srm.models import SRMProduct
    branch = context(db, user, True, appointments=True)
    require_pack_operation(db, user, 'appointments.schedule', 'reservations.schedule')
    prior = existing(db, user, branch, data, 'appointment')
    if prior:
        return out(prior)
    buyer = customer(db, data.customer_id, user)
    service = record(db, SRMProduct, data.service_id, user)
    if not service.active or service.product_type.lower() not in {'service', 'services'}:
        fail("Choose an active service from the shared catalog")
    if data.project_id:
        context(db, user)
        get_project_for_action(db, data.project_id, user, 'manage_tasks')
    if data.deal_id:
        from app.module_registry import is_app_enabled
        from app.apps.business_os.services.module_service import assert_module_enabled
        if not is_app_enabled('crm'): fail('Enable CRM to link an opportunity', 409)
        assert_module_enabled(db, 'crm', company_id=tenant(user))
        from app.apps.crm.api.router import _assert_record_visible, _get_resource
        from app.apps.crm.models import CRMDeal
        _assert_record_visible(db, _get_resource('deals'), data.deal_id, tenant(user), user)
        deal = record(db, CRMDeal, data.deal_id, user)
        if deal.company_id != data.customer_id:
            fail("CRM deal must belong to the same customer")
    available(db, user, branch, data.starts_at, data.duration_minutes, data.resource_ids)
    row = create(db, user, branch, 'appointment', data, customer_id=data.customer_id, project_id=data.project_id)
    row.starts_at, row.ends_at = data.starts_at, data.starts_at + timedelta(minutes=data.duration_minutes)
    row.data = {**row.data, 'customer_name': buyer.name, 'service_name': service.item_name, 'unit_price': str(service.sales_rate), 'tax_rate': str(service.gst_rate), 'currency': service.currency}
    row.status = 'booked'
    if data.create_pms_task:
        from app.apps.project_management.api.router import create_task_operation
        from app.apps.project_management.schemas import PMSTaskCreate
        provider = next(get(db, user, branch, i, 'resource') for i in data.resource_ids if get(db, user, branch, i, 'resource').data['resource_type'] in PROVIDER_TYPES)
        day = data.starts_at.astimezone(ZoneInfo(provider.data['timezone'])).date()
        from app.shared.business_profile import term
        label = term(db, tenant(user), 'appointment', branch_id=branch)
        prefix = 'SALON' if provider.data['resource_type'] == 'stylist' else 'APPT'
        task = create_task_operation(data.project_id, PMSTaskCreate(task_key=f'{prefix}-{row.id}', title=data.title, description=f'{label} #{row.id}. Service: {service.item_name}. Manage booking, service and billing in /srm/appointments.', start_date=day, due_date=day, estimated_hours=Decimal(data.duration_minutes)/60), db, user, commit=False)
        row.data = {**row.data, 'pms_task_id': task.id}
    if commit:
        db.commit()
    else:
        db.flush()
    return out(row)


@router.put("/appointments/{ident}/schedule")
def reschedule(ident: int, data: Reschedule, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, True, appointments=True)
    require_pack_operation(db, user, 'appointments.schedule', 'reservations.schedule')
    row = get(db, user, branch, ident, 'appointment')
    from app.apps.srm.appointment_checkout import checkout_link
    if checkout_link(db, row) is not None:
        fail({'code': 'grouped_service_schedule',
              'message': 'Use the linked service schedule to keep its specialist and policy revisions together'}, 409)
    revision(row, data.expected_revision)
    if row.status != 'booked':
        fail("Only booked appointments can be rescheduled", 409)
    available(db, user, branch, data.starts_at, data.duration_minutes, data.resource_ids, row.id)
    row.data = {**row.data, **data.model_dump(mode='json', exclude={'expected_revision'})}
    row.starts_at, row.ends_at = data.starts_at, data.starts_at + timedelta(minutes=data.duration_minutes)
    if row.data.get('pms_task_id'):
        context(db, user)
        from app.apps.project_management.api.router import update_task_operation
        from app.apps.project_management.schemas import PMSTaskUpdate
        local = data.starts_at.astimezone(ZoneInfo(get(db, user, branch, data.resource_ids[0], 'resource').data['timezone'])).date()
        update_task_operation(row.data['pms_task_id'], PMSTaskUpdate(start_date=local, due_date=local, estimated_hours=Decimal(data.duration_minutes)/60), db, user, commit=False)
    return save(db, user, row, 'rescheduled')


@router.post("/boq", status_code=201)
def boq(data: BOQInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    branch = context(db, user, True)
    kind = 'variation' if data.variation_of else 'boq'
    require_pack_operation(db, user, 'variations.prepare' if data.variation_of else 'boq.prepare')
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
    require_pack_operation(db, user, 'measurements.prepare')
    prior = existing(db, user, branch, data, 'measurement')
    if prior:
        return out(prior)
    item = get(db, user, branch, data.boq_id)
    if item.kind not in {'boq', 'variation'} or item.status != 'approved':
        fail("Measure an approved BOQ item or variation")
    get_project_for_action(db, item.project_id, user, 'manage_tasks')
    package_source = {}
    if data.work_package_id is not None:
        from app.business_packs.construction_workpackages import measurement_source
        package_source = measurement_source(db, user, item.id, data.work_package_id)
    row = create(db, user, branch, 'measurement', data, project_id=item.project_id, parent_id=item.id,
        record_data={'unit': item.data['unit'], 'unit_rate': item.data['unit_rate'], 'tax_rate': item.data['tax_rate'],
            'boq_code': item.data['code'], 'currency': item.data['currency'], **package_source})
    db.commit()
    return out(row)


@router.post("/site-diaries", status_code=201)
def diary(data: DiaryInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.apps.project_management.models import PMSFileAsset
    branch = context(db, user, True)
    require_pack_operation(db, user, 'diary.record')
    prior = existing(db, user, branch, data, 'site_diary')
    if prior:
        return out(prior)
    get_project_for_action(db, data.project_id, user, 'manage_tasks')
    selected = db.info.get('business_pack_scope')
    if selected is not None and selected.pack_key == 'construction':
        from app.business_packs.construction import project_files
        project_files(db, user, data.project_id, file_ids=data.file_ids)
    else:
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
    require_pack_operation(db, user, 'subcontracts.manage')
    prior = existing(db, user, branch, data, 'subcontract')
    if prior:
        return out(prior)
    get_project_for_action(db, data.project_id, user, 'edit_project')
    vendor = customer(db, data.vendor_id, user)
    from app.shared.master_data import relationships
    selected = db.info.get('business_pack_scope')
    if selected is not None and selected.pack_key == 'construction':
        from app.business_packs.construction import subcontract_vendor_roles
        roles = subcontract_vendor_roles(db, user, data.project_id, vendor)
    else:
        roles = relationships(db, vendor, 'company')
    vendor_roles = {r.lower() for r in roles} | {(vendor.account_type or '').lower()}
    if not vendor_roles.intersection({'vendor', 'supplier'}):
        fail("Choose a vendor from the shared company directory")
    row = create(db, user, branch, 'subcontract', data, project_id=data.project_id)
    row.data = {**row.data, 'currency': project_currency(db, user, data.project_id)}
    db.commit()
    return out(row)


@router.post('/material-issues', status_code=201)
def material_issue(data: MaterialInput, db: Session = Depends(get_db), user=Depends(get_current_user)):
    selected = db.info.get('business_pack_scope')
    if selected is not None and selected.pack_key == 'construction':
        from app.business_packs.construction_materials import issue
        return issue(data, db, user)
    from app.apps.srm.api.router import _product_or_404, _warehouse_or_404, _post_stock_movement, _balance_for_update
    branch = context(db, user, True)
    require_pack_operation(db, user, 'materials.request')
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
    branch = context(db, user, True, appointments=True)
    row = get(db, user, branch, ident)
    for_transition(db, user, row.kind, data.status)
    if row.kind != 'appointment': context(db, user)
    revision(row, data.expected_revision)
    if row.kind == 'appointment':
        allowed = {'booked': {'checked_in', 'cancelled', 'no_show'}, 'checked_in': {'in_service', 'cancelled'}, 'in_service': {'completed'}}
        if data.status not in allowed.get(row.status, set()):
            fail("Invalid appointment transition", 409)
        if data.status == 'no_show' and datetime.fromisoformat(row.data['starts_at']) > datetime.now(timezone.utc):
            fail('A no-show can only be recorded after the appointment starts', 409)
    elif row.kind in {'boq', 'variation', 'measurement', 'subcontract'}:
        get_project_for_action(db, row.project_id, user, 'approve')
        if row.status != 'draft' or data.status not in {'approved', 'rejected'}:
            fail("Only draft records can be approved or rejected", 409)
        selected = db.info.get('business_pack_scope')
        if row.created_by == user.id and (not user.is_superuser or
                (selected is not None and selected.pack_key == 'construction')):
            fail("A different project approver must review this record", 403)
        if row.kind in {'boq', 'variation'} and data.status == 'approved':
            require_clean_billing_start(db, user, row.project_id)
        if row.kind == 'measurement' and data.status == 'approved':
            if row.data.get('work_package_id'):
                from app.business_packs.construction_workpackages import validate_measurement_quantity
                validate_measurement_quantity(db, user, row)
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
    require_pack_operation(db, user, 'billing.prepare', 'checkout.create')
    from app.apps.srm.api.router import _create_invoice_from_lines, _invoice_payload
    from app.apps.srm.commercial_models import InvoiceContext, ProjectCommercial
    require(user, 'srm_invoice_create', 'srm_admin')
    branch = context(db, user, True, finance=True, appointments=True)
    row = get(db, user, branch, ident)
    from app.apps.srm.appointment_checkout import require_standalone
    require_standalone(db, row)
    if row.kind != 'appointment': context(db, user)
    if row.invoice_id:
        return _invoice_payload(invoice_for(db, row.invoice_id, user), db)
    revision(row, data.expected_revision)
    if row.kind == 'appointment' and row.status == 'completed':
        if data.retention_percent:
            fail("Retention applies only to construction measurements")
        buyer, seller_id, currency = row.customer_id, tenant(user), row.data['currency']
        qty, rate, tax = Decimal(1), Decimal(row.data['unit_price']), Decimal(row.data['tax_rate'])
    elif row.kind == 'measurement' and row.status == 'approved':
        selected = db.info.get('business_pack_scope')
        if selected is not None and selected.pack_key == 'construction':
            from app.business_packs.construction_billing import draft
            return draft(db, user, row, data)
        else:
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


@router.post("/records/{ident}/payments", status_code=201)
def measurement_payment(ident: int, data: "MeasurementPaymentInput", db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.business_packs.construction_billing import payment
    return payment(db, user, ident, data)


@router.get("/projects/{project_id}/summary")
def summary(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_pack_operation(db, user, 'sites.view')
    from app.apps.srm.models import SRMInventoryMovement
    from app.apps.srm.services.commercial import scoped
    from app.shared.settings import effective
    branch = context(db, user)
    get_project_for_action(db, project_id, user)
    rows = query(db, user, branch).filter_by(project_id=project_id).all()
    approved = [r for r in rows if r.kind in {'boq', 'variation'} and r.status == 'approved']
    measured = [r for r in rows if r.kind == 'measurement' and r.status == 'approved']
    value = lambda r: Decimal(r.data['quantity']) * Decimal(r.data['unit_rate'])
    movement_ids = [r.stock_movement_id for r in rows if r.stock_movement_id]
    material_cost = sum((m.value for m in db.query(SRMInventoryMovement).filter(SRMInventoryMovement.id.in_(movement_ids), scoped(SRMInventoryMovement.organization_id, user)).all()), Decimal(0)) if movement_ids else Decimal(0)
    base_currency = effective(db, tenant(user), 'srm')['values']['currency']
    scope_currency = project_currency(db, user, project_id)
    if any(r.data.get('currency', scope_currency) != scope_currency for r in rows if r.kind in {'boq', 'variation', 'measurement', 'subcontract'}):
        fail('Project scope contains another currency. Reconcile commercial currency before combining totals.', 409)
    return {'approved_scope_value': money(sum((value(r) for r in approved), Decimal(0))),
            'certified_value': money(sum((value(r) for r in measured), Decimal(0))),
            'unbilled_certified_value': money(sum((value(r) for r in measured if not r.invoice_id), Decimal(0))),
            'committed_subcontracts': money(sum((Decimal(r.data['amount']) for r in rows if r.kind == 'subcontract' and r.status == 'approved'), Decimal(0))),
            'retention_tracked': money(sum((Decimal(r.data.get('retention_amount', '0')) for r in measured), Decimal(0))),
            'actual_material_cost': money(material_cost),
            'currency': scope_currency, 'material_cost_currency': base_currency,
            'currency_source': 'PMS Project Billing', 'amount_basis': 'Before tax; retention is tracked within the full invoice receivable, not a discount or payment'}


from app.business_packs.construction_workpackages import router as construction_workpackages_router
from app.business_packs.construction_delivery import router as construction_delivery_router
from app.business_packs.construction_controls import router as construction_controls_router
from app.business_packs.construction_definition import router as construction_definition_router
from app.business_packs.construction_actuals import router as construction_actuals_router
router.include_router(construction_workpackages_router)
router.include_router(construction_delivery_router)
router.include_router(construction_controls_router)
router.include_router(construction_definition_router)
router.include_router(construction_actuals_router)


from app.apps.srm.appointment_billing import router as appointment_billing_router
router.include_router(appointment_billing_router)

from app.business_packs.construction_commercial import router as construction_commercial_router
from app.business_packs.construction_dependencies import router as construction_dependencies_router
router.include_router(construction_commercial_router)
router.include_router(construction_dependencies_router)

from app.business_packs.construction_workspaces import router as construction_workspaces_router
router.include_router(construction_workspaces_router)
