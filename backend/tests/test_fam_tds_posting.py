from tests.fam_test_utils import create_party, fam_admin_headers, ledger_by_nature


def test_fam_purchase_posting_creates_tds_transaction(client, db):
    headers = fam_admin_headers(client, db)
    vendor = create_party(client, headers, "vendor", "VEN-TDS-1", "Vendor TDS")
    expense = ledger_by_nature(client, headers, "expense")
    section = client.post("/api/v1/fam/tds/sections", headers=headers, json={"section_code": "194J", "description": "Professional", "default_rate": 10, "threshold_amount": 0, "effective_from": "2026-04-01"}).json()
    bill = client.post("/api/v1/fam/purchase-bills", headers=headers, json={"vendor_id": vendor["id"], "bill_number": "PB-TDS-001", "bill_date": "2026-06-06", "lines": [{"expense_ledger_id": expense["id"], "description": "Fees", "taxable_value": 1000, "gst_amount": 0, "tds_section_id": section["id"], "tds_amount": 100}]}).json()
    posted = client.post(f"/api/v1/fam/purchase-bills/{bill['id']}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    tds = client.get("/api/v1/fam/tds/transactions", headers=headers).json()
    assert tds["total"] == 1
    assert tds["items"][0]["tds_amount"] == 100
