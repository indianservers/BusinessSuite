from tests.analytics_test_utils import analytics_headers, create_analytics_deal, create_report


def test_report_builder_runs_paginated_preview(client, db):
    headers = analytics_headers(client, db)
    create_analytics_deal(db, "Pipeline Deal", 100000, 70)
    report = create_report(client, headers, "crm_deals")
    run = client.post(f"/api/v1/analytics/reports/{report['id']}/run", headers=headers, json={"page": 1, "page_size": 10})
    assert run.status_code == 200, run.text
    assert run.json()["total"] >= 1
    assert "fields" in run.json()
