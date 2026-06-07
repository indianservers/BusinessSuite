from tests.fam_test_utils import create_party, fam_admin_headers, ledger_by_nature


def test_fam_purchase_bill_posting_creates_voucher_and_ap_bill(client, db):
    headers = fam_admin_headers(client, db)
    vendor = create_party(client, headers, "vendor", "VEN-POST-1", "Vendor Post")
    expense = ledger_by_nature(client, headers, "expense")
    bill = client.post("/api/v1/fam/purchase-bills", headers=headers, json={"vendor_id": vendor["id"], "bill_number": "PB-POST-001", "bill_date": "2026-06-06", "lines": [{"expense_ledger_id": expense["id"], "description": "Services", "taxable_value": 1000, "gst_amount": 180}]}).json()
    posted = client.post(f"/api/v1/fam/purchase-bills/{bill['id']}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    assert posted.json()["status"] == "posted"
    ap = client.get("/api/v1/fam/ap/outstanding", headers=headers).json()
    assert ap["totalOutstanding"] >= 1180
