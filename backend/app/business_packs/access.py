"""Resolve exact operational pack grants without expanding native authorization.

This module grants no HRMS/CRM/PMS/Sales/accounting permission and never promotes
a pack role to company/platform administrator. Native company, branch, module,
record and action guards remain mandatory in addition to a returned PackScope.
The caller supplies a freshly verified server-side BranchContext; client input
can select one eligible context, never manufacture branch/pack cross-products.
"""
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import and_, exists, inspect, select

from .models import PackActivation, PackContext, PackMasterAvailability, PackRecordOwnership, PackUserGrant
from .registry import PackRegistryError, get_pack, get_role


_MODELS = (PackActivation, PackContext, PackUserGrant, PackRecordOwnership, PackMasterAvailability)


@dataclass(frozen=True)
class PackScope:
    company_id: int
    branch_id: int
    context_id: int
    activation_id: int
    pack_key: str
    pack_version: int
    user_id: int
    grant_id: int
    role: str
    capabilities: frozenset[str]
    writable: bool
    activation_revision: int
    context_revision: int
    grant_revision: int

    @property
    def version(self):
        return self.pack_version

    @property
    def revisions(self):
        return (self.activation_revision, self.context_revision, self.grant_revision)


def _deny(message='An assigned active Business Pack context is required'):
    raise HTTPException(403, message)


def _positive(value):
    return type(value) is int and 0 < value <= 2147483647


def _selector(value):
    if value is None:
        return None
    if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 10:
        value = int(value)
    if not _positive(value):
        _deny('Invalid Business Pack context selection')
    return value


def _installed(db):
    from app.db.schema_columns import table_columns
    columns = table_columns(db.connection(), (model.__tablename__ for model in _MODELS))
    present = set(columns)
    if not present:
        return False
    if len(present) != len(_MODELS) or any(
        not set(model.__table__.c.keys()) <= columns[model.__tablename__]
        for model in _MODELS
    ):
        raise HTTPException(503, 'Business Pack installation is incomplete')
    return True


def _actor_company(db, actor, branch_ctx):
    from app.models.company import Company
    from app.models.user import User
    from app.access.models import AccessPolicy
    from app.core.tenant_boundary import company_ids

    company, user_id = getattr(branch_ctx, 'company_id', None), getattr(actor, 'id', None)
    if not _positive(company) or not _positive(user_id):
        _deny('Verified company and actor are required')
    selected = getattr(actor, 'organization_id', None)
    if selected is not None and selected != company:
        _deny('Business Pack company does not match the verified company')
    row = db.connection().execute(select(User.id, User.is_active, User.is_superuser, User.role_id,
        Company.is_active.label('company_active'),AccessPolicy.status.label('policy_status')).select_from(
        User.__table__.outerjoin(Company.__table__,Company.id==company).outerjoin(AccessPolicy.__table__,and_(
            AccessPolicy.company_id==company,AccessPolicy.user_id==User.id))).where(User.id==user_id)).mappings().first()
    if (not row or not row['is_active'] or getattr(actor, 'is_active', True) is False
            or bool(row['is_superuser']) != bool(getattr(actor, 'is_superuser', False))
            or getattr(actor, 'role_id', row['role_id']) != row['role_id']):
        _deny('Active verified Business Pack actor is required')
    if row['company_active'] is not True:
        _deny('Business Pack company is unavailable')
    if not row['is_superuser'] and company not in company_ids(db, actor):
        _deny('Verified company membership is required')
    policy = row['policy_status']
    if policy is not None and policy != 'active':
        _deny('Business Pack company access is revoked')
    branch_id = getattr(branch_ctx, 'branch_id', None)
    if branch_id is not None and not _positive(branch_id):
        _deny('Invalid verified branch context')
    return company, user_id


def _rows(db, company, user_id, branch_ctx):
    from app.models.company import Branch
    from app.branches.models import BranchLifecycle

    activation, context, grant = PackActivation.__table__, PackContext.__table__, PackUserGrant.__table__
    branch, lifecycle = Branch.__table__, BranchLifecycle.__table__
    allowed = frozenset(value for value in branch_ctx.allowed if _positive(value))
    statement = select(
        context.c.id.label('context_id'), context.c.activation_id, context.c.company_id,
        context.c.branch_id, context.c.pack_key, context.c.pack_version,
        activation.c.revision.label('activation_revision'), context.c.revision.label('context_revision'),
        grant.c.id.label('grant_id'), grant.c.user_id, grant.c.role, grant.c.revision.label('grant_revision'),
    ).select_from(context.join(activation, and_(
        activation.c.id == context.c.activation_id, activation.c.company_id == context.c.company_id,
        activation.c.pack_key == context.c.pack_key, activation.c.pack_version == context.c.pack_version,
    )).join(grant, and_(
        grant.c.context_id == context.c.id, grant.c.company_id == context.c.company_id, grant.c.branch_id == context.c.branch_id,
    )).join(branch, and_(branch.c.id == context.c.branch_id, branch.c.company_id == context.c.company_id))).where(
        context.c.company_id == company, grant.c.user_id == user_id, grant.c.active.is_(True),
        context.c.state == 'active', activation.c.state == 'active', branch.c.is_active.is_(True),
        context.c.branch_id.in_(allowed),
        ~exists(select(1).where(lifecycle.c.branch_id == branch.c.id, lifecycle.c.deleted_at.is_not(None))).correlate(branch),
    )
    if branch_ctx.branch_id is not None:
        statement = statement.where(context.c.branch_id == branch_ctx.branch_id)
    return db.connection().execute(statement.order_by(context.c.branch_id, context.c.id, grant.c.id)).mappings().all()


def _eligible(db, actor, branch_ctx, company, user_id):
    from app.access.entitlements import states
    from app.module_registry import is_app_enabled

    enabled = None
    result = []
    for row in _rows(db, company, user_id, branch_ctx):
        try:
            manifest = get_pack(row['pack_key'])
            role = get_role(manifest.key, row['role'])
        except PackRegistryError:
            continue
        if (row['pack_key'] != manifest.key or row['pack_version'] != manifest.version
                or any(not _positive(row[field]) for field in ('activation_revision', 'context_revision', 'grant_revision'))):
            continue
        if enabled is None:
            enabled = states(db, company)
        if any(not is_app_enabled(module) or enabled.get(module) is False for module in manifest.required_modules):
            continue
        result.append(PackScope(
            company_id=company, branch_id=row['branch_id'], context_id=row['context_id'],
            activation_id=row['activation_id'], pack_key=manifest.key, pack_version=manifest.version,
            user_id=user_id, grant_id=row['grant_id'], role=role.key, capabilities=role.capabilities,
            writable=row['branch_id'] in branch_ctx.writable,
            activation_revision=row['activation_revision'], context_revision=row['context_revision'], grant_revision=row['grant_revision'],
        ))
    return tuple(result)


def _has_history(db, company, branch_id):
    activation, context = PackActivation.__table__, PackContext.__table__
    statement = select(
        context.c.state, context.c.ever_activated, activation.c.state.label('activation_state'),
    ).select_from(context.outerjoin(activation, and_(
        activation.c.id == context.c.activation_id, activation.c.company_id == context.c.company_id,
        activation.c.pack_key == context.c.pack_key, activation.c.pack_version == context.c.pack_version,
    ))).where(context.c.company_id == company)
    if branch_id is not None:
        statement = statement.where(context.c.branch_id == branch_id)
    # Security/configuration revisions can advance before activation. Durable
    # history, rather than revision, prevents an activated context resetting to
    # draft from reopening the legacy branch namespace.
    return any(row.state != 'draft' or row.ever_activated is not False or row.activation_state not in {'draft', 'active'}
               for row in db.connection().execute(statement))


def available_contexts(db, actor, branch_ctx):
    """Own verified context pairs only; these capabilities grant no native action."""
    if not _installed(db):
        return ()
    company, user_id = _actor_company(db, actor, branch_ctx)
    return _eligible(db, actor, branch_ctx, company, user_id)


def _bound_result(db, result):
    if 'business_pack_request_binding' in db.info and db.info['business_pack_request_binding'] != result:
        _deny('Business Pack authorization changed during this request')
    return result


def resolve_context(db, actor, branch_ctx, requested_context_id=None):
    """Bind exactly one operational context, or preserve genuinely legacy scope.

    Invalid/revoked explicit selectors never fall back. All-branch reads with
    non-draft company pack history require an explicit eligible context. Company
    administrators and platform owners still need an operational PackUserGrant.
    Control-plane routes are explicitly handled by the caller, never inferred.
    """
    requested = _selector(requested_context_id)
    if not _installed(db):
        if requested is not None:
            raise HTTPException(503, 'Business Pack installation is required for context selection')
        return _bound_result(db, None)
    company, user_id = _actor_company(db, actor, branch_ctx)
    history = _has_history(db, company, branch_ctx.branch_id)
    if requested is None and not history:
        return _bound_result(db, None)
    if requested is None and branch_ctx.branch_id is None:
        _deny('Choose one assigned Business Pack context for an all-branch request')
    scopes = _eligible(db, actor, branch_ctx, company, user_id)
    if requested is not None:
        chosen = next((scope for scope in scopes if scope.context_id == requested), None)
        if chosen is None:
            _deny('Business Pack context is unavailable or not assigned to this actor and branch')
        return _bound_result(db, chosen)
    if len(scopes) == 1:
        return _bound_result(db, scopes[0])
    if len(scopes) > 1:
        _deny('Choose one assigned Business Pack context; multiple contexts are available')
    _deny()
