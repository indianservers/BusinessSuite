"""Bill the existing tab once; canonical checkout receipts retain all money."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid5, NAMESPACE_URL
from sqlalchemy import select, inspect
from app.apps.srm import service_checkout as checkout
from app.apps.srm.models import SRMSalesOrder, SRMInvoice, SRMInvoiceLine, SRMProduct
from app.apps.srm.service_checkout_models import POSServiceCheckout, POSCheckoutLine
from app.apps.srm.services.commercial import require, lock_tenant, customer
from app.business_packs.native_checkout_authority import capture
from .models import RestaurantServiceOrder as Order, RestaurantKitchenTicket as Ticket, RestaurantTabLine
from .service import fail, record, prior, save_command, scoped, sent_quantities
from .sources import private, paid_source


def registers(db, actor, *, after=0):
    """Only actual usable open registers; no money or another cashier's data."""
    from app.apps.srm.models import SRMPOSSession
    from .service import capabilities
    scope = authority(db, actor, write=False)
    allowed = capabilities(db, actor)
    if not (allowed['billing_prepare'] or allowed['payments_record']):
        fail('Native Restaurant billing or collection rights are required')
    rows = db.query(SRMPOSSession).filter(SRMPOSSession.organization_id == scope.company_id,
        SRMPOSSession.id > after, SRMPOSSession.status == 'open', SRMPOSSession.deleted_at.is_(None),
        (SRMPOSSession.cashier_user_id == actor.id) | SRMPOSSession.cashier_user_id.is_(None)).order_by(SRMPOSSession.id).limit(51).all()
    items = []
    from fastapi import HTTPException
    for row in rows[:50]:
        try:
            checkout._collection_register(db, actor, scope.company_id, scope.branch_id, scope, row.id)
        except HTTPException as error:
            if error.status_code not in {403,404,409}:
                raise
            continue
        items.append({'id': row.id, 'label': row.session_number + (' · My register' if row.cashier_user_id == actor.id else ' · Shared register')})
    return {'items': items, 'next': rows[49].id if len(rows) > 50 else None}


def authority(db, actor, *, billing=False, payments=False, write=True):
    if not write:
        require(actor, 'srm_invoice_view', 'srm_invoice_create', 'srm_invoice_approve',
            'srm_collection_view', 'srm_collection_create', 'srm_admin')
    company, branch, scope = checkout._authority(db, actor, order=False, billing=billing, payments=payments, write=write)
    needed = 'billing.prepare' if billing else 'payments.record' if payments else 'billing.view'
    if (scope is None or scope.pack_key != 'restaurant' or db.info.get('business_pack_scope') != scope
            or not ({'restaurant.'+needed} | ({'restaurant.payments.record'} if not write else set())) & scope.capabilities):
        fail('An authorized Restaurant billing context is required')
    return scope


def writer(db, actor, *, billing=False, payments=False):
    scope = authority(db, actor, billing=billing, payments=payments)
    epoch = capture(db, actor, scope, order=False, billing=billing, payments=payments, write=True)
    lock_tenant(db, actor)
    if (authority(db, actor, billing=billing, payments=payments) != scope
            or capture(db, actor, scope, order=False, billing=billing, payments=payments, write=True) != epoch):
        fail('Native Restaurant financial authority changed while waiting')
    return scope


def result(db, scope, order, root):
    return {'order_id': order.id, 'order_revision': order.revision, 'state': order.state,
        'checkout': checkout.checkout_result(root, db, scope=scope)}


def close_if_settled(db, scope, order, source):
    if order.state != 'open' or not source.get('billing') or Decimal(source['billing']['balance']) != 0:
        return
    outstanding = scoped(db, Ticket, scope).filter(Ticket.service_order_id == order.id, Ticket.state != 'served').first()
    sent = sent_quantities(db, scope, order)
    if outstanding is None and all(sent.get(line['sales_order_line_id'], Decimal(0)) == Decimal(line['quantity']) for line in source['lines']):
        order.state, order.revision = 'served', order.revision+1
        if order.table_id is not None:
            from .models import RestaurantTable
            record(db, RestaurantTable, scope, order.table_id).revision += 1
        db.flush()


def after_native_payment(db, actor, scope, root, native_fingerprint):
    """Finite post-payment reconciliation; never creates payment authority.

    The native collector supplies its original pre-writer fingerprint and the
    already-flushed persistent group. Only the actual unpaid Restaurant source
    can close; other packs and ordinary paid POS fulfillment are unchanged.
    """
    if scope is None or getattr(scope, 'pack_key', None) != 'restaurant':
        return
    from app.business_packs.access import PackScope
    if not isinstance(scope, PackScope) or db.info.get('business_pack_scope') != scope:
        fail('A genuine current Restaurant payment scope is required')
    state = inspect(root, raiseerr=False)
    if (type(root) is not POSServiceCheckout or state is None or not state.persistent or state.session is not db
            or state.identity != (root.id,) or root in db.deleted or db.is_modified(root, include_collections=True)):
        fail('Restaurant payment source must be the unchanged persistent native checkout')
    current = authority(db, actor, payments=True)
    if current != scope or native_fingerprint is None or capture(db, actor, scope,
            order=False, billing=False, payments=True, write=True) != native_fingerprint:
        fail('Native Restaurant payment authority changed')
    lock_tenant(db, actor)
    if capture(db, actor, scope, order=False, billing=False, payments=True, write=True) != native_fingerprint:
        fail('Native Restaurant payment authority changed while waiting')
    def value(item):
        if isinstance(item, datetime):
            return (item.replace(tzinfo=timezone.utc) if item.tzinfo is None else item).astimezone(timezone.utc)
        return item
    table = POSServiceCheckout.__table__
    stored = db.connection().execute(select(table).where(table.c.id == root.id).with_for_update()).mappings().one_or_none()
    if (stored is None or any(value(stored[key]) != value(getattr(root, key)) for key in table.c.keys())
            or (root.organization_id, root.branch_id, root.pack_context_id) != (scope.company_id, scope.branch_id, scope.context_id)
            or root.state != 'committed'):
        fail('Restaurant payment checkout identity changed')
    source = Order.__table__
    bound = db.connection().execute(select(source).where(source.c.sales_order_id == root.sales_order_id)).mappings().one_or_none()
    if bound is None or bound['source_kind'] == 'paid_pos':
        return
    if (bound['source_kind'] != 'unpaid_tab' or bound['checkout_id'] is not None
            or (bound['organization_id'], bound['branch_id'], bound['pack_context_id']) != (scope.company_id, scope.branch_id, scope.context_id)):
        fail('Restaurant payment has a foreign or changed service-order source')
    private(db, scope, POSServiceCheckout, root.id)
    order = record(db, Order, scope, bound['id'])
    from .tabs import source as tab_source
    proof = tab_source(db, actor, scope, order)
    if proof.get('billing', {}).get('checkout_id') != root.id:
        fail('Restaurant payment does not match its immutable billing command')
    close_if_settled(db, scope, order, proof)


def bill(ident, data, db, actor, *, commit=True):
    from app.apps.srm.api import router as native
    from .tabs import source
    scope = writer(db, actor, billing=True)
    order = record(db, Order, scope, ident)
    replay = prior(db, actor, scope, 'tab.bill', ident, data)
    if replay is not None:
        return replay
    if order.source_kind != 'unpaid_tab' or order.state != 'open' or order.revision != data.expected_revision:
        fail('Only the current open unpaid tab can be billed', 409)
    proof = source(db, actor, scope, order)
    if proof.get('billing'):
        fail('This tab already has its canonical invoice', 409)
    if Decimal(proof['total']) != data.expected_total:
        fail('Tab total changed; review its current charges', 409)
    sent = sent_quantities(db, scope, order)
    if any(sent.get(line['sales_order_line_id'], Decimal(0)) != Decimal(line['quantity']) for line in proof['lines']):
        fail('Send every ordered item to the kitchen before billing', 409)
    native_order = db.get(SRMSalesOrder, order.sales_order_id)
    if native_order.customer_id is None:
        fail('This historical walk-in tab needs an audited customer identity assignment before billing', 409)
    customer(db, native_order.customer_id, actor)
    with db.begin_nested():
        register = checkout._collection_register(db, actor, scope.company_id, scope.branch_id, scope, data.pos_session_id)
        root = POSServiceCheckout(organization_id=scope.company_id, branch_id=scope.branch_id, pack_context_id=scope.context_id,
            request_id=str(data.request_key), request_sha256=checkout._digest(data), created_by=actor.id,
            customer_id=native_order.customer_id, currency=native_order.currency, pos_session_id=register.id,
            sales_order_id=native_order.id, billing_mode='invoice_at_checkout')
        db.add(root); db.flush()
        checkout._stamp_new(db, scope, scope.company_id, scope.branch_id, [root])
        invoice = native._create_invoice_from_lines(db, actor, 'sales_order', native_order.id, None, native_order,
            [{'source_type': 'sales_order_line', 'source_id': line.id, 'description': line.description,
              **{key: getattr(line, key) for key in ('quantity','unit_price','discount_amount','tax_amount','line_total')}}
             for line in native_order.lines], native_order.currency)
        db.flush()
        native.approve_invoice_operation(invoice.id, db, actor, commit=False)
        root.invoice_id = invoice.id
        db.flush()
        billed = {line.source_id: line for line in db.query(SRMInvoiceLine).filter_by(invoice_id=invoice.id)}
        snapshots = {line.sales_order_line_id: line for line in scoped(db, RestaurantTabLine, scope).filter_by(service_order_id=order.id)}
        checkout._stamp_new(db, scope, scope.company_id, scope.branch_id, [invoice, *billed.values()])
        for line in native_order.lines:
            product = db.get(SRMProduct, line.product_id)
            mapped = POSCheckoutLine(checkout_id=root.id,
                client_line_key=str(uuid5(NAMESPACE_URL, f'restaurant-tab:{scope.company_id}:{scope.context_id}:{order.id}:{line.id}')),
                line_kind='unscheduled_service' if product.product_type.lower() in {'service','services'} else 'product',
                product_id=line.product_id, sales_order_line_id=line.id, invoice_line_id=billed[line.id].id,
                **{key: getattr(line, key) for key in ('quantity','unit_price','discount_amount','tax_amount','line_total')},
                catalog_tax_snapshot=snapshots[line.id].catalog_tax_snapshot)
            db.add(mapped); db.flush()
            checkout._stamp_new(db, scope, scope.company_id, scope.branch_id, [mapped])
        root.state, root.committed_at = 'committed', datetime.now(timezone.utc)
        order.revision += 1
        db.flush()
        answer = save_command(db, actor, scope, 'tab.bill', ident, data, result(db, scope, order, root), order=order)
        paid_source(db, actor, scope, root.id, settlement_order=order)
    if commit:
        db.commit()
    return answer


def state(ident, db, actor):
    from .tabs import source
    scope = authority(db, actor, write=False)
    order = record(db, Order, scope, ident)
    if order.source_kind != 'unpaid_tab':
        fail('Restaurant tab billing requires its original unpaid source', 409)
    source(db, actor, scope, order)
    root = db.query(POSServiceCheckout).filter_by(sales_order_id=order.sales_order_id).first()
    if root is None:
        return {'order_id': order.id, 'order_revision': order.revision, 'state': order.state, 'checkout': None}
    paid_source(db, actor, scope, root.id, settlement_order=order)
    return result(db, scope, order, root)


def payment(ident, data, db, actor, *, commit=True):
    from app.apps.srm.service_checkout_schemas import AppendPaymentInput
    from .tabs import source
    scope = writer(db, actor, payments=True)
    order = record(db, Order, scope, ident)
    replay = prior(db, actor, scope, 'tab.payment', ident, data)
    if replay is not None:
        return replay
    root = db.query(POSServiceCheckout).filter_by(sales_order_id=order.sales_order_id).first()
    if root is None:
        fail('Bill this tab before collecting payment', 409)
    source(db, actor, scope, order)
    with db.begin_nested():
        checkout.append_payment(root.id, AppendPaymentInput(expected_revision=data.expected_revision,
            pos_session_id=data.pos_session_id, payment=data.payment), db, actor, commit=False)
        db.flush()
        answer = save_command(db, actor, scope, 'tab.payment', ident, data, result(db, scope, order, root), order=order)
    if commit:
        db.commit()
    return answer
