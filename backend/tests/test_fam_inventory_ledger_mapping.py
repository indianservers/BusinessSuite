from app.apps.fam.models import FAMAuditLog, FAMStockItem
from tests.fam_inventory_accounting_cases import accounting_setup


def test_fam_inventory_ledger_mapping_updates_item_and_audit(client, db):
    headers, item, _, _ = accounting_setup(client, db, "MAP")
    payload = {"inventory_ledger_id": 1, "purchase_ledger_id": 2, "sales_ledger_id": 3, "cogs_ledger_id": 4, "grni_ledger_id": 5, "hsn_code": "9983", "valuation_method": "weighted_average"}

    response = client.put(f"/api/v1/fam/inventory/items/{item['id']}/ledger-mapping", headers=headers, json=payload)

    assert response.status_code == 200, response.text
    assert response.json()["purchase_ledger_id"] == 2
    stored = db.query(FAMStockItem).filter(FAMStockItem.id == item["id"]).one()
    assert stored.grni_ledger_id == 5
    assert db.query(FAMAuditLog).filter(FAMAuditLog.record_type == "inventory_item_ledger_mapping", FAMAuditLog.action == "UPDATE").count() == 1
