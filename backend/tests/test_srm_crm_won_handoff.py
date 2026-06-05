from datetime import date

from app.apps.crm.models import CRMActivity, CRMDeal, CRMQuotation, CRMQuotationItem, CRMPipeline, CRMPipelineStage
from app.apps.srm.models import SRMAuditLog, SRMBillingPlan, SRMContract, SRMEngagement, SRMRevenueEvent, SRMSalesOrder, SRMSalesOrderLine


def create_won_deal_with_quote(db, name: str = "Won ERP rollout"):
    pipeline = CRMPipeline(organization_id=1, name=f"Default {name}", is_default=True)
    db.add(pipeline)
    db.flush()
    stage = CRMPipelineStage(organization_id=1, pipeline_id=pipeline.id, name="Closed Won", probability=100, is_won=True)
    db.add(stage)
    db.flush()
    deal = CRMDeal(organization_id=1, pipeline_id=pipeline.id, stage_id=stage.id, name=name, amount=250000, currency="INR", status="Won")
    db.add(deal)
    db.flush()
    quote = CRMQuotation(
        organization_id=1,
        quote_number=f"Q-{deal.id:04d}",
        issue_date=date(2026, 6, 1),
        expiry_date=date(2026, 7, 1),
        deal_id=deal.id,
        status="Approved",
        currency="INR",
        subtotal=250000,
        discount_amount=0,
        tax_amount=45000,
        total_amount=295000,
    )
    db.add(quote)
    db.flush()
    db.add(CRMQuotationItem(quotation_id=quote.id, name="Implementation", quantity=1, unit_price=200000, total_amount=200000))
    db.add(CRMQuotationItem(quotation_id=quote.id, name="Training", quantity=1, unit_price=95000, total_amount=95000))
    db.commit()
    return deal, quote


def test_srm_crm_won_handoff_creates_sales_order_and_engagement(client, db, superuser_headers):
    deal, quote = create_won_deal_with_quote(db)

    response = client.post(f"/api/v1/srm/from-crm/deals/{deal.id}/create-sales-order", headers=superuser_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["sales_order"]["crm_deal_id"] == deal.id
    assert body["sales_order"]["crm_quote_id"] == quote.id
    assert body["engagement"]["crm_deal_id"] == deal.id
    assert body["contract"]["sales_order_id"] == body["sales_order"]["id"]
    assert body["billing_plan"]["engagement_id"] == body["engagement"]["id"]
    assert db.query(SRMSalesOrder).filter(SRMSalesOrder.crm_deal_id == deal.id).count() == 1
    assert db.query(SRMSalesOrderLine).filter(SRMSalesOrderLine.sales_order_id == body["sales_order"]["id"]).count() == 2
    assert db.query(SRMEngagement).filter(SRMEngagement.crm_deal_id == deal.id).count() == 1
    assert db.query(SRMContract).filter(SRMContract.sales_order_id == body["sales_order"]["id"]).count() == 1
    assert db.query(SRMBillingPlan).filter(SRMBillingPlan.engagement_id == body["engagement"]["id"]).count() == 1
    assert db.query(SRMRevenueEvent).filter(SRMRevenueEvent.engagement_id == body["engagement"]["id"], SRMRevenueEvent.event_type == "crm_won_handoff").count() == 1
    assert db.query(SRMAuditLog).filter(SRMAuditLog.entity_type == "sales_order", SRMAuditLog.entity_id == body["sales_order"]["id"]).count() >= 1


def test_crm_deal_update_to_won_triggers_srm_handoff(client, db, superuser_headers):
    deal, _quote = create_won_deal_with_quote(db, "API Won Deal")
    deal.status = "Open"
    db.commit()

    response = client.patch(f"/api/v1/crm/deals/{deal.id}", headers=superuser_headers, json={"status": "Won"})
    assert response.status_code == 200, response.text
    assert db.query(SRMSalesOrder).filter(SRMSalesOrder.crm_deal_id == deal.id).count() == 1
    assert db.query(CRMActivity).filter(CRMActivity.deal_id == deal.id, CRMActivity.activity_type == "srm_handoff").count() == 1


def test_srm_by_crm_deal_returns_links(client, db, superuser_headers):
    deal, _quote = create_won_deal_with_quote(db, "Lookup Won Deal")
    client.post(f"/api/v1/srm/from-crm/deals/{deal.id}/create-sales-order", headers=superuser_headers)

    response = client.get(f"/api/v1/srm/by-crm-deal/{deal.id}", headers=superuser_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sales_order"]["crm_deal_id"] == deal.id
    assert body["engagement"]["crm_deal_id"] == deal.id
