from tests.communication_test_utils import communication_headers


def test_sales_can_send_but_not_manage_templates(client, db):
    headers = communication_headers(client, db, "sales-comm@example.com", ["communication_view", "communication_email_send"])
    send = client.post("/api/v1/communication/emails/draft", headers=headers, json={"related_record_type": "lead", "related_record_id": 1, "to_email": "buyer@example.com", "subject": "Draft", "body": "Hello"})
    assert send.status_code == 201

    blocked = client.post("/api/v1/communication/email-templates", headers=headers, json={"name": "No", "subject": "No", "body_text": "No", "module_name": "lead"})
    assert blocked.status_code == 403


def test_non_authorized_user_blocked_from_communication(client, db):
    headers = communication_headers(client, db, "blocked-comm@example.com", [])
    response = client.get("/api/v1/communication/email-templates", headers=headers)
    assert response.status_code == 403

