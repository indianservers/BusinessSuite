from datetime import date

from app.apps.crm.models import CRMDeal, CRMQuotation, CRMQuotationItem, CRMQuoteSRMConversionLog, CRMPipeline, CRMPipelineStage
from app.apps.srm.models import SRMSalesOrder


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
    quote = CRMQuotation(organization_id=1, quote_number=f"Q-{deal.id:04d}", issue_date=date(2026, 6, 1), expiry_date=date(2026, 7, 1), deal_id=deal.id, status="Accepted", approval_status="approved", currency="INR", subtotal=250000, discount_amount=0, tax_amount=45000, total_amount=295000)
    db.add(quote)
    db.flush()
    db.add(CRMQuotationItem(quotation_id=quote.id, quote_id=quote.id, name="Implementation", quantity=1, unit_price=200000, total_amount=200000, line_total=200000))
    db.add(CRMQuotationItem(quotation_id=quote.id, quote_id=quote.id, name="Training", quantity=1, unit_price=95000, total_amount=95000, line_total=95000))
    db.commit()
    return deal, quote


def test_accepted_crm_quote_converts_to_srm_idempotently(client, db, superuser_headers):
    deal, quote = create_won_deal_with_quote(db, "Quote Accepted Deal")
    quote.status = "Accepted"
    quote.approval_status = "approved"
    db.commit()

    response = client.post(f"/api/v1/crm/quotes/{quote.id}/convert-to-srm", headers=superuser_headers)
    assert response.status_code == 200, response.text
    assert response.json()["conversionLog"]["status"] == "converted"
    assert db.query(SRMSalesOrder).filter(SRMSalesOrder.crm_deal_id == deal.id).count() == 1
    assert db.query(CRMQuoteSRMConversionLog).filter(CRMQuoteSRMConversionLog.quote_id == quote.id, CRMQuoteSRMConversionLog.status == "converted").count() == 1

    second = client.post(f"/api/v1/crm/quotes/{quote.id}/convert-to-srm", headers=superuser_headers)
    assert second.status_code == 200, second.text
    assert second.json()["idempotent"] is True
    assert db.query(SRMSalesOrder).filter(SRMSalesOrder.crm_deal_id == deal.id).count() == 1
