"""Explicit master availability control plane; sharing never grants native access."""
from datetime import date
from fastapi import HTTPException
from sqlalchemy import String, and_, cast, exists, false, func, literal, or_, select, true, union_all
from . import service
from .models import PackMasterAvailability, PackRecordOwnership
from .registry import get_role
from app.models.employee import Employee
from app.models.user import User
from app.models.company import Branch
from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMProduct, SRMWarehouse
from app.branches.models import BranchOwnership

SOURCES = {'employees': (Employee, 'hrms'), 'customers': (CRMCompany, 'crm'),
           'products': (SRMProduct, 'srm'), 'warehouses': (SRMWarehouse, 'srm')}


def _control(db, actor, ident, *, write=False):
    _active_actor(db, actor)
    if write and db.info.get('security_write_request') is False:
        raise HTTPException(403, 'Read-only requests cannot change master availability')
    company = service.company_control(db, actor)
    service._require_schema(db)
    context, activation, manifest = service._context(db, company, ident, lock=write)
    if not write:
        db.refresh(context); db.refresh(activation)
    service._branch(db, actor, company, context.branch_id, write=write)
    if context.state not in {'draft', 'active'} or activation.state not in {'draft', 'active'}:
        raise HTTPException(409, 'Business Pack context is unavailable for enrollment')
    if context.state == 'active' and activation.state != 'active':
        raise HTTPException(409, 'Active context requires an active Business Pack activation')
    return company, context, manifest


def _active_actor(db, actor):
    actual = db.connection().execute(select(User.is_active, User.is_superuser).where(User.id == actor.id)).first()
    if actual is None or not actual.is_active or bool(actual.is_superuser) != bool(actor.is_superuser):
        raise HTTPException(403, 'An active verified company administrator is required')


def _native_read(db, actor, module, branch):
    from app.access.service import check_background_access
    check_background_access(db, actor, module, 'view', branch_id=branch)
    from app.access.catalog import permission_names
    required = {'hrms': {'employee_view'}, 'crm': {'crm_view', 'crm_manage', 'crm_admin', 'crm_companies_view', 'crm_companies_manage'},
                'srm': {'srm_view', 'srm_manage', 'srm_admin'}}[module]
    if not actor.is_superuser and not required.intersection(permission_names(actor)):
        raise HTTPException(403, 'Native source view permission is required')


def _sources(kind, company, branch, *, eligible=True):
    if kind not in SOURCES:
        raise HTTPException(422, 'Unsupported master kind')
    model, module = SOURCES[kind]
    if kind == 'employees':
        name = (model.first_name + ' ' + model.last_name).label('name')
        statement = select(model.id, name).join(Branch, Branch.id == model.branch_id).where(
            Branch.company_id == company, model.branch_id == branch)
        if eligible:
            statement = statement.where(model.deleted_at.is_(None), model.status.in_(('Active', 'Probation', 'On Leave')), or_(model.date_of_exit.is_(None), model.date_of_exit > date.today()))
        search = (model.first_name, model.last_name, model.employee_id)
    else:
        name = getattr(model, {'customers': 'name', 'products': 'item_name', 'warehouses': 'warehouse_name'}[kind])
        statement = select(model.id, name.label('name')).where(model.organization_id == company)
        if kind == 'products':
            from app.shared.catalog_branches import availability_clause
            statement = statement.where(availability_clause(model, branch))
            if eligible: statement = statement.where(model.active.is_(True), model.deleted_at.is_(None))
        else:
            owner = BranchOwnership.__table__
            statement = statement.where(exists(select(1).where(owner.c.resource_table == model.__tablename__,
                owner.c.resource_key == cast(model.id, String), owner.c.company_id == company, owner.c.branch_id == branch)))
            if eligible: statement = statement.where(model.status == 'Active', model.deleted_at.is_(None)) if kind == 'customers' else statement.where(model.active.is_(True))
        search = (name,)
    # Availability never turns a private operational source into a canonical
    # master, even for the same context or an administrator. Apply this to
    # historical names too; old enrollment remains discoverable and revocable
    # through the existing unavailable-master projection.
    private = PackRecordOwnership.__table__
    statement = statement.where(~exists(select(1).where(
        private.c.resource_table == model.__tablename__,
        private.c.resource_key == cast(model.id, String))).correlate(model.__table__))
    return model, module, statement, search


def _search(statement, columns, search):
    if len(search) > 100:
        raise HTTPException(422, 'Search must be at most 100 characters')
    if search.strip():
        match = '%' + search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        statement = statement.where(or_(*(column.ilike(match, escape='\\') for column in columns)))
    return statement


def master_options(db, actor, context_id, kind, search=''):
    company, context, _ = _control(db, actor, context_id)
    model, module, statement, columns = _sources(kind, company, context.branch_id)
    _native_read(db, actor, module, context.branch_id)
    available = PackMasterAvailability.__table__
    eligible = statement.subquery('eligible_masters')
    _, _, historical_query, _ = _sources(kind, company, context.branch_id, eligible=False)
    historical = historical_query.subquery('historical_masters')
    scope = and_(available.c.resource_table == model.__tablename__, available.c.company_id == company,
                 available.c.branch_id == context.branch_id, available.c.context_id == context.id)
    candidates = select(cast(eligible.c.id, String).label('resource_key'), eligible.c.name,
        available.c.id.label('availability_id'), available.c.revision.label('availability_revision'), available.c.active,
        true().label('eligible')).select_from(eligible.outerjoin(available, and_(scope, available.c.resource_key == cast(eligible.c.id, String))))
    enrolled = select(available.c.resource_key, func.coalesce(historical.c.name, literal('Unavailable master')).label('name'),
        available.c.id.label('availability_id'), available.c.revision.label('availability_revision'), available.c.active,
        false().label('eligible')).select_from(available.outerjoin(historical, available.c.resource_key == cast(historical.c.id, String))).where(
        scope, ~exists(select(1).where(cast(eligible.c.id, String) == available.c.resource_key)))
    choices = union_all(candidates, enrolled).subquery('master_choices')
    query = _search(select(choices), (choices.c.name,), search).order_by(func.length(choices.c.resource_key), choices.c.resource_key).limit(101)
    rows = db.connection().execute(query).mappings().all()
    items = []
    for source in rows[:100]:
        row = dict(source)
        key = row.pop('resource_key')
        if not key.isascii() or not key.isdigit() or int(key) <= 0 or str(int(key)) != key:
            raise HTTPException(503, 'Master enrollment identity requires reconciliation')
        row['id'] = int(key)
        items.append(row)
    return {'context_id': context.id, 'context_revision': context.revision, 'kind': kind,
            'items': items, 'has_more': len(rows) > 100}



def share_master(db, actor, context_id, data, request=None):
    company = service.company_control(db, actor)
    service._lock_company(db, company)
    company, context, _ = _control(db, actor, context_id, write=True)
    service._revision(context, data.expected_context_revision)
    model, module, statement, _ = _sources(data.kind, company, context.branch_id, eligible=data.active)
    _native_read(db, actor, module, context.branch_id)
    source = db.connection().execute(statement.where(model.id == data.id)).mappings().first()
    row = db.query(PackMasterAvailability).filter_by(company_id=company, branch_id=context.branch_id,
        context_id=context.id, resource_table=model.__tablename__, resource_key=str(data.id)).with_for_update().populate_existing().first()
    if data.expected_revision != (row.revision if row else 0):
        raise HTTPException(409, 'Master availability changed; reload before saving')
    if source is None and (data.active or row is None):
        raise HTTPException(404, 'Native master is unavailable in this company branch')
    before = service._output(row) if row else None
    if row is None:
        row = PackMasterAvailability(company_id=company, branch_id=context.branch_id, context_id=context.id,
            resource_table=model.__tablename__, resource_key=str(data.id), active=data.active)
        db.add(row)
    else:
        row.active = data.active
        row.revision += 1
    before_context_revision = context.revision
    context.revision += 1
    service._flush(db)
    service._audit(db, actor, company, 'master.shared' if data.active else 'master.unshared', data.reason, {'availability': before, 'context_revision': before_context_revision}, {'availability': service._output(row), 'context_revision': context.revision}, request)
    service._commit(db)
    return {'context_id': context.id, 'context_revision': context.revision, 'kind': data.kind, 'id': data.id,
        'name': source['name'] if source else 'Unavailable master', 'availability_id': row.id, 'availability_revision': row.revision, 'active': row.active}


def user_options(db, actor, context_id, search=''):
    company, context, _ = _control(db, actor, context_id)
    from app.access.models import AccessMembership
    from app.common.models import CommonPerson
    member, person, employee, branch = AccessMembership.__table__, CommonPerson.__table__, Employee.__table__, Branch.__table__
    native = or_(exists(select(1).where(member.c.user_id == User.id, member.c.company_id == company, member.c.active.is_(True))),
        exists(select(1).where(person.c.user_id == User.id, person.c.organization_id == company)),
        exists(select(1).select_from(employee.join(branch, employee.c.branch_id == branch.c.id)).where(employee.c.user_id == User.id, branch.c.company_id == company)))
    statement = select(User.id, User.email).where(User.is_active.is_(True), native,
        ~exists(select(1).where(member.c.user_id == User.id, member.c.company_id == company, member.c.active.is_(False))))
    can_names = True
    try: _native_read(db, actor, 'hrms', context.branch_id)
    except HTTPException as error:
        if error.status_code != 403: raise
        can_names = False
    names = employee.alias('master_enrollment_name')
    if can_names:
        statement = statement.outerjoin(names, and_(names.c.user_id == User.id, names.c.branch_id == context.branch_id, names.c.deleted_at.is_(None)))
        statement = statement.add_columns(names.c.first_name, names.c.last_name)
        columns = (User.email, names.c.first_name, names.c.last_name)
    else:
        columns = (User.email,)
    rows = db.connection().execute(_search(statement, columns, search).order_by(User.id).limit(101)).mappings().all()
    return {'context_id': context.id, 'context_revision': context.revision,
        'items': [{'id': row['id'], 'name': (' '.join(filter(None, (row.get('first_name'), row.get('last_name')))) or row['email'])} for row in rows[:100]], 'has_more': len(rows) > 100}



def grant_preview(db, actor, context_id, data):
    _active_actor(db, actor)
    if data.active:
        _control(db, actor, context_id)
    else:
        # Refresh the preview's revision snapshot without imposing active-only
        # enrollment rules on an existing grant revocation.
        from .models import PackContext
        company = service.company_control(db, actor)
        db.query(PackContext).filter_by(id=context_id, company_id=company).populate_existing().first()
    company, manifest, row, after = service._grant(db, actor, context_id, data.user_id, data)
    # Shared validator is also executed again by the actual grant endpoint.
    return {'allowed': True, 'before': service._output(row) if row else None, 'after': after,
        'capabilities': sorted(get_role(manifest.key, data.role).capabilities), 'grants_native_permissions': False}
