from app.apps.crm.models import CRMForecastSnapshot


def test_crm_phase_2_forecast_scenarios_and_snapshot(client, db, superuser_headers):
    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Forecast Pipeline"})
    stage = client.post(f"/api/v1/crm/pipelines/{pipeline.json()['id']}/stages", headers=superuser_headers, json={"name": "Commit", "probability": 80, "position": 1})
    deal = client.post(
        "/api/v1/crm/deals",
        headers=superuser_headers,
        json={"name": "Forecast Deal", "pipelineId": pipeline.json()["id"], "stageId": stage.json()["id"], "amount": 100000, "probability": 80, "expectedCloseDate": "2026-06-15"},
    )
    assert deal.status_code == 201

    forecast = client.get("/api/v1/crm/forecast?startDate=2026-06-01&endDate=2026-06-30", headers=superuser_headers)
    assert forecast.status_code == 200
    assert forecast.json()["summary"]["pipelineAmount"] >= 100000
    assert set(forecast.json()["summary"]["scenarios"]) == {"conservative", "expected", "aggressive"}

    snapshot = client.post("/api/v1/crm/forecast/snapshot", headers=superuser_headers, json={"snapshotName": "June snapshot", "periodStart": "2026-06-01", "periodEnd": "2026-06-30"})
    assert snapshot.status_code == 201
    assert db.query(CRMForecastSnapshot).filter(CRMForecastSnapshot.snapshot_name == "June snapshot").count() == 1
