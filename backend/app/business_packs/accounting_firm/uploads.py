"""Atomic request/checklist provenance around one canonical native binary upload."""
from hashlib import sha256
from weakref import WeakKeyDictionary
from sqlalchemy import event, select
from . import service, documents
from .models import AccountsCommand
from .schemas import DocumentBinaryInput
from .pms_sources import upload_task, upload_task_access, file_source
from .upload_resources import UploadCommand

_UPLOADS = WeakKeyDictionary()


@event.listens_for(AccountsCommand, 'before_insert')
def certify_upload(mapper, connection, row):
    if row.action != 'document.upload':
        return
    from sqlalchemy import inspect
    db = inspect(row).session
    plan = _UPLOADS.get(db)
    if (plan is None or plan.certificate is not row or plan.result != row.result or plan.asset is None
            or row.id is not None or row.created_at is not None or row.period_id != plan.period_id
            or row.created_by != plan.actor.id or row.organization_id != plan.scope.company_id
            or row.branch_id != plan.scope.branch_id or row.pack_context_id != plan.scope.context_id):
        service.fail('A genuinely minted native Accounts document certificate is required')
    plan.current()
    from app.apps.project_management.models import PMSFileAsset
    stored = db.connection().execute(select(PMSFileAsset.__table__).where(
        PMSFileAsset.__table__.c.id == plan.asset.id)).mappings().one()
    if (stored['project_id'] != plan.project_id or stored['task_id'] != plan.task_id
            or stored['uploaded_by_user_id'] != plan.actor.id or stored['storage_path'] != plan.asset.storage_path
            or stored['size_bytes'] != plan.data.size_bytes or row.result['file']['file_id'] != stored['id']):
        service.fail('Accounts document certificate differs from its actual new native asset', 409)


def upload(ident, key, data, file, db, actor):
    from app.apps.project_management.api.router import _validate_attachment_upload, _safe_attachment_name, PMS_MAX_ATTACHMENT_BYTES
    scope = documents._access(db, actor, write=True)
    _validate_attachment_upload(file)
    digest, size = sha256(), 0
    while chunk := file.file.read(1024 * 1024):
        size += len(chunk)
        if size > PMS_MAX_ATTACHMENT_BYTES:
            service.fail('Attachment exceeds the configured size limit', 413)
        digest.update(chunk)
    file.file.seek(0)
    if not size:
        service.fail('Attachment cannot be empty', 400)
    binary = DocumentBinaryInput(**data.model_dump(), filename=_safe_attachment_name(file.filename),
        content_type=file.content_type or 'application/octet-stream', size_bytes=size, sha256=digest.hexdigest())
    service.lock_tenant(db, actor)
    documents._access(db, actor, write=True)
    period = service.record(db, actor, scope, ident)
    project_id = documents._project(db, actor, scope, period)
    upload_task_access(db, actor, project_id, data.task_id)
    current = documents._current(db, scope, ident, key)
    identity = f'{ident}:{key}'
    old = service.replay(db, actor, scope, 'document.upload', identity, binary)
    if old is not None:
        file_source(db, actor, project_id, old['file']['file_id'])
        return old
    service.source(db, actor, scope, period.engagement_id, period.client_id, require_open=True)
    if period.state not in {'draft', 'returned'}:
        service.fail('Reopen preparation before uploading submitted documents', 409)
    if period.revision != data.expected_revision or current['revision'] != data.expected_document_revision:
        service.fail('Document request changed; reload before uploading', 409)
    if db in _UPLOADS:
        service.fail('Native document upload commands cannot nest')
    with db.begin_nested():
        plan = UploadCommand(db, actor, project_id, data.task_id, file, binary)
        plan.period_id = period.id
        _UPLOADS[db] = plan
        try:
            native_file = upload_task(db, actor, plan)
            result = current | {'status': 'uploaded', 'revision': current['revision'] + 1,
                'file': native_file, 'task_id': data.task_id, 'sha256': binary.sha256}
            plan.result = result
            certificate = AccountsCommand(**service.fields(scope, actor), period_id=period.id,
                request_key=str(data.request_key), request_sha256=service.fingerprint('document.upload', identity, binary),
                action='document.upload', reason='', result=result)
            plan.certificate = certificate
            db.add(certificate); db.flush()
            plan.current()
        finally:
            _UPLOADS.pop(db, None)
    plan.current()
    db.info.setdefault('verified_cloud_staging', {}).update(plan.verified_staging)
    db.commit()
    return result
