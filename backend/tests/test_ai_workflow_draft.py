from ai_test_utils import auth_headers, create_mock_provider


def test_ai_workflow_draft_does_not_auto_activate(client, db):
    headers, _ = auth_headers(client, db)
    create_mock_provider(client, headers)
    response = client.post("/api/v1/ai/workflow-draft", headers=headers, json={"module_name": "analytics", "record_type": "report", "prompt": "Create reminder workflow"})
    assert response.status_code == 200, response.text
    assert response.json()["auto_activated"] is False
    assert response.json()["output"]["workflow_json"]["active"] is False

