""": native workspace team setup; User ORM remains SELF.

Depends on reviewed add_workspace_member_operation extraction. New native
membership notifications must be admitted by an explicit common121 source
certificate; this module does not suppress or deliver notifications/email.
"""
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Literal
from uuid import UUID
from weakref import WeakKeyDictionary
from copy import deepcopy
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, event, exists, inspect, or_, select
from sqlalchemy.orm import with_loader_criteria

from app.core.deps import get_db, get_current_user
from app.models.user import User, Role, Permission, role_permissions
from app.models.employee import Employee
from app.models.company import Branch
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.models.email_outbox import EmailOutbox
from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember, PMSWorkspaceInvitation
from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
from app.apps.srm.industry_models import IndustryRecord
from .access import PackScope
from .boundary import _current
from .common_core import _native_authority
from .common_queries import assert_mapped_sources
from .construction_definition import _DefinitionSession, _Birth, _workspace
from .construction_planning import _PlanAuthority, _owned
from .construction_workspaces import _WorkspaceBirth
from .models import PackRecordOwnership, PackUserGrant
from .operations import require

router = APIRouter(tags=['Construction workspace team setup'])
KIND = 'workspace_member_definition'
_COMMANDS = WeakKeyDictionary()


def fail(message, status=403):
    raise HTTPException(status, message)


class MemberInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    user_id: int = Field(gt=0)
    role: Literal['Member', 'Admin'] = 'Member'


@dataclass(frozen=True, slots=True)
class TargetReference:
    """A persisted exact-target scalar FK reference, never a User or actor."""
    id: int
    email: str
    is_active: bool
    organization_id: int


def access(db, actor, wid):
    from .catalog_management import _module_grant
    from app.access.service import check_background_access
    from app.apps.srm.industry_api import context
    scope = db.info.get('business_pack_scope')
    if not isinstance(scope, PackScope) or scope.pack_key != 'construction' or scope.user_id != actor.id or scope.company_id != actor.organization_id:
        fail('Select the authorized Construction team context')
    require(db, actor, 'settings.manage')
    _current(scope, db.connection())
    authority = _native_authority(db, actor, scope.company_id)
    grants = {key: _module_grant(db, actor, scope, key) for key in ('project_management','srm','hrms','crm')}
    if not actor.is_superuser:
        pms, sales = grants['project_management'], grants['srm']
        if not pms.get('enabled') or not {'view','create','edit'} <= set(pms.get('actions', ())):
            fail('Fresh native PMS create, edit and view are required')
        if not sales.get('enabled') or 'create' not in sales.get('actions', ()) or not {'srm_manage','srm_admin'}.intersection(sales.get('permissions', ())):
            fail('Fresh native Sales write permission is required')
    check_background_access(db, actor, 'project_management', 'create', administrative_read=False, stamp=False)
    check_background_access(db, actor, 'project_management', 'edit', administrative_read=False, stamp=False)
    check_background_access(db, actor, 'srm', 'create', administrative_read=False, stamp=False)
    context(db, actor, True)
    workspace = _workspace(db, actor, scope, wid)
    if authority != _native_authority(db, actor, scope.company_id):
        fail('Native team setup authority changed while waiting')
    _owner_access(db,actor,scope,grants,wid)
    if authority != _native_authority(db,actor,scope.company_id):
        fail('Native team authority changed during workspace management proof')
    return scope, grants, authority, workspace


def _owner_access(db,actor,scope,grants,wid):
    """Actual native management check without exposing another User ORM row."""
    from app.access.models import AccessMembership,AccessPolicy,AccessRole
    from app.access.scope import install_scope
    from app.common.models import CommonPerson
    from app.apps.project_management.workspaces import workspace_member
    criteria = {User:User.id == actor.id,Role:Role.id == actor.role_id,
        Employee:and_(Employee.user_id == actor.id,or_(Employee.branch_id.in_(select(Branch.__table__.c.id).where(Branch.__table__.c.company_id == scope.company_id)),Employee.branch_id.is_(None) & (scope.company_id == 1))),
        Branch:and_(Branch.company_id == scope.company_id,Branch.id.in_(select(Employee.__table__.c.branch_id).where(Employee.__table__.c.user_id == actor.id))),
        Permission:Permission.id.in_(select(role_permissions.c.permission_id).where(role_permissions.c.role_id == actor.role_id)),
        CommonPerson:and_(CommonPerson.user_id == actor.id,CommonPerson.organization_id == scope.company_id),
        AccessMembership:and_(AccessMembership.company_id == scope.company_id,AccessMembership.user_id == actor.id),
        AccessPolicy:and_(AccessPolicy.company_id == scope.company_id,AccessPolicy.user_id == actor.id),
        AccessRole:and_(AccessRole.company_id == scope.company_id,AccessRole.id.in_([g['roleId'] for g in grants.values() if type(g.get('roleId')) is int])),
        PMSWorkspace:and_(PMSWorkspace.id == wid,PMSWorkspace.organization_id == scope.company_id),
        PMSWorkspaceMember:and_(PMSWorkspaceMember.workspace_id == wid,PMSWorkspaceMember.user_id == actor.id),
        WorkspaceArchive:WorkspaceArchive.workspace_id == wid}
    reader = _DefinitionSession(bind=db.connection(),autoflush=False,expire_on_commit=False,join_transaction_mode='rollback_only')
    reader._authority_reads = _PlanAuthority(db.connection(),scope.company_id,{actor.id})
    cleanup = None
    try:
        def restrict(execution):
            if not execution.is_select or not execution.is_orm_statement:
                fail('Workspace management proof cannot write or issue generic SQL')
            assert_mapped_sources(execution.statement,frozenset(criteria),allowed_associations=(role_permissions,))
            execution.statement = execution.statement.options(*(with_loader_criteria(model,clause,include_aliases=True,propagate_to_loaders=True) for model,clause in criteria.items()))
        event.listen(reader,'do_orm_execute',restrict)
        def no_write(*args):
            fail('Workspace management proof is read-only')
        event.listen(reader,'before_flush',no_write)
        principal = reader.get(User,actor.id)
        if principal is None or inspect(principal).session is not reader:
            fail('Workspace management requires the genuine authenticated User')
        principal.organization_id = scope.company_id
        principal._suite_grants,principal._suite_current_module,principal._suite_admin_read = grants,'project_management',False
        principal._suite_permission_objects = [SimpleNamespace(name=name,module='project_management') for name in grants['project_management'].get('permissions',())]
        membership = AccessMembership.__table__
        principal._suite_is_company_admin = bool(db.connection().scalar(select(membership.c.is_admin).where(
            membership.c.company_id == scope.company_id,membership.c.user_id == actor.id,membership.c.active.is_(True))))
        previous = tuple(reader.dispatch.do_orm_execute)
        cleanup = install_scope(reader,principal,scope.company_id,grants)
        if len([hook for hook in reader.dispatch.do_orm_execute if hook not in previous]) != 1:
            fail('Unexpected workspace ownership reader graph')
        _,member = workspace_member(reader,wid,principal,True)
        state = inspect(member,raiseerr=False)
        if (type(member) is not PMSWorkspaceMember or state is None or not state.persistent
                or state.session is not reader or member.workspace_id != wid or member.user_id != actor.id
                or member.role not in {'Owner','Admin'}
                or not db.connection().scalar(select(exists().where(PMSWorkspaceMember.__table__.c.id == member.id,
                    _owned(PMSWorkspaceMember.__table__,PMSWorkspaceMember.__table__.c.id,scope))))):
            fail('An actual explicitly owned native workspace Owner or Admin membership is required')
        return member.role
    finally:
        if cleanup:
            cleanup()
        reader.close()


def target_proof(db, actor, scope, uid):
    """Bootstrap eligibility deliberately does not require workspace membership."""
    from .access import _actor_company, _eligible
    from .catalog_management import _module_grant
    from app.core.tenant_boundary import company_ids
    user, grant = User.__table__, PackUserGrant.__table__
    row = db.connection().execute(select(user.c.id,user.c.email,user.c.is_active,user.c.is_superuser,user.c.role_id).where(
        user.c.id == uid, user.c.is_active.is_(True), exists().where(grant.c.user_id == user.c.id,
            grant.c.company_id == scope.company_id, grant.c.branch_id == scope.branch_id,
            grant.c.context_id == scope.context_id, grant.c.active.is_(True)))).first()
    if row is None:
        fail('Target needs its own active Construction grant', 404)
    candidate = SimpleNamespace(**dict(row._mapping))
    role = Role.__table__
    role_fact = db.connection().execute(select(role.c.id,role.c.name).where(role.c.id == row.role_id)).first()
    if role_fact is None:
        fail('Target native role identity is unavailable',404)
    # Scalar authority facts only, not a target User ORM row or an actor.
    candidate.role = SimpleNamespace(id=role_fact.id,name=role_fact.name)
    if scope.company_id not in company_ids(db, candidate):
        fail('Target needs persisted canonical company membership', 404)
    candidate.organization_id = scope.company_id
    branch = db.info.get('branch_context')
    _actor_company(db, candidate, branch)
    target_scope = next((item for item in _eligible(db, candidate, branch, scope.company_id, uid)
        if item.context_id == scope.context_id and 'construction.sites.view' in item.capabilities), None)
    if target_scope is None:
        fail('Target Construction branch authority is unavailable', 404)
    pms = _module_grant(db, candidate, target_scope, 'project_management')
    if not pms.get('enabled') or 'view' not in pms.get('actions', ()):
        fail('Target needs its own current native PMS view', 404)
    candidate._suite_grants = {'project_management':pms}
    candidate._suite_admin_read = False
    candidate._suite_permission_objects = [SimpleNamespace(name=name,module='project_management') for name in pms.get('permissions', ())]
    return TargetReference(uid,row.email,True,scope.company_id), (_native_authority(db,candidate,scope.company_id), target_scope, pms)


class _MemberSession(_DefinitionSession):
    def get(self, entity, identity, **kwargs):
        if entity is User and self._target_window and identity == self._member_plan.data.user_id:
            if kwargs:
                fail('A native member target reference accepts only the exact scalar identity')
            self._member_plan.current()
            return self._member_plan.reference
        return super().get(entity, identity, **kwargs)


class _Member:
    provenance_current = _WorkspaceBirth.provenance_current
    seal_provenance = _WorkspaceBirth.seal_provenance

    def __init__(self, db, actor, wid, data):
        self.db,self.actor,self.wid,self.data = db,actor,wid,data
        self.scope,self.grants,self.authority,self.workspace_epoch = access(db,actor,wid)
        self.workspace_name = db.connection().scalar(select(PMSWorkspace.__table__.c.name).where(
            PMSWorkspace.__table__.c.id == wid,PMSWorkspace.__table__.c.organization_id == self.scope.company_id,
            _owned(PMSWorkspace.__table__,PMSWorkspace.__table__.c.id,self.scope)))
        if data.user_id == actor.id:
            fail('Team setup cannot use its actor as a target reference',409)
        self.reference,self.target_epoch = target_proof(db,actor,self.scope,data.user_id)
        self.root,self.notice,self.record = None,None,None
        self.births,self.stamped,self.expected = [],set(),None
        self.record_expected,self.record_identity = None,None
        table = PMSWorkspaceInvitation.__table__
        self.invites = tuple(db.connection().execute(select(table).where(table.c.workspace_id == wid,
            table.c.email == self.reference.email.lower(), table.c.status == 'pending').order_by(table.c.id)))
        if any(not db.connection().scalar(select(exists().where(table.c.id == row.id,_owned(table,table.c.id,self.scope)))) for row in self.invites):
            fail('Pending native invitations require their separately reviewed exact ownership',409)
        self.accepted = set()
        self.prepared_notices = set()

    def current(self):
        scope,grants,authority,workspace = access(self.db,self.actor,self.wid)
        if (scope,grants,authority,workspace) != (self.scope,self.grants,self.authority,self.workspace_epoch):
            fail('Native workspace management authority changed')
        reference,epoch = target_proof(self.db,self.actor,scope,self.data.user_id)
        if reference != self.reference or epoch != self.target_epoch:
            fail('Canonical target eligibility changed')
        table = PMSWorkspaceInvitation.__table__
        known = {item.id for item in self.invites}
        observed = set(self.db.connection().scalars(select(table.c.id).where(table.c.workspace_id == self.wid,
            table.c.email == self.reference.email.lower(),(table.c.status == 'pending') | table.c.id.in_(known))))
        if observed != known:
            fail('The native pending invitation set changed')
        for original in self.invites:
            row = self.db.connection().execute(select(table).where(table.c.id == original.id,_owned(table,table.c.id,scope))).first()
            expected = dict(original._mapping)
            if original.id in self.accepted:
                expected['status'] = 'accepted'
            if row is None or dict(row._mapping) != expected:
                fail('The exact native pending invitation changed')
        if self.expected is not None:
            for model,identity,expected in self.expected:
                table = model.__table__
                row = self.db.connection().execute(select(table).where(table.c.id == identity,_owned(table,table.c.id,scope))).first()
                if row is None or tuple(row) != expected:
                    fail('Native member/audit/notification output changed')
        self.provenance_current()

    def validate(self, session, *args):
        self.current()
        if session.deleted:
            fail('Team setup cannot delete native records')
        for row in session.dirty:
            changed = {key for key,attr in inspect(row).attrs.items() if attr.history.has_changes()}
            if not changed:
                continue
            if type(row) is not PMSWorkspaceInvitation or row.id not in {item.id for item in self.invites} or changed != {'status'} or row.status != 'accepted':
                fail('Only exact matching native invitation acceptance is writable')
        for row in session.new:
            if row not in self.births and row.id is not None:
                fail('Native team setup requires genuinely new identities')
            if type(row) is PMSWorkspaceMember:
                if self.root is not None and row is not self.root:
                    fail('One command creates one actual native member')
                if (row.workspace_id,row.user_id,row.role) != (self.wid,self.reference.id,self.data.role):
                    fail('Native member differs from its exact authorized target and role')
                self.root = row
            elif type(row) is AuditLog:
                if (row.organization_id,row.user_id,row.actor_email,row.method,row.module,row.entity_type,row.entity_id,row.action,
                    row.description,row.workspace_id,row.project_id,row.status_code,row.old_values,row.new_values) != (
                    self.scope.company_id,self.actor.id,self.actor.email,'POST','project_management','user',self.reference.id,
                    'PMS_WORKSPACE_ADDED','Added existing person directly',self.wid,None,200,None,json.dumps({'role':self.data.role})):
                    fail('Native team audit requires the actual actor, target and workspace')
            elif type(row) is Notification:
                if (self.root is None or getattr(row,'_suite_source_record',None) is not self.root
                        or inspect(self.root).session is not session or not inspect(self.root).persistent
                        or row.company_id != self.scope.company_id or row.user_id != self.reference.id
                        or row.title != 'Added to workspace' or row.message != f'You were added to {self.workspace_name} as {self.data.role}.'
                        or row.module != 'project_management' or row.event_type != 'workspace.member_added'
                        or row.action_url != f'/pms/workspaces?workspace={self.wid}'):
                    fail('Private native membership notice needs its actual persisted member witness')
                self.notice = row
            elif type(row) is EmailOutbox:
                from .construction_outbox import notification_email_identity
                if notification_email_identity(session,row,self.scope) != {'source_table':'notifications','source_key':str(self.notice.id if self.notice is not None else -1)}:
                    fail('Native team email needs its exact pending membership notice')
            else:
                fail('Unreviewed native team setup side effect: '+row.__tablename__)
            if row not in self.births:
                self.births.append(row)
            if type(row) is Notification and id(row) not in self.prepared_notices:
                from .delivery_sources import prepare_native_notice
                prepare_native_notice(session,self.scope,row,self.root)
                self.prepared_notices.add(id(row))

    def stamp(self, session, *args):
        previous = set(self.stamped)
        _Birth.stamp(self,session)
        from .delivery_sources import mint_private_notice
        for row in self.births:
            if id(row) in previous or id(row) not in self.stamped:
                continue
            if type(row) is Notification:
                mint_private_notice(session,self.scope,row)
        self.accepted.update(item.id for item in self.invites if not session.query(PMSWorkspaceInvitation).filter_by(id=item.id,status='pending').first())


def _native(plan):
    from app.access.models import AccessMembership,AccessPolicy,AccessRole
    from app.access.scope import install_scope
    from app.common.models import CommonPerson
    from app.models.company import Company
    from app.apps.project_management import workspaces as native
    db,actor,scope = plan.db,plan.actor,plan.scope
    criteria = {
        User:User.id == actor.id, Role:Role.id == actor.role_id,
        Employee:and_(Employee.user_id == actor.id,or_(Employee.branch_id.in_(select(Branch.__table__.c.id).where(Branch.__table__.c.company_id == scope.company_id)),Employee.branch_id.is_(None) & (scope.company_id == 1))),
        Branch:and_(Branch.company_id == scope.company_id,Branch.id.in_(select(Employee.__table__.c.branch_id).where(Employee.__table__.c.user_id == actor.id))),
        Permission:Permission.id.in_(select(role_permissions.c.permission_id).where(role_permissions.c.role_id == actor.role_id)),
        CommonPerson:and_(CommonPerson.user_id == actor.id,CommonPerson.organization_id == scope.company_id),
        Company:Company.id == scope.company_id,
        AccessMembership:and_(AccessMembership.company_id == scope.company_id,AccessMembership.user_id == actor.id),
        AccessPolicy:and_(AccessPolicy.company_id == scope.company_id,AccessPolicy.user_id == actor.id),
        AccessRole:and_(AccessRole.company_id == scope.company_id,AccessRole.id.in_([g['roleId'] for g in plan.grants.values() if type(g.get('roleId')) is int])),
        PMSWorkspace:and_(PMSWorkspace.id == plan.wid,PMSWorkspace.organization_id == scope.company_id),
        PMSWorkspaceMember:and_(PMSWorkspaceMember.workspace_id == plan.wid,PMSWorkspaceMember.user_id.in_([actor.id,plan.reference.id])),
        WorkspaceArchive:WorkspaceArchive.workspace_id == plan.wid,
        EmailOutbox:and_(EmailOutbox.organization_id == scope.company_id,EmailOutbox.module == 'notifications',
            EmailOutbox.recipient_user_id == plan.reference.id,_owned(EmailOutbox.__table__,EmailOutbox.id,scope)),
        PMSWorkspaceInvitation:PMSWorkspaceInvitation.id.in_([item.id for item in plan.invites]),
    }
    reader = _MemberSession(bind=db.connection(),autoflush=False,expire_on_commit=False,join_transaction_mode='create_savepoint')
    reader._member_plan,reader._target_window = plan,False
    # Exact company_ids scalar facts for the independently proved target do
    # not change the User/Person ORM SELF criteria.
    reader._authority_reads = _PlanAuthority(db.connection(),scope.company_id,{actor.id,plan.reference.id})
    reader.info.update(shared_actor=(actor.id,scope.company_id),security_write_request=True)
    cleanup = None
    emitter_frame,emitter_cleanup,emitter_successful = None,None,False
    try:
        def restrict(execution):
            if not execution.is_select or not execution.is_orm_statement:
                fail('Team setup has no general SQL authority')
            assert_mapped_sources(execution.statement,frozenset(criteria),allowed_associations=(role_permissions,))
            execution.statement = execution.statement.options(*(with_loader_criteria(model,condition,include_aliases=True,propagate_to_loaders=True) for model,condition in criteria.items()))
        event.listen(reader,'do_orm_execute',restrict)
        event.listen(reader,'before_flush',plan.validate);event.listen(reader,'after_flush_postexec',plan.stamp)
        principal = reader.get(User,actor.id)
        if principal is None or inspect(principal).session is not reader:
            fail('The native actor must be the actual authenticated User')
        principal.organization_id = scope.company_id
        principal._suite_grants,principal._suite_current_module,principal._suite_admin_read = plan.grants,'project_management',False
        principal._suite_permission_objects = [SimpleNamespace(name=name,module='project_management') for name in plan.grants['project_management'].get('permissions',())]
        member = AccessMembership.__table__
        principal._suite_is_company_admin = bool(db.connection().scalar(select(member.c.is_admin).where(member.c.user_id == actor.id,member.c.company_id == scope.company_id,member.c.active.is_(True))))
        prior = tuple(reader.dispatch.do_orm_execute)
        cleanup = install_scope(reader,principal,scope.company_id,plan.grants)
        if len([hook for hook in reader.dispatch.do_orm_execute if hook not in prior]) != 1:
            fail('Unexpected native team source graph')
        from .construction_emitter import issue
        from .delivery_sources import bind_native_emitter
        emitter_frame = issue(reader,parent=db,scope=scope,actor=actor,self_user=principal,
            purpose='construction.team.member',current=plan.current,epoch=plan.authority)
        emitter_cleanup = bind_native_emitter(reader,scope,parent=db,frame=emitter_frame)
        reader._target_window = True
        try:
            result = native.add_workspace_member_operation(plan.wid,native.AddMemberInput(user_id=plan.reference.id,role=plan.data.role),reader,principal,commit=False)
        finally:
            reader._target_window = False
        while reader.new or reader.dirty:
            reader.flush()
        if result is not plan.root or plan.notice is None:
            fail('Native team setup did not produce its actual member and notice')
        plan.expected = [(type(row),row.id,tuple(getattr(row,c.name) for c in row.__table__.columns)) for row in plan.births]
        plan.current()
        from .construction_emitter import seal
        seal(emitter_frame)
        reader.get_transaction().commit()
        emitter_successful = True
        return {'id':plan.root.id,'user_id':plan.reference.id,'email':plan.reference.email,'role':plan.data.role}
    finally:
        if emitter_cleanup:
            emitter_cleanup()
        if cleanup:
            cleanup()
        reader.close()
        if emitter_frame is not None:
            from .construction_emitter import release_native
            release_native(emitter_frame,successful=emitter_successful)


def validate_record(db,scope,row):
    plan = _COMMANDS.get(db)
    live = plan is not None and plan.record is row
    if type(row) is not IndustryRecord or row.kind != KIND and not live:
        return False
    if row in db.deleted or inspect(row).persistent and db.is_modified(row,include_collections=True):
        fail('Native team setup provenance is immutable')
    if not inspect(row).persistent and (not live or plan.scope != scope):
        fail('Native team provenance requires its exact real membership command')
    if live:
        plan.current()
    return True


def create(wid,data,db,actor):
    from app.apps.srm.industry_api import digest,audit
    plan = _Member(db,actor,wid,data)
    scope,table = plan.scope,IndustryRecord.__table__
    prior = db.connection().execute(select(table).where(table.c.organization_id == scope.company_id,table.c.branch_id == scope.branch_id,table.c.request_id == str(data.request_id))).first()
    if prior:
        if (prior.kind != KIND or prior.created_by != actor.id or prior.data.get('_request_digest') != digest(data)
                or prior.data.get('workspace_id') != wid or not db.connection().scalar(select(exists().where(
                    PackRecordOwnership.resource_table == table.name,PackRecordOwnership.resource_key == str(prior.id),PackRecordOwnership.context_id == scope.context_id)))):
            fail('The team request identity is already reserved',409)
        return prior.data['native_result']
    if db in _COMMANDS:
        fail('Team setup commands cannot nest')
    try:
        with db.begin_nested():
            result = _native(plan)
            payload = {'workspace_id':wid,'member_id':result['id'],'target_user_id':data.user_id,'role':data.role,
                '_request_digest':digest(data),'native_result':result}
            plan.record = IndustryRecord(organization_id=scope.company_id,branch_id=scope.branch_id,project_id=None,parent_id=None,
                kind=KIND,title=f'Workspace {wid} membership {data.user_id}',status='created',revision=1,request_id=str(data.request_id),created_by=actor.id,data=payload)
            plan.record_expected = {key:getattr(plan.record,key) for key in ('organization_id','branch_id','project_id','parent_id','kind','title','status','revision','request_id','created_by')}
            plan.record_expected.update(approved_by=None,customer_id=None,invoice_id=None,stock_movement_id=None,starts_at=None,ends_at=None,data=deepcopy(payload))
            _COMMANDS[db] = plan
            try:
                db.add(plan.record);db.flush();plan.seal_provenance()
                audit(db,actor,plan.record,'workspace_member_created');plan.current()
            finally:
                _COMMANDS.pop(db,None)
        plan.current();db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.post('/workspaces/{workspace_id}/member-definitions',status_code=201)
def add_member(workspace_id:int,data:MemberInput,db=Depends(get_db),actor=Depends(get_current_user)):
    return create(workspace_id,data,db,actor)


@router.get('/workspaces/{workspace_id}/member-options')
def options(workspace_id:int,after_user_id:int=0,db=Depends(get_db),actor=Depends(get_current_user)):
    source = access(db,actor,workspace_id)
    scope = source[0]
    # access() runs the actual native Owner/Admin check in a SELF-only reader.
    user,grant,member = User.__table__,PackUserGrant.__table__,PMSWorkspaceMember.__table__
    ids = tuple(db.connection().scalars(select(user.c.id).where(user.c.id>max(0,after_user_id),user.c.is_active.is_(True),
        exists().where(grant.c.user_id == user.c.id,grant.c.context_id == scope.context_id,grant.c.company_id == scope.company_id,grant.c.branch_id == scope.branch_id,grant.c.active.is_(True)),
        ~exists().where(member.c.workspace_id == workspace_id,member.c.user_id == user.c.id)).order_by(user.c.id).limit(26)))
    result = []
    for uid in ids[:25]:
        try:
            reference,_ = target_proof(db,actor,scope,uid)
            result.append({'id':uid,'name':reference.email})
        except HTTPException as exc:
            if exc.status_code not in {403,404}:
                raise
    if source != access(db,actor,workspace_id):
        fail('Native roster authority changed before the response')
    return {'items':result,'next_after_user_id':ids[24] if len(ids)>25 else None,
        'can_add_admin':_owner_access(db,actor,scope,source[1],workspace_id) == 'Owner'}
