"""One native statistics read over explicitly owned Construction follow-ups.

The native aggregate, native own/team visibility and central native scope all
remain in force. The request's operational Session/boundary is never relaxed.
Only the aggregate dictionary escapes the closed, read-only resource Session.
"""
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import String, and_, event, exists, inspect, select
from sqlalchemy.orm import Session, with_loader_criteria

from .access import PackScope
from .boundary import _current
from .catalog_management import _module_grant
from .common_core import _native_authority
from .common_queries import assert_mapped_sources
from .operations import require


def deny(message='An authorized Construction statistics context is required'):
    raise HTTPException(403, message)


class _ModuleRead:
    """Frozen exact native enabled-module probe; no connection is returned."""
    def __init__(self, db, company):
        from app.apps.business_os.models import BOSEnabledModule
        from app.apps.business_os.services.module_service import CORE_MODULES
        self.statement = select(BOSEnabledModule.module_key, BOSEnabledModule.enabled).where(
            BOSEnabledModule.company_id == company, BOSEnabledModule.module_key.in_(CORE_MODULES.keys()))
        self.key = str(self.statement.compile(compile_kwargs={'literal_binds': True}))
        self.rows = db.connection().execute(self.statement).freeze()

    def execute(self, statement, parameters=None, **kwargs):
        if parameters or kwargs or str(statement.compile(compile_kwargs={'literal_binds': True})) != self.key:
            deny('Unreviewed native Construction statistics authority query')
        return self.rows()


class _Reader(Session):
    """Closed native ORM reader; public raw SQL and transaction escapes deny."""
    _orm_depth = 0
    _bootstrap = True

    def connection(self, *args, **kwargs):
        if self._bootstrap:
            return super().connection(*args, **kwargs)
        if args or kwargs:
            deny()
        return self._module_read

    @property
    def bind(self):
        if not self._orm_depth and not self._bootstrap:
            deny('Construction statistics cannot expose its native bind')
        return self._native_bind

    @bind.setter
    def bind(self, value):
        self._native_bind = value

    def get_bind(self, *args, **kwargs):
        if not self._orm_depth and not self._bootstrap:
            deny('Construction statistics cannot expose its native bind')
        return super().get_bind(*args, **kwargs)

    def _execute_internal(self, *args, **kwargs):
        self._orm_depth += 1
        try:
            return super()._execute_internal(*args, **kwargs)
        finally:
            self._orm_depth -= 1


def _authority(db, actor):
    from app.apps.crm.models import CRMOwner
    scope = db.info.get('business_pack_scope')
    branch = db.info.get('branch_context')
    state = inspect(actor, raiseerr=False)
    if (not isinstance(scope, PackScope) or scope.pack_key != 'construction'
            or state is None or not state.persistent or state.session is not db
            or scope.user_id != actor.id or scope.company_id != actor.organization_id
            or getattr(branch, 'company_id', None) != scope.company_id
            or getattr(branch, 'branch_id', None) != scope.branch_id):
        deny()
    require(db, actor, 'sites.view', 'reports.view')
    _current(scope, db.connection())
    fingerprint = _native_authority(db, actor, scope.company_id)
    grants = {key: _module_grant(db, actor, scope, key)
              for key in ('crm', 'srm', 'project_management')}
    suffixes = ('view', 'manage', 'admin', 'activities_view', 'activities_manage')
    names = {f'{key}_{suffix}' for key in ('crm', 'srm') for suffix in suffixes}
    names |= {'pms_view', 'pms_manage_tasks', 'pms_manage_projects', 'pms_admin'}
    if not actor.is_superuser and not any(
            grant.get('enabled') and 'view' in grant.get('actions', ())
            and names.intersection(grant.get('permissions', ())) for grant in grants.values()):
        deny('Fresh native follow-up view permission is required')
    owner = CRMOwner.__table__
    teams = tuple(db.connection().execute(select(owner.c.id, owner.c.team_id, owner.c.deleted_at).where(
        owner.c.organization_id == scope.company_id, owner.c.user_id == scope.user_id).order_by(owner.c.id)))
    return scope, fingerprint, grants, teams


def statistics(db, actor, native_operation=None):
    from app.access.scope import install_scope
    from app.apps.crm.models import CRMOwner
    from app.apps.business_os.models import BOSEnabledModule
    from app.branches.models import BranchOwnership
    from app.shared import follow_ups
    from .models import PackRecordOwnership
    expected = follow_ups._statistics_operation
    if native_operation is None:
        native_operation = expected
    if native_operation is not expected:
        deny('Construction statistics requires the native aggregate operation')
    authority = _authority(db, actor)
    scope, _, grants, _ = authority
    # A local principal prevents stale compiled permissions (for example a
    # revoked native admin grant) from changing native visible() semantics.
    current_module = getattr(actor, '_suite_current_module', None)
    permission_grants = [grants[current_module]] if current_module in grants else grants.values()
    permissions = [SimpleNamespace(name=name, module=key)
                   for key, grant in grants.items() if grant in permission_grants and grant.get('enabled')
                   for name in grant.get('permissions', ())]
    principal = SimpleNamespace(**{**actor.__dict__, '_suite_grants': grants,
        '_suite_permission_objects': permissions, 'employee': getattr(actor, 'employee', None)})
    follow, owned, native_owned = (model.__table__ for model in
        (follow_ups.FollowUp, PackRecordOwnership, BranchOwnership))
    exact_follow = and_(follow.c.organization_id == scope.company_id,
        exists().where(owned.c.resource_table == follow.name,
            owned.c.resource_key == follow.c.id.cast(String), owned.c.company_id == scope.company_id,
            owned.c.branch_id == scope.branch_id, owned.c.context_id == scope.context_id),
        exists().where(native_owned.c.resource_table == follow.name,
            native_owned.c.resource_key == follow.c.id.cast(String), native_owned.c.company_id == scope.company_id,
            native_owned.c.branch_id == scope.branch_id))
    criteria = {
        follow_ups.FollowUp: exact_follow,
        CRMOwner: and_(CRMOwner.organization_id == scope.company_id, CRMOwner.user_id == scope.user_id),
        BOSEnabledModule: BOSEnabledModule.company_id == scope.company_id,
    }
    native = _Reader(bind=db.connection(), autoflush=False, expire_on_commit=False,
                     join_transaction_mode='rollback_only')
    native.info.update(shared_actor=(scope.user_id, scope.company_id), security_write_request=False)
    cleanup = None
    def no_write(*args, **kwargs):
        deny('Construction statistics resource is read-only')
    try:
        # Invoke the existing central native predicate builder, including its
        # internal tenant/team authority lookups, before installing the closed
        # operational-source reader. Those authority facts never escape.
        prior_listeners = tuple(native.dispatch.do_orm_execute)
        cleanup = install_scope(native, principal, scope.company_id, grants)
        def restrict(execution):
            if not execution.is_select or not execution.is_orm_statement:
                deny('Construction statistics resource is read-only')
            assert_mapped_sources(execution.statement, frozenset(criteria))
            execution.statement = execution.statement.options(*(with_loader_criteria(model, criterion,
                include_aliases=True, propagate_to_loaders=True) for model, criterion in criteria.items()))
        # Central native criteria already use audited native subqueries. Guard
        # the requested mapper graph before native scope expands its predicates.
        native_listeners = [listener for listener in native.dispatch.do_orm_execute if listener not in prior_listeners]
        if len(native_listeners) != 1:
            deny('Native statistics scope has an unexpected reader graph')
        native_listener = native_listeners[0]
        event.remove(native, 'do_orm_execute', native_listener)
        event.listen(native, 'do_orm_execute', restrict)
        # Reinstalling native scope would repeat its bootstrap queries; retain
        # its actual listener object instead of copying its predicate logic.
        event.listen(native, 'do_orm_execute', native_listener)
        native._module_read = _ModuleRead(db, scope.company_id)
        native._bootstrap = False
        for name in ('add', 'add_all', 'delete', 'flush', 'commit', 'rollback', 'merge', 'begin', 'begin_nested',
                     'bulk_save_objects', 'bulk_insert_mappings', 'bulk_update_mappings'):
            setattr(native, name, no_write)
        event.listen(native, 'before_flush', no_write)
        event.listen(native, 'before_commit', no_write)
        result = native_operation(native, principal)
        if authority != _authority(db, actor):
            deny('Construction statistics native authority changed during the read')
        return result
    finally:
        if cleanup is not None:
            cleanup()
        native.close()
