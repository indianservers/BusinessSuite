from tests.communication_test_utils import communication_headers
from app.apps.communication.models import CommunicationEmailTemplate, CommunicationTimelineEvent


def test_email_template_crud_and_audit_timeline(client, db):
    headers = communication_headers(client, db)
    created = client.post("/api/v1/communication/email-templates", headers=headers, json={"name": "Intro", "subject": "Hello {{name}}", "body_text": "Welcome", "module_name": "lead"}).json()
    assert created["id"]
    assert db.query(CommunicationEmailTemplate).filter_by(id=created["id"]).first()

    updated = client.put(f"/api/v1/communication/email-templates/{created['id']}", headers=headers, json={"name": "Intro Updated", "subject": "Hi", "body_text": "Updated", "module_name": "lead"}).json()
    assert updated["name"] == "Intro Updated"

    listed = client.get("/api/v1/communication/email-templates", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert db.query(CommunicationTimelineEvent).filter_by(record_type="template", record_id=created["id"]).count() >= 2

