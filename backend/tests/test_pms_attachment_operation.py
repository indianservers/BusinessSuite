from io import BytesIO
from uuid import uuid4
import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers
from app.apps.project_management.models import PMSTask, PMSFileAsset
from app.core.config import settings
from tests.test_accounts_periods import accounts, scenario, catalog, directory_identity
from tests.test_accounts_actual_time import delivery
from tests.test_srm_native_transaction_operations import native_writer


@pytest.fixture
def attachment_source(db, accounts, delivery, tmp_path, monkeypatch):
    from app.apps.project_management.api import router
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    monkeypatch.setattr(settings, 'PMS_GOOGLE_DRIVE_REQUIRED', False)
    root = tmp_path / 'pms'
    root.mkdir()
    monkeypatch.setattr(router, 'PMS_UPLOAD_ROOT', root)
    with native_writer(db, accounts['manager'], accounts['branch']):
        task = PMSTask(project_id=delivery, task_key=uuid4().hex[:20], title='Canonical source task')
        db.add(task); db.commit(); ident = task.id
    return ident, root


def upload():
    return UploadFile(BytesIO(b'Actual uploaded client records'), filename='statement.txt',
        headers=Headers({'content-type': 'text/plain'}))


def test_native_attachment_commit_false_retains_caller_transaction_and_storage_staging(db, accounts, attachment_source):
    from app.apps.project_management.api.router import upload_task_attachment_operation
    task_id, root = attachment_source
    with native_writer(db, accounts['manager'], accounts['branch']):
        parent = db.connection().get_transaction()
        row = upload_task_attachment_operation(task_id, upload(), db, accounts['manager'], commit=False)
        assert type(row) is PMSFileAsset and row.project_id == db.get(PMSTask, task_id).project_id
        assert parent.is_active and db.connection().get_transaction() is parent
        assert db.query(PMSFileAsset).count() == 1
        db.rollback()
    assert db.query(PMSFileAsset).count() == 0
    # Native staging is deliberately retained for recovery; no shared object is deleted.
    assert len(list(root.rglob('*.txt'))) == 1


def test_native_attachment_public_default_still_commits_and_returns_existing_payload(db, accounts, attachment_source):
    from app.apps.project_management.api.router import upload_task_attachment_operation
    with native_writer(db, accounts['manager'], accounts['branch']):
        result = upload_task_attachment_operation(attachment_source[0], upload(), db, accounts['manager'])
        assert result['id'] == db.query(PMSFileAsset).one().id
        db.rollback()
    assert db.query(PMSFileAsset).count() == 1


def test_storage_abstraction_failure_leaves_no_attachment_and_preserves_recovery_original(db, accounts, attachment_source, monkeypatch):
    from app.apps.project_management.api.router import upload_task_attachment_operation
    from app.core import storage
    from types import SimpleNamespace
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 's3')
    def unavailable(*args, **kwargs):
        raise RuntimeError('Injected S3 upload failure')
    monkeypatch.setattr(storage, 's3_client', lambda: SimpleNamespace(upload_file=unavailable))
    with native_writer(db, accounts['manager'], accounts['branch']):
        parent = db.connection().get_transaction()
        with pytest.raises(RuntimeError, match='Injected S3'):
            upload_task_attachment_operation(attachment_source[0], upload(), db, accounts['manager'], commit=False)
        assert parent.is_active
        db.rollback()
    assert db.query(PMSFileAsset).count() == 0
    assert len(list(attachment_source[1].rglob('*.txt'))) == 1
