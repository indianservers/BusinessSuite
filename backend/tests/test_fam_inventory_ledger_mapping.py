from app.apps.fam.models import FAMAuditLog, FAMStockItem, FAMLedger
from tests.fam_inventory_accounting_cases import accounting_setup


def test_fam_inventory_ledger_mapping_updates_item_and_audit(client, db):
    headers, item, _, _ = accounting_setup(client, db, "MAP")
    ledgers = db.query(FAMLedger).order_by(FAMLedger.id).limit(5).all()
    assert len(ledgers) == 5
    payload = {key: ledger.id for key, ledger in zip(["inventory_ledger_id", "purchase_ledger_id", "sales_ledger_id", "cogs_ledger_id", "grni_ledger_id"], ledgers)}
    payload.update(hsn_code="9983", valuation_method="weighted_average")

    response = client.put(f"/api/v1/fam/inventory/items/{item['id']}/ledger-mapping", headers=headers, json=payload)

    assert response.status_code == 200, response.text
    assert response.json()["purchase_ledger_id"] == ledgers[1].id
    stored = db.query(FAMStockItem).filter(FAMStockItem.id == item["id"]).one()
    assert stored.grni_ledger_id == ledgers[4].id
    assert db.query(FAMAuditLog).filter(FAMAuditLog.record_type == "inventory_item_ledger_mapping", FAMAuditLog.action == "UPDATE").count() == 1
