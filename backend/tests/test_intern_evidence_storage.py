from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.private_uploads import ProtectedUploads
import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['\\\\untrusted.invalid\\share', 'C:/Windows/file', '//untrusted.invalid/share'])
async def test_windows_network_paths_rejected_before_filesystem_resolution(tmp_path, monkeypatch, path):
    from fastapi.staticfiles import StaticFiles
    async def must_not_resolve(*args, **kwargs):
        raise AssertionError('Filesystem resolution must not happen')
    monkeypatch.setattr(StaticFiles, 'get_response', must_not_resolve)
    with pytest.raises(HTTPException) as exc:
        await ProtectedUploads(directory=str(tmp_path)).get_response(path,{})
    assert exc.value.status_code==404


def test_public_upload_mount_never_serves_private_pms_evidence(tmp_path):
    for directory in ['pms/work/1','pms/legacy','_private','employee_docs','resumes','documents','certificates','certificate_imports','avatars']:
        target=tmp_path/directory;target.mkdir(parents=True)
        (target/'known-file.txt').write_text('evidence',encoding='utf-8')
    app=FastAPI();app.mount('/uploads',ProtectedUploads(directory=str(tmp_path)))
    with TestClient(app) as client:
        for path in ['pms/work/1','pms/legacy','_private','PMS/WORK/1','employee_docs','resumes','documents','certificates','certificate_imports']:
            assert client.get('/uploads/'+path+'/known-file.txt').status_code==404
        assert client.get('/uploads/avatars/known-file.txt').status_code==404
