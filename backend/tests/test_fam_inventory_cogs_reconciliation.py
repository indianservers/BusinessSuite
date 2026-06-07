from tests.fam_inventory_accounting_cases import accounting_setup, create_posted_delivery


def test_fam_inventory_cogs_reconciliation_endpoint_matches_delivery_posting(client, db):
    headers, item, warehouse, _ = accounting_setup(client, db, "COGSREC")
    create_posted_delivery(client, headers, item, warehouse, "COGSREC")

    response = client.get("/api/v1/fam/inventory/reconciliation/cogs", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["status"] in {"matched", "variance"}
    assert response.json()["items"]
