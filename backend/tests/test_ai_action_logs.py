from ai_test_utils import auth_headers, create_mock_provider


def test_ai_action_log_records_runs_and_provider_events(client, db):
    headers, _ = auth_headers(client, db)
    create_mock_provider(client, headers)
    client.post("/api/v1/ai/summary", headers=headers, json={"module_name": "crm", "record_type": "lead"})
    response = client.get("/api/v1/ai/action-log", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 2



def test_provider_events_have_explicit_company_ownership(client, db):
    first_headers, first = auth_headers(client, db, email='company-one-ai@example.com', company_id=1)
    create_mock_provider(client, first_headers)
    second_headers, second = auth_headers(client, db, email='company-two-ai@example.com', company_id=2)
    create_mock_provider(client, second_headers)
    for headers, user, company in [(first_headers, first, 1), (second_headers, second, 2)]:
        response = client.get('/api/v1/ai/action-log', headers=headers)
        assert response.status_code == 200, response.text
        entries = response.json()['items']
        assert entries
        assert all(item['created_by'] == user.id and item['organization_id'] == company for item in entries)
        assert any(item['event_type'] == 'ai_provider_setting_created' for item in entries)
