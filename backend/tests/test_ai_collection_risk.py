from ai_test_utils import auth_headers, create_mock_provider


def test_ai_collection_risk_requires_srm_collection_permission(client, db):
    headers, _ = auth_headers(client, db)
    create_mock_provider(client, headers)
    response = client.post("/api/v1/ai/collection-risk", headers=headers, json={"module_name": "srm", "record_type": "collection", "data": {"overdue_days": 35}})
    assert response.status_code == 200, response.text
    assert "collection risk" in response.json()["output"]["summary"].lower()

