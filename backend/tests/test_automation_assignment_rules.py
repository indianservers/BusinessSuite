from tests.automation_test_utils import automation_headers


def test_assignment_rule_create_and_test(client, db):
    headers = automation_headers(client, db)
    response = client.post("/api/v1/automation/assignment-rules", headers=headers, json={
        "name": "Website lead assignment",
        "module_name": "crm",
        "record_type": "lead",
        "condition_json": [{"field": "source", "operator": "equals", "value": "website"}],
        "assignment_json": {"owner_strategy": "round_robin"},
    })
    assert response.status_code == 201, response.text
    response = client.post(f"/api/v1/automation/assignment-rules/{response.json()['id']}/test", headers=headers, json={"record": {"source": "website"}})
    assert response.status_code == 200
    assert response.json()["matched"] is True

