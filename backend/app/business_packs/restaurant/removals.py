"""Typed native DELETE for unissued charges; immutable birth provenance survives."""
from copy import deepcopy
from weakref import WeakKeyDictionary
from sqlalchemy import inspect, select
from app.access.service import check_background_access
from app.apps.srm.models import SRMInvoice
from app.apps.srm.service_checkout_models import POSServiceCheckout
from . import service, tabs
from .models import RestaurantCommand, RestaurantServiceOrder as Order, RestaurantTabLine as Snapshot

_plans = WeakKeyDictionary()


def _current(db, plan):
    actor, scope = plan['actor'], plan['scope']
    if (service.authority(db, actor, 'orders.create', write=True) is not scope or
            tabs._native_epoch(db, actor, scope) != plan['epoch']):
        service.fail('Restaurant cancellation authority changed')
    check_background_access(db, actor, 'srm', 'delete', administrative_read=False, stamp=False)


def snapshot_transition(row):
    db = inspect(row).session
    plan = _plans.get(db)
    if plan is None or row.id not in plan['snapshots']:
        return False
    _current(db, plan)
    original = plan['snapshots'][row.id]
    state = inspect(row)
    return (row.sales_order_line_id is None and original['sales_order_line_id'] in plan['lines'] and
        all(getattr(row, name) == value and not state.attrs[name].history.has_changes()
            for name, value in original.items() if name != 'sales_order_line_id'))


def cancellation_sources(db, actor, scope, order):
    result = []
    for command in service.scoped(db, RestaurantCommand, scope).filter_by(service_order_id=order.id, action='tab.remove').all():
        service.private(db, scope, RestaurantCommand, command.id)
        result.extend(command.result.get('removed_sources', []))
    plan = _plans.get(db)
    if plan is not None and plan['order'] is order:
        if plan['actor'] is not actor or plan['scope'] is not scope:
            service.fail('Restaurant cancellation source changed')
        _current(db, plan)
        result.extend(plan['sources'])
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


def reconcile_native_deletion(db, actor, native, line):
    plan = _plans.get(db)
    if plan is None:
        return False
    _current(db, plan)
    if plan['actor'] is not actor or native.id != plan['order'].sales_order_id or plan['lines'].get(line.id) is not line or line not in db.deleted:
        service.fail('Native deletion differs from the exact Restaurant cancellation')
    db.flush()
    db.expire(native, ['lines'])
    from app.apps.srm.api.router import _total_from_lines
    from .references import header_update
    totals = _total_from_lines(native.lines)
    with header_update(db, actor, plan['scope'], plan['epoch'], native, plan['order'], totals):
        native.subtotal, native.discount_amount, native.tax_amount, native.total_amount = totals
        plan['order'].revision += 1
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
    plan = dict(actor=actor, scope=scope, epoch=epoch, order=order, lines={i: active[i] for i in ids}, sources=sources,
        snapshots={row.id: deepcopy(dict(db.connection().execute(select(Snapshot.__table__).where(Snapshot.id == row.id)).mappings().one())) for row in snapshots})
    with db.begin_nested():
        _plans[db] = plan
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
    if commit:
        db.commit()
    return result
