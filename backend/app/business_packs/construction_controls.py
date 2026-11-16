"""Approved cost/progress baselines and earned value over canonical PMS sources.

Cost budgets are allocations of PMS estimated_cost, never BOQ selling prices.
Actual cost remains the canonical PMS actual_cost, so stock costs are not added
twice. Physical earned value requires certified quantities linked to a WBS row.
"""
import hashlib
import json
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from uuid import UUID
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.apps.srm.industry_models import IndustryRecord
from .construction import _source, project_for_action
from .construction import _project_epoch
from .common_core import _native_authority
from .operations import require

router = APIRouter(tags=['Construction planning controls'])
_COMMANDS = WeakKeyDictionary()
ZERO = Decimal(0)


def fail(message, status=409):
    raise HTTPException(status, message)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class BaselineInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    title: str = Field(min_length=1, max_length=220)
    project_id: int = Field(gt=0)
    native_baseline_id: UUID


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1)
    status: str = Field(pattern='^(approved|rejected)$')
    reason: str = Field(default='', max_length=2000)


def access(db, actor, project_id, *, write=False, approve=False):
    from app.apps.srm.industry_api import context
    from app.access.service import check_background_access
    require(db, actor, 'boq.approve' if approve else ('boq.prepare' if write else 'sites.view'))
    scope = _source(db, actor, project_id)[0]
    authority = _native_authority(db, actor, scope.company_id)
    context(db, actor, write)
    if authority != _native_authority(db, actor, scope.company_id):
        fail('Native planning control authority changed while waiting', 403)
    if write:
        check_background_access(db, actor, 'srm', 'create', stamp=False)
        from .catalog_management import _module_grant
        grant = _module_grant(db, actor, scope, 'srm')
        if not grant.get('enabled') or 'create' not in grant.get('actions', ()):
            fail('Fresh native Sales create authority is required for planning control writes', 403)
    project_for_action(db, actor, project_id, 'approve' if approve else ('manage_tasks' if write else 'browse'))
    return _source(db, actor, project_id)[0]


def financial_source(db, actor, project_id):
    from app.apps.project_management.models import PMSProject
    from app.shared.settings import effective
    project = project_for_action(db, actor, project_id)
    scope, _ = _source(db, actor, project_id)
    table = PMSProject.__table__
    row = db.connection().execute(select(table.c.estimated_cost, table.c.actual_cost).where(
        table.c.id == project_id, table.c.organization_id == scope.company_id,
        table.c.branch_id == scope.branch_id)).one()
    company_currency = effective(db, scope.company_id, 'srm')['values']['currency']
    if project.currency != company_currency:
        fail('PMS costs have no separate currency field; reconcile project and company cost currency first')
    return project.currency, row.estimated_cost, row.actual_cost


def basis(db, actor, project_id, native_baseline_id):
    from app.apps.srm.industry_api import query
    from app.apps.project_management.scheduling import CalendarSpec
    from .construction_planning import baseline_source, task_sources
    from .construction_workpackages import validate_work_package_source
    scope = _source(db, actor, project_id)[0]
    native = baseline_source(db, actor, project_id, str(native_baseline_id))
    if 'calendar' not in native:
        fail('Capture a native PMS baseline with its working calendar before preparing cost/progress approval')
    calendar = CalendarSpec.model_validate(native['calendar']).model_dump(mode='json')
    dates = {row['id']: row for row in native['tasks']}
    if set(dates) != {task['id'] for task in task_sources(db, actor, project_id)}:
        fail('The actual WBS task set changed; capture and approve a revised native baseline')
    if any(not task.get('start_date') or not task.get('due_date') for task in dates.values()):
        fail('Date every native WBS task before approving the project baseline')
    rows = query(db, actor, scope.branch_id).filter_by(project_id=project_id).filter(
        IndustryRecord.kind.in_(('boq', 'variation', 'work_package'))).all()
    boqs = [row for row in rows if row.kind in {'boq', 'variation'} and row.status == 'approved']
    packages = [row for row in rows if row.kind == 'work_package' and row.status == 'mapped']
    if not boqs or not packages:
        fail('Prepare approved BOQ scope and canonical WBS work packages first')
    currency, estimated, _ = financial_source(db, actor, project_id)
    if estimated is None or estimated <= 0:
        fail('Set the canonical PMS estimated cost before approving a cost baseline')
    quantities = {}
    snapshots = []
    total = ZERO
    for package in sorted(packages, key=lambda row: row.id):
        validate_work_package_source(db, scope, package, write=False)
        task_id = package.data['task_id']
        planned = dates.get(task_id)
        if not planned or not planned['start_date'] or not planned['due_date']:
            fail('Every work package requires dates in this native PMS baseline')
        start, end = date.fromisoformat(planned['start_date']), date.fromisoformat(planned['due_date'])
        if end < start:
            fail('Native baseline dates require reconciliation')
        if package.data['currency'] != currency:
            fail('Work package currency differs from the cost baseline')
        quantity, budget = Decimal(package.data['quantity']), Decimal(package.data['budget_cost'])
        quantities[package.parent_id] = quantities.get(package.parent_id, ZERO) + quantity
        total += budget
        snapshots.append({'id': package.id, 'revision': package.revision, 'task_id': task_id,
            'boq_id': package.parent_id, 'quantity': str(quantity), 'budget_cost': str(budget),
            'unit': package.data['unit'], 'start_date': start.isoformat(), 'due_date': end.isoformat()})
    scope_rows = []
    for row in sorted(boqs, key=lambda row: row.id):
        if row.data['currency'] != currency or quantities.get(row.id, ZERO) != Decimal(row.data['quantity']):
            fail('Allocate every approved BOQ quantity exactly once across the WBS before baseline approval')
        scope_rows.append({'id': row.id, 'revision': row.revision, 'quantity': row.data['quantity'],
            'unit': row.data['unit'], 'unit_rate': row.data['unit_rate'], 'currency': row.data['currency']})
    if set(quantities) != {row.id for row in boqs} or total != estimated:
        fail('Work package cost allocations must equal the canonical PMS estimated cost')
    return {'native_baseline': native, 'calendar': calendar, 'work_packages': snapshots,
        'scope': scope_rows, 'currency': currency, 'budget_at_completion': str(total),
        'cost_source': 'PMSProject.estimated_cost; BOQ selling prices are excluded'}


@contextmanager
def command(db, row, action):
    from app.models.user import User
    if db in _COMMANDS:
        fail('Construction baseline commands cannot nest', 403)
    scope = db.info['business_pack_scope']
    _COMMANDS[db] = (row, action, _native_authority(db, db.get(User, scope.user_id), scope.company_id), _project_epoch(db, scope, row.project_id))
    try:
        yield
    finally:
        _COMMANDS.pop(db, None)


def validate_baseline_record(db, scope, row):
    if type(row) is not IndustryRecord or row.kind != 'planning_baseline':
        return
    from app.models.user import User
    actor = db.get(User, scope.user_id)
    current = _COMMANDS.get(db)
    state = inspect(row)
    if current is not None:
        if (current[2] != _native_authority(db, actor, scope.company_id)
                or current[3] != _project_epoch(db, scope, row.project_id)):
            fail('Native planning control authority changed before saving', 403)
        access(db, actor, row.project_id, write=True, approve=current[1] == 'review')
    if not state.persistent:
        if (current is None or current[:2] != (row, 'create') or row.status != 'draft' or row.created_by != actor.id
                or row.approved_by is not None or row.parent_id is not None or row.invoice_id is not None):
            fail('A typed baseline preparation command is required', 403)
    elif any(attr.history.has_changes() for attr in state.attrs):
        if current is None or current[:2] != (row, 'review'):
            fail('Construction planning baselines are immutable outside independent review', 403)
        original = db.connection().execute(select(IndustryRecord.__table__).where(IndustryRecord.__table__.c.id == row.id)).one()
        unchanged = {key: value for key, value in row.data.items() if key != 'review_reason'}
        if original.status != 'draft' or row.status not in {'approved', 'rejected'} or unchanged != original.data:
            fail('Approved/rejected baseline evidence is immutable', 403)
        if actor.id in {row.created_by, row.data['native_baseline']['author_id']} or row.approved_by != actor.id:
            fail('A different native project approver must approve the baseline', 403)
    if current is not None:
        expected = basis(db, actor, row.project_id, row.data['native_baseline']['id'])
        if any(row.data.get(key) != value for key, value in expected.items()):
            fail('Native schedule, BOQ, WBS allocation or cost budget changed; prepare a fresh baseline')


def prepare(data, db, actor):
    from app.apps.srm.industry_api import query, digest, audit, out
    scope = access(db, actor, data.project_id, write=True)
    prior = query(db, actor, scope.branch_id).filter_by(request_id=str(data.request_id)).first()
    if prior:
        if prior.kind != 'planning_baseline' or prior.data.get('_request_digest') != digest(data):
            fail('Baseline request was already used with different details')
        return out(prior)
    snapshot = basis(db, actor, data.project_id, str(data.native_baseline_id))
    row = IndustryRecord(organization_id=scope.company_id, branch_id=scope.branch_id,
        project_id=data.project_id, kind='planning_baseline', title=data.title,
        request_id=str(data.request_id), created_by=actor.id, status='draft', revision=1,
        data={**snapshot, '_request_digest': digest(data)})
    with command(db, row, 'create'):
        db.add(row); db.flush()
        audit(db, actor, row, 'baseline_prepared')
        validate_baseline_record(db, scope, row)
        db.commit()
    return out(row)


def review(ident, data, db, actor):
    from .construction import authorize_record_project
    from app.apps.srm.industry_api import get, revision, audit, out
    authorize_record_project(db, actor, ident)
    scope = db.info.get('business_pack_scope')
    row = get(db, actor, scope.branch_id, ident, 'planning_baseline')
    access(db, actor, row.project_id, write=True, approve=True)
    revision(row, data.expected_revision)
    if row.status != 'draft':
        fail('Only a draft planning baseline can be reviewed')
    if actor.id in {row.created_by, row.data['native_baseline']['author_id']}:
        fail('A different native project approver must review the baseline', 403)
    if data.status == 'rejected' and not data.reason.strip():
        fail('Enter a rejection reason', 422)
    with command(db, row, 'review'):
        row.status, row.approved_by, row.revision = data.status, actor.id, row.revision + 1
        row.data = {**row.data, 'review_reason': data.reason.strip()}
        audit(db, actor, row, 'baseline_' + data.status)
        validate_baseline_record(db, scope, row)
        db.commit()
    return out(row)


def working_days(start, end, calendar):
    if end < start:
        return []
    if (end - start).days > 3660:
        fail('Construction performance reporting supports at most ten years per work package', 422)
    holidays = {date.fromisoformat(day) for day in calendar['holidays']}
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() in calendar['weekdays'] and start + timedelta(days=offset) not in holidays]


def parsed_date(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


def metrics(db, actor, project_id, baseline_id, as_of):
    from app.apps.srm.industry_api import get, query
    from .construction_planning import task_sources
    access(db, actor, project_id)
    scope = _source(db, actor, project_id)[0]
    baseline = get(db, actor, scope.branch_id, baseline_id, 'planning_baseline')
    if baseline.project_id != project_id or baseline.status != 'approved':
        fail('Choose an independently approved baseline for this project')
    current = basis(db, actor, project_id, baseline.data['native_baseline']['id'])
    if any(baseline.data.get(key) != value for key, value in current.items()):
        fail('Scope or WBS cost allocation changed; approve a revised baseline before project-wide analysis')
    packages = {row['id']: row for row in baseline.data['work_packages']}
    measurements = query(db, actor, scope.branch_id).filter_by(project_id=project_id, kind='measurement', status='approved').all()
    quantities = {ident: ZERO for ident in packages}
    for row in measurements:
        if date.fromisoformat(row.data['measured_on']) > as_of:
            continue
        ident = row.data.get('work_package_id')
        if ident not in packages or row.parent_id != packages[ident]['boq_id']:
            fail('Certified actual quantities need their exact WBS work package before earned-value reporting')
        quantities[ident] += Decimal(row.data['quantity'])
    planned, earned, units = ZERO, ZERO, {}
    calendar = baseline.data['calendar']
    all_dates = []
    for ident, package in packages.items():
        quantity, budget = Decimal(package['quantity']), Decimal(package['budget_cost'])
        actual = quantities[ident]
        if actual > quantity:
            fail('Certified work package quantities exceed the approved baseline')
        days = working_days(date.fromisoformat(package['start_date']), date.fromisoformat(package['due_date']), calendar)
        if not days:
            fail('A baseline work package has no working days; reconcile its calendar')
        all_dates.extend(days)
        planned += budget * Decimal(sum(day <= as_of for day in days)) / Decimal(len(days))
        earned += budget * actual / quantity
        units[package['unit']] = units.get(package['unit'], ZERO) + actual
    currency, _, actual_cost = financial_source(db, actor, project_id)
    # The canonical actual_cost field is current, not a dated cost ledger.
    cost_available = actual_cost is not None and as_of == date.today()
    if actual_cost is not None and actual_cost < 0:
        fail('Reconcile a negative canonical PMS actual cost before earned-value reporting')
    cost = Decimal(actual_cost) if cost_available else None
    cost_source = 'Current canonical PMSProject.actual_cost, without adding stock costs again'
    if as_of < date.today():
        history = query(db, actor, scope.branch_id).filter_by(project_id=project_id, kind='cost_actual').all()
        history = [row for row in history if row.data.get('source_project_id') == project_id
            and row.data.get('as_of') and date.fromisoformat(row.data['as_of']) <= as_of]
        history.sort(key=lambda row: (row.data['as_of'], row.id), reverse=True)
        if history:
            latest = history[0]
            if latest.data['currency'] != currency:
                fail('The dated actual-cost source has another currency; reconcile it before reporting')
            cost = Decimal(latest.data['cumulative_actual_cost'])
            if cost < 0:
                fail('The dated actual-cost source requires reconciliation')
            cost_available = True
            cost_source = f"Dated canonical PMS actual-cost change #{latest.id}, posted as of {latest.data['as_of']}"
    bac = Decimal(baseline.data['budget_at_completion'])
    spi = earned / planned if planned else None
    cpi = earned / cost if cost and cost > 0 else None
    eac = bac / cpi if cpi else None
    elapsed = len(working_days(min(all_dates), as_of, calendar))
    forecast = None
    if earned >= bac:
        forecast = as_of.isoformat()
    elif earned > 0 and elapsed:
        remaining = int(((bac - earned) / (earned / Decimal(elapsed))).to_integral_value(rounding=ROUND_CEILING))
        cursor = as_of
        for _ in range(3661):
            if not remaining:
                forecast = cursor.isoformat(); break
            cursor += timedelta(days=1)
            if working_days(cursor, cursor, calendar):
                remaining -= 1
    tasks = task_sources(db, actor, project_id)
    original_dates = {row['id']: row for row in baseline.data['native_baseline']['tasks']}
    delays = [{'task_id': row['id'], 'variance_calendar_days': (parsed_date(row['due_date']) - parsed_date(original_dates[row['id']]['due_date'])).days}
        for row in tasks if row['id'] in original_dates and row.get('due_date') and original_dates[row['id']].get('due_date')]
    diaries = query(db, actor, scope.branch_id).filter_by(project_id=project_id, kind='site_diary').all()
    daily_headcounts = {}
    for row in diaries:
        day = date.fromisoformat(row.data['entry_date'])
        if min(all_dates) <= day <= as_of:
            daily_headcounts[day] = max(daily_headcounts.get(day, 0), int(row.data.get('workforce', 0)))
    workforce_days = sum(daily_headcounts.values())
    def number(value):
        return str(value.quantize(Decimal('0.01'))) if value is not None else None
    return {'project_id': project_id, 'baseline_id': baseline.id, 'as_of': as_of.isoformat(), 'currency': currency,
        'BAC': number(bac), 'PV': number(planned), 'EV': number(earned), 'AC': number(cost),
        'CPI': number(cpi), 'SPI': number(spi), 'CV': number(earned - cost) if cost is not None else None,
        'SV': number(earned - planned), 'EAC': number(eac), 'ETC': number(eac - cost) if eac is not None else None,
        'VAC': number(bac - eac) if eac is not None else None, 'physical_progress_percent': number(earned * 100 / bac),
        'forecast_completion': forecast, 'forecast_basis': 'Constant certified cost-weighted physical progress per elapsed baseline working day; not a guarantee',
        'actual_cost_source': cost_source,
        'cost_unavailable_reason': None if cost_available else 'Canonical PMS actual_cost is missing or this is a historical/future as-of date; no dated actual cost was invented',
        'task_delay_variance': delays, 'workforce_days': workforce_days,
        'physical_progress_basis': 'Approved work-package cost weights applied to certified quantities, not a count of completed tasks',
        'certified_quantities_by_unit': {unit: str(value) for unit, value in units.items()},
        'certified_quantity_per_workforce_day_by_unit': {unit: number(value / workforce_days) if workforce_days else None for unit, value in units.items()},
        'productivity_basis': 'Certified quantities by unit per maximum recorded daily site headcount, a workforce-day proxy rather than payroll hours; same-day diaries and different units are never added together'}


@router.post('/planning-baselines', status_code=201)
def create_baseline(data: BaselineInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    return prepare(data, db, actor)


@router.post('/planning-baselines/{ident}/review')
def review_baseline(ident: int, data: ReviewInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    return review(ident, data, db, actor)


@router.get('/projects/{project_id}/planning-baselines')
def list_baselines(project_id: int, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    from app.apps.srm.industry_api import query, out
    scope = access(db, actor, project_id)
    return {'items': [out(row) for row in query(db, actor, scope.branch_id).filter_by(project_id=project_id, kind='planning_baseline').order_by(IndustryRecord.id.desc()).all()]}


@router.get('/projects/{project_id}/planning-tasks')
def planning_tasks(project_id: int, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    from .construction_planning import task_sources
    access(db, actor, project_id)
    return {'items': task_sources(db, actor, project_id)}


@router.get('/projects/{project_id}/cost-source')
def cost_source(project_id: int, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    access(db, actor, project_id)
    currency, estimated, actual = financial_source(db, actor, project_id)
    return {'project_id': project_id, 'currency': currency,
        'estimated_cost': str(estimated) if estimated is not None else None,
        'actual_cost': str(actual) if actual is not None else None}


@router.get('/projects/{project_id}/performance')
def performance(project_id: int, baseline_id: int, as_of: date, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    return metrics(db, actor, project_id, baseline_id, as_of)


@router.get('/projects/{project_id}/client-report')
def client_report(project_id: int, baseline_id: int, as_of: date, format: str = 'json', db: Session = Depends(get_db), actor=Depends(get_current_user)):
    from fastapi.responses import Response
    from .construction_delivery import client_report as report, export_data
    if format not in {'json', 'csv'}:
        fail('Choose JSON or CSV for the client report', 422)
    result = report(db, actor, project_id, metrics=metrics(db, actor, project_id, baseline_id, as_of))
    content, media_type, filename = export_data(result, f'construction-client-report-{project_id}', format)
    return Response(content, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="{filename}"'})
