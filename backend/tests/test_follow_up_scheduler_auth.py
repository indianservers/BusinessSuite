from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import scheduled_jobs
from app.core.deps import get_db
from app.core.route_policy import enforce_private_defaults, is_public


def test_follow_up_scheduler_accepts_only_cron_secret_without_user_session(monkeypatch):
    from app.shared import follow_ups

    calls = []
    monkeypatch.setattr(scheduled_jobs.settings, "CRON_SECRET", "scheduler-regression-secret")
    monkeypatch.setattr(follow_ups, "dispatch", lambda db: calls.append(db))
    app = FastAPI()
    app.include_router(scheduled_jobs.router, prefix="/api/v1")
    enforce_private_defaults(app.router)
    app.dependency_overrides[get_db] = lambda: None
    client = TestClient(app)
    path = "/api/v1/internal/service-follow-up-reminders"

    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert calls == []
    response = client.get(path, headers={"Authorization": "Bearer scheduler-regression-secret"})
    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    assert response.headers["cache-control"] == "no-store"
    assert calls == [None]
    assert not is_public(path + "/extra")
    assert not is_public("/api/v1/internal/jobs")
