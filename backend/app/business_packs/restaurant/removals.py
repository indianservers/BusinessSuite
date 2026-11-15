"""Typed native DELETE for unissued charges; immutable birth provenance survives."""
from copy import deepcopy
from dataclasses import dataclass
from weakref import WeakKeyDictionary, WeakSet
from sqlalchemy import inspect, select
from app.access.service import check_background_access
from app.apps.srm.models import SRMInvoice, SRMSalesOrderLine
from app.apps.srm.service_checkout_models import POSServiceCheckout
from . import service, tabs
from .models import RestaurantCommand, RestaurantServiceOrder as Order, RestaurantTabLine as Snapshot

@dataclass(frozen=True, eq=False)
class _Cancellation:
    actor: object
    scope: object
    epoch: str
    order: object
    lines: dict
    sources: list
    snapshots: dict
    native_values: dict


_plans = WeakKeyDictionary()
_issued = WeakSet()


def _current(db, plan):
    if type(plan) is not _Cancellation or plan not in _issued or _plans.get(db) is not plan:
        service.fail('An authentic typed Restaurant cancellation is required')
    actor, scope = plan.actor, plan.scope
    if (service.authority(db, actor, 'orders.create', write=True) is not scope or
            tabs._native_epoch(db, actor, scope) != plan.epoch):
        service.fail('Restaurant cancellation authority changed')
    check_background_access(db, actor, 'srm', 'delete', administrative_read=False, stamp=False)


def snapshot_transition(row):
    db = inspect(row).session
    plan = _plans.get(db)
    if plan is None:
        return False
    _current(db, plan)
    if row.id not in plan.snapshots:
        return False
    original = plan.snapshots[row.id]
    state = inspect(row)
    return (row.sales_order_line_id is None and original['sales_order_line_id'] in plan.lines and
        all(getattr(row, name) == value and not state.attrs[name].history.has_changes()
            for name, value in original.items() if name != 'sales_order_line_id'))


def cancellation_sources(db, actor, scope, order):
    result = []
    for command in service.scoped(db, RestaurantCommand, scope).filter_by(service_order_id=order.id, action='tab.remove').all():
        service.private(db, scope, RestaurantCommand, command.id)
        result.extend(command.result.get('removed_sources', []))
    plan = _plans.get(db)
    if plan is not None:
        _current(db, plan)
    if plan is not None and plan.order is order:
        if plan.actor is not actor or plan.scope is not scope:
            service.fail('Restaurant cancellation source changed')
        _current(db, plan)
        result.extend(plan.sources)
    return result


def validate_cancellations(db, actor, scope, order, snapshots):
    by_id = {}
    for proof in cancellation_sources(db, actor, scope, order):
        if (not isinstance(proof, dict) or set(proof) != {'snapshot_id', 'line_id', 'modifier'} or
                type(proof['snapshot_id']) is not int or type(proof['line_id']) is not int or
                proof['snapshot_id'] in by_id):
            service.fail('Restaurant cancellation command is invalid', 409)
        by_id[proof['snapshot_id']] = proof
    found = set()
    for row in snapshots:
        if row['sales_order_line_id'] is None:
            proof = by_id.get(row['id'])
            if proof is None or proof['line_id'] != row['original_sales_order_line_id']:
                service.fail('Missing native charge has no exact cancellation command', 409)
            service.private(db, scope, Snapshot, row['id'])
            found.add(row['id'])
        elif row['original_sales_order_line_id'] != row['sales_order_line_id'] or row['id'] in by_id:
            service.fail('Active native charge identity changed', 409)
    if found != set(by_id):
        service.fail('Restaurant cancellation snapshot is missing', 409)
    return found


def retain_deleted_branch_source(db, item):
    """Retain immutable branch/pack history for one exact native cancellation.

    This is not a permission grant. The native branch validator has already
    checked its own write boundary, and all original source checks still apply.
    """
    plan = _plans.get(db)
    if plan is None or type(item) is not SRMSalesOrderLine:
        return False
    _current(db, plan)
    state = inspect(item)
    if (state.session is not db or not state.persistent or state.identity != (item.id,) or
            item not in db.deleted or plan.lines.get(item.id) is not item or
            item.sales_order_id != plan.order.sales_order_id):
        service.fail('Native deletion differs from the exact cancellation source')
    source = db.connection().execute(select(Order.__table__).where(Order.id == plan.order.id)).mappings().one_or_none()
    if (source is None or (source['organization_id'], source['branch_id'], source['pack_context_id'], source['sales_order_id'], source['source_kind'], source['state']) !=
            (plan.scope.company_id, plan.scope.branch_id, plan.scope.context_id, item.sales_order_id, 'unpaid_tab', 'open')):
        service.fail('Native cancellation parent changed')
    if any(db.connection().scalar(select(model.id).where(model.sales_order_id == item.sales_order_id).limit(1)) for model in (POSServiceCheckout, SRMInvoice)):
        service.fail('A billed native source cannot be cancelled')
    sent = service.sent_quantities(db, plan.scope, plan.order)
    if any(sent.get(ident, 0) != 0 for ident in plan.lines):
        service.fail('An issued native charge cannot be cancelled')
    original = plan.native_values[item.id]
    if any(getattr(item, name) != value or state.attrs[name].history.has_changes() for name, value in original.items()):
        service.fail('Native cancellation charge changed')
    current = db.connection().execute(select(SRMSalesOrderLine.__table__).where(SRMSalesOrderLine.id == item.id)).mappings().one_or_none()
    if current is None or dict(current) != original:
        service.fail('Native cancellation source changed')
    from app.apps.srm.access import sales_order_query
    from app.apps.srm.models import SRMSalesOrder
    if sales_order_query(db, plan.actor).with_entities(SRMSalesOrder.id).filter_by(id=item.sales_order_id).first() is None:
        service.fail('Native cancellation parent is unavailable')
    service.private(db, plan.scope, SRMSalesOrderLine, item.id)
    sources = [proof for proof in plan.sources if proof['line_id'] == item.id]
    if len(sources) != 1:
        service.fail('Exact cancellation provenance is required')
    snapshot = service.record(db, Snapshot, plan.scope, sources[0]['snapshot_id'])
    if snapshot.sales_order_line_id is not None or snapshot.original_sales_order_line_id != item.id:
        service.fail('Original cancellation snapshot changed')
    return True


def reconcile_native_deletion(db, actor, native, line):
    plan = _plans.get(db)
    if plan is None:
        return False
    _current(db, plan)
    if plan.actor is not actor or native.id != plan.order.sales_order_id or plan.lines.get(line.id) is not line or line not in db.deleted:
        service.fail('Native deletion differs from the exact Restaurant cancellation')
    db.flush()
    db.expire(native, ['lines'])
    from app.apps.srm.api.router import _total_from_lines
    from .references import header_update
    totals = _total_from_lines(native.lines)
    with header_update(db, actor, plan.scope, plan.epoch, native, plan.order, totals):
        native.subtotal, native.discount_amount, native.tax_amount, native.total_amount = totals
        plan.order.revision += 1
        db.flush()
    return True


def remove(ident, data, db, actor, *, commit=True):
    # The POST capability cannot substitute for the native DELETE action.
    check_background_access(db, actor, 'srm', 'delete', administrative_read=False, stamp=False)
    scope, epoch = tabs.writer(db, actor)
    check_background_access(db, actor, 'srm', 'delete', administrative_read=False, stamp=False)
    order = service.record(db, Order, scope, ident)
    service.order_source(db, actor, scope, order)
    replay = service.prior(db, actor, scope, 'tab.remove', ident, data)
    if replay is not None:
        return replay
    if order.source_kind != 'unpaid_tab' or order.state != 'open' or order.revision != data.expected_revision:
        service.fail('Only the current open unpaid tab can remove items', 409)
    if any(db.connection().scalar(select(model.id).where(model.sales_order_id == order.sales_order_id).limit(1)) for model in (POSServiceCheckout, SRMInvoice)):
        service.fail('Billed items cannot be removed', 409)
    from app.apps.srm.access import get_sales_order_for_user
    native = get_sales_order_for_user(db, order.sales_order_id, actor)
    ids = set(data.sales_order_line_ids)
    active = {line.id: line for line in native.lines}
    if not ids <= active.keys() or ids == active.keys():
        service.fail('Choose current items and retain at least one item on the tab', 409)
    sent = service.sent_quantities(db, scope, order)
    if any(sent.get(i, 0) != 0 for i in ids):
        service.fail('Items already sent to the kitchen cannot be removed', 409)
    for line in active.values():
        marker = (line.metadata_json or {}).get('restaurant_modifier')
        if marker and line.id in ids:
            group = {other.id for other in active.values() if
                ((other.metadata_json or {}).get('restaurant_modifier') or {}).get('request_key') == marker['request_key'] and
                ((other.metadata_json or {}).get('restaurant_modifier') or {}).get('base_slot') == marker['base_slot']}
            if not group <= ids:
                service.fail('Remove the complete menu item and its modifiers together', 409)
    snapshots = service.scoped(db, Snapshot, scope).filter(Snapshot.service_order_id == order.id, Snapshot.sales_order_line_id.in_(ids)).all()
    if {row.sales_order_line_id for row in snapshots} != ids or db in _plans:
        service.fail('Exact cancellation snapshots are required', 409)
    sources = [{'snapshot_id': row.id, 'line_id': row.sales_order_line_id,
        'modifier': deepcopy((active[row.sales_order_line_id].metadata_json or {}).get('restaurant_modifier'))} for row in snapshots]
    plan = _Cancellation(actor=actor, scope=scope, epoch=epoch, order=order, lines={i: active[i] for i in ids}, sources=sources,
        native_values={i: deepcopy(dict(db.connection().execute(select(SRMSalesOrderLine.__table__).where(SRMSalesOrderLine.id == i)).mappings().one())) for i in ids},
        snapshots={row.id: deepcopy(dict(db.connection().execute(select(Snapshot.__table__).where(Snapshot.id == row.id)).mappings().one())) for row in snapshots})
    with db.begin_nested():
        _plans[db] = plan
        _issued.add(plan)
        try:
            # Explicit ORM transition also works with SQLite FK enforcement off;
            # PostgreSQL retains ON DELETE SET NULL as the native safety net.
            for row in snapshots:
                row.sales_order_line_id = None
            db.flush()
            from app.apps.srm.api.router import delete_sales_order_line_operation
            for line_id in sorted(ids):
                delete_sales_order_line_operation(native.id, line_id, db, actor, commit=False)
            result = service.order_result(db, actor, scope, order)
            result['removed_sources'] = sources
            result = service.save_command(db, actor, scope, 'tab.remove', ident, data, result, order=order)
        finally:
            _plans.pop(db, None)
            _issued.discard(plan)
    if commit:
        db.commit()
    return result
