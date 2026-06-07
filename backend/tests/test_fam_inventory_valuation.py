from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock


def test_fam_inventory_weighted_average_valuation(client, db):
    headers = inventory_headers(client, db)
    item, warehouse = create_stock_item(client, headers, "VAL")
    post_opening_stock(client, headers, item, warehouse, quantity=10, rate=50, suffix="VAL")
    valuation = client.get("/api/v1/fam/inventory/valuation", headers=headers)
    assert valuation.status_code == 200
    row = next(record for record in valuation.json()["items"] if record["id"] == item["id"])
    assert row["stock_value"] == 500
    assert valuation.json()["valuation_method"] == "weighted_average"
