from datetime import date

from app.apps.crm.models import CRMQuotation, CRMQuotationItem


def test_crm_quote_create_line_detail_and_status(client, db, superuser_headers):
    response = client.post("/api/v1/crm/quotes", headers=superuser_headers, json={
        "quoteNumber": "QT-P3-001",
        "quoteDate": "2026-06-01",
        "validUntil": "2026-06-30",
        "status": "Draft",
    })
    assert response.status_code == 201, response.text
    quote_id = response.json()["id"]
    quote = db.query(CRMQuotation).filter(CRMQuotation.id == quote_id).one()
    assert quote.quote_number == "QT-P3-001"
    assert quote.issue_date == date(2026, 6, 1)

    line = client.post(f"/api/v1/crm/quotes/{quote_id}/lines", headers=superuser_headers, json={
        "itemType": "service",
        "name": "Implementation",
        "quantity": 2,
        "unitPrice": 50000,
        "discountType": "percent",
        "discountValue": 10,
        "taxRate": 18,
        "estimatedCost": 50000,
    })
    assert line.status_code == 201, line.text
    assert db.query(CRMQuotationItem).filter(CRMQuotationItem.quote_id == quote_id).count() == 1

    detail = client.get(f"/api/v1/crm/quotes/{quote_id}", headers=superuser_headers)
    assert detail.status_code == 200
    assert detail.json()["lines"][0]["name"] == "Implementation"
