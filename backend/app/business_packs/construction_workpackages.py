"""WBS scope allocations over existing native PMS task hierarchy and BOQ rows."""
from dataclasses import dataclass
from contextlib import contextmanager
from decimal import Decimal
from hashlib import sha256
from uuid import UUID
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, and_, exists, inspect, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.apps.project_management.models import PMSTask
from app.apps.srm.industry_models import IndustryRecord
from app.branches.models import BranchOwnership
from .models import PackRecordOwnership
from .construction import _source, project_for_action
from .operations import require

router = APIRouter(tags=['Construction work packages'])
_ATTRIBUTIONS = WeakKeyDictionary()


class WorkPackageInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    title: str = Field(min_length=1, max_length=220)
    project_id: int = Field(gt=0)
    task_id: int = Field(gt=0)
    boq_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=4)
    budget_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    notes: str = Field(default='', max_length=4000)


class WorkPackageUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1)
    quantity: Decimal = Field(gt=0, max_digits=16, decimal_places=4)
    budget_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    notes: str = Field(default='', max_length=4000)


class MeasurementAttributionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    expected_revision: int = Field(ge=1)
    work_package_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)


def fail(message, status=409):
    raise HTTPException(status, message)


@dataclass(frozen=True)
class TaskSource:
    id: int
    parent_task_id: int | None
    title: str
    hierarchy: str


def task_source(db, actor, project_id, task_id, *, action='browse'):
    """Every ancestor must be the actual current, explicitly enrolled native task."""
    if type(task_id) is not int or task_id <= 0:
        fail('A canonical task identity is required', 422)
    scope, _ = _source(db, actor, project_id)
    project_for_action(db, actor, project_id, action)
    task, owner, branch = PMSTask.__table__, PackRecordOwnership.__table__, BranchOwnership.__table__
    current, seen, chain, selected = task_id, set(), [], None
    while current is not None:
        if type(current) is not int or current in seen or len(seen) >= 200:
            fail('Canonical work package hierarchy is cyclic or too deep')
        seen.add(current)
        query = select(task.c.id, task.c.project_id, task.c.parent_task_id, task.c.title).where(
            task.c.id == current, task.c.project_id == project_id, task.c.deleted_at.is_(None),
            exists().where(owner.c.resource_table == task.name, owner.c.resource_key == str(current),
                owner.c.company_id == scope.company_id, owner.c.branch_id == scope.branch_id, owner.c.context_id == scope.context_id),
            exists().where(branch.c.resource_table == task.name, branch.c.resource_key == str(current),
                branch.c.company_id == scope.company_id, branch.c.branch_id == scope.branch_id))
        if db.info.get('security_write_request'):
            query = query.with_for_update()
        row = db.connection().execute(query).first()
        if row is None:
            fail('An explicitly owned canonical task and same-site ancestors are required', 404)
        selected = selected or row
        chain.append((row.id, row.project_id, row.parent_task_id))
        current = row.parent_task_id
    return TaskSource(selected.id, selected.parent_task_id, selected.title, sha256(repr(chain).encode()).hexdigest())


def _parent(db, actor, project_id, boq_id):
    from app.apps.srm.industry_api import get, project_currency
    scope, _ = _source(db, actor, project_id)
    parent = get(db, actor, scope.branch_id, boq_id)
    if parent.kind not in {'boq', 'variation'} or parent.project_id != project_id or parent.status != 'approved':
        fail('A work package requires approved BOQ scope in the same site', 422)
    if parent.data['currency'] != project_currency(db, actor, project_id):
        fail('Reconcile the project currency before mapping approved scope')
    return parent


def _parent_stamp(parent):
    return sha256(repr((parent.id, parent.project_id, parent.kind, parent.status, parent.revision,
        tuple(str(parent.data.get(key)) for key in ('quantity', 'unit', 'unit_rate', 'currency')))).encode()).hexdigest()


def _allocations(db, actor, project_id, boq_id):
    from app.apps.srm.industry_api import query
    scope, _ = _source(db, actor, project_id)
    return query(db, actor, scope.branch_id).filter_by(project_id=project_id, parent_id=boq_id, kind='work_package', status='mapped').all()


def _ceiling(db, actor, row, parent):
    quantity = Decimal(row.data['quantity'])
    total = sum((Decimal(item.data['quantity']) for item in _allocations(db, actor, row.project_id, parent.id)
        if item is not row and item.id != row.id), Decimal(0)) + quantity
    if total > Decimal(parent.data['quantity']):
        fail('Mapped work package quantities exceed approved BOQ; approve a variation first')


def validate_work_package_source(db, scope, row, *, write=True):
    """Called by the Construction boundary before every work-package write."""
    if type(row) is not IndustryRecord:
        return
    from app.models.user import User
    actor = db.get(User, scope.user_id)
    if row.kind == 'measurement':
        ident = row.data.get('work_package_id')
        _validate_attribution_write(db, actor, scope, row)
        if ident is None:
            return
        expected = measurement_source(db, actor, row.parent_id, ident)
        if any(row.data.get(key) != value for key, value in expected.items()):
            fail('Certified work package source cannot be changed', 403)
        if row.status == 'approved':
            validate_measurement_quantity(db, actor, row)
        return
    if row.kind != 'work_package':
        return
    if write:
        from app.access.service import check_background_access
        check_background_access(db, actor, 'project_management', 'edit', administrative_read=False, stamp=False)
        require(db, actor, 'boq.prepare')
    else:
        require(db, actor, 'sites.view')
    if row.status != 'mapped' or row.parent_id is None or row.invoice_id is not None or row.stock_movement_id is not None:
        fail('Work package mapping cannot mint invoices, stock or alternate statuses', 403)
    if type(row.data.get('task_id')) is not int:
        fail('A canonical native task is required', 422)
    task = task_source(db, actor, row.project_id, row.data['task_id'], action='manage_tasks' if write else 'browse')
    parent = _parent(db, actor, row.project_id, row.parent_id)
    required = {'task_id', 'parent_task_id', 'boq_id', 'quantity', 'budget_cost', 'unit', 'unit_rate', 'currency', 'notes', '_task_hierarchy', '_boq_source', '_request_digest'}
    if (set(row.data) != required or row.data['parent_task_id'] != task.parent_task_id or row.data['boq_id'] != parent.id
            or row.data['_task_hierarchy'] != task.hierarchy or row.data['_boq_source'] != _parent_stamp(parent)
            or any(str(row.data[key]) != str(parent.data[key]) for key in ('unit', 'unit_rate', 'currency'))):
        fail('Canonical task hierarchy or approved scope changed; reconcile the mapping')
    try:
        quantity = Decimal(row.data['quantity'])
        if not quantity.is_finite() or quantity <= 0:
            raise ValueError()
        budget = Decimal(row.data['budget_cost'])
        if not budget.is_finite() or budget < 0:
            raise ValueError()
    except (ValueError, TypeError, ArithmeticError):
        fail('Work package quantity must be positive', 422)
    state = inspect(row)
    if state.persistent:
        original = db.connection().execute(select(IndustryRecord.__table__.c.data).where(IndustryRecord.__table__.c.id == row.id)).scalar_one()
        if any(row.data.get(key) != original.get(key) for key in required - {'quantity', 'budget_cost', 'notes'}):
            fail('Work package task, source and original hierarchy are immutable', 403)
    _ceiling(db, actor, row, parent)
    if row.id is not None and _certified(db, actor, row.project_id, row.parent_id, row.id) > quantity:
        fail('Mapped quantity cannot be reduced below certified work')


def _write(db, actor, project_id):
    from app.apps.srm.industry_api import context
    from app.access.service import check_background_access
    branch = context(db, actor, True)
    require(db, actor, 'boq.prepare')
    check_background_access(db, actor, 'project_management', 'edit', administrative_read=False, stamp=False)
    scope, _ = _source(db, actor, project_id)
    if not scope.writable or branch != scope.branch_id:
        fail('A writable Construction site context is required', 403)
    project_for_action(db, actor, project_id, 'manage_tasks')
    return scope


@router.post('/work-packages', status_code=201)
def create_work_package(data: WorkPackageInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    from app.apps.srm.industry_api import existing, digest, audit, out, query
    scope = _write(db, actor, data.project_id)
    # Explicit proof precedes the parent-filtered native idempotency lookup.
    from .construction import authorize_retry_project
    authorize_retry_project(db, actor, data.request_id)
    previous = existing(db, actor, scope.branch_id, data, 'work_package')
    if previous:
        return out(previous)
    parent = _parent(db, actor, data.project_id, data.boq_id)
    task = task_source(db, actor, data.project_id, data.task_id, action='manage_tasks')
    if any(item.data.get('task_id') == task.id for item in _allocations(db, actor, data.project_id, parent.id)):
        fail('This task is already mapped to the approved BOQ item')
    row = IndustryRecord(organization_id=scope.company_id, branch_id=scope.branch_id, project_id=data.project_id,
        parent_id=parent.id, kind='work_package', title=data.title, status='mapped', revision=1,
        request_id=str(data.request_id), created_by=actor.id,
        data={'task_id': task.id, 'parent_task_id': task.parent_task_id, 'boq_id': parent.id,
            'quantity': str(data.quantity), 'budget_cost': str(data.budget_cost), 'notes': data.notes, '_task_hierarchy': task.hierarchy,
            '_boq_source': _parent_stamp(parent), '_request_digest': digest(data),
            **{key: parent.data[key] for key in ('unit', 'unit_rate', 'currency')}})
    _ceiling(db, actor, row, parent)
    db.add(row); db.flush()
    audit(db, actor, row, 'work_package_mapped')
    db.commit()
    return out(row)


@router.put('/work-packages/{ident}')
def update_work_package(ident: int, data: WorkPackageUpdate, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    from app.apps.srm.industry_api import context, get, revision, save
    branch = context(db, actor, True)
    require(db, actor, 'boq.prepare')
    row = get(db, actor, branch, ident, 'work_package')
    _write(db, actor, row.project_id)
    revision(row, data.expected_revision)
    row.data = {**row.data, 'quantity': str(data.quantity), 'budget_cost': str(data.budget_cost), 'notes': data.notes}
    validate_work_package_source(db, db.info['business_pack_scope'], row)
    return save(db, actor, row, 'work_package_updated')


@router.get('/work-packages')
def list_work_packages(project_id: int, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    from app.apps.srm.industry_api import context, query, out
    branch = context(db, actor)
    require(db, actor, 'sites.view')
    _source(db, actor, project_id)
    project_for_action(db, actor, project_id)
    rows = query(db, actor, branch).filter_by(project_id=project_id, kind='work_package').order_by(IndustryRecord.id).all()
    for row in rows:
        task = task_source(db, actor, project_id, row.data['task_id'])
        if task.hierarchy != row.data['_task_hierarchy']:
            fail('Canonical work package hierarchy changed; reconcile the mapping')
        parent = _parent(db, actor, project_id, row.parent_id)
        if _parent_stamp(parent) != row.data['_boq_source']:
            fail('Approved work package scope changed; reconcile the mapping')
    return {'items': [out(row) for row in rows]}


def measurement_source(db, actor, boq_id, work_package_id):
    """Bind a measurement to the exact owned task allocation of its actual BOQ."""
    if type(work_package_id) is not int or work_package_id <= 0:
        fail('A canonical work package mapping is required', 422)
    from app.apps.srm.industry_api import get
    scope = db.info.get('business_pack_scope')
    if scope is None or scope.pack_key != 'construction':
        fail('A selected Construction context is required', 403)
    require(db, actor, 'measurements.prepare', 'measurements.certify', 'sites.view')
    parent = get(db, actor, scope.branch_id, boq_id)
    mapping = get(db, actor, scope.branch_id, work_package_id, 'work_package')
    if mapping.status != 'mapped' or mapping.parent_id != boq_id or mapping.project_id != parent.project_id:
        fail('Measurement work package must map its approved BOQ in the same site', 422)
    _parent(db, actor, mapping.project_id, boq_id)
    task = task_source(db, actor, mapping.project_id, mapping.data['task_id'])
    if task.hierarchy != mapping.data['_task_hierarchy'] or _parent_stamp(parent) != mapping.data['_boq_source']:
        fail('Reconcile the work package hierarchy and approved scope before certification')
    return {'work_package_id': mapping.id, 'work_package_task_id': task.id}


def _certified(db, actor, project_id, boq_id, mapping_id, *, exclude=None):
    from app.apps.srm.industry_api import query
    scope, _ = _source(db, actor, project_id)
    rows = query(db, actor, scope.branch_id).filter_by(project_id=project_id, parent_id=boq_id, kind='measurement', status='approved').all()
    return sum((Decimal(row.data['quantity']) for row in rows
        if row.id != exclude and row.data.get('work_package_id') == mapping_id), Decimal(0))


def validate_measurement_quantity(db, actor, row):
    """Additional per-allocation ceiling; the native approved BOQ cap remains."""
    ident = row.data.get('work_package_id')
    if ident is None:
        return
    source = measurement_source(db, actor, row.parent_id, ident)
    from app.apps.srm.industry_api import get
    scope = db.info['business_pack_scope']
    mapping = get(db, actor, scope.branch_id, source['work_package_id'], 'work_package')
    total = _certified(db, actor, row.project_id, row.parent_id, mapping.id, exclude=row.id) + Decimal(row.data['quantity'])
    if total > Decimal(mapping.data['quantity']):
        fail('Certified quantity exceeds the mapped work package allocation')


@dataclass(frozen=True)
class _Attribution:
    scope: object
    row: object
    actor: object
    data: MeasurementAttributionInput
    original: object
    native_authority: str
    project_epoch: object


def _attribution_marker(command):
    return {'request_id': str(command.data.request_id), 'from_revision': command.original.revision,
        'to_revision': command.original.revision + 1, 'work_package_id': command.data.work_package_id,
        'task_id': command.row.data['work_package_task_id'], 'actor_id': command.actor.id, 'reason': command.data.reason}


def _attribution_access(db, actor, row):
    from app.access.service import check_background_access
    from app.apps.srm.industry_api import context
    context(db, actor, True)
    require(db, actor, 'measurements.certify')
    check_background_access(db, actor, 'srm', 'create', administrative_read=False, stamp=False)
    check_background_access(db, actor, 'project_management', 'approve', administrative_read=False, stamp=False)
    scope, _ = _source(db, actor, row.project_id)
    if not scope.writable:
        fail('A writable Construction attribution context is required', 403)
    project_for_action(db, actor, row.project_id, 'approve')
    if row.created_by == actor.id:
        fail('A different native project reviewer must attribute certified work', 403)
    return scope


def _validate_attribution_write(db, actor, scope, row):
    if not inspect(row).persistent:
        return
    original = db.connection().execute(select(IndustryRecord.__table__).where(IndustryRecord.__table__.c.id == row.id)).first()
    old = original.data or {}
    previous, current = old.get('work_package_id'), row.data.get('work_package_id')
    command = _ATTRIBUTIONS.get(db)
    if previous is not None:
        if (current != previous or row.data.get('work_package_task_id') != old.get('work_package_task_id')
                or row.data.get('_work_package_attribution') != old.get('_work_package_attribution')):
            fail('Certified work package attribution is immutable', 403)
        if type(command) is not _Attribution or command.row is not row:
            return
        # A post-flush check must still compare against the original unassigned
        # certified source, not treat our first flush as unrelated history.
        original, old = command.original, command.original.data or {}
    if current is None:
        if row.data.get('_work_package_attribution') is not None:
            fail('A genuine first-attribution command is required', 403)
        return
    if (type(command) is not _Attribution or command.scope is not scope or command.row is not row
            or command.actor is not actor or type(command.data) is not MeasurementAttributionInput
            or original.status != 'approved' or row.status != 'approved'
            or row.revision != original.revision + 1):
        fail('A genuine independent first-attribution command is required', 403)
    _attribution_access(db, actor, row)
    from .common_core import _native_authority
    from .construction import _project_epoch
    if (command.native_authority != _native_authority(db, actor, scope.company_id)
            or command.project_epoch != _project_epoch(db, scope, row.project_id)):
        fail('Native certified attribution authority changed', 403)
    allowed = {'work_package_id', 'work_package_task_id', '_work_package_attribution'}
    if ({key: value for key, value in row.data.items() if key not in allowed}
            != {key: value for key, value in old.items() if key not in allowed}
            or row.data['_work_package_attribution'] != _attribution_marker(command)
            or any(getattr(row, key) != getattr(original, key) for key in
                ('id', 'organization_id', 'branch_id', 'project_id', 'parent_id', 'kind', 'title', 'status',
                 'request_id', 'customer_id', 'invoice_id', 'stock_movement_id', 'created_by', 'approved_by', 'starts_at', 'ends_at'))):
        fail('Attribution cannot rewrite the original certified financial source', 403)
    validate_measurement_quantity(db, actor, row)


@router.post('/measurements/{ident}/work-package')
def attribute_measurement(ident: int, data: MeasurementAttributionInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    from app.apps.srm.industry_api import get, revision, audit, out
    scope = db.info.get('business_pack_scope')
    if scope is None or scope.pack_key != 'construction':
        fail('A selected Construction attribution context is required', 403)
    # Serialize retries and remaining allocation against the native company lock.
    from app.apps.srm.industry_api import context
    from .common_core import _native_authority
    from .construction import _project_epoch
    before_wait = _native_authority(db, actor, scope.company_id)
    context(db, actor, True)
    if before_wait != _native_authority(db, actor, scope.company_id):
        fail('Native attribution authority changed while waiting', 403)
    row = get(db, actor, scope.branch_id, ident, 'measurement')
    scope = _attribution_access(db, actor, row)
    marker = row.data.get('_work_package_attribution')
    if marker and marker.get('request_id') == str(data.request_id):
        if (marker.get('actor_id') != actor.id or marker.get('work_package_id') != data.work_package_id
                or marker.get('from_revision') != data.expected_revision or marker.get('reason') != data.reason):
            fail('Attribution request was already used with different details')
        return out(row)
    revision(row, data.expected_revision)
    if row.status != 'approved' or row.data.get('work_package_id') is not None:
        fail('Only a certified measurement without work package attribution can be reconciled')
    if not data.reason.strip():
        fail('Enter an independent attribution reason', 422)
    source = measurement_source(db, actor, row.parent_id, data.work_package_id)
    original = db.connection().execute(select(IndustryRecord.__table__).where(IndustryRecord.__table__.c.id == row.id)).first()
    command = _Attribution(scope, row, actor, data, original,
        _native_authority(db, actor, scope.company_id), _project_epoch(db, scope, row.project_id))
    if db in _ATTRIBUTIONS:
        fail('Attribution commands cannot nest', 403)
    _ATTRIBUTIONS[db] = command
    try:
        row.data = {**row.data, **source}
        row.data = {**row.data, '_work_package_attribution': _attribution_marker(command)}
        row.revision += 1
        _validate_attribution_write(db, actor, scope, row)
        audit(db, actor, row, 'certified_work_package_attributed')
        db.flush()
        _validate_attribution_write(db, actor, scope, row)
        _attribution_access(db, actor, row)
        validate_measurement_quantity(db, actor, row)
        db.commit()
        return out(row)
    except Exception:
        db.rollback()
        raise
    finally:
        _ATTRIBUTIONS.pop(db, None)
