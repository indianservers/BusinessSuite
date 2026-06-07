def test_crm_phase_2_funnel_includes_crm_and_srm_stages(client, superuser_headers):
    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Funnel Pipeline"})
    stage = client.post(f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages", headers=superuser_headers, json={"name": "Open", "probability": 30, "position": 1})
    client.post("/api/v1/crm/leads", headers=superuser_headers, json={"firstName": "Funnel", "fullName": "Funnel Lead", "status": "Qualified", "estimatedValue": 150000})
    client.post("/api/v1/crm/deals", headers=superuser_headers, json={"name": "Funnel Deal", "pipelineId": pipeline.json()["id"], "stageId": stage.json()["id"], "amount": 150000})

    response = client.get("/api/v1/crm/funnel?startDate=2026-01-01&endDate=2026-12-31", headers=superuser_headers)
    assert response.status_code == 200
    stages = [item["stage"] for item in response.json()["items"]]
    assert "Lead" in stages
    assert "SRM Sales Order" in stages
    assert "Receipt Collected" in stages
