"""Typed canonical PMS project/WBS births inside one owned Construction workspace."""
import json
import hashlib
import re
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import String, and_, bindparam, event, exists, inspect, or_, select, update
from sqlalchemy.orm import Session, with_loader_criteria

from app.core.deps import get_db, get_current_user
from app.apps.project_management.models import (PMSProject, PMSWorkspace, PMSWorkspaceMember, PMSProjectMember,
    PMSTask, PMSTaskAssignee, PMSBoard, PMSBoardColumn, PMSFileAsset, PMSActivity, PMSWorkspaceEntry)
from app.apps.project_management.recovery_models import RecoveryChange
from app.apps.srm.industry_models import IndustryRecord
from app.branches.models import BranchOwnership
from app.models.email_outbox import EmailOutbox
from .models import PackRecordOwnership
from .access import PackScope
from .boundary import _current
from .common_core import _native_authority
from .common_queries import assert_mapped_sources
from .construction import _source, _project_epoch, project_for_action
from .construction_documents import _Writer
from .construction_planning import _PlanAuthority, _owned
from .operations import require

router = APIRouter(tags=['Construction project definition'])
KINDS = {'project_definition', 'task_definition'}
_COMMANDS = WeakKeyDictionary()


class _DefinitionSession(_Writer):
    def get_bind(self, *args, **kwargs):
        if not self._orm_depth:
            # Native scope chooses its schema probe by dialect; this facade
            # provides no driver, engine, execute method or raw connection.
            return SimpleNamespace(dialect=self._authority_reads.dialect)
        return super().get_bind(*args, **kwargs)


def fail(message, status=409):
    raise HTTPException(status, message)


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    workspace_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=180)
    project_key: str = Field(min_length=1, max_length=20)
    description: str = Field(default='', max_length=10000)
    start_date: date
    due_date: date
    estimated_cost: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    estimated_hours: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    @model_validator(mode='after')
    def dates(self):
        if self.due_date < self.start_date:
            raise ValueError('Project due date must follow its start date')
        self.project_key = self.project_key.strip().upper()
        self.name = self.name.strip()
        if not self.name or not self.project_key:
            raise ValueError('Project name and key are required')
        return self


class TaskInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    title: str = Field(min_length=1, max_length=220)
    task_key: str = Field(min_length=1, max_length=30)
    description: str = Field(default='', max_length=10000)
    parent_task_id: int | None = Field(default=None, gt=0)
    assignee_user_ids: list[int] = Field(default_factory=list, max_length=50)
    start_date: date
    due_date: date
    estimated_hours: Decimal = Field(gt=0, max_digits=10, decimal_places=2)

    @model_validator(mode='after')
    def dates(self):
        if self.due_date < self.start_date:
            raise ValueError('Task due date must follow its start date')
        self.task_key, self.title = self.task_key.strip().upper(), self.title.strip()
        if not self.task_key or not self.title:
            raise ValueError('Task title and key are required')
        if any(type(value) is not int or value <= 0 for value in self.assignee_user_ids):
            raise ValueError('Assignees require canonical positive user IDs')
        self.assignee_user_ids = sorted(set(self.assignee_user_ids))
        return self


def _workspace(db, actor, scope, workspace_id):
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    table = PMSWorkspace.__table__
    connection = db.connection()
    row = connection.execute(select(table).where(table.c.id == workspace_id,
        table.c.organization_id == scope.company_id, _owned(table, table.c.id, scope))).first()
    if row is None:
        fail('Choose an explicitly owned canonical Construction workspace', 404)
    members = tuple(connection.execute(select(PMSWorkspaceMember.__table__).where(
        PMSWorkspaceMember.__table__.c.workspace_id == workspace_id,
        PMSWorkspaceMember.__table__.c.user_id == actor.id)))
    archive = connection.execute(select(WorkspaceArchive.__table__).where(
        WorkspaceArchive.__table__.c.workspace_id == workspace_id)).first()
    if archive is not None and archive.deleted_at is not None:
        fail('The native workspace is archived', 404)
    return tuple(row), members, tuple(archive) if archive else None


def _access(db, actor, project_id=None):
    from app.apps.srm.industry_api import context
    from app.access.service import check_background_access
    scope = db.info.get('business_pack_scope')
    if not isinstance(scope, PackScope) or scope.pack_key != 'construction' or scope.user_id != actor.id:
        fail('A selected Construction definition context is required', 403)
    require(db, actor, *(['settings.manage'] if project_id is None else ['boq.prepare']))
    _current(scope, db.connection())
    epoch = _native_authority(db, actor, scope.company_id)
    context(db, actor, True)
    check_background_access(db, actor, 'srm', 'create', administrative_read=False, stamp=False)
    check_background_access(db, actor, 'project_management', 'create', administrative_read=False, stamp=False)
    if epoch != _native_authority(db, actor, scope.company_id):
        fail('Native Construction definition authority changed while waiting', 403)
    if project_id is not None:
        project_for_action(db, actor, project_id, 'manage_tasks')
    return scope


def _replay(db, actor, scope, data, kind, project_id):
    from app.apps.srm.industry_api import digest
    row = IndustryRecord.__table__
    # Global UUID reservation remains blind to foreign/private record bodies.
    found = db.connection().execute(select(row.c.id, row.c.project_id).where(
        row.c.organization_id == scope.company_id, row.c.branch_id == scope.branch_id,
        row.c.request_id == str(data.request_id))).first()
    if found is None:
        return None
    owner = PackRecordOwnership.__table__
    if not db.connection().scalar(select(exists().where(owner.c.resource_table == row.name,
        owner.c.resource_key == str(found.id), owner.c.company_id == scope.company_id,
        owner.c.branch_id == scope.branch_id, owner.c.context_id == scope.context_id))):
        fail('This request identity is already reserved')
    project_for_action(db, actor, found.project_id)
    existing = db.query(IndustryRecord).filter_by(id=found.id).one()
    if existing.kind != kind or existing.data['_request_digest'] != digest(data) or (project_id is not None and existing.project_id != project_id):
        fail('Definition request identity was already used with different details')
    return existing.data['native_result']


class _Birth:
    def __init__(self, db, actor, scope, data, project_id=None):
        self.db, self.actor, self.scope, self.data = db, actor, scope, data
        self.kind = 'project_definition' if project_id is None else 'task_definition'
        self.project_id = project_id
        self.root, self.births, self.stamped, self.expected = None, [], set(), None
        self.workspace_id = data.workspace_id if project_id is None else _source(db, actor, project_id)[1]
        if self.workspace_id is None:
            fail('Create WBS tasks in a canonical workspace-linked project', 422)
        self.authority = _native_authority(db, actor, scope.company_id)
        self.workspace_epoch = _workspace(db, actor, scope, self.workspace_id)
        self.project_epoch = _project_epoch(db, scope, project_id) if project_id is not None else None
        self.task_ids, self.board_ids, self.column_ids = (), (), ()
        self.recovery_ids = ()
        self.resource_proofs = []
        if project_id is not None:
            if data.assignee_user_ids:
                from .construction_dependencies import resource_sources
                self.resource_proofs = resource_sources(db, actor, project_id, data.assignee_user_ids)
            from .construction_planning import _graph
            _, _, self.task_ids, _, _, _ = _graph(db, actor, project_id, True)
            project = db.connection().execute(select(PMSProject.__table__).where(PMSProject.__table__.c.id == project_id)).first()
            if data.parent_task_id is not None:
                from .construction_workpackages import task_source
                task_source(db, actor, project_id, data.parent_task_id, action='manage_tasks')
                parent = db.connection().execute(select(PMSTask.__table__).where(PMSTask.__table__.c.id == data.parent_task_id)).first()
                if parent.sprint_id is not None or parent.epic_id is not None:
                    fail('Native advanced parent planning links require their separately reviewed source adapter', 422)
            board, column = PMSBoard.__table__, PMSBoardColumn.__table__
            self.board_ids = tuple(db.connection().scalars(select(board.c.id).where(board.c.project_id == project_id)))
            self.column_ids = tuple(db.connection().scalars(select(column.c.id).where(column.c.board_id.in_(self.board_ids))))
            for table, identities in ((board, self.board_ids), (column, self.column_ids)):
                if db.connection().scalar(select(exists().where(table.c.id.in_(identities), ~_owned(table, table.c.id, scope)))):
                    fail('Native project board configuration requires explicit Construction ownership')
            entry = PMSWorkspaceEntry.__table__
            for body in db.connection().scalars(select(entry.c.body).where(entry.c.workspace_id == self.workspace_id, entry.c.kind == 'auto_rule')):
                rule = json.loads(body)
                if rule.get('enabled') and rule.get('project_id') == project_id and rule.get('trigger') == 'task.created':
                    fail('Review the native task-created automation source before using this minimal WBS creation command')
            history = RecoveryChange.__table__
            if db.connection().scalar(select(exists().where(history.c.workspace_id == self.workspace_id,
                    history.c.actor_id == actor.id, history.c.state == 'undone',
                    or_(history.c.task_id.notin_(self.task_ids), ~_owned(history, history.c.id, scope))))):
                fail('Resolve the native undo branch outside this Construction project before creating WBS tasks')
            self.recovery_ids = tuple(db.connection().scalars(select(history.c.id).where(
                history.c.workspace_id == self.workspace_id, history.c.actor_id == actor.id,
                history.c.state == 'undone', history.c.task_id.in_(self.task_ids), _owned(history, history.c.id, scope))))

    @property
    def pid(self):
        return self.project_id if self.project_id is not None else self.root.id if self.root is not None else -1

    @property
    def tid(self):
        return self.root.id if self.kind == 'task_definition' and self.root is not None else -1

    def current(self):
        _current(self.scope, self.db.connection())
        if (self.authority != _native_authority(self.db, self.actor, self.scope.company_id)
                or self.workspace_epoch != _workspace(self.db, self.actor, self.scope, self.workspace_id)
                or self.project_id is not None and self.project_epoch != _project_epoch(self.db, self.scope, self.project_id)):
            fail('Native Construction definition authority or parent source changed', 403)
        if self.kind == 'task_definition' and self.data.parent_task_id is not None:
            from .construction_workpackages import task_source
            task_source(self.db, self.actor, self.project_id, self.data.parent_task_id, action='manage_tasks')
        if self.resource_proofs:
            from .construction_dependencies import resource_sources
            if self.resource_proofs != resource_sources(self.db, self.actor, self.project_id, self.data.assignee_user_ids):
                fail('Native Construction resource authority changed', 403)
        if self.root is not None and id(self.root) in self.stamped:
            table = type(self.root).__table__
            actual = self.db.connection().execute(select(table).where(table.c.id == self.root.id)).first()
            if (actual is None or any(getattr(actual, key) != value for key, value in self.expected.items())
                    or self.kind == 'project_definition' and actual.organization_id != self.scope.company_id):
                fail('The actual canonical definition changed before commit', 403)

    def validate(self, session, *args):
        from app.shared.models import ServiceEvent
        from app.apps.project_management.recovery import task_state
        self.current()
        if session.deleted:
            fail('Native definition creation cannot delete business records', 403)
        if any(session.is_modified(row, include_collections=False) for row in session.dirty if row not in self.births):
            fail('Native definition creation cannot rewrite existing business records', 403)
        for row in session.new:
            if row not in self.births and type(row) is not PMSTaskAssignee and any(getattr(row, key.name) is not None for key in row.__table__.primary_key):
                fail('Definition creation requires genuinely new native identities', 403)
            if type(row) is (PMSProject if self.kind == 'project_definition' else PMSTask):
                if self.root is not None and row is not self.root:
                    fail('One definition command may create exactly one canonical root', 403)
                self.root = row
                if self.kind == 'project_definition' and row.organization_id != self.scope.company_id:
                    fail('Native project must belong to the selected Construction company', 403)
                if any(getattr(row, key) != value for key, value in self.expected.items()):
                    fail('Native definition root differs from the exact canonical input', 403)
            elif type(row) is PMSProjectMember:
                if self.kind != 'project_definition' or row.project_id != self.pid or row.user_id != self.actor.id or row.role != 'Manager':
                    fail('Definition may create only its actual author project membership', 403)
            elif type(row) is PMSTaskAssignee:
                if (self.kind != 'task_definition' or self.root is None or row not in self.root.assignments
                        or row.user_id not in self.data.assignee_user_ids or row.task_id not in {None, self.tid}
                        or row.source_key is not None or row.reviewer_user_id is not None):
                    fail('Definition assignment requires its exact new native task and eligible resource', 403)
            elif type(row) is PMSBoard:
                if self.kind != 'task_definition' or self.board_ids or row.project_id != self.pid or row.name != 'Default Board' or row.board_type != 'Kanban':
                    fail('Definition board must be its actual missing native default', 403)
            elif type(row) is PMSBoardColumn:
                boards = {*self.board_ids, *(item.id for item in self.births if type(item) is PMSBoard and item.id is not None)}
                allowed = {'BACKLOG': 'Backlog', 'TODO': 'To Do', 'IN_PROGRESS': 'In Progress', 'IN_REVIEW': 'In Review', 'DONE': 'Done'}
                if self.kind != 'task_definition' or row.board_id not in boards or allowed.get(row.status_key) != row.name or row.wip_limit is not None:
                    fail('Definition may create only exact default native board stages', 403)
            elif type(row) is PMSActivity:
                if row.project_id != self.pid or row.actor_user_id != self.actor.id or row.action not in {'project.created', 'task.created', 'subtask.created'}:
                    fail('Definition activity must belong to its actual new native source', 403)
                expected_id = self.data.parent_task_id if row.action == 'subtask.created' else self.tid if self.kind == 'task_definition' else self.pid
                if row.entity_id != (self.tid if row.action == 'subtask.created' else expected_id) or row.task_id != (expected_id if self.kind == 'task_definition' else None):
                    fail('Definition activity cannot reference another task or project', 403)
            elif type(row) is RecoveryChange:
                if (self.kind != 'task_definition' or row.workspace_id != self.workspace_id or row.actor_id != self.actor.id
                        or row.task_id != self.tid or row.state != 'applied' or row.after != task_state(self.root)
                        or not row.before.get('deleted_at') or {k: v for k, v in row.before.items() if k != 'deleted_at'} != {k: v for k, v in row.after.items() if k != 'deleted_at'}):
                    fail('Definition recovery history must be the native new-task birth', 403)
            elif type(row) is EmailOutbox:
                from app.core.config import settings
                source = getattr(row, '_suite_source_record', None)
                assignment = (type(source) is PMSTaskAssignee and source in self.births
                    and self.root is not None and source in self.root.assignments and source.user_id == row.recipient_user_id)
                label, path = ('Assigned task', '/dashboard') if assignment else ('Task', '/pms/my-work')
                expected_body = (f'{label} #{self.tid} has an update.\nCurrent status: To Do.\nSign in to review details: '
                    + settings.FRONTEND_PUBLIC_URL.rstrip('/') + path)
                recipients = {self.actor.id: self.actor.email, **{item['id']: item['email'] for item in self.resource_proofs}}
                address = recipients.get(row.recipient_user_id, '')
                suffix = hashlib.sha256(address.casefold().encode()).hexdigest()
                if (self.kind != 'task_definition' or not (source is self.root or assignment)
                        or row.organization_id != self.scope.company_id or row.module != 'pms'
                        or not address or row.recipient != address
                        or row.subject != label + ': To Do' or row.body != expected_body or row.is_html
                        or row.status != 'queued' or not re.fullmatch(r'event:[0-9a-f]{32}:' + suffix, row.event_key)):
                    fail('Definition email must retain its actual native task and reporter', 403)
            elif type(row) is ServiceEvent:
                source = getattr(row, '_suite_source_record', None)
                standard = source is self.root and row.event_type == 'record.created' and row.payload_json == {'depth': row.payload_json.get('depth'), 'data': {}}
                pipeline = (self.kind == 'task_definition' and row.event_type == 'pipeline.stage_entered'
                    and row.payload_json.get('origin') == 'pipeline_workspace'
                    and row.payload_json.get('data') == {'previous_stage': 'None', 'stage': 'To Do', 'previous_stage_name': 'Created',
                        'stage_name': 'To Do', 'owner_id': self.data.assignee_user_ids[0] if self.data.assignee_user_ids else None,
                        'scope': f'project:{self.pid}'})
                if (row.organization_id != self.scope.company_id or row.actor_id != self.actor.id or row.module_key != 'project_management'
                        or row.entity_type != ('project' if self.kind == 'project_definition' else 'task')
                        or row.entity_id != (self.pid if self.kind == 'project_definition' else self.tid) or not (standard or pipeline)):
                    fail('Definition event must retain its actual native source', 403)
            else:
                fail('Native definition creation attempted an unreviewed side effect', 403)
            if row not in self.births:
                self.births.append(row)

    def stamp(self, session, *args):
        from app.branches.catalog import resource_key
        connection = self.db.connection()
        for row in self.births:
            state = inspect(row)
            if not state.persistent or id(row) in self.stamped:
                continue
            key = resource_key(type(row).__table__, dict(zip([column.name for column in row.__table__.primary_key], state.identity)))
            for target in (PackRecordOwnership.__table__, BranchOwnership.__table__):
                if connection.scalar(select(exists().where(target.c.resource_table == row.__tablename__, target.c.resource_key == key))):
                    fail('Native definition identities cannot reuse retained ownership history', 403)
                values = dict(resource_table=row.__tablename__, resource_key=key, company_id=self.scope.company_id,
                    branch_id=self.scope.branch_id, source='construction-definition:' + str(self.data.request_id))
                if target is PackRecordOwnership.__table__:
                    values.update(context_id=self.scope.context_id, revision=1)
                connection.execute(target.insert().values(**values))
            self.stamped.add(id(row))


def _native(plan):
    from app.access.models import AccessMembership, AccessPolicy, AccessRole
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.shared.communication.models import FollowUp as ChatFollowUp
    from app.shared.models import ServiceEvent
    from app.models.user import User, Role
    from app.common.models import CommonPerson
    from .catalog_management import _module_grant
    from app.access.scope import install_scope
    db, actor, scope = plan.db, plan.actor, plan.scope
    users = {actor.id, *(item['id'] for item in plan.resource_proofs)}
    grants = {key: _module_grant(db, actor, scope, key) for key in ('project_management', 'srm', 'hrms', 'crm')}
    role_ids = {g['roleId'] for g in grants.values() if type(g.get('roleId')) is int}
    for policy in db.connection().scalars(select(AccessPolicy.__table__.c.grants).where(
            AccessPolicy.__table__.c.company_id == scope.company_id, AccessPolicy.__table__.c.user_id.in_(users))):
        role_ids.update(value['roleId'] for value in (policy or {}).values()
            if isinstance(value, dict) and type(value.get('roleId')) is int)
    principal = SimpleNamespace(**{**actor.__dict__, '_suite_grants': grants, '_suite_current_module': 'project_management',
        '_suite_permission_objects': [SimpleNamespace(name=name, module='project_management') for name in grants['project_management'].get('permissions', ())],
        'employee': getattr(actor, 'employee', None)})
    project_id = bindparam('definition_project_id', callable_=lambda: plan.pid, unique=True)
    task_id = bindparam('definition_task_id', callable_=lambda: plan.tid, unique=True)
    boards = select(PMSBoard.id).where(PMSBoard.project_id == project_id)
    tasks = select(PMSTask.id).where(PMSTask.project_id == project_id)
    criteria = {
        PMSWorkspace: and_(PMSWorkspace.id == plan.workspace_id, PMSWorkspace.organization_id == scope.company_id),
        PMSWorkspaceMember: and_(PMSWorkspaceMember.workspace_id == plan.workspace_id, PMSWorkspaceMember.user_id.in_(users)),
        WorkspaceArchive: WorkspaceArchive.workspace_id == plan.workspace_id,
        PMSProject: and_(PMSProject.organization_id == scope.company_id,
            or_(PMSProject.id == project_id, and_(plan.kind == 'project_definition', PMSProject.project_key == getattr(plan.data, 'project_key', '')))),
        PMSProjectMember: and_(PMSProjectMember.project_id == project_id, PMSProjectMember.user_id.in_(users)),
        PMSTask: PMSTask.project_id == project_id,
        PMSTaskAssignee: PMSTaskAssignee.task_id.in_(tasks),
        PMSBoard: PMSBoard.project_id == project_id, PMSBoardColumn: PMSBoardColumn.board_id.in_(boards),
        PMSFileAsset: and_(PMSFileAsset.project_id == project_id, PMSFileAsset.task_id == task_id),
        PMSWorkspaceEntry: and_(PMSWorkspaceEntry.workspace_id == plan.workspace_id, PMSWorkspaceEntry.kind == 'auto_rule'),
        RecoveryChange: and_(RecoveryChange.workspace_id == plan.workspace_id, RecoveryChange.actor_id == actor.id, RecoveryChange.task_id.in_(tasks)),
        ChatFollowUp: ChatFollowUp.task_id == task_id,
        AccessMembership: and_(AccessMembership.company_id == scope.company_id, AccessMembership.user_id.in_(users)),
        AccessPolicy: and_(AccessPolicy.company_id == scope.company_id, AccessPolicy.user_id.in_(users)),
        AccessRole: and_(AccessRole.company_id == scope.company_id, AccessRole.id.in_(role_ids)),
        User: User.id.in_(users),
        Role: Role.id.in_(select(User.__table__.c.role_id).where(User.__table__.c.id.in_(users))),
        CommonPerson: and_(CommonPerson.user_id.in_(users), CommonPerson.organization_id == scope.company_id),
        EmailOutbox: and_(EmailOutbox.organization_id == scope.company_id, EmailOutbox.module == 'pms',
            EmailOutbox.recipient_user_id.in_(users), _owned(EmailOutbox.__table__, EmailOutbox.id, scope)),
        PMSActivity: PMSActivity.project_id == project_id,
        ServiceEvent: and_(ServiceEvent.organization_id == scope.company_id, ServiceEvent.actor_id == actor.id,
                          ServiceEvent.entity_id == (project_id if plan.kind == 'project_definition' else task_id)),
    }
    native = _DefinitionSession(bind=db.connection(), autoflush=False, expire_on_commit=False, join_transaction_mode='create_savepoint')
    native._authority_reads = _PlanAuthority(db.connection(), scope.company_id, users)
    native.info.update(shared_actor=(actor.id, scope.company_id), security_write_request=True)
    cleanup = None
    try:
        prior = tuple(native.dispatch.do_orm_execute)
        cleanup = install_scope(native, principal, scope.company_id, grants)
        listeners = [listener for listener in native.dispatch.do_orm_execute if listener not in prior]
        if len(listeners) != 1:
            fail('Native definition scope has an unexpected reader graph', 403)
        event.remove(native, 'do_orm_execute', listeners[0])
        recovery_update = str(update(RecoveryChange).where(RecoveryChange.workspace_id == plan.workspace_id,
            RecoveryChange.actor_id == actor.id, RecoveryChange.state == 'undone').values(state='discarded').compile(compile_kwargs={'literal_binds': True}))
        def restrict(execution):
            if execution.is_update:
                if plan.kind != 'task_definition' or str(execution.statement.compile(compile_kwargs={'literal_binds': True})) != recovery_update:
                    fail('Native definition cannot perform an unreviewed bulk update', 403)
                plan.current()
                execution.statement = execution.statement.where(RecoveryChange.id.in_(plan.recovery_ids))
                return
            if not execution.is_select or not execution.is_orm_statement:
                fail('Native definition cannot issue arbitrary SQL', 403)
            assert_mapped_sources(execution.statement, frozenset(criteria))
            execution.statement = execution.statement.options(*(with_loader_criteria(model, criterion,
                include_aliases=True, propagate_to_loaders=True) for model, criterion in criteria.items()))
        event.listen(native, 'do_orm_execute', restrict)
        event.listen(native, 'do_orm_execute', listeners[0])
        event.listen(native, 'before_flush', plan.validate)
        event.listen(native, 'after_flush_postexec', plan.stamp)
        resource_principals = [native.get(User, identity) for identity in users - {actor.id}]
        for resource in resource_principals:
            resource.organization_id = scope.company_id
        from app.apps.project_management.api import router as pms
        if plan.kind == 'project_definition':
            from app.apps.project_management.schemas import PMSProjectCreate
            data = PMSProjectCreate(**plan.data.model_dump(exclude={'request_id'}), manager_user_id=actor.id,
                owner_user_id=actor.id, branch_id=scope.branch_id)
            plan.expected = {key: value for key, value in data.model_dump(exclude={'custom_fields'}).items()}
            result = pms.create_project_operation(data, native, principal, commit=False)
        else:
            from app.apps.project_management.schemas import PMSTaskCreate
            data = PMSTaskCreate(**plan.data.model_dump(exclude={'request_id'}), reporter_user_id=actor.id,
                work_type='Sub-task' if plan.data.parent_task_id is not None else 'Task')
            plan.expected = {'project_id': plan.project_id, **data.model_dump(exclude={
                'custom_fields', 'assignee_user_ids', 'column_id', 'rank', 'position'})}
            plan.expected['assignee_user_id'] = plan.data.assignee_user_ids[0] if plan.data.assignee_user_ids else None
            result = pms.create_task_operation(plan.project_id, data, native, principal, commit=False)
        while native.new or native.dirty:
            native.flush()
        plan.current()
        native.commit = lambda: fail('Native definition does not own the outer commit', 403)
        # SessionTransaction commit releases only this native savepoint; the
        # public native operation was explicitly called commit=False.
        native.get_transaction().commit()
        return {column.name: getattr(result, column.name) for column in result.__table__.columns
                if column.name in {'id', 'name', 'title', 'project_key', 'task_key', 'workspace_id', 'project_id',
                    'branch_id', 'parent_task_id', 'status', 'start_date', 'due_date', 'estimated_cost', 'estimated_hours'}}
    finally:
        if cleanup is not None:
            cleanup()
        native.close()


def validate_record(db, scope, row):
    if type(row) is not IndustryRecord or row.kind not in KINDS:
        return
    plan = _COMMANDS.get(db)
    if not inspect(row).persistent:
        if plan is None or plan['record'] is not row or row.status != 'created' or row.created_by != scope.user_id:
            fail('Definition provenance requires its actual new canonical source command', 403)
    elif db.is_modified(row, include_collections=True):
        fail('Canonical project/task definition provenance is immutable', 403)


def _create(data, db, actor, project_id=None):
    from app.apps.srm.industry_api import digest, audit
    scope = _access(db, actor, project_id)
    kind = 'project_definition' if project_id is None else 'task_definition'
    old = _replay(db, actor, scope, data, kind, project_id)
    if old is not None:
        return old
    plan = _Birth(db, actor, scope, data, project_id)
    root_table = PMSProject.__table__ if project_id is None else PMSTask.__table__
    clauses = [root_table.c.organization_id == scope.company_id, root_table.c.project_key == data.project_key] if project_id is None else [root_table.c.project_id == project_id, root_table.c.task_key == data.task_key]
    if db.connection().scalar(select(exists().where(*clauses))):
        fail('The canonical project/task key already exists; select its existing record')
    if db in _COMMANDS:
        fail('Canonical Construction definition commands cannot nest', 403)
    with db.begin_nested():
        result = json.loads(json.dumps(_native(plan), default=str))
        pid = result['id'] if project_id is None else project_id
        project_for_action(db, actor, pid)
        row = IndustryRecord(organization_id=scope.company_id, branch_id=scope.branch_id, project_id=pid,
            kind=kind, title=result.get('name') or result['title'], request_id=str(data.request_id), status='created',
            revision=1, created_by=actor.id, data={'_request_digest': digest(data), 'native_result': result})
        _COMMANDS[db] = {'record': row, 'plan': plan}
        try:
            db.add(row); db.flush()
            audit(db, actor, row, kind + '_created')
            plan.current()
        finally:
            _COMMANDS.pop(db, None)
    try:
        plan.current()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


@router.post('/site-projects', status_code=201)
def create_project(data: ProjectInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    return _create(data, db, actor)


@router.get('/definition-workspaces')
def workspaces(db: Session = Depends(get_db), actor=Depends(get_current_user)):
    """Existing owned workspace choices; no new workspace master is created."""
    from .catalog_management import _module_grant
    from app.apps.project_management.people_management import organization_admin
    scope = _access(db, actor)
    grant = _module_grant(db, actor, scope, 'project_management')
    principal = SimpleNamespace(**{**actor.__dict__, '_suite_grants': {'project_management': grant}})
    organization_manager = organization_admin(principal)
    table, member = PMSWorkspace.__table__, PMSWorkspaceMember.__table__
    rows = db.connection().execute(select(table.c.id, table.c.name).where(table.c.organization_id == scope.company_id,
        _owned(table, table.c.id, scope), or_(organization_manager, exists().where(member.c.workspace_id == table.c.id,
            member.c.user_id == actor.id, member.c.role.in_(['Owner', 'Admin'])))).order_by(table.c.name, table.c.id)).all()
    result = []
    for row in rows:
        try:
            _workspace(db, actor, scope, row.id)
        except HTTPException as exc:
            if exc.status_code == 404:
                continue
            raise
        result.append({'id': row.id, 'name': row.name})
    return {'items': result}


@router.post('/projects/{project_id}/wbs-tasks', status_code=201)
def create_task(project_id: int, data: TaskInput, db: Session = Depends(get_db), actor=Depends(get_current_user)):
    return _create(data, db, actor, project_id)
