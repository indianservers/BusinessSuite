from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.apps.business_os.services.module_service import ensure_business_os_seed
from app.apps.srm.schema import ensure_srm_schema
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.user import Permission, Role, User


PASSWORD = "Password@123"
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("passlib").setLevel(logging.ERROR)
engine.echo = False
SMOKE_PERMISSIONS = [
    "srm_view",
    "srm_manage",
    "srm_admin",
    "srm_invoice_view",
    "srm_invoice_create",
    "srm_invoice_approve",
    "srm_collection_view",
    "srm_collection_create",
    "srm_profitability_view",
]


class SmokeFailure(RuntimeError):
    pass


class Smoke:
    def __init__(self, client: TestClient, prefix: str, verbose: bool = False):
        self.client = client
        self.prefix = prefix
        self.verbose = verbose
        self.headers: dict[str, str] = {}
        self.passed: list[str] = []

    def step(self, name: str, method: str, url: str, *, expected: int | set[int] = 200, json: dict[str, Any] | None = None) -> Any:
        expected_set = expected if isinstance(expected, set) else {expected}
        response = self.client.request(method, url, headers=self.headers, json=json)
        if response.status_code not in expected_set:
            raise SmokeFailure(f"{name} failed: {method} {url} returned {response.status_code}: {response.text}")
        body: Any
        try:
            body = response.json()
        except Exception:
            body = response.content
        self.passed.append(name)
        if self.verbose:
            print(f"PASS {name}: {response.status_code}")
        return body

    def assert_true(self, name: str, condition: bool, detail: str) -> None:
        if not condition:
            raise SmokeFailure(f"{name} failed: {detail}")
        self.passed.append(name)
        if self.verbose:
            print(f"PASS {name}")


def ensure_smoke_user(email: str) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_business_os_seed(db, company_id=1)
        ensure_srm_schema(db)

        role = db.query(Role).filter(Role.name == "srm_admin").first()
        if not role:
            role = Role(name="srm_admin", description="SRM admin", is_system=True)
            db.add(role)
            db.flush()

        permissions: list[Permission] = []
        for name in SMOKE_PERMISSIONS:
            permission = db.query(Permission).filter(Permission.name == name).first()
            if not permission:
                permission = Permission(name=name, description=name, module="srm")
                db.add(permission)
                db.flush()
            permissions.append(permission)
        role.permissions = permissions

        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, is_active=True, is_superuser=False, role_id=role.id)
            db.add(user)
        user.hashed_password = get_password_hash(PASSWORD)
        user.is_active = True
        user.role_id = role.id
        db.commit()
    finally:
        db.close()


def first_item(client: TestClient, headers: dict[str, str], url: str, label: str) -> dict[str, Any]:
    response = client.get(url, headers=headers)
    if response.status_code != 200:
        raise SmokeFailure(f"{label} listing failed: {response.status_code}: {response.text}")
    body = response.json()
    items = body if isinstance(body, list) else body.get("items", [])
    if not items:
        raise SmokeFailure(f"{label} listing returned no rows")
    return items[0]


def run_smoke(verbose: bool = False) -> dict[str, Any]:
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    prefix = f"SMOKE-{suffix}"
    email = f"srm.smoke.{suffix}@srmflow.com"
    ensure_smoke_user(email)

    with TestClient(app) as client:
        smoke = Smoke(client, prefix, verbose)
        token = smoke.step(
            "login smoke SRM admin",
            "POST",
            "/api/v1/auth/login",
            expected=200,
            json={"email": email, "password": PASSWORD, "module": "srm"},
        )["access_token"]
        smoke.headers = {"Authorization": f"Bearer {token}"}

        smoke.step("module info", "GET", "/api/v1/srm/module-info")

        category = smoke.step(
            "create category",
            "POST",
            "/api/v1/srm/inventory/categories",
            expected=201,
            json={"category_code": f"{prefix}-CAT", "category_name": f"{prefix} Retail Items"},
        )
        main_wh = smoke.step(
            "create main warehouse",
            "POST",
            "/api/v1/srm/inventory/warehouses",
            expected=201,
            json={"warehouse_code": f"{prefix}-MAIN", "warehouse_name": f"{prefix} Main Warehouse", "branch": "Smoke Branch"},
        )
        reserve_wh = smoke.step(
            "create reserve warehouse",
            "POST",
            "/api/v1/srm/inventory/warehouses",
            expected=201,
            json={"warehouse_code": f"{prefix}-RES", "warehouse_name": f"{prefix} Reserve Warehouse", "branch": "Smoke Branch"},
        )
        product = smoke.step(
            "create product master",
            "POST",
            "/api/v1/srm/inventory/items",
            expected=201,
            json={
                "category_id": category["id"],
                "default_warehouse_id": main_wh["id"],
                "sku": f"{prefix}-BOOK",
                "item_name": f"{prefix} Counter Book",
                "barcode": f"SMK{suffix}",
                "category_name": category["category_name"],
                "hsn_code": "4820",
                "gst_rate": 12,
                "purchase_rate": 40,
                "sales_rate": 64,
                "mrp": 75,
                "reorder_level": 5,
            },
        )
        smoke.step(
            "opening stock",
            "POST",
            "/api/v1/srm/inventory/opening-stock",
            expected=201,
            json={"product_id": product["id"], "warehouse_id": main_wh["id"], "quantity": 30, "rate": 40},
        )
        stock_detail = smoke.step("inventory item detail after opening", "GET", f"/api/v1/srm/inventory/items/{product['id']}")
        smoke.assert_true("opening stock persisted", stock_detail["current_quantity"] == 30.0, "expected quantity 30")

        smoke.step(
            "stock movement in",
            "POST",
            "/api/v1/srm/inventory/stock-movements",
            expected=201,
            json={"product_id": product["id"], "warehouse_id": main_wh["id"], "movement_type": "stock_in", "quantity": 5, "rate": 41, "reference_number": f"{prefix}-IN"},
        )
        smoke.step(
            "stock movement out",
            "POST",
            "/api/v1/srm/inventory/stock-movements",
            expected=201,
            json={"product_id": product["id"], "warehouse_id": main_wh["id"], "movement_type": "stock_out", "quantity": 2, "rate": 41, "reference_number": f"{prefix}-OUT"},
        )
        smoke.step(
            "stock transfer",
            "POST",
            "/api/v1/srm/inventory/stock-transfers",
            expected=201,
            json={"product_id": product["id"], "from_warehouse_id": main_wh["id"], "to_warehouse_id": reserve_wh["id"], "quantity": 3, "rate": 41},
        )
        smoke.step(
            "stock adjustment",
            "POST",
            "/api/v1/srm/inventory/stock-adjustments",
            expected=201,
            json={"product_id": product["id"], "warehouse_id": reserve_wh["id"], "quantity_out": 1, "rate": 41, "reason": "Smoke count"},
        )

        price_list = smoke.step(
            "create price list",
            "POST",
            "/api/v1/srm/pricing/price-lists",
            expected=201,
            json={
                "price_list_name": f"{prefix} Retail Price List",
                "channel": "retail",
                "customer_type": "cash",
                "priority": 50,
                "lines": [{"product_id": product["id"], "min_quantity": 1, "price": 58, "discount_percent": 5}],
            },
        )
        price_lookup = smoke.step(
            "price lookup",
            "POST",
            "/api/v1/srm/pricing/lookup",
            json={"product_ids": [product["id"]], "channel": "retail", "customer_type": "cash"},
        )
        smoke.assert_true("price lookup returns created list", price_lookup["items"][0]["price_list_id"] == price_list["id"], "lookup did not select smoke price list")

        batch = smoke.step(
            "create batch",
            "POST",
            "/api/v1/srm/inventory/batches",
            expected=201,
            json={"product_id": product["id"], "warehouse_id": main_wh["id"], "batch_number": f"{prefix}-BATCH", "quantity": 20, "available_quantity": 20, "unit_cost": 40},
        )
        smoke.step(
            "create serial number",
            "POST",
            "/api/v1/srm/inventory/serial-numbers",
            expected=201,
            json={"product_id": product["id"], "warehouse_id": main_wh["id"], "batch_id": batch["id"], "serial_number": f"{prefix}-SER-001", "reference_number": prefix},
        )

        purchase_order = smoke.step(
            "create purchase order",
            "POST",
            "/api/v1/srm/procurement/purchase-orders",
            expected=201,
            json={"vendor_id": 77, "vendor_name": f"{prefix} Supplier", "lines": [{"product_id": product["id"], "warehouse_id": main_wh["id"], "quantity": 10, "unit_price": 38, "tax_amount": 45.6}]},
        )
        smoke.step(
            "post GRN",
            "POST",
            "/api/v1/srm/procurement/grn",
            expected=201,
            json={"purchase_order_id": purchase_order["id"], "reference_number": f"{prefix}-DC", "lines": [{"purchase_order_line_id": purchase_order["lines"][0]["id"], "quantity": 10, "accepted_quantity": 10, "unit_price": 38, "tax_amount": 45.6}]},
        )

        component = smoke.step(
            "create manufacturing component",
            "POST",
            "/api/v1/srm/inventory/items",
            expected=201,
            json={"default_warehouse_id": main_wh["id"], "sku": f"{prefix}-COMP", "item_name": f"{prefix} Component", "category_name": category["category_name"], "purchase_rate": 5, "sales_rate": 8},
        )
        finished = smoke.step(
            "create manufacturing output item",
            "POST",
            "/api/v1/srm/inventory/items",
            expected=201,
            json={"default_warehouse_id": main_wh["id"], "sku": f"{prefix}-KIT", "item_name": f"{prefix} Finished Kit", "category_name": category["category_name"], "purchase_rate": 0, "sales_rate": 80},
        )
        smoke.step(
            "component opening stock",
            "POST",
            "/api/v1/srm/inventory/opening-stock",
            expected=201,
            json={"product_id": component["id"], "warehouse_id": main_wh["id"], "quantity": 20, "rate": 5},
        )
        bom = smoke.step(
            "create BOM",
            "POST",
            "/api/v1/srm/inventory/manufacturing/bom",
            expected=201,
            json={"bom_name": f"{prefix} Assembly", "finished_product_id": finished["id"], "output_quantity": 1, "components": [{"component_product_id": component["id"], "warehouse_id": main_wh["id"], "quantity": 4, "unit_cost": 5}]},
        )
        production_order = smoke.step(
            "create production order",
            "POST",
            "/api/v1/srm/inventory/manufacturing/orders",
            expected=201,
            json={"bom_id": bom["id"], "warehouse_id": main_wh["id"], "planned_quantity": 2},
        )
        smoke.step(
            "post production order",
            "POST",
            f"/api/v1/srm/inventory/manufacturing/orders/{production_order['id']}/post",
            json={"completed_quantity": 2, "warehouse_id": main_wh["id"]},
        )

        session = smoke.step(
            "open POS session",
            "POST",
            "/api/v1/srm/pos/sessions",
            expected=201,
            json={"opening_cash": 5000, "branch": "Smoke Branch", "register_name": f"{prefix} Register"},
        )["session"]
        smoke.step(
            "cash movement",
            "POST",
            "/api/v1/srm/pos/cash-movements",
            expected=201,
            json={"session_id": session["id"], "movement_type": "cash_in", "amount": 500, "reason": "Smoke float"},
        )
        held = smoke.step(
            "hold POS bill",
            "POST",
            "/api/v1/srm/pos/held-bills",
            expected=201,
            json={"session_id": session["id"], "customer_id": 1, "customer_name": "Cash Customer", "amount": 128, "item_count": 2, "cart_json": [{"id": product["id"], "name": product["item_name"], "sku": product["sku"], "qty": 2, "rate": 64}]},
        )
        smoke.step("recall POS held bill", "POST", f"/api/v1/srm/pos/held-bills/{held['id']}/recall")

        before_pos = smoke.step("inventory before POS sale", "GET", f"/api/v1/srm/inventory/items/{product['id']}")["current_quantity"]
        pos_sale = smoke.step(
            "create POS sale",
            "POST",
            "/api/v1/srm/sales-orders",
            expected=201,
            json={
                "order_number": f"{prefix}-POS",
                "title": "POS sale - Cash Customer",
                "customer_id": 1,
                "metadata_json": {"source": "pos", "payment_mode": "Cash", "session_id": session["id"]},
                "lines": [{"product_id": product["id"], "item_code": product["sku"], "description": product["item_name"], "service_type": "product", "quantity": 3, "unit_price": 64, "tax_amount": 23.04}],
            },
        )
        after_pos = smoke.step("inventory after POS sale", "GET", f"/api/v1/srm/inventory/items/{product['id']}")["current_quantity"]
        smoke.assert_true("POS sale deducted stock", Decimal(str(before_pos)) - Decimal(str(after_pos)) == Decimal("3.0"), "POS did not deduct 3 units")

        smoke.step(
            "create POS return",
            "POST",
            "/api/v1/srm/pos/returns",
            expected=201,
            json={"sales_order_id": pos_sale["id"], "session_id": session["id"], "customer_id": 1, "customer_name": "Cash Customer", "refund_method": "cash", "reason": "Smoke return", "lines": [{"sales_order_line_id": pos_sale["lines"][0]["id"], "product_id": product["id"], "quantity": 1, "unit_price": 64, "tax_amount": 7.68, "restock": True}]},
        )
        after_return = smoke.step("inventory after POS return", "GET", f"/api/v1/srm/inventory/items/{product['id']}")["current_quantity"]
        smoke.assert_true("POS return restocked", Decimal(str(after_return)) - Decimal(str(after_pos)) == Decimal("1.0"), "return did not restock 1 unit")

        before_confirm = smoke.step("inventory before normal sales order", "GET", f"/api/v1/srm/inventory/items/{product['id']}")["current_quantity"]
        normal_order = smoke.step(
            "create normal sales order",
            "POST",
            "/api/v1/srm/sales-orders",
            expected=201,
            json={"title": f"{prefix} Normal Sales Order", "customer_id": 101, "currency": "INR", "lines": [{"product_id": product["id"], "description": product["item_name"], "service_type": "product", "quantity": 2, "unit_price": 64, "tax_amount": 15.36}]},
        )
        smoke.step("submit normal sales order", "POST", f"/api/v1/srm/sales-orders/{normal_order['id']}/submit")
        confirmed = smoke.step("confirm normal sales order", "POST", f"/api/v1/srm/sales-orders/{normal_order['id']}/confirm")
        after_confirm = smoke.step("inventory after normal sales order", "GET", f"/api/v1/srm/inventory/items/{product['id']}")["current_quantity"]
        smoke.assert_true("confirmed order deducted stock", Decimal(str(before_confirm)) - Decimal(str(after_confirm)) == Decimal("2.0"), "confirm did not deduct 2 units")

        invoice = smoke.step("draft invoice from sales order", "POST", f"/api/v1/srm/invoices/draft-from-sales-order/{normal_order['id']}", expected=201)
        smoke.step("approve invoice", "POST", f"/api/v1/srm/invoices/{invoice['id']}/approve")
        smoke.step("send invoice", "POST", f"/api/v1/srm/invoices/{invoice['id']}/send")
        receipt = smoke.step("create receipt", "POST", "/api/v1/srm/receipts", expected=201, json={"customer_id": 101, "amount": invoice["balance_amount"], "reference_number": f"{prefix}-BANK"})
        smoke.step("confirm receipt", "POST", f"/api/v1/srm/receipts/{receipt['id']}/confirm")
        smoke.step("allocate receipt", "POST", f"/api/v1/srm/receipts/{receipt['id']}/allocate", json={"invoice_id": invoice["id"], "amount": invoice["balance_amount"]})

        smoke.step("sales order listing", "GET", "/api/v1/srm/sales-orders")
        smoke.step("invoice listing", "GET", "/api/v1/srm/invoices")
        smoke.step("receipt listing", "GET", "/api/v1/srm/receipts")
        smoke.step("collection aging", "GET", "/api/v1/srm/collections/aging")
        smoke.step("profitability snapshot", "GET", f"/api/v1/srm/profitability?engagement_id={confirmed['engagement']['id']}")
        smoke.step("SRM dashboard", "GET", "/api/v1/srm/dashboard")
        smoke.step("SRM reports", "GET", "/api/v1/srm/reports")

        smoke.step("close POS session", "POST", "/api/v1/srm/pos/cashier-closing", expected=201, json={"session_id": session["id"], "counted_cash": 5500, "notes": "Smoke balanced"})
        closed_session = first_item(client, smoke.headers, "/api/v1/srm/pos/sessions", "POS sessions")
        smoke.assert_true("POS session closed", closed_session["session"]["id"] == session["id"] and closed_session["session"]["status"] == "closed", "session did not close")

        return {
            "prefix": prefix,
            "email": email,
            "passed": smoke.passed,
            "counts": {
                "checks": len(smoke.passed),
                "product_id": product["id"],
                "sales_order_id": normal_order["id"],
                "pos_sale_id": pos_sale["id"],
                "invoice_id": invoice["id"],
                "receipt_id": receipt["id"],
                "pos_session_id": session["id"],
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed and verify live SRM Sales/POS smoke data.")
    parser.add_argument("--verbose", action="store_true", help="Print every passed check.")
    args = parser.parse_args()
    result = run_smoke(verbose=args.verbose)
    print(f"SRM Sales/POS smoke passed: {result['counts']['checks']} checks")
    print(f"Prefix: {result['prefix']}")
    print(f"Smoke login: {result['email']} / {PASSWORD}")
    for key, value in result["counts"].items():
        if key != "checks":
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
