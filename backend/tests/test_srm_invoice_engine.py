from app.apps.srm.models import SRMInvoice, SRMInvoiceHistory

from tests.srm_test_utils import create_sales_order


def test_srm_invoice_draft_approve_send_and_duplicate_guard(client, db, superuser_headers):
    order = create_sales_order(client, superuser_headers)

    draft = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers)
    assert draft.status_code == 201, draft.text
    invoice = draft.json()

    duplicate = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers)
    assert duplicate.status_code == 409

    line = client.post(f"/api/v1/srm/invoices/{invoice['id']}/lines", headers=superuser_headers, json={
        "description": "Additional onboarding fee",
        "quantity": 1,
        "unit_price": 10000,
        "tax_amount": 1800,
    })
    assert line.status_code == 201, line.text

    approved = client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve", headers=superuser_headers)
    assert approved.status_code == 200, approved.text
    sent = client.post(f"/api/v1/srm/invoices/{invoice['id']}/send", headers=superuser_headers)
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "sent"

    pdf = client.get(f"/api/v1/srm/invoices/{invoice['id']}/pdf", headers=superuser_headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert db.query(SRMInvoice).filter(SRMInvoice.id == invoice["id"]).first().status == "sent"
    assert db.query(SRMInvoiceHistory).filter(SRMInvoiceHistory.invoice_id == invoice["id"]).count() >= 3


def test_srm_manual_invoice_and_reports(client, db, superuser_headers):
    response = client.post("/api/v1/srm/invoices/manual", headers=superuser_headers, json={
        "customer_id": 202,
        "currency": "INR",
        "lines": [{"description": "Manual advisory fee", "quantity": 2, "unit_price": 15000, "tax_amount": 5400}],
    })
    assert response.status_code == 201, response.text
    invoice = response.json()
    assert invoice["source_type"] == "manual"
    assert invoice["total_amount"] == 35400.0

    listing = client.get("/api/v1/srm/invoices", headers=superuser_headers)
    assert listing.status_code == 200
    assert any(item["id"] == invoice["id"] for item in listing.json())

    reports = client.get("/api/v1/srm/reports", headers=superuser_headers)
    assert reports.status_code == 200, reports.text
    body = reports.json()
    assert "invoice_register" in body
    assert "cash_margin_report" in body
