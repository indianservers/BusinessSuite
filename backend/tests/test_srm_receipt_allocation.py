from tests.srm_test_utils import create_sales_order


def test_srm_receipt_allocation_rejects_over_allocation(client, db, superuser_headers):
    order = create_sales_order(client, superuser_headers)
    invoice = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers).json()
    receipt = client.post("/api/v1/srm/receipts", headers=superuser_headers, json={"customer_id": 101, "amount": 200000}).json()

    too_much = client.post(f"/api/v1/srm/receipts/{receipt['id']}/allocate", headers=superuser_headers, json={"invoice_id": invoice["id"], "amount": invoice["balance_amount"] + 1})
    assert too_much.status_code == 400

    ok = client.post(f"/api/v1/srm/receipts/{receipt['id']}/allocate", headers=superuser_headers, json={"invoice_id": invoice["id"], "amount": invoice["balance_amount"]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["invoice"]["status"] == "paid"
