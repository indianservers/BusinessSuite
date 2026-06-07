from tests.communication_test_utils import communication_headers
from app.core.config import settings


def test_timeline_returns_email_events(client, db, monkeypatch):
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "stub")
    headers = communication_headers(client, db)
    send = client.post("/api/v1/communication/emails/send", headers=headers, json={"related_record_type": "lead", "related_record_id": 42, "to_email": "timeline@example.com", "subject": "Timeline", "body": "Hello"})
    assert send.status_code == 201

    timeline = client.get("/api/v1/communication/timeline/lead/42", headers=headers)
    assert timeline.status_code == 200
    assert timeline.json()["total"] >= 1
    assert any(item["channel"] == "email" for item in timeline.json()["items"])

