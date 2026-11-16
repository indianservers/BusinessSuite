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
            or certificate.source_table not in {'pms_tasks', 'pms_task_assignees', 'pms_workspace_members'}):
        return False
    if certificate.source_table == 'pms_workspace_members':
        return _member_source_allowed(db, certificate, recipient, scope)
    return source_access(db, company_id=scope.company_id, branch_id=scope.branch_id, context_id=scope.context_id,
        recipient_user_id=recipient.id, source_table=certificate.source_table, source_key=certificate.source_key)


def verify_native_emitter(native, scope, parent, frame):
    from .construction_emitter import verify_native_emitter as verify
    return verify(native, scope, parent=parent, frame=frame)


def issuer_allowed(db, certificate, actual_issuer, scope):
    """Original issuer's current authority, separate from recipient eligibility.

    This is a predicate for the shared retained certificate verifier. It cannot
    mint a certificate, reinterpret its recipient, or authorize a provider.
    """
    from app.models.user import User
    from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember
    from .common_core import _native_authority
    from .boundary import _current
    from .operations import require
    state = inspect(actual_issuer, raiseerr=False)
    if (type(actual_issuer) is not User or state is None or not state.persistent
            or state.session is not db or actual_issuer in db.deleted or not actual_issuer.is_active
            or not isinstance(scope, PackScope) or scope.pack_key != 'construction'
            or db.info.get('business_pack_scope') is not scope or scope.user_id != actual_issuer.id
            or getattr(certificate, 'actor_user_id', None) != actual_issuer.id
            or (certificate.company_id, certificate.branch_id, certificate.context_id,
                certificate.pack_key, certificate.pack_version)
            != (scope.company_id, scope.branch_id, scope.context_id, 'construction', scope.pack_version)
            or certificate.module not in {'pms', 'project_management'}):
        return False
    try:
        authority = _native_authority(db, actual_issuer, scope.company_id)
        _current(scope, db.connection())
        if certificate.source_table == 'pms_workspace_members':
            from .construction_workspace_members import access
            key = certificate.source_key
            if not isinstance(key, str) or not re.fullmatch(r'[1-9][0-9]{0,9}', key) or int(key) > 2147483647:
                return False
            member, workspace = PMSWorkspaceMember.__table__, PMSWorkspace.__table__
            def member_facts():
                return db.connection().execute(select(member.c.id, member.c.workspace_id,
                    member.c.user_id, member.c.role).where(member.c.id == int(key),
                    member.c.user_id == certificate.recipient_user_id, member.c.role.in_(('Member','Admin')),
                    _owned(member, member.c.id, scope), member.c.workspace_id.in_(select(workspace.c.id).where(
                        workspace.c.organization_id == scope.company_id, _owned(workspace, workspace.c.id, scope))))).first()
            before = member_facts()
            if before is None:
                return False
            # Includes settings.manage, native PMS create/edit/view + Sales
            # create, and the actual native Workspace Owner/Admin guard.
            access(db, actual_issuer, before.workspace_id)
            if before != member_facts():
                return False
        elif certificate.source_table in {'pms_tasks', 'pms_task_assignees'}:
            from .construction_workpackages import task_source
            task_id, assignee = _decode(certificate.source_table, certificate.source_key)
            task, assignment = PMSTask.__table__, PMSTaskAssignee.__table__
            def task_facts():
                row = db.connection().execute(select(task.c.project_id, task.c.parent_task_id).where(
                    task.c.id == task_id, task.c.deleted_at.is_(None), _owned(task, task.c.id, scope))).first()
                if row is None:
                    _deny()
                if assignee is not None and db.connection().execute(select(assignment.c.task_id).where(
                        assignment.c.task_id == task_id, assignment.c.user_id == assignee,
                        _owned(assignment, None, scope))).first() is None:
                    _deny()
                return row
            before = task_facts()
            require(db, actual_issuer, 'sites.view')
            task_source(db, actual_issuer, before.project_id, task_id)
            # Exercise PMS visibility through the finite native reader, rather
            # than asking the common delivery reader to acquire PMS query rights.
            if not _native_visible(db, actual_issuer, scope, before.project_id, task_id):
                return False
            if before != task_facts():
                return False
        else:
            return False
        _current(scope, db.connection())
        return authority == _native_authority(db, actual_issuer, scope.company_id)
    except (HTTPException, ValueError, TypeError, AttributeError, KeyError):
        return False


def _member_notice(native, notice, scope, *, pending):
    from app.models.notification import Notification
    from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember
    from .construction_workspace_members import _MemberSession
    plan = getattr(native, '_member_plan', None)
    state = inspect(notice, raiseerr=False)
    member = getattr(notice, '_suite_source_record', None)
    member_state = inspect(member, raiseerr=False)
    if (type(native) is not _MemberSession or plan is None or plan.scope is not scope
            or not isinstance(scope, PackScope) or scope.pack_key != 'construction'
            or native.info.get('shared_actor') != (scope.user_id, scope.company_id)
            or type(notice) is not Notification or notice is not plan.notice
            or state is None or state.session is not native or notice in native.deleted
            or notice not in plan.births
            or (pending and (not state.pending or notice.id is not None or notice not in native.new))
            or (not pending and (not state.persistent or not notice.id))
            or type(member) is not PMSWorkspaceMember or member is not plan.root
            or member_state is None or not member_state.persistent or member_state.session is not native
            or member in native.deleted or id(member) not in plan.stamped
            or not member.id or member.workspace_id != plan.wid or member.user_id != plan.reference.id
            or member.role != plan.data.role or member.role not in {'Member', 'Admin'}):
        _deny()
    plan.current()
    workspace = PMSWorkspace.__table__
    name = plan.db.connection().scalar(select(workspace.c.name).where(
        workspace.c.id == member.workspace_id, workspace.c.organization_id == scope.company_id,
        _owned(workspace, workspace.c.id, scope)))
    if (name is None or notice.company_id != scope.company_id or notice.user_id != member.user_id
            or notice.title != 'Added to workspace' or notice.module != 'project_management'
            or notice.event_type != 'workspace.member_added'
            or notice.message != f'You were added to {name} as {member.role}.'
            or notice.action_url != f'/pms/workspaces?workspace={member.workspace_id}'):
        _deny()
    return member


def notice_identity(native, notice, scope):
    """Describe only the pending native notice's genuine born membership."""
    member = _member_notice(native, notice, scope, pending=True)
    return {'source_table': 'pms_workspace_members', 'source_key': str(member.id)}


def notification_email_identity(native, outbox, scope):
    """Describe the native email's persisted notice, without delivery authority."""
    import hashlib
    from app.core.config import settings
    state = inspect(outbox, raiseerr=False)
    if (type(outbox) is not EmailOutbox or state is None or not state.pending
            or state.session is not native or outbox.id is not None or outbox not in native.new):
        _deny()
    notice = getattr(outbox, '_suite_source_record', None)
    member = _member_notice(native, notice, scope, pending=False)
    plan = native._member_plan
    suffix = hashlib.sha256(plan.reference.email.casefold().encode()).hexdigest()
    body = (f'Business Suite notification #{notice.id} has an update.\nSign in to review details: '
        + settings.FRONTEND_PUBLIC_URL.rstrip('/') + '/notifications')
    if (outbox.organization_id != scope.company_id or outbox.module != 'notifications'
            or outbox.recipient_user_id != member.user_id or outbox.recipient != plan.reference.email
            or outbox.subject != 'Business Suite notification: created' or outbox.body != body
            or outbox.is_html or not isinstance(outbox.event_key, str)
            or not re.fullmatch(r'event:[0-9a-f]{32}:' + suffix, outbox.event_key)):
        _deny()
    return {'source_table': 'notifications', 'source_key': str(notice.id)}


def _member_source_allowed(db, certificate, recipient, scope):
    """Revalidate an exact certified membership under the recipient's own ACL."""
    from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.models.notification import Notification
    from .construction_workspace_members import target_proof
    from .boundary import _current
    key = certificate.source_key
    if not isinstance(key, str) or not re.fullmatch(r'[1-9][0-9]{0,9}', key) or int(key) > 2147483647:
        return False
    member, workspace, archived = PMSWorkspaceMember.__table__, PMSWorkspace.__table__, WorkspaceArchive.__table__
    def facts():
        return db.connection().execute(select(member.c.id, member.c.workspace_id, member.c.user_id, member.c.role,
            workspace.c.name).select_from(member.join(workspace, member.c.workspace_id == workspace.c.id)).where(
            member.c.id == int(key), member.c.user_id == recipient.id, member.c.role.in_(('Member','Admin')),
            _owned(member, member.c.id, scope),
            workspace.c.organization_id == scope.company_id, _owned(workspace, workspace.c.id, scope),
            ~select(archived.c.workspace_id).where(archived.c.workspace_id == workspace.c.id,
                archived.c.deleted_at.is_not(None)).exists())).first()
    try:
        before = facts()
        if before is None:
            return False
        notice_id = getattr(certificate, 'notification_id', None)
        def notice_matches():
            # The shared certificate seals this historical native payload. Its
            # fixed action URL binds the same-ID membership to its born parent.
            # A renamed workspace intentionally fails closed until its native
            # notice is superseded; body text never discovers the source.
            if notice_id is None:
                return True  # Internal mint has already checked the live pointer.
            if type(notice_id) is not int or not 1 <= notice_id <= 2147483647:
                return False
            notice = Notification.__table__
            row = db.connection().execute(select(notice.c.title, notice.c.message, notice.c.module,
                notice.c.event_type, notice.c.action_url).where(notice.c.id == notice_id,
                notice.c.company_id == scope.company_id, notice.c.user_id == recipient.id,
                _owned(notice, notice.c.id, scope))).first()
            return row is not None and tuple(row) == ('Added to workspace',
                f'You were added to {before.name} as {before.role}.', 'project_management',
                'workspace.member_added', f'/pms/workspaces?workspace={before.workspace_id}')
        if not notice_matches():
            return False
        reference, epoch = target_proof(db, recipient, scope, recipient.id)
        _current(scope, db.connection())
        fresh_reference, fresh_epoch = target_proof(db, recipient, scope, recipient.id)
        return reference == fresh_reference and epoch == fresh_epoch and before == facts() and notice_matches()
    except (HTTPException, ValueError, TypeError, AttributeError, KeyError):
        return False
