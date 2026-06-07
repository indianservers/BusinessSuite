from tests.fam_test_utils import create_party, fam_admin_headers, ledger_by_nature


def test_fam_purchase_bill_create_and_view(client, db):
    headers = fam_admin_headers(client, db)
    vendor = create_party(client, headers, "vendor", "VEN-PB-1", "Vendor PB")
    expense = ledger_by_nature(client, headers, "expense")
    payload = {"vendor_id": vendor["id"], "bill_number": "PB-001", "bill_date": "2026-06-06", "lines": [{"expense_ledger_id": expense["id"], "description": "Consulting", "quantity": 1, "rate": 1000, "gst_amount": 180, "line_total": 1180}]}
    response = client.post("/api/v1/fam/purchase-bills", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    bill = response.json()
    assert bill["grand_total"] == 1180
    detail = client.get(f"/api/v1/fam/purchase-bills/{bill['id']}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["lines"]) == 1
