from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from app.apps.crm.models import CRMWebhookDelivery


@pytest.fixture
def headers(db, superuser_headers):
    from app.models.user import User
    from test_identity_utils import attach_test_identity
    attach_test_identity(db, db.query(User).filter_by(email="testadmin@test.com").one())
    db.commit()
    return superuser_headers


def test_reading_logs_never_retries_and_explicit_retry_obeys_due_time(client, db, headers, monkeypatch):
    from app.apps.crm.api import router as crm
    sent = []
    def deliver(*args, **kwargs):
        sent.append(args[0])
        return SimpleNamespace(status_code=200, text="ok")
    hook = client.post("/api/v1/crm/webhooks", headers=headers, json={"name":"Audit hook", "url":"https://example.com/audit", "events":["lead.created"], "isActive":True})
    assert hook.status_code == 201, hook.text
    identity = hook.json()["id"]
    monkeypatch.setattr(crm.httpx, "post", lambda *args, **kwargs: SimpleNamespace(status_code=503, text="unavailable"))
    response = client.post(f"/api/v1/crm/webhooks/{identity}/test", headers=headers)
    assert response.status_code == 201, response.text
    record = db.query(CRMWebhookDelivery).filter_by(id=response.json()["id"]).one()
    record.next_retry_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    monkeypatch.setattr(crm.httpx, "post", deliver)
    assert client.get(f"/api/v1/crm/webhooks/{identity}/deliveries", headers=headers).status_code == 200
    assert client.get("/api/v1/crm/webhooks", headers=headers).status_code == 200
    assert sent == []
    retry = client.post(f"/api/v1/crm/webhooks/{identity}/retry", headers=headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["retried"] == 1
    assert len(sent) == 1
    assert client.post(f"/api/v1/crm/webhooks/{identity}/retry", headers=headers).json()["retried"] == 0
    assert len(sent) == 1
    assert client.post("/api/v1/crm/webhooks/999999/retry", headers=headers).status_code == 404


def test_calendar_push_does_not_claim_unimplemented_delivery(client, headers):
    response = client.post("/api/v1/crm/calendar/webhook", headers=headers, json={"event":"changed"})
    assert response.status_code == 501
    assert "scheduled two-way sync" in response.json()["detail"]
