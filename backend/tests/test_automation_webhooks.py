from app.apps.automation.models import AutomationExecutionLog
from tests.automation_test_utils import automation_headers


def test_webhook_create_requires_https_and_test_logs_delivery(client, db):
    headers = automation_headers(client, db)
    rejected = client.post("/api/v1/automation/webhooks", headers=headers, json={"name": "Bad hook", "target_url": "http://example.com/hook"})
    assert rejected.status_code == 400

    response = client.post("/api/v1/automation/webhooks", headers=headers, json={"name": "Good hook", "target_url": "https://example.com/hook", "event_types_json": ["deal.won"]})
    assert response.status_code == 201, response.text
    response = client.post(f"/api/v1/automation/webhooks/{response.json()['id']}/test", headers=headers, json={"payload": {"event": "deal.won"}})
    assert response.status_code == 200
    assert response.json()["result_json"]["delivery"] == "logged_only"
    assert db.query(AutomationExecutionLog).count() == 1

