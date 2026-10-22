from urllib.parse import urlsplit, parse_qs

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.storage import signed_file_url, blob_token_path, normalize_upload_references


def test_blob_links_round_trip_without_exposing_storage_credentials(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "vercel_blob")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    path = str(tmp_path / "employee_docs" / "private.pdf")
    url = signed_file_url(path)
    token = parse_qs(urlsplit(url).query)["token"][0]
    assert blob_token_path(token) == path
    assert normalize_upload_references(url) == "/uploads/employee_docs/private.pdf"
    assert "vercel_blob_rw_" not in url
    with pytest.raises(HTTPException):
        blob_token_path(token + "tampered")


@pytest.mark.parametrize("payload", [
    {"path": "private.pdf", "purpose": "blob-download", "aud": "private-file", "exp": 1},
    {"path": "../outside.pdf", "purpose": "blob-download", "aud": "private-file"},
    {"path": "private.pdf", "purpose": "access", "aud": "private-file"},
    {"path": "private.pdf", "purpose": "blob-download", "aud": "other-service"},
])
def test_blob_links_reject_expiry_traversal_and_wrong_scope(monkeypatch, tmp_path, payload):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    with pytest.raises(HTTPException):
        blob_token_path(token)
