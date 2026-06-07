from tests.analytics_test_utils import analytics_headers, create_analytics_deal, create_report
from app.apps.analytics.models import AnalyticsExportAuditLog


def test_analytics_csv_xlsx_pdf_exports_are_real_downloads(client, db):
    headers = analytics_headers(client, db)
    create_analytics_deal(db, "Export Deal", 50000, 60)
    report = create_report(client, headers, "crm_deals")
    for export_type, expected in [("csv", b"name"), ("xlsx", b"PK"), ("pdf", b"%PDF")]:
        exported = client.post(f"/api/v1/analytics/reports/{report['id']}/export", headers=headers, json={"export_type": export_type})
        assert exported.status_code == 201, exported.text
        assert exported.json()["status"] == "completed"
        downloaded = client.get(f"/api/v1/analytics/exports/{exported.json()['id']}/download", headers=headers)
        assert downloaded.status_code == 200
        assert expected in downloaded.content[:200]
    assert db.query(AnalyticsExportAuditLog).count() >= 6
