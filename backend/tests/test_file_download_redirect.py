import pytest

from app.core import storage
from app.core.config import settings


@pytest.mark.parametrize("cloud_locator", [False, True])
def test_private_download_redirect_preserves_request_origin(monkeypatch, cloud_locator):
    from types import SimpleNamespace
    from app.services import file_storage

    monkeypatch.setattr(settings, "BACKEND_PUBLIC_URL", "http://localhost:1534")
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "vercel_blob")
    monkeypatch.setattr(file_storage, "locator", lambda path: SimpleNamespace(status="cloud") if cloud_locator else None)
    monkeypatch.setattr(storage, "signed_file_url", lambda path: "http://localhost:1534/api/v1/files/blob?token=private-signed-value")
    response = storage.FileResponse("/uploads/example.txt")
    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/files/blob?token=private-signed-value"
    assert response.headers["cache-control"] == "private, no-store"


def test_provider_download_signature_is_not_rewritten(monkeypatch):
    monkeypatch.setattr(settings, "BACKEND_PUBLIC_URL", "https://api.example.test")
    signed = "https://bucket.example.test/private.txt?X-Amz-Signature=signature&X-Amz-Expires=60"
    monkeypatch.setattr(storage, "signed_file_url", lambda path: signed)
    assert storage._download_redirect("/uploads/example.txt").headers["location"] == signed
