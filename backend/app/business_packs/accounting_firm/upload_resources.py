"""One native task attachment/storage birth, never a general storage session."""
from hashlib import sha256
from pathlib import Path
from sqlalchemy import and_, bindparam, exists, inspect, select, func
from app.apps.project_management.models import PMSTask, PMSFileAsset, PMSActivity
from app.models.file_storage import StorageObject, StoragePolicy, StorageConnection
from app.business_packs.models import PackRecordOwnership
from app.branches.models import BranchOwnership
from app.business_packs.common_core import _native_authority
from . import service


def task_source(db, actor, project_id, task_id):
    from .pms_sources import _source
    scope, _ = _source(db, actor, project_id)
    task, owner, branch = PMSTask.__table__, PackRecordOwnership.__table__, BranchOwnership.__table__
    if not db.connection().scalar(select(exists().where(task.c.id == task_id, task.c.project_id == project_id,
            task.c.deleted_at.is_(None), exists().where(owner.c.resource_table == task.name,
                owner.c.resource_key == str(task_id), owner.c.company_id == scope.company_id,
                owner.c.branch_id == scope.branch_id, owner.c.context_id == scope.context_id),
            exists().where(branch.c.resource_table == task.name, branch.c.resource_key == str(task_id),
                branch.c.company_id == scope.company_id, branch.c.branch_id == scope.branch_id)))):
        service.fail('An explicitly owned canonical delivery task is required', 404)
    return scope


def storage_epoch(db, scope):
    from app.core.config import settings
    policy, connection = StoragePolicy.__table__, StorageConnection.__table__
    row = db.connection().execute(select(policy).where(policy.c.organization_id == scope.company_id)).mappings().first()
    route = ((row['routes'] or {}).get('pms') or (row['routes'] or {}).get('default')) if row and row['enabled'] else None
    ident = route.get('connection_id') if isinstance(route, dict) else None
    selected = db.connection().execute(select(connection.c.id, connection.c.organization_id,
        connection.c.provider, connection.c.connected, connection.c.created_by).where(
        connection.c.organization_id == scope.company_id, connection.c.id == ident)).first() if ident is not None else None
    return (dict(row) if row else None, tuple(selected) if selected else None,
        settings.STORAGE_BACKEND, settings.PMS_GOOGLE_DRIVE_REQUIRED, settings.UPLOAD_DIR), ident


class UploadCommand:
    def __init__(self, db, actor, project_id, task_id, upload, data):
        self.db, self.actor, self.project_id, self.task_id = db, actor, project_id, task_id
        self.upload, self.data = upload, data
        self.scope = task_source(db, actor, project_id, task_id)
        self.authority = _native_authority(db, actor, self.scope.company_id)
        self.storage, self.connection_id = storage_epoch(db, self.scope)
        self.minted, self.asset, self.locator = [], None, None
        self.certificate, self.result, self.verified_staging = None, None, {}

    def current(self):
        from .pms_sources import project_for_action
        if (task_source(self.db, self.actor, self.project_id, self.task_id) is not self.scope
                or _native_authority(self.db, self.actor, self.scope.company_id) != self.authority
                or storage_epoch(self.db, self.scope)[0] != self.storage):
            service.fail('Native upload authority or storage route changed')
        project_for_action(self.db, self.actor, self.project_id, 'upload')

    def criteria(self):
        return {
            PMSTask: and_(PMSTask.id == self.task_id, PMSTask.project_id == self.project_id, PMSTask.deleted_at.is_(None)),
            StoragePolicy: StoragePolicy.organization_id == self.scope.company_id,
            StorageConnection: and_(StorageConnection.id == self.connection_id, StorageConnection.organization_id == self.scope.company_id),
            StorageObject: and_(StorageObject.organization_id == self.scope.company_id,
                StorageObject.id == bindparam('accounts_new_locator', callable_=lambda: self.locator.id if self.locator else -1, unique=True)),
        }

    def quota_query(self, native):
        return str(native.query(func.coalesce(func.sum(StorageObject.size), 0)).filter_by(
            organization_id=self.scope.company_id).statement.compile(compile_kwargs={'literal_binds': True}))

    def path(self, value):
        from app.apps.project_management.api.router import PMS_UPLOAD_ROOT
        path = Path(value).resolve()
        directory = (PMS_UPLOAD_ROOT / 'tasks' / str(self.task_id)).resolve()
        if path.parent != directory or not path.is_file() or path.stat().st_size != self.data.size_bytes:
            service.fail('Native upload staging differs from its exact task/input', 409)
        from app.apps.project_management.api.router import _safe_attachment_name
        prefix, _, suffix = path.name.partition('_')
        if len(prefix) != 32 or any(c not in '0123456789abcdef' for c in prefix) or suffix != _safe_attachment_name(self.upload.filename):
            service.fail('Native upload requires its newly generated staging identity', 409)
        if sha256(path.read_bytes()).hexdigest() != self.data.sha256:
            service.fail('Native upload content changed', 409)
        return path

    def validate(self, session, *args):
        self.current()
        if session.deleted:
            service.fail('Native attachment creation cannot delete records')
        for row in session.dirty:
            if row is self.locator:
                self.validate_locator(row)
            elif type(row) is StorageConnection and row.id == self.connection_id:
                if any(attr.history.has_changes() and name not in {'encrypted_value', 'expires_at'}
                        for name, attr in inspect(row).attrs.items()):
                    service.fail('Only native token refresh may update the selected storage connection')
            else:
                service.fail('Native upload cannot alter existing business records')
        for row in session.new:
            if row not in self.minted and row.id is not None:
                service.fail('Native attachment requires a genuinely new identity', 409)
            if type(row) is StorageObject:
                if self.locator is not None and row is not self.locator:
                    service.fail('One upload requires exactly one new native storage locator')
                self.validate_locator(row)
                self.locator = row
            elif type(row) is PMSFileAsset:
                path = self.path(row.storage_path)
                if (self.asset is not None or row.project_id != self.project_id or row.task_id != self.task_id
                        or row.uploaded_by_user_id != self.actor.id or row.file_name != path.name
                        or row.original_name != self.data.filename or row.size_bytes != self.data.size_bytes
                        or row.mime_type != self.data.content_type or row.visibility != 'Internal'
                        or row.folder_id is not None or row.milestone_id is not None or row.deleted_at is not None):
                    service.fail('Native attachment differs from the exact document upload', 409)
                self.asset = row
            elif type(row) is PMSActivity:
                if (self.asset is None or row.project_id != self.project_id or row.task_id != self.task_id
                        or row.actor_user_id != self.actor.id or row.action != 'attachment.added'
                        or row.entity_type != 'file' or row.entity_id != self.asset.id or row.sprint_id is not None):
                    service.fail('Native attachment activity requires its actual new file source', 409)
            else:
                service.fail('Unreviewed native upload write')
            if row not in self.minted:
                self.minted.append(row)

    def validate_locator(self, row):
        from app.core.config import settings
        path = self.path(Path(settings.UPLOAD_DIR) / row.relative_path)
        policy = self.storage[0]
        route = ((policy['routes'] or {}).get('pms') or (policy['routes'] or {}).get('default')) if policy and policy['enabled'] else None
        folder = route.get('folder_id') if isinstance(route, dict) else None
        providers = {settings.STORAGE_BACKEND, self.storage[1][2] if self.storage[1] else settings.STORAGE_BACKEND}
        if (row.organization_id != self.scope.company_id or row.module != 'pms'
                or row.filename != self.data.filename or row.size != self.data.size_bytes or row.sha256 != self.data.sha256
                or row.uploaded_by not in {None, self.actor.id} or row.connection_id not in {None, self.connection_id}
                or row.folder_id not in {None, folder} or row.provider not in providers
                or row.status not in {'local', 'pending', 'cloud'} or row.versions not in (None, [])):
            service.fail('Native storage locator differs from its new upload source', 409)
        if row not in self.minted and self.db.connection().scalar(select(exists().where(
                StorageObject.__table__.c.organization_id == self.scope.company_id,
                StorageObject.__table__.c.relative_path == row.relative_path))):
            service.fail('An existing storage object cannot be adopted as a new upload', 409)

    def finish(self, native, row):
        self.current()
        if self.asset is not row or row.version_number != 1 or len([x for x in self.minted if type(x) is PMSFileAsset]) != 1 or len([
                x for x in self.minted if type(x) is PMSActivity]) != 1:
            service.fail('Native upload must mint exactly one asset and activity', 409)
        for item in self.minted:
            if type(item) not in {PMSFileAsset, PMSActivity, StorageObject}:
                service.fail('Unreviewed upload provenance')
            self.db.connection().execute(BranchOwnership.__table__.insert().values(resource_table=item.__tablename__,
                resource_key=str(item.id), company_id=self.scope.company_id, branch_id=self.scope.branch_id, source='accounts-upload'))
            self.db.connection().execute(PackRecordOwnership.__table__.insert().values(resource_table=item.__tablename__,
                resource_key=str(item.id), company_id=self.scope.company_id, branch_id=self.scope.branch_id,
                context_id=self.scope.context_id, source='accounts-upload', revision=1))
        pending = native.info.pop('verified_cloud_staging', {})
        for name, digest in pending.items():
            if Path(name).resolve() != Path(row.storage_path).resolve() or digest != self.data.sha256:
                service.fail('Cloud staging must belong to this exact new attachment', 409)
        # The original Session's after_commit hook also runs on savepoint
        # release. Queue this only after the Accounts savepoint has released.
        self.verified_staging = pending
        return {'file_id': row.id, 'project_id': self.project_id, 'name': row.original_name,
            'size_bytes': row.size_bytes, 'version_number': row.version_number}
