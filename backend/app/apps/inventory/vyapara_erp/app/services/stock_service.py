from datetime import date
from decimal import Decimal

from flask import abort

from app.extensions import db
from app.models import CompanySetting, InventoryLedger, Product, Warehouse
from app.utils.helpers import money, qty


def _negative_stock_allowed():
    setting = CompanySetting.query.first()
    return bool(setting and setting.enable_negative_stock)


def _locked_product(product_id):
    # Serialize stock writers per product on databases that support row locks.
    return Product.query.filter_by(id=product_id).populate_existing().with_for_update().first_or_404()


def warehouse_quantity(product, warehouse_id):
    balances = dict(db.session.query(InventoryLedger.warehouse_id,
        db.func.sum(InventoryLedger.qty_in - InventoryLedger.qty_out))
        .filter_by(product_id=product.id).group_by(InventoryLedger.warehouse_id).all())
    available = qty(balances.get(warehouse_id, 0))
    if product.warehouse_id == warehouse_id:
        # Historical opening balances without movements belong to the default location.
        available += qty(product.current_stock) - sum((qty(v) for v in balances.values()), qty(0))
    return available


def add_inventory_entry(product, warehouse_id, movement_type, reference_type, reference_id, reference_no, qty_in=0, qty_out=0, rate=0, notes=None):
    if warehouse_id is not None:
        warehouse = db.session.get(Warehouse, int(warehouse_id))
        if not warehouse or not warehouse.status:
            abort(400, "Stock movements require an active warehouse")
    qty_in, qty_out, rate = qty(qty_in), qty(qty_out), Decimal(str(rate or 0))
    if qty_out > qty_in and not _negative_stock_allowed():
        location_id = int(warehouse_id) if warehouse_id is not None else None
        if warehouse_quantity(product, location_id) < qty_out - qty_in:
            abort(400, f"Insufficient stock for {product.name} in the selected warehouse")
    product.current_stock = qty(product.current_stock) + qty_in - qty_out
    if product.current_stock < 0 and not _negative_stock_allowed():
        abort(400, f"Insufficient stock for {product.name}")

    entry = InventoryLedger(
        date=date.today(),
        product_id=product.id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        reference_type=reference_type,
        reference_id=reference_id,
        reference_no=reference_no,
        qty_in=qty_in,
        qty_out=qty_out,
        balance_qty=product.current_stock,
        rate=rate,
        value=money((qty_in or qty_out) * rate),
        notes=notes,
    )
    db.session.add(entry)
    return entry


def apply_purchase_item(product_id, warehouse_id, quantity, rate, purchase_id, purchase_no):
    product = _locked_product(product_id)
    quantity, rate = qty(quantity), Decimal(str(rate or 0))
    old_qty = qty(product.current_stock)
    old_value = old_qty * Decimal(str(product.average_cost or 0))
    new_value = old_value + quantity * rate
    new_qty = old_qty + quantity
    product.average_cost = money(new_value / new_qty) if new_qty else money(rate)
    product.purchase_price = money(rate)
    add_inventory_entry(product, warehouse_id, "Purchase", "Purchase", purchase_id, purchase_no, qty_in=quantity, rate=rate)
    return product


def apply_sale_item(product_id, warehouse_id, quantity, sale_id, invoice_no):
    product = _locked_product(product_id)
    if not product.track_inventory:
        return Decimal("0")
    quantity = qty(quantity)
    if apply_composite_sale(product, warehouse_id, quantity, sale_id, invoice_no):
        return Decimal("0")
    cost = Decimal(str(product.average_cost or product.purchase_price or 0))
    add_inventory_entry(product, warehouse_id, "Sale", "Sale", sale_id, invoice_no, qty_out=quantity, rate=cost)
    return cost


def apply_stock_adjustment(product_id, warehouse_id, qty_in, qty_out, rate, adjustment_id, adjustment_no, reason):
    product = _locked_product(product_id)
    add_inventory_entry(product, warehouse_id, "Adjustment In" if qty(qty_in) else "Adjustment Out", "StockAdjustment", adjustment_id, adjustment_no, qty_in=qty_in, qty_out=qty_out, rate=rate, notes=reason)


def apply_stock_opening(product_id, warehouse_id, quantity, rate, opening_id, opening_no, notes=None):
    product = _locked_product(product_id)
    quantity = qty(quantity)
    rate = Decimal(str(rate or product.average_cost or product.purchase_price or 0))
    old_qty = qty(product.current_stock)
    old_value = old_qty * Decimal(str(product.average_cost or 0))
    new_qty = old_qty + quantity
    new_value = old_value + quantity * rate
    product.average_cost = money(new_value / new_qty) if new_qty else money(rate)
    return add_inventory_entry(product, warehouse_id, "Opening Stock", "StockOpening", opening_id, opening_no, qty_in=quantity, rate=rate, notes=notes)


def apply_stock_transfer(product_id, from_warehouse_id, to_warehouse_id, quantity, rate, transfer_id, transfer_no, notes=None):
    product = _locked_product(product_id)
    quantity = qty(quantity)
    rate = Decimal(str(rate or product.average_cost or product.purchase_price or 0))
    add_inventory_entry(product, from_warehouse_id, "Transfer Out", "StockTransfer", transfer_id, transfer_no, qty_out=quantity, rate=rate, notes=notes)
    add_inventory_entry(product, to_warehouse_id, "Transfer In", "StockTransfer", transfer_id, transfer_no, qty_in=quantity, rate=rate, notes=notes)


def apply_stock_transfer_out(product_id, from_warehouse_id, quantity, rate, transfer_id, transfer_no, notes=None):
    product = _locked_product(product_id)
    quantity = qty(quantity)
    rate = Decimal(str(rate or product.average_cost or product.purchase_price or 0))
    add_inventory_entry(product, from_warehouse_id, "Transfer Out", "StockTransfer", transfer_id, transfer_no, qty_out=quantity, rate=rate, notes=notes)


def apply_stock_transfer_in(product_id, to_warehouse_id, quantity, rate, transfer_id, transfer_no, notes=None):
    product = _locked_product(product_id)
    quantity = qty(quantity)
    rate = Decimal(str(rate or product.average_cost or product.purchase_price or 0))
    add_inventory_entry(product, to_warehouse_id, "Transfer In", "StockTransfer", transfer_id, transfer_no, qty_in=quantity, rate=rate, notes=notes)


def apply_composite_sale(product, warehouse_id, quantity, sale_id, invoice_no):
    quantity = qty(quantity)
    definition = next((item for item in product.composite_definition if item.status), None)
    if not definition:
        return False
    for component in definition.components.all():
        component_product = _locked_product(component.component_product_id)
        component_qty = qty(component.quantity) * quantity
        rate = Decimal(str(component_product.average_cost or component_product.purchase_price or 0))
        add_inventory_entry(component_product, warehouse_id, "Composite Sale", "Sale", sale_id, invoice_no, qty_out=component_qty, rate=rate, notes=f"Component for {product.sku}")
    return True


def apply_repacking_line(product_id, warehouse_id, line_type, quantity, rate, repack_id, repack_no, notes=None):
    product = _locked_product(product_id)
    quantity = qty(quantity)
    rate = Decimal(str(rate or product.average_cost or product.purchase_price or 0))
    if line_type == "Input":
        return add_inventory_entry(product, warehouse_id, "Repack Out", "Repacking", repack_id, repack_no, qty_out=quantity, rate=rate, notes=notes)
    return add_inventory_entry(product, warehouse_id, "Repack In", "Repacking", repack_id, repack_no, qty_in=quantity, rate=rate, notes=notes)


def apply_sales_return_item(product_id, warehouse_id, quantity, rate, return_id, return_no):
    product = _locked_product(product_id)
    old_qty, returned_qty = qty(product.current_stock), qty(quantity)
    total_qty = old_qty + returned_qty
    if total_qty:
        product.average_cost = money((old_qty * money(product.average_cost) + returned_qty * money(rate)) / total_qty)
    add_inventory_entry(product, warehouse_id, "Sales Return", "SalesReturn", return_id, return_no, qty_in=quantity, rate=rate)


def reverse_sale_item(product_id, warehouse_id, quantity, rate, sale_id, invoice_no, notes=None):
    product = _locked_product(product_id)
    issued = InventoryLedger.query.filter_by(product_id=product.id, reference_type="Sale", reference_id=sale_id, movement_type="Sale").first()
    if not issued and not product.track_inventory:
        return
    add_inventory_entry(product, warehouse_id, "Sale Cancellation", "Sale", sale_id, invoice_no, qty_in=quantity, rate=rate, notes=notes or "Invoice cancelled")


def apply_purchase_return_item(product_id, warehouse_id, quantity, rate, return_id, return_no):
    product = _locked_product(product_id)
    add_inventory_entry(product, warehouse_id, "Purchase Return", "PurchaseReturn", return_id, return_no, qty_out=quantity, rate=rate)
