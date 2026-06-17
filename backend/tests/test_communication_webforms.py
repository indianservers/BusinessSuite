from tests.communication_test_utils import communication_headers
from app.apps.communication.models import CommunicationDeliveryLog, CommunicationTimelineEvent
from app.apps.crm.models import CRMLead


def test_public_webform_submission_creates_lead_and_detects_duplicate(client, db):
    headers = communication_headers(client, db)
    created = client.post("/api/v1/communication/webforms", headers=headers, json={"name": "Lead Capture", "target_module": "lead", "public_slug": "lead-capture", "fields_json": [{"key": "email"}], "mapping_json": {"first_name": "first_name", "email": "email"}, "active": True})
    assert created.status_code == 201

    public = client.get("/api/v1/public/webforms/lead-capture")
    assert public.status_code == 200

    payload = {"values": {"first_name": "Asha", "last_name": "Buyer", "email": "asha@example.com"}, "anti_spam": ""}
    submitted = client.post("/api/v1/public/webforms/lead-capture/submit", json=payload)
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["created_record_type"] == "lead"
    assert db.query(CRMLead).filter_by(email="asha@example.com").first()

    duplicate = client.post("/api/v1/public/webforms/lead-capture/submit", json=payload)
    assert duplicate.status_code == 201
    assert duplicate.json()["duplicate_detected"] is True


def test_webform_antispam_blocks_submission(client, db):
    headers = communication_headers(client, db)
    client.post("/api/v1/communication/webforms", headers=headers, json={"name": "Spam Safe", "target_module": "lead", "public_slug": "spam-safe", "active": True})
    blocked = client.post("/api/v1/public/webforms/spam-safe/submit", json={"values": {"email": "bot@example.com"}, "anti_spam": "filled"})
    assert blocked.status_code == 400


def test_webform_auto_response_can_queue_whatsapp_placeholder(client, db):
    headers = communication_headers(client, db)
    template = client.post(
        "/api/v1/communication/whatsapp-templates",
        headers=headers,
        json={"name": "Instant Lead Reply", "template_key": "instant_lead_reply", "body_text": "Thanks {{first_name}}, we received your enquiry."},
    )
    assert template.status_code == 201, template.text
    rule = client.post(
        "/api/v1/communication/auto-response-rules",
        headers=headers,
        json={"name": "Lead WhatsApp Reply", "condition_json": {"whatsapp_template_id": template.json()["id"]}},
    )
    assert rule.status_code == 201, rule.text
    webform = client.post(
        "/api/v1/communication/webforms",
        headers=headers,
        json={
            "name": "WhatsApp Lead Capture",
            "target_module": "lead",
            "public_slug": "whatsapp-lead-capture",
            "mapping_json": {"first_name": "first_name", "email": "email", "phone": "phone"},
            "auto_response_rule_id": rule.json()["id"],
            "active": True,
        },
    )
    assert webform.status_code == 201, webform.text

    submitted = client.post(
        "/api/v1/public/webforms/whatsapp-lead-capture/submit",
        json={"values": {"first_name": "Asha", "email": "asha-wa@example.com", "phone": "+919900000001"}, "anti_spam": ""},
    )

    assert submitted.status_code == 201, submitted.text
    assert {"channel": "whatsapp", "status": "queued", "template_id": template.json()["id"]} in submitted.json()["auto_responses"]
    assert db.query(CommunicationDeliveryLog).filter_by(channel="whatsapp", status="queued").count() == 1
    assert db.query(CommunicationTimelineEvent).filter_by(channel="whatsapp", event_type="queued").count() == 1

