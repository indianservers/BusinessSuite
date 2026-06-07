from app.apps.saas.models import DeveloperWebhook, DeveloperWebhookDelivery
from phase10_test_utils import auth_headers


def test_developer_webhook_requires_https_and_supports_test_replay(client, db):
    headers = auth_headers(client, db, permissions=["developer_manage"])
    bad = client.post("/api/v1/developer/webhooks", json={"name": "Bad", "target_url": "http://localhost/hook", "events": ["lead.created"]}, headers=headers)
    assert bad.status_code == 422

    create = client.post("/api/v1/developer/webhooks", json={"name": "Good", "target_url": "https://example.com/hook", "events": ["lead.created"], "secret": "shared"}, headers=headers)
    assert create.status_code == 201, create.text
    webhook_id = create.json()["id"]
    assert db.query(DeveloperWebhook).first().secret_hash

    test = client.post(f"/api/v1/developer/webhooks/{webhook_id}/test", headers=headers)
    replay = client.post(f"/api/v1/developer/webhooks/{webhook_id}/replay", headers=headers)
    assert test.status_code == replay.status_code == 201
    assert db.query(DeveloperWebhookDelivery).count() == 2
