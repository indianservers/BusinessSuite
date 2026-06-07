from app.apps.fam.models import FAMStockTransfer
from tests.fam_inventory_accounting_cases import accounting_setup, create_transfer


def test_fam_inventory_transfer_accounting_posts_existing_transfer(client, db):
    headers, item, warehouse, _ = accounting_setup(client, db, "TRFACC")
    transfer = create_transfer(client, headers, item, warehouse, "TRFACC")

    response = client.post(f"/api/v1/fam/inventory/transfers/{transfer['id']}/post-accounting", headers=headers)

    assert response.status_code == 200, response.text
    stored = db.query(FAMStockTransfer).filter(FAMStockTransfer.id == transfer["id"]).one()
    assert stored.status == "posted"
    assert stored.movement_id
