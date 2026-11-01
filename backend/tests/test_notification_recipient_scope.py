from admin_security_test_utils import auth_headers
from app.models.user import User
from test_identity_utils import attach_test_identity


def test_sender_can_create_delivery_without_reading_recipient_inbox(client, db):
    sender = auth_headers(client, db, email="notice-sender@example.com", role_name="notice_sender", permissions=["notification_manage"])
    recipient = auth_headers(client, db, email="notice-recipient@example.com", role_name="notice_recipient", permissions=[])
    target = db.query(User).filter_by(email="notice-recipient@example.com").one()
    payload = {"user_id": target.id, "title": "Workflow update", "message": "Fixture update", "channels": ["in_app"]}
    created = client.post("/api/v1/notifications/", headers=sender, json=payload)
    assert created.status_code == 201, created.text
    notification_id = created.json()["id"]
    assert created.json()["delivery_logs"][0]["status"] == "delivered"
    assert client.get("/api/v1/notifications/", headers=sender).json()["items"] == []
    assert client.put(f"/api/v1/notifications/{notification_id}/read", headers=sender).status_code == 404
    inbox = client.get("/api/v1/notifications/", headers=recipient)
    assert any(row["id"] == notification_id for row in inbox.json()["items"])
    assert client.put(f"/api/v1/notifications/{notification_id}/read", headers=recipient).status_code == 200
    foreign = User(email="foreign-notice@example.com", hashed_password="unused", is_active=True)
    db.add(foreign)
    attach_test_identity(db, foreign, company_id=2)
    db.commit()
    assert client.post("/api/v1/notifications/", headers=sender, json={**payload, "user_id": foreign.id}).status_code == 404
