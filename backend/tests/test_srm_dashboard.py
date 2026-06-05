from datetime import date, timedelta
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


def test_srm_dashboard_returns_phase_5_metrics(client, db, superuser_headers):
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
