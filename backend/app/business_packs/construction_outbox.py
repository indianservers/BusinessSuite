"""Canonical Construction source binding for the shared private-pack outbox.

The shared producer owns the genuine birth witness and immutable certificate.
These functions supply only the actual PMS source and its current recipient ACL.
No email body or event key is used to discover an authorization source.
"""
import re
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import and_, event, inspect, or_, select
from sqlalchemy.orm import Session, with_loader_criteria

from app.apps.project_management.models import PMSProject, PMSTask, PMSTaskAssignee
from app.branches.catalog import resource_key
from app.models.email_outbox import EmailOutbox
from .access import PackScope
from .common_queries import assert_mapped_sources
from .construction_planning import _owned


def _deny():
    raise HTTPException(403, 'Construction email requires its exact native source and recipient')


def _decode(table, key):
    if not isinstance(key, str) or len(key) > 100:
        _deny()
    if table == PMSTask.__tablename__:
        if not re.fullmatch(r'[1-9][0-9]{0,9}', key):
            _deny()
        if int(key) > 2147483647:
            _deny()
        return int(key), None
    if table != PMSTaskAssignee.__tablename__:
        _deny()
    match = re.fullmatch(r'([1-9][0-9]*):([1-9][0-9]{0,9}):([1-9][0-9]*):([1-9][0-9]{0,9})', key)
    if not match:
        _deny()
    size_task, task, size_user, user = match.groups()
    if int(size_task) != len(task) or int(size_user) != len(user):
        _deny()
    values = {'task_id': int(task), 'user_id': int(user)}
    if max(values.values()) > 2147483647:
        _deny()
    if resource_key(PMSTaskAssignee.__table__, values) != key:
        _deny()
    return values['task_id'], values['user_id']


def source_identity(native, outbox, scope):
    """Bind a pending native email to its actual same-session PMS source.

    This must run at the shared producer's pending-row birth phase. Loading an
    old email and attaching a source pointer cannot satisfy this contract.
    """
    from app.services.email_events import EVENTS
    from app.core.config import settings
    from .construction_definition import _DefinitionSession
    from .construction_planning import _PlanSession
    state = inspect(outbox, raiseerr=False)
    source = getattr(outbox, '_suite_source_record', None)
    source_state = inspect(source, raiseerr=False)
    if (type(native) not in {_DefinitionSession, _PlanSession}
            or not isinstance(scope, PackScope) or scope.pack_key != 'construction'
            or type(outbox) is not EmailOutbox or state is None or not state.pending
            or state.session is not native or outbox not in native.new or outbox.id is not None
            or native.info.get('shared_actor') != (scope.user_id, scope.company_id)
            or outbox.organization_id != scope.company_id or outbox.module != 'pms'
            or not outbox.recipient_user_id or source_state is None or not source_state.persistent
            or source_state.session is not native or source in native.deleted
            or type(source) not in {PMSTask, PMSTaskAssignee}):
        _deny()
    task_id = source.id if type(source) is PMSTask else source.task_id
    task = native.get(PMSTask, task_id)
    if task is None or task.deleted_at is not None:
        _deny()
    project = native.get(PMSProject, task.project_id)
    if project is None or project.organization_id != scope.company_id or project.branch_id != scope.branch_id or project.deleted_at is not None:
        _deny()
    if type(source) is PMSTask:
        if outbox.recipient_user_id not in {task.assignee_user_id, task.reporter_user_id}:
            _deny()
    elif source.user_id != outbox.recipient_user_id:
        _deny()
    # Validate the native event's supplied contents; they never select the
    # source. The source above came solely from the actual ORM source pointer.
    module, label, _, _, _, path = EVENTS[source.__tablename__]
    status = str(getattr(source, 'status', None) or getattr(source, 'execution_status', None) or '')
    subject = f'{label}: {status or "created"}'
    body = f'{label} #{task_id} has an update.'
    if status:
        body += f'\nCurrent status: {status}.'
    body += '\nSign in to review details: ' + settings.FRONTEND_PUBLIC_URL.rstrip('/') + path
    if outbox.module != module or outbox.subject != subject or outbox.body != body or outbox.is_html:
        _deny()
    model = type(source)
    key = resource_key(model.__table__, {column.name: getattr(source, column.name) for column in model.__table__.primary_key})
    _decode(model.__tablename__, key)
    return {'source_table': model.__tablename__, 'source_key': key}


def _current_source(connection, scope, source_table, source_key, recipient):
    task_id, assignment_user = _decode(source_table, source_key)
    task, project, assignment = (model.__table__ for model in (PMSTask, PMSProject, PMSTaskAssignee))
    row = connection.execute(select(task.c.project_id, task.c.assignee_user_id, task.c.reporter_user_id).where(
        task.c.id == task_id, task.c.deleted_at.is_(None), _owned(task, task.c.id, scope))).first()
    if row is None:
        _deny()
    parent = connection.execute(select(project.c.id).where(project.c.id == row.project_id,
        project.c.organization_id == scope.company_id, project.c.branch_id == scope.branch_id,
        project.c.deleted_at.is_(None), _owned(project, project.c.id, scope))).first()
    if parent is None:
        _deny()
    if assignment_user is None:
        if recipient not in {row.assignee_user_id, row.reporter_user_id}:
            _deny()
    elif assignment_user != recipient or connection.execute(select(assignment.c.task_id).where(
            assignment.c.task_id == task_id, assignment.c.user_id == assignment_user,
            _owned(assignment, None, scope))).first() is None:
        _deny()
    return row.project_id, task_id


def _native_visible(db, actor, scope, project_id, task_id):
    """Actual native task scope and project browse, over this source only."""
    from app.access.scope import install_scope
    from app.access.models import AccessPolicy, AccessMembership, AccessRole
    from app.apps.project_management.models import PMSProjectMember, PMSWorkspaceMember
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.apps.project_management.access import get_project_for_action
    from .construction_planning import _PlanSession, _PlanAuthority
    from .catalog_management import _module_grant
    connection = db.connection()
    workspace = connection.scalar(select(PMSProject.__table__.c.workspace_id).where(PMSProject.__table__.c.id == project_id))
    grants = {key: _module_grant(db, actor, scope, key) for key in ('project_management', 'srm', 'crm', 'hrms')}
    roles = set()
    for policy in connection.scalars(select(AccessPolicy.__table__.c.grants).where(
            AccessPolicy.__table__.c.company_id == scope.company_id, AccessPolicy.__table__.c.user_id == actor.id)):
        roles.update(value['roleId'] for value in (policy or {}).values() if isinstance(value, dict) and type(value.get('roleId')) is int)
    principal = SimpleNamespace(**{**actor.__dict__, 'employee': getattr(actor, 'employee', None),
        '_suite_grants': grants, '_suite_current_module': 'project_management', '_suite_admin_read': False,
        '_suite_permission_objects': [SimpleNamespace(name=name, module='project_management')
            for name in grants['project_management'].get('permissions', ())]})
    criteria = {
        PMSTask: and_(PMSTask.id == task_id, PMSTask.project_id == project_id, PMSTask.deleted_at.is_(None)),
        PMSTaskAssignee: and_(PMSTaskAssignee.task_id == task_id, PMSTaskAssignee.user_id == actor.id),
        PMSProject: and_(PMSProject.id == project_id, PMSProject.organization_id == scope.company_id, PMSProject.branch_id == scope.branch_id),
        PMSProjectMember: and_(PMSProjectMember.project_id == project_id, PMSProjectMember.user_id == actor.id),
        PMSWorkspaceMember: and_(PMSWorkspaceMember.workspace_id == workspace, PMSWorkspaceMember.user_id == actor.id),
        WorkspaceArchive: WorkspaceArchive.workspace_id == workspace,
        AccessPolicy: and_(AccessPolicy.company_id == scope.company_id, AccessPolicy.user_id == actor.id),
        AccessMembership: and_(AccessMembership.company_id == scope.company_id, AccessMembership.user_id == actor.id),
        AccessRole: and_(AccessRole.company_id == scope.company_id, AccessRole.id.in_(roles)),
    }
    native = _PlanSession(bind=connection, autoflush=False, expire_on_commit=False, join_transaction_mode='rollback_only')
    native._authority_reads = _PlanAuthority(connection, scope.company_id, {actor.id})
    native._planning_connection, native._can_write = connection, False
    native.info.update(shared_actor=(actor.id, scope.company_id), security_write_request=False)
    cleanup = None
    try:
        prior = tuple(native.dispatch.do_orm_execute)
        cleanup = install_scope(native, principal, scope.company_id, grants)
        added = [listener for listener in native.dispatch.do_orm_execute if listener not in prior]
        if len(added) != 1:
            _deny()
        event.remove(native, 'do_orm_execute', added[0])
        def restrict(execution):
            if not execution.is_select or not execution.is_orm_statement:
                _deny()
            assert_mapped_sources(execution.statement, frozenset(criteria))
            execution.statement = execution.statement.options(*(with_loader_criteria(model, condition,
                include_aliases=True, propagate_to_loaders=True) for model, condition in criteria.items()))
        event.listen(native, 'do_orm_execute', restrict)
        event.listen(native, 'do_orm_execute', added[0])
        event.listen(native, 'before_flush', lambda *args: _deny())
        event.listen(native, 'before_commit', lambda *args: _deny())
        if native.query(PMSTask.id).filter(PMSTask.id == task_id).first() is None:
            return False
        return get_project_for_action(native, project_id, principal, 'browse') is not None
    finally:
        if cleanup:
            cleanup()
        native.close()


def source_access(db, *, company_id, branch_id, context_id, recipient_user_id, source_table, source_key):
    """Fresh native/pack/branch ACL, after the shared certificate is verified.

    The caller retains immutable sidecar/payload/lifecycle-version checks and
    generic current-email checks. No session or principal escapes this function.
    """
    from app.access.models import AccessPolicy, AccessRole, AccessMembership
    from app.access.service import check_background_access
    from app.branches.models import BranchGrant, BranchPolicy, BranchLifecycle
    from app.branches.service import context as branch_context
    from app.models.user import User, Role, Permission, role_permissions
    from app.models.company import Company, Branch
    from app.models.employee import Employee
    from app.common.models import CommonPerson
    from app.core.tenant_boundary import company_ids
    from .access import resolve_context
    from .catalog_management import _module_grant
    from .construction_workpackages import task_source
    from .common_core import _native_authority
    from .boundary import _current
    if any(type(value) is not int or not 1 <= value <= 2147483647 for value in (company_id, branch_id, context_id, recipient_user_id)):
        return False
    connection = db.connection()
    local = Session(bind=connection, autoflush=False, expire_on_commit=False, join_transaction_mode='rollback_only')
    roles = set()
    for policy in connection.scalars(select(AccessPolicy.__table__.c.grants).where(
            AccessPolicy.__table__.c.company_id == company_id, AccessPolicy.__table__.c.user_id == recipient_user_id)):
        roles.update(value['roleId'] for value in (policy or {}).values() if isinstance(value, dict) and type(value.get('roleId')) is int)
    for policy in connection.scalars(select(BranchGrant.__table__.c.module_grants).where(
            BranchGrant.__table__.c.company_id == company_id, BranchGrant.__table__.c.branch_id == branch_id,
            BranchGrant.__table__.c.user_id == recipient_user_id)):
        roles.update(value['roleId'] for value in (policy or {}).values() if isinstance(value, dict) and type(value.get('roleId')) is int)
    role_id = select(User.__table__.c.role_id).where(User.__table__.c.id == recipient_user_id)
    criteria = {
        User: User.id == recipient_user_id, Role: Role.id.in_(role_id),
        Permission: Permission.id.in_(select(role_permissions.c.permission_id).where(role_permissions.c.role_id.in_(role_id))),
        AccessPolicy: and_(AccessPolicy.company_id == company_id, AccessPolicy.user_id == recipient_user_id),
        AccessRole: and_(AccessRole.company_id == company_id, AccessRole.id.in_(roles)),
        AccessMembership: and_(AccessMembership.company_id == company_id, AccessMembership.user_id == recipient_user_id),
        Branch: and_(Branch.id == branch_id, Branch.company_id == company_id), Company: Company.id == company_id,
        BranchGrant: and_(BranchGrant.company_id == company_id, BranchGrant.branch_id == branch_id, BranchGrant.user_id == recipient_user_id),
        BranchPolicy: and_(BranchPolicy.company_id == company_id, BranchPolicy.user_id == recipient_user_id),
        BranchLifecycle: BranchLifecycle.branch_id == branch_id,
        Employee: and_(Employee.user_id == recipient_user_id, or_(
            Employee.branch_id.in_(select(Branch.__table__.c.id).where(Branch.__table__.c.company_id == company_id)),
            Employee.branch_id.is_(None) & (company_id == 1))),
        CommonPerson: and_(CommonPerson.user_id == recipient_user_id, CommonPerson.organization_id == company_id),
    }
    def restrict(execution):
        if not execution.is_select or not execution.is_orm_statement:
            _deny()
        assert_mapped_sources(execution.statement, frozenset(criteria), allowed_associations=(role_permissions,))
        execution.statement = execution.statement.options(*(with_loader_criteria(model, condition,
            include_aliases=True, propagate_to_loaders=True) for model, condition in criteria.items()))
    event.listen(local, 'do_orm_execute', restrict)
    event.listen(local, 'before_flush', lambda *args: _deny())
    event.listen(local, 'before_commit', lambda *args: _deny())
    try:
        actor = local.get(User, recipient_user_id)
        if actor is None or not actor.is_active or company_id not in company_ids(local, actor):
            return False
        actor.organization_id = company_id  # Fresh principal, after persisted tenancy proof.
        actor.role  # Exact persisted role is part of the finite source inventory.
        branch = branch_context(local, actor, company_id, str(branch_id))
        scope = resolve_context(local, actor, branch, context_id)
        if scope is None or scope.pack_key != 'construction' or 'construction.sites.view' not in scope.capabilities:
            return False
        grant = _module_grant(local, actor, scope, 'project_management')
        if not grant.get('enabled') or 'view' not in grant.get('actions', ()):
            return False
        check_background_access(local, actor, 'project_management', 'view', branch_id=branch_id,
            administrative_read=False, stamp=False)
        actor._suite_grants = {'project_management': grant}
        actor._suite_current_module = 'project_management'
        actor._suite_admin_read = False
        actor._suite_permission_objects = [SimpleNamespace(name=name, module='project_management') for name in grant.get('permissions', ())]
        local.info.update(business_pack_scope=scope, branch_context=branch,
            shared_actor=(actor.id, company_id), security_boundary=company_id, security_write_request=False)
        authority = _native_authority(local, actor, company_id)
        project_id, task_id = _current_source(connection, scope, source_table, source_key, actor.id)
        task_source(local, actor, project_id, task_id)
        if not _native_visible(local, actor, scope, project_id, task_id):
            return False
        # Re-read the actual source after native ACL evaluation as well.
        _current_source(connection, scope, source_table, source_key, actor.id)
        _current(scope, connection)
        if authority != _native_authority(local, actor, company_id):
            return False
        return True
    except (HTTPException, ValueError, TypeError, AttributeError, KeyError):
        return False
    finally:
        local.close()


def source_allowed(db, certificate, recipient, scope):
    """Shared PackDeliverySource callback, after its immutable proof checks."""
    state = inspect(recipient, raiseerr=False)
    if (not isinstance(scope, PackScope) or scope.pack_key != 'construction'
            or db.info.get('business_pack_scope') is not scope or state is None
            or not state.persistent or state.session is not db
            or recipient.id != scope.user_id or not recipient.is_active
            or (certificate.company_id, certificate.branch_id, certificate.context_id,
                certificate.pack_key, certificate.pack_version, certificate.recipient_user_id)
            != (scope.company_id, scope.branch_id, scope.context_id, 'construction', scope.pack_version, recipient.id)
            or certificate.module not in {'pms', 'project_management'}
            or certificate.source_table not in {'pms_tasks', 'pms_task_assignees'}):
        return False
    return source_access(db, company_id=scope.company_id, branch_id=scope.branch_id, context_id=scope.context_id,
        recipient_user_id=recipient.id, source_table=certificate.source_table, source_key=certificate.source_key)
