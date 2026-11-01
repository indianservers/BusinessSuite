from tests.communication_test_utils import communication_headers
from app.apps.crm.models import CRMLead
from app.apps.communication.models import CommunicationTimelineEvent, CommunicationWebform


def test_public_form_uses_its_company_and_cannot_link_foreign_rules(client, db):
    first = communication_headers(client, db, email="forms-one@example.com")
    second = communication_headers(client, db, email="forms-two@example.com", company_id=2)
    template = client.post("/api/v1/communication/whatsapp-templates", headers=second,
                           json={"name": "Reply", "template_key": "fixture_reply", "body_text": "Thanks"})
    assert template.status_code == 201, template.text
    body = {"name": "Reply rule", "condition_json": {"whatsapp_template_id": template.json()["id"]}}
    assert client.post("/api/v1/communication/auto-response-rules", headers=first, json=body).status_code == 404
    rule = client.post("/api/v1/communication/auto-response-rules", headers=second, json=body)
    assert rule.status_code == 201, rule.text
    form = {"name": "Company two form", "target_module": "lead", "public_slug": "company-two-fixture", "auto_response_rule_id": rule.json()["id"], "active": True}
    assert client.post("/api/v1/communication/webforms", headers=first, json=form).status_code == 404
    created = client.post("/api/v1/communication/webforms", headers=second, json=form)
    assert created.status_code == 201, created.text
    assert client.get("/api/v1/communication/webforms", headers=first).json()["items"] == []
    db.add(CRMLead(organization_id=1, first_name="Company One", full_name="Company One", email="shared-form@example.com", status="New"))
    db.commit()
    submitted = client.post("/api/v1/public/webforms/company-two-fixture/submit", json={"values": {"first_name": "Company Two", "email": "shared-form@example.com"}, "anti_spam": ""})
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["duplicate_detected"] is False
    lead = db.get(CRMLead, submitted.json()["created_record_id"])
    assert lead.organization_id == 2
    event = db.query(CommunicationTimelineEvent).filter_by(record_type="lead", record_id=lead.id, event_type="submitted").one()
    assert event.organization_id == 2
    db.add(CommunicationWebform(name="Unattributed", target_module="lead", public_slug="unattributed-fixture", active=True))
    db.commit()
    assert client.get("/api/v1/public/webforms/unattributed-fixture").status_code == 404
    assert client.post("/api/v1/public/webforms/unattributed-fixture/submit", json={"values": {"email": "unknown@example.com"}}).status_code == 404


def test_invalid_whatsapp_template_id_returns_validation_error(client, db):
    headers = communication_headers(client, db)
    response = client.post("/api/v1/communication/auto-response-rules", headers=headers,
                           json={"name": "Invalid rule", "condition_json": {"whatsapp_template_id": "invalid"}})
    assert response.status_code == 422, response.text
