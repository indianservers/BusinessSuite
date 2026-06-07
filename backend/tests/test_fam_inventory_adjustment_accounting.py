from app.apps.fam.models import FAMStockAdjustment
from tests.fam_inventory_accounting_cases import accounting_setup, create_adjustment, posted_voucher


def test_fam_inventory_adjustment_accounting_posts_existing_adjustment(client, db):
    headers, item, warehouse, _ = accounting_setup(client, db, "ADJACC")
    adjustment = create_adjustment(client, headers, item, warehouse, "ADJACC")

    response = client.post(f"/api/v1/fam/inventory/adjustments/{adjustment['id']}/post-accounting", headers=headers, json={})

    assert response.status_code == 200, response.text
    stored = db.query(FAMStockAdjustment).filter(FAMStockAdjustment.id == adjustment["id"]).one()
    assert stored.status == "posted"
    posted_voucher(db, stored.voucher_id)
