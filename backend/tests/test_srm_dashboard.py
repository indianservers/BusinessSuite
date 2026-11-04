from tests.rich_text_test_utils import organization_context
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.apps.srm.models import (
    SRMBillingPlan,
    SRMContract,
    SRMEngagement,
    SRMInvoice,
    SRMInvoiceDraft,
    SRMProfitabilitySnapshot,
    SRMRevenueEvent,
    SRMSalesOrder,
)
from tests.srm_test_utils import auth_headers_for


def attach_dashboard_identity(db):
    from app.models.user import User
    from test_identity_utils import attach_test_identity
    attach_test_identity(db, db.query(User).filter_by(email="testadmin@test.com").one())
    db.commit()


def test_srm_dashboard_returns_phase_5_metrics(client, db, superuser_headers):
    attach_dashboard_identity(db)
    order = SRMSalesOrder(order_number="SO-DASH-001", title="Dashboard order", status="confirmed", customer_id=501, total_amount=Decimal("250000"))
    pending = SRMSalesOrder(order_number="SO-DASH-002", title="Pending order", status="pending_approval", customer_id=501, total_amount=Decimal("50000"))
    db.add_all([order, pending])
    db.flush()
    contract = SRMContract(contract_number="CTR-DASH-001", title="Dashboard contract", status="active", customer_id=501, sales_order_id=order.id, contract_value=Decimal("250000"))
    engagement = SRMEngagement(engagement_number="ENG-DASH-001", name="Dashboard engagement", status="delivery_in_progress", customer_id=501, sales_order_id=order.id, pms_project_id=301, budget_amount=Decimal("250000"))
    db.add_all([contract, engagement])
    db.flush()
    db.add_all([
        SRMBillingPlan(engagement_id=engagement.id, name="Dashboard billing", status="active", total_amount=Decimal("250000")),
        SRMInvoiceDraft(sales_order_id=order.id, engagement_id=engagement.id, customer_id=501, status="draft", source_type="sales_order", total_amount=Decimal("250000")),
        SRMInvoice(invoice_number="INV-DASH-001", sales_order_id=order.id, engagement_id=engagement.id, customer_id=501, status="sent", issue_date=date.today(), due_date=date.today() - timedelta(days=10), total_amount=Decimal("250000"), paid_amount=Decimal("100000"), balance_amount=Decimal("150000")),
        SRMProfitabilitySnapshot(engagement_id=engagement.id, customer_id=501, invoiced_amount=Decimal("250000"), collected_amount=Decimal("100000"), outstanding_amount=Decimal("150000"), gross_margin_amount=Decimal("80000"), cash_margin_amount=Decimal("30000")),
        SRMRevenueEvent(engagement_id=engagement.id, invoice_id=None, event_type="invoice_sent", amount=Decimal("250000"), recognized_on=date.today()),
    ])
    db.commit()

    response = client.get("/api/v1/srm/dashboard", headers=superuser_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_sales_orders"] == 2
    assert body["pending_approvals"] == 1
    assert body["confirmed_sales_orders"] == 1
    assert body["active_contracts"] == 1
    assert body["active_engagements"] == 1
    assert body["active_billing_plans"] == 1
    assert body["invoice_drafts_pending"] == 1
    assert body["sent_invoices"] == 1
    assert body["total_invoiced_value"] == 250000.0
    assert body["total_collected_value"] == 100000.0
    assert body["outstanding_value"] == 150000.0
    assert body["overdue_value"] == 150000.0
    assert body["collection_risk"] == "high"
    assert body["gross_margin"] == 80000.0
    assert body["cash_margin"] == 30000.0
    assert body["recent_sales_orders"][0]["order_number"].startswith("SO-DASH")
    assert body["recent_invoices"][0]["invoice_number"] == "INV-DASH-001"
    assert body["collection_alerts"][0]["overdue_days"] >= 10
    assert body["revenue_trend"]
    assert body["profitability_summary"]["margin_status"] in {"healthy", "at_risk"}


def test_srm_dashboard_rbac_blocks_user_without_srm_permission(client, db):
    blocked_headers = auth_headers_for(client, db, "dashboard-blocked@example.com", "srm_viewer", permissions=[])
    response = client.get("/api/v1/srm/dashboard", headers=blocked_headers)
    assert response.status_code == 403

    allowed_headers = auth_headers_for(client, db, "dashboard-viewer@example.com", "srm_viewer", permissions=["srm_view"])
    response = client.get("/api/v1/srm/dashboard", headers=allowed_headers)
    assert response.status_code == 200


def test_dashboard_reporting_period_filters_invoice_cohort_and_events(client, db, superuser_headers, monkeypatch):
    attach_dashboard_identity(db)
    from app.services.metrics import queries
    monkeypatch.setattr(queries, "business_day", lambda *args: date(2026, 1, 15))
    # Last three calendar months crosses the year boundary: Nov 1 through Jan 15.
    for index, (issued, amount, currency) in enumerate([
        (date(2025, 10, 31), 1000, "INR"),
        (date(2025, 11, 1), 200, "INR"),
        (date(2026, 1, 15), 400, "INR"),
        (date(2026, 1, 16), 800, "INR"),
        (date(2025, 12, 1), 100, "USD"),
    ]):
        db.add(SRMInvoice(invoice_number=f"INV-PERIOD-{index}", customer_id=501,
            status="sent", currency=currency, issue_date=issued, due_date=date(2026, 1, 1),
            total_amount=amount, paid_amount=amount / 4, balance_amount=amount * 3 / 4))
        db.add(SRMRevenueEvent(event_type="invoice_sent", amount=amount, currency=currency, recognized_on=issued))
    db.commit()
    for endpoint in ("/api/v1/srm/dashboard", "/api/v1/srm/reports/dashboard"):
        response = client.get(endpoint, params={"period": "3"}, headers=superuser_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["reporting_period"]["start_date"] == "2025-11-01"
        assert body["reporting_period"]["end_date"] == "2026-01-15"
        assert body["total_invoiced_value"] is None  # Mixed currencies are never summed.
        for key, expected in (("total_invoiced_value", 600), ("total_collected_value", 150), ("outstanding_value", 450), ("overdue_value", 450)):
            totals = {row["currency"]: Decimal(str(row["amount"])) for row in body["currency_totals"][key]}
            assert totals["INR"] == expected
        assert len(body["recent_invoices"]) == 3
        assert len(body["collection_alerts"]) == 3
        assert len(body["revenue_time_series"]) == 3
    all_time = client.get("/api/v1/srm/dashboard", headers=superuser_headers).json()
    assert all_time["reporting_period"]["start_date"] is None
    assert sum(Decimal(str(row["amount"])) for row in all_time["currency_totals"]["total_invoiced_value"] if row["currency"] == "INR") == 2400
    year = client.get("/api/v1/srm/dashboard", params={"period": "12"}, headers=superuser_headers).json()
    assert year["reporting_period"]["start_date"] == "2025-02-01"
    assert client.get("/api/v1/srm/dashboard", params={"period": "invalid"}, headers=superuser_headers).status_code == 422


def test_dashboard_custom_range_includes_both_dates_before_monthly_grouping(client, db, superuser_headers, monkeypatch):
    attach_dashboard_identity(db)
    from app.services.metrics import queries
    monkeypatch.setattr(queries, "business_day", lambda *args: date(2026, 4, 1))
    for index, (day, amount) in enumerate([(date(2026, 2, 9), 1000), (date(2026, 2, 10), 200), (date(2026, 3, 20), 400), (date(2026, 3, 21), 800)]):
        db.add(SRMSalesOrder(order_number=f"SO-CUSTOM-{index}", title="Custom range order", status="confirmed", created_at=datetime.combine(day, datetime.min.time()).replace(hour=12)))
        db.add(SRMInvoice(invoice_number=f"INV-CUSTOM-{index}", customer_id=501, status="sent", currency="INR", issue_date=day, due_date=day, total_amount=amount, paid_amount=amount / 4, balance_amount=amount * 3 / 4))
        db.add(SRMRevenueEvent(event_type="invoice_sent", amount=amount, currency="INR", recognized_on=day))
    db.commit()
    for endpoint in ("/api/v1/srm/dashboard", "/api/v1/srm/reports/dashboard"):
        response = client.get(endpoint, params={"period":"custom", "start_date":"2026-02-10", "end_date":"2026-03-20"}, headers=superuser_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total_sales_orders"] == 2
        assert body["confirmed_sales_orders"] == 2
        assert body["total_invoiced_value"] == 600
        assert body["total_collected_value"] == 150
        assert body["outstanding_value"] == 450
        assert body["overdue_value"] == 450
        assert len(body["recent_invoices"]) == 2
        assert [Decimal(row["amount"]) for row in body["revenue_time_series"]] == [200, 400]
        assert body["reporting_period"]["start_date"] == "2026-02-10"
        assert body["reporting_period"]["end_date"] == "2026-03-20"
        single = client.get(endpoint, params={"period":"custom", "start_date":"2026-02-10", "end_date":"2026-02-10"}, headers=superuser_headers).json()
        assert single["total_invoiced_value"] == 200
        empty = client.get(endpoint, params={"period":"custom", "start_date":"2025-01-01", "end_date":"2025-01-31"}, headers=superuser_headers).json()
        assert empty["total_invoiced_value"] == 0
        assert empty["revenue_time_series"] == []
        for params in [
            {"period":"custom"},
            {"period":"custom", "start_date":"2026-02-10"},
            {"period":"custom", "start_date":"2026-03-20", "end_date":"2026-02-10"},
            {"period":"custom", "start_date":"invalid", "end_date":"2026-03-20"},
            {"period":"all", "start_date":"2026-02-10", "end_date":"2026-03-20"},
        ]:
            assert client.get(endpoint, params=params, headers=superuser_headers).status_code == 422
