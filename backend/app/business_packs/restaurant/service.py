"""Restaurant fulfillment. Only unpaid kitchen firing issues canonical stock."""
from hashlib import sha256
import json
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import inspect, func, select
from sqlalchemy.exc import IntegrityError
from app.apps.srm.service_checkout import _authority
from app.apps.srm.services.commercial import require, lock_tenant
from .models import (MODELS, RestaurantTable as Table, RestaurantServiceOrder as Order,
    RestaurantKitchenTicket as Ticket, RestaurantKitchenLine as Line, RestaurantCommand as Command)
from .sources import paid_source, private


def fail(message, code=403):
    raise HTTPException(code, message)


def authority(db, actor, *actions, write=False):
    from app.apps.srm.access import SRM_VIEW_PERMISSIONS
    require(actor, *(('srm_manage', 'srm_admin') if write else tuple(sorted(SRM_VIEW_PERMISSIONS))))
    company, branch, fresh = _authority(db, actor, order=False, write=write)
    scope = db.info.get('business_pack_scope')
    state = inspect(actor, raiseerr=False)
    if (scope is None or scope.pack_key != 'restaurant' or fresh != scope
            or state is None or not state.persistent or state.session is not db
            or not any('restaurant.'+action in scope.capabilities for action in actions)):
        fail('Select an authorized Restaurant context for this operation')
    from app.business_packs.native_policy import native_srm_policy
    if db.info.get('business_pack_policy') != native_srm_policy('restaurant').policy:
        fail('Audited Restaurant isolation adapter is not installed', 503)
    if not all(inspect(db.connection()).has_table(model.__tablename__) for model in MODELS):
        fail('Install the Restaurant fulfillment extension first', 503)
    return scope


def scoped(db, model, scope):
    return db.query(model).filter_by(organization_id=scope.company_id, branch_id=scope.branch_id, pack_context_id=scope.context_id)


def fields(scope, actor):
    return dict(organization_id=scope.company_id, branch_id=scope.branch_id, pack_context_id=scope.context_id, created_by=actor.id)


def capabilities(db, actor):
    scope = authority(db, actor, 'tables.view', 'tables.manage', 'orders.view', 'orders.create', 'kitchen.view')
    from app.access.service import check_background_access
    can_write = scope.branch_id in db.info['branch_context'].writable
    try:
        require(actor, 'srm_manage', 'srm_admin')
        check_background_access(db, actor, 'srm', 'create', administrative_read=False, stamp=False)
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
        can_write = False
    writable = {'tables.manage', 'orders.create', 'orders.serve', 'kitchen.prepare', 'kitchen.ready'}
    result = {action.replace('.', '_'): ('restaurant.'+action in scope.capabilities and (can_write or action not in writable))
        for action in ('tables.view', 'tables.manage', 'orders.view', 'orders.create', 'orders.serve', 'kitchen.view', 'kitchen.prepare', 'kitchen.ready')}
    from app.business_packs.native_checkout_authority import capture
    result['billing_view'] = 'restaurant.billing.view' in scope.capabilities or 'restaurant.payments.record' in scope.capabilities
    for name, billing, payments in (('billing_prepare', True, False), ('payments_record', False, True)):
        action = 'billing.prepare' if billing else 'payments.record'
        allowed = 'restaurant.'+action in scope.capabilities and scope.branch_id in db.info['branch_context'].writable
        if allowed:
            try:
                capture(db, actor, scope, order=False, billing=billing, payments=payments, write=True)
                require(actor, *(['srm_invoice_create', 'srm_admin'] if billing else ['srm_collection_create', 'srm_admin']))
                if billing:
                    require(actor, 'srm_invoice_approve', 'srm_admin')
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise
                allowed = False
        result[name] = allowed
    anonymous = {'restaurant.orders.create','restaurant.billing.prepare','restaurant.payments.record'} <= scope.capabilities
    anonymous = anonymous and scope.branch_id in db.info['branch_context'].writable
    if anonymous:
        try:
            capture(db, actor, scope, order=True, billing=True, payments=True, write=True)
            for names in (('srm_manage','srm_admin'), ('srm_invoice_create','srm_admin'),
                    ('srm_invoice_approve','srm_admin'), ('srm_collection_create','srm_admin')):
                require(actor, *names)
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
            anonymous = False
    result['anonymous_settle'] = anonymous
    result['operational_scope'] = {'realm': 'pack', 'user_id': actor.id, 'company_id': scope.company_id, 'branch_id': scope.branch_id,
        **{key: getattr(scope, key) for key in ('context_id', 'pack_key', 'pack_version', 'context_revision', 'grant_revision', 'activation_revision')}}
    return result


def record(db, model, scope, ident):
    row = scoped(db, model, scope).filter(model.id == ident).first()
    if row is None:
        fail('Restaurant record is unavailable', 404)
    private(db, scope, model, row.id)
    return row


def digest(action, ident, data):
    return sha256(json.dumps({'action': action, 'id': ident, 'input': data.model_dump(mode='json')},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def prior(db, actor, scope, action, ident, data):
    row = scoped(db, Command, scope).filter_by(request_key=str(data.request_key)).one_or_none()
    fingerprint = digest(action, ident, data)
    if row is not None:
        private(db, scope, Command, row.id)
        if row.created_by != actor.id or row.action != action or row.request_sha256 != fingerprint:
            fail('Request key was already used for a different Restaurant command', 409)
        return dict(row.result)


def save_command(db, actor, scope, action, ident, data, result, *, table=None, order=None, ticket=None):
    row = Command(**fields(scope, actor), request_key=str(data.request_key), request_sha256=digest(action, ident, data),
        action=action, table_id=getattr(table, 'id', None), service_order_id=getattr(order, 'id', None),
        ticket_id=getattr(ticket, 'id', None), result=result)
    db.add(row)
    db.flush()
    return result


def occupied(db, scope, table_id):
    # Physical availability bit only, including another authorized server's
    # private order. Native own-scope filtering must not permit double seating.
    table = Order.__table__
    return db.connection().scalar(select(table.c.id).where(table.c.organization_id == scope.company_id,
        table.c.branch_id == scope.branch_id, table.c.pack_context_id == scope.context_id,
        table.c.table_id == table_id, table.c.state == 'open').limit(1)) is not None


def sent_quantities(db, scope, order):
    # Validated parent -> fixed cumulative quantities, never another actor's
    # ticket body. The immutable source and composite FKs constrain the set.
    line, ticket = Line.__table__, Ticket.__table__
    return dict(db.connection().execute(select(line.c.sales_order_line_id, func.sum(line.c.quantity)).select_from(
        line.join(ticket, line.c.ticket_id == ticket.c.id)).where(ticket.c.service_order_id == order.id,
        ticket.c.organization_id == scope.company_id, ticket.c.branch_id == scope.branch_id,
        ticket.c.pack_context_id == scope.context_id, line.c.organization_id == scope.company_id,
        line.c.branch_id == scope.branch_id, line.c.pack_context_id == scope.context_id).group_by(line.c.sales_order_line_id)).all())


def table_result(row, *, occupied=False):
    return {'id': row.id, 'name': row.name, 'capacity': row.capacity, 'active': row.active, 'revision': row.revision, 'occupied': occupied}


def table_list(db, actor, *, after=0, limit=50):
    scope = authority(db, actor, 'tables.view', 'tables.manage')
    rows = scoped(db, Table, scope).filter(Table.id > after).order_by(Table.id).limit(limit+1).all()
    return {'items': [table_result(row, occupied=occupied(db, scope, row.id)) for row in rows[:limit]], 'next': rows[limit-1].id if len(rows) > limit else None}


def table_write(data, db, actor, *, ident=None, commit=True):
    scope = authority(db, actor, 'tables.manage', write=True)
    lock_tenant(db, actor)
    authority(db, actor, 'tables.manage', write=True)
    action = 'table.create' if ident is None else 'table.update'
    row = None if ident is None else record(db, Table, scope, ident)
    replay = prior(db, actor, scope, action, ident, data)
    if replay is not None:
        return replay
    try:
        with db.begin_nested():
            if row is None:
                row = Table(**fields(scope, actor), name=data.name, capacity=data.capacity, active=True, revision=1)
                db.add(row)
            else:
                if row.revision != data.expected_revision:
                    fail('Table changed; reload its current revision', 409)
                if not data.active and occupied(db, scope, row.id):
                    fail('An occupied table cannot be deactivated', 409)
                row.name, row.capacity, row.active = data.name, data.capacity, data.active
                row.revision += 1
            db.flush()
            result = save_command(db, actor, scope, action, ident, data, table_result(row, occupied=occupied(db, scope, row.id)), table=row)
    except IntegrityError:
        fail('A table with this name already exists in the selected context', 409)
    if commit:
        db.commit()
    return result


def ticket_result(db, scope, ticket):
    lines = scoped(db, Line, scope).filter_by(ticket_id=ticket.id).order_by(Line.id).all()
    order = scoped(db, Order, scope).filter(Order.id == ticket.service_order_id).first()
    if order is None:
        fail('Kitchen ticket parent is unavailable',404)
    table = scoped(db, Table, scope).filter(Table.id == order.table_id).first() if order.table_id is not None else None
    if order.table_id is not None and table is None:
        fail('Kitchen table parent is unavailable',404)
    return {'id': ticket.id, 'service_order_id': ticket.service_order_id, 'state': ticket.state, 'revision': ticket.revision,
        'table': {'id':table.id,'name':table.name} if table is not None else None,
        'items': [{'id': row.id, 'item': row.item, 'quantity': format(Decimal(row.quantity).normalize(), 'f'), 'instruction': row.instruction} for row in lines]}


def order_source(db, actor, scope, order):
    if order.source_kind == 'unpaid_tab':
        from .tabs import source
        return source(db, actor, scope, order)
    result, fingerprint = paid_source(db, actor, scope, order.checkout_id)
    if result['sales_order_id'] != order.sales_order_id or fingerprint != order.source_sha256:
        fail('Paid order source changed; restaurant fulfillment requires reconciliation', 409)
    return result


def order_result(db, actor, scope, order):
    source = order_source(db, actor, scope, order)
    tickets = scoped(db, Ticket, scope).filter_by(service_order_id=order.id).order_by(Ticket.id).all()
    quantities = sent_quantities(db, scope, order)
    return {'id': order.id, 'checkout_id': order.checkout_id, 'sales_order_id': order.sales_order_id,
        'state': order.state, 'revision': order.revision, 'table_id': order.table_id,
        'billing_state': ('billed_tab' if source.get('billing') else order.source_kind),
        **({key: source[key] for key in ('currency', 'total')} if order.source_kind == 'unpaid_tab' else {}),
        **({'customer_assigned': source['customer_assigned']} if order.source_kind == 'unpaid_tab' else {}),
        'items': [dict(row, sent_quantity=str(quantities.get(row['sales_order_line_id'], Decimal(0)))) for row in source['lines']],
        'tickets': [ticket_result(db, scope, row) for row in tickets]}


def open_paid_order(data, db, actor, *, commit=True):
    scope = authority(db, actor, 'orders.create', write=True)
    lock_tenant(db, actor)
    authority(db, actor, 'orders.create', write=True)
    source, fingerprint = paid_source(db, actor, scope, data.checkout_id)
    replay = prior(db, actor, scope, 'order.open_paid', None, data)
    if replay is not None:
        return replay
    with db.begin_nested():
        if source['checkout_revision'] != data.expected_checkout_revision:
            fail('Paid checkout changed; reload its current revision', 409)
        source_table = Order.__table__
        if db.connection().scalar(select(source_table.c.id).where(source_table.c.checkout_id == data.checkout_id)):
            fail('Paid order already has a Restaurant fulfillment record', 409)
        table = None
        if data.table_id is not None:
            table = record(db, Table, scope, data.table_id)
            if not table.active or table.revision != data.expected_table_revision:
                fail('Table availability changed; reload before assigning', 409)
            if occupied(db, scope, table.id):
                fail('This table already has an open fulfillment order', 409)
        order = Order(**fields(scope, actor), checkout_id=data.checkout_id, sales_order_id=source['sales_order_id'],
            table_id=data.table_id, source_sha256=fingerprint, state='open', revision=1)
        db.add(order)
        db.flush()
        if table is not None:
            table.revision += 1
            db.flush()
        result = save_command(db, actor, scope, 'order.open_paid', None, data,
            order_result(db, actor, scope, order), order=order, table=table)
    if commit:
        db.commit()
    return result


def get_order(ident, db, actor):
    scope = authority(db, actor, 'orders.view', 'orders.create')
    return order_result(db, actor, scope, record(db, Order, scope, ident))


def paid_order_source(ident, db, actor):
    scope = authority(db, actor, 'orders.create')
    source, _ = paid_source(db, actor, scope, ident)
    return source


def submit(data, db, actor, *, commit=True):
    scope = authority(db, actor, 'orders.create', write=True)
    from app.business_packs.native_checkout_authority import capture
    epoch = capture(db, actor, scope, order=True, billing=False, payments=False, write=True)
    lock_tenant(db, actor)
    authority(db, actor, 'orders.create', write=True)
    if capture(db, actor, scope, order=True, billing=False, payments=False, write=True) != epoch:
        fail('Native kitchen order rights changed while waiting', 403)
    order = record(db, Order, scope, data.service_order_id)
    source = order_source(db, actor, scope, order)
    replay = prior(db, actor, scope, 'kitchen.submit', order.id, data)
    if replay is not None:
        return replay
    with db.begin_nested():
        if order.state != 'open' or order.revision != data.expected_revision:
            fail('Order changed or is already served; reload before sending items', 409)
        sources = {row['sales_order_line_id']: row for row in source['lines']}
        sent = sent_quantities(db, scope, order)
        for row in data.lines:
            if row.sales_order_line_id not in sources or row.quantity + sent.get(row.sales_order_line_id, Decimal(0)) > Decimal(sources[row.sales_order_line_id]['quantity']):
                fail('Kitchen quantity exceeds the remaining source order quantity', 409)
        ticket = Ticket(**fields(scope, actor), service_order_id=order.id, state='queued', revision=1)
        db.add(ticket)
        db.flush()
        created = []
        for row in data.lines:
            line = Line(**fields(scope, actor), ticket_id=ticket.id, sales_order_line_id=row.sales_order_line_id,
                item=sources[row.sales_order_line_id]['item'], quantity=row.quantity, instruction=row.instruction)
            db.add(line)
            created.append(line)
        order.revision += 1
        db.flush()
        if order.source_kind == 'unpaid_tab':
            from .stock import issue
            issue(ticket, order, created, db, actor, scope)
        result = save_command(db, actor, scope, 'kitchen.submit', order.id, data, ticket_result(db, scope, ticket), order=order, ticket=ticket)
    if commit:
        db.commit()
    return result


def kitchen(db, actor, *, after=0, limit=50, include_served=False):
    scope = authority(db, actor, 'kitchen.view')
    query = scoped(db, Ticket, scope).filter(Ticket.id > after)
    if not include_served:
        query = query.filter(Ticket.state != 'served')
    rows = query.order_by(Ticket.id).limit(limit+1).all()
    for row in rows[:limit]:
        order_source(db, actor, scope, record(db, Order, scope, row.service_order_id))
    return {'items': [ticket_result(db, scope, row) for row in rows[:limit]],
            'next': rows[limit-1].id if len(rows) > limit else None}


def transition(ident, action, data, db, actor, *, commit=True):
    spec = {'prepare': ('kitchen.prepare', 'queued', 'preparing'), 'ready': ('kitchen.ready', 'preparing', 'ready'),
            'serve': ('orders.serve', 'ready', 'served')}
    if action not in spec:
        fail('Unknown kitchen transition', 422)
    capability, before, after = spec[action]
    scope = authority(db, actor, capability, write=True)
    lock_tenant(db, actor)
    authority(db, actor, capability, write=True)
    ticket = record(db, Ticket, scope, ident)
    order = record(db, Order, scope, ticket.service_order_id)
    source = order_source(db, actor, scope, order)
    replay = prior(db, actor, scope, 'kitchen.'+action, ticket.id, data)
    if replay is not None:
        return replay
    with db.begin_nested():
        if order.state != 'open' or ticket.state != before or ticket.revision != data.expected_revision:
            fail('Ticket changed or this transition is unavailable; reload', 409)
        ticket.state, ticket.revision = after, ticket.revision+1
        db.flush()
        if after == 'served':
            if order.source_kind == 'unpaid_tab' and source.get('billing'):
                from .settlement import close_if_settled
                close_if_settled(db, scope, order, source)
            tickets_table = Ticket.__table__
            outstanding = db.connection().scalar(select(tickets_table.c.id).where(tickets_table.c.service_order_id == order.id,
                tickets_table.c.organization_id == scope.company_id, tickets_table.c.branch_id == scope.branch_id,
                tickets_table.c.pack_context_id == scope.context_id, tickets_table.c.state != 'served').limit(1)) is not None
            sent = sent_quantities(db, scope, order)
            if order.source_kind == 'paid_pos' and not outstanding and all(sent.get(row['sales_order_line_id'], Decimal(0)) == Decimal(row['quantity']) for row in source['lines']):
                order.state, order.revision = 'served', order.revision+1
                if order.table_id is not None:
                    table = record(db, Table, scope, order.table_id)
                    table.revision += 1
                db.flush()
        result = save_command(db, actor, scope, 'kitchen.'+action, ticket.id, data, ticket_result(db, scope, ticket), order=order, ticket=ticket)
    if commit:
        db.commit()
    return result
