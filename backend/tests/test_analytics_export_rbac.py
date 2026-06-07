from tests.analytics_test_utils import analytics_headers, create_report


def test_analytics_export_permission_and_financial_rbac(client, db):
    builder_headers = analytics_headers(client, db, "builder@example.com", ["analytics_view", "analytics_report_builder"])
    report = create_report(client, builder_headers, "crm_deals")
    blocked_export = client.post(f"/api/v1/analytics/reports/{report['id']}/export", headers=builder_headers, json={"export_type": "csv"})
    assert blocked_export.status_code == 403

    financial_blocked = client.post("/api/v1/analytics/reports", headers=builder_headers, json={"name": "Profit", "module_name": "srm_profitability", "report_type": "table"})
    assert financial_blocked.status_code == 403

    finance_headers = analytics_headers(client, db, "finance@example.com", ["analytics_view", "analytics_report_builder", "analytics_profitability_view"])
    financial_ok = client.post("/api/v1/analytics/reports", headers=finance_headers, json={"name": "Profit", "module_name": "srm_profitability", "report_type": "table"})
    assert financial_ok.status_code == 201

