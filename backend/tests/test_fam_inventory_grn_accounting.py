from tests.fam_inventory_accounting_cases import accounting_setup, posted_voucher


def test_fam_inventory_grn_accounting_posts_grni_voucher(client, db):
    headers, item, warehouse, _ = accounting_setup(client, db, "GRN")
    receipt = client.post(
        "/api/v1/fam/inventory/purchase-receipts",
        headers=headers,
        json={"movement_date": "2026-06-07", "movement_type": "purchase_receipt", "reference_number": "GRN-001", "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_in": 3, "rate": 100}]},
    )

    assert receipt.status_code == 201, receipt.text
    response = client.post(f"/api/v1/fam/inventory/grn/{receipt.json()['id']}/post-accounting", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["voucher"]["id"]
    posted_voucher(db, response.json()["voucher"]["id"])
