from tests.communication_test_utils import communication_headers
from app.core.config import settings
import pytest


def test_opt_out_blocks_email_send(client, db, monkeypatch):
    monkeypatch.setattr(settings, "COMMUNICATION_EMAIL_PROVIDER", "stub")
    headers = communication_headers(client, db)
    opted = client.post("/api/v1/communication/opt-out", headers=headers, json={"email": "blocked@example.com", "channel": "email", "reason": "No more"})
    assert opted.status_code == 201

    response = client.post("/api/v1/communication/emails/send", headers=headers, json={"related_record_type": "lead", "related_record_id": 1, "to_email": "blocked@example.com", "subject": "Blocked", "body": "Nope"})
    assert response.status_code == 201
    assert response.json()["status"] == "blocked"
    assert "opted out" in response.json()["error_message"]


@pytest.mark.parametrize('copy_field', ['cc', 'bcc'])
def test_opt_out_blocks_copied_recipients(client, db, monkeypatch, copy_field):
    monkeypatch.setattr(settings, 'COMMUNICATION_EMAIL_PROVIDER', 'stub')
    headers = communication_headers(client, db)
    opted = client.post('/api/v1/communication/opt-out', headers=headers,
        json={'email': 'blocked@example.com', 'channel': 'email'})
    assert opted.status_code == 201, opted.text
    response = client.post('/api/v1/communication/emails/send', headers=headers, json={
        'related_record_type': 'lead', 'related_record_id': 1,
        'to_email': 'allowed@example.com', copy_field: 'Customer <BLOCKED@example.com>',
        'subject': 'Follow up', 'body': 'Customer message'})
    assert response.status_code == 201, response.text
    assert response.json()['status'] == 'blocked'
    assert 'opted out' in response.json()['error_message']

