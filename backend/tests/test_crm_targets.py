from app.apps.crm.models import CRMSalesTarget


def test_crm_phase_2_targets_and_performance(client, db, superuser_headers):
    created = client.post(
        "/api/v1/crm/targets",
        headers=superuser_headers,
        json={"periodType": "monthly", "periodStart": "2026-06-01", "periodEnd": "2026-06-30", "targetOwnerType": "user", "targetOwnerId": 1, "targetAmount": 500000, "currency": "INR"},
    )
    assert created.status_code == 201
    assert db.query(CRMSalesTarget).filter(CRMSalesTarget.id == created.json()["id"]).count() == 1

    updated = client.put(f"/api/v1/crm/targets/{created.json()['id']}", headers=superuser_headers, json={"targetAmount": 750000})
    assert updated.status_code == 200
    assert float(updated.json()["targetAmount"]) == 750000

    performance = client.get("/api/v1/crm/targets/performance?startDate=2026-06-01&endDate=2026-06-30", headers=superuser_headers)
    assert performance.status_code == 200
    assert performance.json()["items"][0]["targetAmount"] == 750000
    assert "achievementPercent" in performance.json()["items"][0]
