from ai_test_utils import auth_headers, create_mock_provider
from app.apps.ai_copilot.models import AIRecordSummary


def test_ai_record_summary_requires_provider_and_logs_success(client, db):
    headers, _ = auth_headers(client, db)
    blocked = client.post("/api/v1/ai/summary", headers=headers, json={"module_name": "crm", "record_type": "lead"})
    assert blocked.status_code == 409
    create_mock_provider(client, headers)
    response = client.post("/api/v1/ai/summary", headers=headers, json={"module_name": "crm", "record_type": "lead"})
    assert response.status_code == 200, response.text
    assert db.query(AIRecordSummary).count() == 1

