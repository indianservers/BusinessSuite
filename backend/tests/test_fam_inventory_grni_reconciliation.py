from tests.fam_inventory_accounting_cases import accounting_setup


def test_fam_inventory_grni_reconciliation_endpoint_returns_outstanding(client, db):
    headers, item, warehouse, _ = accounting_setup(client, db, "GRNIREC")
    client.post("/api/v1/fam/inventory/purchase-receipts", headers=headers, json={"movement_date": "2026-06-07", "movement_type": "purchase_receipt", "reference_number": "GRNI-REC", "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_in": 2, "rate": 100}]})

    response = client.get("/api/v1/fam/inventory/reconciliation/grni", headers=headers)

    assert response.status_code == 200, response.text
    assert "grni_outstanding" in response.json()
    assert response.json()["items"]
