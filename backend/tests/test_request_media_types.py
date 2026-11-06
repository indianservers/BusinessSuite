"""JSON safety limits apply to every JSON media type accepted by FastAPI."""
import pytest
from fastapi import FastAPI, Body
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.middleware.request_boundary import RequestBoundaryMiddleware


@pytest.fixture
def media_client(monkeypatch):
    monkeypatch.setattr(settings, "SECURITY_RATE_LIMIT_ENABLED", False)
    app = FastAPI()
    app.add_middleware(RequestBoundaryMiddleware)

    @app.post("/api/echo")
    def echo(payload: dict = Body(...)):
        return {"accepted": True}

    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("media_type", [
    "application/json", "application/json; charset=utf-8",
    "application/vnd.suite+json", "Application/JSON",
    "application/problem+json; charset=utf-8",
])
@pytest.mark.parametrize("body", [
    '{"value": NaN}',
    '{"value": 1e999}',
    '{"ids": [' + ','.join('1' for _ in range(settings.SECURITY_MAX_BATCH + 1)) + ']}',
    '{"value":' + '[' * (settings.SECURITY_MAX_JSON_DEPTH + 1) + '0' + ']' * (settings.SECURITY_MAX_JSON_DEPTH + 1) + '}',
], ids=["nan", "overflow", "batch", "depth"])
def test_json_media_types_enforce_safety_limits(media_client, media_type, body):
    headers = {"Content-Type": media_type} if media_type else {}
    response = media_client.post("/api/echo", content=body, headers=headers)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("media_type", ["application/json", "application/vnd.suite+json"])
def test_valid_json_media_types_remain_accepted(media_client, media_type):
    headers = {"Content-Type": media_type} if media_type else {}
    response = media_client.post("/api/echo", content='{"value": 1}', headers=headers)
    assert response.status_code == 200, response.text
