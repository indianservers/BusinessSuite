from ai_test_utils import auth_headers, create_mock_provider
from app.apps.ai_copilot.models import AIScore


def test_ai_lead_score_creates_score_row(client, db):
    headers, _ = auth_headers(client, db)
    create_mock_provider(client, headers)
    response = client.post("/api/v1/ai/lead-score", headers=headers, json={"module_name": "crm", "record_type": "lead", "data": {"source": "Website"}})
    assert response.status_code == 200, response.text
    assert response.json()["output"]["score"] == 78
    assert db.query(AIScore).count() == 1

