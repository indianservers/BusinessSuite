from tests.fam_inventory_accounting_cases import accounting_setup, employee_headers


def test_fam_inventory_accounting_rbac_blocks_employee_mutation(client, db):
    headers, item, _, _ = accounting_setup(client, db, "RBACINV")
    employee = employee_headers(client, db, "fam-inv-rbac@example.com")

    view = client.get("/api/v1/fam/inventory/accounting", headers=employee)
    update = client.put(f"/api/v1/fam/inventory/items/{item['id']}/ledger-mapping", headers=employee, json={"inventory_ledger_id": 1})

    assert view.status_code == 403
    assert update.status_code == 403
