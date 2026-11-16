"""Public native PMS upload defaults remain intact without a selected pack."""
from pathlib import Path

from app.apps.project_management.models import PMSFileAsset
from app.models.file_storage import StorageObject
from tests.test_industry_operations import business, directory_identity


def test_legacy_native_project_upload_download_and_failed_retry(client, db, business, monkeypatch, tmp_path):
    from app.core.config import settings
    from app.apps.project_management.api import router as pms
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    monkeypatch.setattr(settings, 'PMS_GOOGLE_DRIVE_REQUIRED', False)
    monkeypatch.setattr(pms, 'PMS_UPLOAD_ROOT', tmp_path / 'pms')
    headers, _, project, _ = business
    path = f'/api/v1/project-management/projects/{project.id}/files/upload'
    failed = client.post(path, headers=headers, files={'file': ('Legacy report.txt', b'', 'text/plain')})
    assert failed.status_code == 400, failed.text
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0
    content = b'Legacy native defaults are preserved\n'
    response = client.post(path, headers=headers, files={'file': ('Legacy report.txt', content, 'text/plain')})
    assert response.status_code == 201, response.text
    row = response.json()
    assert row['project_id'] == project.id and row['storage_path'] != '[private]'
    assert Path(row['storage_path']).read_bytes() == content
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 1
    downloaded = client.get(f'/api/v1/project-management/attachments/{row["id"]}/download', headers=headers)
    assert downloaded.status_code == 200 and downloaded.content == content
