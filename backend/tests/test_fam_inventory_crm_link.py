from app.apps.crm.models import CRMProduct
from app.apps.fam.models import FAMInventoryIntegrationLink
from tests.fam_inventory_test_utils import create_stock_item, inventory_headers


def test_inventory_links_to_crm_product_catalog_by_sku_and_explicit_link(client, db):
    headers = inventory_headers(client, db, "phase9-crm@example.com")
    item, _warehouse = create_stock_item(client, headers, "P9-CRM")
    db.add(CRMProduct(organization_id=1, name=item["item_name"], sku=item["sku"], category="Inventory", unit_price=250, status="Active"))
    db.commit()

    crm_link = client.get("/api/v1/fam/inventory/crm-link", headers=headers)
    assert crm_link.status_code == 200, crm_link.text
    row = next(row for row in crm_link.json()["items"] if row["id"] == item["id"])
    assert row["crm_product"]["sku"] == item["sku"]

    explicit = client.post(
        f"/api/v1/fam/inventory/items/{item['id']}/link",
        headers=headers,
        json={"stock_item_id": item["id"], "target_module": "crm", "target_record_type": "product", "target_record_id": "1", "link_type": "catalog", "metadata_json": {"margin": 25}},
    )
    assert explicit.status_code == 200, explicit.text
    assert db.query(FAMInventoryIntegrationLink).filter(FAMInventoryIntegrationLink.target_module == "crm").count() == 1
