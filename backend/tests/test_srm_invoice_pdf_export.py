from tests.srm_test_utils import create_sales_order


def test_srm_invoice_pdf_export(client, db, superuser_headers):
    order = create_sales_order(client, superuser_headers)
    invoice = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers).json()
    pdf = client.get(f"/api/v1/srm/invoices/{invoice['id']}/pdf", headers=superuser_headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert invoice["invoice_number"].encode() in pdf.content
