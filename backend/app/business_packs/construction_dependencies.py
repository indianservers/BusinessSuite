"""Finite native PMS dependency commands and Construction resource proofs."""
import json
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Literal
from uuid import UUID
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, event, exists, inspect, select
from sqlalchemy.orm import with_loader_criteria

from app.core.deps import get_db, get_current_user
from app.apps.project_management.models import (PMSProject, PMSProjectMember, PMSWorkspace,
    PMSWorkspaceMember, PMSTask, PMSTaskAssignee, PMSTaskDependency, PMSActivity)
from app.apps.srm.industry_models import IndustryRecord
from .construction import _source, _project_epoch, project_for_action
from .construction_definition import _access, _workspace
from .construction_planning import _PlanSession, _PlanAuthority, _graph, _owned
from .common_core import _native_authority
from .common_queries import assert_mapped_sources
from .boundary import _current
from .models import PackUserGrant, PackRecordOwnership

router = APIRouter(tags=['Construction native dependencies'])
KINDS = {'dependency_definition'}
_COMMANDS = WeakKeyDictionary()


def fail(message, status=409):
    raise HTTPException(status, message)


class DependencyInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    source_task_id: int = Field(gt=0)
    target_task_id: int = Field(gt=0)
    dependency_type: Literal['FS', 'SS', 'FF', 'SF'] = 'FS'
    lag_days: int = Field(default=0, ge=-365, le=365)


@contextmanager
def _finite(db, actor, project_id, users, *, write=False, lease=None):
    from app.access.models import AccessMembership, AccessPolicy, AccessRole
    from app.access.scope import install_scope
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.common.models import CommonPerson
    from app.models.user import User, Role
    from app.shared.communication.models import FollowUp
    from .catalog_management import _module_grant
    scope, wid, tasks, dependencies, _, _ = _graph(db, actor, project_id, write)
    grants = {key: _module_grant(db, actor, scope, key) for key in ('project_management', 'srm', 'hrms', 'crm')}
    role_ids = {g['roleId'] for g in grants.values() if isinstance(g.get('roleId'), int)}
    for policy in db.connection().scalars(select(AccessPolicy.__table__.c.grants).where(
            AccessPolicy.__table__.c.company_id == scope.company_id, AccessPolicy.__table__.c.user_id.in_(users))):
        role_ids.update(value['roleId'] for value in (policy or {}).values()
            if isinstance(value, dict) and type(value.get('roleId')) is int)
    criteria = {
        PMSProject: and_(PMSProject.id == project_id, PMSProject.organization_id == scope.company_id),
        PMSWorkspace: and_(PMSWorkspace.id == wid, PMSWorkspace.organization_id == scope.company_id),
        PMSWorkspaceMember: and_(PMSWorkspaceMember.workspace_id == wid, PMSWorkspaceMember.user_id.in_(users)),
        PMSProjectMember: and_(PMSProjectMember.project_id == project_id, PMSProjectMember.user_id.in_(users)),
        WorkspaceArchive: WorkspaceArchive.workspace_id == wid,
        PMSTask: and_(PMSTask.id.in_(tasks), PMSTask.project_id == project_id),
        PMSTaskAssignee: PMSTaskAssignee.task_id.in_(tasks),
        PMSTaskDependency: PMSTaskDependency.id.in_(dependencies),
        PMSActivity: PMSActivity.project_id == project_id,
        FollowUp: and_(FollowUp.workspace_id == wid, FollowUp.task_id.in_(tasks)),
        User: User.id.in_(users),
        Role: Role.id.in_(select(User.__table__.c.role_id).where(User.__table__.c.id.in_(users))),
        CommonPerson: and_(CommonPerson.organization_id == scope.company_id, CommonPerson.user_id.in_(users)),
        AccessMembership: and_(AccessMembership.company_id == scope.company_id, AccessMembership.user_id.in_(users)),
        AccessPolicy: and_(AccessPolicy.company_id == scope.company_id, AccessPolicy.user_id.in_(users)),
        AccessRole: and_(AccessRole.company_id == scope.company_id, AccessRole.id.in_(role_ids)),
    }
    native = _PlanSession(bind=db.connection(), autoflush=False, expire_on_commit=False,
        join_transaction_mode='create_savepoint' if write else 'rollback_only')
    native._authority_reads = _PlanAuthority(db.connection(), scope.company_id, users)
    native._planning_connection, native._can_write = db.connection(), write
    native.info.update(shared_actor=(actor.id, scope.company_id), security_write_request=write)
    principal = SimpleNamespace(**{**actor.__dict__, '_suite_grants': grants,
        '_suite_current_module': 'project_management', '_suite_admin_read': False,
        '_suite_permission_objects': [SimpleNamespace(name=name, module='project_management')
            for name in grants['project_management'].get('permissions', ())]})
    cleanup = None
    try:
        prior = tuple(native.dispatch.do_orm_execute)
        cleanup = install_scope(native, principal, scope.company_id, grants)
        added = [listener for listener in native.dispatch.do_orm_execute if listener not in prior]
        if len(added) != 1:
            fail('Unexpected native dependency reader graph', 403)
        event.remove(native, 'do_orm_execute', added[0])
        def restrict(execution):
            if not execution.is_select or not execution.is_orm_statement:
                fail('Construction dependencies have no general SQL authority', 403)
            assert_mapped_sources(execution.statement, frozenset(criteria))
            execution.statement = execution.statement.options(*(with_loader_criteria(model, criterion,
                include_aliases=True, propagate_to_loaders=True) for model, criterion in criteria.items()))
        event.listen(native, 'do_orm_execute', restrict)
        event.listen(native, 'do_orm_execute', added[0])
        if lease:
            event.listen(native, 'before_flush', lease.validate)
            event.listen(native, 'after_flush_postexec', lease.stamp)
        else:
            event.listen(native, 'before_flush', lambda *args: fail('Resource proofs cannot write business records', 403))
        yield native, principal
    finally:
        if cleanup:
            cleanup()
        native.close()


def resource_sources(db, actor, project_id, ids=None):
    """Only current-context native collaborators; never an organization directory."""
    from app.models.user import User
    from app.common.models import CommonPerson
    from .access import _actor_company, _eligible
    from .catalog_management import _module_grant
    from app.apps.project_management.api.router import _project_user_query
    from app.apps.project_management.access import can_access_project
    scope, wid = _source(db, actor, project_id)
    project_for_action(db, actor, project_id)
    branch_context = db.info.get('branch_context')
    if branch_context is None:
        fail('Verified branch context is required for Construction resources', 403)
    grant, member, user, person = (m.__table__ for m in (PackUserGrant, PMSWorkspaceMember, User, CommonPerson))
    statement = select(user, person.c.display_name).outerjoin(person, and_(person.c.user_id == user.c.id,
        person.c.organization_id == scope.company_id)).where(user.c.is_active.is_(True),
        exists().where(grant.c.context_id == scope.context_id, grant.c.company_id == scope.company_id,
            grant.c.branch_id == scope.branch_id, grant.c.user_id == user.c.id, grant.c.active.is_(True)),
        exists().where(member.c.workspace_id == wid, member.c.user_id == user.c.id, member.c.role != 'Guest'))
    requested = None if ids is None else set(ids)
    if requested is not None:
        statement = statement.where(user.c.id.in_(requested))
    facts = list(db.connection().execute(statement.order_by(user.c.id)).mappings())
    result = []
    if facts:
        with _finite(db, actor, project_id, {actor.id, *(row['id'] for row in facts)}) as (native, principal):
            project = native.get(PMSProject, project_id)
            native_ids = {row.id for row in _project_user_query(native, project).all()}
            for row in facts:
                target = SimpleNamespace(**dict(row), organization_id=scope.company_id)
                try:
                    _actor_company(db, target, branch_context)
                    target_scope = next((item for item in _eligible(db, target, branch_context, scope.company_id, target.id)
                        if item.context_id == scope.context_id and 'construction.sites.view' in item.capabilities), None)
                    if target_scope is None:
                        continue
                    module = _module_grant(db, target, target_scope, 'project_management')
                    if not module.get('enabled') or 'view' not in module.get('actions', ()):
                        continue
                    candidate = native.get(User, target.id)
                    # This is a fresh finite-session principal. The selected
                    # organization was just proved from persisted membership;
                    # do not make optional HR/person profiles an access source.
                    candidate.organization_id = scope.company_id
                    candidate._suite_grants = {'project_management': module}
                    candidate._suite_permission_objects = [SimpleNamespace(name=name, module='project_management') for name in module.get('permissions', ())]
                    candidate._suite_admin_read = False
                    if target.id not in native_ids or not can_access_project(native, project, candidate):
                        continue
                    result.append({'id': target.id, 'email': target.email, 'name': row['display_name'] or target.email,
                        'role_id': target.role_id, 'epoch': (_native_authority(db, candidate, scope.company_id), target_scope,
                            _workspace(db, target, scope, wid))})
                except HTTPException as exc:
                    if exc.status_code not in {403, 404}:
                        raise
    if requested is not None and {row['id'] for row in result} != requested:
        fail('Resource requires its own active Construction grant and native project access', 404)
    return result


def recipient_proof(db, actor, project_id, user_id):
    return resource_sources(db, actor, project_id, [user_id])[0]


@router.get('/projects/{project_id}/resource-options')
def resource_options(project_id: int, db=Depends(get_db), actor=Depends(get_current_user)):
    _access(db, actor, project_id)
    return {'items': [{key: row[key] for key in ('id', 'name')} for row in resource_sources(db, actor, project_id)]}


class _Dependency:
    def __init__(self, db, actor, scope, project_id, data):
        self.db, self.actor, self.scope, self.project_id, self.data = db, actor, scope, project_id, data
        _, self.wid, self.tasks, self.dependencies, _, _ = _graph(db, actor, project_id, True)
        if data.source_task_id not in self.tasks or data.target_task_id not in self.tasks:
            fail('Dependency endpoints must be actual owned tasks in this project', 404)
        self.epoch = _project_epoch(db, scope, project_id)
        self.authority = _native_authority(db, actor, scope.company_id)
        self.root, self.source, self.births, self.stamped = None, None, [], set()

    def current(self):
        _current(self.scope, self.db.connection())
        if self.authority != _native_authority(self.db, self.actor, self.scope.company_id) or self.epoch != _project_epoch(self.db, self.scope, self.project_id):
            fail('Native dependency authority changed', 403)
        from .construction_workpackages import task_source
        for identity in (self.data.source_task_id, self.data.target_task_id):
            task_source(self.db, self.actor, self.project_id, identity, action='manage_tasks')
        _graph(self.db, self.actor, self.project_id, True)
        if self.root is not None and id(self.root) in self.stamped:
            from app.apps.project_management.api.router import _normalize_dependency_type
            table = PMSTaskDependency.__table__
            row = self.db.connection().execute(select(table).where(table.c.id == self.root.id)).first()
            blocking = self.db.connection().scalar(select(PMSTask.__table__.c.is_blocking).where(
                PMSTask.__table__.c.id == self.data.source_task_id))
            if (row is None or row.task_id != self.data.target_task_id or row.depends_on_task_id != self.data.source_task_id
                    or row.dependency_type != _normalize_dependency_type(self.data.dependency_type)
                    or row.lag_days != self.data.lag_days or blocking is not True):
                fail('The actual native dependency result changed before commit', 403)

    def validate(self, session, *args):
        from app.shared.models import ServiceEvent
        from app.shared.communication.models import CommunicationEvent, FollowUp
        from app.apps.project_management.api.router import _normalize_dependency_type
        self.current()
        if session.deleted:
            fail('Dependency creation cannot delete records', 403)
        for row in session.dirty:
            changed = {key for key, attr in inspect(row).attrs.items() if attr.history.has_changes()}
            if not changed:
                continue
            if type(row) is not PMSTask or row.id != self.data.source_task_id or row.project_id != self.project_id or changed - {'is_blocking', 'updated_at'} or not row.is_blocking:
                fail('Dependency command may change only its actual source blocking marker', 403)
            self.source = row
        for row in session.new:
            if row not in self.births and row.id is not None:
                fail('Dependency command requires genuinely new native identities', 403)
            if type(row) is PMSTaskDependency:
                if self.root is not None and row is not self.root:
                    fail('One dependency command creates one native link', 403)
                self.root = row
                if (row.task_id != self.data.target_task_id or row.depends_on_task_id != self.data.source_task_id
                        or row.dependency_type != _normalize_dependency_type(self.data.dependency_type) or row.lag_days != self.data.lag_days):
                    fail('Native dependency differs from its exact command', 403)
            elif type(row) is PMSActivity:
                if (self.root is None or row.project_id != self.project_id or row.actor_user_id != self.actor.id
                        or row.action != 'dependency.added' or row.entity_type != 'task_dependency'
                        or row.entity_id != self.root.id or row.task_id != self.data.target_task_id):
                    fail('Dependency activity requires its actual native link', 403)
            elif type(row) is ServiceEvent:
                if (self.source is None or getattr(row, '_suite_source_record', None) is not self.source
                        or row.organization_id != self.scope.company_id or row.actor_id != self.actor.id
                        or row.module_key != 'project_management' or row.entity_type != 'task'
                        or row.entity_id != self.data.source_task_id or row.event_type != 'record.updated'
                        or set(row.payload_json) != {'depth', 'data'} or row.payload_json['data'] != {}):
                    fail('Dependency event requires its actual blocking-source mutation', 403)
            elif type(row) is CommunicationEvent:
                table = FollowUp.__table__
                if not self.db.connection().scalar(select(exists().where(table.c.workspace_id == self.wid,
                    table.c.workspace_id == row.workspace_id, table.c.conversation_id == row.conversation_id,
                    table.c.task_id == self.data.target_task_id))):
                    fail('Dependency cache event requires its actual linked target task', 403)
            else:
                fail('Native dependency attempted an unreviewed side effect', 403)
            if row not in self.births:
                self.births.append(row)

    def stamp(self, session, *args):
        from .construction_definition import _Birth
        _Birth.stamp(self, session)


def validate_record(db, scope, row):
    if type(row) is IndustryRecord and row.kind in KINDS:
        if not inspect(row).persistent:
            if _COMMANDS.get(db) is not row or row.status != 'created' or row.created_by != scope.user_id:
                fail('Dependency provenance requires its actual native command', 403)
        elif db.is_modified(row, include_collections=True):
            fail('Native dependency provenance is immutable', 403)


@router.post('/projects/{project_id}/task-dependencies', status_code=201)
def create_dependency(project_id: int, data: DependencyInput, db=Depends(get_db), actor=Depends(get_current_user)):
    from .construction_definition import _replay
    from app.apps.srm.industry_api import digest, audit
    from app.apps.project_management.api import router as pms
    scope = _access(db, actor, project_id)
    old = _replay(db, actor, scope, data, 'dependency_definition', project_id)
    if old is not None:
        return old
    plan = _Dependency(db, actor, scope, project_id, data)
    with db.begin_nested():
        with _finite(db, actor, project_id, {actor.id}, write=True, lease=plan) as (native, principal):
            native_data = pms.TaskDependencyCreateRequest(**data.model_dump(exclude={'request_id'}))
            result = pms.create_task_dependency_operation(native_data, native, principal, commit=False)
            while native.new or native.dirty:
                native.flush()
            plan.current()
            native.get_transaction().commit()
        row = IndustryRecord(organization_id=scope.company_id, branch_id=scope.branch_id, project_id=project_id,
            kind='dependency_definition', title=f'{data.source_task_id} {data.dependency_type} {data.target_task_id}',
            status='created', revision=1, created_by=actor.id, request_id=str(data.request_id),
            data={'_request_digest': digest(data), 'native_result': jsonable_encoder(result)})
        _COMMANDS[db] = row
        try:
            db.add(row); db.flush()
            audit(db, actor, row, 'dependency_created')
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
