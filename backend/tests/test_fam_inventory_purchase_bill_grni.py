from tests.fam_inventory_accounting_cases import accounting_setup, create_purchase_bill, posted_voucher


def test_fam_inventory_purchase_bill_against_grni_posts_inventory_accounting(client, db):
    headers, item, _, _ = accounting_setup(client, db, "PBGRNI")
    bill = create_purchase_bill(client, headers, item, "PBGRNI")

    response = client.post(f"/api/v1/fam/inventory/purchase-bill/{bill['id']}/post-inventory-accounting", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "posted"
    posted_voucher(db, response.json()["voucher_id"])
