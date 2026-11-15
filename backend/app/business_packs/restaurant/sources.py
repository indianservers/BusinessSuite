"""Fixed paid-order proof; only item/quantity primitives leave this adapter.

Kitchen requests never load a customer, receipt, invoice or SO ORM body. The
native SO ID query retains the real native record scope, then fixed Connection
projections check canonical source identities and settlement without exposing it.
"""
from decimal import Decimal
from hashlib import sha256
import json
from sqlalchemy import select
from fastapi import HTTPException
from app.apps.srm.models import (SRMSalesOrder, SRMSalesOrderLine, SRMInvoice,
    SRMInvoiceLine, SRMReceipt, SRMReceiptAllocation)
from app.apps.srm.service_checkout_models import POSServiceCheckout, POSCheckoutLine, POSCheckoutPayment


def fail(message='Paid restaurant order is unavailable', code=409):
    raise HTTPException(code, message)


def amounts(row, names):
    try:
        values = [Decimal(row[name]) for name in names]
        if any(not value.is_finite() or value < 0 for value in values):
            fail('Canonical source amount is invalid')
    except (TypeError, ValueError, ArithmeticError):
        fail('Canonical source amount is invalid')


def private(db, scope, model, ident):
    from app.apps.srm.service_checkout import _source_scope
    from app.branches.models import BranchOwnership
    _source_scope(db, scope, scope.company_id, scope.branch_id, model, ident)
    native = BranchOwnership.__table__
    if not db.connection().scalar(select(native.c.resource_key).where(native.c.resource_table == model.__tablename__,
            native.c.resource_key == str(ident), native.c.company_id == scope.company_id,
            native.c.branch_id == scope.branch_id)):
        fail('Restaurant source has no native branch proof', 403)


def paid_source(db, actor, scope, checkout_id, *, settlement_order=None):
    from app.apps.srm.access import sales_order_query
    c, line, mapped_payment = (m.__table__ for m in (POSServiceCheckout, POSCheckoutLine, POSCheckoutPayment))
    connection = db.connection()
    root = connection.execute(select(*(c.c[name] for name in ('id', 'state', 'billing_mode', 'customer_id', 'currency', 'sales_order_id', 'invoice_id', 'revision'))).where(c.c.id == checkout_id, c.c.organization_id == scope.company_id,
        c.c.branch_id == scope.branch_id, c.c.pack_context_id == scope.context_id)).mappings().first()
    if root is None:
        fail(code=404)
    private(db, scope, POSServiceCheckout, root['id'])
    if settlement_order is not None:
        from .models import RestaurantServiceOrder, RestaurantCommand
        source, command = RestaurantServiceOrder.__table__, RestaurantCommand.__table__
        actual_tab = connection.execute(select(source).where(source.c.id == settlement_order.id,
            source.c.organization_id == scope.company_id, source.c.branch_id == scope.branch_id,
            source.c.pack_context_id == scope.context_id, source.c.source_kind == 'unpaid_tab',
            source.c.sales_order_id == root['sales_order_id'], source.c.checkout_id.is_(None))).mappings().first()
        commands = connection.execute(select(command.c.id, command.c.result).where(
            command.c.service_order_id == settlement_order.id, command.c.action == 'tab.bill',
            command.c.organization_id == scope.company_id, command.c.branch_id == scope.branch_id,
            command.c.pack_context_id == scope.context_id)).mappings().all()
        if (not actual_tab or len(commands) != 1 or commands[0]['result'].get('checkout', {}).get('id') != root['id']):
            fail('Restaurant invoice has no exact immutable billing source')
        private(db, scope, RestaurantServiceOrder, actual_tab['id'])
        private(db, scope, RestaurantCommand, commands[0]['id'])
    if root['state'] != 'committed' or root['billing_mode'] != 'invoice_at_checkout':
        fail('Only a committed, fully paid POS order can be sent to this kitchen')
    # ID only: native organization/branch/own/team restrictions remain installed.
    if sales_order_query(db, actor).with_entities(SRMSalesOrder.id).filter(SRMSalesOrder.id == root['sales_order_id']).first() is None:
        fail(code=404)
    private(db, scope, SRMSalesOrder, root['sales_order_id'])
    private(db, scope, SRMInvoice, root['invoice_id'])
    order, invoice = SRMSalesOrder.__table__, SRMInvoice.__table__
    actual = connection.execute(select(order.c.id, order.c.customer_id, order.c.currency, order.c.status,
        order.c.created_by, order.c.metadata_json, order.c.subtotal, order.c.discount_amount, order.c.tax_amount, order.c.total_amount).where(
        order.c.id == root['sales_order_id'], order.c.organization_id == scope.company_id, order.c.deleted_at.is_(None))).mappings().first()
    bill = connection.execute(select(invoice.c.id, invoice.c.sales_order_id, invoice.c.customer_id, invoice.c.currency,
        invoice.c.status, invoice.c.total_amount, invoice.c.paid_amount, invoice.c.balance_amount).where(
        invoice.c.id == root['invoice_id'], invoice.c.organization_id == scope.company_id, invoice.c.deleted_at.is_(None))).mappings().first()
    if bill:
        amounts(bill, ('total_amount', 'paid_amount', 'balance_amount'))
    if settlement_order is not None and actual:
        from .customers import valid_birth
        if (not valid_birth(db, scope, settlement_order, actual) or actual_tab['created_by'] != actual['created_by']
                or (actual['metadata_json'] or {}).get('source') != 'restaurant_tab' or actual['status'] != 'draft'):
            fail('Restaurant billing source birth identity changed')
    if (not actual or not bill or actual['status'] in {'cancelled', 'closed'}
            or (actual['customer_id'], actual['currency']) != (root['customer_id'], root['currency'])
            or (bill['sales_order_id'], bill['customer_id'], bill['currency']) != (actual['id'], root['customer_id'], root['currency'])
            or bill['status'] not in {'approved', 'sent', 'partially_paid', 'paid'}
            or bill['total_amount'] <= 0 or bill['paid_amount']+bill['balance_amount'] != bill['total_amount']
            or (settlement_order is None and (bill['paid_amount'] != bill['total_amount'] or bill['balance_amount'] != 0))):
        fail('The canonical POS invoice must remain fully paid')
    native_line, billed_line = SRMSalesOrderLine.__table__, SRMInvoiceLine.__table__
    fields = ('quantity', 'unit_price', 'discount_amount', 'tax_amount', 'line_total')
    mapped = connection.execute(select(*(line.c[name] for name in ('id', 'sales_order_line_id', 'invoice_line_id',
        'organization_id', 'branch_id', 'scope_context_key', 'line_kind', 'product_id', 'catalog_tax_snapshot', *fields))).where(line.c.checkout_id == checkout_id)).mappings().all()
    if not mapped or {r['invoice_line_id'] for r in mapped} != set(connection.scalars(select(billed_line.c.id).where(billed_line.c.invoice_id == bill['id']))):
        fail('Canonical invoice line mapping differs')
    if {r['sales_order_line_id'] for r in mapped} != set(connection.scalars(select(native_line.c.id).where(native_line.c.sales_order_id == actual['id']))):
        fail('Canonical order line mapping differs')
    snapshots = []
    for row in mapped:
        for model, ident in ((POSCheckoutLine, row['id']), (SRMSalesOrderLine, row['sales_order_line_id']), (SRMInvoiceLine, row['invoice_line_id'])):
            private(db, scope, model, ident)
        source = connection.execute(select(*(native_line.c[name] for name in ('id', 'sales_order_id', 'product_id', 'description', 'item_code', 'metadata_json', *fields))).where(native_line.c.id == row['sales_order_line_id'])).mappings().one()
        charge = connection.execute(select(*(billed_line.c[name] for name in ('invoice_id', 'source_type', 'source_id', *fields))).where(billed_line.c.id == row['invoice_line_id'])).mappings().one()
        for values in (row, source, charge):
            amounts(values, fields)
        if (row['organization_id'], row['branch_id'], row['scope_context_key']) != (scope.company_id, scope.branch_id, scope.context_id):
            fail('Checkout line scope differs')
        if (row['line_kind'] == 'booked_service' or source['sales_order_id'] != actual['id']
                or source['product_id'] != row['product_id'] or charge['invoice_id'] != bill['id']
                or charge['source_type'] != 'sales_order_line' or charge['source_id'] != source['id']
                or row['quantity'] <= 0 or row['discount_amount'] > row['quantity'] * row['unit_price']
                or any(source[key] != row[key] or charge[key] != row[key] for key in fields)):
            fail('Kitchen requires canonical unscheduled POS item lines')
        if settlement_order is not None:
            from .models import RestaurantTabLine
            snapshot = RestaurantTabLine.__table__
            frozen = connection.execute(select(snapshot).where(snapshot.c.service_order_id == settlement_order.id,
                snapshot.c.sales_order_line_id == source['id'], snapshot.c.organization_id == scope.company_id,
                snapshot.c.branch_id == scope.branch_id, snapshot.c.pack_context_id == scope.context_id)).mappings().one_or_none()
            if (frozen is None or row['discount_amount'] != 0 or any(frozen[key] != row[key] for key in ('product_id','quantity','unit_price','tax_amount','line_total'))
                    or frozen['item'] != source['description'] or frozen['warehouse_id'] != (source['metadata_json'] or {}).get('warehouse_id')
                    or frozen['catalog_tax_snapshot'] != row['catalog_tax_snapshot']
                    or frozen['catalog_tax_snapshot'] != (source['metadata_json'] or {}).get('tax_snapshot', {})):
                fail('Restaurant billed charge differs from immutable tab provenance')
            private(db, scope, RestaurantTabLine, frozen['id'])
        snapshots.append({'sales_order_line_id': source['id'], 'item': (source['description'] or source['item_code'] or 'Item')[:500],
                          'quantity': str(source['quantity'])})
    if sum((r['line_total'] for r in mapped), Decimal(0)) != bill['total_amount']:
        fail('Canonical invoice total differs')
    if settlement_order is not None and (actual['total_amount'] != bill['total_amount']
            or actual['discount_amount'] != 0 or actual['tax_amount'] != sum((r['tax_amount'] for r in mapped), Decimal(0))):
        fail('Restaurant billed header differs from immutable tab charges')
    receipt, allocation = SRMReceipt.__table__, SRMReceiptAllocation.__table__
    paid = Decimal(0)
    payments = connection.execute(select(*(mapped_payment.c[name] for name in ('id', 'organization_id', 'branch_id', 'scope_context_key', 'receipt_id', 'payment_key'))).where(mapped_payment.c.checkout_id == checkout_id)).mappings().all()
    if not payments and settlement_order is None:
        fail('A confirmed canonical payment is required')
    for payment in payments:
        if (payment['organization_id'], payment['branch_id'], payment['scope_context_key']) != (scope.company_id, scope.branch_id, scope.context_id):
            fail('Checkout payment scope differs')
        private(db, scope, POSCheckoutPayment, payment['id'])
        private(db, scope, SRMReceipt, payment['receipt_id'])
        r = connection.execute(select(receipt.c.id, receipt.c.organization_id, receipt.c.customer_id, receipt.c.currency,
            receipt.c.status, receipt.c.amount).where(receipt.c.id == payment['receipt_id'])).mappings().one()
        amounts(r, ('amount',))
        if (r['organization_id'], r['customer_id'], r['currency'], r['status']) != (scope.company_id, root['customer_id'], root['currency'], 'allocated'):
            fail('Canonical payment is no longer confirmed and fully allocated')
        allocations = connection.execute(select(allocation.c.id, allocation.c.invoice_id, allocation.c.request_id, allocation.c.amount).where(allocation.c.receipt_id == r['id'])).mappings().all()
        if not allocations or any(a['invoice_id'] != bill['id'] or a['request_id'] != payment['payment_key'] for a in allocations):
            fail('Canonical receipt allocation differs')
        for a in allocations:
            private(db, scope, SRMReceiptAllocation, a['id'])
            amounts(a, ('amount',))
            if a['amount'] <= 0:
                fail('Canonical receipt allocation is invalid')
            paid += a['amount']
        if sum((a['amount'] for a in allocations), Decimal(0)) != r['amount']:
            fail('Canonical payment amount differs')
    if paid != bill['paid_amount'] or (settlement_order is None and paid != bill['total_amount']):
        fail('Confirmed canonical allocations must fully settle the order')
    # No totals, customer, payment references, or invoice bodies escape.
    result = {'checkout_id': root['id'], 'checkout_revision': root['revision'], 'sales_order_id': actual['id'],
              'lines': sorted(snapshots, key=lambda r: r['sales_order_line_id'])}
    if settlement_order is not None:
        result['billing'] = {'checkout_id': root['id'], 'currency': root['currency'], 'total': str(bill['total_amount']),
            'paid': str(bill['paid_amount']), 'balance': str(bill['balance_amount'])}
    fingerprint = sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return result, fingerprint
