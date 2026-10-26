from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from scripts import check_deployment as deployment


@pytest.mark.parametrize('backend', ['s3', 'vercel_blob'])
@pytest.mark.parametrize('failure', [None, 'public_object', 'signed_download', 'cors', 'unsigned_api'])
def test_storage_readiness_uses_api_links_and_cleans_up(monkeypatch, tmp_path, backend, failure):
    monkeypatch.setattr(deployment.settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(deployment.settings, 'STORAGE_BACKEND', backend)
    monkeypatch.setattr(deployment.settings, 'FRONTEND_PUBLIC_URL', 'https://frontend.example')
    monkeypatch.setattr(deployment.settings, 'BACKEND_PUBLIC_URL', 'https://configured.example')
    payload = []
    def persist(path):
        from pathlib import Path
        payload.append(Path(path).read_bytes())
    monkeypatch.setattr(deployment, 'persist_file', persist)
    cleanup = Mock()
    s3 = SimpleNamespace(generate_presigned_url=lambda *a, **k: 'https://objects.example/probe?signature=private', delete_object=cleanup)
    monkeypatch.setattr(deployment, 's3_client', lambda: s3)
    monkeypatch.setattr(deployment, 'blob_session', nullcontext)
    import vercel.blob.sync as blob
    monkeypatch.setattr(blob, 'head_blob', lambda key: SimpleNamespace(url='https://objects.example/probe'))
    monkeypatch.setattr(blob, 'delete_blob', cleanup)
    requests = []
    def respond(request):
        requests.append(request)
        assert not list(tmp_path.rglob('*.txt')), 'Staging must be removed before download'
        if request.url.host == 'objects.example':
            assert not request.url.query
            return httpx.Response(200 if failure == 'public_object' else 403)
        assert request.url.host == 'preview.example'
        assert request.url.path == '/api/v1/files/blob'
        if 'token' not in request.url.params:
            return httpx.Response(200 if failure == 'unsigned_api' else 422)
        return httpx.Response(500 if failure == 'signed_download' else 200, content=payload[0],
            headers={} if failure == 'cors' else {'Access-Control-Allow-Origin': 'https://frontend.example'})
    original_client = httpx.Client
    monkeypatch.setattr(deployment.httpx, 'Client', lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    if failure:
        with pytest.raises(RuntimeError):
            deployment.check_storage('https://preview.example')
    else:
        deployment.check_storage('https://preview.example')
        assert len(requests) == 3
    cleanup.assert_called_once()
    assert not list(tmp_path.rglob('*.txt'))
