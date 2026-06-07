from app.apps.crm.models import CRMPipelineStage


def test_crm_phase_2_pipeline_stage_reorder_updates_database(client, db, superuser_headers):
    pipeline = client.post("/api/v1/crm/pipelines", headers=superuser_headers, json={"name": "Phase 2 Pipeline", "active": True})
    assert pipeline.status_code == 201
    pipeline_id = pipeline.json()["id"]
    first = client.post(f"/api/v1/crm/pipelines/{pipeline_id}/stages", headers=superuser_headers, json={"name": "Discover", "orderIndex": 1, "probability": 20})
    second = client.post(f"/api/v1/crm/pipelines/{pipeline_id}/stages", headers=superuser_headers, json={"name": "Proposal", "orderIndex": 2, "probability": 60})
    assert first.status_code == 201
    assert second.status_code == 201

    reordered = client.post(
        "/api/v1/crm/pipeline-stages/reorder",
        headers=superuser_headers,
        json={"items": [{"id": first.json()["id"], "orderIndex": 2}, {"id": second.json()["id"], "orderIndex": 1}]},
    )
    assert reordered.status_code == 200
    assert reordered.json()["total"] == 2
    db.expire_all()
    assert db.query(CRMPipelineStage).filter(CRMPipelineStage.id == first.json()["id"]).first().order_index == 2
    assert db.query(CRMPipelineStage).filter(CRMPipelineStage.id == second.json()["id"]).first().position == 1
