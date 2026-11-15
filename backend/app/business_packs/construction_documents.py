"""Closed native PMS project documents for one authenticated Construction site.

The operational pack Session never receives PMS or storage ORM access. A private
same-transaction Session runs the native PMS operation over exact sources and
may create only its one file, activity and storage locator.
"""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import String, and_, bindparam, event, exists, func, inspect, select
from sqlalchemy.inspection import _inspects
from sqlalchemy.orm import Session, with_loader_criteria

from .boundary import _current
from .common_core import _native_authority
from .common_queries import assert_mapped_sources
from .construction import _source, _project_epoch
from .operations import require


def deny(message='Construction document is unavailable', status=403):
    raise HTTPException(status, message)


def _key(statement, parameters=None):
    return str(statement.compile(compile_kwargs={'literal_binds': True})), repr(parameters or {})


class _AuthorityReads:
    def __init__(self, connection, company):
        from app.apps.business_os.models import BOSEnabledModule
        from app.models.company import Company
        from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
        from app.shared.master_data_models import ContactChannel
        from app.shared.models import ServiceEvent
        from app.db.schema_columns import table_columns
        schema = inspect(connection)
        self.dialect = SimpleNamespace(name=connection.dialect.name)
        self.columns = {name: [c['name'] for c in schema.get_columns(name)] if schema.has_table(name) else None
            for name in ('bos_enabled_modules', 'tenant_subscriptions', ContactChannel.__tablename__, ServiceEvent.__tablename__)}
        self.rows = {}
        def freeze(statement, parameters=None):
            frozen = connection.execute(statement, parameters or {}).freeze()
            self.rows[_key(statement, parameters)] = frozen
            return frozen().mappings().first()
        enabled, organization, subscription, plan = (model.__table__ for model in
            (BOSEnabledModule, Company, TenantSubscription, TenantSubscriptionPlan))
        if self.columns['bos_enabled_modules'] is not None:
            freeze(enabled.select().where(enabled.c.company_id == company))
        freeze(organization.select().where(organization.c.id == company))
        if connection.dialect.name == 'postgresql':
            class Recorder:
                dialect = connection.dialect
                def execute(self, statement, parameters=None):
                    freeze(statement, parameters)
                    return self_outer.rows[_key(statement, parameters)]()
            self_outer = self
            table_columns(Recorder(), ('tenant_subscriptions',))
        if self.columns['tenant_subscriptions'] is not None and 'company_id' in self.columns['tenant_subscriptions']:
            current = freeze(select(subscription).where(subscription.c.company_id == company))
            if current:
                assigned = freeze(select(plan).where(plan.c.id == current['plan_id']))
                config = dict(assigned['config_json'] or {}) if assigned else {}
                config.update(current['config_json'] or {})
                pending = config.get('scheduled_change')
                if isinstance(pending, dict) and type(pending.get('plan_id')) is int:
                    freeze(select(plan).where(plan.c.id == pending['plan_id']))
        self.fingerprint = sha256(repr([(k, v.data) for k, v in self.rows.items()]).encode()).hexdigest()

    def execute(self, statement, parameters=None, **kwargs):
        frozen = self.rows.get(_key(statement, parameters))
        if frozen is None or kwargs:
            deny('Unreviewed Construction document authority query')
        return frozen()

    def has_table(self, name, schema=None, **kwargs):
        if schema is not None or name not in self.columns:
            deny('Unreviewed Construction document authority schema')
        return self.columns[name] is not None

    def get_columns(self, name, schema=None, **kwargs):
        if not self.has_table(name, schema):
            from sqlalchemy.exc import NoSuchTableError
            raise NoSuchTableError(name)
        return [{'name': value} for value in self.columns[name]]


@_inspects(_AuthorityReads)
def _inspect_authority(value):
    return value


class _Reader(Session):
    _orm_depth = 0
    def _deny(self, *args, **kwargs):
        deny('Construction document resource has no general database authority')
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


class _Writer(_Reader):
    add = Session.add
    def flush(self, *args, **kwargs):
        self._orm_depth += 1
        try:
            return Session.flush(self, *args, **kwargs)
        finally:
            self._orm_depth -= 1


def _storage_epoch(db, company):
    from app.core.config import settings
    from app.models.file_storage import StoragePolicy, StorageConnection
    policy, connection = StoragePolicy.__table__, StorageConnection.__table__
    row = db.connection().execute(select(policy).where(policy.c.organization_id == company)).mappings().first()
    route = ((row['routes'] or {}).get('pms') or (row['routes'] or {}).get('default')) if row and row['enabled'] else None
    ident = route.get('connection_id') if isinstance(route, dict) else None
    selected = db.connection().execute(select(connection.c.id, connection.c.organization_id,
        connection.c.provider, connection.c.connected, connection.c.created_by).where(
        connection.c.organization_id == company, connection.c.id == ident)).mappings().first() if ident is not None else None
    return (dict(row) if row else None, dict(selected) if selected else None,
        settings.STORAGE_BACKEND, settings.PMS_GOOGLE_DRIVE_REQUIRED, settings.UPLOAD_DIR), ident


def _authority(db, actor, project_id, *, write=False):
    from app.access.service import check_background_access
    check_background_access(db, actor, 'project_management', 'create' if write else 'view',
        administrative_read=False, stamp=False)
    require(db, actor, 'diary.record' if write else 'sites.view')
    scope, _ = _source(db, actor, project_id)
    if write and not scope.writable:
        deny('Construction document writes require a writable context')
    return scope


def _owned_file(db, actor, file_id):
    from app.apps.project_management.models import PMSFileAsset
    from .models import PackRecordOwnership
    from app.branches.models import BranchOwnership
    from app.models.file_storage import StorageObject
    from app.services.file_storage import relative
    scope = db.info.get('business_pack_scope')
    if scope is None or scope.pack_key != 'construction':
        deny('A selected Construction context is required')
    require(db, actor, 'sites.view')
    row, owner = PMSFileAsset.__table__, PackRecordOwnership.__table__
    source = db.connection().execute(select(row).where(row.c.id == file_id,
        row.c.deleted_at.is_(None), exists().where(owner.c.resource_table == row.name,
            owner.c.resource_key == str(file_id), owner.c.company_id == scope.company_id,
            owner.c.branch_id == scope.branch_id, owner.c.context_id == scope.context_id))).first()
    if source is None:
        deny(status=404)
    _source(db, actor, source.project_id)
    path = relative(source.storage_path)
    storage = StorageObject.__table__
    locator = db.connection().execute(select(storage).where(storage.c.organization_id == scope.company_id,
        storage.c.relative_path == path)).first()
    if locator is None:
        deny('Construction document storage source is unavailable', 404)
    certificate = _certificate(source, locator)
    for target, identity in ((row, source.id), (storage, locator.id)):
        for ownership, selected in ((owner, (owner.c.context_id == scope.context_id)),
                (BranchOwnership.__table__, True)):
            if not db.connection().scalar(select(exists().where(ownership.c.resource_table == target.name,
                    ownership.c.resource_key == str(identity), ownership.c.company_id == scope.company_id,
                    ownership.c.branch_id == scope.branch_id, ownership.c.source == certificate, selected))):
                deny('Construction document native source changed', 409)
    return source


def _certificate(asset, locator):
    fields = tuple(getattr(asset, name) for name in ('id', 'project_id', 'task_id', 'milestone_id',
        'uploaded_by_user_id', 'storage_path', 'original_name', 'mime_type', 'size_bytes'))
    storage = tuple(getattr(locator, name) for name in ('id', 'organization_id', 'module', 'relative_path', 'filename', 'size', 'sha256'))
    # Ownership.source is immutable and limited to80 chars. The digest binds
    # the exact new canonical asset and locator without a duplicate master.
    return 'construction:' + sha256(repr((fields, storage)).encode()).hexdigest()


def _payload(row):
    # Keep native response shape for existing FilesPage without exposing paths.
    names = ('id', 'project_id', 'task_id', 'milestone_id', 'folder_id', 'file_name', 'original_name',
        'mime_type', 'size_bytes', 'visibility', 'version_number', 'uploaded_by_user_id', 'created_at', 'updated_at')
    result = {name: getattr(row, name) for name in names}
    result.update(storage_path='[private]', uploaded_by_name=None,
        download_url=f'/project-management/attachments/{row.id}/download')
    result['preview_url'] = result['download_url'] if (row.mime_type or '').startswith('image/') or row.mime_type == 'application/pdf' else None
    return result


@dataclass
class _Upload:
    db: object
    actor: object
    project_id: int
    upload: object
    folder_id: object
    size: int
    digest: str

    def __post_init__(self):
        self.scope = _authority(self.db, self.actor, self.project_id, write=True)
        self.authority = _native_authority(self.db, self.actor, self.scope.company_id)
        self.epoch = _project_epoch(self.db, self.scope, self.project_id)
        self.storage, self.connection_id = _storage_epoch(self.db, self.scope.company_id)
        self.minted, self.asset, self.locator, self.staging = [], None, None, {}

    def current(self):
        if (_authority(self.db, self.actor, self.project_id, write=True) is not self.scope
                or _native_authority(self.db, self.actor, self.scope.company_id) != self.authority
                or _project_epoch(self.db, self.scope, self.project_id) != self.epoch
                or _storage_epoch(self.db, self.scope.company_id)[0] != self.storage):
            deny('Construction upload authority or storage policy changed')
        from .construction import project_for_action
        project_for_action(self.db, self.actor, self.project_id, 'upload')

    def path(self, value):
        from app.apps.project_management.api.router import PMS_UPLOAD_ROOT, _safe_attachment_name
        path = Path(value).resolve()
        prefix, _, suffix = path.name.partition('_')
        if (path.parent != (PMS_UPLOAD_ROOT / 'projects' / str(self.project_id)).resolve()
                or not path.is_file() or path.stat().st_size != self.size
                or len(prefix) != 32 or any(c not in '0123456789abcdef' for c in prefix)
                or suffix != _safe_attachment_name(self.upload.filename)
                or sha256(path.read_bytes()).hexdigest() != self.digest):
            deny('Native upload staging differs from the exact project/input', 409)
        return path

    def validate(self, session, *args):
        from app.apps.project_management.models import PMSFileAsset, PMSActivity
        from app.models.file_storage import StorageObject, StorageConnection
        from app.core.config import settings
        self.current()
        if session.deleted:
            deny('Construction upload cannot delete records')
        for row in session.dirty:
            if row is self.locator:
                self.validate_locator(row)
            elif type(row) is StorageConnection and row.id == self.connection_id:
                if any(attr.history.has_changes() and name not in {'encrypted_value', 'expires_at'} for name, attr in inspect(row).attrs.items()):
                    deny('Only native token refresh can change the selected storage connection')
            else:
                deny('Construction upload cannot modify existing business records')
        for row in session.new:
            if row not in self.minted and row.id is not None:
                deny('Construction upload requires genuinely new identities', 409)
            if type(row) is StorageObject:
                if self.locator is not None and self.locator is not row:
                    deny('One upload requires one new storage locator')
                self.validate_locator(row)
                self.locator = row
            elif type(row) is PMSFileAsset:
                path = self.path(row.storage_path)
                from app.apps.project_management.api.router import _safe_attachment_name
                if (self.asset is not None or row.project_id != self.project_id or row.task_id is not None
                        or row.milestone_id is not None or row.folder_id != self.folder_id
                        or row.uploaded_by_user_id != self.actor.id or row.file_name != path.name
                        or row.original_name != _safe_attachment_name(self.upload.filename)
                        or row.size_bytes != self.size or row.mime_type != (self.upload.content_type or 'application/octet-stream')
                        or row.visibility != 'Project Team' or row.deleted_at is not None):
                    deny('Native project attachment differs from its exact upload', 409)
                self.asset = row
            elif type(row) is PMSActivity:
                if (self.asset is None or row.project_id != self.project_id or row.task_id is not None
                        or row.sprint_id is not None or row.actor_user_id != self.actor.id
                        or row.action != 'attachment.added' or row.entity_type != 'file' or row.entity_id != self.asset.id):
                    deny('Native upload activity requires its actual new attachment', 409)
            else:
                deny('Unreviewed Construction upload write')
            if row not in self.minted:
                self.minted.append(row)

    def validate_locator(self, row):
        import mimetypes
        from app.core.config import settings
        from app.models.file_storage import StorageObject
        from app.apps.project_management.api.router import _safe_attachment_name
        self.path(Path(settings.UPLOAD_DIR) / row.relative_path)
        policy, connection = self.storage[:2]
        route = ((policy['routes'] or {}).get('pms') or (policy['routes'] or {}).get('default')) if policy and policy['enabled'] else None
        folder = route.get('folder_id') if isinstance(route, dict) else None
        providers = {settings.STORAGE_BACKEND, connection['provider'] if connection else settings.STORAGE_BACKEND}
        if (row.organization_id != self.scope.company_id or row.module != 'pms'
                or row.filename != _safe_attachment_name(self.upload.filename) or row.size != self.size or row.sha256 != self.digest
                or row.content_type != (mimetypes.guess_type(row.relative_path)[0] or 'application/octet-stream')
                or row.uploaded_by not in {None, self.actor.id} or row.connection_id not in {None, self.connection_id}
                or row.folder_id not in {None, folder} or row.provider not in providers
                or row.status not in {'local', 'pending', 'cloud'} or row.versions not in (None, [])):
            deny('Native locator differs from its new project attachment', 409)
        if row not in self.minted and self.db.connection().scalar(select(exists().where(
                StorageObject.__table__.c.organization_id == self.scope.company_id,
                StorageObject.__table__.c.relative_path == row.relative_path))):
            deny('Existing storage objects cannot be adopted by an upload', 409)

    def finish(self, native, row):
        from app.apps.project_management.models import PMSFileAsset, PMSActivity
        from app.models.file_storage import StorageObject
        from app.branches.models import BranchOwnership
        from .models import PackRecordOwnership
        self.current()
        if (row is not self.asset or row.version_number != 1
                or len([x for x in self.minted if type(x) is PMSFileAsset]) != 1
                or len([x for x in self.minted if type(x) is PMSActivity]) != 1
                or len([x for x in self.minted if type(x) is StorageObject]) != 1):
            deny('Native upload must mint one file, activity and locator', 409)
        certificate = _certificate(row, self.locator)
        for item in self.minted:
            for table, extra in ((BranchOwnership.__table__, {}), (PackRecordOwnership.__table__, {'context_id': self.scope.context_id, 'revision': 1})):
                self.db.connection().execute(table.insert().values(resource_table=item.__tablename__, resource_key=str(item.id),
                    company_id=self.scope.company_id, branch_id=self.scope.branch_id, source=certificate, **extra))
        pending = native.info.pop('verified_cloud_staging', {})
        if any(Path(name).resolve() != Path(row.storage_path).resolve() or digest != self.digest for name, digest in pending.items()):
            deny('Verified staging requires its exact new project attachment', 409)
        self.staging = pending
        return _payload(row)


def _resource(db, actor, project_id, action, *, command=None, file_id=None):
    from app.access.models import AccessMembership, AccessPolicy, AccessRole
    from app.apps.project_management.models import PMSProject, PMSProjectMember, PMSWorkspaceMember, PMSFileAsset, PMSFileFolder
    from app.apps.project_management.workspace_lifecycle import WorkspaceArchive
    from app.apps.project_management.access import get_project_for_action
    from app.models.company import Company
    from app.models.file_storage import StorageObject, StoragePolicy, StorageConnection
    scope = _authority(db, actor, project_id, write=command is not None)
    _, workspace_id = _source(db, actor, project_id)
    native_authority, epoch = _native_authority(db, actor, scope.company_id), _project_epoch(db, scope, project_id)
    connection = db.connection()
    authority_reads = _AuthorityReads(connection, scope.company_id)
    grants = connection.scalar(select(AccessPolicy.__table__.c.grants).where(AccessPolicy.__table__.c.company_id == scope.company_id, AccessPolicy.__table__.c.user_id == actor.id)) or {}
    role_ids = {g['roleId'] for g in grants.values() if isinstance(g, dict) and type(g.get('roleId')) is int}
    criteria = {
        PMSProject: and_(PMSProject.id == project_id, PMSProject.organization_id == scope.company_id, PMSProject.branch_id == scope.branch_id),
        PMSProjectMember: and_(PMSProjectMember.project_id == project_id, PMSProjectMember.user_id == actor.id),
        PMSWorkspaceMember: and_(PMSWorkspaceMember.workspace_id == workspace_id, PMSWorkspaceMember.user_id == actor.id),
        WorkspaceArchive: WorkspaceArchive.workspace_id == workspace_id,
        AccessMembership: and_(AccessMembership.company_id == scope.company_id, AccessMembership.user_id == actor.id),
        AccessPolicy: and_(AccessPolicy.company_id == scope.company_id, AccessPolicy.user_id == actor.id),
        AccessRole: and_(AccessRole.company_id == scope.company_id, AccessRole.id.in_(role_ids)),
        Company: Company.id == scope.company_id,
    }
    stored_connection = None
    if file_id is not None:
        source = _owned_file(db, actor, file_id)
        from app.services.file_storage import relative
        path = relative(source.storage_path)
        stored = StorageObject.__table__
        stored_connection = connection.scalar(select(stored.c.connection_id).where(stored.c.organization_id == scope.company_id, stored.c.relative_path == path))
        criteria[PMSFileAsset] = and_(PMSFileAsset.id == file_id, PMSFileAsset.project_id == project_id, PMSFileAsset.deleted_at.is_(None))
        criteria[StorageObject] = and_(StorageObject.organization_id == scope.company_id, StorageObject.relative_path == path)
        criteria[StorageConnection] = and_(StorageConnection.organization_id == scope.company_id, StorageConnection.id == stored_connection)
    if command is not None:
        criteria.update({
            PMSFileAsset: and_(PMSFileAsset.project_id == project_id, PMSFileAsset.id == bindparam(
                'construction_new_file', callable_=lambda: command.asset.id if command.asset else -1, unique=True)),
            PMSFileFolder: and_(PMSFileFolder.project_id == project_id, PMSFileFolder.id == command.folder_id),
            StoragePolicy: StoragePolicy.organization_id == scope.company_id,
            StorageConnection: and_(StorageConnection.organization_id == scope.company_id, StorageConnection.id == command.connection_id),
            StorageObject: and_(StorageObject.organization_id == scope.company_id, StorageObject.id == bindparam(
                'construction_new_storage_locator', callable_=lambda: command.locator.id if command.locator else -1, unique=True)),
        })
    native = _Writer(bind=connection, autoflush=False, expire_on_commit=False,
        join_transaction_mode='create_savepoint')
    native._authority_reads = authority_reads
    native.info.update(shared_actor=(scope.user_id, scope.company_id), branch_context=db.info.get('branch_context'),
        security_write_request=bool(db.info.get('security_write_request')), file_download_company=scope.company_id,
        suite_access_schema_ready=all(inspect(connection).has_table(m.__tablename__) for m in (AccessMembership, AccessPolicy, AccessRole)))
    def no_write(*args, **kwargs):
        deny('Construction document resource cannot commit arbitrary writes')
    def token_refresh_only(session, *args):
        _owned_file(db, actor, file_id)
        if session.new or session.deleted:
            deny('Construction download can only refresh its original storage account token')
        for row in session.dirty:
            if (type(row) is not StorageConnection or row.id != stored_connection or row.organization_id != scope.company_id
                    or any(attr.history.has_changes() and name not in {'encrypted_value', 'expires_at'}
                        for name, attr in inspect(row).attrs.items())):
                deny('Construction download can only refresh its original storage account token')
    def restrict(execution):
        if not execution.is_select or not execution.is_orm_statement:
            no_write()
        assert_mapped_sources(execution.statement, frozenset(criteria))
        quota = (command is not None and getattr(execution.bind_mapper, 'class_', None) is StorageObject
            and _key(execution.statement) == _key(native.query(func.coalesce(func.sum(StorageObject.size), 0)).filter_by(organization_id=scope.company_id).statement))
        execution.statement = execution.statement.options(*(with_loader_criteria(model, criterion, include_aliases=True, propagate_to_loaders=True)
            for model, criterion in criteria.items() if not (quota and model is StorageObject)))
    event.listen(native, 'do_orm_execute', restrict)
    event.listen(native, 'before_flush', command.validate if command is not None else token_refresh_only)
    event.listen(native, 'before_commit', no_write)
    try:
        get_project_for_action(native, project_id, actor, action)
        if command is not None:
            from app.apps.project_management.file_workspace import upload_project_file_operation
            row = upload_project_file_operation(project_id, command.upload, command.folder_id, native, actor, commit=False)
            result = command.finish(native, row)
        else:
            from app.apps.project_management.api.router import download_attachment
            from app.core.audit_context import context
            original = context.get()
            evidence = dict(original or {}, storage_session=native)
            token = context.set(evidence)
            try:
                result = download_attachment(file_id, native, actor)
                if result.status_code in (302, 307):
                    # Generic blob tokens are native-user bound, not selected
                    # pack bound. Never release one from a Construction source.
                    from app.services.file_storage import cloud_content
                    from fastapi.responses import Response
                    from urllib.parse import quote
                    stored = _owned_file(db, actor, file_id)
                    verified = cloud_content(stored.storage_path, db=native, company=scope.company_id)
                    if verified is None:
                        deny('Construction cloud document source changed', 409)
                    content, locator = verified
                    result = Response(content=content, media_type=stored.mime_type or 'application/octet-stream',
                        headers={'Content-Disposition': "attachment; filename*=utf-8''" + quote(stored.original_name or stored.file_name),
                            'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
                            'Content-Security-Policy': 'sandbox'})
                if original is not None and 'file_response_path' in evidence:
                    original['file_response_path'] = evidence['file_response_path']
            finally:
                context.reset(token)
        _source(db, actor, project_id)
        if (native_authority != _native_authority(db, actor, scope.company_id) or epoch != _project_epoch(db, scope, project_id)
                or authority_reads.fingerprint != _AuthorityReads(connection, scope.company_id).fingerprint):
            deny('Construction native document authority changed')
        get_project_for_action(native, project_id, actor, action)
        event.remove(native, 'before_commit', no_write)
        Session.commit(native)
        return result
    finally:
        native.close()


def upload(db, actor, project_id, file, folder_id=None):
    from app.apps.project_management.api.router import PMS_MAX_ATTACHMENT_BYTES
    scope = _authority(db, actor, project_id, write=True)
    # Bound the digest pass before any filesystem or native storage mutation.
    digest, size = sha256(), 0
    while chunk := file.file.read(1024 * 1024):
        size += len(chunk)
        if size > PMS_MAX_ATTACHMENT_BYTES:
            file.file.seek(0)
            deny('File exceeds the configured size limit', 413)
        digest.update(chunk)
    file.file.seek(0)
    command = _Upload(db, actor, project_id, file, folder_id, size, digest.hexdigest())
    try:
        with db.begin_nested():
            result = _resource(db, actor, project_id, 'upload', command=command)
        command.current()
        db.info.setdefault('verified_cloud_staging', {}).update(command.staging)
        _current(scope, db.connection())
        command.current()
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def download(db, actor, file_id):
    source = _owned_file(db, actor, file_id)
    scope = _authority(db, actor, source.project_id)
    authority = _native_authority(db, actor, scope.company_id)
    epoch = _project_epoch(db, scope, source.project_id)
    try:
        with db.begin_nested():
            result = _resource(db, actor, source.project_id, 'browse', file_id=file_id)
        _owned_file(db, actor, file_id)
        if authority != _native_authority(db, actor, scope.company_id) or epoch != _project_epoch(db, scope, source.project_id):
            deny('Construction download authority changed')
        from .construction import project_for_action
        project_for_action(db, actor, source.project_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def list_files(db, actor, project_id, *, skip=0, limit=100):
    from app.apps.project_management.models import PMSFileAsset
    from .models import PackRecordOwnership
    from .construction import project_for_action
    scope = _authority(db, actor, project_id)
    project_for_action(db, actor, project_id)
    row, owner = PMSFileAsset.__table__, PackRecordOwnership.__table__
    rows = db.connection().execute(select(row).where(row.c.project_id == project_id, row.c.deleted_at.is_(None),
        (row.c.visibility != 'Work Evidence') | (row.c.uploaded_by_user_id == actor.id),
        exists().where(owner.c.resource_table == row.name, owner.c.resource_key == row.c.id.cast(String),
            owner.c.company_id == scope.company_id, owner.c.branch_id == scope.branch_id, owner.c.context_id == scope.context_id))
        .order_by(row.c.created_at.desc(), row.c.id.desc()).offset(skip).limit(limit)).mappings().all()
    for value in rows:
        _owned_file(db, actor, value['id'])
    _source(db, actor, project_id)
    return [_payload(SimpleNamespace(**dict(value))) for value in rows]


def list_folders(db, actor, project_id):
    from app.apps.project_management.models import PMSFileFolder
    from .construction import project_for_action
    _authority(db, actor, project_id)
    project_for_action(db, actor, project_id)
    table = PMSFileFolder.__table__
    rows = db.connection().execute(select(table.c.id, table.c.name).where(table.c.project_id == project_id)
        .order_by(table.c.name, table.c.id)).all()
    _source(db, actor, project_id)
    return [{'id': row.id, 'name': row.name} for row in rows]
