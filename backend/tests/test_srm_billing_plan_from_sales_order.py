from app.apps.srm.models import SRMBillingMilestone, SRMBillingPlan

from tests.test_srm_crm_won_handoff import create_won_deal_with_quote


def test_srm_billing_plan_from_sales_order_is_invoice_ready(client, db, superuser_headers):
    deal, _quote = create_won_deal_with_quote(db, "Billing Plan Deal")
    handoff = client.post(f"/api/v1/srm/from-crm/deals/{deal.id}/create-sales-order", headers=superuser_headers).json()
    order_id = handoff["sales_order"]["id"]

    response = client.post(f"/api/v1/srm/sales-orders/{order_id}/billing-plan", headers=superuser_headers)
    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["engagement_id"] == handoff["engagement"]["id"]
    assert plan["total_amount"] == handoff["sales_order"]["total_amount"]
    assert len(plan["milestones"]) == 2
    assert db.query(SRMBillingPlan).filter(SRMBillingPlan.engagement_id == handoff["engagement"]["id"]).count() == 1
    assert db.query(SRMBillingMilestone).filter(SRMBillingMilestone.billing_plan_id == plan["id"]).count() == 2
