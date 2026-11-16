"""Company-admin Business Pack configuration; no implicit activation or grants.

Runtime readiness belongs to the integration-owned runtime module. Registry
metadata alone cannot turn on operational features or prove record isolation.
"""
from dataclasses import asdict
from importlib import import_module
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from .registry import PackRegistryError, get_pack, get_role, list_packs
from . import schemas

TABLES = (
    'business_pack_activations', 'business_pack_contexts', 'business_pack_user_grants',
    'business_pack_record_ownership', 'business_pack_master_availability',
)


def company_control(db, actor):
    from app.access.settings_hub import context, can_edit_company
    ctx = context(db, actor)
    # A pack manager's contextual settings capability is not company authority.
    if not ctx['admin'] or not can_edit_company(ctx):
        raise HTTPException(403, 'Company access administrator required for Business Packs')
    from app.models.company import Company
    company = db.connection().execute(select(Company.id).where(
        Company.id == ctx['company'], Company.is_active.is_(True))).scalar_one_or_none()
    if company is None:
        raise HTTPException(403, 'Active company is required')
    return ctx['company']


def schema_status(db):
    inspector = inspect(db.connection())
    missing = [table for table in TABLES if not inspector.has_table(table)]
    from .models import PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability
    missing_columns = {}
    for model in (PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability):
        name = model.__tablename__
        if name in missing:
            continue
        absent = set(model.__table__.columns.keys()) - {column['name'] for column in inspector.get_columns(name)}
        if absent:
            missing_columns[name] = sorted(absent)
    return {'schema_ready': not missing and not missing_columns,
            'missing_tables': missing, 'missing_columns': missing_columns}


def _require_schema(db):
    status = schema_status(db)
    if not status['schema_ready']:
        raise HTTPException(503, 'Apply the Business Pack foundation migration before configuring packs')


def _manifest(key):
    try:
        return get_pack(key)
    except PackRegistryError as error:
        raise HTTPException(422, str(error)) from None


def manifest_output(manifest):
    return {
        **asdict(manifest),
        'required_modules': sorted(manifest.required_modules),
        'optional_modules': sorted(manifest.optional_modules),
        'roles': [{**asdict(role), 'capabilities': sorted(role.capabilities)} for role in manifest.roles],
        'workflows': [{**asdict(workflow), 'state': workflow.state.value} for workflow in manifest.workflows],
        'capabilities': sorted(manifest.capabilities), 'shared_services': sorted(manifest.shared_services),
    }


def catalog(db, actor):
    return {'company_id': company_control(db, actor), 'items': [manifest_output(pack) for pack in list_packs()]}


def _module_status(db, company, manifest):
    from app.access.entitlements import states
    from app.module_registry import is_app_enabled
    state = states(db, company)
    missing = sorted(module for module in manifest.required_modules
                     if not is_app_enabled(module) or state.get(module) is False)
    return {'required_modules': sorted(manifest.required_modules), 'missing_modules': missing}


def _require_modules(db, company, manifest):
    missing = _module_status(db, company, manifest)['missing_modules']
    if missing:
        raise HTTPException(403, 'Business Pack dependencies are unavailable: ' + ', '.join(missing))


def _branch(db, actor, company, ident, *, write=False, active=True):
    # Company controls address a branch independently of the operational default
    # branch filter. This is administration metadata, never a Branch ORM lease.
    from types import SimpleNamespace
    from app.models.company import Branch
    from app.branches.models import BranchLifecycle
    if company_control(db, actor) != company:
        raise HTTPException(403, 'Company access administrator required')
    table, lifecycle = Branch.__table__, BranchLifecycle.__table__
    row = db.connection().execute(select(table.c.id, table.c.company_id, table.c.is_active,
        lifecycle.c.company_id.label('lifecycle_company'), lifecycle.c.deleted_at).select_from(
            table.outerjoin(lifecycle, lifecycle.c.branch_id == table.c.id)).where(
                table.c.id == ident, table.c.company_id == company)).mappings().first()
    if row is None or row['lifecycle_company'] not in {None, company} or active and (not row['is_active'] or row['deleted_at'] is not None):
        raise HTTPException(404, 'Active branch not found in this company')
    if active:
        from app.branches.service import context
        native = context(db, actor, company, str(ident))
        if write and ident not in native.writable:
            raise HTTPException(403, 'Branch configuration is read-only')
    return SimpleNamespace(id=row['id'], company_id=row['company_id'], is_active=row['is_active'])


def _runtime_status(db, company, pack_key, branch_id):
    module_name = 'app.business_packs.runtime'
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name != module_name:
            raise
        return {'ready': False, 'isolation_ready': False, 'workflows_ready': False,
                'reasons': ['Operational pack isolation and workflow integration are not installed.']}
    result = module.activation_readiness(db, company, pack_key, branch_id=branch_id)
    # Fail closed for malformed integration responses, including truthy strings.
    valid = (isinstance(result, dict) and all(type(result.get(key)) is bool for key in
        ('ready', 'schema_ready', 'isolation_ready', 'workflows_ready'))
        and isinstance(result.get('reasons'), list)
        and all(isinstance(reason, str) for reason in result['reasons']))
    if not valid:
        return {'ready': False, 'isolation_ready': False, 'workflows_ready': False,
                'reasons': ['Operational pack readiness could not be verified.']}
    ready = (result['ready'] and result['schema_ready'] and result['isolation_ready']
             and result['workflows_ready'] and not result['reasons'])
    reasons = result['reasons'] or ([] if ready else ['Operational pack readiness is incomplete.'])
    return {**result, 'ready': ready, 'reasons': reasons}


def readiness(db, actor, pack_key, branch_id=None):
    company = company_control(db, actor)
    manifest = _manifest(pack_key)
    if branch_id is not None:
        _branch(db, actor, company, branch_id)
    schema = schema_status(db)
    modules = _module_status(db, company, manifest)
    runtime = _runtime_status(db, company, manifest.key, branch_id) if schema['schema_ready'] else {
        'ready': False, 'isolation_ready': False, 'workflows_ready': False, 'reasons': []}
    reasons = []
    if not schema['schema_ready']:
        reasons.append('The Business Pack foundation migration is not installed.')
    if modules['missing_modules']:
        reasons.append('Required modules are unavailable: ' + ', '.join(modules['missing_modules']))
    reasons.extend(runtime['reasons'])
    ready = schema['schema_ready'] and not modules['missing_modules'] and runtime['ready']
    return {'company_id': company, 'pack_key': manifest.key, 'branch_id': branch_id,
            **schema, **modules, 'ready': bool(ready),
            'isolation_ready': runtime['isolation_ready'], 'workflows_ready': runtime['workflows_ready'],
            'reasons': list(dict.fromkeys(reasons))}


def _output(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def configuration(db, actor, limit=200):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise HTTPException(422, 'Business Pack page size must be between 1 and 200')
    company = company_control(db, actor)
    status = schema_status(db)
    from app.models.company import Branch
    from app.branches.models import BranchLifecycle
    branches = db.query(Branch).filter(Branch.company_id == company, Branch.is_active.is_(True),
        ~Branch.id.in_(select(BranchLifecycle.branch_id).where(BranchLifecycle.company_id == company,
            BranchLifecycle.deleted_at.is_not(None)))).order_by(Branch.name, Branch.id).limit(limit + 1).all()
    result = {'company_id': company, **status, 'branches': [{'id': row.id, 'name': row.name} for row in branches[:limit]],
        'activations': [], 'contexts': [], 'grants': [], 'has_more': {'branches': len(branches) > limit},
        'users_url': '/api/v1/access/users',
        'runtime_note': 'Draft configuration does not activate workflows or grant native module permissions.'}
    if not status['schema_ready']:
        return result
    from .models import PackActivation, PackContext, PackUserGrant
    for key, model in [('activations', PackActivation), ('contexts', PackContext), ('grants', PackUserGrant)]:
        rows = db.query(model).filter_by(company_id=company).order_by(model.id).limit(limit + 1).all()
        result[key] = [_output(row) for row in rows[:limit]]
        result['has_more'][key] = len(rows) > limit
    return result


def _lock_company(db, company):
    from app.core.company_writer import lock_company_writer
    lock_company_writer(db, company)


def _activation(db, company, ident, *, lock=False):
    from .models import PackActivation
    query = db.query(PackActivation).filter_by(id=ident, company_id=company)
    row = (query.with_for_update().populate_existing() if lock else query).first()
    if row is None:
        raise HTTPException(404, 'Business Pack activation not found')
    manifest = _manifest(row.pack_key)
    if row.pack_version != manifest.version:
        raise HTTPException(409, 'Business Pack definition changed; review the installed version')
    return row, manifest


def _context(db, company, ident, *, lock=False):
    from .models import PackContext
    query = db.query(PackContext).filter_by(id=ident, company_id=company)
    row = (query.with_for_update().populate_existing() if lock else query).first()
    if row is None:
        raise HTTPException(404, 'Business Pack branch context not found')
    activation, manifest = _activation(db, company, row.activation_id, lock=lock)
    if (row.company_id, row.pack_key, row.pack_version) != (activation.company_id, activation.pack_key, activation.pack_version):
        raise HTTPException(409, 'Business Pack context identity is inconsistent')
    return row, activation, manifest


def _revision(row, expected):
    if row.revision != expected:
        raise HTTPException(409, 'Business Pack configuration changed; reload and review before saving')


def _commit(db):
    try:
        db.commit()
    except (IntegrityError, StaleDataError):
        db.rollback()
        raise HTTPException(409, 'Business Pack configuration changed; reload and review before saving') from None


def _flush(db):
    try:
        db.flush()
    except (IntegrityError, StaleDataError):
        db.rollback()
        raise HTTPException(409, 'Business Pack configuration changed; reload and review before saving') from None


def _audit(db, actor, company, operation, reason, before, after, request=None, target=None):
    from app.access.service import audit
    audit(db, actor, company, 'settings.business-packs.' + operation, reason,
          before=jsonable_encoder(before), after=jsonable_encoder(after), request=request, target=target)


def _draft_activation(db, actor, data):
    company = company_control(db, actor)
    _require_schema(db)
    manifest = _manifest(data.pack_key)
    _require_modules(db, company, manifest)
    from .models import PackActivation
    existing = db.query(PackActivation).filter_by(company_id=company, pack_key=manifest.key, pack_version=manifest.version).first()
    if existing is not None:
        raise HTTPException(409, 'This Business Pack version is already configured; reload its configuration')
    return company, manifest, {'company_id': company, 'pack_key': manifest.key, 'pack_version': manifest.version, 'state': 'draft', 'revision': 1}


def draft_activation(db, actor, data, request=None):
    company = company_control(db, actor)
    _lock_company(db, company)
    company, _, after = _draft_activation(db, actor, data)
    from .models import PackActivation
    row = PackActivation(**after)
    db.add(row); _flush(db)
    _audit(db, actor, company, 'activation.drafted', data.reason, None, _output(row), request)
    _commit(db)
    return _output(row)


def _draft_context(db, actor, data, *, lock=False):
    company = company_control(db, actor)
    _require_schema(db)
    activation, manifest = _activation(db, company, data.activation_id, lock=lock)
    _revision(activation, data.activation_revision)
    if activation.state not in {'draft', 'active'}:
        raise HTTPException(409, 'The parent Business Pack is not available for branch setup')
    _require_modules(db, company, manifest)
    _branch(db, actor, company, data.branch_id, write=True)
    from .models import PackContext
    if db.query(PackContext).filter_by(activation_id=activation.id, branch_id=data.branch_id, company_id=company).first():
        raise HTTPException(409, 'This branch already has a context for the Business Pack version')
    return company, manifest, {'company_id': company, 'branch_id': data.branch_id, 'activation_id': activation.id,
        'pack_key': manifest.key, 'pack_version': manifest.version, 'state': 'draft', 'revision': 1}


def draft_context(db, actor, data, request=None):
    company = company_control(db, actor)
    _lock_company(db, company)
    company, _, after = _draft_context(db, actor, data, lock=True)
    from .models import PackContext
    row = PackContext(**after)
    db.add(row); _flush(db)
    _audit(db, actor, company, 'context.drafted', data.reason, None, _output(row), request)
    _commit(db)
    return _output(row)


def _grant(db, actor, context_id, user_id, data, *, lock=False):
    company = company_control(db, actor)
    _require_schema(db)
    context, activation, manifest = _context(db, company, context_id, lock=lock)
    _revision(context, data.context_revision)
    try:
        role = get_role(manifest.key, data.role)
    except PackRegistryError as error:
        raise HTTPException(422, str(error)) from None
    _branch(db, actor, company, context.branch_id, write=True, active=data.active)
    if data.active:
        if context.state not in {'draft', 'active'} or activation.state not in {'draft', 'active'}:
            raise HTTPException(409, 'The Business Pack context is not available for role assignment')
        _require_modules(db, company, manifest)
    from .models import PackUserGrant
    query = db.query(PackUserGrant).filter_by(company_id=company, context_id=context.id, user_id=user_id)
    row = (query.with_for_update().populate_existing() if lock else query).first()
    if data.expected_revision != (row.revision if row else 0):
        raise HTTPException(409, 'Pack role changed; reload and review before saving')
    from app.models.user import User
    from app.core.tenant_boundary import company_ids
    target_query = db.query(User).filter_by(id=user_id).populate_existing()
    if lock:
        target_query = target_query.with_for_update(of=User)
    target = target_query.first() if data.active or row is None else None
    if (data.active or row is None) and (target is None or company not in company_ids(db, target)):
        raise HTTPException(404, 'User not found in this company')
    if data.active:
        if not target.is_active:
            raise HTTPException(409, 'Only an active company user can receive a pack role')
        from app.branches.service import access
        if context.branch_id not in access(db, target, company)[0]:
            raise HTTPException(403, 'Assign native branch access before assigning a pack role')
    after = {'company_id': company, 'branch_id': context.branch_id, 'context_id': context.id,
             'user_id': user_id, 'role': role.key, 'active': data.active, 'revision': (row.revision + 1) if row else 1}
    return company, manifest, row, after


def grant_role(db, actor, context_id, user_id, data, request=None):
    company = company_control(db, actor)
    _lock_company(db, company)
    company, _, row, after = _grant(db, actor, context_id, user_id, data, lock=True)
    before = _output(row) if row else None
    from .models import PackUserGrant
    if row is None:
        row = PackUserGrant(**after); db.add(row)
    else:
        row.role, row.active = after['role'], after['active']
        row.revision = after['revision']
    _flush(db)
    _audit(db, actor, company, 'role.assigned' if data.active else 'role.revoked', data.reason, before, _output(row), request, user_id)
    _commit(db)
    return _output(row)


def _activation_preview(db, actor, ident, data, *, lock=False):
    company = company_control(db, actor)
    _require_schema(db)
    activation, manifest = _activation(db, company, ident, lock=lock)
    _revision(activation, data.expected_revision)
    if activation.state not in {'draft', 'suspended'}:
        raise HTTPException(409, 'Only a draft or suspended Business Pack can be activated')
    ready = readiness(db, actor, manifest.key)
    return activation, ready


def activate(db, actor, ident, data, request=None):
    company = company_control(db, actor)
    _lock_company(db, company)
    row, ready = _activation_preview(db, actor, ident, data, lock=True)
    if not ready['ready']:
        raise HTTPException(409, {'message': 'Business Pack activation is blocked', 'readiness': ready})
    before = _output(row)
    row.state = 'active'; _flush(db)
    _audit(db, actor, row.company_id, 'activation.activated', data.reason, before, _output(row), request)
    _commit(db)
    return _output(row)


def _context_activation_preview(db, actor, ident, data, *, lock=False):
    company = company_control(db, actor)
    _require_schema(db)
    context, activation, manifest = _context(db, company, ident, lock=lock)
    _revision(context, data.expected_revision)
    _revision(activation, data.activation_revision)
    _branch(db, actor, company, context.branch_id, write=True)
    if activation.state != 'active':
        raise HTTPException(409, 'Activate the parent Business Pack before its branch context')
    if context.state not in {'draft', 'suspended'}:
        raise HTTPException(409, 'Only a draft or suspended branch context can be activated')
    return context, readiness(db, actor, manifest.key, context.branch_id)


def activate_context(db, actor, ident, data, request=None):
    company = company_control(db, actor)
    _lock_company(db, company)
    row, ready = _context_activation_preview(db, actor, ident, data, lock=True)
    if not ready['ready']:
        raise HTTPException(409, {'message': 'Branch pack activation is blocked', 'readiness': ready})
    before = _output(row)
    row.state = 'active'; _flush(db)
    _audit(db, actor, row.company_id, 'context.activated', data.reason, before, _output(row), request)
    _commit(db)
    return _output(row)


def preview(db, actor, data):
    company_control(db, actor)
    before = None
    if isinstance(data, schemas.PreviewActivation):
        _, manifest, after = _draft_activation(db, actor, data)
        ready = readiness(db, actor, manifest.key)
    elif isinstance(data, schemas.PreviewContext):
        _, manifest, after = _draft_context(db, actor, data)
        ready = readiness(db, actor, manifest.key, data.branch_id)
    elif isinstance(data, schemas.PreviewGrant):
        _, manifest, row, after = _grant(db, actor, data.context_id, data.user_id, data)
        before = _output(row) if row else None
        ready = readiness(db, actor, manifest.key, after['branch_id'])
    elif isinstance(data, schemas.PreviewActivate):
        row, ready = _activation_preview(db, actor, data.activation_id, data)
        before = _output(row); after = {**before, 'state': 'active', 'revision': row.revision + 1}
    elif isinstance(data, schemas.PreviewActivateContext):
        row, ready = _context_activation_preview(db, actor, data.context_id, data)
        before = _output(row); after = {**before, 'state': 'active', 'revision': row.revision + 1}
    else:
        raise HTTPException(422, 'Unsupported Business Pack preview operation')
    activation = isinstance(data, (schemas.PreviewActivate, schemas.PreviewActivateContext))
    return {'action': data.action, 'allowed': ready['ready'] if activation else True,
        'before': before, 'after': after, 'readiness': ready,
        'reasons': ready['reasons'] if activation else [], 'persists': False}


def history(db, actor, limit=50):
    from app.access.models import AccessAudit
    company = company_control(db, actor)
    rows = db.query(AccessAudit).filter(AccessAudit.company_id == company,
        AccessAudit.operation.startswith('settings.business-packs.')).order_by(AccessAudit.id.desc()).limit(limit).all()
    return {'items': [{key: getattr(row, key) for key in ('id', 'actor_id', 'target_id', 'operation',
        'reason', 'before_json', 'after_json', 'created_at')} for row in rows]}
