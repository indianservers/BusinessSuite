from app.apps.business_os.services.module_service import ensure_business_os_seed
from app.main import app
from tests.srm_test_utils import auth_headers_for


def test_srm_product_master_and_opening_stock_are_database_backed(client, db):
    app.state.business_os_session_factory = lambda: db
    app.state.business_os_close_session = False
    try:
        ensure_business_os_seed(db, company_id=1)
        headers = auth_headers_for(
            client,
            db,
            "inventory-manager@srm.example.com",
            "srm_sales_manager",
            permissions=["srm_view", "srm_manage"],
        )

        category = client.post(
            "/api/v1/srm/inventory/categories",
            headers=headers,
            json={"category_code": "BOOKS", "category_name": "Stationery"},
        )
        assert category.status_code == 201, category.text

        warehouse = client.post(
            "/api/v1/srm/inventory/warehouses",
            headers=headers,
            json={"warehouse_code": "MAIN", "warehouse_name": "Main Warehouse", "branch": "Main Branch"},
        )
        assert warehouse.status_code == 201, warehouse.text
        reserve_warehouse = client.post(
            "/api/v1/srm/inventory/warehouses",
            headers=headers,
            json={"warehouse_code": "RESERVE", "warehouse_name": "Reserve Warehouse", "branch": "Main Branch"},
        )
        assert reserve_warehouse.status_code == 201, reserve_warehouse.text

        product = client.post(
            "/api/v1/srm/inventory/items",
            headers=headers,
            json={
                "category_id": category.json()["id"],
                "default_warehouse_id": warehouse.json()["id"],
                "sku": "NOTE-A4-100",
                "item_name": "A4 Notebook",
                "barcode": "8901234567001",
                "category_name": "Stationery",
                "hsn_code": "4820",
                "gst_rate": 12,
                "purchase_rate": 40,
                "sales_rate": 64,
                "mrp": 75,
                "reorder_level": 10,
            },
        )
        assert product.status_code == 201, product.text
        assert product.json()["current_quantity"] == 0.0

        opening = client.post(
            "/api/v1/srm/inventory/opening-stock",
            headers=headers,
            json={
                "product_id": product.json()["id"],
                "warehouse_id": warehouse.json()["id"],
                "quantity": 25,
                "rate": 40,
                "movement_date": "2026-06-20",
            },
        )
        assert opening.status_code == 201, opening.text
        assert opening.json()["product"]["current_quantity"] == 25.0
        assert opening.json()["balance"]["quantity"] == 25.0

        listed = client.get("/api/v1/srm/inventory/items?search=note", headers=headers)
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["sku"] == "NOTE-A4-100"
        assert listed.json()["items"][0]["category"]["category_name"] == "Stationery"

        ops_product = client.post(
            "/api/v1/srm/inventory/items",
            headers=headers,
            json={
                "default_warehouse_id": warehouse.json()["id"],
                "sku": "OPS-STOCK-001",
                "item_name": "Operations Stock Item",
                "category_name": "Stationery",
                "purchase_rate": 20,
                "sales_rate": 30,
            },
        )
        assert ops_product.status_code == 201, ops_product.text
        ops_opening = client.post(
            "/api/v1/srm/inventory/opening-stock",
            headers=headers,
            json={"product_id": ops_product.json()["id"], "warehouse_id": warehouse.json()["id"], "quantity": 10, "rate": 20},
        )
        assert ops_opening.status_code == 201, ops_opening.text

        stock_in = client.post(
            "/api/v1/srm/inventory/stock-movements",
            headers=headers,
            json={"product_id": ops_product.json()["id"], "warehouse_id": warehouse.json()["id"], "movement_type": "stock_in", "quantity": 5, "rate": 21, "reference_number": "ADHOC-IN"},
        )
        assert stock_in.status_code == 201, stock_in.text
        assert stock_in.json()["product"]["current_quantity"] == 15.0

        stock_out = client.post(
            "/api/v1/srm/inventory/stock-movements",
            headers=headers,
            json={"product_id": ops_product.json()["id"], "warehouse_id": warehouse.json()["id"], "movement_type": "stock_out", "quantity": 2, "rate": 21, "reference_number": "ADHOC-OUT"},
        )
        assert stock_out.status_code == 201, stock_out.text
        assert stock_out.json()["product"]["current_quantity"] == 13.0

        transfer = client.post(
            "/api/v1/srm/inventory/stock-transfers",
            headers=headers,
            json={"product_id": ops_product.json()["id"], "from_warehouse_id": warehouse.json()["id"], "to_warehouse_id": reserve_warehouse.json()["id"], "quantity": 3, "rate": 21},
        )
        assert transfer.status_code == 201, transfer.text
        assert len(transfer.json()["movements"]) == 2
        assert transfer.json()["product"]["current_quantity"] == 13.0

        adjustment = client.post(
            "/api/v1/srm/inventory/stock-adjustments",
            headers=headers,
            json={"product_id": ops_product.json()["id"], "warehouse_id": reserve_warehouse.json()["id"], "quantity_in": 0, "quantity_out": 1, "rate": 21, "reason": "Cycle count"},
        )
        assert adjustment.status_code == 201, adjustment.text
        assert adjustment.json()["product"]["current_quantity"] == 12.0

        ops_detail = client.get(f"/api/v1/srm/inventory/items/{ops_product.json()['id']}", headers=headers)
        assert ops_detail.status_code == 200, ops_detail.text
        assert ops_detail.json()["ledger"][0]["movement_type"] == "stock_adjustment_out"
        assert sorted(balance["quantity"] for balance in ops_detail.json()["balances"]) == [2.0, 10.0]

        stock_sales_order = client.post(
            "/api/v1/srm/sales-orders",
            headers=headers,
            json={
                "title": "Counter sales order with stock",
                "customer_id": 1,
                "lines": [
                    {
                        "product_id": ops_product.json()["id"],
                        "description": "Operations Stock Item",
                        "service_type": "product",
                        "quantity": 2,
                        "unit_price": 30,
                    }
                ],
            },
        )
        assert stock_sales_order.status_code == 201, stock_sales_order.text
        submitted_order = client.post(f"/api/v1/srm/sales-orders/{stock_sales_order.json()['id']}/submit", headers=headers)
        assert submitted_order.status_code == 200, submitted_order.text
        confirmed_order = client.post(f"/api/v1/srm/sales-orders/{stock_sales_order.json()['id']}/confirm", headers=headers)
        assert confirmed_order.status_code == 200, confirmed_order.text

        ops_after_sales_order = client.get(f"/api/v1/srm/inventory/items/{ops_product.json()['id']}", headers=headers)
        assert ops_after_sales_order.status_code == 200, ops_after_sales_order.text
        assert ops_after_sales_order.json()["current_quantity"] == 10.0
        assert ops_after_sales_order.json()["ledger"][0]["movement_type"] == "sales_order_issue"

        confirmed_again = client.post(f"/api/v1/srm/sales-orders/{stock_sales_order.json()['id']}/confirm", headers=headers)
        assert confirmed_again.status_code == 200, confirmed_again.text
        ops_after_second_confirm = client.get(f"/api/v1/srm/inventory/items/{ops_product.json()['id']}", headers=headers)
        assert ops_after_second_confirm.status_code == 200, ops_after_second_confirm.text
        assert ops_after_second_confirm.json()["current_quantity"] == 10.0

        price_list = client.post(
            "/api/v1/srm/pricing/price-lists",
            headers=headers,
            json={
                "price_list_name": "Retail stationery prices",
                "channel": "retail",
                "customer_type": "cash",
                "effective_from": "2026-06-20",
                "priority": 10,
                "lines": [
                    {
                        "product_id": product.json()["id"],
                        "min_quantity": 1,
                        "price": 58,
                        "discount_percent": 5,
                    }
                ],
            },
        )
        assert price_list.status_code == 201, price_list.text
        assert price_list.json()["price_list_code"].startswith("PL-")
        assert price_list.json()["lines"][0]["sku"] == "NOTE-A4-100"

        price_lists = client.get("/api/v1/srm/pricing/price-lists", headers=headers)
        assert price_lists.status_code == 200, price_lists.text
        assert price_lists.json()["total"] == 1

        price_list_detail = client.get(f"/api/v1/srm/pricing/price-lists/{price_list.json()['id']}", headers=headers)
        assert price_list_detail.status_code == 200, price_list_detail.text
        assert price_list_detail.json()["lines"][0]["price"] == 58.0

        price_lookup = client.post(
            "/api/v1/srm/pricing/lookup",
            headers=headers,
            json={"product_ids": [product.json()["id"]], "channel": "retail", "customer_type": "cash", "price_date": "2026-06-20"},
        )
        assert price_lookup.status_code == 200, price_lookup.text
        assert price_lookup.json()["items"][0]["price_list_name"] == "Retail stationery prices"
        assert price_lookup.json()["items"][0]["net_price"] == 55.1

        batch = client.post(
            "/api/v1/srm/inventory/batches",
            headers=headers,
            json={
                "product_id": product.json()["id"],
                "warehouse_id": warehouse.json()["id"],
                "batch_number": "NOTE-JUN26",
                "manufacture_date": "2026-06-01",
                "expiry_date": "2027-06-01",
                "quantity": 25,
                "available_quantity": 25,
                "unit_cost": 40,
            },
        )
        assert batch.status_code == 201, batch.text
        assert batch.json()["batch_number"] == "NOTE-JUN26"
        assert batch.json()["product"]["sku"] == "NOTE-A4-100"

        serial = client.post(
            "/api/v1/srm/inventory/serial-numbers",
            headers=headers,
            json={
                "product_id": product.json()["id"],
                "warehouse_id": warehouse.json()["id"],
                "batch_id": batch.json()["id"],
                "serial_number": "NOTE-SER-0001",
                "reference_number": "OPENING",
            },
        )
        assert serial.status_code == 201, serial.text
        assert serial.json()["serial_number"] == "NOTE-SER-0001"
        assert serial.json()["batch"]["batch_number"] == "NOTE-JUN26"

        batch_detail = client.get(f"/api/v1/srm/inventory/batches/{batch.json()['id']}", headers=headers)
        assert batch_detail.status_code == 200, batch_detail.text
        assert batch_detail.json()["serial_count"] == 1
        assert batch_detail.json()["serials"][0]["serial_number"] == "NOTE-SER-0001"

        duplicate_serial = client.post(
            "/api/v1/srm/inventory/serial-numbers",
            headers=headers,
            json={"product_id": product.json()["id"], "serial_number": "NOTE-SER-0001"},
        )
        assert duplicate_serial.status_code == 409

        tracked_product = client.get(f"/api/v1/srm/inventory/items/{product.json()['id']}", headers=headers)
        assert tracked_product.status_code == 200, tracked_product.text
        assert tracked_product.json()["batch_tracking"] is True
        assert tracked_product.json()["serial_tracking"] is True
        assert tracked_product.json()["expiry_tracking"] is True

        component_product = client.post(
            "/api/v1/srm/inventory/items",
            headers=headers,
            json={
                "default_warehouse_id": warehouse.json()["id"],
                "sku": "COMP-PAPER-001",
                "item_name": "Notebook Paper Component",
                "category_name": "Stationery",
                "purchase_rate": 5,
                "sales_rate": 8,
            },
        )
        assert component_product.status_code == 201, component_product.text
        finished_product = client.post(
            "/api/v1/srm/inventory/items",
            headers=headers,
            json={
                "default_warehouse_id": warehouse.json()["id"],
                "sku": "KIT-NOTE-001",
                "item_name": "Notebook Kit",
                "category_name": "Stationery",
                "purchase_rate": 0,
                "sales_rate": 80,
            },
        )
        assert finished_product.status_code == 201, finished_product.text
        component_opening = client.post(
            "/api/v1/srm/inventory/opening-stock",
            headers=headers,
            json={"product_id": component_product.json()["id"], "warehouse_id": warehouse.json()["id"], "quantity": 20, "rate": 5},
        )
        assert component_opening.status_code == 201, component_opening.text

        bom = client.post(
            "/api/v1/srm/inventory/manufacturing/bom",
            headers=headers,
            json={
                "bom_name": "Notebook kit assembly",
                "finished_product_id": finished_product.json()["id"],
                "output_quantity": 1,
                "components": [
                    {
                        "component_product_id": component_product.json()["id"],
                        "warehouse_id": warehouse.json()["id"],
                        "quantity": 4,
                        "unit_cost": 5,
                    }
                ],
            },
        )
        assert bom.status_code == 201, bom.text
        assert bom.json()["bom_number"].startswith("BOM-")
        assert bom.json()["components"][0]["component_product"]["sku"] == "COMP-PAPER-001"

        production_order = client.post(
            "/api/v1/srm/inventory/manufacturing/orders",
            headers=headers,
            json={"bom_id": bom.json()["id"], "warehouse_id": warehouse.json()["id"], "planned_quantity": 2},
        )
        assert production_order.status_code == 201, production_order.text
        assert production_order.json()["production_number"].startswith("MFG-")

        production_post = client.post(
            f"/api/v1/srm/inventory/manufacturing/orders/{production_order.json()['id']}/post",
            headers=headers,
            json={"completed_quantity": 2, "warehouse_id": warehouse.json()["id"]},
        )
        assert production_post.status_code == 200, production_post.text
        assert production_post.json()["production_order"]["status"] == "completed"

        component_after_production = client.get(f"/api/v1/srm/inventory/items/{component_product.json()['id']}", headers=headers)
        assert component_after_production.status_code == 200, component_after_production.text
        assert component_after_production.json()["current_quantity"] == 12.0
        assert component_after_production.json()["ledger"][0]["movement_type"] == "production_consumption"

        finished_after_production = client.get(f"/api/v1/srm/inventory/items/{finished_product.json()['id']}", headers=headers)
        assert finished_after_production.status_code == 200, finished_after_production.text
        assert finished_after_production.json()["current_quantity"] == 2.0
        assert finished_after_production.json()["ledger"][0]["movement_type"] == "production_output"

        pos_sale = client.post(
            "/api/v1/srm/sales-orders",
            headers=headers,
            json={
                "order_number": "POS-STOCK-001",
                "title": "POS sale - Cash Customer",
                "customer_id": 1,
                "metadata_json": {"source": "pos", "payment_mode": "Cash"},
                "lines": [
                    {
                        "product_id": product.json()["id"],
                        "item_code": "NOTE-A4-100",
                        "description": "A4 Notebook",
                        "service_type": "product",
                        "quantity": 3,
                        "unit_price": 64,
                        "tax_amount": 23.04,
                    }
                ],
            },
        )
        assert pos_sale.status_code == 201, pos_sale.text

        detail = client.get(f"/api/v1/srm/inventory/items/{product.json()['id']}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["current_quantity"] == 22.0
        assert detail.json()["balances"][0]["quantity"] == 22.0
        assert detail.json()["ledger"][0]["movement_type"] == "pos_sale"
        assert detail.json()["ledger"][0]["reference_number"] == "POS-STOCK-001"

        returned = client.post(
            "/api/v1/srm/pos/returns",
            headers=headers,
            json={
                "sales_order_id": pos_sale.json()["id"],
                "customer_id": 1,
                "customer_name": "Cash Customer",
                "refund_method": "cash",
                "reason": "Customer returned sealed item",
                "lines": [
                    {
                        "sales_order_line_id": pos_sale.json()["lines"][0]["id"],
                        "product_id": product.json()["id"],
                        "quantity": 1,
                        "unit_price": 64,
                        "tax_amount": 7.68,
                        "restock": True,
                        "condition": "sellable",
                    }
                ],
            },
        )
        assert returned.status_code == 201, returned.text
        assert returned.json()["return_number"].startswith("RET-")
        assert returned.json()["refund_amount"] == 71.68

        after_return = client.get(f"/api/v1/srm/inventory/items/{product.json()['id']}", headers=headers)
        assert after_return.status_code == 200, after_return.text
        assert after_return.json()["current_quantity"] == 23.0
        assert after_return.json()["ledger"][0]["movement_type"] == "pos_return"

        over_return = client.post(
            "/api/v1/srm/pos/returns",
            headers=headers,
            json={
                "sales_order_id": pos_sale.json()["id"],
                "lines": [
                    {
                        "sales_order_line_id": pos_sale.json()["lines"][0]["id"],
                        "product_id": product.json()["id"],
                        "quantity": 3,
                        "unit_price": 64,
                    }
                ],
            },
        )
        assert over_return.status_code == 409

        purchase_order = client.post(
            "/api/v1/srm/procurement/purchase-orders",
            headers=headers,
            json={
                "vendor_id": 77,
                "vendor_name": "Notebook Supplier",
                "lines": [
                    {
                        "product_id": product.json()["id"],
                        "warehouse_id": warehouse.json()["id"],
                        "quantity": 10,
                        "unit_price": 38,
                        "tax_amount": 45.6,
                    }
                ],
            },
        )
        assert purchase_order.status_code == 201, purchase_order.text
        po_body = purchase_order.json()
        assert po_body["po_number"].startswith("PO-")
        assert po_body["status"] == "ordered"

        grn = client.post(
            "/api/v1/srm/procurement/grn",
            headers=headers,
            json={
                "purchase_order_id": po_body["id"],
                "reference_number": "SUP-DC-1",
                "lines": [
                    {
                        "purchase_order_line_id": po_body["lines"][0]["id"],
                        "quantity": 10,
                        "accepted_quantity": 10,
                        "unit_price": 38,
                        "tax_amount": 45.6,
                    }
                ],
            },
        )
        assert grn.status_code == 201, grn.text
        assert grn.json()["grn_number"].startswith("GRN-")

        after_grn = client.get(f"/api/v1/srm/inventory/items/{product.json()['id']}", headers=headers)
        assert after_grn.status_code == 200, after_grn.text
        assert after_grn.json()["current_quantity"] == 33.0
        assert after_grn.json()["ledger"][0]["movement_type"] == "grn_receipt"

        po_after_grn = client.get(f"/api/v1/srm/procurement/purchase-orders/{po_body['id']}", headers=headers)
        assert po_after_grn.status_code == 200, po_after_grn.text
        assert po_after_grn.json()["status"] == "received"
        assert po_after_grn.json()["lines"][0]["received_quantity"] == 10.0

        over_grn = client.post(
            "/api/v1/srm/procurement/grn",
            headers=headers,
            json={
                "purchase_order_id": po_body["id"],
                "lines": [
                    {
                        "purchase_order_line_id": po_body["lines"][0]["id"],
                        "quantity": 1,
                        "accepted_quantity": 1,
                        "unit_price": 38,
                    }
                ],
            },
        )
        assert over_grn.status_code == 409

        short_sale = client.post(
            "/api/v1/srm/sales-orders",
            headers=headers,
            json={
                "order_number": "POS-STOCK-002",
                "title": "POS sale - Short stock",
                "metadata_json": {"source": "pos", "payment_mode": "Cash"},
                "lines": [
                    {
                        "product_id": product.json()["id"],
                        "description": "A4 Notebook",
                        "service_type": "product",
                        "quantity": 99,
                        "unit_price": 64,
                    }
                ],
            },
        )
        assert short_sale.status_code == 409
    finally:
        delattr(app.state, "business_os_session_factory")
        delattr(app.state, "business_os_close_session")
