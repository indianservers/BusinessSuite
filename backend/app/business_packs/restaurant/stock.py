"""One fixed canonical stock issue per persisted unpaid kitchen line.

Balances, product quantity and movement remain native. This adapter exposes
neither a balance write API nor a second restaurant stock ledger.
"""
from datetime import date
from decimal import Decimal
from sqlalchemy import inspect, select
from app.apps.srm.models import SRMInventoryBalance, SRMInventoryMovement, SRMWarehouse, SRMSalesOrder
from app.apps.srm.stock_resource import _product, _native_branch, _write_quantity_cache
from app.apps.srm.service_checkout import _source_scope
from app.business_packs.models import PackRecordOwnership
from app.business_packs.native_checkout_authority import capture
from .models import RestaurantKitchenLine as Line, RestaurantTabLine as TabLine, RestaurantKitchenIssue as Issue
from .sources import private


def _fail(message, code=403):
    from .service import fail
    fail(message, code)


def issue(ticket, order, lines, db, actor, scope):
    if order.source_kind != 'unpaid_tab':
        return
    from .service import authority
    from .tabs import source
    if authority(db, actor, 'orders.create', write=True) is not scope:
        _fail('Kitchen stock scope changed')
    epoch = capture(db, actor, scope, order=True, billing=False, payments=False, write=True)
    source(db, actor, scope, order)
    native = SRMSalesOrder.__table__
    header = db.connection().execute(select(native.c.order_number, native.c.currency).where(native.c.id == order.sales_order_id,
        native.c.organization_id == scope.company_id)).one()
    tab = TabLine.__table__
    snapshots = {row['sales_order_line_id']: row for row in db.connection().execute(select(tab).where(
        tab.c.service_order_id == order.id, tab.c.organization_id == scope.company_id,
        tab.c.branch_id == scope.branch_id, tab.c.pack_context_id == scope.context_id)).mappings()}
    products = {}
    for ident in sorted({snapshots[row.sales_order_line_id]['product_id'] for row in lines}):
        products[ident] = _product(db, ident, scope.company_id, scope.branch_id, scope, header.currency)
    selected, requirements = [], {}
    for row in lines:
        state = inspect(row)
        if (type(row) is not Line or state.session is not db or not state.persistent or state.identity != (row.id,)
                or row.ticket_id != ticket.id or row.created_by != actor.id or any(attr.history.has_changes() for attr in state.attrs)):
            _fail('Kitchen stock requires an unchanged persisted source line')
        private(db, scope, Line, row.id)
        proof = snapshots.get(row.sales_order_line_id)
        if proof is None:
            _fail('Kitchen source has no actual issued native charge')
        canonical = Line.__table__
        actual = db.connection().execute(select(canonical.c.ticket_id, canonical.c.sales_order_line_id, canonical.c.quantity,
            canonical.c.created_by, canonical.c.organization_id, canonical.c.branch_id, canonical.c.pack_context_id).where(canonical.c.id == row.id)).one()
        if tuple(actual) != (ticket.id, row.sales_order_line_id, row.quantity, actor.id, scope.company_id, scope.branch_id, scope.context_id):
            _fail('Kitchen stock source differs from its actual persisted line')
        _, physical = products[proof['product_id']]
        if not physical:
            if proof['warehouse_id'] is not None:
                _fail('Menu stock classification changed; reconcile before firing', 409)
            continue
        warehouse = proof['warehouse_id']
        if type(warehouse) is not int or warehouse < 1:
            _fail('Menu stock classification changed; choose a supported new order', 409)
        key = (proof['product_id'], warehouse)
        requirements[key] = requirements.get(key, Decimal(0)) + row.quantity
        selected.append((row, proof, key))
    for warehouse in sorted({key[1] for key in requirements}):
        _source_scope(db, scope, scope.company_id, scope.branch_id, SRMWarehouse, warehouse, master=True)
        _native_branch(db, SRMWarehouse.__tablename__, warehouse, scope.company_id, scope.branch_id)
        table = SRMWarehouse.__table__
        if not db.connection().scalar(select(table.c.id).where(table.c.id == warehouse,
                table.c.organization_id == scope.company_id, table.c.active.is_(True)).with_for_update()):
            _fail('Eligible kitchen warehouse is unavailable', 409)
    balance = SRMInventoryBalance.__table__
    changes = []
    for key, quantity in sorted(requirements.items()):
        row = db.connection().execute(select(balance.c.id, balance.c.quantity).where(balance.c.organization_id == scope.company_id,
            balance.c.product_id == key[0], balance.c.warehouse_id == key[1]).with_for_update()).first()
        if row is None or row.quantity is None or row.quantity < quantity:
            _fail('Insufficient eligible stock to fire these kitchen items', 409)
        owner = PackRecordOwnership.__table__
        if db.connection().scalar(select(owner.c.id).where(owner.c.resource_table == balance.name, owner.c.resource_key == str(row.id))):
            _fail('Canonical kitchen stock cannot adopt a private balance')
        changes.append((row, quantity))
    if capture(db, actor, scope, order=True, billing=False, payments=False, write=True) != epoch:
        _fail('Native kitchen stock authorization changed while waiting')
    for row, quantity in changes:
        result = db.connection().execute(balance.update().where(balance.c.id == row.id, balance.c.quantity == row.quantity).values(quantity=row.quantity-quantity))
        if result.rowcount != 1:
            _fail('Kitchen stock changed; reload before firing', 409)
    from app.apps.srm.services.commercial_numbering import reserve_number
    for row, proof, key in selected:
        if db.connection().scalar(select(Issue.id).where(Issue.kitchen_line_id == row.id)):
            _fail('This kitchen line already issued stock; replay its original command', 409)
        movement = SRMInventoryMovement(organization_id=scope.company_id,
            movement_number=reserve_number(db, SRMInventoryMovement, 'INV', 'movement_number', scope.company_id, actor=actor),
            movement_type='restaurant_kitchen', movement_date=date.today(), product_id=key[0], warehouse_id=key[1],
            quantity_in=Decimal(0), quantity_out=row.quantity, rate=proof['unit_price'], value=row.quantity*proof['unit_price'],
            reference_number=header.order_number, notes='Kitchen ticket '+str(ticket.id), created_by=actor.id)
        movement._suite_source_record = row
        db.add(movement)
        db.flush()
        db.add(Issue(organization_id=scope.company_id, branch_id=scope.branch_id, pack_context_id=scope.context_id,
                     created_by=actor.id, kitchen_line_id=row.id, movement_id=movement.id))
        db.flush()
    for ident in sorted({key[0] for key in requirements}):
        _write_quantity_cache(db, ident, scope.company_id)
