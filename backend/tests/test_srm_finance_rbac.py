from tests.srm_test_utils import auth_headers_for, create_sales_order


def test_srm_finance_collection_and_sales_rbac(client, db, superuser_headers):
    order = create_sales_order(client, superuser_headers)
    finance_headers = auth_headers_for(client, db, "finance@srm.example.com", "srm_finance_manager", permissions=[
        "srm_invoice_view",
        "srm_invoice_create",
        "srm_invoice_approve",
        "srm_collection_view",
        "srm_collection_create",
        "srm_profitability_view",
    ])
    collection_headers = auth_headers_for(client, db, "collector@srm.example.com", "srm_collection_executive", permissions=[
        "srm_collection_view",
        "srm_collection_create",
    ])
    sales_headers = auth_headers_for(client, db, "sales-limited@srm.example.com", "srm_sales_executive", permissions=["srm_invoice_view"])

    invoice = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=finance_headers)
    assert invoice.status_code == 201, invoice.text
    approved = client.post(f"/api/v1/srm/invoices/{invoice.json()['id']}/approve", headers=finance_headers)
    assert approved.status_code == 200, approved.text
    assert client.get("/api/v1/srm/profitability", headers=finance_headers).status_code == 200

    receipt = client.post("/api/v1/srm/receipts", headers=collection_headers, json={"customer_id": 101, "amount": 1000})
    assert receipt.status_code == 201, receipt.text
    blocked_invoice_edit = client.patch(f"/api/v1/srm/invoices/{invoice.json()['id']}", headers=collection_headers, json={"status": "cancelled"})
    assert blocked_invoice_edit.status_code == 403

    blocked_create = client.post(f"/api/v1/srm/invoices/draft-from-engagement/9999", headers=sales_headers)
    assert blocked_create.status_code == 403
