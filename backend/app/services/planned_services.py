"""Read-only HRMS projection of services assigned to an employee.

This is an explicit derived-read adapter, not a general Sales record query.
Reception can create an appointment on behalf of a specialist, so its creator
is not its workforce owner. After independently checking native HRMS rights,
employee/branch assignment and live pack scope, the bounded Core projection
selects only schedule fields for that employee. It never exposes appointment
notes, customers, payments or creates actual timesheet/attendance/payroll work.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
import jwt
from jwt import PyJWTError as JWTError
from sqlalchemy import JSON, String, and_, case, cast, exists, func, inspect, literal, or_, select

from app.core.config import settings
from app.models.employee import Employee
from app.models.company import Branch, Company
from app.models.user import User, Permission, role_permissions
from app.branches.service import BranchContext


STATUSES = frozenset({'booked', 'checked_in', 'in_service', 'completed', 'cancelled', 'no_show'})
BLOCKING = frozenset({'booked', 'checked_in', 'in_service'})
_AUDIENCE = 'employee-planned-services-page'


def _fail(detail, status=403):
    raise HTTPException(status, detail)


def _positive(value):
    return type(value) is int and 0 < value <= 2147483647


def _utc(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        _fail('Planned service range requires timezone-aware dates', 422)
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        _fail('Planned service dates are outside the supported range', 422)


def _stored_utc(value):
    # SQLite stores the UTC-normalized appointment timestamps without tzinfo.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _actor_and_branch(db, actor, supplied):
    from app.core.tenant_boundary import company_ids
    from app.branches.service import context
    if not isinstance(supplied, BranchContext) or not _positive(supplied.company_id):
        _fail('Verified employee schedule branch context is required')
    company = supplied.company_id
    row = db.connection().execute(select(User.id, User.role_id, User.is_active, User.is_superuser).where(User.id == actor.id)).mappings().first()
    if (not row or not row['is_active'] or not actor.is_active
            or row['is_superuser'] != bool(actor.is_superuser) or row['role_id'] != actor.role_id
            or getattr(actor, 'organization_id', company) != company):
        _fail('Active verified employee schedule actor is required')
    if not actor.is_superuser and company not in company_ids(db, actor):
        _fail('Employee schedule company membership is required')
    if not db.connection().execute(select(Company.id).where(Company.id == company, Company.is_active.is_(True))).first():
        _fail('Employee schedule company is unavailable')
    # Re-resolve rights; a retained BranchContext must not survive revocation.
    fresh = context(db, actor, company, supplied.branch_id if supplied.branch_id is not None else 'all')
    return company, fresh


def _modules(db, company):
    from app.module_registry import is_app_enabled
    from app.access.entitlements import states
    if not is_app_enabled('hrms') or not is_app_enabled('srm'):
        _fail('Planned services require HRMS and shared appointment scheduling', 404)
    state = states(db, company)
    if state.get('hrms') is False or state.get('srm') is False:
        _fail('Planned services are unavailable in the current approved modules')
    inspector = inspect(db.connection())
    if not inspector.has_table('srm_industry_records'):
        _fail('Shared appointment scheduling is not installed', 404)
    required = {'id', 'organization_id', 'branch_id', 'kind', 'revision', 'status', 'data', 'starts_at', 'ends_at'}
    if not required <= {column['name'] for column in inspector.get_columns('srm_industry_records')}:
        _fail('Shared appointment scheduling installation is incomplete', 503)


def _native_employee_predicate(db, actor, company, branch_id):
    """Return a SQL employee scope after refreshing the native HRMS authority."""
    from app.access.models import AccessPolicy, AccessRole
    from app.access.service import resolved_grants, legacy_grants
    from app.branches.roles import effective_grants
    from app.branches.service import company_administrator
    policy = db.query(AccessPolicy).filter_by(user_id=actor.id, company_id=company).populate_existing().first()
    if policy and policy.status != 'active':
        _fail('Employee schedule access is revoked')
    own = Employee.user_id == actor.id
    if actor.is_superuser or company_administrator(db, actor, company):
        return literal(True)
    from app.branches.models import BranchGrant
    branch_override = db.connection().execute(select(BranchGrant.module_grants).where(
        BranchGrant.company_id == company, BranchGrant.user_id == actor.id,
        BranchGrant.branch_id == branch_id)).scalar_one_or_none()
    role_ids = {grant.get('hrms', {}).get('roleId') for grant in
                ([policy.grants] if policy else []) + ([branch_override] if branch_override else [])}
    role_ids.discard(None)
    if role_ids:
        # Centrally managed roles may have changed since the supplied actor or
        # pack scope was first loaded. Refresh only the exact referenced roles.
        db.query(AccessRole).filter(AccessRole.id.in_(role_ids)).populate_existing().all()
    base = resolved_grants(db, policy) if policy else legacy_grants(db, actor, company, administrative_read=False)
    if not policy:
        fresh_names = set(db.connection().execute(select(Permission.name).join(
            role_permissions, role_permissions.c.permission_id == Permission.id).where(
            role_permissions.c.role_id == actor.role_id)).scalars())
        # Cached ORM relationships may retain a now-revoked legacy permission.
        base = {key: {**grant, 'permissions': sorted(set(grant.get('permissions', [])) & fresh_names)}
                for key, grant in base.items()}
    missing = object()
    previous = getattr(actor, '_suite_branch_roles_fingerprint', missing)
    try:
        grants = effective_grants(db, actor, company, branch_id, base)
        if grants is None:
            grants = base
    finally:
        if previous is missing:
            actor.__dict__.pop('_suite_branch_roles_fingerprint', None)
        else:
            actor._suite_branch_roles_fingerprint = previous
    grant = grants.get('hrms', {})
    names = set(grant.get('permissions', []))
    if not grant.get('enabled') or 'view' not in grant.get('actions', []) or not names.intersection({'employee_view', 'timesheet_view', 'hr_admin'}):
        _fail('Native HRMS schedule viewing permission is required')
    own_employee = db.connection().execute(select(Employee.id, Employee.department_id).where(
        Employee.user_id == actor.id, Employee.deleted_at.is_(None), Employee.branch_id == branch_id,
    )).mappings().first()
    scope = grant.get('scope', 'own')
    if scope in {'organization', 'all', 'branch'}:
        return literal(True)
    if scope == 'team' and own_employee:
        return or_(own, Employee.reporting_manager_id == own_employee['id'])
    if scope == 'department' and own_employee and own_employee['department_id'] is not None:
        return or_(own, Employee.department_id == own_employee['department_id'])
    # Preserve explicit legacy HR authority; arbitrary role names do not count.
    if not policy and branch_override is None:
        if 'hr_admin' in names:
            return literal(True)
        if 'timesheet_approve' in names and own_employee:
            return or_(own, Employee.reporting_manager_id == own_employee['id'])
    return own


def _native_employee_access(db, actor, company, employee):
    allowed = _native_employee_predicate(db, actor, company, employee['branch_id'])
    if not db.connection().execute(select(Employee.id).where(Employee.id == employee['id'], allowed)).first():
        _fail('Employee planned services are outside your authorized workforce scope', 404)


def _pack(db, actor, branch_ctx, supplied):
    from app.business_packs.access import PackScope, resolve_context
    if supplied is not None and not isinstance(supplied, PackScope):
        _fail('A verified Business Pack scope is required')
    current = resolve_context(db, actor, branch_ctx, supplied.context_id if supplied else None)
    if supplied is not None and current != supplied:
        _fail('Business Pack schedule access changed; resolve the current context again')
    if current is not None and not {
        current.pack_key + '.appointments.view', current.pack_key + '.planned_services.view',
    }.intersection(current.capabilities):
        _fail('The assigned Business Pack role does not allow planned service schedules')
    return current


def _ownership(db, table, company, branch, pack, *, master=False):
    from app.business_packs.models import PackRecordOwnership, PackMasterAvailability
    if not inspect(db.connection()).has_table(PackRecordOwnership.__tablename__):
        return literal(True) if pack is None else literal(False)
    anchor = PackRecordOwnership.__table__
    # An SQL alias never changes a native record's immutable ownership table.
    source_name = getattr(table, 'original', table).name
    identity = and_(anchor.c.resource_table == source_name, anchor.c.resource_key == cast(table.c.id, String))
    if pack is None:
        # Any anchor, including a corrupt foreign-company anchor, excludes legacy.
        return ~exists(select(1).where(identity)).correlate(table)
    allowed = exists(select(1).where(identity, anchor.c.context_id == pack.context_id,
        anchor.c.company_id == company, anchor.c.branch_id == branch)).correlate(table)
    if master:
        availability = PackMasterAvailability.__table__
        shared = exists(select(1).where(availability.c.resource_table == source_name,
            availability.c.resource_key == cast(table.c.id, String), availability.c.context_id == pack.context_id,
            availability.c.company_id == company, availability.c.branch_id == branch,
            availability.c.active.is_(True))).correlate(table)
        allowed = or_(allowed, shared)
    return allowed


def _resources_match(db, appointments, resource_ids):
    if db.get_bind().dialect.name == 'postgresql':
        values = appointments.c.data['resource_ids']
        safe = case((func.json_typeof(values) == 'array', values), else_=cast('[]', JSON))
        resources = func.json_array_elements_text(safe).table_valued('value').render_derived(name='planned_service_resources')
    elif db.get_bind().dialect.name == 'sqlite':
        safe = case((func.json_type(appointments.c.data, '$.resource_ids') == 'array',
                     func.json_extract(appointments.c.data, '$.resource_ids')), else_='[]')
        resources = func.json_each(safe).table_valued('value').alias('planned_service_resources')
    else:
        _fail('Planned service projection requires PostgreSQL or SQLite', 503)
    return exists(select(1).select_from(resources).where(cast(resources.c.value, String).in_(resource_ids))).correlate(appointments)


def _cursor_scope(actor, company, branch, employee_id, pack, start, end, statuses):
    values = [1, actor.id, company, branch, employee_id, pack.context_id if pack else None,
              start.isoformat(), end.isoformat(), sorted(statuses)]
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def _decode_cursor(value, scope):
    if not isinstance(value, str) or not value or len(value) > 4096:
        _fail('Invalid planned service cursor', 422)
    try:
        data = jwt.decode(value, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], audience=_AUDIENCE)
        if data.get('scope') != scope or not _positive(data.get('id')):
            raise ValueError()
        return _utc(datetime.fromisoformat(data['at'])), data['id']
    except (JWTError, ValueError, TypeError, KeyError, OverflowError):
        _fail('Invalid or expired planned service cursor for this request', 422)


def _request_range(from_at, until_at, limit, statuses):
    if type(limit) is not int or not 1 <= limit <= 100:
        _fail('Choose a planned service page size from 1 to 100', 422)
    start, end = _utc(from_at), _utc(until_at)
    if end <= start or end - start > timedelta(days=93):
        _fail('Planned service range must be positive and at most 93 days', 422)
    if statuses is None:
        statuses = STATUSES
    elif (not isinstance(statuses, (list, tuple, set, frozenset)) or not statuses
            or len(statuses) > len(STATUSES) or any(not isinstance(value, str) or value not in STATUSES for value in statuses)):
        _fail('Choose supported planned service statuses', 422)
    return start, end, frozenset(statuses)


def _service_item(row):
    service = row['service_id']
    if not isinstance(service, str) or not service.isascii() or not service.isdigit() or len(service) > 10 or not _positive(int(service)) or not isinstance(row['service_name'], str) or not row['service_name'].strip():
        _fail('Assigned service schedule metadata is incomplete', 503)
    begins, finishes = _stored_utc(row['starts_at']), _stored_utc(row['ends_at'])
    minutes = Decimal(str((finishes - begins).total_seconds())) / Decimal(60)
    return {'appointment_id': row['id'], 'revision': row['revision'], 'service_id': int(service),
            'service_name': row['service_name'], 'starts_at': begins.isoformat(), 'ends_at': finishes.isoformat(),
            'planned_minutes': int(minutes) if minutes == int(minutes) else float(minutes),
            'status': row['status'], 'blocks_availability': row['status'] in BLOCKING}


def _booking_resources(db, rows, company, pack):
    """Only room/equipment labels from the already-authorized booking page."""
    from app.apps.srm.industry_models import IndustryRecord
    table = IndustryRecord.__table__
    ids = {ident for row in rows for ident in (row['resource_ids'] if isinstance(row['resource_ids'], list) else [])[:10] if _positive(ident)}
    if not ids:
        return {}
    resources = db.connection().execute(select(table.c.id, table.c.branch_id, table.c.title,
        table.c.data['resource_type'].as_string().label('resource_type')).where(
        table.c.id.in_(ids), table.c.organization_id == company, table.c.kind == 'resource',
        table.c.data['resource_type'].as_string().in_(('room', 'chair', 'equipment', 'location')),
        _ownership(db, table, company, pack.branch_id if pack else None, pack, master=True))
        .order_by(table.c.title, table.c.id)).mappings().all()
    return {row['id']: [{'id': resource['id'], 'name': resource['title'], 'resource_type': resource['resource_type']}
        for resource in resources if resource['branch_id'] == row['branch_id'] and resource['id'] in (row['resource_ids'] or [])]
        for row in rows}


def planned_services(db, actor, branch_ctx, employee_id, from_at, until_at, pack_scope=None, *, limit=100, cursor=None, statuses=None):
    """One bounded projection for employee profiles, schedules and HRMS sheets."""
    if not _positive(employee_id) or type(limit) is not int or not 1 <= limit <= 100:
        _fail('Choose a valid employee and a planned service page size from 1 to 100', 422)
    start, end, statuses = _request_range(from_at, until_at, limit, statuses)
    company, fresh_branch = _actor_and_branch(db, actor, branch_ctx)
    _modules(db, company)
    employee = db.connection().execute(select(Employee.id, Employee.user_id, Employee.branch_id,
        Employee.department_id, Employee.reporting_manager_id, Employee.work_categories).join(Branch, Branch.id == Employee.branch_id).where(
        Employee.id == employee_id, Employee.deleted_at.is_(None), Branch.company_id == company,
        Branch.is_active.is_(True), Branch.id.in_(fresh_branch.allowed),
        *([Branch.id == fresh_branch.branch_id] if fresh_branch.branch_id is not None else []),
    )).mappings().first()
    if not employee:
        _fail('Employee planned service schedule not found', 404)
    _native_employee_access(db, actor, company, employee)
    pack = _pack(db, actor, fresh_branch, pack_scope)
    branch = employee['branch_id']
    if pack is not None and (pack.company_id != company or pack.branch_id != branch):
        _fail('Employee planned service schedule not found', 404)
    from app.shared.form_defaults import effective
    zone = effective(db, company, 'hrms', branch)['values']['timezone']
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        _fail('Employee schedule timezone is unavailable', 503)
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.industry_api import PROVIDER_TYPES
    table = IndustryRecord.__table__
    resource = table.alias('planned_service_provider')
    linked_employee = cast(resource.c.data['employee_id'].as_string(), String) == str(employee_id)
    if employee['user_id'] is not None:
        # Legacy providers can identify a staff account only. Employee.user_id
        # is unique, so this fallback is a verified native link, not a name match.
        linked_employee = or_(linked_employee, and_(resource.c.data['employee_id'].as_string().is_(None),
            cast(resource.c.data['user_id'].as_string(), String) == str(employee['user_id'])))
    provider_ids = select(cast(resource.c.id, String)).where(resource.c.organization_id == company,
        resource.c.branch_id == branch, resource.c.kind == 'resource',
        resource.c.data['resource_type'].as_string().in_(PROVIDER_TYPES), linked_employee,
        _ownership(db, resource, company, branch, pack, master=True))
    query = select(table.c.id, table.c.revision, table.c.starts_at, table.c.ends_at, table.c.status,
        table.c.branch_id, table.c.data['resource_ids'].label('resource_ids'),
        cast(table.c.data['service_id'].as_string(), String).label('service_id'),
        table.c.data['service_name'].as_string().label('service_name')).where(
        table.c.organization_id == company, table.c.branch_id == branch, table.c.kind == 'appointment',
        table.c.status.in_(statuses), table.c.starts_at.is_not(None), table.c.ends_at.is_not(None),
        table.c.starts_at < end, table.c.ends_at > start, table.c.ends_at > table.c.starts_at,
        _ownership(db, table, company, branch, pack), _resources_match(db, table, provider_ids))
    scope = _cursor_scope(actor, company, branch, employee_id, pack, start, end, statuses)
    if cursor is not None:
        after, ident = _decode_cursor(cursor, scope)
        query = query.where(or_(table.c.starts_at > after, and_(table.c.starts_at == after, table.c.id > ident)))
    rows = db.connection().execute(query.order_by(table.c.starts_at, table.c.id).limit(limit + 1)).mappings().all()
    more, rows = len(rows) > limit, rows[:limit]
    resources = _booking_resources(db, rows, company, pack)
    items = [{**_service_item(row), 'resources': resources.get(row['id'], []),
              'employee_categories': employee['work_categories'] or []} for row in rows]
    next_cursor = None
    if more and rows:
        last = rows[-1]
        next_cursor = jwt.encode({'aud': _AUDIENCE, 'scope': scope, 'id': last['id'],
            'at': _stored_utc(last['starts_at']).isoformat(),
            'exp': int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp())},
            settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {'employee_id': employee_id, 'company_id': company, 'branch_id': branch,
        'pack_context_id': pack.context_id if pack else None, 'timezone': zone,
        'from_at': start.isoformat(), 'until_at': end.isoformat(), 'items': items, 'next_cursor': next_cursor}


def scheduled_services(db, actor, branch_ctx, from_at, until_at, pack_scope=None, *,
                       employee_id=None, service_id=None, limit=100, cursor=None, statuses=None):
    """One SQL-authorized schedule across own/team/organization assignments.

    Workforce and source-context predicates run before paging and descriptors.
    A shared appointment assigned to two employees produces one row per employee;
    provider aliases for the same employee do not multiply that employee's row.
    """
    if any(value is not None and not _positive(value) for value in (employee_id, service_id)):
        _fail('Choose valid employee and service filters', 422)
    start, end, statuses = _request_range(from_at, until_at, limit, statuses)
    company, branch_ctx = _actor_and_branch(db, actor, branch_ctx)
    _modules(db, company)
    pack = _pack(db, actor, branch_ctx, pack_scope)
    selected_branch = pack.branch_id if pack else branch_ctx.branch_id
    branch_ids = [selected_branch] if selected_branch is not None else sorted(branch_ctx.allowed)
    workforce = []
    for branch_id in branch_ids:
        try:
            allowed = _native_employee_predicate(db, actor, company, branch_id)
        except HTTPException as error:
            if selected_branch is not None or error.status_code != 403:
                raise
            continue
        workforce.append(and_(Employee.branch_id == branch_id, allowed))
    if not workforce:
        _fail('Native HRMS schedule viewing permission is required')

    from app.apps.srm.industry_models import IndustryRecord
    table, employees = IndustryRecord.__table__, Employee.__table__
    provider = table.alias('scheduled_service_provider')
    provider_ids = select(cast(provider.c.id, String)).where(
        provider.c.organization_id == company, provider.c.branch_id == employees.c.branch_id,
        provider.c.kind == 'resource',
        cast(provider.c.data['employee_id'].as_string(), String) == cast(employees.c.id, String),
        _ownership(db, provider, company, pack.branch_id if pack else None, pack, master=True),
    ).correlate(employees)
    service_column = cast(table.c.data['service_id'].as_string(), String).label('service_id')
    name_column = table.c.data['service_name'].as_string().label('service_name')
    employee_name = func.trim(func.coalesce(employees.c.first_name, '') + ' ' + func.coalesce(employees.c.last_name, '')).label('employee_name')
    base = select(table.c.id, table.c.revision, table.c.starts_at, table.c.ends_at, table.c.status,
                  table.c.branch_id, table.c.data['resource_ids'].label('resource_ids'), employees.c.work_categories,
                  service_column, name_column, employees.c.id.label('employee_id'),
                  employee_name, employees.c.employee_id.label('employee_code')).select_from(
        table.join(employees, employees.c.branch_id == table.c.branch_id).join(
            Branch.__table__, Branch.id == employees.c.branch_id)).where(
        table.c.organization_id == company, table.c.kind == 'appointment',
        table.c.status.in_(statuses), table.c.starts_at.is_not(None), table.c.ends_at.is_not(None),
        table.c.starts_at < end, table.c.ends_at > start, table.c.ends_at > table.c.starts_at,
        employees.c.deleted_at.is_(None), Branch.company_id == company, Branch.is_active.is_(True),
        or_(*workforce), _ownership(db, table, company, pack.branch_id if pack else None, pack),
        _resources_match(db, table, provider_ids))

    # Descriptor lists come from this complete authorized range, not the loaded
    # page or public employee directory. Their explicit caps are never hidden.
    employee_options = db.connection().execute(base.with_only_columns(
        employees.c.id, employee_name, employees.c.employee_id).distinct().order_by(
            employee_name, employees.c.id).limit(201)).all()
    service_options = db.connection().execute(base.with_only_columns(service_column, name_column)
        .distinct().order_by(service_column, name_column).limit(201)).all()
    options = {
        'employees': [{'id': row[0], 'name': row[1], 'code': row[2]} for row in employee_options[:200]],
        'services': [], 'employees_complete': len(employee_options) <= 200,
        'services_complete': len(service_options) <= 200,
    }
    for ident, name in service_options[:200]:
        if not isinstance(ident, str) or not ident.isascii() or not ident.isdigit() or len(ident) > 10 or not _positive(int(ident)) or not isinstance(name, str) or not name.strip():
            _fail('Assigned service schedule metadata is incomplete', 503)
        options['services'].append({'id': int(ident), 'name': name})

    query = base
    if employee_id is not None:
        query = query.where(employees.c.id == employee_id)
    if service_id is not None:
        query = query.where(service_column == str(service_id))
    scope = hashlib.sha256(json.dumps(['scheduled-services-v1', actor.id, company, selected_branch,
        pack.context_id if pack else None, employee_id, service_id, start.isoformat(), end.isoformat(),
        sorted(statuses)], separators=(',', ':')).encode()).hexdigest()
    if cursor is not None:
        after, ident = _decode_cursor(cursor, scope)
        try:
            payload = jwt.decode(cursor, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], audience=_AUDIENCE)
            employee_after = payload['employee_id']
            if not _positive(employee_after):
                raise ValueError()
        except (JWTError, ValueError, TypeError, KeyError):
            _fail('Invalid scheduled service cursor', 422)
        query = query.where(or_(table.c.starts_at > after,
            and_(table.c.starts_at == after, table.c.id > ident),
            and_(table.c.starts_at == after, table.c.id == ident, employees.c.id > employee_after)))
    rows = db.connection().execute(query.order_by(table.c.starts_at, table.c.id, employees.c.id).limit(limit + 1)).mappings().all()
    more, rows = len(rows) > limit, rows[:limit]
    resources = _booking_resources(db, rows, company, pack)
    items = [{**_service_item(row), 'resources': resources.get(row['id'], []),
              'employee_categories': row['work_categories'] or [], 'employee_id': row['employee_id'],
              'employee_name': row['employee_name'], 'employee_code': row['employee_code']} for row in rows]
    next_cursor = None
    if more and rows:
        last = rows[-1]
        next_cursor = jwt.encode({'aud': _AUDIENCE, 'scope': scope, 'id': last['id'],
            'employee_id': last['employee_id'], 'at': _stored_utc(last['starts_at']).isoformat(),
            'exp': int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp())},
            settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    from app.shared.form_defaults import effective
    zone = effective(db, company, 'hrms', selected_branch)['values']['timezone']
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        _fail('Employee schedule timezone is unavailable', 503)
    return {'company_id': company, 'pack_context_id': pack.context_id if pack else None,
            'timezone': zone, 'from_at': start.isoformat(), 'until_at': end.isoformat(),
            'items': items, 'next_cursor': next_cursor, 'filter_options': options}
