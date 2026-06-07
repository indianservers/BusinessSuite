from tests.fam_inventory_accounting_cases import accounting_setup, posted_voucher


def test_fam_inventory_opening_stock_accounting_posts_voucher(client, db):
    headers, _, _, opening = accounting_setup(client, db, "OPENACC")

    response = client.post("/api/v1/fam/inventory/opening-stock/post-accounting", headers=headers, json={"opening_stock_id": opening["id"]})

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    posted_voucher(db, response.json()["items"][0]["id"])
