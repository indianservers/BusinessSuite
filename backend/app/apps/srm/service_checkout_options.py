"""Minimal read-only POS scheduling choices with explicit native/context proof."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import String, and_, cast, exists, or_, select

from app.apps.srm.service_checkout import _scope, _source_scope, installation_ready
from app.apps.srm.service_checkout_models import ServiceBookingPolicy, ServiceSpecialistEligibility
from app.apps.srm.services.commercial import require, tenant
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMProduct
from app.models.employee import Employee
from app.models.company import Branch
from app.business_packs.models import PackRecordOwnership


def _authority(db, actor, selected=None):
    from app.access.service import check_background_access
    from app.branches.service import context
    from app.business_packs.access import resolve_context
    from app.apps.srm.industry_api import context as native_context
    if not actor.is_active:
        raise HTTPException(403, 'An active actor is required')
    require(actor, 'srm_manage', 'srm_admin')
    check_background_access(db, actor, 'srm', 'view')
    if not installation_ready(db):
        raise HTTPException(503, 'Service checkout installation is incomplete')
    company = tenant(actor)
    branch = getattr(db.info.get('branch_context'), 'branch_id', None)
    if not branch:
        raise HTTPException(409, 'Select one branch')
    fresh = context(db, actor, company, str(branch))
    scope = resolve_context(db, actor, fresh, requested_context_id=selected)
    installed = db.info.get('business_pack_scope')
    if installed is not None and installed != scope:
        raise HTTPException(403, 'Business Pack selection cannot change inside a request')
    if scope is not None and not any(scope.pack_key + '.' + key in scope.capabilities
            for key in ('appointments.schedule', 'providers.manage', 'settings.manage')):
        raise HTTPException(403, 'Assigned Business Pack role cannot view scheduling choices')
    if native_context(db, actor, appointments=True) != branch:
        raise HTTPException(403, 'Verified branch context changed')
    return company, branch, scope


def _owned_clause(model, company, branch, scope):
    """Private provider sources require anchors, never shared master availability."""
    from sqlalchemy import String, cast
    anchor = PackRecordOwnership.__table__
    proof = and_(anchor.c.resource_table == model.__tablename__, anchor.c.resource_key == cast(model.id, String))
    if scope is None:
        return ~exists(select(1).where(proof))
    return exists(select(1).where(proof, anchor.c.company_id == company,
        anchor.c.branch_id == branch, anchor.c.context_id == scope.context_id))


def _providers(db, company, branch, scope, *, search='', policy=None, offset=0, eligibility_id=None, target_employee_id=None, staff_assignments=False):
    from app.apps.srm.industry_api import PROVIDER_TYPES
    r, e = IndustryRecord, Employee
    employee_id = cast(r.data['employee_id'].as_string(), String)
    statement = select(r.id.label('provider_resource_id'), r.title.label('provider_name'),
        r.data['timezone'].as_string().label('timezone'), r.data['employee_id'].label('_employee_ref'), e.id.label('employee_id'), e.first_name, e.last_name, e.work_categories, e.profile_photo_url)
    statement = statement.select_from(r.__table__.join(e.__table__, cast(e.id, String) == employee_id).join(Branch.__table__, Branch.id == e.branch_id)).where(
        r.organization_id == company, r.branch_id == branch, r.kind == 'resource', r.status == 'active',
        r.data['resource_type'].as_string().in_(PROVIDER_TYPES), e.branch_id == branch, Branch.company_id == company,
        e.deleted_at.is_(None), e.status.in_(('Active', 'Probation', 'On Leave')),
        _owned_clause(r, company, branch, scope))
    if target_employee_id is not None:
        statement = statement.where(e.id == target_employee_id)
    if search:
        match = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        statement = statement.where(or_(r.title.ilike(match, escape='\\'), e.first_name.ilike(match, escape='\\'), e.last_name.ilike(match, escape='\\'), e.employee_id.ilike(match, escape='\\')))
    if policy is not None:
        eligibility = ServiceSpecialistEligibility
        statement = statement.add_columns(eligibility.id.label('eligibility_id'), eligibility.revision.label('eligibility_revision'))
        statement = statement.join(eligibility.__table__, eligibility.provider_resource_id == r.id)
        statement = _scope(statement, eligibility, company, branch, scope).where(
            eligibility.booking_policy_id == policy['id'], eligibility.service_product_id == policy['service_product_id'],
            eligibility.active.is_(True), or_(eligibility.effective_from.is_(None), eligibility.effective_from <= datetime.now(timezone.utc)),
            or_(eligibility.effective_until.is_(None), eligibility.effective_until > datetime.now(timezone.utc)),
            _owned_clause(eligibility, company, branch, scope))
    if policy is not None and eligibility_id is not None:
        statement = statement.where(ServiceSpecialistEligibility.id == eligibility_id)
    if policy is not None and policy.get('employee_categories') and not staff_assignments:
        from app.shared.employee_categories import category_clause
        statement = statement.where(category_clause(db, e.work_categories, policy['employee_categories']))
    # Date of exit is interpreted in each provider's local timezone.
    statement = statement.add_columns(e.date_of_exit).order_by(r.title, r.id)
    output = []
    skipped = 0
    for source in db.connection().execute(statement).mappings():
        row = dict(source)
        reference = row.pop('_employee_ref')
        if type(reference) is not int or reference != row['employee_id']:
            continue
        try:
            zone = ZoneInfo(row['timezone'])
        except (ZoneInfoNotFoundError, TypeError, ValueError):
            continue
        exit_date = row.pop('date_of_exit')
        if exit_date is not None and exit_date <= datetime.now(zone).date():
            continue
        photo = row.pop('profile_photo_url', None)
        if photo:
            row['avatar_url'] = photo
        row['employee_name'] = ' '.join(value for value in (row.pop('first_name'), row.pop('last_name')) if value)
        if skipped < offset:
            skipped += 1
            continue
        output.append(row)
        if len(output) == 101:
            break
    return output[:100], len(output) > 100


def provider_options(db, actor, *, selected=None, search=''):
    company, branch, scope = _authority(db, actor, selected)
    if len(search) > 100:
        raise HTTPException(422, 'Search must be at most 100 characters')
    rows, more = _providers(db, company, branch, scope, search=search.strip())
    return {'providers': rows, 'has_more': more, 'employee_categories': sorted({name for row in rows for name in row.get('work_categories') or []}, key=str.casefold)}


def service_options(db, actor, service_id, *, selected=None, search='', offset=0, employee_id=None, staff_assignments=False):
    company, branch, scope = _authority(db, actor, selected)
    if len(search) > 100:
        raise HTTPException(422, 'Search must be at most 100 characters')
    if type(service_id) is not int or service_id <= 0:
        raise HTTPException(422, 'Choose a service')
    from app.shared.catalog_branches import availability_clause
    product = db.connection().execute(select(SRMProduct.id, SRMProduct.metadata_json, SRMProduct.item_name, SRMProduct.sales_rate, SRMProduct.category_name).where(SRMProduct.id == service_id,
        SRMProduct.organization_id == company, SRMProduct.active.is_(True),
        SRMProduct.product_type.in_(('service', 'services')), availability_clause(SRMProduct, branch))).first()
    if product is None:
        raise HTTPException(404, 'Service not found')
    _source_scope(db, scope, company, branch, SRMProduct, service_id, master=True)
    model = ServiceBookingPolicy
    columns = ('id', 'revision', 'booking_required', 'default_duration_minutes', 'min_duration_minutes',
        'max_duration_minutes', 'allow_duration_override', 'active', 'service_product_id', 'employee_categories')
    policy = db.connection().execute(_scope(select(*(getattr(model, key) for key in columns)), model,
        company, branch, scope).where(model.service_product_id == service_id)).mappings().first()
    resources = db.connection().execute(select(IndustryRecord.id, IndustryRecord.title,
        IndustryRecord.data).where(IndustryRecord.organization_id == company,
        IndustryRecord.branch_id == branch, IndustryRecord.kind == 'resource',
        IndustryRecord.status == 'active',
        IndustryRecord.data['resource_type'].as_string().in_(('room', 'chair', 'equipment', 'location')),
        _owned_clause(IndustryRecord, company, branch, scope)).order_by(IndustryRecord.title).limit(100)).mappings()
    resource_options = [{'id': row['id'], 'name': row['title'], 'resource_type': row['data'].get('resource_type'),
        **{key: row['data'].get(key) for key in ('timezone', 'opens', 'closes', 'weekdays', 'capacity', 'location', 'accessibility', 'facilities')}} for row in resources]
    can_configure = False
    try:
        from app.apps.srm.service_checkout import _authority as checkout_authority
        _, configuration_branch, _ = checkout_authority(db, actor, configuration=True, write=False)
        can_configure = configuration_branch in db.info['branch_context'].writable
    except HTTPException as error:
        if error.status_code not in (403, 409, 503):
            raise
    if staff_assignments and not can_configure:
        raise HTTPException(403, 'Service scheduling configuration access is required')
    from app.shared.settings import effective
    details = {'can_configure': can_configure, 'branch_timezone': effective(db, company, 'srm')['values'].get('timezone'),
        'service': {'name': product.item_name, 'price': str(product.sales_rate), 'category': product.category_name,
                    'currency': (product.metadata_json or {}).get('currency', 'INR')}}
    if policy is None:
        return {'service_id': service_id, 'policy': None, 'specialists': [], 'has_more': False, 'resources': resource_options, **details}
    _source_scope(db, scope, company, branch, model, policy['id'])
    rows, more = ([], False)
    if policy['active'] or staff_assignments:
        rows, more = _providers(db, company, branch, scope, policy=policy, search=search.strip(),
                                offset=offset, target_employee_id=employee_id, staff_assignments=staff_assignments)
    from app.apps.srm.service_resource_requirements import required_types
    from types import SimpleNamespace
    requirements = sorted(required_types(SimpleNamespace(metadata_json=product.metadata_json), policy['id']))
    return {'service_id': service_id, 'policy': {**{key: value for key, value in policy.items() if key != 'service_product_id'}, 'required_resource_types': requirements},
        'specialists': rows, 'has_more': more, 'next_offset': offset + len(rows) if more else None, 'resources': resource_options, **details}


class _AvailabilityRead:
    """Request-local blind occupancy snapshot; never grants resource authority.

    The caller has already authorized the service/provider/resource choices. Keep
    the shared availability reader's identity and malformed-data validation, but
    perform each lookup once rather than once per quarter-hour candidate.
    """
    def __init__(self, db, actor, company, branch, lower, upper, provider, employee):
        from sqlalchemy import func
        self.db, self.actor, self.company, self.branch = db, actor, company, branch
        self.memo = {}
        self.selected = {provider.id: provider}
        self.employees = {employee.id: employee}
        table = IndustryRecord.__table__
        self.resource_shape = func.json_type if db.get_bind().dialect.name == 'sqlite' else func.json_typeof
        self.bookings = db.connection().execute(select(table.c.id, table.c.branch_id,
            table.c.starts_at, table.c.ends_at, table.c.data['resource_ids'].label('resource_ids')).where(
            table.c.organization_id == company, table.c.kind == 'appointment',
            table.c.status.in_(('booked', 'checked_in', 'in_service')),
            or_(table.c.starts_at.is_(None), table.c.ends_at.is_(None), table.c.starts_at >= table.c.ends_at,
                and_(table.c.starts_at < upper, table.c.ends_at > lower)))).mappings().all()
        self.identities = {}

    def remember(self, key, call):
        if key not in self.memo:
            try:
                self.memo[key] = (True, call())
            except HTTPException as error:
                self.memo[key] = (False, (error.status_code, error.detail))
        ok, result = self.memo[key]
        if not ok:
            raise HTTPException(result[0], result[1])
        return result

    def resource(self, identity, historical_branch=None):
        from app.business_packs.availability import _employee, _id, _unavailable, _user
        table = IndustryRecord.__table__
        if identity not in self.identities:
            self.identities[identity] = self.db.connection().execute(select(table.c.branch_id,
                table.c.data['employee_id'].label('employee_id'), table.c.data['user_id'].label('user_id'), table.c.data['capacity'].label('capacity'),
                self.resource_shape(table.c.data).label('shape')).where(table.c.id == identity,
                table.c.kind == 'resource', table.c.organization_id == self.company)).mappings().first()
        row = self.identities[identity]
        if not row or row['shape'] != 'object':
            _unavailable()
        def check_branch():
            if not self.db.connection().execute(select(Branch.id).where(Branch.id == row['branch_id'],
                    Branch.company_id == self.company)).first():
                _unavailable()
        self.remember(('branch', row['branch_id']), check_branch)
        if historical_branch is not None and row['branch_id'] != historical_branch:
            _unavailable()
        employee, user = row['employee_id'], row['user_id']
        if employee is not None:
            _id(employee)
            self.remember(('employee', employee), lambda: _employee(self.db.connection(), self.company, employee))
        if user is not None:
            _id(user)
            historical = historical_branch is not None
            self.remember(('user', user, historical, employee), lambda: _user(self.db, self.company, user,
                historical=historical, employee_id=employee))
        return employee, user

    def conflict(self, start, end, resource_ids):
        from app.business_packs.availability import _company, _ids, _instant, _unavailable
        start, end = _instant(start), _instant(end)
        if start >= end:
            _unavailable()
        self.remember(('company',), lambda: _company(self.db.connection(), self.company))
        selected, employees, users = _ids(resource_ids), set(), set()
        for identity in selected:
            employee, user = self.resource(identity)
            if employee is not None:
                employees.add(employee)
            if user is not None:
                users.add(user)
        occupancy = {identity: [] for identity in selected}
        busy = False
        for row in self.bookings:
            old_start = _instant(row['starts_at'], stored=self.db.get_bind().dialect.name == 'sqlite')
            old_end = _instant(row['ends_at'], stored=self.db.get_bind().dialect.name == 'sqlite')
            if old_start >= old_end:
                _unavailable()
            if old_start >= end or old_end <= start:
                continue
            def check_branch():
                if not self.db.connection().execute(select(Branch.id).where(Branch.id == row['branch_id'],
                        Branch.company_id == self.company)).first():
                    _unavailable()
            self.remember(('branch', row['branch_id']), check_branch)
            source_ids = row['resource_ids']
            if not isinstance(source_ids, list) or not source_ids:
                _unavailable()
            prior = _ids(source_ids)
            if len(prior) != len(source_ids):
                _unavailable()
            for identity in prior & selected:
                occupancy[identity].append((max(start, old_start), min(end, old_end)))
            for identity in prior:
                employee, user = self.resource(identity, row['branch_id'])
                busy |= employee in employees or user in users
        from app.business_packs.availability import capacity_conflict, resource_capacity
        return busy or any(capacity_conflict(intervals, resource_capacity(self.identities[identity]['capacity'])) for identity, intervals in occupancy.items())

    def remaining_capacity(self, start, minutes, identity):
        """Return free units without revealing another booking's identity."""
        from app.business_packs.availability import _instant, resource_capacity
        from datetime import timedelta
        start = _instant(start); end = start + timedelta(minutes=minutes)
        self.conflict(start, end, [identity])  # Validate the same private occupancy snapshot.
        capacity = resource_capacity(self.identities[identity]['capacity'])
        events = []
        for row in self.bookings:
            begin = _instant(row['starts_at'], stored=self.db.get_bind().dialect.name == 'sqlite')
            finish = _instant(row['ends_at'], stored=self.db.get_bind().dialect.name == 'sqlite')
            if begin < end and finish > start and identity in row['resource_ids']:
                events.extend([(max(start, begin), 1), (min(end, finish), -1)])
        occupied = peak = 0
        for _, delta in sorted(events):
            occupied += delta; peak = max(peak, occupied)
        return {'capacity': capacity, 'remaining_capacity': max(0, capacity - peak)}

    def available(self, start, minutes, resource_ids):
        from datetime import timedelta, time
        from app.apps.srm.industry_api import get, provider_employee
        from app.business_packs.availability import employee_leave_conflict
        end = start + timedelta(minutes=minutes)
        for identity in resource_ids:
            if identity not in self.selected:
                self.selected[identity] = get(self.db, self.actor, self.branch, identity, 'resource', lock=False)
            resource = self.selected[identity]
            local = start.astimezone(ZoneInfo(resource.data['timezone']))
            local_end = end.astimezone(ZoneInfo(resource.data['timezone']))
            if resource.data.get('employee_id'):
                employee_id = resource.data['employee_id']
                if employee_id not in self.employees:
                    self.employees[employee_id] = provider_employee(self.db, self.actor, self.branch, employee_id)
                employee = self.employees[employee_id]
                if employee.date_of_exit and employee.date_of_exit <= local.date():
                    return False
                if self.remember(('leave', employee_id, local.date(), local_end.date()),
                        lambda: employee_leave_conflict(self.db, self.company, employee_id, local.date(), local_end.date())):
                    return False
            if (resource.status != 'active' or local.weekday() not in resource.data['weekdays']
                    or local.date() != local_end.date()
                    or local.time().replace(tzinfo=None) < time.fromisoformat(resource.data['opens'])
                    or local_end.time().replace(tzinfo=None) > time.fromisoformat(resource.data['closes'])):
                return False
        return not self.conflict(start, end, resource_ids)


def scheduling_availability(db, actor, service_id, eligibility_id, day, duration_minutes, *, resource_ids=None, starts_at=None, selected=None):
    """Advisory availability only; atomic checkout revalidates every resource."""
    from datetime import timedelta, time
    from app.apps.srm.service_checkout import _assert_employee_category
    from app.apps.srm.industry_api import get, provider_employee, PROVIDER_TYPES
    company, branch, scope = _authority(db, actor, selected)
    options = service_options(db, actor, service_id, selected=selected)
    policy = db.query(ServiceBookingPolicy).filter(ServiceBookingPolicy.id == (options['policy'] or {}).get('id')).first()
    if not policy or not policy.active:
        raise HTTPException(409, 'Configure an active scheduling policy first')
    if not policy.min_duration_minutes <= duration_minutes <= policy.max_duration_minutes or (not policy.allow_duration_override and duration_minutes != policy.default_duration_minutes):
        raise HTTPException(422, 'Choose a duration permitted by the service policy')
    eligibility = _scope(db.query(ServiceSpecialistEligibility), ServiceSpecialistEligibility, company, branch, scope).filter_by(id=eligibility_id, booking_policy_id=policy.id, active=True).first()
    if not eligibility:
        raise HTTPException(404, 'Eligible employee not found')
    _source_scope(db, scope, company, branch, ServiceSpecialistEligibility, eligibility.id)
    provider = get(db, actor, branch, eligibility.provider_resource_id, 'resource', lock=False)
    employee_id = provider.data.get('employee_id')
    employee = provider_employee(db, actor, branch, employee_id)
    if provider.status != 'active' or provider.data.get('resource_type') not in PROVIDER_TYPES:
        raise HTTPException(422, 'Choose an active HRMS-linked employee resource')
    _source_scope(db, scope, company, branch, IndustryRecord, provider.id, master=True)
    _assert_employee_category(db, employee_id, policy)
    zone = ZoneInfo(provider.data['timezone'])
    today = datetime.now(zone).date()
    if not today <= day <= today + timedelta(days=90):
        raise HTTPException(422, 'Choose a day within the next 90 days')
    resource_ids = resource_ids or []
    allowed = {resource['id'] for resource in options.get('resources', [])}
    if len(resource_ids) > 9 or len(set(resource_ids)) != len(resource_ids) or not set(resource_ids) <= allowed:
        raise HTTPException(422, 'Choose current rooms or equipment once each')
    if starts_at is not None and (starts_at.utcoffset() is None or starts_at.astimezone(zone).date() != day):
        raise HTTPException(422, 'Availability time must include a timezone and match the selected day')

    # Cover all provider-day candidates plus a selected interval that can extend
    # into the next day. Busy metadata stays private and is discarded on return.
    lower = datetime.combine(day, time.min, zone).astimezone(timezone.utc)
    upper = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(timezone.utc) + timedelta(minutes=duration_minutes)
    prepared = _AvailabilityRead(db, actor, company, branch, lower, upper, provider, employee)

    def usable(start, additional):
        end = start + timedelta(minutes=duration_minutes)
        if set(options['policy'].get('required_resource_types') or []) - {r['resource_type'] for r in options.get('resources', []) if r['id'] in additional}:
            return False
        if start <= datetime.now(timezone.utc):
            return False
        for bound, lower in ((eligibility.effective_from, True), (eligibility.effective_until, False)):
            if bound:
                bound = bound.replace(tzinfo=timezone.utc) if bound.tzinfo is None else bound
                if (lower and start < bound) or (not lower and end > bound):
                    return False
        try:
            return prepared.available(start, duration_minutes, [provider.id, *additional])
        except HTTPException as error:
            if error.status_code not in (409, 422):
                raise
            return False

    required = set(options['policy'].get('required_resource_types') or [])
    selected_types = {r['resource_type'] for r in options.get('resources', []) if r['id'] in resource_ids}
    missing = sorted(required - selected_types)
    candidate = datetime.combine(day, time.fromisoformat(provider.data['opens']), zone)
    close = datetime.combine(day, time.fromisoformat(provider.data['closes']), zone)
    slots = []
    for _ in range(96):
        if candidate + timedelta(minutes=duration_minutes) > close:
            break
        start = candidate.astimezone(timezone.utc)
        if start.astimezone(zone).replace(tzinfo=None) == candidate.replace(tzinfo=None) and usable(start, resource_ids):
            slots.append({'starts_at': start.isoformat(), 'label': candidate.strftime('%H:%M')})
        candidate += timedelta(minutes=15)
    conflicts = []
    if starts_at:
        end = starts_at + timedelta(minutes=duration_minutes)
        for identity, name in [(provider.id, provider.title), *[(r['id'], r['name']) for r in options.get('resources', []) if r['id'] in resource_ids]]:
            try:
                free = prepared.available(starts_at, duration_minutes, [identity])
            except HTTPException as error:
                if error.status_code not in (409, 422):
                    raise
                free = False
            if not free:
                resource = prepared.selected.get(identity) or get(db,actor,branch,identity,'resource',lock=False)
                local = starts_at.astimezone(ZoneInfo(resource.data['timezone']))
                local_end = end.astimezone(ZoneInfo(resource.data['timezone']))
                code = 'capacity' if int(resource.data.get('capacity') or 1)>1 else 'booking'
                detail = 'capacity is full or the resource is otherwise reserved' if code=='capacity' else 'already reserved or unavailable'
                if (local.weekday() not in resource.data['weekdays'] or local.date()!=local_end.date()
                    or local.time().replace(tzinfo=None)<time.fromisoformat(resource.data['opens'])
                    or local_end.time().replace(tzinfo=None)>time.fromisoformat(resource.data['closes'])):
                    code,detail='working_hours','outside working hours'
                elif resource.data.get('employee_id'):
                    from app.business_packs.availability import employee_leave_conflict
                    if employee_leave_conflict(db,company,resource.data['employee_id'],local.date(),local_end.date()):
                        code,detail='leave','on leave'
                conflicts.append({'resource_id': identity, 'name': name, 'reason_code':code,
                    'message': f'{name} is {detail} ({local.strftime("%H:%M")}–{local_end.strftime("%H:%M")} {resource.data["timezone"]}).'})
    return {'missing_resource_types': missing, 'conflicts': conflicts, 'timezone': str(zone), 'slots': slots, 'checked_at': datetime.now(timezone.utc).isoformat(),
        'selection_available': usable(starts_at, resource_ids) if starts_at else None,
        'resources': [{'id': item['id'], 'available': usable(starts_at, list(set([*resource_ids, item['id']]))), **prepared.remaining_capacity(starts_at, duration_minutes, item['id'])} for item in options.get('resources', [])] if starts_at else []}


def validate_prebooking(db, actor, data):
    """Apply POS eligibility rules to a reservation without financial writes.

    The caller holds the same tenant writer lock used by atomic checkout; the
    subsequent appointment insert and resource validation share its transaction.
    """
    b = data.booking
    company, branch, scope = _authority(db, actor)
    policy = _scope(db.query(ServiceBookingPolicy), ServiceBookingPolicy, company, branch, scope).filter_by(
        id=b.policy_id, service_product_id=data.service_id, active=True).with_for_update().first()
    if not policy or policy.revision != b.expected_policy_revision:
        raise HTTPException(409, 'Service policy changed. Review booking details.')
    eligibility = _scope(db.query(ServiceSpecialistEligibility), ServiceSpecialistEligibility, company, branch, scope).filter_by(
        id=b.eligibility_id, booking_policy_id=policy.id, service_product_id=data.service_id,
        provider_resource_id=b.provider_resource_id, active=True).with_for_update().first()
    if not eligibility or eligibility.revision != b.expected_eligibility_revision:
        raise HTTPException(409, 'Employee eligibility changed. Review booking details.')
    if (data.starts_at != b.starts_at or data.duration_minutes != b.duration_minutes
            or sorted(data.resource_ids) != sorted([b.provider_resource_id, *b.additional_resource_ids])):
        raise HTTPException(422, 'Appointment details differ from the selected booking.')
    from app.apps.srm.service_checkout import _provider
    provider = _provider(db, actor, branch, b.provider_resource_id, b.employee_id)
    zone = ZoneInfo(provider.data['timezone'])
    result = scheduling_availability(db, actor, data.service_id, b.eligibility_id,
        b.starts_at.astimezone(zone).date(), b.duration_minutes,
        resource_ids=b.additional_resource_ids, starts_at=b.starts_at)
    if result['selection_available'] is not True:
        raise HTTPException(409, 'The employee or required resource is unavailable. Choose another available time.')
