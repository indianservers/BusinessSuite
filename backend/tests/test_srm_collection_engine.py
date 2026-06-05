from app.apps.srm.models import SRMCustomerAging, SRMReceipt, SRMReceiptAllocation

from tests.srm_test_utils import create_sales_order


def test_srm_receipt_allocation_updates_invoice_and_aging(client, db, superuser_headers):
    order = create_sales_order(client, superuser_headers)
    invoice = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers).json()
    receipt = client.post("/api/v1/srm/receipts", headers=superuser_headers, json={"customer_id": 101, "amount": 50000}).json()
    assert receipt["status"] == "draft"
    confirmed = client.post(f"/api/v1/srm/receipts/{receipt['id']}/confirm", headers=superuser_headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"

    allocation = client.post(f"/api/v1/srm/receipts/{receipt['id']}/allocate", headers=superuser_headers, json={"invoice_id": invoice["id"], "amount": 50000})
    assert allocation.status_code == 200, allocation.text
    assert allocation.json()["invoice"]["paid_amount"] == 50000.0
    assert db.query(SRMReceiptAllocation).filter(SRMReceiptAllocation.receipt_id == receipt["id"]).count() == 1
    assert db.query(SRMReceipt).filter(SRMReceipt.id == receipt["id"]).first().status == "allocated"

    aging = client.get("/api/v1/srm/collections/aging", headers=superuser_headers)
    assert aging.status_code == 200
    assert aging.json()[0]["total_outstanding"] > 0
    assert db.query(SRMCustomerAging).filter(SRMCustomerAging.customer_id == 101).first() is not None

    reminder = client.post("/api/v1/srm/collections/reminders/send", headers=superuser_headers, json={"customer_id": 101, "invoice_id": invoice["id"]})
    assert reminder.status_code == 200, reminder.text
