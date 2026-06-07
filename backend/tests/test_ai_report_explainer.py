from ai_test_utils import auth_headers, create_mock_provider


def test_ai_report_explainer_uses_analytics_permission(client, db):
    headers, _ = auth_headers(client, db)
    create_mock_provider(client, headers)
    response = client.post("/api/v1/ai/report-explain", headers=headers, json={"module_name": "analytics", "record_type": "report", "data": {"metric": "forecast"}})
    assert response.status_code == 200, response.text
    assert response.json()["module_name"] == "analytics"

