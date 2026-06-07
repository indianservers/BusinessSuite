from tests.communication_test_utils import communication_headers
from app.apps.communication.models import CommunicationDeliveryLog, CommunicationEmailMessage
from app.core.config import settings


def test_email_send_blocks_when_provider_missing(client, db, monkeypatch):
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "")
    headers = communication_headers(client, db)
    response = client.post("/api/v1/communication/emails/send", headers=headers, json={"related_record_type": "lead", "related_record_id": 1, "to_email": "lead@example.com", "subject": "Follow up", "body": "Hello"})
    assert response.status_code == 201
    assert response.json()["status"] == "blocked"
    assert "No configured" in response.json()["error_message"]
    assert db.query(CommunicationDeliveryLog).filter_by(status="blocked").count() == 1


def test_email_send_uses_stub_provider_when_configured(client, db, monkeypatch):
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "stub")
    headers = communication_headers(client, db)
    response = client.post("/api/v1/communication/emails/send", headers=headers, json={"related_record_type": "lead", "related_record_id": 2, "to_email": "lead2@example.com", "subject": "Follow up", "body": "Hello"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "sent"
    assert body["provider_message_id"].startswith("stub-")
    assert db.query(CommunicationEmailMessage).filter_by(id=body["id"], status="sent").first()

