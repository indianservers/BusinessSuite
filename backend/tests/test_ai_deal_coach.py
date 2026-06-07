from ai_test_utils import auth_headers, create_mock_provider


def test_ai_deal_coach_returns_evidence_confidence(client, db):
    headers, _ = auth_headers(client, db)
    create_mock_provider(client, headers)
    response = client.post("/api/v1/ai/deal-coach", headers=headers, json={"module_name": "crm", "record_type": "deal", "data": {"stage": "Proposal"}})
    assert response.status_code == 200, response.text
    assert response.json()["confidence"] > 0

