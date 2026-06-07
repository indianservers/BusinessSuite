from tests.communication_test_utils import communication_headers, create_template
from app.apps.communication.models import CommunicationEmailMessage
from app.core.config import settings


def test_webform_auto_response_respects_provider_availability(client, db, monkeypatch):
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "")
    headers = communication_headers(client, db)
    template = create_template(client, headers)
    rule = client.post("/api/v1/communication/auto-response-rules", headers=headers, json={"name": "Reply", "template_id": template["id"], "active": True}).json()
    client.post("/api/v1/communication/webforms", headers=headers, json={"name": "Auto", "target_module": "lead", "public_slug": "auto-response", "active": True, "auto_response_rule_id": rule["id"]})

    response = client.post("/api/v1/public/webforms/auto-response/submit", json={"values": {"first_name": "Auto", "email": "auto@example.com"}, "anti_spam": ""})
    assert response.status_code == 201
    message = db.query(CommunicationEmailMessage).filter_by(to_email="auto@example.com").first()
    assert message
    assert message.status == "blocked"
    assert "No configured" in message.error_message

