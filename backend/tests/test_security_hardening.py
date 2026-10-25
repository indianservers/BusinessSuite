from datetime import timedelta, datetime, timezone

import pytest
import jwt

from app.core.config import Settings, settings
from app.core.security import create_access_token, verify_access_token


def test_access_token_accepts_previous_secret_during_rotation(monkeypatch):
    previous_secret = "previous-secret-for-rotation"
    monkeypatch.setattr(settings, "SECRET_KEY_PREVIOUS", previous_secret)
    token = jwt.encode(
        {"sub": "1", "type": "access", "exp":datetime.now(timezone.utc)+timedelta(minutes=5)},
        previous_secret,
        algorithm=settings.ALGORITHM,
    )

    assert verify_access_token(token)["sub"] == "1"


def test_access_token_still_uses_current_secret():
    token = create_access_token(1, expires_delta=timedelta(minutes=5))

    assert verify_access_token(token)["sub"] == "1"


def test_production_cors_rejects_wildcard():
    with pytest.raises(ValueError, match="explicit origins"):
        Settings(_env_file=None,ENVIRONMENT="production", BACKEND_CORS_ORIGINS=["*"])


def test_request_id_header_is_returned(client):
    response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.headers["X-Request-ID"] == "test-request-id"


def test_production_browser_origins_require_https():
    with pytest.raises(ValueError,match='HTTPS'):
        Settings(_env_file=None,ENVIRONMENT='production',BACKEND_CORS_ORIGINS=['http://customer.example'])
