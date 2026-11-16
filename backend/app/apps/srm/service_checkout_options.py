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


def _providers(db, company, branch, scope, *, search='', policy=None):
    from app.apps.srm.industry_api import PROVIDER_TYPES
    r, e = IndustryRecord, Employee
    employee_id = cast(r.data['employee_id'].as_string(), String)
    statement = select(r.id.label('provider_resource_id'), r.title.label('provider_name'),
        r.data['timezone'].as_string().label('timezone'), r.data['employee_id'].label('_employee_ref'), e.id.label('employee_id'), e.first_name, e.last_name, e.work_categories)
    statement = statement.select_from(r.__table__.join(e.__table__, cast(e.id, String) == employee_id).join(Branch.__table__, Branch.id == e.branch_id)).where(
        r.organization_id == company, r.branch_id == branch, r.kind == 'resource', r.status == 'active',
        r.data['resource_type'].as_string().in_(PROVIDER_TYPES), e.branch_id == branch, Branch.company_id == company,
        e.deleted_at.is_(None), e.status.in_(('Active', 'Probation', 'On Leave')),
        _owned_clause(r, company, branch, scope))
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
    if policy is not None and policy.get('employee_categories'):
        from app.shared.employee_categories import category_clause
        statement = statement.where(category_clause(db, e.work_categories, policy['employee_categories']))
    # Date of exit is interpreted in each provider's local timezone.
    statement = statement.add_columns(e.date_of_exit).order_by(r.title, r.id)
    output = []
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
        row['employee_name'] = ' '.join(value for value in (row.pop('first_name'), row.pop('last_name')) if value)
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


def service_options(db, actor, service_id, *, selected=None, search=''):
    company, branch, scope = _authority(db, actor, selected)
    if len(search) > 100:
        raise HTTPException(422, 'Search must be at most 100 characters')
    if type(service_id) is not int or service_id <= 0:
        raise HTTPException(422, 'Choose a service')
    from app.shared.catalog_branches import availability_clause
    product = db.connection().execute(select(SRMProduct.id).where(SRMProduct.id == service_id,
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
    resource_options = [{'id': row['id'], 'name': row['title'], 'resource_type': row['data'].get('resource_type')} for row in resources]
    if policy is None:
        return {'service_id': service_id, 'policy': None, 'specialists': [], 'has_more': False, 'resources': resource_options}
    _source_scope(db, scope, company, branch, model, policy['id'])
    rows, more = _providers(db, company, branch, scope, policy=policy, search=search.strip()) if policy['active'] else ([], False)
    return {'service_id': service_id, 'policy': {key: value for key, value in policy.items() if key != 'service_product_id'},
        'specialists': rows, 'has_more': more, 'resources': resource_options}


def scheduling_availability(db, actor, service_id, eligibility_id, day, duration_minutes, *, resource_ids=None, starts_at=None, selected=None):
    """Advisory availability only; atomic checkout revalidates every resource."""
    from datetime import timedelta, time
    from types import SimpleNamespace
    from app.apps.srm.service_checkout import _assert_employee_category, _cross_pack_busy
    from app.apps.srm.industry_api import get, available, provider_employee, PROVIDER_TYPES
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
    provider_employee(db, actor, branch, employee_id)
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

    def usable(start, additional):
        end = start + timedelta(minutes=duration_minutes)
        if start <= datetime.now(timezone.utc):
            return False
        for bound, lower in ((eligibility.effective_from, True), (eligibility.effective_until, False)):
            if bound:
                bound = bound.replace(tzinfo=timezone.utc) if bound.tzinfo is None else bound
                if (lower and start < bound) or (not lower and end > bound):
                    return False
        try:
            available(db, actor, branch, start, duration_minutes, [provider.id, *additional], lock=False)
            _cross_pack_busy(db, company, branch, SimpleNamespace(provider_resource_id=provider.id,
                employee_id=employee_id, additional_resource_ids=additional, starts_at=start, duration_minutes=duration_minutes))
            return True
        except HTTPException as error:
            if error.status_code not in (409, 422):
                raise
            return False

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
    return {'timezone': str(zone), 'slots': slots, 'checked_at': datetime.now(timezone.utc).isoformat(),
        'selection_available': usable(starts_at, resource_ids) if starts_at else None,
        'resources': [{'id': item['id'], 'available': usable(starts_at, [item['id']])} for item in options.get('resources', [])] if starts_at else []}
