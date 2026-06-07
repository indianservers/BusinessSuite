from tests.automation_test_utils import automation_headers


def test_invalid_action_and_arbitrary_webhook_url_are_rejected(client, db):
    headers = automation_headers(client, db)
    response = client.post("/api/v1/automation/workflows", headers=headers, json={
        "name": "Unsafe action",
        "module_name": "crm",
        "record_type": "lead",
        "trigger_type": "created",
        "conditions": [],
        "actions": [{"type": "run_python", "code": "print(1)"}],
    })
    assert response.status_code == 400
    assert "Unsupported action type" in response.text

    response = client.post("/api/v1/automation/workflows", headers=headers, json={
        "name": "URL injection",
        "module_name": "crm",
        "record_type": "lead",
        "trigger_type": "created",
        "conditions": [],
        "actions": [{"type": "call_webhook", "webhook_endpoint_id": 1, "target_url": "https://attacker.example"}],
    })
    assert response.status_code == 400
    assert "Arbitrary webhook URLs" in response.text

