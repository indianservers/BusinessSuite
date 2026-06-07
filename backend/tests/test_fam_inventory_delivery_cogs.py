from tests.fam_inventory_accounting_cases import accounting_setup, create_posted_delivery, posted_voucher


def test_fam_inventory_delivery_cogs_posts_from_delivery_note(client, db):
    headers, item, warehouse, _ = accounting_setup(client, db, "DELC")
    delivery = create_posted_delivery(client, headers, item, warehouse, "DELC")

    response = client.post(f"/api/v1/fam/inventory/delivery/{delivery['id']}/post-cogs", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["voucher"]["id"] == delivery["voucher_id"]
    posted_voucher(db, response.json()["voucher"]["id"])
