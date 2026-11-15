"""Exact native PMS resources and typed time creation, without a general graph grant."""
from dataclasses import dataclass
from sqlalchemy import and_, event, exists, inspect, select
from sqlalchemy.orm import Session, with_loader_criteria
from app.business_packs.boundary import _current
from app.business_packs.common_core import _native_authority
from app.business_packs.common_queries import assert_mapped_sources
from fastapi import HTTPException


class _Reader(Session):
    """Native ORM reader without a public raw SQL/transaction escape."""
    _orm_depth = 0

    def _deny(self, *args, **kwargs):
        raise HTTPException(403, 'Accounts project authorization is read-only')

    add = add_all = delete = flush = commit = rollback = merge = _deny
    bulk_save_objects = bulk_insert_mappings = bulk_update_mappings = _deny

    def connection(self, *args, **kwargs):
        if args or kwargs:
            self._deny()
        return self._authority_reads

    @property
    def bind(self):
        if not self._orm_depth:
            self._deny()
        return self._native_bind

    @bind.setter
    def bind(self, value):
        self._native_bind = value

    def get_bind(self, *args, **kwargs):
        if not self._orm_depth:
            self._deny()
        return super().get_bind(*args, **kwargs)

    def _execute_internal(self, *args, **kwargs):
        self._orm_depth += 1
        try:
            return super()._execute_internal(*args, **kwargs)
        finally:
            self._orm_depth -= 1


class _TimeWriter(_Reader):
    add = Session.add

    def flush(self, *args, **kwargs):
        self._orm_depth += 1
        try:
            return Session.flush(self, *args, **kwargs)
        finally:
            self._orm_depth -= 1

def _project_epoch(db, scope, project_id):
    from app.apps.project_management.models import PMSProject, PMSProjectMember, PMSWorkspaceMember
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    p, member, workspace, archive = (m.__table__ for m in
        (PMSProject, PMSProjectMember, PMSWorkspaceMember, WorkspaceArchive))
    connection = db.connection()
    row = connection.execute(select(p.c.organization_id, p.c.workspace_id, p.c.manager_user_id,
        p.c.owner_user_id, p.c.department_id, p.c.branch_id, p.c.is_task_collection,
        p.c.is_client_visible, p.c.deleted_at).where(p.c.id == project_id)).first()
    if row is None:
        return None
    membership = tuple(connection.execute(select(member.c.id, member.c.role).where(
        member.c.project_id == project_id, member.c.user_id == scope.user_id)).all())
    workspace_membership = tuple(connection.execute(select(workspace.c.id, workspace.c.role).where(
        workspace.c.workspace_id == row.workspace_id, workspace.c.user_id == scope.user_id)).all())
    lifecycle = connection.execute(select(archive.c.deleted_at, archive.c.restored_at).where(
        archive.c.workspace_id == row.workspace_id)).first()
    return tuple(row), membership, workspace_membership, tuple(lifecycle) if lifecycle else None


@dataclass(frozen=True)
class ProjectSource:
    id: int
    name: str
    currency: str


def _deny(message='Accounts project is unavailable', status=404):
    raise HTTPException(status, message)


def _source(db, actor, project_id):
    from app.apps.project_management.models import PMSProject
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackRecordOwnership
    scope = db.info.get('business_pack_scope')
    branch = db.info.get('branch_context')
    state = inspect(actor, raiseerr=False)
    if (scope is None or scope.pack_key != 'accounting_firm' or type(project_id) is not int or project_id < 1
            or state is None or state.session is not db or not state.persistent
            or actor.id != scope.user_id or actor.organization_id != scope.company_id
            or getattr(branch, 'company_id', None) != scope.company_id
            or getattr(branch, 'branch_id', None) != scope.branch_id):
        _deny('Accounts source authorization changed', 403)
    connection = db.connection()
    _current(scope, connection)
    project = PMSProject.__table__
    owner = PackRecordOwnership.__table__
    native = BranchOwnership.__table__
    row = connection.execute(select(project.c.id, project.c.workspace_id).where(
        project.c.id == project_id, project.c.organization_id == scope.company_id,
        project.c.branch_id == scope.branch_id, project.c.deleted_at.is_(None),
        exists().where(owner.c.resource_table == project.name, owner.c.resource_key == str(project_id),
            owner.c.company_id == scope.company_id, owner.c.branch_id == scope.branch_id,
            owner.c.context_id == scope.context_id),
        exists().where(native.c.resource_table == project.name, native.c.resource_key == str(project_id),
            native.c.company_id == scope.company_id, native.c.branch_id == scope.branch_id),
    )).first()
    if row is None:
        _deny()
    if row.workspace_id is not None:
        from app.apps.project_management.models import PMSWorkspace
        workspace = PMSWorkspace.__table__
        if not connection.scalar(select(exists().where(workspace.c.id == row.workspace_id,
                workspace.c.organization_id == scope.company_id,
                exists().where(owner.c.resource_table == workspace.name, owner.c.resource_key == str(row.workspace_id),
                    owner.c.company_id == scope.company_id, owner.c.branch_id == scope.branch_id,
                    owner.c.context_id == scope.context_id),
                exists().where(native.c.resource_table == workspace.name, native.c.resource_key == str(row.workspace_id),
                    native.c.company_id == scope.company_id, native.c.branch_id == scope.branch_id)))):
            _deny('Accounts project workspace is unavailable')
    return scope, row.workspace_id


def project_for_action(db, actor, project_id, action='browse'):
    return _resource(db, actor, project_id, action)


def file_source(db, actor, project_id, file_id, *, download=False):
    from app.apps.project_management.models import PMSFileAsset
    from app.business_packs.models import PackRecordOwnership
    scope, _ = _source(db, actor, project_id)
    files, owners = PMSFileAsset.__table__, PackRecordOwnership.__table__
    if not db.connection().scalar(select(exists().where(files.c.id == file_id,
            files.c.project_id == project_id, files.c.deleted_at.is_(None), exists().where(
                owners.c.resource_table == files.name, owners.c.resource_key == str(file_id),
                owners.c.company_id == scope.company_id, owners.c.branch_id == scope.branch_id,
                owners.c.context_id == scope.context_id)))):
        _deny('Accounts document is unavailable')
    task_id = db.connection().scalar(select(files.c.task_id).where(files.c.id == file_id))
    if task_id is not None:
        from .upload_resources import task_source
        task_source(db, actor, project_id, task_id)
    return _resource(db, actor, project_id, 'browse', file_id=file_id, download=download)


def create_actual_time(db, actor, project_id, data):
    from app.apps.project_management.schemas import PMSTimeLogCreate
    from .service import authority
    authority(db, actor, 'time.record', write=True)
    if (type(data) is not PMSTimeLogCreate or data.project_id != project_id or data.task_id is not None
            or data.approval_status != 'Pending' or data.start_time is not None or data.end_time is not None):
        _deny('Only an explicit new native project time entry is supported', 422)
    return _resource(db, actor, project_id, 'log_time', time_input=data)


def upload_task(db, actor, command):
    from .upload_resources import UploadCommand
    if type(command) is not UploadCommand or command.db is not db or command.actor is not actor:
        _deny('An exact Accounts upload command is required', 403)
    return _resource(db, actor, command.project_id, 'upload', task_id=command.task_id, upload_command=command)


def upload_task_access(db, actor, project_id, task_id):
    return _resource(db, actor, project_id, 'upload', task_id=task_id)


def _resource(db, actor, project_id, action, *, time_input=None, file_id=None, download=False,
              task_id=None, upload_command=None):
    """Run the actual native action check over one explicitly owned project."""
    from app.access.models import AccessMembership, AccessPolicy, AccessRole
    from app.apps.project_management.access import get_project_for_action
    from app.apps.project_management.models import PMSProject, PMSProjectMember, PMSWorkspaceMember
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.apps.srm.commercial_models import ProjectCommercial
    from app.models.company import Company
    from app.shared.models import ServicePolicy
    from app.shared.settings import effective

    if action not in {'browse', 'log_time', 'upload', 'approve'}:
        _deny('Unreviewed Accounts project action', 403)
    scope, workspace_id = _source(db, actor, project_id)
    if task_id is not None:
        from .upload_resources import task_source
        task_source(db, actor, project_id, task_id)
    authority = _native_authority(db, actor, scope.company_id)
    epoch = _project_epoch(db, scope, project_id)
    policy_table = AccessPolicy.__table__
    policy = db.connection().execute(select(policy_table.c.grants).where(
        policy_table.c.company_id == scope.company_id, policy_table.c.user_id == scope.user_id)).scalar_one_or_none()
    role_ids = frozenset(grant['roleId'] for grant in (policy or {}).values()
                         if isinstance(grant, dict) and type(grant.get('roleId')) is int)
    criteria = {
        PMSProject: and_(PMSProject.id == project_id, PMSProject.organization_id == scope.company_id,
                         PMSProject.branch_id == scope.branch_id),
        PMSProjectMember: and_(PMSProjectMember.project_id == project_id, PMSProjectMember.user_id == scope.user_id),
        PMSWorkspaceMember: and_(PMSWorkspaceMember.workspace_id == workspace_id, PMSWorkspaceMember.user_id == scope.user_id),
        WorkspaceArchive: WorkspaceArchive.workspace_id == workspace_id,
        AccessMembership: and_(AccessMembership.company_id == scope.company_id, AccessMembership.user_id == scope.user_id),
        AccessPolicy: and_(AccessPolicy.company_id == scope.company_id, AccessPolicy.user_id == scope.user_id),
        AccessRole: and_(AccessRole.company_id == scope.company_id, AccessRole.id.in_(role_ids)),
        ProjectCommercial: and_(ProjectCommercial.project_id == project_id, ProjectCommercial.seller_id == scope.company_id),
        Company: Company.id == scope.company_id,
        ServicePolicy: and_(ServicePolicy.kind == 'settings', ServicePolicy.scope_key.in_(
            ('platform', f'company:{scope.company_id}', f'company:{scope.company_id}:module:srm'))),
    }
    if file_id is not None:
        from app.apps.project_management.models import PMSFileAsset
        from app.models.file_storage import StorageObject
        from app.services.file_storage import relative
        criteria[PMSFileAsset] = and_(PMSFileAsset.id == file_id, PMSFileAsset.project_id == project_id,
            PMSFileAsset.deleted_at.is_(None))
        stored = db.connection().scalar(select(PMSFileAsset.__table__.c.storage_path).where(
            PMSFileAsset.__table__.c.id == file_id, PMSFileAsset.__table__.c.project_id == project_id))
        try:
            relative_path = relative(stored)
        except HTTPException:
            relative_path = ''
        criteria[StorageObject] = and_(StorageObject.organization_id == scope.company_id,
            StorageObject.relative_path == relative_path)
    if task_id is not None:
        from app.apps.project_management.models import PMSTask, PMSTaskAssignee
        criteria[PMSTask] = and_(PMSTask.id == task_id, PMSTask.project_id == project_id, PMSTask.deleted_at.is_(None))
        criteria[PMSTaskAssignee] = and_(PMSTaskAssignee.task_id == task_id, PMSTaskAssignee.user_id == actor.id)
    if upload_command is not None:
        criteria.update(upload_command.criteria())
    allowed = frozenset(criteria)

    def restrict(execution):
        if (not execution.is_select or not execution.is_orm_statement
                or execution.is_insert or execution.is_update or execution.is_delete):
            _deny('Accounts authorization resource is read-only', 403)
        assert_mapped_sources(execution.statement, allowed)
        from app.models.file_storage import StorageObject
        quota = (upload_command is not None and getattr(execution.bind_mapper, 'class_', None) is StorageObject
            and str(execution.statement.compile(compile_kwargs={'literal_binds': True})) == upload_command.quota_query(native))
        execution.statement = execution.statement.options(*(with_loader_criteria(model, criterion,
            include_aliases=True, propagate_to_loaders=True) for model, criterion in criteria.items()
            if not (quota and model is StorageObject)))

    def no_write(*args, **kwargs):
        _deny('Accounts authorization resource is read-only', 403)

    connection = db.connection()
    # rollback_only prevents closing this private Session from rolling back or
    # committing the request's already-open transaction.
    writing = time_input is not None or upload_command is not None
    native = (_TimeWriter if writing else _Reader)(bind=connection, autoflush=False, expire_on_commit=False,
                     join_transaction_mode='create_savepoint' if writing else 'rollback_only')
    native.info.update(shared_actor=(scope.user_id, scope.company_id),
                       suite_access_schema_ready=all(inspect(connection).has_table(model.__tablename__)
                           for model in (AccessMembership, AccessPolicy, AccessRole)),
                       branch_context=db.info.get('branch_context'),
                       security_write_request=bool(db.info.get('security_write_request')))
    if upload_command is not None:
        native.info['file_download_company'] = scope.company_id
    from .authority_reads import capture as capture_authority_reads
    native._authority_reads = capture_authority_reads(db, scope.company_id)
    event.listen(native, 'do_orm_execute', restrict)
    minted = []
    def validate_time(session, *args):
        from app.apps.project_management.models import PMSTimeLog, PMSActivity
        if session.dirty or session.deleted:
            _deny('Native time creation cannot alter existing records', 403)
        _source(db, actor, project_id)
        if authority != _native_authority(db, actor, scope.company_id) or epoch != _project_epoch(db, scope, project_id):
            _deny('Native time authority changed', 403)
        for item in session.new:
            if item not in minted and item.id is not None:
                _deny('Native time creation requires a genuine new generated identity', 409)
            if type(item) is PMSTimeLog:
                expected = dict(time_input.model_dump(), user_id=actor.id)
                if (any(getattr(item, key) != value for key, value in expected.items())
                        or item.timesheet_id is not None or item.approved_by_user_id is not None or item.approved_at is not None):
                    _deny('Native time differs from its explicit creation input', 409)
            elif type(item) is PMSActivity:
                if (item.project_id != project_id or item.actor_user_id != actor.id or item.action != 'time.logged'
                        or item.entity_type != 'time_log' or item.task_id is not None or item.sprint_id is not None
                        or not any(type(row) is PMSTimeLog and row.id == item.entity_id for row in minted)):
                    _deny('Native time activity differs from its actual new time source', 409)
            else:
                _deny('Unreviewed native time write', 403)
            if item not in minted:
                minted.append(item)
    event.listen(native, 'before_flush', upload_command.validate if upload_command is not None else
        validate_time if time_input is not None else no_write)
    event.listen(native, 'before_commit', no_write)
    native.commit = no_write
    native.rollback = no_write
    if not writing:
        native.flush = native.add = no_write
    native.add_all = native.delete = no_write
    native.bulk_save_objects = native.bulk_insert_mappings = native.bulk_update_mappings = no_write
    result = None
    try:
        project = get_project_for_action(native, project_id, actor, action)
        if task_id is not None:
            from app.apps.project_management.access import get_task_project_for_action
            get_task_project_for_action(native, task_id, actor, action)
        commercial = native.get(ProjectCommercial, project_id)
        # A mismatched legal seller is corrupt linkage, never a default-currency
        # fallback that could alter an already priced project.
        actual_seller = connection.scalar(select(ProjectCommercial.__table__.c.seller_id).where(
            ProjectCommercial.__table__.c.project_id == project_id))
        if actual_seller is not None and actual_seller != scope.company_id:
            _deny('Project seller requires reconciliation', 409)
        currency = commercial.currency if commercial else effective(native, scope.company_id, 'srm')['values']['currency']
        result = ProjectSource(project.id, project.name, currency)
        if upload_command is not None:
            from app.apps.project_management.api.router import upload_task_attachment_operation
            row = upload_task_attachment_operation(task_id, upload_command.upload, native, actor, commit=False)
            result = upload_command.finish(native, row)
        if file_id is not None:
            from app.apps.project_management.api.router import _get_file_for_action, download_attachment
            asset, parent = _get_file_for_action(native, file_id, actor, 'browse')
            if parent.id != project_id:
                _deny('Accounts document project changed', 409)
            if download:
                from app.core.audit_context import context as audit_context
                original = audit_context.get()
                evidence = dict(original or {}, storage_session=native)
                token = audit_context.set(evidence)
                native.info['file_download_company'] = scope.company_id
                try:
                    from .cloud_download import response as cloud_response
                    result = cloud_response(db,actor,scope,native,asset)
                    if result is None:result = download_attachment(file_id, native, actor)
                    if original is not None and 'file_response_path' in evidence:
                        original['file_response_path'] = evidence['file_response_path']
                finally:
                    audit_context.reset(token)
            else:
                result = {'file_id': asset.id, 'project_id': project_id, 'name': asset.original_name,
                    'size_bytes': asset.size_bytes, 'version_number': asset.version_number}
        if time_input is not None:
            from app.apps.project_management.api.router import create_time_log_operation
            from app.apps.project_management.models import PMSTimeLog, PMSActivity
            row = create_time_log_operation(time_input, native, actor, commit=False)
            logs = [item for item in minted if type(item) is PMSTimeLog]
            activities = [item for item in minted if type(item) is PMSActivity]
            if logs != [row] or len(activities) != 1:
                _deny('Native time creation must mint exactly one log and its activity', 409)
            from app.branches.models import BranchOwnership
            from app.business_packs.models import PackRecordOwnership
            for item in minted:
                connection.execute(BranchOwnership.__table__.insert().values(resource_table=item.__tablename__,
                    resource_key=str(item.id), company_id=scope.company_id, branch_id=scope.branch_id, source='accounts-time'))
                connection.execute(PackRecordOwnership.__table__.insert().values(resource_table=item.__tablename__,
                    resource_key=str(item.id), company_id=scope.company_id, branch_id=scope.branch_id,
                    context_id=scope.context_id, source='accounts-time', revision=1))
            result = {'time_log_id': row.id, 'project_id': project_id, 'duration_minutes': row.duration_minutes,
                'log_date': row.log_date.isoformat(), 'approval_status': row.approval_status}
        _source(db, actor, project_id)
        if _native_authority(db, actor, scope.company_id) != authority:
            _deny('Native Accounts authority changed', 403)
        if epoch != _project_epoch(db, scope, project_id):
            _deny('Native Accounts project authority changed', 403)
        if native._authority_reads.fingerprint != capture_authority_reads(db, scope.company_id).fingerprint:
            _deny('Native Accounts company entitlements changed', 403)
        # Re-run native licensing logic as well as comparing data: an unchanged
        # subscription can expire while this operation is in progress.
        get_project_for_action(native, project_id, actor, action)
        if task_id is not None:
            task_source(db, actor, project_id, task_id)
            get_task_project_for_action(native, task_id, actor, action)
        if writing:
            # Release only this private Session's savepoint. The request's outer
            # savepoint/transaction still owns time, ownership and command writes.
            event.remove(native, 'before_commit', no_write)
            Session.commit(native)
        return result
    except BaseException:
        if download:
            from .cloud_download import abort
            abort(result)
        raise
    finally:
        try:
            native.close()
        except BaseException:
            if download:
                from .cloud_download import abort
                abort(result)
            raise
