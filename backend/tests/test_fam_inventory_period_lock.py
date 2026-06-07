from tests.fam_inventory_accounting_cases import accounting_setup


def test_fam_inventory_posting_respects_locked_period(client, db):
    headers, item, warehouse, _ = accounting_setup(client, db, "LOCK")
    years = client.get("/api/v1/fam/financial-years", headers=headers)
    year_id = years.json()["items"][0]["id"]
    lock = client.post(f"/api/v1/fam/financial-years/{year_id}/lock", headers=headers)
    assert lock.status_code == 200, lock.text

    response = client.post("/api/v1/fam/inventory/opening-stock", headers=headers, json={"opening_number": "OPEN-LOCK-2", "opening_date": "2026-06-06", "stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity": 1, "rate": 100})

    assert response.status_code == 409
