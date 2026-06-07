def test_crm_phase_2_lost_analysis_breaks_down_lost_reasons(client, superuser_headers):
    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Lost Pipeline"})
    stage = client.post(f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages", headers=superuser_headers, json={"name": "Lost", "probability": 0, "position": 1, "isLost": True})
    deal = client.post("/api/v1/crm/deals", headers=superuser_headers, json={"name": "Lost Deal", "pipelineId": pipeline.json()["id"], "stageId": stage.json()["id"], "amount": 90000})
    lost = client.post(f"/api/v1/crm/deals/{deal.json()['id']}/mark-lost", headers=superuser_headers, json={"lostReason": "Budget frozen"})
    assert lost.status_code == 200

    response = client.get("/api/v1/crm/lost-analysis?startDate=2026-01-01&endDate=2026-12-31", headers=superuser_headers)
    assert response.status_code == 200
    assert response.json()["summary"]["lostDeals"] >= 1
    assert any(item["reason"] == "Budget frozen" for item in response.json()["lostReasonBreakdown"])
    assert "aiPatternDetection" in response.json()["summary"]
