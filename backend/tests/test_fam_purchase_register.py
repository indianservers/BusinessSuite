from tests.fam_test_utils import create_party, fam_admin_headers, ledger_by_nature


def test_fam_purchase_and_expense_registers(client, db):
    headers = fam_admin_headers(client, db)
    vendor = create_party(client, headers, "vendor", "VEN-REG-1", "Vendor Reg")
    expense = ledger_by_nature(client, headers, "expense")
    client.post("/api/v1/fam/purchase-bills", headers=headers, json={"vendor_id": vendor["id"], "bill_number": "PB-REG-001", "bill_date": "2026-06-06", "lines": [{"expense_ledger_id": expense["id"], "description": "Services", "taxable_value": 1000}]})
    purchase_register = client.get("/api/v1/fam/purchase-register", headers=headers)
    expense_register = client.get("/api/v1/fam/expense-register", headers=headers)
    assert purchase_register.status_code == 200
    assert purchase_register.json()["total"] == 1
    assert expense_register.status_code == 200
