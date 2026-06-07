from tests.analytics_test_utils import analytics_headers, create_report
from app.apps.analytics.models import AnalyticsReport


def test_analytics_report_crud(client, db):
    headers = analytics_headers(client, db)
    report = create_report(client, headers)
    assert db.query(AnalyticsReport).filter_by(id=report["id"]).first()
    listed = client.get("/api/v1/analytics/reports", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    updated = client.put(f"/api/v1/analytics/reports/{report['id']}", headers=headers, json={"name": "Updated Pipeline", "module_name": "crm_deals", "report_type": "summary", "visibility": "team"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Pipeline"

