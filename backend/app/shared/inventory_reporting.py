"""Read-only inventory analytics over the existing Sales and Finance ledgers.

No balance repair, invoice-total valuation, or cross-realm consolidation occurs here.
Quantities remain Decimal until serialization; aggregation/paging happens in SQL.
"""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, and_, case, func, literal, or_, select


REPORTS = ("overview", "summary", "ledger", "valuation", "purchases", "sales", "reorder", "aging", "expiry", "adjustments", "transfers", "dead-stock", "reconciliation")


class InventoryReportFilters(BaseModel):
    report: Literal["overview", "summary", "ledger", "valuation", "purchases", "sales", "reorder", "aging", "expiry", "adjustments", "transfers", "dead-stock", "reconciliation"] = "overview"
    start_date: date | None = None
    end_date: date | None = None
    product_id: int | None = Field(None, gt=0)
    warehouse_id: int | None = Field(None, gt=0)
    category: str = Field("", max_length=180)
    search: str = Field("", max_length=160)
    transaction_type: str = Field("", max_length=80)
    movement_id: int | None = Field(None, gt=0)
    page: int = Field(1, ge=1)
    per_page: int = Field(25, ge=1, le=100)
    days: int = Field(90, ge=1, le=36500)
    sort: Literal["item_name", "sku", "quantity", "stock_value"] = "item_name"
    descending: bool = False


def number(value):
    return Decimal(str(value or 0))


def money(value):
    return number(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def serialize(row):
    return {key: float(value) if isinstance(value, Decimal) else value.isoformat() if isinstance(value, (date, datetime)) else value for key, value in dict(row).items()}


def scoped_sources(db, user, source, filters):
    """Return scoped item, warehouse and normalized *posted* movement relations."""
    if db.info.get("business_pack_scope") is not None:
        raise HTTPException(503, "Use the selected Business Pack's native inventory reports; shared ledgers cannot represent its stock")
    if source == "srm":
        from app.apps.srm.models import SRMProduct as Item, SRMWarehouse as Warehouse, SRMInventoryMovement as Movement
        from app.apps.srm.api.router import _org
        from app.shared.catalog import restrict_workspaces
        from app.shared.catalog_branches import availability_clause, selected_branch
        company = _org(user)
        items = db.query(Item).filter(Item.organization_id == company, Item.deleted_at.is_(None), Item.product_type.notin_(["service", "membership", "subscription", "bundle"]))
        items = restrict_workspaces(items, Item, db, user).filter(availability_clause(Item, selected_branch(user)))
        raw_currency = func.upper(func.coalesce(Item.metadata_json["currency"].as_string(), "INR"))
        currency = case((and_(func.length(raw_currency) == 3, *(func.substr(raw_currency, index, 1).between("A", "Z") for index in (1, 2, 3))), raw_currency), else_=None)
        category = Item.category_id
        products = items.with_entities(Item.id.label("product_id"), Item.sku, Item.item_name, category.label("category"), Item.unit_code.label("unit"), Item.reorder_level, Item.min_stock, Item.max_stock, Item.track_inventory, currency.label("currency"), literal("weighted_average").label("valuation_method"), Item.current_quantity.label("stored_quantity"), Item.average_cost.label("stored_cost")).subquery()
        warehouses = db.query(Warehouse.id.label("warehouse_id"), Warehouse.warehouse_name).filter(Warehouse.organization_id == company).subquery()
        movements = db.query(Movement.id.label("id"), Movement.id.label("movement_id"), Movement.product_id, Movement.warehouse_id, Movement.movement_date, Movement.movement_number, Movement.movement_type, Movement.quantity_in, Movement.quantity_out, Movement.rate, Movement.value, Movement.reference_number, Movement.notes.label("notes"), Movement.created_by, Movement.created_by.label("posted_by"), literal("posted").label("status"), literal("srm").label("source_module"), literal(None).label("source_record_type"), literal(None).label("source_record_id")).filter(Movement.organization_id == company)
    else:
        from app.apps.fam.models import FAMStockItem as Item, FAMWarehouse as Warehouse, FAMStockMovement as Movement, FAMStockMovementLine as Line, FAMCompanyFinancialSettings, FAMUnitOfMeasure as Unit
        from app.apps.fam.api.router import bootstrap
        company = bootstrap(db, user)
        settings = db.query(FAMCompanyFinancialSettings).filter_by(company_id=company).first()
        currency = settings.base_currency if settings else None
        products = db.query(Item.id.label("product_id"), Item.sku, Item.item_name, Item.stock_group_id.label("category"), Unit.unit_code.label("unit"), Item.reorder_level, Item.min_stock, Item.max_stock, Item.track_inventory, literal(currency).label("currency"), Item.valuation_method, Item.current_quantity.label("stored_quantity"), Item.average_cost.label("stored_cost")).outerjoin(Unit, and_(Unit.id == Item.unit_id, Unit.company_id == company)).filter(Item.company_id == company).subquery()
        warehouses = db.query(Warehouse.id.label("warehouse_id"), Warehouse.warehouse_name).filter(Warehouse.company_id == company).subquery()
        movements = db.query(Line.id.label("id"), Movement.id.label("movement_id"), Line.stock_item_id.label("product_id"), Line.warehouse_id, Movement.movement_date, Movement.movement_number, Movement.movement_type, Line.quantity_in, Line.quantity_out, Line.rate, Line.value, Movement.reference_number, Movement.narration.label("notes"), Movement.created_by, Movement.posted_by, Movement.status, Movement.source_module, Movement.source_record_type, Movement.source_record_id).join(Movement, Movement.id == Line.movement_id).filter(Line.company_id == company, Movement.company_id == company, Movement.status == "posted")
    raw = movements.subquery()
    p, w, m = products.c, warehouses.c, raw.c
    base = db.query(*raw.c, p.sku, p.item_name, p.category, p.unit, p.currency, p.valuation_method, w.warehouse_name).join(products, p.product_id == m.product_id).join(warehouses, w.warehouse_id == m.warehouse_id)
    if filters.product_id:
        base = base.filter(m.product_id == filters.product_id)
    if filters.warehouse_id:
        base = base.filter(m.warehouse_id == filters.warehouse_id)
    if filters.category:
        base = base.filter(func.cast(p.category, String) == filters.category)
    if filters.search:
        pattern = "%" + filters.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        # Search narrows items, never the history used to calculate their balance.
        base = base.filter(or_(p.sku.ilike(pattern, escape="\\"), p.item_name.ilike(pattern, escape="\\")))
    base = base.filter(m.movement_date <= (filters.end_date or date.today()))
    return company, products, base.subquery()


def page_rows(db, query, filters):
    total = query.order_by(None).count()
    rows = query.offset((filters.page - 1) * filters.per_page).limit(filters.per_page).all()
    return {"items": [serialize(row._mapping) for row in rows], "total": total, "page": filters.page, "per_page": filters.per_page}


PURCHASE = ("purchase_receipt", "stock_in")
PURCHASE_RETURN = ("purchase_return", "purchase_return_issue")
SALE = ("delivery_note", "stock_out", "cogs_issue", "sales_order_issue", "pos_sale")
SALE_RETURN = ("sales_return", "sales_return_receipt", "pos_return")
TRANSFER = ("stock_transfer", "transfer_in", "transfer_out", "stock_transfer_in", "stock_transfer_out")


def inventory_analysis(db, user, source, filters):
    if filters.start_date and filters.end_date and filters.start_date > filters.end_date:
        raise HTTPException(422, "Start date must not follow end date")
    company, products, base = scoped_sources(db, user, source, filters)
    b, p = base.c, products.c
    signed = b.quantity_in - b.quantity_out
    signed_value = case((b.quantity_in > 0, b.value), else_=-b.value)
    in_period = b.movement_date >= filters.start_date if filters.start_date else literal(True)
    report = filters.report
    meta = {"source": source, "report": report, "as_of": (filters.end_date or date.today()).isoformat(), "filters": filters.model_dump(mode="json"), "quantity_basis": "posted_stock_movements_in_base_unit", "value_basis": "recorded_movement_cost_excluding_sales_tax", "available_reports": REPORTS, "warnings": ["Sales and Finance stock are separate ledgers. No cross-ledger consolidation is applied."]}
    if filters.transaction_type and report not in {"ledger", "adjustments", "transfers", "purchases", "sales"}:
        raise HTTPException(422, "Transaction type filters apply to transaction reports; a partial ledger must not be presented as closing stock")
    if report in {"ledger", "adjustments", "transfers", "purchases", "sales"}:
        partition = [b.product_id, b.warehouse_id]
        ordering = [b.movement_date, b.movement_id, b.id]
        running = func.sum(signed).over(partition_by=partition, order_by=ordering, rows=(None, 0))
        running_value = func.sum(signed_value).over(partition_by=partition, order_by=ordering, rows=(None, 0))
        ledger = db.query(*base.c, (running - signed).label("opening_quantity"), running.label("closing_quantity"), running_value.label("stock_value")).subquery()
        l = ledger.c
        query = db.query(*ledger.c)
        if filters.start_date:
            query = query.filter(l.movement_date >= filters.start_date)
        kinds = {"purchases": PURCHASE + PURCHASE_RETURN, "sales": SALE + SALE_RETURN, "transfers": TRANSFER}
        if report in kinds:
            query = query.filter(l.movement_type.in_(kinds[report]))
        if report == "adjustments":
            query = query.filter(or_(l.movement_type.ilike("%adjust%"), l.movement_type.in_(["opening_stock", "damaged", "write_off", "lost_stock"])))
        if filters.transaction_type:
            query = query.filter(l.movement_type == filters.transaction_type)
        if filters.movement_id:
            query = query.filter(l.movement_id == filters.movement_id)
        result = page_rows(db, query.order_by(l.movement_date, l.movement_id, l.id), filters)
        for row in result["items"]:
            row["id"] = f"{source}:movement:{row['id']}"
            row["source_url"] = f"/{source}/inventory/reports?report=ledger&movement_id={row['movement_id']}"
        if report == "sales":
            meta["warnings"].append("Stock issue value is recorded cost, not sales revenue. Invoice revenue and refunds require explicit source attribution; no profit is inferred here.")
        return {**meta, **result}
    grouped = db.query(b.product_id, b.warehouse_id, b.sku, b.item_name, b.category, b.unit, b.currency, b.valuation_method, b.warehouse_name,
        func.sum(case((or_(~in_period, b.movement_type == "opening_stock"), signed), else_=0)).label("opening_quantity"),
        func.sum(signed).label("quantity"), func.sum(signed_value).label("stock_value"),
        func.sum(case((and_(in_period, b.movement_type != "opening_stock"), b.quantity_in), else_=0)).label("quantity_in"),
        func.sum(case((and_(in_period, b.movement_type != "opening_stock"), b.quantity_out), else_=0)).label("quantity_out"),
        func.sum(case((and_(in_period, b.movement_type.in_(PURCHASE)), b.quantity_in), else_=0)).label("purchases"),
        func.sum(case((and_(in_period, b.movement_type.in_(PURCHASE_RETURN)), b.quantity_out), else_=0)).label("purchase_returns"),
        func.sum(case((and_(in_period, b.movement_type.in_(SALE)), b.quantity_out), else_=0)).label("sales"),
        func.sum(case((and_(in_period, b.movement_type.in_(SALE_RETURN)), b.quantity_in), else_=0)).label("sales_returns"),
        func.sum(case((and_(in_period, b.movement_type.in_(TRANSFER)), b.quantity_in), else_=0)).label("transfers_in"),
        func.sum(case((and_(in_period, b.movement_type.in_(TRANSFER)), b.quantity_out), else_=0)).label("transfers_out"),
        func.max(case((b.movement_type.in_(SALE), b.movement_date), else_=None)).label("last_sale_date"),
        func.max(b.movement_date).label("last_movement_date")
    ).group_by(b.product_id, b.warehouse_id, b.sku, b.item_name, b.category, b.unit, b.currency, b.valuation_method, b.warehouse_name).subquery()
    g = grouped.c
    if source == "fam":
        from app.apps.fam.models import FAMInventoryReservation as Reservation
        reserved = db.query(Reservation.stock_item_id.label("product_id"), Reservation.warehouse_id, func.sum(Reservation.reserved_quantity).label("reserved_quantity")).filter(Reservation.company_id == company, Reservation.status == "active", or_(Reservation.expires_at.is_(None), Reservation.expires_at > datetime.now(timezone.utc))).group_by(Reservation.stock_item_id, Reservation.warehouse_id).subquery()
        unallocated = db.query(Reservation.stock_item_id.label("product_id"), func.sum(Reservation.reserved_quantity).label("quantity")).filter(Reservation.company_id == company, Reservation.status == "active", Reservation.warehouse_id.is_(None), or_(Reservation.expires_at.is_(None), Reservation.expires_at > datetime.now(timezone.utc))).group_by(Reservation.stock_item_id).subquery()
        reservation_known = and_(func.coalesce(unallocated.c.quantity, 0) == 0, literal(not filters.end_date or filters.end_date == date.today()))
        reserved_value = case((reservation_known, func.coalesce(reserved.c.reserved_quantity, 0)), else_=None)
        query = db.query(*grouped.c, reserved_value.label("reserved_quantity"), (g.quantity - reserved_value).label("available_quantity"), p.min_stock, p.max_stock, p.reorder_level).join(products, p.product_id == g.product_id).outerjoin(reserved, and_(reserved.c.product_id == g.product_id, reserved.c.warehouse_id == g.warehouse_id)).outerjoin(unallocated, unallocated.c.product_id == g.product_id)
        meta["warnings"].append("Unallocated reservations cannot be assigned to an individual warehouse; historical reservation balances are unavailable.")
    else:
        query = db.query(*grouped.c, literal(None).label("reserved_quantity"), literal(None).label("available_quantity"), p.min_stock, p.max_stock, p.reorder_level).join(products, p.product_id == g.product_id)
        meta["warnings"].append("Sales has no stock reservation balance in this ledger. Available quantity is unknown, not assumed equal to physical stock.")
    if report == "dead-stock":
        from datetime import timedelta
        query = query.filter(g.quantity > 0, or_(g.last_sale_date.is_(None), g.last_sale_date < (filters.end_date or date.today()) - timedelta(days=filters.days)))
    if report == "reorder":
        threshold = case((p.reorder_level > 0, p.reorder_level), else_=p.min_stock)
        quantity_for_reorder = func.coalesce(g.quantity - reserved_value, g.quantity) if source == "fam" else g.quantity
        query = query.filter(threshold > 0, quantity_for_reorder <= threshold)
        meta["warnings"].append("Reorder uses allocated available stock when known, otherwise physical stock. Thresholds are item settings applied per warehouse. Lead time and preferred supplier rules are not configured in this ledger.")
    if report == "reconciliation":
        return {**meta, **reconcile(db, user, source, company, products, base, filters)}
    if report == "aging":
        return {**meta, **receipt_aging(db, base, grouped, filters)}
    if report == "expiry":
        return {**meta, **expiry(db, source, company, products, filters)}
    if report == "overview":
        totals = db.query(g.currency, func.sum(g.stock_value).label("stock_value"), func.sum(g.quantity).label("quantity"), func.count().label("positions"), func.sum(case((g.quantity < 0, 1), else_=0)).label("negative_positions")).group_by(g.currency).all()
        trends = db.query(b.movement_date, b.currency, func.sum(b.quantity_in).label("quantity_in"), func.sum(b.quantity_out).label("quantity_out"), func.sum(signed_value).label("value_change")).filter(in_period).group_by(b.movement_date, b.currency).order_by(b.movement_date.desc()).limit(90).all()
        return {**meta, **page_rows(db, query.order_by(g.item_name, g.product_id, g.warehouse_id), filters), "totals_by_currency": [{**serialize(r._mapping), "stock_value": float(r.stock_value) if r.currency else None} for r in totals], "trends": [serialize(r._mapping) for r in reversed(trends)], "total_products": db.query(func.count(func.distinct(g.product_id))).scalar(), "warnings": meta["warnings"] + ["Quantity totals combine base units; compare individual item units before interpreting totals."]}
    sort_column = getattr(g, filters.sort)
    result = page_rows(db, query.order_by(sort_column.desc() if filters.descending else sort_column.asc(), g.product_id, g.warehouse_id), filters)
    for row in result["items"]:
        row["id"] = f"{source}:{row['product_id']}:{row['warehouse_id']}"
        row["average_cost"] = float((number(row["stock_value"]) / number(row["quantity"])).quantize(Decimal("0.0001"))) if row["quantity"] else None
        row["adjustments_and_other"] = float(number(row["quantity_in"]) - number(row["quantity_out"]) - number(row["purchases"]) + number(row["purchase_returns"]) + number(row["sales"]) - number(row["sales_returns"]) - number(row["transfers_in"]) + number(row["transfers_out"]))
        row["source_url"] = f"/{source}/inventory/reports?report=ledger&product_id={row['product_id']}&warehouse_id={row['warehouse_id']}"
    if report == "valuation":
        meta["warnings"].append("Values reproduce posted movement costs. The method shown is the current item configuration; historical method changes are not inferred. Specific identification requires lot/serial cost provenance.")
    return {**meta, **result}


def reconcile(db, user, source, company, products, base, filters):
    """Compare independently stored current balances with ledger sums; never repair."""
    if filters.end_date and filters.end_date != date.today():
        raise HTTPException(422, "Stored balances are current. Historical reconciliation requires a stored snapshot; use historical valuation instead.")
    b, p = base.c, products.c
    totals = db.query(b.product_id, func.sum(b.quantity_in - b.quantity_out).label("expected_quantity"), func.sum(case((b.quantity_in > 0, b.value), else_=-b.value)).label("expected_value")).group_by(b.product_id).subquery()
    if source == "srm":
        from app.apps.srm.models import SRMInventoryBalance as Balance
        ledger_totals = db.query(b.product_id, b.warehouse_id, func.sum(b.quantity_in - b.quantity_out).label("expected_quantity"), func.sum(case((b.quantity_in > 0, b.value), else_=-b.value)).label("expected_value")).group_by(b.product_id, b.warehouse_id).subquery()
        balances = db.query(Balance.product_id, Balance.warehouse_id, Balance.quantity.label("actual_quantity"), (Balance.quantity * Balance.average_cost).label("actual_value")).filter(Balance.organization_id == company)
        if filters.warehouse_id:
            balances = balances.filter(Balance.warehouse_id == filters.warehouse_id)
        actual = balances.subquery()
        keys = select(ledger_totals.c.product_id.label("product_id"), ledger_totals.c.warehouse_id.label("warehouse_id")).union(select(actual.c.product_id.label("product_id"), actual.c.warehouse_id.label("warehouse_id"))).subquery()
        totals = ledger_totals
        aq, av = func.coalesce(actual.c.actual_quantity, 0), func.coalesce(actual.c.actual_value, 0)
        query = db.query(p.product_id, p.sku, p.item_name, keys.c.warehouse_id, func.coalesce(totals.c.expected_quantity, 0).label("expected_quantity"), func.coalesce(totals.c.expected_value, 0).label("expected_value"), aq.label("actual_quantity"), av.label("actual_value"), (aq - func.coalesce(totals.c.expected_quantity, 0)).label("quantity_difference"), (av - func.coalesce(totals.c.expected_value, 0)).label("value_difference")).select_from(products).join(keys, keys.c.product_id == p.product_id).outerjoin(totals, and_(totals.c.product_id == keys.c.product_id, totals.c.warehouse_id == keys.c.warehouse_id)).outerjoin(actual, and_(actual.c.product_id == keys.c.product_id, actual.c.warehouse_id == keys.c.warehouse_id))
    else:
        if filters.warehouse_id:
            raise HTTPException(422, "Finance stores item balances across warehouses. Remove the warehouse filter to compare the stored balance.")
        aq, av = p.stored_quantity, p.stored_quantity * p.stored_cost
        query = db.query(p.product_id, p.sku, p.item_name, totals.c.expected_quantity, totals.c.expected_value, aq.label("actual_quantity"), av.label("actual_value"), (aq - func.coalesce(totals.c.expected_quantity, 0)).label("quantity_difference"), (av - func.coalesce(totals.c.expected_value, 0)).label("value_difference")).outerjoin(totals, totals.c.product_id == p.product_id)
    if filters.search or filters.category:
        # Search/category filters on movements cannot safely limit a balance comparison.
        raise HTTPException(422, "Reconciliation accepts product and warehouse filters; remove search/category to compare the complete ledger")
    if filters.product_id:
        query = query.filter(p.product_id == filters.product_id)
    query = query.filter(or_(func.abs(aq - func.coalesce(totals.c.expected_quantity, 0)) > Decimal("0.0005"), func.abs(av - func.coalesce(totals.c.expected_value, 0)) > Decimal("0.01"), aq < 0))
    if source == "fam":
        from app.apps.fam.models import FAMInventoryValuationLayer as Layer, FAMStockMovement as Header
        layer_totals = db.query(Layer.stock_item_id.label("product_id"), func.sum(Layer.remaining_quantity).label("quantity"), func.sum(Layer.remaining_value).label("value")).join(Header, Header.id == Layer.movement_id).filter(Layer.company_id == company, Header.company_id == company, Header.status == "posted").group_by(Layer.stock_item_id).subquery()
        expected_q = case((p.stored_quantity < 0, 0), else_=p.stored_quantity)
        expected_v = case((p.stored_quantity < 0, 0), else_=p.stored_quantity * p.stored_cost)
        layer_q, layer_v = func.coalesce(layer_totals.c.quantity, 0), func.coalesce(layer_totals.c.value, 0)
        layer_query = db.query(p.product_id, p.sku, p.item_name, expected_q.label("expected_quantity"), expected_v.label("expected_value"), layer_q.label("actual_quantity"), layer_v.label("actual_value"), (layer_q - expected_q).label("quantity_difference"), (layer_v - expected_v).label("value_difference"), literal("Receipt layer/balance mismatch").label("issue_type"), literal(None).label("warehouse_id")).outerjoin(layer_totals, layer_totals.c.product_id == p.product_id).filter(or_(func.abs(layer_q - expected_q) > Decimal("0.0005"), func.abs(layer_v - expected_v) > Decimal("0.01")))
        if filters.product_id:
            layer_query = layer_query.filter(p.product_id == filters.product_id)
        combined = query.add_columns(literal("Ledger/balance mismatch").label("issue_type"), literal(None).label("warehouse_id")).statement.union_all(layer_query.statement).subquery()
        query = db.query(*combined.c)
    result = page_rows(db, query.order_by("sku", "product_id"), filters)
    for row in result["items"]:
        row.update(id=f"audit:{row['product_id']}:{row.get('warehouse_id','all')}:{row.get('issue_type','balance')}", issue_type="Negative stock" if number(row["actual_quantity"]) < 0 else row.get("issue_type", "Ledger/balance mismatch"), investigation="Inspect posted movement references and authorized adjustments; do not edit historical records.", source_url=f"/{source}/inventory/reports?report=ledger&product_id={row['product_id']}")
    return result


def receipt_aging(db, base, grouped, filters):
    b, g = base.c, grouped.c
    # Infer remaining receipts by FIFO depletion. This is an age allocation,
    # not a claim that FIFO accounting or original transfer layers were posted.
    receipts = db.query(b.product_id, b.warehouse_id, b.movement_date, b.id, b.quantity_in,
        func.sum(b.quantity_in).over(partition_by=[b.product_id, b.warehouse_id], order_by=[b.movement_date.desc(), b.movement_id.desc(), b.id.desc()], rows=(None, 0)).label("newer_receipts")).filter(b.quantity_in > 0).subquery()
    r = receipts.c
    remaining = case((g.quantity <= r.newer_receipts - r.quantity_in, 0), (g.quantity >= r.newer_receipts, r.quantity_in), else_=g.quantity - (r.newer_receipts - r.quantity_in))
    query = db.query(g.product_id, g.warehouse_id, g.sku, g.item_name, g.warehouse_name, r.movement_date.label("receipt_date"), remaining.label("remaining_quantity"), r.id.label("id")).join(receipts, and_(r.product_id == g.product_id, r.warehouse_id == g.warehouse_id)).filter(g.quantity > 0, remaining > 0)
    result = page_rows(db, query.order_by(r.movement_date, r.id), filters)
    for row in result["items"]:
        age = ((filters.end_date or date.today()) - date.fromisoformat(row["receipt_date"])).days
        row.update(age_days=age, age_bucket="0â€“30" if age <= 30 else "31â€“60" if age <= 60 else "61â€“90" if age <= 90 else "91â€“180" if age <= 180 else "Above 180")
    return {**result, "age_basis": "receipt_dates_with_inferred_FIFO_depletion", "limitations": "Receipt age is reconstructed from posted movements. Transfers use receipt date at destination; original lot provenance and specific identification are not available."}


def expiry(db, source, company, products, filters):
    if filters.end_date and filters.end_date != date.today():
        raise HTTPException(422, "Batch balances are current; historical batch quantities require lot snapshots")
    if source != "srm":
        return {"items": [], "total": 0, "supported": False, "limitations": "Finance stock movements have no batch or expiry identity. Use Sales batch inventory; no expiry values are inferred."}
    from app.apps.srm.models import SRMInventoryBatch as Batch
    p = products.c
    query = db.query(Batch.id, Batch.product_id, Batch.warehouse_id, p.sku, p.item_name, p.currency, Batch.batch_number, Batch.manufacture_date, Batch.expiry_date, Batch.available_quantity.label("quantity"), (Batch.available_quantity * Batch.unit_cost).label("stock_value"), Batch.status).join(products, p.product_id == Batch.product_id).filter(Batch.organization_id == company)
    if filters.product_id:
        query = query.filter(Batch.product_id == filters.product_id)
    if filters.warehouse_id:
        query = query.filter(Batch.warehouse_id == filters.warehouse_id)
    if filters.search:
        query = query.filter(or_(p.sku.ilike("%" + filters.search + "%"), p.item_name.ilike("%" + filters.search + "%")))
    if filters.category:
        query = query.filter(func.cast(p.category, String) == filters.category)
    result = page_rows(db, query.order_by(Batch.expiry_date, Batch.id), filters)
    for row in result["items"]:
        row["days_until_expiry"] = (date.fromisoformat(row["expiry_date"]) - (filters.end_date or date.today())).days if row["expiry_date"] else None
    return {**result, "supported": True}


def inventory_report_response(db, user, source, filters, export_format=None):
    if not export_format:
        return inventory_analysis(db, user, source, filters)
    from io import BytesIO
    from fastapi.responses import Response
    first = inventory_analysis(db, user, source, filters.model_copy(update={"page": 1, "per_page": 100}))
    if first["total"] > 5000:
        raise HTTPException(413, "This export exceeds 5,000 records. Narrow the filters; background exports are not yet available.")
    rows = first["items"]
    for page in range(2, (first["total"] + 99) // 100 + 1):
        rows.extend(inventory_analysis(db, user, source, filters.model_copy(update={"page": page, "per_page": 100}))["items"])
    columns = list(rows[0]) if rows else ["No matching records"]
    stream = BytesIO()
    if export_format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        book = Workbook()
        sheet = book.active
        sheet.title = "Inventory report"
        sheet.append([f"{source.upper()} inventory: {filters.report}"])
        sheet.append([f"As of {first['as_of']}; source: posted movements. Filters: {filters.model_dump_json()}"])
        for warning in first.get("warnings", []) + ([first["limitations"]] if first.get("limitations") else []):
            sheet.append([warning])
        header_row = sheet.max_row + 1
        sheet.append(columns)
        for cell in sheet[header_row]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="343B53")
        for row in rows:
            sheet.append([row.get(key) for key in columns])
            for cell in sheet[sheet.max_row]:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
        sheet.freeze_panes = f"A{header_row + 1}"
        sheet.auto_filter.ref = f"A{header_row}:{sheet.cell(sheet.max_row, len(columns)).coordinate}"
        from openpyxl.utils import get_column_letter
        for index in range(1, len(columns) + 1):
            sheet.column_dimensions[get_column_letter(index)].width = 23
        book.save(stream)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        from xml.sax.saxutils import escape
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        styles = getSampleStyleSheet()
        identity = [key for key in ("sku", "item_name") if key in columns]
        rest = [key for key in columns if key not in identity]
        groups = [identity + rest[index:index + 6] for index in range(0, len(rest), 6)] or [columns]
        elements = []
        style = styles["BodyText"]
        style.fontSize, style.leading = 7, 9
        for section, chosen in enumerate(groups):
            if section:
                elements.append(PageBreak())
            elements.extend([Paragraph(escape(f"{source.upper()} inventory: {filters.report} - columns {section + 1}/{len(groups)}"), styles["Heading2"]), Paragraph(escape(f"As of {first['as_of']}. {first['value_basis'].replace('_', ' ')}."), styles["Normal"]), Paragraph(escape("Filters: " + filters.model_dump_json()), style), Spacer(1, 8)])
            for warning in first.get("warnings", []) + ([first["limitations"]] if first.get("limitations") else []):
                elements.append(Paragraph(escape(warning), styles["Normal"]))
            elements.append(Spacer(1, 8))
            data = [[Paragraph(escape(key.replace("_", " ")), style) for key in chosen]] + [[Paragraph(escape(str(row.get(key) if row.get(key) is not None else "Not available")), style) for key in chosen] for row in rows]
            table = Table(data, colWidths=[770 / len(chosen)] * len(chosen), repeatRows=1)
            table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ebf1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
            elements.append(table)
        SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=30, rightMargin=30, topMargin=24, bottomMargin=24).build(elements)
        media = "application/pdf"
    return Response(stream.getvalue(), media_type=media, headers={"Content-Disposition": f'attachment; filename="inventory-{source}-{filters.report}.{export_format}"'})
