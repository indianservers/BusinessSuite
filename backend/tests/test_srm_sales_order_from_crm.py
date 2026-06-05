from app.apps.srm.models import SRMSalesOrderLine

from tests.test_srm_crm_won_handoff import create_won_deal_with_quote


def test_srm_sales_order_from_crm_copies_quote_amount_and_lines(client, db, superuser_headers):
    deal, quote = create_won_deal_with_quote(db, "Quote Copy Deal")

    response = client.post(f"/api/v1/srm/from-crm/deals/{deal.id}/create-sales-order", headers=superuser_headers)
    assert response.status_code == 201, response.text
    order = response.json()["sales_order"]
    assert order["total_amount"] == float(quote.total_amount)
    assert order["currency"] == quote.currency

    lines = db.query(SRMSalesOrderLine).filter(SRMSalesOrderLine.sales_order_id == order["id"]).all()
    assert len(lines) == 2
    assert {line.description for line in lines} == {"Implementation", "Training"}
    assert {line.source_quote_line_id for line in lines}
