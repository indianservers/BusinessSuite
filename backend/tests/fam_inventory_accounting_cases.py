from app.apps.fam.models import FAMStockAdjustment, FAMStockTransfer, FAMVoucher
from tests.fam_inventory_test_utils import create_stock_item, inventory_headers, post_opening_stock
from tests.fam_test_utils import auth_headers_for, create_party, ledger_by_nature


def accounting_setup(client, db, suffix="ACCT"):
    headers = inventory_headers(client, db, f"fam-inv-{suffix.lower()}@example.com")
    item, warehouse = create_stock_item(client, headers, suffix)
    opening = post_opening_stock(client, headers, item, warehouse, quantity=12, rate=100, suffix=suffix)
    return headers, item, warehouse, opening


def create_posted_delivery(client, headers, item, warehouse, suffix="DEL"):
    response = client.post(
        "/api/v1/fam/inventory/delivery-notes",
        headers=headers,
        json={
            "movement_date": "2026-06-07",
            "movement_type": "delivery_note",
            "reference_number": f"DN-{suffix}",
            "source_module": "srm",
            "source_record_type": "invoice",
            "source_record_id": suffix,
            "lines": [{"stock_item_id": item["id"], "warehouse_id": warehouse["id"], "quantity_out": 2, "rate": 100}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_purchase_bill(client, headers, item, suffix="PB"):
    vendor = create_party(client, headers, "vendor", f"VEN-{suffix}", f"Vendor {suffix}")
    expense = ledger_by_nature(client, headers, "expense")
    response = client.post(
        "/api/v1/fam/purchase-bills",
        headers=headers,
        json={
            "vendor_id": vendor["id"],
            "bill_number": f"PB-{suffix}",
            "bill_date": "2026-06-07",
            "lines": [{"item_id": item["id"], "expense_ledger_id": expense["id"], "description": "Inventory purchase", "taxable_value": 500, "gst_amount": 90}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_transfer(client, headers, item, from_warehouse, suffix="TRF"):
    extra = client.post("/api/v1/fam/inventory/warehouses", headers=headers, json={"warehouse_code": f"WH-X-{suffix}", "warehouse_name": f"Extra {suffix}"})
    assert extra.status_code == 201, extra.text
    response = client.post(
        "/api/v1/fam/inventory/stock-transfers",
        headers=headers,
        json={"transfer_number": f"TRF-{suffix}", "transfer_date": "2026-06-07", "from_warehouse_id": from_warehouse["id"], "to_warehouse_id": extra.json()["id"], "lines": [{"stock_item_id": item["id"], "quantity": 1, "rate": 100}]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_adjustment(client, headers, item, warehouse, suffix="ADJ"):
    response = client.post(
        "/api/v1/fam/inventory/stock-adjustments",
        headers=headers,
        json={"adjustment_number": f"ADJ-{suffix}", "adjustment_date": "2026-06-07", "warehouse_id": warehouse["id"], "reason": "Cycle count", "lines": [{"stock_item_id": item["id"], "quantity_in": 1, "quantity_out": 0, "rate": 100}]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def employee_headers(client, db, email="fam-inv-employee@example.com"):
    return auth_headers_for(client, db, email, "employee", permissions=["fam_view"])


def posted_voucher(db, voucher_id):
    voucher = db.query(FAMVoucher).filter(FAMVoucher.id == voucher_id).first()
    assert voucher is not None
    assert voucher.status == "posted"
    return voucher


__all__ = [
    "FAMStockAdjustment",
    "FAMStockTransfer",
    "accounting_setup",
    "create_adjustment",
    "create_posted_delivery",
    "create_purchase_bill",
    "create_transfer",
    "employee_headers",
    "posted_voucher",
]
