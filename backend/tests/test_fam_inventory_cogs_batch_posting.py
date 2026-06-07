from tests.fam_inventory_accounting_cases import accounting_setup


def test_fam_inventory_cogs_batch_posting_posts_each_item(client, db):
    headers, item, warehouse, _ = accounting_setup(client, db, "BATCHCOGS")
    payload = {"items": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity": 1, "posting_date": "2026-06-07", "source_module": "srm", "source_record_type": "invoice_line", "source_record_id": "BATCH-1"}]}

    response = client.post("/api/v1/fam/inventory/cogs/batch-post", headers=headers, json=payload)

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["voucher"]["id"]
