"""Unpaid native orders with append-only issued charge provenance.

An internal creation lease postpones stock until a persisted kitchen firing.
Neither a request flag nor order metadata can establish this authority.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from weakref import WeakKeyDictionary
import json
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import inspect, select, exists
from app.apps.srm.models import SRMProduct, SRMSalesOrder, SRMSalesOrderLine, SRMInvoice
from app.apps.srm.service_checkout_models import POSServiceCheckout, ServiceBookingPolicy
from app.apps.srm.schemas import SRMSalesOrderCreate, SRMSalesOrderLineInput
from app.apps.srm.services.commercial import customer, record as native_record, lock_tenant
from app.business_packs.native_checkout_authority import capture
from .models import RestaurantServiceOrder as Order, RestaurantTable as Table, RestaurantTabLine as TabLine
from .sources import private

_leases = WeakKeyDictionary()


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _fail(message, code=403):
    from .service import fail
    fail(message, code)


def _native_epoch(db, actor, scope, *, write=True):
    return capture(db, actor, scope, order=True, billing=False, payments=False, write=write)


def writer(db, actor):
    """Capture fresh native create rights before the FIRST company-writer wait."""
    from .service import authority
    installed = db.info.get('business_pack_scope')
    fingerprint = _native_epoch(db, actor, installed)
    scope = authority(db, actor, 'orders.create', write=True)
    if scope is not installed:
        _fail('Restaurant scope changed')
    lock_tenant(db, actor)
    if authority(db, actor, 'orders.create', write=True) is not scope or _native_epoch(db, actor, scope) != fingerprint:
        _fail('Native order authorization changed while waiting; reload')
    return scope, fingerprint


@dataclass
class _Creation:
    scope: object
    actor: object
    epoch: str
    source: object
    source_values: tuple
    data: object
    fingerprint: str
    native_order: object = None


def _source_values(row):
    return (row.organization_id, row.branch_id, row.pack_context_id, row.created_by, row.table_id,
            row.checkout_id, row.source_kind, row.state, row.revision, row.sales_order_id, row.source_sha256, row.id, row.created_at)


@contextmanager
def _creation(db, actor, scope, epoch, source, data):
    if (db in _leases or db.info.get('business_pack_scope') is not scope or not inspect(source).transient
            or (source.organization_id, source.branch_id, source.pack_context_id, source.created_by) !=
               (scope.company_id, scope.branch_id, scope.context_id, actor.id)
            or (source.source_kind, source.checkout_id, source.sales_order_id, source.id, source.created_at, source.state, source.revision) !=
               ('unpaid_tab', None, None, None, None, 'open', 1)):
        _fail('A new unpaid Restaurant source is required')
    plan = _Creation(scope, actor, epoch, source, _source_values(source), data, _digest(data.model_dump(mode='json')))
    _leases[db] = plan
    try:
        yield plan
    finally:
        _leases.pop(db, None)


def _plan(db, actor):
    plan = _leases.get(db)
    if plan is None:
        return None
    from .service import authority
    if (plan.actor is not actor or db.info.get('business_pack_scope') is not plan.scope
            or inspect(actor).session is not db or not inspect(actor).persistent
            or not inspect(plan.source).transient or _source_values(plan.source) != plan.source_values
            or authority(db, actor, 'orders.create', write=True) is not plan.scope
            or _native_epoch(db, actor, plan.scope) != plan.epoch
            or _digest(plan.data.model_dump(mode='json')) != plan.fingerprint):
        _fail('Restaurant native creation certificate changed')
    return plan


def native_creation(db, actor, data):
    plan = _plan(db, actor)
    if plan is None:
        return False
    if plan.data is not data or plan.native_order is not None:
        _fail('Restaurant native creation certificate does not match this exact new order')
    return True


def capture_native_order(db, actor, row):
    plan = _plan(db, actor)
    state = inspect(row)
    if (plan is None or plan.native_order is not None or type(row) is not SRMSalesOrder
            or state.session is not db or not state.persistent or state.identity != (row.id,)
            or (row.organization_id, row.created_by, row.assigned_user_id, row.customer_id, row.currency, row.status, row.metadata_json) !=
            (plan.scope.company_id, actor.id, actor.id, plan.data.customer_id, plan.data.currency, 'draft', plan.data.metadata_json)):
        _fail('New native Restaurant order differs from its exact creation plan')
    private(db, plan.scope, SRMSalesOrder, row.id)
    plan.native_order = row


def _workspace(db, scope, product_id):
    from app.shared.catalog_models import CatalogDetails
    table = CatalogDetails.__table__
    return db.connection().scalar(select(exists().where(table.c.organization_id == scope.company_id,
        table.c.product_id == product_id, table.c.service_id.is_(None), table.c.workspace_id.is_not(None))))


def _product(db, actor, scope, ident, currency):
    from app.apps.srm.stock_resource import _product as stock_product
    from app.shared.catalog_branches import assert_available
    value = native_record(db, SRMProduct, ident, actor)
    assert_available(value, actor)
    # Reuse GLOBAL managed-Pharma detection, batch/expiry/serial classification,
    # actual source availability and the native locked product signature.
    stock, physical = stock_product(db, ident, scope.company_id, scope.branch_id, scope, currency)
    if value.currency != currency or _workspace(db, scope, ident):
        _fail('This menu item needs a different supported workflow', 409)
    if ((value.metadata_json or {}).get('follow_up') or {}).get('required'):
        _fail('Follow-up commitments require their supported checkout workflow', 409)
    booking = db.query(ServiceBookingPolicy.id).filter_by(organization_id=scope.company_id,
        branch_id=scope.branch_id, pack_context_id=scope.context_id, service_product_id=ident, active=True, booking_required=True).first()
    if booking:
        _fail('Appointment services cannot be sent to a restaurant kitchen', 409)
    return value, stock, physical


def _prepare(data, db, actor, scope, currency):
    from app.apps.srm.stock_resource import _native_branch
    from app.apps.srm.models import SRMWarehouse
    prepared = []
    for slot, selected in enumerate(data.lines):
        product, stock, physical = _product(db, actor, scope, selected.product_id, currency)
        if selected.expected_unit_price is not None and selected.expected_unit_price != Decimal(product.sales_rate or 0):
            _fail('Menu price changed; reload before adding the item', 409)
        warehouse = selected.warehouse_id or (stock['default_warehouse_id'] if physical else None)
        if not physical and selected.warehouse_id is not None:
            _fail('An untracked menu item does not consume a warehouse', 422)
        if physical:
            if type(warehouse) is not int or warehouse < 1:
                _fail('Choose an eligible warehouse for this menu item', 422)
            from app.apps.srm.service_checkout import _source_scope
            _source_scope(db, scope, scope.company_id, scope.branch_id, SRMWarehouse, warehouse, master=True)
            _native_branch(db, SRMWarehouse.__tablename__, warehouse, scope.company_id, scope.branch_id)
            w = SRMWarehouse.__table__
            if not db.connection().scalar(select(w.c.id).where(w.c.id == warehouse, w.c.organization_id == scope.company_id, w.c.active.is_(True))):
                _fail('Menu warehouse is unavailable', 409)
        base = SRMSalesOrderLineInput(product_id=product.id, description=product.item_name,
            quantity=selected.quantity, unit_price=product.sales_rate or Decimal(0),
            metadata_json={'warehouse_id': warehouse} if warehouse else {})
        prepared.append(base)
        from .modifiers import catalog, selections
        from pydantic import ValidationError
        try:
            definition = catalog(product)
            choices = selections(definition, selected.modifiers, base_product_id=product.id)
        except (ValidationError, ValueError):
            _fail('Menu modifier definition or selections changed; reload the menu', 422)
        if definition.groups:
            marker = {'request_key': str(data.request_key), 'base_slot': slot, 'base_product_id': product.id,
                      'definition_sha256': _digest(definition.model_dump(mode='json'))}
            base.metadata_json['restaurant_modifier'] = {**marker, 'kind': 'base',
                'selections': [value.model_dump(mode='json') for value in selected.modifiers]}
            for group, option, quantity in choices:
                modifier, _, _ = _product(db, actor, scope, option.product_id, currency)
                selected_option = next(value for value in selected.modifiers if value.group == group.key and value.product_id == option.product_id)
                if selected_option.expected_unit_price is not None and selected_option.expected_unit_price != Decimal(modifier.sales_rate or 0):
                    _fail('Modifier price changed; reload before adding the item', 409)
                try:
                    if catalog(modifier).groups:
                        _fail('Nested modifier menus require their own supported workflow', 409)
                except ValidationError:
                    _fail('Modifier catalog configuration is invalid', 422)
                from types import SimpleNamespace
                from .schemas import TabMenuLine
                extras = _prepare(SimpleNamespace(request_key=data.request_key, lines=[TabMenuLine(
                    product_id=option.product_id, quantity=selected.quantity * quantity)]), db, actor, scope, currency)
                extra = extras[0]
                description = f'{product.item_name} / {group.label}: {modifier.item_name}'
                if len(description) > 500:
                    _fail('Modifier description exceeds the issued source capacity', 422)
                extra.description = description
                extra.metadata_json['restaurant_modifier'] = {**marker, 'kind': 'option',
                    'group': group.key, 'product_id': option.product_id, 'per_base_quantity': quantity}
                prepared.append(extra)
        if len(prepared) > 100:
            _fail('A Restaurant command supports at most 100 native charge lines including modifiers', 422)
    return prepared


def _birth(scope, native):
    return _digest({'company': scope.company_id, 'branch': scope.branch_id, 'context': scope.context_id,
        'native_order': native['id'], 'created_by': native['created_by'], 'customer': native['customer_id'], 'currency': native['currency']})


def _snapshot(db, actor, scope, order, line):
    value = TabLine(organization_id=scope.company_id, branch_id=scope.branch_id, pack_context_id=scope.context_id,
        created_by=actor.id, service_order_id=order.id, sales_order_line_id=line.id, original_sales_order_line_id=line.id, product_id=line.product_id,
        warehouse_id=(line.metadata_json or {}).get('warehouse_id'), quantity=line.quantity,
        unit_price=line.unit_price, tax_amount=line.tax_amount, line_total=line.line_total, item=line.description[:500],
        catalog_tax_snapshot=(line.metadata_json or {}).get('tax_snapshot', {}))
    db.add(value)
    db.flush()


def _capacity(lines):
    from app.apps.srm.api.router import _total_from_lines
    values = [value for line in lines for value in (line.unit_price, line.tax_amount, line.line_total)]
    values.extend(_total_from_lines(lines))
    if any(not Decimal(value).is_finite() or Decimal(value) < 0 or Decimal(value) >= Decimal('1000000000000') for value in values):
        _fail('Tab charges exceed the native order amount capacity', 422)


def create(data, db, actor, *, commit=True):
    from .service import prior, fields, record, occupied, order_result, save_command
    scope, epoch = writer(db, actor)
    replay = prior(db, actor, scope, 'tab.create', None, data)
    if replay is not None:
        return replay
    with db.begin_nested():
        if data.customer_id is not None:
            customer(db, data.customer_id, actor)
        table = None
        if data.table_id is not None:
            table = record(db, Table, scope, data.table_id)
            if not table.active or table.revision != data.expected_table_revision or occupied(db, scope, table.id):
                _fail('Table availability changed; reload before opening a tab', 409)
        lines = _prepare(data, db, actor, scope, data.currency)
        native_input = SRMSalesOrderCreate(title='Restaurant tab', customer_id=data.customer_id, currency=data.currency,
            metadata_json={'source': 'restaurant_tab', 'request_id': str(data.request_key)}, lines=lines)
        from app.apps.srm.api.router import _normalize_pos_order
        native_input = _normalize_pos_order(db, native_input, scope.company_id)
        _capacity(native_input.lines)
        order = Order(**fields(scope, actor), checkout_id=None, source_kind='unpaid_tab', table_id=data.table_id,
                      state='open', revision=1, source_sha256='0'*64)
        from app.apps.srm.api.router import create_sales_order_operation
        with _creation(db, actor, scope, epoch, order, native_input) as plan:
            create_sales_order_operation(native_input, db, actor, commit=False)
            native = plan.native_order
            if native is None:
                _fail('Native Restaurant order creation did not complete')
        order.sales_order_id = native.id
        order.source_sha256 = _birth(scope, {'id': native.id, 'created_by': native.created_by,
            'customer_id': native.customer_id, 'currency': native.currency})
        db.add(order)
        db.flush()
        for line in native.lines:
            _snapshot(db, actor, scope, order, line)
        if table is not None:
            table.revision += 1
            db.flush()
        from .modifiers import issuance
        with issuance(db, actor, scope, epoch, order, native.lines, data) as modifiers:
            result = order_result(db, actor, scope, order)
            if modifiers:
                result['modifier_sources'] = modifiers
            result = save_command(db, actor, scope, 'tab.create', None, data, result, order=order, table=table)
    if commit:
        db.commit()
    return result


def add(ident, data, db, actor, *, commit=True):
    from .service import record, order_source, prior, save_command, order_result
    scope, epoch = writer(db, actor)
    order = record(db, Order, scope, ident)
    order_source(db, actor, scope, order)
    replay = prior(db, actor, scope, 'tab.add', ident, data)
    if replay is not None:
        return replay
    if order.source_kind != 'unpaid_tab' or order.state != 'open' or order.revision != data.expected_revision:
        _fail('Only the current unpaid open tab can receive additional items', 409)
    if db.connection().scalar(select(POSServiceCheckout.id).where(POSServiceCheckout.sales_order_id == order.sales_order_id).limit(1)):
        _fail('An issued tab cannot receive further items', 409)
    from app.apps.srm.access import get_sales_order_for_user
    native = get_sales_order_for_user(db, order.sales_order_id, actor)
    with db.begin_nested():
        prepared = _prepare(data, db, actor, scope, native.currency)
        from app.apps.srm.api.router import _normalize_pos_order, _total_from_lines, _audit
        normalized = _normalize_pos_order(db, SRMSalesOrderCreate(title='Restaurant tab additions',
            customer_id=native.customer_id, currency=native.currency, lines=prepared), scope.company_id)
        _capacity([*native.lines, *normalized.lines])
        added = []
        for value in normalized.lines:
            row = SRMSalesOrderLine(sales_order_id=native.id, **value.model_dump())
            db.add(row)
            db.flush()
            _snapshot(db, actor, scope, order, row)
            added.append(row)
        # Native relationship scope inherits the actual authorized SO parent.
        db.expire(native, ['lines'])
        totals = _total_from_lines(native.lines)
        from .references import header_update
        with header_update(db, actor, scope, epoch, native, order, totals):
            native.subtotal, native.discount_amount, native.tax_amount, native.total_amount = totals
            order.revision += 1
            db.flush()
        _audit(db, actor, 'sales_order', native.id, 'restaurant_items_added')
        from .modifiers import issuance
        with issuance(db, actor, scope, epoch, order, added, data) as modifiers:
            result = order_result(db, actor, scope, order)
            if modifiers:
                result['modifier_sources'] = modifiers
            result = save_command(db, actor, scope, 'tab.add', ident, data, result, order=order)
    if commit:
        db.commit()
    return result


def source(db, actor, scope, order):
    from app.apps.srm.access import sales_order_query
    if sales_order_query(db, actor).with_entities(SRMSalesOrder.id).filter(SRMSalesOrder.id == order.sales_order_id).first() is None:
        _fail('Restaurant source order is unavailable', 404)
    private(db, scope, SRMSalesOrder, order.sales_order_id)
    native, line, snap = SRMSalesOrder.__table__, SRMSalesOrderLine.__table__, TabLine.__table__
    root = db.connection().execute(select(native.c.id, native.c.organization_id, native.c.created_by, native.c.customer_id,
        native.c.currency, native.c.status, native.c.subtotal, native.c.discount_amount, native.c.tax_amount, native.c.total_amount,
        native.c.metadata_json).where(native.c.id == order.sales_order_id, native.c.organization_id == scope.company_id,
        native.c.deleted_at.is_(None))).mappings().first()
    from .customers import valid_birth
    if (root is None or root['status'] != 'draft' or root['created_by'] != order.created_by
            or (root['metadata_json'] or {}).get('source') != 'restaurant_tab' or not valid_birth(db, scope, order, root)):
        _fail('Unpaid Restaurant source identity changed', 409)
    billed_checkout = db.connection().scalar(select(POSServiceCheckout.id).where(POSServiceCheckout.sales_order_id == order.sales_order_id).limit(1))
    billed_invoice = db.connection().scalar(select(SRMInvoice.id).where(SRMInvoice.sales_order_id == order.sales_order_id).limit(1))
    billing = None
    if billed_checkout or billed_invoice:
        if not billed_checkout or not billed_invoice:
            _fail('This Restaurant order entered billing without its exact checkout source', 409)
        from .sources import paid_source
        billing, _ = paid_source(db, actor, scope, billed_checkout, settlement_order=order)
    snapshots = db.connection().execute(select(snap).where(snap.c.service_order_id == order.id,
        snap.c.organization_id == scope.company_id, snap.c.branch_id == scope.branch_id, snap.c.pack_context_id == scope.context_id)).mappings().all()
    actual = db.connection().execute(select(line).where(line.c.sales_order_id == order.sales_order_id).order_by(line.c.id)).mappings().all()
    from .removals import validate_cancellations
    cancelled = validate_cancellations(db, actor, scope, order, snapshots)
    snapshots = [row for row in snapshots if row['id'] not in cancelled]
    if {row['id'] for row in actual} != {row['sales_order_line_id'] for row in snapshots} or not snapshots:
        _fail('Restaurant charge provenance differs from its actual native lines', 409)
    lookup = {row['sales_order_line_id']: row for row in snapshots}
    from .modifiers import validate_source
    validate_source(db, actor, scope, order, actual)
    from .sources import amounts
    for row in actual:
        proof = lookup[row['id']]
        private(db, scope, SRMSalesOrderLine, row['id'])
        private(db, scope, TabLine, proof['id'])
        amounts(row, ('quantity', 'unit_price', 'discount_amount', 'tax_amount', 'line_total'))
        if (row['product_id'], row['description'], row['quantity'], row['unit_price'], row['tax_amount'], row['line_total'],
                row['discount_amount'], (row['metadata_json'] or {}).get('warehouse_id')) != (
                proof['product_id'], proof['item'], proof['quantity'], proof['unit_price'], proof['tax_amount'], proof['line_total'], Decimal(0), proof['warehouse_id']):
            _fail('Restaurant issued source charge changed', 409)
        if (row['metadata_json'] or {}).get('tax_snapshot', {}) != proof['catalog_tax_snapshot']:
            _fail('Restaurant native catalog tax snapshot changed', 409)
    amounts(root, ('subtotal', 'discount_amount', 'tax_amount', 'total_amount'))
    if (root['subtotal'], root['discount_amount'], root['tax_amount'], root['total_amount']) != (
            sum((row['quantity']*row['unit_price'] for row in actual), Decimal(0)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), Decimal(0),
            sum((row['tax_amount'] for row in actual), Decimal(0)), sum((row['line_total'] for row in actual), Decimal(0))):
        _fail('Restaurant native header charges differ', 409)
    return {'sales_order_id': order.sales_order_id, 'lines': [{'sales_order_line_id': row['id'], 'item': row['description'],
        'quantity': str(row['quantity']), 'unit_price': str(row['unit_price']), 'line_total': str(row['line_total'])} for row in actual],
        'currency': root['currency'], 'total': str(root['total_amount']), 'customer_assigned': root['customer_id'] is not None,
        **({'billing': billing['billing']} if billing else {})}


def menu(db, actor, *, search='', after=0, limit=30, currency='INR'):
    from .service import authority
    scope = authority(db, actor, 'orders.create')
    query = db.query(SRMProduct).filter(SRMProduct.organization_id == scope.company_id, SRMProduct.active.is_(True),
        SRMProduct.deleted_at.is_(None), SRMProduct.id > after)
    if search:
        query = query.filter(SRMProduct.item_name.contains(search, autoescape=True) | SRMProduct.sku.contains(search, autoescape=True))
    rows = query.order_by(SRMProduct.id).limit(limit+1).all()
    result = []
    from fastapi import HTTPException
    for row in rows[:limit]:
        try:
            product, _, _ = _product(db, actor, scope, row.id, currency)
            from .modifiers import menu_groups
            modifier_groups = menu_groups(db, actor, scope, product, currency)
        except HTTPException as exc:
            if exc.status_code in (409, 422):
                continue
            raise
        result.append({'id': product.id, 'name': product.item_name, 'price': str(product.sales_rate or 0), 'currency': product.currency, 'modifier_groups': modifier_groups})
    return {'items': result, 'next': rows[limit-1].id if len(rows) > limit else None}


def active(db, actor, *, after=0, limit=30):
    from .service import authority, scoped
    from app.apps.srm.access import sales_order_query
    scope = authority(db, actor, 'orders.view', 'orders.create')
    native_ids = sales_order_query(db, actor).with_entities(SRMSalesOrder.id)
    rows = scoped(db, Order, scope).filter(Order.id > after, Order.source_kind == 'unpaid_tab', Order.state == 'open',
        Order.sales_order_id.in_(native_ids)).order_by(Order.id).limit(limit+1).all()
    # No price, cost, customer or kitchen payload. Selecting a row performs the
    # full current source proof through the independently authorized detail API.
    return {'items': [{'id': row.id, 'revision': row.revision, 'table_id': row.table_id, 'state': row.state} for row in rows[:limit]],
            'next': rows[limit-1].id if len(rows) > limit else None}
