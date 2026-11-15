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
        r.data['timezone'].as_string().label('timezone'), r.data['employee_id'].label('_employee_ref'), e.id.label('employee_id'), e.first_name, e.last_name)
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
    return {'providers': rows, 'has_more': more}


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
        'max_duration_minutes', 'allow_duration_override', 'active', 'service_product_id')
    policy = db.connection().execute(_scope(select(*(getattr(model, key) for key in columns)), model,
        company, branch, scope).where(model.service_product_id == service_id)).mappings().first()
    if policy is None:
        return {'service_id': service_id, 'policy': None, 'specialists': [], 'has_more': False}
    _source_scope(db, scope, company, branch, model, policy['id'])
    rows, more = _providers(db, company, branch, scope, policy=policy, search=search.strip()) if policy['active'] else ([], False)
    return {'service_id': service_id, 'policy': {key: value for key, value in policy.items() if key != 'service_product_id'},
        'specialists': rows, 'has_more': more}
