from tests.automation_test_utils import automation_headers


def test_invalid_condition_operator_is_rejected(client, db):
    headers = automation_headers(client, db)
    response = client.post("/api/v1/automation/workflows", headers=headers, json={
        "name": "Unsafe condition",
        "module_name": "crm",
        "record_type": "lead",
        "trigger_type": "created",
        "conditions": [{"field": "email", "operator": "eval", "value": "x"}],
        "actions": [{"type": "send_notification", "title": "Notify"}],
    })
    assert response.status_code == 400
    assert "Unsupported condition operator" in response.text


def test_requested_condition_operator_vocabulary_executes(client, db):
    headers = automation_headers(client, db)
    response = client.post("/api/v1/automation/workflows", headers=headers, json={
        "name": "Requested operators",
        "module_name": "crm",
        "record_type": "deal",
        "trigger_type": "stage_changed",
        "conditions": [
            {"field": "amount", "operator": "between", "value": [1000, 5000]},
            {"field": "owner_id", "operator": "owner is", "value": 7},
            {"field": "stage", "operator": "stage is", "value": "proposal"},
            {"field": "notes", "operator": "is not empty"},
        ],
        "actions": [{"type": "send_notification", "title": "Stage automation"}],
    })
    assert response.status_code == 201, response.text
    workflow = response.json()
    assert workflow["active"] is False
    assert workflow["condition_json"][0]["operator"] == "between"

    response = client.post(f"/api/v1/automation/workflows/{workflow['id']}/test", headers=headers, json={
        "record": {"amount": 3000, "owner_id": 7, "stage": "proposal", "notes": "ready"},
        "record_id": 200,
    })
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"
