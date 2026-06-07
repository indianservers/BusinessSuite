from tests.fam_test_utils import create_party, fam_admin_headers, ledger_by_nature, ledger_by_type


def test_fam_vendor_payment_posts_and_marks_bill_paid(client, db):
    headers = fam_admin_headers(client, db)
    vendor = create_party(client, headers, "vendor", "VEN-PAY-1", "Vendor Pay")
    expense = ledger_by_nature(client, headers, "expense")
    bank = ledger_by_type(client, headers, "bank")
    bill = client.post("/api/v1/fam/purchase-bills", headers=headers, json={"vendor_id": vendor["id"], "bill_number": "PB-PAY-001", "bill_date": "2026-06-06", "lines": [{"expense_ledger_id": expense["id"], "description": "Services", "taxable_value": 1000}]}).json()
    client.post(f"/api/v1/fam/purchase-bills/{bill['id']}/post", headers=headers)
    response = client.post("/api/v1/fam/vendor-payments/post", headers=headers, json={"payment_date": "2026-06-07", "bank_ledger_id": bank["id"], "items": [{"vendor_id": vendor["id"], "purchase_bill_id": bill["id"], "amount": 1000}]})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "posted"
    assert client.get(f"/api/v1/fam/purchase-bills/{bill['id']}", headers=headers).json()["status"] == "paid"
