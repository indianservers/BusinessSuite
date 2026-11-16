"""Native project uploads/downloads retain selected Construction source ownership."""
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.apps.project_management.models import PMSFileAsset, PMSActivity, PMSProject, PMSFileFolder
from app.business_packs.models import PackRecordOwnership, PackUserGrant
from app.models.file_storage import StorageObject
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity


@pytest.fixture
def documents(construction, catalog, monkeypatch, tmp_path):
    from app.core.config import settings
    from app.apps.project_management.api import router as pms
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    monkeypatch.setattr(settings, 'PMS_GOOGLE_DRIVE_REQUIRED', False)
    monkeypatch.setattr(pms, 'PMS_UPLOAD_ROOT', tmp_path / 'pms')
    actor, branch, context_id, project = construction
    return {'actor': actor, 'branch': branch, 'context': context_id, 'project': project,
        'root': tmp_path, 'headers': {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}}


def upload(client, case, content=b'Native site report\n', content_type='text/plain', *, project=None, headers=None, status=201, folder=None):
    response = client.post(f'/api/v1/project-management/projects/{project or case["project"]}/files/upload',
        headers=headers or case['headers'], files={'file': ('Site report.txt', content, content_type)},
        data={'folder_id': str(folder)} if folder else {})
    assert response.status_code == status, response.text
    return response


def test_native_project_upload_roundtrip_and_diary_attachment(client, db, documents):
    case = documents
    content = b'Construction evidence: actual native bytes\n'
    row = upload(client, case, content).json()
    assert row['project_id'] == case['project'] and row['task_id'] is None
    assert row['storage_path'] == '[private]'
    asset = db.get(PMSFileAsset, row['id'])
    assert Path(asset.storage_path).read_bytes() == content
    locator = db.query(StorageObject).one()
    assert locator.size == len(content) and locator.sha256 == sha256(content).hexdigest()
    for model, identity in ((PMSFileAsset, asset.id), (StorageObject, locator.id)):
        owner = db.query(PackRecordOwnership).filter_by(resource_table=model.__tablename__, resource_key=str(identity)).one()
        assert (owner.company_id, owner.branch_id, owner.context_id) == (1, case['branch'], case['context'])
    listing = client.get('/api/v1/project-management/files', headers=case['headers'], params={'project_id': case['project']})
    assert listing.status_code == 200, listing.text
    assert [r['id'] for r in listing.json()] == [asset.id]
    downloaded = client.get(f'/api/v1/project-management/attachments/{asset.id}/download', headers=case['headers'])
    assert downloaded.status_code == 200 and downloaded.content == content, downloaded.text
    assert 'Site' in downloaded.headers['content-disposition']
    diary = client.post('/api/v1/srm/industry/site-diaries', headers=case['headers'], json={
        'request_id': str(uuid4()), 'title': 'Native uploaded evidence', 'project_id': case['project'],
        'entry_date': '2026-11-16', 'work_done': 'Site survey', 'workforce': 7, 'file_ids': [asset.id]})
    assert diary.status_code == 201, diary.text
    assert diary.json()['data']['file_ids'] == [asset.id]
    projects = client.get('/api/v1/srm/industry/project-options', headers=case['headers'], params={'files_project_id': case['project']})
    assert projects.status_code == 200, projects.text
    assert projects.json()['items'] == [{'id': case['project'], 'name': 'Private site', 'can_upload_files': True}]


@pytest.mark.parametrize('content,mime,status', [(b'', 'text/plain', 400), (b'<script/>', 'text/html', 400)])
def test_invalid_native_upload_mints_no_document_or_locator(client, db, documents, content, mime, status):
    upload(client, documents, content, mime, status=status)
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0
    assert not list(documents['root'].rglob('*Site report*'))


def test_native_upload_late_failure_rolls_back_then_retry(client, db, documents, monkeypatch):
    from app.business_packs import construction_documents as native
    original = native._Upload.finish
    def fail_after_birth(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('Construction attachment late failure')
    with monkeypatch.context() as fault:
        fault.setattr(native._Upload, 'finish', fail_after_birth)
        with pytest.raises(RuntimeError, match='Construction attachment late failure'):
            upload(client, documents)
    db.expire_all()
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0
    assert db.query(PMSActivity).filter_by(action='attachment.added').count() == 0
    assert db.query(PackRecordOwnership).filter(PackRecordOwnership.resource_table.in_(
        (PMSFileAsset.__tablename__, StorageObject.__tablename__, PMSActivity.__tablename__))).count() == 0
    row = upload(client, documents).json()
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 1
    response = client.get(f'/api/v1/project-management/attachments/{row["id"]}/download', headers=documents['headers'])
    assert response.status_code == 200 and response.content == b'Native site report\n'


def test_unowned_foreign_private_deleted_and_missing_file_denied(client, db, documents):
    case = documents
    row = upload(client, case).json()
    asset = db.get(PMSFileAsset, row['id'])
    other = PMSProject(organization_id=1, branch_id=case['branch'], name='Foreign documents',
        project_key=uuid4().hex[:16], manager_user_id=case['actor'].id)
    db.add(other); db.flush()
    folder = PMSFileFolder(project_id=other.id, name='Foreign folder')
    db.add(folder); db.commit()
    upload(client, case, project=other.id, status=404)
    upload(client, case, folder=folder.id, status=404)
    for route in ('files', 'file-folders'):
        response = client.get('/api/v1/project-management/' + route, headers=case['headers'], params={'project_id': other.id})
        assert response.status_code == 404, response.text
    projects = client.get('/api/v1/srm/industry/project-options', headers=case['headers'], params={'files_project_id': other.id})
    assert projects.status_code == 404, projects.text
    asset.project_id = other.id; db.commit()
    response = client.get(f'/api/v1/project-management/attachments/{asset.id}/download', headers=case['headers'])
    assert response.status_code == 404, response.text
    asset.project_id = case['project']; db.commit()
    Path(asset.storage_path).unlink()
    response = client.get(f'/api/v1/project-management/attachments/{asset.id}/download', headers=case['headers'])
    assert response.status_code == 404, response.text


def test_private_evidence_and_deleted_file_keep_native_access_rules(client, db, documents):
    from datetime import datetime, timezone
    from tests.test_construction_site_workflows import native_member
    case = documents
    row = upload(client, case).json()
    asset = db.get(PMSFileAsset, row['id'])
    asset.visibility = 'Work Evidence'; db.commit()
    headers, actor = native_member(db, case['branch'], case['context'], case['project'], 'Viewer')
    response = client.get(f'/api/v1/project-management/attachments/{asset.id}/download', headers=headers)
    assert response.status_code == 403, response.text
    listing = client.get('/api/v1/project-management/files', headers=headers, params={'project_id': case['project']})
    assert listing.status_code == 200 and listing.json() == [], listing.text
    # The real uploader retains native evidence access.
    response = client.get(f'/api/v1/project-management/attachments/{asset.id}/download', headers=case['headers'])
    assert response.status_code == 200, response.text
    asset.deleted_at = datetime.now(timezone.utc); db.commit()
    response = client.get(f'/api/v1/project-management/attachments/{asset.id}/download', headers=case['headers'])
    assert response.status_code == 404, response.text


@pytest.mark.parametrize('field', ['storage_path', 'size_bytes', 'original_name'])
def test_immutable_document_source_cannot_be_retargeted(client, db, documents, field):
    case = documents
    first = upload(client, case, b'Actual first document').json()
    second = upload(client, case, b'Actual second document').json()
    asset, target = db.get(PMSFileAsset, first['id']), db.get(PMSFileAsset, second['id'])
    setattr(asset, field, getattr(target, field) if field != 'original_name' else 'Injected name.txt')
    db.commit()
    response = client.get(f'/api/v1/project-management/attachments/{asset.id}/download', headers=case['headers'])
    assert response.status_code == 409, response.text


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_same_actor_specialist_context_cannot_upload_or_download(client, db, documents, pack, role):
    from tests.test_business_pack_http_integration import grant
    case = documents
    row = upload(client, case).json()
    selected, _ = grant(db, case['actor'], case['branch'], pack, role)
    headers = {**case['headers'], 'X-Suite-Pack-Context': str(selected.id)}
    upload(client, case, headers=headers, status=403)
    projects = client.get('/api/v1/srm/industry/project-options', headers=headers, params={'files_project_id': case['project']})
    assert projects.status_code == 403, projects.text
    response = client.get(f'/api/v1/project-management/attachments/{row["id"]}/download', headers=headers)
    assert response.status_code == 403, response.text
    assert db.query(PMSFileAsset).count() == 1


def test_drive_requirement_is_not_disabled_by_construction_upload(client, db, documents, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'PMS_GOOGLE_DRIVE_REQUIRED', True)
    upload(client, documents, status=409)
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0


def test_upload_preserves_native_project_permission_denial(client, db, documents):
    from tests.test_construction_site_workflows import native_member
    case = documents
    headers, actor = native_member(db, case['branch'], case['context'], case['project'], 'Viewer')
    assert not actor.is_superuser
    projects = client.get('/api/v1/srm/industry/project-options', headers=headers, params={'files_project_id': case['project']})
    assert projects.status_code == 200, projects.text
    assert projects.json()['items'] == [{'id': case['project'], 'name': 'Private site', 'can_upload_files': False}]
    upload(client, case, headers=headers, status=403)
    assert db.query(PMSFileAsset).count() == 0


def test_native_manager_module_view_only_cannot_use_upload_command(client, db, documents):
    from tests.test_construction_site_workflows import native_member
    from tests.test_srm_native_transaction_operations import native_writer
    from app.access.models import AccessPolicy
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.business_packs import construction_documents as native
    from starlette.datastructures import UploadFile, Headers
    from io import BytesIO
    from fastapi import HTTPException
    case = documents
    headers, actor = native_member(db, case['branch'], case['context'], case['project'], 'Manager')
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {**policy.grants, 'project_management': {**policy.grants['project_management'], 'actions': ['view']}}
    db.commit()
    upload(client, case, headers=headers, status=403)
    with native_writer(db, actor, case['branch']):
        scope = resolve_context(db, actor, db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            file = UploadFile(filename='View only.txt', file=BytesIO(b'Native upload denied'), headers=Headers({'content-type': 'text/plain'}))
            with pytest.raises(HTTPException) as error:
                native.upload(db, actor, case['project'], file)
            assert error.value.status_code == 403
        finally:
            cleanup()
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0


def test_file_project_metadata_requires_selected_construction_context(client, db, documents):
    from app.models.company import Branch
    legacy = Branch(company_id=1, name='Native branch without Construction', code='NO-CONSTRUCTION', is_active=True)
    db.add(legacy); db.commit()
    headers = {key: value for key, value in documents['headers'].items() if key != 'X-Suite-Pack-Context'}
    headers['X-Suite-Branch'] = str(legacy.id)
    response = client.get('/api/v1/srm/industry/project-options', headers=headers, params={'files_project_id': documents['project']})
    assert response.status_code == 403, response.text


def cloud_route(db, case, monkeypatch, content):
    from app.core.config import settings
    from app.models.file_storage import StorageConnection, StoragePolicy
    from app.services import file_storage_providers as providers
    connection = StorageConnection(organization_id=1, provider='google_drive', label='Owned test Drive',
        connected=True, created_by=case['actor'].id)
    db.add(connection); db.flush()
    db.add(StoragePolicy(organization_id=1, enabled=True, routes={'pms': {'connection_id': connection.id, 'folder_id': 'owned-test-folder'}}))
    db.commit()
    monkeypatch.setattr(settings, 'PMS_GOOGLE_DRIVE_REQUIRED', True)
    monkeypatch.setattr(providers, 'upload', lambda *args, **kwargs: 'verified-test-object')
    monkeypatch.setattr(providers, 'download', lambda *args, **kwargs: content)
    return connection


def test_verified_cloud_staging_survives_private_savepoints_until_root_commit(client, db, documents, monkeypatch):
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app.business_packs import construction_documents as native
    content = b'Verified cloud site document\n'
    cloud_route(db, documents, monkeypatch, content)
    paths, observed = [], []
    original = native._Upload.finish
    def finish(command, session, row):
        result = original(command, session, row)
        paths.append(Path(row.storage_path))
        assert paths[-1].is_file()
        assert command.staging and 'verified_cloud_staging' not in session.info
        return result
    def after_commit(session):
        if paths:
            observed.append(('private' if session is not db else 'nested' if session.in_nested_transaction() else 'root', paths[-1].is_file()))
    monkeypatch.setattr(native._Upload, 'finish', finish)
    event.listen(Session, 'after_commit', after_commit)
    try:
        row = upload(client, documents, content).json()
    finally:
        event.remove(Session, 'after_commit', after_commit)
    assert ('private', True) in observed and ('nested', True) in observed
    assert ('root', False) in observed
    assert not paths[0].exists()
    assert db.query(StorageObject).one().status == 'cloud'
    # Selected Construction returns verified bytes, never a pack-unbound token.
    response = client.get(f'/api/v1/project-management/attachments/{row["id"]}/download', headers=documents['headers'], follow_redirects=False)
    assert response.status_code == 200 and response.content == content, response.text
    assert 'location' not in response.headers
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['content-security-policy'] == 'sandbox'


def test_verified_cloud_late_failure_keeps_staging_and_rolls_back_locators(client, db, documents, monkeypatch):
    from app.business_packs import construction_documents as native
    content = b'Recoverable cloud original\n'
    cloud_route(db, documents, monkeypatch, content)
    paths = []
    original = native._Upload.finish
    def fail(command, session, row):
        original(command, session, row)
        paths.append(Path(row.storage_path))
        raise RuntimeError('Verified cloud late failure')
    with monkeypatch.context() as fault:
        fault.setattr(native._Upload, 'finish', fail)
        with pytest.raises(RuntimeError, match='Verified cloud late failure'):
            upload(client, documents, content)
    assert paths[0].read_bytes() == content
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0
    upload(client, documents, content)
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 1
    assert paths[0].is_file(), 'Rollback original is retained for recovery, never deleted by a later upload'


def test_cloud_download_token_refresh_checksum_and_grant_revocation(client, db, documents, monkeypatch):
    from app.services import file_storage_providers as providers
    from app.models.file_storage import StorageConnection
    content = b'Verified direct Construction bytes\n'
    connection = cloud_route(db, documents, monkeypatch, content)
    ident = connection.id
    row = upload(client, documents, content).json()
    def refresh_and_download(native, account, remote_id):
        account.encrypted_value = 'test-only-rotated-native-token'
        native.flush()
        return content
    monkeypatch.setattr(providers, 'download', refresh_and_download)
    response = client.get(f'/api/v1/project-management/attachments/{row["id"]}/download', headers=documents['headers'], follow_redirects=False)
    assert response.status_code == 200 and response.content == content, response.text
    assert 'location' not in response.headers
    db.expire_all()
    assert db.get(StorageConnection, ident).encrypted_value == 'test-only-rotated-native-token'
    monkeypatch.setattr(providers, 'download', lambda *args, **kwargs: b'Changed cloud content')
    response = client.get(f'/api/v1/project-management/attachments/{row["id"]}/download', headers=documents['headers'], follow_redirects=False)
    assert response.status_code == 409 and response.content != content, response.text
    selected = db.query(PackUserGrant).filter_by(context_id=documents['context'], user_id=documents['actor'].id).one()
    selected.active = False; db.commit()
    response = client.get(f'/api/v1/project-management/attachments/{row["id"]}/download', headers=documents['headers'], follow_redirects=False)
    assert response.status_code == 403 and 'location' not in response.headers, response.text


@pytest.mark.parametrize('revocation', ['project', 'storage', 'native_policy'])
def test_outer_savepoint_authority_revocation_prevents_commit(client, db, documents, monkeypatch, revocation):
    from sqlalchemy import event, update
    from app.access.models import AccessPolicy
    from app.models.file_storage import StoragePolicy
    from app.business_packs import construction_documents as native
    content = b'Original retained after authority revocation\n'
    cloud_route(db, documents, monkeypatch, content)
    connection, paths, revoked = db.connection(), [], []
    original = native._Upload.finish
    def finish(command, session, row):
        result = original(command, session, row)
        paths.append(Path(row.storage_path))
        return result
    def after_commit(session):
        if session is db and session.in_nested_transaction() and paths and not revoked:
            revoked.append(True)
            if revocation == 'project':
                table = PMSProject.__table__
                connection.execute(update(table).where(table.c.id == documents['project']).values(manager_user_id=None))
            elif revocation == 'storage':
                table = StoragePolicy.__table__
                connection.execute(update(table).where(table.c.organization_id == 1).values(enabled=False))
            else:
                from app.models.user import User
                table = User.__table__
                connection.execute(update(table).where(table.c.id == documents['actor'].id).values(is_active=False))
    monkeypatch.setattr(native._Upload, 'finish', finish)
    event.listen(db, 'after_commit', after_commit)
    try:
        upload(client, documents, content, status=403)
    finally:
        event.remove(db, 'after_commit', after_commit)
    assert revoked and paths[0].read_bytes() == content
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0


@pytest.mark.parametrize('attack', ['raw', 'mixed', 'commit', 'connection'])
def test_closed_document_resource_rejects_unreviewed_session_use(client, db, documents, monkeypatch, attack):
    from fastapi import HTTPException
    from sqlalchemy import text
    from app.apps.project_management import file_workspace
    from app.models.employee import Employee
    original = file_workspace.upload_project_file_operation
    def hostile(project_id, file, folder_id, native, actor, **kwargs):
        if attack == 'raw':
            native.execute(text('SELECT 1'))
        elif attack == 'mixed':
            native.query(PMSProject, Employee).all()
        elif attack == 'commit':
            native.commit()
        else:
            native.connection().execute(text('SELECT 1'))
        return original(project_id, file, folder_id, native, actor, **kwargs)
    monkeypatch.setattr(file_workspace, 'upload_project_file_operation', hostile)
    upload(client, documents, status=403)
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0
