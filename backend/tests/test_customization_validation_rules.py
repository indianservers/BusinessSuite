from tests.customization_test_utils import customization_headers


def test_validation_rule_create_and_test(client, db):
    headers = customization_headers(client, db)
    response = client.post("/api/v1/customization/validation-rules", headers=headers, json={"module_name": "partner_projects", "name": "Budget positive", "condition_json": {"field": "budget", "operator": "less_or_equal", "value": 0}, "error_message": "Budget must be positive"})
    assert response.status_code == 201, response.text
    response = client.post(f"/api/v1/customization/validation-rules/{response.json()['id']}/test", headers=headers, json={"record": {"budget": 0}})
    assert response.status_code == 200
    assert response.json()["triggered"] is True

