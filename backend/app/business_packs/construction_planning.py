"""Finite native PMS scheduling over one explicitly owned Construction graph.

The existing scheduler owns dependency/calendar/resource calculations. This
adapter supplies its exact canonical source graph, not a second project/task
master or a general PMS/HR session.
"""
from copy import deepcopy
import json
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import re
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import String, and_, event, exists, inspect, or_, select
from sqlalchemy.orm import Session, with_loader_criteria
from sqlalchemy.sql.elements import TextClause

from .boundary import _current
from .common_core import _native_authority
from .common_queries import assert_mapped_sources
from .construction import _project_epoch, _source, project_for_action
from .construction_documents import _AuthorityReads, _Writer
from .operations import require

_CHECKS = WeakKeyDictionary()


def _start_checks(db):
    if db in _CHECKS:
        deny('Native Construction write commands cannot nest')
    _CHECKS[db] = []


def _final_checks(db):
    checks = _CHECKS.get(db)
    if not checks:
        deny('A native Construction write requires its retained source lease')
    for check in checks:
        check()


def _drop_checks(db):
    _CHECKS.pop(db, None)


def deny(message='Construction planning source is unavailable', status=403):
    raise HTTPException(status, message)


def _task_email(row, source, actor, scope, native, recipients=None):
    from app.core.config import settings
    recipients = recipients or {actor.id: {'id': actor.id, 'email': actor.email}}
    if (source is None or inspect(source).session is not native
            or {source.assignee_user_id, source.reporter_user_id} - {None, *recipients}):
        deny('Native task mail needs its separately reviewed recipient graph')
    recipient = recipients.get(row.recipient_user_id)
    status = str(source.status or '')
    body = f'Task #{source.id} has an update.' + (f'\nCurrent status: {status}.' if status else '')
    body += '\nSign in to review details: ' + settings.FRONTEND_PUBLIC_URL.rstrip('/') + '/pms/my-work'
    suffix = sha256(recipient['email'].casefold().encode()).hexdigest() if recipient else ''
    if (getattr(row, '_suite_source_record', None) is not source or row.organization_id != scope.company_id
            or row.module != 'pms' or recipient is None or row.recipient_user_id not in {source.assignee_user_id, source.reporter_user_id}
            or row.recipient != recipient['email']
            or row.subject != 'Task: ' + (status or 'updated') or row.body != body or row.is_html
            or row.status != 'queued' or not re.fullmatch(r'event:[0-9a-f]{32}:' + suffix, row.event_key)):
        deny('Native task mail requires the exact actual changed source')


def _owned(table, key, scope):
    from .models import PackRecordOwnership
    from app.branches.models import BranchOwnership
    from app.branches.catalog import key_expression
    key = key.cast(String) if key is not None else key_expression(table)
    pack, branch = PackRecordOwnership.__table__, BranchOwnership.__table__
    return and_(exists().where(pack.c.resource_table == table.name,
        pack.c.resource_key == key, pack.c.company_id == scope.company_id,
        pack.c.branch_id == scope.branch_id, pack.c.context_id == scope.context_id),
        exists().where(branch.c.resource_table == table.name, branch.c.resource_key == key,
            branch.c.company_id == scope.company_id, branch.c.branch_id == scope.branch_id))


def _graph(db, actor, project_id, write=False, actual=False):
    from app.apps.project_management.models import (PMSTask, PMSTaskAssignee, PMSTaskDependency,
        PMSWorkspaceEntry, PMSTaskWorkspaceState, PMSChecklistItem)
    require(db, actor, *(['billing.prepare' if actual == 'cost_actual' else 'boq.prepare' if actual == 'cost_budget' else 'diary.record'] if actual else ['boq.prepare', 'settings.manage'] if write else ['sites.view', 'reports.view']))
    scope, workspace_id = _source(db, actor, project_id)
    from .catalog_management import _module_grant
    grant = _module_grant(db, actor, scope, 'project_management')
    native_action = 'edit' if actual else 'create' if write else 'view'
    if not actor.is_superuser and (not grant.get('enabled') or native_action not in grant.get('actions', ())):
        deny('Fresh native PMS module action is required for Construction planning')
    from app.access.service import check_background_access
    check_background_access(db, actor, 'project_management', native_action, administrative_read=False, stamp=False)
    project_for_action(db, actor, project_id, 'edit_project' if actual in {'cost_actual', 'cost_budget'} else 'manage_tasks' if write else 'browse')
    connection = db.connection()
    task, assignment, dependency, entry = (m.__table__ for m in
        (PMSTask, PMSTaskAssignee, PMSTaskDependency, PMSWorkspaceEntry))
    ids = tuple(connection.scalars(select(task.c.id).where(task.c.project_id == project_id,
        task.c.deleted_at.is_(None)).order_by(task.c.id)))
    if len(ids) > 1000:
        deny('Advanced scheduling currently supports up to 1,000 tasks per project', 422)
    if connection.scalar(select(exists().where(task.c.id.in_(ids), ~_owned(task, task.c.id, scope)))):
        deny('Every planned native task requires explicit Construction ownership', 409)
    if connection.scalar(select(exists().where(task.c.id.in_(ids), task.c.parent_task_id.is_not(None),
            task.c.parent_task_id.notin_(ids)))):
        deny('Reconcile native work-package parents outside the active Construction project', 409)
    dependencies = tuple(connection.execute(select(dependency).where(or_(dependency.c.task_id.in_(ids),
        dependency.c.depends_on_task_id.in_(ids))).order_by(dependency.c.id)))
    if any(row.task_id not in ids or row.depends_on_task_id not in ids for row in dependencies):
        deny("Resolve dependencies outside this project's active task set before planning", 409)
    if connection.scalar(select(exists().where(dependency.c.id.in_([row.id for row in dependencies]),
            ~_owned(dependency, dependency.c.id, scope)))):
        deny('Every dependency requires explicit Construction ownership', 409)
    assignments = tuple(connection.execute(select(assignment.c.task_id, assignment.c.user_id).where(assignment.c.task_id.in_(ids)).order_by(assignment.c.task_id, assignment.c.user_id)))
    if connection.scalar(select(exists().where(assignment.c.task_id.in_(ids), ~_owned(assignment, None, scope)))):
        deny('Every planned assignment requires explicit Construction ownership', 409)
    users = {actor.id, *(row.user_id for row in assignments)}
    users.update(connection.scalars(select(task.c.assignee_user_id).where(task.c.id.in_(ids), task.c.assignee_user_id.is_not(None))))
    kind = f'sc{project_id:x}'
    entries = tuple(connection.scalars(select(entry.c.id).where(entry.c.workspace_id == workspace_id, entry.c.kind == kind))) if workspace_id else ()
    if len(entries) > 1:
        deny('Canonical project schedule state requires reconciliation', 409)
    if entries and connection.scalar(select(exists().where(entry.c.id.in_(entries), ~_owned(entry, entry.c.id, scope)))):
        deny('The retained native schedule requires explicit Construction ownership', 409)
    for model in (PMSTaskWorkspaceState, PMSChecklistItem):
        table = model.__table__
        if connection.scalar(select(exists().where(table.c.task_id.in_(ids), ~_owned(table, None, scope)))):
            deny('Native task progress requires explicit Construction ownership', 409)
    return scope, workspace_id, ids, tuple(row.id for row in dependencies), users, entries


def _capacity_epoch(db, actor, project_id, data):
    """Existence/availability facts only; never return HR records to the caller."""
    if not data.level_resources:
        return None
    from app.apps.project_management.models import PMSTask, PMSPlannerPreference, PMSUserCapacity
    from app.models.employee import Employee
    from app.models.user import User
    from app.models.company import Branch
    from app.models.leave import LeaveRequest
    from app.models.attendance import Holiday
    scope, _, ids, _, users, _ = _graph(db, actor, project_id, True)
    connection = db.connection()
    task, pref, capacity, employee, branch, leave, holiday, user = (model.__table__ for model in
        (PMSTask, PMSPlannerPreference, PMSUserCapacity, Employee, Branch, LeaveRequest, Holiday, User))
    starts = list(connection.scalars(select(task.c.start_date).where(task.c.id.in_(ids))))
    if data.start_date:
        starts.append(data.start_date)
    if not starts or any(value is None for value in starts):
        # Actual native scheduler returns its original dated-task validation.
        return None
    start, end = min(starts), min(starts) + timedelta(days=365)
    employee_ids = select(employee.c.id).where(employee.c.user_id.in_(users), employee.c.branch_id.in_(
        select(branch.c.id).where(branch.c.company_id == scope.company_id)))
    statements = (
        select(user.c.id, user.c.is_active).where(user.c.id.in_(users)).order_by(user.c.id),
        select(pref).where(pref.c.user_id.in_(users)).order_by(pref.c.user_id),
        select(capacity).where(capacity.c.organization_id == scope.company_id, capacity.c.user_id.in_(users), capacity.c.week_start_date.between(start-timedelta(days=6), end)).order_by(capacity.c.id),
        select(leave.c.id, leave.c.employee_id, leave.c.from_date, leave.c.to_date, leave.c.is_half_day).where(leave.c.company_id == scope.company_id, leave.c.employee_id.in_(employee_ids), leave.c.status == 'Approved', leave.c.deleted_at.is_(None), leave.c.from_date <= end, leave.c.to_date >= start).order_by(leave.c.id),
        select(holiday.c.id, holiday.c.holiday_date, holiday.c.is_active, holiday.c.applicable_branches).where(holiday.c.is_active.is_(True), holiday.c.holiday_date.between(start, end)).order_by(holiday.c.id),
    )
    return sha256(repr([tuple(connection.execute(statement)) for statement in statements]).encode()).hexdigest()


class _PlanAuthority(_AuthorityReads):
    def __init__(self, connection, company, users):
        super().__init__(connection, company)
        from .models import PackRecordOwnership
        self.columns[PackRecordOwnership.__tablename__] = [] if inspect(connection).has_table(PackRecordOwnership.__tablename__) else None
        from app.access.models import AccessPolicy
        self.columns[AccessPolicy.__tablename__] = [] if inspect(connection).has_table(AccessPolicy.__tablename__) else None
        from app.common.models import CommonPerson
        from app.models.employee import Employee
        from app.models.company import Branch
        from app.access.models import AccessMembership
        from .construction_documents import _key
        person, employee, branch, membership = (m.__table__ for m in (CommonPerson, Employee, Branch, AccessMembership))
        for uid in users:
            for statement in (
                select(person.c.organization_id).where(person.c.user_id == uid, person.c.organization_id.is_not(None)),
                select(branch.c.company_id).select_from(employee.join(branch, employee.c.branch_id == branch.c.id)).where(employee.c.user_id == uid),
                select(membership.c.company_id).where(membership.c.user_id == uid, membership.c.active.is_(True)),
                select(membership.c.company_id).where(membership.c.user_id == uid, membership.c.active.is_(False))):
                self.rows[_key(statement)] = connection.execute(statement).freeze()
        self.fingerprint = sha256(repr([(key, frozen.data) for key, frozen in self.rows.items()]).encode()).hexdigest()


class _PlanSession(_Writer):
    def get_bind(self, *args, **kwargs):
        if not self._orm_depth:
            return SimpleNamespace(dialect=self._authority_reads.dialect)
        return super().get_bind(*args, **kwargs)

    def execute(self, statement, *args, **kwargs):
        # The native activity helper emits only this one advisory lock after
        # reading real task-linked communication cache identities.
        if isinstance(statement, TextClause) and str(statement) == 'SELECT pg_advisory_xact_lock(211028004)' and self._can_write:
            return self._planning_connection.exec_driver_sql(str(statement))
        return super().execute(statement, *args, **kwargs)


def _run(db, actor, project_id, action, data=None, baseline_id=None, file_format='csv'):
    from app.access.models import AccessMembership, AccessPolicy, AccessRole
    from app.access.scope import install_scope
    from app.apps.project_management import scheduling
    from app.apps.project_management.models import (PMSProject, PMSProjectMember, PMSWorkspaceMember,
        PMSTask, PMSTaskAssignee, PMSTaskDependency, PMSWorkspaceEntry, PMSActivity,
        PMSPlannerPreference, PMSUserCapacity, PMSTaskWorkspaceState, PMSChecklistItem)
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.apps.business_os.models import BOSEnabledModule
    from app.models.user import User, Role, Permission, role_permissions
    from app.models.email_outbox import EmailOutbox
    from app.models.employee import Employee
    from app.models.company import Company, Branch
    from app.common.models import CommonPerson
    from app.models.leave import LeaveRequest
    from app.models.attendance import Holiday
    from app.shared.communication.models import FollowUp as ChatFollowUp, CommunicationEvent
    from app.shared.models import ServiceEvent
    from .catalog_management import _module_grant
    from .models import PackRecordOwnership
    from app.branches.models import BranchOwnership

    if action not in {'analysis', 'preview', 'apply', 'capture', 'tasks', 'baseline', 'export', 'task_actual', 'cost_actual', 'cost_budget'}:
        deny('Unreviewed Construction planning operation')
    actual = action in {'task_actual', 'cost_actual', 'cost_budget'}
    write = action in {'apply', 'capture'} or actual
    management = action in {'preview', 'apply', 'capture'} or actual
    source_graph = _graph(db, actor, project_id, management, action if actual else False)
    scope, workspace_id, task_ids, dependency_ids, users, entries = source_graph
    users = set(users)
    resource_plan = bool(data is not None and getattr(data, 'level_resources', False))
    if resource_plan and len(users) > 51:
        deny('Native resource leveling supports up to 50 assignees', 422)
    if not resource_plan:
        # CPM, baselines and handover source reads need no other person's HR or
        # company identity graph, even when many users are assigned to tasks.
        users = {actor.id}
    connection = db.connection()
    mail_tasks = task_ids if action == 'apply' else (data['task_id'],) if action == 'task_actual' else ()
    task_table = PMSTask.__table__
    def mail_refs():
        return tuple(connection.execute(select(task_table.c.id, task_table.c.assignee_user_id, task_table.c.reporter_user_id)
            .where(task_table.c.id.in_(mail_tasks)).order_by(task_table.c.id)))
    mail_source = mail_refs()
    recipient_ids = {uid for row in mail_source for uid in (row.assignee_user_id, row.reporter_user_id) if uid is not None and uid != actor.id}
    if len(recipient_ids) > 50:
        deny('Native task mail supports up to 50 explicitly verified resource recipients', 422)
    def recipient_proofs():
        if not recipient_ids:
            return []
        from .construction_dependencies import resource_sources
        return resource_sources(db, actor, project_id, ids=recipient_ids)
    mail_proofs = recipient_proofs()
    recipients = {actor.id: {'id': actor.id, 'email': actor.email}, **{row['id']: row for row in mail_proofs}}
    users.update(recipient_ids)
    authority, epoch = _native_authority(db, actor, scope.company_id), _project_epoch(db, scope, project_id)
    grants = {key: _module_grant(db, actor, scope, key) for key in ('project_management', 'hrms', 'crm', 'srm')}
    role_ids = {g['roleId'] for g in grants.values() if isinstance(g, dict) and type(g.get('roleId')) is int}
    auth_users = {actor.id, *recipient_ids}
    for policy in connection.scalars(select(AccessPolicy.__table__.c.grants).where(
            AccessPolicy.__table__.c.company_id == scope.company_id, AccessPolicy.__table__.c.user_id.in_(auth_users))):
        role_ids.update(grant['roleId'] for grant in (policy or {}).values() if isinstance(grant, dict) and type(grant.get('roleId')) is int)
    legacy_roles = set(connection.scalars(select(User.__table__.c.role_id).where(User.__table__.c.id.in_(auth_users))))
    employee_ids = select(Employee.__table__.c.id).where(Employee.__table__.c.user_id.in_(users),
        Employee.__table__.c.branch_id.in_(select(Branch.__table__.c.id).where(Branch.__table__.c.company_id == scope.company_id)))
    kind = f'sc{project_id:x}'
    def fact(value):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if isinstance(value, datetime) and value.tzinfo else value
    task_fields = ('id', 'task_key', 'title', 'parent_task_id', 'status', 'start_date', 'due_date',
        'estimated_hours', 'actual_hours', 'completed_at', 'updated_at', 'assignee_user_id', 'reporter_user_id', 'is_blocking')
    def task_facts():
        return {row.id: {name: fact(getattr(row, name)) for name in task_fields} for row in connection.execute(
            select(*(task_table.c[name] for name in task_fields)).where(task_table.c.id.in_(task_ids)).order_by(task_table.c.id))}
    def dependency_facts():
        table = PMSTaskDependency.__table__
        return tuple(tuple(fact(value) for value in row) for row in connection.execute(select(table).where(table.c.id.in_(dependency_ids)).order_by(table.c.id)))
    def assignment_facts():
        table = PMSTaskAssignee.__table__
        return tuple(tuple(fact(value) for value in row) for row in connection.execute(select(table).where(table.c.task_id.in_(task_ids)).order_by(table.c.task_id, table.c.user_id)))
    def entry_facts():
        table = PMSWorkspaceEntry.__table__
        return {row.id: {column.name: fact(getattr(row, column.name)) for column in table.columns}
            for row in connection.execute(select(table).where(table.c.workspace_id == workspace_id, table.c.kind == kind))}
    expected_tasks, expected_state = task_facts(), entry_facts()
    original_dependencies, original_assignments = dependency_facts(), assignment_facts()
    verify_outputs = not write
    criteria = {
        PMSProject: and_(PMSProject.id == project_id, PMSProject.organization_id == scope.company_id, PMSProject.branch_id == scope.branch_id),
        PMSTask: and_(PMSTask.project_id == project_id, PMSTask.id.in_(task_ids)),
        PMSTaskAssignee: PMSTaskAssignee.task_id.in_(task_ids),
        PMSTaskWorkspaceState: and_(PMSTaskWorkspaceState.task_id.in_(task_ids), _owned(PMSTaskWorkspaceState.__table__, PMSTaskWorkspaceState.task_id, scope)),
        PMSChecklistItem: and_(PMSChecklistItem.task_id.in_(task_ids), _owned(PMSChecklistItem.__table__, PMSChecklistItem.id, scope)),
        PMSTaskDependency: PMSTaskDependency.id.in_(dependency_ids),
        PMSWorkspaceEntry: and_(PMSWorkspaceEntry.workspace_id == workspace_id, PMSWorkspaceEntry.kind == kind),
        PMSProjectMember: and_(PMSProjectMember.project_id == project_id, PMSProjectMember.user_id.in_(auth_users)),
        PMSWorkspaceMember: and_(PMSWorkspaceMember.workspace_id == workspace_id, PMSWorkspaceMember.user_id.in_(users)),
        WorkspaceArchive: WorkspaceArchive.workspace_id == workspace_id,
        AccessMembership: and_(AccessMembership.company_id == scope.company_id, AccessMembership.user_id.in_(users)),
        AccessPolicy: and_(AccessPolicy.company_id == scope.company_id, AccessPolicy.user_id.in_(auth_users)),
        AccessRole: and_(AccessRole.company_id == scope.company_id, AccessRole.id.in_(role_ids)),
        Company: Company.id == scope.company_id,
        User: User.id.in_(users), Role: Role.id.in_(legacy_roles),
        Permission: Permission.id.in_(select(role_permissions.c.permission_id).where(role_permissions.c.role_id.in_(legacy_roles))),
        Employee: Employee.id.in_(employee_ids),
        Branch: Branch.company_id == scope.company_id,
        CommonPerson: and_(CommonPerson.organization_id == scope.company_id, CommonPerson.user_id.in_(users)),
        BOSEnabledModule: BOSEnabledModule.company_id == scope.company_id,
        PMSPlannerPreference: PMSPlannerPreference.user_id.in_(users),
        PMSUserCapacity: and_(PMSUserCapacity.organization_id == scope.company_id, PMSUserCapacity.user_id.in_(users)),
        LeaveRequest: and_(LeaveRequest.company_id == scope.company_id, LeaveRequest.employee_id.in_(employee_ids), LeaveRequest.status == 'Approved', LeaveRequest.deleted_at.is_(None)),
        Holiday: Holiday.is_active.is_(True),
        ChatFollowUp: and_(ChatFollowUp.workspace_id == workspace_id, ChatFollowUp.task_id.in_(task_ids)),
        EmailOutbox: and_(EmailOutbox.organization_id == scope.company_id, EmailOutbox.module == 'pms',
            EmailOutbox.recipient_user_id.in_(recipients), _owned(EmailOutbox.__table__, EmailOutbox.id, scope)),
    }
    lease = None
    if actual:
        from .construction_actuals import _Actual
        lease = _Actual(db, actor, project_id, action, data, scope, workspace_id, task_ids, recipients)
        criteria.update(lease.criteria())
    native = _PlanSession(bind=connection, autoflush=False, expire_on_commit=False,
        join_transaction_mode='create_savepoint' if write else 'rollback_only')
    native._authority_reads = _PlanAuthority(connection, scope.company_id, users)
    native._planning_connection, native._can_write = connection, write
    native.info.update(shared_actor=(scope.user_id, scope.company_id), branch_context=db.info.get('branch_context'), security_write_request=management)
    minted = []
    stamped = set()
    changed_tasks = {}
    changed_entries = {}
    cleanup = None
    def current():
        _current(scope, connection)
        if authority != _native_authority(db, actor, scope.company_id) or epoch != _project_epoch(db, scope, project_id):
            deny('Native Construction planning authority changed')
        if native._authority_reads.fingerprint != _PlanAuthority(connection, scope.company_id, users).fingerprint:
            deny('Native Construction resource identities or control facts changed')
        fresh_graph = _graph(db, actor, project_id, management, action if actual else False)
        expected_entries = {*entries, *(row.id for row in minted if type(row) is PMSWorkspaceEntry and id(row) in stamped)}
        if fresh_graph[1:5] != source_graph[1:5] or set(fresh_graph[5]) != expected_entries:
            deny('The actual native Construction planning source graph changed', 409)
        if dependency_facts() != original_dependencies or assignment_facts() != original_assignments:
            deny('Canonical native dependency or resource assignment facts changed', 409)
        if verify_outputs and (task_facts() != expected_tasks or entry_facts() != expected_state):
            deny('The certified native task schedule or retained state changed', 409)
        if mail_source != mail_refs() or mail_proofs != recipient_proofs():
            deny('Native task email recipient authority or source assignment changed')
        if lease:
            lease.current()
    def validate(session, *args):
        current()
        if lease:
            lease.validate(session, minted)
            return
        if not write or session.deleted:
            deny('Native Construction planning cannot delete or perform unreviewed writes')
        for row in session.dirty:
            changed = {name for name, attr in inspect(row).attrs.items() if attr.history.has_changes()}
            if type(row) is PMSTask and row.id in task_ids:
                if row.project_id != project_id or changed - {'start_date', 'due_date', 'updated_at'}:
                    deny('A schedule plan may change only its actual native task dates')
                if changed & {'start_date', 'due_date'}:
                    if {row.assignee_user_id, row.reporter_user_id} - {None, *recipients}:
                        deny('Native schedule mail requires a separately reviewed recipient graph', 422)
                    changed_tasks[row.id] = row
            elif type(row) is PMSWorkspaceEntry and row.id in entries:
                if row.workspace_id != workspace_id or row.kind != kind or changed - {'body'}:
                    deny('Native schedule state identity is immutable')
                changed_entries[row.id] = row
            else:
                deny('Unreviewed native planning update')
        for row in session.new:
            if row.id is not None and row not in minted:
                deny('Planning requires genuinely new native audit/state identities')
            if type(row) is PMSWorkspaceEntry:
                if entries or row.workspace_id != workspace_id or row.kind != kind or row.author_id != actor.id or row.task_id is not None:
                    deny('Native schedule state must belong to the exact project')
            elif type(row) is PMSActivity:
                if (row.project_id != project_id or row.actor_user_id != actor.id or row.sprint_id is not None
                        or (row.action == 'schedule.changed' and (row.task_id not in task_ids or row.entity_id != row.task_id or row.entity_type != 'task'))
                        or (row.action == 'schedule.baseline' and (row.task_id is not None or row.entity_id != project_id or row.entity_type != 'project'))
                        or row.action not in {'schedule.changed', 'schedule.baseline'}):
                    deny('Schedule activity requires its exact native task/project')
            elif type(row) is CommunicationEvent:
                table = ChatFollowUp.__table__
                if not connection.scalar(select(exists().where(table.c.workspace_id == row.workspace_id,
                        table.c.workspace_id == workspace_id, table.c.conversation_id == row.conversation_id,
                        table.c.task_id.in_(task_ids)))):
                    deny('Schedule cache event requires a real linked task source')
            elif type(row) is ServiceEvent:
                source = getattr(row, '_suite_source_record', None)
                if (type(source) is not PMSTask or source is not changed_tasks.get(row.entity_id)
                        or inspect(source).session is not session or source.project_id != project_id
                        or row.organization_id != scope.company_id or row.actor_id != actor.id
                        or row.module_key != 'project_management' or row.entity_type != 'task'
                        or row.event_type != 'record.updated' or row.status not in {'pending', 'depth_limited'}
                        or not isinstance(row.payload_json, dict) or set(row.payload_json) != {'depth', 'data'}
                        or row.payload_json.get('data') != {}):
                    deny('Native task event requires its real validated schedule-date mutation')
            elif type(row) is EmailOutbox:
                _task_email(row, changed_tasks.get(getattr(getattr(row, '_suite_source_record', None), 'id', None)), actor, scope, session, recipients)
            else:
                deny('Unreviewed native planning insert: ' + type(row).__tablename__)
            if row not in minted:
                minted.append(row)
    def restrict(execution):
        if lease and lease.bulk(execution):
            return
        if not execution.is_select or not execution.is_orm_statement:
            deny('Construction planning has no general query/write authority')
        assert_mapped_sources(execution.statement, frozenset(criteria), allowed_associations=(role_permissions,))
        execution.statement = execution.statement.options(*(with_loader_criteria(model, criterion,
            include_aliases=True, propagate_to_loaders=True) for model, criterion in criteria.items()))
    def stamp_births(*args):
        # The first native flush can birth the project schedule entry and queue
        # runtime events for a second flush. Certify only genuinely persistent
        # validated births before that second flush rechecks the exact graph.
        for row in minted:
            if id(row) in stamped:
                continue
            if inspect(row).session is not native or not inspect(row).persistent:
                deny('Schedule ownership requires the actual flushed native birth')
            from app.branches.catalog import resource_key
            key = resource_key(type(row).__table__, {column.name: getattr(row, column.name) for column in row.__table__.primary_key})
            for table, extra in ((BranchOwnership.__table__, {}), (PackRecordOwnership.__table__, {'context_id': scope.context_id, 'revision': 1})):
                connection.execute(table.insert().values(resource_table=row.__tablename__, resource_key=key,
                    company_id=scope.company_id, branch_id=scope.branch_id, source='construction-native-schedule', **extra))
            stamped.add(id(row))
    try:
        # Actual native central scope remains in force, then the closed source
        # inventory restricts requested ORM graphs before those native filters.
        principal = native.get(User, actor.id)
        for key, value in actor.__dict__.items():
            if key.startswith('_suite_'):
                setattr(principal, key, value)
        principal._suite_grants = grants
        principal._suite_current_module = 'project_management'
        principal._suite_permission_objects = [SimpleNamespace(name=name, module='project_management')
            for name in grants['project_management'].get('permissions', ())]
        principal._suite_admin_read = False
        membership = AccessMembership.__table__
        principal._suite_is_company_admin = bool(connection.scalar(select(membership.c.is_admin).where(
            membership.c.company_id == scope.company_id, membership.c.user_id == actor.id, membership.c.active.is_(True))))
        prior = tuple(native.dispatch.do_orm_execute)
        cleanup = install_scope(native, principal, scope.company_id, grants)
        added = [listener for listener in native.dispatch.do_orm_execute if listener not in prior]
        if len(added) != 1:
            deny('Unexpected native planning scope graph')
        event.remove(native, 'do_orm_execute', added[0])
        event.listen(native, 'do_orm_execute', restrict)
        event.listen(native, 'do_orm_execute', added[0])
        event.listen(native, 'before_flush', validate)
        event.listen(native, 'after_flush_postexec', stamp_births)
        for proof in mail_proofs:
            target = native.get(User, proof['id'])
            target_grant = _module_grant(db, target, proof['epoch'][1], 'project_management')
            target._suite_grants = {'project_management': target_grant}
            target._suite_current_module = 'project_management'
            target._suite_permission_objects = [SimpleNamespace(name=name, module='project_management') for name in target_grant.get('permissions', ())]
            target._suite_admin_read = False
            target._suite_is_company_admin = bool(connection.scalar(select(membership.c.is_admin).where(
                membership.c.company_id == scope.company_id, membership.c.user_id == target.id, membership.c.active.is_(True))))
        if lease:
            result = lease.run(native, principal)
        elif action == 'tasks':
            tasks = native.query(PMSTask).filter(PMSTask.id.in_(task_ids)).order_by(PMSTask.id).all()
            if {task.id for task in tasks} != set(task_ids):
                deny('The native project task set is outside the current planning visibility', 404)
            states = {row.task_id: row for row in native.query(PMSTaskWorkspaceState).filter(PMSTaskWorkspaceState.task_id.in_(task_ids))}
            checks = native.query(PMSChecklistItem).filter(PMSChecklistItem.task_id.in_(task_ids)).all()
            result = []
            for task in tasks:
                state = states.get(task.id)
                own_checks = [check for check in checks if check.task_id == task.id]
                # Match the native task-workspace progress presentation. No
                # physical/earned quantity is inferred from this task percent.
                progress = round(100 * sum(check.is_completed for check in own_checks) / len(own_checks)) if state and state.progress_mode == 'checklist' and own_checks else state.progress if state else 0
                if task.status in {'Done', 'Completed', 'Closed'}:
                    progress = 100
                result.append({**{name: getattr(task, name) for name in ('id', 'parent_task_id', 'task_key', 'title', 'status', 'completed_at', 'updated_at', 'start_date', 'due_date', 'estimated_hours', 'actual_hours')}, 'progress_percent': progress, 'progress_revision': state.revision if state else 0, 'progress_mode': state.progress_mode if state else 'manual'})
        elif action == 'baseline':
            row = native.query(PMSWorkspaceEntry).filter_by(workspace_id=workspace_id, kind=kind).first() if workspace_id else None
            state = json.loads(row.body) if row else {}
            selected = next((item for item in state.get('baselines', []) if item.get('id') == baseline_id), None)
            if selected is None:
                deny('Native baseline not found in this Construction project', 404)
            result = selected
        elif action == 'export':
            result = scheduling.export_variance(project_id, baseline_id, file_format, native, principal)
        elif action == 'analysis':
            result = scheduling.analysis(project_id, baseline_id, native, principal)
        elif action == 'preview':
            result = scheduling.preview(project_id, data, native, principal)
        elif action == 'apply':
            result = scheduling.apply_operation(project_id, data, native, principal, commit=False)
        else:
            result = scheduling.capture_baseline_operation(project_id, data, native, principal, commit=False)
        if write:
            stamp_births()
            native.flush()
            stamp_births()
            for tid, row in changed_tasks.items():
                for name in ('start_date', 'due_date', 'updated_at'):
                    expected_tasks[tid][name] = fact(getattr(row, name))
            if lease and lease.kind == 'task_actual':
                for name in ('status', 'actual_hours', 'completed_at', 'updated_at'):
                    expected_tasks[lease.task_id][name] = fact(getattr(lease.root, name))
            for eid, row in changed_entries.items():
                expected_state[eid]['body'] = row.body
            for row in minted:
                if type(row) is PMSWorkspaceEntry and id(row) in stamped:
                    expected_state[row.id] = {column.name: fact(getattr(row, column.name)) for column in row.__table__.columns}
            verify_outputs = True
            current()
            if db not in _CHECKS:
                deny('A native Construction write requires its outer command lease')
            _CHECKS[db].append(current)
            Session.commit(native)
        else:
            current()
        return deepcopy(result)
    finally:
        if cleanup is not None:
            cleanup()
        native.close()


def analysis(db, actor, project_id, baseline_id=None):
    return _run(db, actor, project_id, 'analysis', baseline_id=baseline_id)


def preview(db, actor, project_id, data):
    return _run(db, actor, project_id, 'preview', data)


def task_sources(db, actor, project_id):
    """All actual nondeleted canonical tasks, or fail closed on any hidden row."""
    return _run(db, actor, project_id, 'tasks')


def baseline_source(db, actor, project_id, baseline_id):
    return _run(db, actor, project_id, 'baseline', baseline_id=baseline_id)


def export_variance(db, actor, project_id, baseline_id=None, file_format='csv'):
    from app.access.service import check_background_access
    from .catalog_management import _module_grant
    if file_format not in {'csv', 'xlsx'}:
        deny('Choose csv or xlsx for native schedule variance', 422)
    scope, _ = _source(db, actor, project_id)
    grant = _module_grant(db, actor, scope, 'project_management')
    if not actor.is_superuser and (not grant.get('enabled') or 'export' not in grant.get('actions', ())):
        deny('Fresh native PMS export action is required')
    check_background_access(db, actor, 'project_management', 'export', administrative_read=False, stamp=False)
    return _run(db, actor, project_id, 'export', baseline_id=baseline_id, file_format=file_format)


def apply(db, actor, project_id, data, *, commit=True):
    _start_checks(db)
    guard = None
    try:
        if not commit:
            db.flush()
        capacity = _capacity_epoch(db, actor, project_id, data)
        if not commit:
            guard = db.connection().begin_nested()
        with db.begin_nested():
            result = _run(db, actor, project_id, 'apply', data)
        _final_checks(db)
        _graph(db, actor, project_id, True)
        _native_authority(db, actor, actor.organization_id)
        if capacity != _capacity_epoch(db, actor, project_id, data):
            deny('Native resource capacity changed while applying the plan', 409)
        if commit:
            db.commit()
        else:
            guard.commit()
        return result
    except Exception:
        if commit:
            db.rollback()
        elif guard is not None and guard.is_active:
            guard.rollback()
            db.expire_all()
        raise
    finally:
        _drop_checks(db)


def capture(db, actor, project_id, data, *, commit=True):
    _start_checks(db)
    guard = None
    try:
        if not commit:
            db.flush()
            guard = db.connection().begin_nested()
        with db.begin_nested():
            result = _run(db, actor, project_id, 'capture', data)
        _final_checks(db)
        _graph(db, actor, project_id, True)
        _native_authority(db, actor, actor.organization_id)
        if commit:
            db.commit()
        else:
            guard.commit()
        return result
    except Exception:
        if commit:
            db.rollback()
        elif guard is not None and guard.is_active:
            guard.rollback()
            db.expire_all()
        raise
    finally:
        _drop_checks(db)
