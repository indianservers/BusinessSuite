"""Canonical native workspace birth; never enroll existing roots.

Uses the reviewed native operation and typed projectless workspace provenance.
"""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID
from weakref import WeakKeyDictionary

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, bindparam, event, exists, inspect, select
from sqlalchemy.orm import with_loader_criteria

from app.core.deps import get_db, get_current_user
from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember
from app.apps.srm.industry_models import IndustryRecord
from app.branches.models import BranchOwnership
from .access import PackScope
from .boundary import _current
from .common_core import _native_authority
from .common_queries import assert_mapped_sources
from .construction_definition import _Birth, _DefinitionSession
from .construction_planning import _PlanAuthority, _owned
from .models import PackRecordOwnership
from .operations import require

router = APIRouter(tags=['Construction workspace setup'])
KIND = 'workspace_definition'
_COMMANDS = WeakKeyDictionary()


def fail(message, status=403):
    raise HTTPException(status, message)


class WorkspaceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    name: str = Field(min_length=1, max_length=180)

    @model_validator(mode='after')
    def named(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError('Workspace name is required')
        return self


def access(db, actor):
    from .catalog_management import _module_grant
    from app.access.service import check_background_access
    from app.apps.srm.industry_api import context
    from app.apps.project_management.access import PMS_GLOBAL_MANAGE_PROJECTS
    scope = db.info.get('business_pack_scope')
    if (not isinstance(scope, PackScope) or scope.pack_key != 'construction'
            or scope.user_id != actor.id or scope.company_id != actor.organization_id):
        fail('Select an authorized Construction setup context')
    require(db, actor, 'settings.manage')
    _current(scope, db.connection())
    authority = _native_authority(db, actor, scope.company_id)
    grants = {key: _module_grant(db, actor, scope, key) for key in ('project_management', 'srm', 'hrms', 'crm')}
    pms, sales = grants['project_management'], grants['srm']
    if not actor.is_superuser:
        if not pms.get('enabled') or 'create' not in pms.get('actions', ()) or not PMS_GLOBAL_MANAGE_PROJECTS.intersection(pms.get('permissions', ())):
            fail('Fresh native PMS global workspace-management permission is required')
        if not sales.get('enabled') or 'create' not in sales.get('actions', ()) or not {'srm_manage', 'srm_admin'}.intersection(sales.get('permissions', ())):
            fail('Fresh native Sales write permission is required for Construction setup')
    check_background_access(db, actor, 'project_management', 'create', administrative_read=False, stamp=False)
    check_background_access(db, actor, 'srm', 'create', administrative_read=False, stamp=False)
    context(db, actor, True)
    if authority != _native_authority(db, actor, scope.company_id):
        fail('Native workspace setup authority changed while waiting')
    return scope, grants, authority


class _WorkspaceBirth:
    def __init__(self, db, actor, data):
        self.db, self.actor, self.data = db, actor, data
        self.scope, self.grants, self.authority = access(db, actor)
        self.root, self.owner, self.record = None, None, None
        self.births, self.stamped, self.expected = [], set(), None
        self.record_expected, self.record_identity = None, None

    @property
    def wid(self):
        return self.root.id if self.root is not None and self.root.id is not None else -1

    def current(self):
        scope, grants, authority = access(self.db, self.actor)
        if scope != self.scope or authority != self.authority or grants != self.grants:
            fail('Native Construction workspace setup authority changed')
        if self.expected is not None:
            for model, key, expected in self.expected:
                table = model.__table__
                actual = self.db.connection().execute(select(table).where(table.c.id == key,
                    _owned(table, table.c.id, self.scope))).first()
                if actual is None or tuple(actual) != expected:
                    fail('The genuine native workspace birth changed before commit')
        self.provenance_current()

    def provenance_current(self):
        if self.record is None:
            return
        def normal(value):
            return value.astimezone(timezone.utc).replace(tzinfo=None) if isinstance(value, datetime) and value.tzinfo else value
        expected = self.record_expected
        if expected is None or any(normal(getattr(self.record, key)) != value for key, value in expected.items()):
            fail('Workspace provenance differs from its exact canonical birth command')
        if self.record_identity is None:
            if any(getattr(self.record, key) is not None for key in ('id', 'created_at', 'updated_at')):
                fail('Workspace provenance requires a genuine new server-issued identity')
            return
        table = IndustryRecord.__table__
        stored = self.db.connection().execute(select(table).where(table.c.id == self.record_identity,
            _owned(table, table.c.id, self.scope))).first()
        if stored is None or any(normal(getattr(stored, key)) != value for key, value in expected.items()):
            fail('Persisted workspace provenance changed before the setup committed')

    def seal_provenance(self):
        self.record_identity = self.record.id
        for key in ('id', 'created_at', 'updated_at'):
            value = getattr(self.record, key)
            self.record_expected[key] = value.astimezone(timezone.utc).replace(tzinfo=None) if isinstance(value, datetime) and value.tzinfo else value
        self.provenance_current()

    def validate(self, session, *args):
        self.current()
        if session.deleted or any(session.is_modified(row, include_collections=False) for row in session.dirty):
            fail('Workspace setup may not mutate existing business records')
        for row in session.new:
            if row not in self.births and row.id is not None:
                fail('Workspace setup requires genuinely new native identities')
            if type(row) is PMSWorkspace:
                if self.root is not None and row is not self.root:
                    fail('One command creates one actual canonical workspace')
                if row.organization_id != self.scope.company_id or row.name != self.data.name:
                    fail('Native workspace differs from the authorized setup input')
                self.root = row
            elif type(row) is PMSWorkspaceMember:
                if self.owner is not None and row is not self.owner:
                    fail('Workspace setup creates only its actual native author membership')
                if row.workspace_id != self.wid or row.user_id != self.actor.id or row.role != 'Owner':
                    fail('Workspace setup cannot confer access on another user or root')
                self.owner = row
            else:
                fail('Unreviewed native workspace setup side effect: ' + row.__tablename__)
            if row not in self.births:
                self.births.append(row)

    def stamp(self, session, *args):
        # Reuse the reviewed genuine-birth stamper, not legacy enrollment.
        _Birth.stamp(self, session)


def _native(plan):
    from app.access.scope import install_scope
    from app.access.models import AccessMembership, AccessPolicy, AccessRole
    from app.models.user import User, Role, Permission, role_permissions
    from app.models.company import Company
    from app.common.models import CommonPerson
    from app.apps.project_management import workspaces as native_workspaces
    db, actor, scope = plan.db, plan.actor, plan.scope
    workspace_id = bindparam('construction_new_workspace_id', callable_=lambda: plan.wid, unique=True)
    role_ids = {g['roleId'] for g in plan.grants.values() if type(g.get('roleId')) is int}
    criteria = {
        PMSWorkspace: and_(PMSWorkspace.id == workspace_id, PMSWorkspace.organization_id == scope.company_id),
        PMSWorkspaceMember: and_(PMSWorkspaceMember.workspace_id == workspace_id, PMSWorkspaceMember.user_id == actor.id),
        User: User.id == actor.id, Role: Role.id == actor.role_id,
        Permission: Permission.id.in_(select(role_permissions.c.permission_id).where(role_permissions.c.role_id == actor.role_id)),
        CommonPerson: and_(CommonPerson.user_id == actor.id, CommonPerson.organization_id == scope.company_id),
        Company: Company.id == scope.company_id,
        AccessMembership: and_(AccessMembership.company_id == scope.company_id, AccessMembership.user_id == actor.id),
        AccessPolicy: and_(AccessPolicy.company_id == scope.company_id, AccessPolicy.user_id == actor.id),
        AccessRole: and_(AccessRole.company_id == scope.company_id, AccessRole.id.in_(role_ids)),
    }
    native = _DefinitionSession(bind=db.connection(), autoflush=False, expire_on_commit=False,
        join_transaction_mode='create_savepoint')
    native._authority_reads = _PlanAuthority(db.connection(), scope.company_id, {actor.id})
    native.info.update(shared_actor=(actor.id, scope.company_id), security_write_request=True)
    cleanup = None
    try:
        prior = tuple(native.dispatch.do_orm_execute)
        cleanup = install_scope(native, actor, scope.company_id, plan.grants)
        added = [listener for listener in native.dispatch.do_orm_execute if listener not in prior]
        if len(added) != 1:
            fail('Unexpected native workspace setup source graph')
        event.remove(native, 'do_orm_execute', added[0])
        def restrict(execution):
            if not execution.is_select or not execution.is_orm_statement:
                fail('Native workspace setup has no general SQL authority')
            assert_mapped_sources(execution.statement, frozenset(criteria), allowed_associations=(role_permissions,))
            execution.statement = execution.statement.options(*(with_loader_criteria(model, clause,
                include_aliases=True, propagate_to_loaders=True) for model, clause in criteria.items()))
        event.listen(native, 'do_orm_execute', restrict)
        event.listen(native, 'do_orm_execute', added[0])
        event.listen(native, 'before_flush', plan.validate)
        event.listen(native, 'after_flush_postexec', plan.stamp)
        principal = native.get(User, actor.id)
        if principal is None or inspect(principal).session is not native:
            fail('Native workspace setup requires its genuine authenticated User')
        principal.organization_id = scope.company_id
        principal._suite_grants = plan.grants
        principal._suite_current_module = 'project_management'
        principal._suite_admin_read = False
        principal._suite_permission_objects = [SimpleNamespace(name=name, module='project_management')
            for name in plan.grants['project_management'].get('permissions', ())]
        membership = AccessMembership.__table__
        principal._suite_is_company_admin = bool(db.connection().scalar(select(membership.c.is_admin).where(
            membership.c.company_id == scope.company_id, membership.c.user_id == actor.id, membership.c.active.is_(True))))
        result = native_workspaces.create_workspace_operation(native_workspaces.WorkspaceInput(name=plan.data.name),
            native, principal, commit=False)
        while native.new or native.dirty:
            native.flush()
        if result is not plan.root or plan.owner is None or len(plan.births) != 2:
            fail('Workspace setup did not produce its exact native root and Owner')
        plan.expected = [(type(row), row.id, tuple(getattr(row, c.name) for c in row.__table__.columns)) for row in plan.births]
        plan.current()
        native.get_transaction().commit()
        return {'id': plan.wid, 'name': plan.root.name, 'role': 'Owner'}
    finally:
        if cleanup:
            cleanup()
        native.close()


def validate_record(db, scope, row):
    """Root source hook must return immediately after this typed projectless case."""
    plan = _COMMANDS.get(db)
    actual_command_row = plan is not None and plan.record is row
    if type(row) is not IndustryRecord or row.kind != KIND and not actual_command_row:
        return False
    if row in db.deleted or inspect(row).persistent and db.is_modified(row, include_collections=True):
        fail('Canonical workspace setup provenance is immutable')
    if not inspect(row).persistent:
        if (plan is None or plan.record is not row or plan.scope != scope or row.project_id is not None
                or row.parent_id is not None or row.status != 'created' or row.revision != 1 or row.created_by != scope.user_id
                or row.data.get('workspace_id') != plan.wid):
            fail('Workspace provenance requires its actual authorized native birth')
    if actual_command_row:
        if plan.scope != scope:
            fail('Workspace provenance belongs to another setup scope')
        plan.provenance_current()
        plan.current()
    return True


def create(data, db, actor):
    from app.apps.srm.industry_api import digest, audit
    plan = _WorkspaceBirth(db, actor, data)
    scope, table = plan.scope, IndustryRecord.__table__
    previous = db.connection().execute(select(table).where(table.c.organization_id == scope.company_id,
        table.c.branch_id == scope.branch_id, table.c.request_id == str(data.request_id))).first()
    if previous is not None:
        if (previous.kind != KIND or previous.created_by != actor.id or previous.project_id is not None
                or not db.connection().scalar(select(exists().where(PackRecordOwnership.resource_table == table.name,
                    PackRecordOwnership.resource_key == str(previous.id), PackRecordOwnership.context_id == scope.context_id)))
                or previous.data.get('_request_digest') != digest(data)):
            fail('This workspace setup request identity is already reserved', 409)
        from .construction_definition import _workspace
        _workspace(db, actor, scope, previous.data['workspace_id'])
        membership = PMSWorkspaceMember.__table__
        if not db.connection().scalar(select(exists().where(membership.c.workspace_id == previous.data['workspace_id'],
                membership.c.user_id == actor.id, membership.c.role.in_(['Owner', 'Admin'])))):
            fail('Native workspace Owner or Admin access is required for setup replay')
        return previous.data['native_result']
    if db in _COMMANDS:
        fail('Native Construction workspace setup cannot nest')
    try:
        with db.begin_nested():
            result = _native(plan)
            plan.record = IndustryRecord(organization_id=scope.company_id, branch_id=scope.branch_id,
                project_id=None, parent_id=None, kind=KIND, title=data.name, status='created', revision=1,
                request_id=str(data.request_id), created_by=actor.id,
                data={'workspace_id': plan.wid, '_request_digest': digest(data), 'native_result': result})
            plan.record_expected = {'organization_id': scope.company_id, 'branch_id': scope.branch_id,
                'project_id': None, 'parent_id': None, 'kind': KIND, 'title': data.name, 'status': 'created',
                'revision': 1, 'request_id': str(data.request_id), 'created_by': actor.id, 'approved_by': None,
                'customer_id': None, 'invoice_id': None, 'stock_movement_id': None, 'starts_at': None, 'ends_at': None,
                'data': deepcopy({'workspace_id': plan.wid, '_request_digest': digest(data), 'native_result': result})}
            _COMMANDS[db] = plan
            try:
                db.add(plan.record); db.flush()
                plan.seal_provenance()
                audit(db, actor, plan.record, 'workspace_created')
                plan.current()
            finally:
                _COMMANDS.pop(db, None)
        plan.current()
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.post('/workspace-definitions', status_code=201)
def create_workspace(data: WorkspaceInput, db=Depends(get_db), actor=Depends(get_current_user)):
    return create(data, db, actor)
