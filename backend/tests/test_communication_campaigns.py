from tests.communication_test_utils import communication_headers, create_template
from app.apps.crm.models import CRMLead
from app.core.config import settings


def test_campaign_preview_and_send_tracks_counts(client, db, monkeypatch):
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "stub")
    headers = communication_headers(client, db)
    db.add(CRMLead(first_name="Cam", last_name="Lead", full_name="Cam Lead", email="campaign@example.com", status="New"))
    db.commit()
    template = create_template(client, headers)
    campaign = client.post("/api/v1/communication/campaigns", headers=headers, json={"name": "June Campaign", "type": "email", "template_id": template["id"], "segment_json": {"source": "lead", "status": "New", "limit": 10}}).json()

    preview = client.post(f"/api/v1/communication/campaigns/{campaign['id']}/preview", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["total"] >= 1

    sent = client.post(f"/api/v1/communication/campaigns/{campaign['id']}/send", headers=headers)
    assert sent.status_code == 200
    assert sent.json()["status"] == "completed"
    assert sent.json()["sent_count"] >= 1

