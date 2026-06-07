from tests.automation_test_utils import automation_headers


def test_blueprint_transition_validation_blocks_missing_required_fields(client, db):
    headers = automation_headers(client, db)
    response = client.post("/api/v1/automation/blueprints", headers=headers, json={
        "name": "Deal Blueprint",
        "module_name": "crm",
        "record_type": "deal",
        "stages": [{"stage_key": "qualified", "label": "Qualified"}, {"stage_key": "proposal", "label": "Proposal"}],
        "transitions": [{"from_stage_key": "qualified", "to_stage_key": "proposal", "required_fields": ["amount"]}],
    })
    assert response.status_code == 201, response.text
    blueprint_id = response.json()["id"]

    response = client.post(f"/api/v1/automation/blueprints/{blueprint_id}/validate-transition", headers=headers, json={"from_stage_key": "qualified", "to_stage_key": "proposal", "record": {}})
    assert response.status_code == 400
    assert "Missing required fields" in response.text

    response = client.post(f"/api/v1/automation/blueprints/{blueprint_id}/validate-transition", headers=headers, json={"from_stage_key": "qualified", "to_stage_key": "proposal", "record": {"amount": 1000}})
    assert response.status_code == 200
    assert response.json()["allowed"] is True


def test_blueprint_detail_update_stage_and_transition_apis(client, db):
    headers = automation_headers(client, db)
    response = client.post("/api/v1/automation/blueprints", headers=headers, json={
        "name": "Quote Blueprint",
        "module_name": "crm",
        "record_type": "quote",
    })
    assert response.status_code == 201, response.text
    blueprint_id = response.json()["id"]

    response = client.get(f"/api/v1/automation/blueprints/{blueprint_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Quote Blueprint"

    response = client.put(f"/api/v1/automation/blueprints/{blueprint_id}", headers=headers, json={
        "name": "Quote Approval Blueprint",
        "module_name": "crm",
        "record_type": "quote",
        "is_active": True,
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Quote Approval Blueprint"

    response = client.post(f"/api/v1/automation/blueprints/{blueprint_id}/stages", headers=headers, json={"stage_key": "draft", "label": "Draft"})
    assert response.status_code == 201, response.text
    response = client.post(f"/api/v1/automation/blueprints/{blueprint_id}/transitions", headers=headers, json={"from_stage_key": "draft", "to_stage_key": "submitted", "required_fields": ["grand_total"]})
    assert response.status_code == 201, response.text
