"""Maintain existing receipt layers during authorized stock postings only."""
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from fastapi import HTTPException
from sqlalchemy import case, func, or_
from app.apps.fam.models import FAMInventoryValuationLayer as Layer, FAMStockMovement as Movement, FAMStockMovementLine as Line


def dec(value):
    return Decimal(str(value or 0))


def prepare(db, company, item, movement, warehouse, quantity_out, requested_rate):
    method = item.valuation_method or "weighted_average"
    if method not in {"weighted_average", "fifo"}:
        raise HTTPException(422, "This costing method requires identification data not supported by this stock document")
    if method == "fifo" and movement.movement_type in {"stock_transfer", "purchase_return", "sales_return"}:
        raise HTTPException(422, "FIFO transfers and returns require original receipt-layer provenance; this document cannot preserve it")
    layers = db.query(Layer).join(Movement, Movement.id == Layer.movement_id).filter(Layer.company_id == company, Movement.company_id == company, Layer.stock_item_id == item.id, Layer.remaining_quantity > 0, or_(Movement.status == "posted", Movement.id == movement.id)).order_by(Movement.movement_date, Layer.id).with_for_update().all()
    ledger_quantity, ledger_value = db.query(func.coalesce(func.sum(Line.quantity_in - Line.quantity_out), 0), func.coalesce(func.sum(case((Line.quantity_in > 0, Line.value), else_=-Line.value)), 0)).join(Movement, Movement.id == Line.movement_id).filter(Line.company_id == company, Movement.company_id == company, Line.stock_item_id == item.id, or_(Movement.status == "posted", Movement.id == movement.id)).one()
    if dec(ledger_quantity) != dec(item.current_quantity):
        raise HTTPException(409, "Stock balance and posted ledger disagree. Investigate before posting; no balance was repaired.")
    cached_value = dec(item.current_quantity) * dec(item.average_cost)
    # The cost cache has four decimal places; monetary movement values retain
    # the authoritative cents. Allow its representational rounding, not a repair.
    rounding_bound = abs(dec(item.current_quantity)) * Decimal("0.00005") + Decimal("0.01")
    if abs(cached_value - dec(ledger_value)) > rounding_bound:
        raise HTTPException(409, "Stock value cache and posted costs disagree. Investigate before posting.")
    layer_value = sum((dec(layer.remaining_value) for layer in layers), Decimal(0))
    complete = sum((dec(layer.remaining_quantity) for layer in layers), Decimal(0)) == max(dec(item.current_quantity), Decimal(0)) and abs(layer_value - max(dec(ledger_value), Decimal(0))) <= Decimal("0.01")
    if method == "fifo" and (not complete or any(layer.valuation_method != "fifo" for layer in layers)):
        raise HTTPException(409, "FIFO receipt layers do not reconcile with stock. Investigate existing layers before posting; no history was changed.")
    old_value = dec(ledger_value)
    rate = (dec(requested_rate) if requested_rate is not None else dec(item.average_cost)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    cost = None
    if quantity_out:
        rate = old_value / dec(item.current_quantity) if item.current_quantity else dec(item.average_cost)
        if method == "fifo":
            needed, cost = dec(quantity_out), Decimal(0)
            for layer in layers:
                if layer.warehouse_id != warehouse:
                    continue
                take = min(needed, dec(layer.remaining_quantity))
                cost += dec(layer.remaining_value) if take == dec(layer.remaining_quantity) else min(dec(layer.remaining_value), (take * dec(layer.unit_cost)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                needed -= take
                if not needed:
                    break
            if needed:
                raise HTTPException(409, "FIFO receipt layers do not cover the selected warehouse issue")
            cost = cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            rate = cost / dec(quantity_out)
    return method, layers, complete, old_value, rate, cost


def maintain(db, company, item, movement, line, layers, complete, method):
    """Never retrofit inconsistent legacy layers to make a report agree."""
    if not complete:
        if line.quantity_in:
            db.add(Layer(company_id=company, stock_item_id=item.id, warehouse_id=line.warehouse_id, movement_id=movement.id, movement_line_id=line.id, valuation_method=method, quantity=line.quantity_in, unit_cost=line.rate, layer_value=line.value, remaining_quantity=line.quantity_in, remaining_value=line.value))
        return
    remaining = dec(line.quantity_out)
    for layer in layers:
        if layer.warehouse_id != line.warehouse_id:
            continue
        previous_quantity = dec(layer.remaining_quantity)
        take = min(remaining, previous_quantity)
        allocated_value = dec(layer.remaining_value) if take == previous_quantity else min(dec(layer.remaining_value), (take * dec(layer.unit_cost)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        layer.remaining_quantity = previous_quantity - take
        remaining -= take
        if method == "fifo":
            layer.remaining_value = dec(layer.remaining_value) - allocated_value
        if not remaining:
            break
    if line.quantity_in:
        remaining_receipt = min(dec(line.quantity_in), max(dec(item.current_quantity), Decimal(0)))
        layer = Layer(company_id=company, stock_item_id=item.id, warehouse_id=line.warehouse_id, movement_id=movement.id, movement_line_id=line.id, valuation_method=method, quantity=line.quantity_in, unit_cost=line.rate, layer_value=line.value, remaining_quantity=remaining_receipt, remaining_value=remaining_receipt * dec(line.rate))
        db.add(layer)
        layers.append(layer)
    if method == "weighted_average":
        positive = [layer for layer in layers if layer.remaining_quantity > 0]
        for layer in layers:
            layer.remaining_value = Decimal(0)
        if positive and item.current_quantity >= 0:
            target = dec(line.balance_value)
            total_quantity = sum((dec(layer.remaining_quantity) for layer in positive), Decimal(0))
            shares = []
            for layer in positive:
                exact = target * dec(layer.remaining_quantity) / total_quantity
                layer.remaining_value = exact.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                shares.append((exact - layer.remaining_value, layer))
            cents = int((target - sum((dec(layer.remaining_value) for layer in positive), Decimal(0))) * 100)
            for _, layer in sorted(shares, key=lambda share: share[0], reverse=True)[:cents]:
                layer.remaining_value += Decimal("0.01")
