from datetime import date

from app.apps.fam.models import FAMGSTRate, FAMHSNSACCode
from tests.fam_inventory_test_utils import create_inventory_master_set, inventory_headers


def test_inventory_item_exposes_hsn_gst_and_einvoice_readiness(client, db):
    headers = inventory_headers(client, db, "phase9-gst@example.com")
    group, unit, warehouse = create_inventory_master_set(client, headers, "P9-GST")
    rate = FAMGSTRate(company_id=1, rate_name="GST 18", tax_type="goods", cgst_rate=9, sgst_rate=9, igst_rate=18, effective_from=date(2026, 4, 1), active=True)
    db.add(rate)
    db.flush()
    db.add(FAMHSNSACCode(company_id=1, code="8471", description="Computing goods", type="hsn", default_gst_rate_id=rate.id, active=True))
    db.commit()
    item = client.post("/api/v1/fam/inventory/items", headers=headers, json={"sku": "SKU-P9-GST", "item_name": "GST Stock", "stock_group_id": group["id"], "unit_id": unit["id"], "default_warehouse_id": warehouse["id"], "hsn_code": "8471", "gst_rate_id": rate.id, "purchase_rate": 100, "sales_rate": 150})
    assert item.status_code == 201, item.text

    link = client.get("/api/v1/fam/inventory/gst-link", headers=headers)
    assert link.status_code == 200, link.text
    row = next(row for row in link.json()["items"] if row["sku"] == "SKU-P9-GST")
    assert row["gst_rate"]["rate_name"] == "GST 18"
    assert row["hsn_sac"]["code"] == "8471"
    assert row["einvoice_item_ready"] is True
