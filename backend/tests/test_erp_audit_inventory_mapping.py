from app.apps.fam.models import FAMLedger, FAMStockItem, FAMAuditLog
from tests.fam_inventory_accounting_cases import accounting_setup


def test_audit_mapping_preserves_omitted_fields_and_rejects_invalid_references_without_writes(client, db):
    headers, item, _, _ = accounting_setup(client, db, "AUDMAP")
    path = f"/api/v1/fam/inventory/items/{item['id']}/ledger-mapping"
    before = client.get(path, headers=headers).json()
    response = client.put(path, headers=headers, json={"hsn_code": "9983"})
    assert response.status_code == 200, response.text
    assert response.json()["inventory_ledger_id"] == before["inventory_ledger_id"]
    assert response.json()["cogs_ledger_id"] == before["cogs_ledger_id"]
    snapshot = response.json()
    audits = db.query(FAMAuditLog).filter_by(record_type="inventory_item_ledger_mapping").count()
    fields = ["inventory_ledger_id", "purchase_ledger_id", "sales_ledger_id", "cogs_ledger_id", "adjustment_gain_ledger_id", "adjustment_loss_ledger_id", "grni_ledger_id", "gst_rate_id", "cost_center_id", "default_warehouse_id"]
    for field in fields:
        response = client.put(path, headers=headers, json={field: 999999})
        assert response.status_code == 422, response.text
        assert client.get(path, headers=headers).json() == snapshot
    assert client.put(path, headers=headers, json={"branch_id": 999999}).status_code == 403
    assert client.put(path, headers=headers, json={"valuation_method": "fifo"}).status_code == 422
    assert db.query(FAMAuditLog).filter_by(record_type="inventory_item_ledger_mapping").count() == audits
    response = client.put(path, headers=headers, json={"purchase_ledger_id": before["inventory_ledger_id"]})
    assert response.status_code == 200
    response = client.put(path, headers=headers, json={"purchase_ledger_id": None})
    assert response.status_code == 200
    assert response.json()["purchase_ledger_id"] is None
    assert response.json()["inventory_ledger_id"] == before["inventory_ledger_id"]


def test_audit_mapping_rejects_foreign_and_inactive_ledgers(client, db):
    headers, item, _, _ = accounting_setup(client, db, "AUDMAPSCOPE")
    stored = db.get(FAMStockItem, item["id"])
    original = db.get(FAMLedger, stored.inventory_ledger_id)
    inactive = FAMLedger(company_id=stored.company_id, ledger_group_id=original.ledger_group_id, ledger_code="AUD-INACTIVE", ledger_name="Retired ledger", nature="asset", ledger_type="general", active=False)
    foreign = FAMLedger(company_id=stored.company_id + 1000, ledger_group_id=original.ledger_group_id, ledger_code="AUD-FOREIGN", ledger_name="Other company ledger", nature="asset", ledger_type="general", active=True)
    db.add_all([inactive, foreign])
    from test_identity_utils import own_workflow_records
    own_workflow_records(db, inactive, company_id=stored.company_id)
    db.commit()
    path = f"/api/v1/fam/inventory/items/{item['id']}/ledger-mapping"
    before = client.get(path, headers=headers).json()
    for ledger in [inactive.id, foreign.id]:
        response = client.put(path, headers=headers, json={"sales_ledger_id": ledger})
        assert response.status_code == 422, response.text
        assert client.get(path, headers=headers).json() == before
