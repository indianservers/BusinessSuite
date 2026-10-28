from tests.rich_text_test_utils import organization_context
from tests.communication_test_utils import communication_headers
from app.apps.communication.models import CommunicationDeliveryLog, CommunicationEmailMessage
from app.core.config import settings


def scoped_headers(client, db):
    from app.common.models import CommonPerson
    from app.models.user import User
    headers = communication_headers(client, db)
    user = db.query(User).filter_by(email="communication-admin@example.com").one()
    db.add(CommonPerson(user_id=user.id, organization_id=1, display_name="Communication admin"))
    db.commit()
    headers["X-Company-ID"] = "1"
    return headers


def test_email_send_blocks_when_provider_missing(client, db, monkeypatch):
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "")
    headers = scoped_headers(client, db)
    response = client.post("/api/v1/communication/emails/send", headers=headers, json={"related_record_type": "lead", "related_record_id": 1, "to_email": "lead@example.com", "subject": "Follow up", "body": "Hello"})
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "blocked"
    assert "No configured" in response.json()["error_message"]
    assert db.query(CommunicationDeliveryLog).filter_by(status="blocked").count() == 1


def test_email_send_uses_stub_provider_when_configured(client, db, monkeypatch):
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "stub")
    headers = scoped_headers(client, db)
    response = client.post("/api/v1/communication/emails/send", headers=headers, json={"related_record_type": "lead", "related_record_id": 2, "to_email": "lead2@example.com", "subject": "Follow up", "body": "Hello"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "sent"
    assert body["provider_message_id"].startswith("stub-")
    assert db.query(CommunicationEmailMessage).filter_by(id=body["id"], status="sent").first()

