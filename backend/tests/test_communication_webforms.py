from tests.communication_test_utils import communication_headers
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

