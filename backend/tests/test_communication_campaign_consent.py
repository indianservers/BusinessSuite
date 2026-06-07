from tests.communication_test_utils import communication_headers, create_template
from app.apps.crm.models import CRMLead
from app.core.config import settings


def test_campaign_respects_opt_out(client, db, monkeypatch):
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "stub")
    headers = communication_headers(client, db)
    db.add(CRMLead(first_name="No", last_name="Mail", full_name="No Mail", email="nomail@example.com", status="New"))
    db.commit()
    client.post("/api/v1/communication/opt-out", headers=headers, json={"email": "nomail@example.com", "channel": "email"})
    template = create_template(client, headers)
    campaign = client.post("/api/v1/communication/campaigns", headers=headers, json={"name": "Consent Campaign", "type": "email", "template_id": template["id"], "segment_json": {"source": "lead", "status": "New", "limit": 10}}).json()

    preview = client.post(f"/api/v1/communication/campaigns/{campaign['id']}/preview", headers=headers).json()
    assert any(item["email"] == "nomail@example.com" and item["blocked"] for item in preview["recipients"])

    sent = client.post(f"/api/v1/communication/campaigns/{campaign['id']}/send", headers=headers).json()
    assert sent["blocked_count"] >= 1

