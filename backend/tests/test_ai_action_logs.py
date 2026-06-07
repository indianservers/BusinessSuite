from ai_test_utils import auth_headers, create_mock_provider


def test_ai_action_log_records_runs_and_provider_events(client, db):
    headers, _ = auth_headers(client, db)
    create_mock_provider(client, headers)
    client.post("/api/v1/ai/summary", headers=headers, json={"module_name": "crm", "record_type": "lead"})
    response = client.get("/api/v1/ai/action-log", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 2

