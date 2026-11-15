"""Item/quantity bills over original charges and canonical native money records."""
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from weakref import WeakKeyDictionary, WeakSet

from sqlalchemy import select, inspect, event, cast, String, and_
from sqlalchemy.orm import Session

from app.apps.srm.models import (SRMSalesOrder, SRMSalesOrderLine, SRMInvoice, SRMInvoiceLine,
    SRMReceipt, SRMReceiptAllocation, SRMPOSSession)
from app.apps.srm.service_checkout_models import POSServiceCheckout
from app.business_packs.native_checkout_authority import capture
from . import service, settlement
from .bill_allocations import Charge, Part, allocate
from .models import RestaurantServiceOrder as Order, RestaurantTabLine as Snapshot, RestaurantCommand, RestaurantKitchenTicket as Ticket
from .split_models import RestaurantBillGroup as Group, RestaurantBillLine as Line, RestaurantBillIssue as Issue, RestaurantBillReceipt as Payment


_active = WeakKeyDictionary()
_issued = WeakSet()
_pending = WeakKeyDictionary()
_collections = WeakKeyDictionary()
_new_sources = WeakKeyDictionary()
_invoice_objects = WeakKeyDictionary()
_receipt_objects = WeakKeyDictionary()
_native_facts = WeakKeyDictionary()


@dataclass(frozen=True, eq=False)
class _Issue:
    actor: object
    scope: object
    epoch: object
    order: object
    group: object
    lines: tuple
    native_order_id: int
    native_hash: str
    native_lines_hash: str

    @property
    def invoice(self):
        return _invoice_objects.get(self)


@dataclass(frozen=True, eq=False)
class _Collection:
    actor: object
    scope: object
    epoch: object
    order: object
    issue_id: int
    invoice_id: int
    register: object
    request_key: str
    request_sha256: str
    payment_key: str
    method: str
    amount: Decimal
    reference: str | None
    cashier_id: int | None
    currency: str | None

    @property
    def receipt(self):
        return _receipt_objects.get(self)


def _current_collection(db, plan):
    if type(plan) is not _Collection or plan not in _issued or _collections.get(db) is not plan:
        service.fail('An authentic same-session Restaurant collection command is required')
    if (settlement.authority(db, plan.actor, payments=True) != plan.scope or
            capture(db, plan.actor, plan.scope, order=False, billing=False, payments=True, write=True) != plan.epoch):
        service.fail('Restaurant split collection authority changed')
    issued = _row(db, Issue, plan.issue_id)
    register = _row(db, SRMPOSSession, plan.register.id)
    if (issued is None or issued['invoice_id'] != plan.invoice_id or register is None or register['status'] != 'open' or register['deleted_at'] is not None
            or register['cashier_user_id'] not in {None, plan.actor.id} or register['cashier_user_id'] != plan.cashier_id or _currency(register) != plan.currency):
        service.fail('Restaurant split collection source changed')
    _private(db, plan.scope, Issue, plan.issue_id)
    _private(db, plan.scope, SRMPOSSession, plan.register.id)
    if plan.receipt is not None:
        state = inspect(plan.receipt)
        receipt = _row(db, SRMReceipt, plan.receipt.id)
        invoice = _row(db, SRMInvoice, plan.invoice_id)
        if (type(plan.receipt) is not SRMReceipt or state.session is not db or not state.persistent or plan.receipt in db.deleted or
                receipt is None or invoice is None or (receipt['organization_id'], receipt['customer_id'], receipt['currency'],
                    receipt['created_by'], receipt['amount'], receipt['payment_method'], receipt['reference_number']) !=
                (plan.scope.company_id, invoice['customer_id'], invoice['currency'], plan.actor.id, plan.amount,
                    plan.method, plan.reference)):
            service.fail('Restaurant split collection receipt changed')


def validate_issue_insert(db, row):
    plan = _active.get(db)
    _current(db, plan)
    if (plan.invoice is None or row.group_id != plan.group.id or row.invoice_id != plan.invoice.id or
            (row.organization_id, row.branch_id, row.pack_context_id, row.created_by) !=
            (plan.scope.company_id, plan.scope.branch_id, plan.scope.context_id, plan.actor.id)):
        service.fail('Restaurant bill issuance differs from its exact command')


def validate_payment_insert(db, row):
    plan = _collections.get(db)
    _current_collection(db, plan)
    if (plan.receipt is None or (row.issue_id, row.receipt_id, row.collection_session_id, row.payment_key,
            row.request_key, row.request_sha256, row.organization_id, row.branch_id, row.pack_context_id, row.created_by) !=
            (plan.issue_id, plan.receipt.id, plan.register.id, plan.payment_key, plan.request_key,
                plan.request_sha256, plan.scope.company_id,
                plan.scope.branch_id, plan.scope.context_id, plan.actor.id)):
        service.fail('Restaurant bill receipt differs from its exact command')
    if (row.collection_cashier_id, row.collection_currency) != (plan.cashier_id, plan.currency):
        service.fail('Restaurant collection register differs from its exact command')
    allocation = _row(db, SRMReceiptAllocation, row.allocation_id)
    if allocation is None or (allocation['receipt_id'], allocation['invoice_id'], allocation['amount'], allocation['request_id']) != (
            plan.receipt.id, plan.invoice_id, plan.amount, plan.payment_key):
        service.fail('Restaurant collection has no exact native allocation')


def register_new_source(db, group_id, model, ident):
    _new_sources.setdefault(db, {})[(model, ident)] = (group_id, deepcopy(dict(_row(db, model, ident))))


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def _row(db, model, ident, columns=None):
    table = model.__table__
    fields = (table,) if columns is None else tuple(table.c[name] for name in columns)
    return db.connection().execute(select(*fields).where(table.c.id == ident)).mappings().one_or_none()


def _currency(register):
    from app.apps.srm.register_currency import valid_currency
    metadata = register['metadata_json']
    if metadata is None:
        return None
    if not isinstance(metadata, dict):
        service.fail('Restaurant collection register currency requires reconciliation', 409)
    if 'cash_currency' not in metadata:
        return None
    code = metadata['cash_currency']
    if not valid_currency(code):
        service.fail('Restaurant collection register currency requires reconciliation', 409)
    return code


def _register_commit_source(db, row):
    current = _row(db, SRMPOSSession, row['collection_session_id'], ('id','organization_id','status','deleted_at','cashier_user_id','metadata_json'))
    if (current is None or current['organization_id'] != row['organization_id'] or current['status'] != 'open' or current['deleted_at'] is not None
            or current['cashier_user_id'] != row['collection_cashier_id'] or _currency(current) != row['collection_currency']):
        service.fail('Restaurant collection register changed before commit', 409)


def _private(db, scope, model, ident):
    from .sources import private
    private(db, scope, model, ident)


def _current(db, plan):
    if type(plan) is not _Issue or plan not in _issued or _active.get(db) is not plan:
        service.fail('An authentic same-session Restaurant split command is required')
    if (settlement.authority(db, plan.actor, billing=True) != plan.scope or
            capture(db, plan.actor, plan.scope, order=False, billing=True, payments=False, write=True) != plan.epoch):
        service.fail('Restaurant split billing authority changed')
    state = inspect(plan.order)
    if state.session is not db or not state.persistent or plan.order in db.deleted:
        service.fail('Restaurant split parent identity changed')
    actual = _row(db, Order, plan.order.id)
    if (actual is None or (actual['organization_id'], actual['branch_id'], actual['pack_context_id'], actual['source_kind'], actual['state'], actual['sales_order_id']) !=
            (plan.scope.company_id, plan.scope.branch_id, plan.scope.context_id, 'unpaid_tab', 'open', plan.native_order_id)):
        service.fail('Restaurant split parent changed')
    if _hash(dict(_row(db, SRMSalesOrder, plan.native_order_id) or {})) != plan.native_hash:
        service.fail('Restaurant split native order changed')
    actual_lines = db.connection().execute(select(SRMSalesOrderLine.__table__).where(
        SRMSalesOrderLine.sales_order_id == plan.native_order_id).order_by(SRMSalesOrderLine.id)).mappings().all()
    if _hash([dict(row) for row in actual_lines]) != plan.native_lines_hash:
        service.fail('Restaurant split original charges changed')
    _private(db, plan.scope, Order, plan.order.id)
    _private(db, plan.scope, SRMSalesOrder, plan.native_order_id)
    _private(db, plan.scope, Group, plan.group.id)
    actual_parts = db.connection().execute(select(Line.id).where(Line.group_id == plan.group.id).order_by(Line.id)).scalars().all()
    if tuple(actual_parts) != plan.lines:
        service.fail('Restaurant split allocation identity changed')


def source_reserved(db, source_type, ident):
    plan = _active.get(db)
    _current(db, plan)
    if ((source_type == 'restaurant_bill' and ident != plan.group.id) or
            (source_type == 'restaurant_bill_line' and ident not in plan.lines) or
            source_type not in {'restaurant_bill', 'restaurant_bill_line'}):
        service.fail('Restaurant split source differs from its command')
    if source_type == 'restaurant_bill':
        return db.connection().scalar(select(Issue.id).where(Issue.group_id == ident)) is not None
    return db.connection().scalar(select(SRMInvoiceLine.id).where(
        SRMInvoiceLine.source_type == source_type, SRMInvoiceLine.source_id == ident)) is not None


def reserves_order(db, order_id):
    """Blind reservation bit: never adopt or hide another context's allocations."""
    return db.connection().scalar(select(Group.id).join(Order, Group.service_order_id == Order.id).where(
        Order.sales_order_id == order_id).limit(1)) is not None


def _part(row, snapshot):
    return Part(snapshot['id'], snapshot['original_sales_order_line_id'], row['quantity'], row['unit_price'], row['tax_amount'], row['line_total'])


def graph(db, scope, order, *, require_complete=False):
    """Validate durable allocations and native invoices without loading money ORM.

    This is proof for reads/reconciliation, never authority for new writes.
    Pending allocations are accepted only inside the actual issued command.
    """
    groups = db.connection().execute(select(Group.__table__).where(Group.service_order_id == order.id).order_by(Group.id)).mappings().all()
    if not groups:
        return None
    parent = _row(db, Order, order.id)
    if parent is None or (parent['organization_id'], parent['branch_id'], parent['pack_context_id'], parent['source_kind'], parent['checkout_id'], parent['sales_order_id']) != (
            scope.company_id, scope.branch_id, scope.context_id, 'unpaid_tab', None, order.sales_order_id):
        service.fail('Restaurant split original parent identity changed', 409)
    _private(db, scope, Order, order.id)
    _private(db, scope, SRMSalesOrder, order.sales_order_id)
    native = _row(db, SRMSalesOrder, order.sales_order_id, ('id','organization_id','customer_id','currency','total_amount','status','deleted_at'))
    if native is None or native['customer_id'] is None or native['organization_id'] != scope.company_id or native['status'] != 'draft' or native['deleted_at'] is not None:
        service.fail('Split invoices require the original named customer', 409)
    histories, invoices, bills = {}, set(), []
    for group in groups:
        if (group['organization_id'], group['branch_id'], group['pack_context_id']) != (scope.company_id, scope.branch_id, scope.context_id):
            service.fail('Restaurant split ownership changed')
        _private(db, scope, Group, group['id'])
        rows = db.connection().execute(select(Line.__table__).where(Line.group_id == group['id']).order_by(Line.id)).mappings().all()
        if not rows:
            service.fail('Restaurant split has no immutable allocations', 409)
        for row in rows:
            if (row['organization_id'], row['branch_id'], row['pack_context_id'], row['created_by']) != (
                    scope.company_id, scope.branch_id, scope.context_id, group['created_by']):
                service.fail('Restaurant split allocation birth identity changed', 409)
            _private(db, scope, Line, row['id'])
            snap = _row(db, Snapshot, row['snapshot_id'])
            if snap is None or snap['service_order_id'] != order.id or snap['sales_order_line_id'] is None:
                service.fail('Restaurant split original charge is unavailable', 409)
            _private(db, scope, Snapshot, snap['id'])
            source = Charge(snap['id'], snap['sales_order_line_id'], snap['quantity'], snap['unit_price'], snap['tax_amount'], snap['line_total'])
            history = histories.setdefault(snap['id'], [])
            expected = allocate(source, row['quantity'], history)
            if expected != _part(row, snap):
                service.fail('Restaurant split allocation differs from original charge', 409)
            history.append(expected)
        issued = db.connection().execute(select(Issue.__table__).where(Issue.group_id == group['id'])).mappings().one_or_none()
        plan = _active.get(db)
        pending = plan is not None and plan.group.id == group['id'] and not require_complete
        if pending:
            _current(db, plan)
        if issued is None:
            if not pending or plan.invoice is None:
                service.fail('Restaurant split is missing its canonical invoice', 409)
            invoice_id = plan.invoice.id
        else:
            _private(db, scope, Issue, issued['id'])
            if (issued['organization_id'], issued['branch_id'], issued['pack_context_id']) != (scope.company_id, scope.branch_id, scope.context_id):
                service.fail('Restaurant split issuance ownership changed', 409)
            invoice_id = issued['invoice_id']
        invoice = _row(db, SRMInvoice, invoice_id, ('id','organization_id','sales_order_id','customer_id','currency','engagement_id',
            'deleted_at','status','created_by','subtotal','discount_amount','tax_amount','total_amount','paid_amount','balance_amount'))
        _private(db, scope, SRMInvoice, invoice_id)
        if invoice is None or (invoice['organization_id'], invoice['sales_order_id'], invoice['customer_id'], invoice['currency'], invoice['engagement_id']) != (
                scope.company_id, order.sales_order_id, native['customer_id'], native['currency'], None) or invoice['deleted_at'] is not None:
            service.fail('Restaurant split canonical invoice identity changed', 409)
        if invoice['created_by'] != group['created_by'] or (issued is not None and issued['created_by'] != group['created_by']):
            service.fail('Restaurant split native invoice creator changed', 409)
        if invoice['status'] not in ({'draft', 'pending_approval', 'approved', 'sent', 'partially_paid', 'paid'} if pending else {'approved', 'sent', 'partially_paid', 'paid'}):
            service.fail('Restaurant split canonical invoice is unavailable', 409)
        charges = db.connection().execute(select(SRMInvoiceLine.__table__).where(SRMInvoiceLine.invoice_id == invoice_id)).mappings().all()
        expected_charges = {row['id']: row for row in rows}
        if len(charges) != len(rows) or {row['source_id'] for row in charges} != set(expected_charges):
            service.fail('Restaurant split native invoice mapping changed', 409)
        for charge in charges:
            _private(db, scope, SRMInvoiceLine, charge['id'])
            part = expected_charges[charge['source_id']]
            snapshot = _row(db, Snapshot, part['snapshot_id'])
            if (charge['source_type'] != 'restaurant_bill_line' or charge['description'] != snapshot['item'] or charge['discount_amount'] != 0 or
                    any(charge[key] != part[key] for key in ('quantity', 'unit_price', 'tax_amount', 'line_total'))):
                service.fail('Restaurant split native charge differs from allocation', 409)
        total = sum((row['line_total'] for row in rows), Decimal(0))
        tax = sum((row['tax_amount'] for row in rows), Decimal(0))
        if (invoice['subtotal'], invoice['discount_amount'], invoice['tax_amount'], invoice['total_amount']) != (total-tax, Decimal(0), tax, total) or total <= 0:
            service.fail('Restaurant split native invoice totals changed', 409)
        paid = Decimal(0)
        mappings = [] if issued is None else db.connection().execute(select(Payment.__table__).where(Payment.issue_id == issued['id'])).mappings().all()
        for mapped in mappings:
            if (mapped['organization_id'], mapped['branch_id'], mapped['pack_context_id']) != (scope.company_id, scope.branch_id, scope.context_id):
                service.fail('Restaurant split payment ownership changed', 409)
            _private(db, scope, Payment, mapped['id'])
            receipt = _row(db, SRMReceipt, mapped['receipt_id'], ('id','organization_id','customer_id','currency','status','amount','unallocated_amount','created_by','payment_method'))
            allocation = _row(db, SRMReceiptAllocation, mapped['allocation_id'], ('id','receipt_id','invoice_id','request_id','amount','allocated_by'))
            for model, ident in ((SRMReceipt, mapped['receipt_id']), (SRMReceiptAllocation, mapped['allocation_id']), (SRMPOSSession, mapped['collection_session_id'])):
                _private(db, scope, model, ident)
            if receipt is None or allocation is None or (receipt['organization_id'], receipt['customer_id'], receipt['currency'], receipt['status']) != (
                    scope.company_id, native['customer_id'], native['currency'], 'allocated') or receipt['amount'] <= 0 or receipt['unallocated_amount'] != 0:
                service.fail('Restaurant split receipt provenance changed', 409)
            if receipt['created_by'] != mapped['created_by'] or allocation['allocated_by'] != mapped['created_by']:
                service.fail('Restaurant split native payment creator changed', 409)
            from app.apps.srm.register_currency import valid_currency
            if ((mapped['collection_currency'] is not None and not valid_currency(mapped['collection_currency'])) or
                    (receipt.get('payment_method') == 'cash' and mapped['collection_currency'] != receipt['currency'])):
                service.fail('Restaurant split collection currency provenance changed', 409)
            allocations = db.connection().execute(select(SRMReceiptAllocation.id).where(SRMReceiptAllocation.receipt_id == receipt['id'])).scalars().all()
            if allocations != [allocation['id']] or (allocation['receipt_id'], allocation['invoice_id'], allocation['request_id'], allocation['amount']) != (
                    receipt['id'], invoice_id, mapped['payment_key'], receipt['amount']):
                service.fail('Restaurant split native receipt allocation changed', 409)
            payment_commands = db.connection().execute(select(RestaurantCommand.__table__).where(
                RestaurantCommand.service_order_id == order.id, RestaurantCommand.action == 'tab.split_payment',
                RestaurantCommand.request_key == mapped['request_key'], RestaurantCommand.request_sha256 == mapped['request_sha256'])).mappings().all()
            collection = _collections.get(db)
            pending_payment = (not require_complete and collection is not None and collection.issue_id == issued['id'] and
                collection.receipt is not None and collection.receipt.id == receipt['id'])
            if pending_payment:
                _current_collection(db, collection)
            if len(payment_commands) != 1:
                if not pending_payment:
                    service.fail('Restaurant split payment has no exact immutable command', 409)
            else:
                command = payment_commands[0]
                _private(db, scope, RestaurantCommand, command['id'])
                if (command['created_by'] != mapped['created_by'] or command['result'].get('bill_id') != issued['id'] or
                        command['result'].get('receipt_id') != receipt['id'] or command['result'].get('allocation_id') != allocation['id']):
                    service.fail('Restaurant split payment command source changed', 409)
            paid += allocation['amount']
        if (invoice['paid_amount'], invoice['balance_amount']) != (paid, total-paid) or paid > total:
            service.fail('Restaurant split payment balance differs from native allocations', 409)
        if not pending:
            commands = db.connection().execute(select(RestaurantCommand.__table__).where(RestaurantCommand.service_order_id == order.id,
                RestaurantCommand.action == 'tab.split_bill', RestaurantCommand.request_key == group['request_key'],
                RestaurantCommand.request_sha256 == group['request_sha256'])).mappings().all()
            if len(commands) != 1 or commands[0]['created_by'] != group['created_by'] or commands[0]['result'].get('bill_id') != issued['id'] or commands[0]['result'].get('invoice_id') != invoice_id:
                service.fail('Restaurant split has no exact immutable command', 409)
            _private(db, scope, RestaurantCommand, commands[0]['id'])
        invoices.add(invoice_id)
        bills.append({'bill_id': issued['id'] if issued else None, 'invoice_id': invoice_id, 'total': str(total),
            'paid': str(paid), 'balance': str(total-paid), 'currency': native['currency'],
            'items': [{'sales_order_line_id': _row(db, Snapshot, row['snapshot_id'])['original_sales_order_line_id'],
                'quantity': str(row['quantity']), 'total': str(row['line_total'])} for row in rows]})
    actual_invoices = set(db.connection().execute(select(SRMInvoice.id).where(SRMInvoice.sales_order_id == order.sales_order_id)).scalars())
    if actual_invoices != invoices or db.connection().scalar(select(POSServiceCheckout.id).where(POSServiceCheckout.sales_order_id == order.sales_order_id)):
        service.fail('Restaurant split conflicts with another native billing source', 409)
    full = db.connection().execute(select(Snapshot.__table__).where(Snapshot.service_order_id == order.id, Snapshot.sales_order_line_id.is_not(None))).mappings().all()
    complete = all(sum((part.quantity for part in histories.get(row['id'], ())), Decimal(0)) == row['quantity'] for row in full)
    paid = sum((Decimal(row['paid']) for row in bills), Decimal(0))
    if parent['state'] == 'served':
        sent = service.sent_quantities(db, scope, order)
        outstanding = db.connection().scalar(select(Ticket.id).where(Ticket.service_order_id == order.id, Ticket.state != 'served').limit(1))
        if not complete or paid != native['total_amount'] or outstanding is not None or any(sent.get(row['sales_order_line_id'], 0) != row['quantity'] for row in full):
            service.fail('Restaurant split tab cannot close before complete billing, payment and service', 409)
    return {'bills': bills, 'histories': histories, 'billing': {'kind': 'split', 'currency': native['currency'],
        'total': str(native['total_amount']), 'paid': str(paid), 'balance': str(native['total_amount']-paid), 'fully_allocated': complete}}


def assert_invoice_source(db, invoice):
    aliases = db.connection().execute(select(SRMInvoiceLine.source_id).where(SRMInvoiceLine.invoice_id == invoice.id,
        SRMInvoiceLine.source_type == 'restaurant_bill_line')).scalars().all()
    if not aliases:
        return False
    line = _row(db, Line, aliases[0])
    group = _row(db, Group, line['group_id']) if line else None
    if group is None:
        service.fail('Restaurant split native source is missing', 409)
    scope = db.info['business_pack_scope']
    order = service.record(db, Order, scope, group['service_order_id'])
    if not any(row['invoice_id'] == invoice.id for row in graph(db, scope, order)['bills']):
        service.fail('Restaurant split invoice has no exact original source', 409)
    return True


def tab_billing(db, scope, order):
    proof = graph(db, scope, order)
    return None if proof is None else proof['billing']


def _known_split_data(db, scope, inspector):
    """Existence-only quarantine when physical attribution schema is incomplete."""
    from .split_models import MODELS
    connection = db.connection()
    for model in MODELS:
        if not inspector.has_table(model.__tablename__):
            continue
        if not connection.exec_driver_sql('SELECT 1 FROM '+model.__tablename__+' LIMIT 1').first():
            continue
        columns = {item['name'] for item in inspector.get_columns(model.__tablename__)}
        if not {'organization_id','branch_id','pack_context_id'} <= columns:
            return True
        if not all(type(getattr(scope, key, None)) is int for key in ('company_id','branch_id','context_id')):
            service.fail('Restaurant collection source authorization changed')
        if connection.execute(select(1).select_from(model.__table__).where(model.organization_id == scope.company_id,
                model.branch_id == scope.branch_id, model.pack_context_id == scope.context_id).limit(1)).first():
            return True
    if not inspector.has_table(SRMInvoiceLine.__tablename__):
        return False
    line = SRMInvoiceLine.__table__
    if not connection.execute(select(1).select_from(line).where(line.c.source_type == 'restaurant_bill_line').limit(1)).first():
        return False
    from app.business_packs.models import PackRecordOwnership
    if not inspector.has_table(PackRecordOwnership.__tablename__) or not inspector.has_table(SRMInvoice.__tablename__):
        return True
    if not all(type(getattr(scope, key, None)) is int for key in ('company_id','branch_id','context_id')):
        service.fail('Restaurant collection source authorization changed')
    invoice, owner = SRMInvoice.__table__, PackRecordOwnership.__table__
    return connection.execute(select(1).select_from(line.join(invoice, invoice.c.id == line.c.invoice_id).join(owner,
        and_(owner.c.resource_table == invoice.name, owner.c.resource_key == cast(invoice.c.id, String)))).where(
        line.c.source_type == 'restaurant_bill_line', invoice.c.organization_id == scope.company_id,
        owner.c.company_id == scope.company_id, owner.c.branch_id == scope.branch_id, owner.c.context_id == scope.context_id).limit(1)).first() is not None


def register_cash(db, session):
    """Only actual allocation-backed cash collected in this exact register."""
    from types import SimpleNamespace
    scope = db.info.get('business_pack_scope')
    result = {'cash_received': Decimal(0), 'cash_by_currency': {}, 'receipt_ids': set(), 'collection_count': 0}
    if scope is None or scope.pack_key != 'restaurant':
        return result
    inspector = inspect(db.connection())
    present = inspector.has_table(Payment.__tablename__)
    complete = present and set(Payment.__table__.c.keys()) <= {column['name'] for column in inspector.get_columns(Payment.__tablename__)}
    if not complete:
        if _known_split_data(db, scope, inspector):
            service.fail('Restaurant collection provenance requires reconciliation', 503)
        return result
    rows = db.connection().execute(select(Payment.__table__).where(Payment.collection_session_id == session.id)).mappings().all()
    if not rows:
        return result  # Ordinary/legacy registers have no new split provenance.
    from .split_models import MODELS
    if any(not inspector.has_table(model.__tablename__) or not set(model.__table__.c.keys()) <=
            {column['name'] for column in inspector.get_columns(model.__tablename__)} for model in MODELS):
        service.fail('Restaurant collection provenance requires reconciliation', 503)
    _private(db, scope, SRMPOSSession, session.id)
    current = _row(db, SRMPOSSession, session.id, ('id','organization_id'))
    if current is None or current['organization_id'] != scope.company_id:
        service.fail('Restaurant collection register identity changed', 503)
    validated = set()
    for row in rows:
        issued = _row(db, Issue, row['issue_id'])
        group = _row(db, Group, issued['group_id']) if issued else None
        original = _row(db, Order, group['service_order_id']) if group else None
        if original is None:
            service.fail('Restaurant collection has no original source', 503)
        if original['id'] not in validated:
            graph(db, scope, SimpleNamespace(**original))
            validated.add(original['id'])
        result['collection_count'] += 1
        receipt = _row(db, SRMReceipt, row['receipt_id'], ('id','payment_method','currency','amount'))
        if receipt['payment_method'] != 'cash':
            continue
        code = receipt['currency']
        from app.apps.srm.register_currency import valid_currency
        if not valid_currency(code) or receipt['id'] in result['receipt_ids']:
            service.fail('Restaurant register cash requires reconciliation', 503)
        result['receipt_ids'].add(receipt['id'])
        result['cash_received'] += receipt['amount']
        result['cash_by_currency'][code] = result['cash_by_currency'].get(code, Decimal(0)) + receipt['amount']
    return result


def _guard_until_commit(db, actor, scope, order, *, billing=False, payments=False, facts=()):
    epoch = capture(db, actor, scope, order=False, billing=billing, payments=payments, write=True)
    _pending.setdefault(db, []).append((actor, scope, order, epoch, billing, payments))
    for model, ident in facts:
        excluded = {'status', 'paid_amount', 'balance_amount', 'sent_at', 'updated_at'} if model is SRMInvoice else set()
        values = {key: value for key, value in _row(db, model, ident).items() if key not in excluded}
        _native_facts.setdefault(db, {})[(model, ident)] = (excluded, _hash(values))


@event.listens_for(Session, 'before_commit')
def _verify_outer_commit(db):
    if db.in_nested_transaction():
        return
    from .split_models import MODELS
    if db in _pending or any(type(row) in MODELS for row in (*db.new, *db.dirty, *db.deleted)):
        db.flush()
    for (model, ident), (group_id, original) in _new_sources.get(db, {}).items():
        actual = _row(db, model, ident)
        if actual is None:
            continue  # A failed nested command rolled back only its own rows.
        if dict(actual) != original:
            service.fail('An immutable Restaurant split source changed before commit')
        if model is Payment:
            _register_commit_source(db, actual)
        group = _row(db, Group, group_id)
        if group is None or not any(order.id == group['service_order_id'] for _, _, order, _, _, _ in _pending.get(db, ())):
            service.fail('A pending Restaurant split source cannot commit without its command')
    for actor, scope, order, epoch, billing, payments in _pending.get(db, ()):
        if (settlement.authority(db, actor, billing=billing, payments=payments) != scope or
                capture(db, actor, scope, order=False, billing=billing, payments=payments, write=True) != epoch):
            service.fail('Restaurant split authority changed before commit')
        service.order_source(db, actor, scope, order)
        graph(db, scope, order, require_complete=True)
    for (model, ident), (excluded, fingerprint) in _native_facts.get(db, {}).items():
        row = _row(db, model, ident)
        if row is None or _hash({key: value for key, value in row.items() if key not in excluded}) != fingerprint:
            service.fail('Restaurant canonical financial source changed before commit', 409)


@event.listens_for(Session, 'after_transaction_end')
def _clear_pending(db, transaction):
    if transaction.parent is None:
        _pending.pop(db, None)
        _new_sources.pop(db, None)
        _native_facts.pop(db, None)


def issue(ident, data, db, actor, *, commit=True):
    from app.apps.srm.api import router as native
    from app.apps.srm import service_checkout as checkout
    from . import tabs
    scope = settlement.writer(db, actor, billing=True)
    order = service.record(db, Order, scope, ident)
    replay = service.prior(db, actor, scope, 'tab.split_bill', ident, data)
    if replay is not None:
        return replay
    if order.source_kind != 'unpaid_tab' or order.state != 'open' or order.revision != data.expected_revision:
        service.fail('Only the current open unpaid tab can issue a split bill', 409)
    original = tabs.source(db, actor, scope, order)
    if not original['customer_assigned'] or (original.get('billing') and original['billing'].get('kind') != 'split'):
        service.fail('Split bills require an original named unbilled tab; anonymous split is unsupported', 409)
    sent = service.sent_quantities(db, scope, order)
    if any(sent.get(line['sales_order_line_id'], Decimal(0)) != Decimal(line['quantity']) for line in original['lines']):
        service.fail('Send every ordered item to the kitchen before split billing', 409)
    existing = graph(db, scope, order)
    histories = {} if existing is None else existing['histories']
    snapshots = {row.sales_order_line_id: row for row in service.scoped(db, Snapshot, scope).filter_by(service_order_id=order.id).all() if row.sales_order_line_id is not None}
    planned = []
    for requested in data.lines:
        snapshot = snapshots.get(requested.sales_order_line_id)
        if snapshot is None:
            service.fail('Choose an active original item from this tab', 409)
        part = allocate(Charge(snapshot.id, snapshot.sales_order_line_id, snapshot.quantity, snapshot.unit_price, snapshot.tax_amount, snapshot.line_total),
            requested.quantity, histories.get(snapshot.id, ()))
        planned.append((snapshot, part))
    if sum((part.line_total for _, part in planned), Decimal(0)) != data.expected_total:
        service.fail('Split bill total changed; review its original charges', 409)
    native_order = db.get(SRMSalesOrder, order.sales_order_id)
    if native_order.subtotal != sum((row.line_total-row.tax_amount for row in snapshots.values()), Decimal(0)):
        service.fail('Original native charge cents require reconciliation before split billing', 409)
    from app.apps.srm.services.commercial import customer
    customer(db, native_order.customer_id, actor)
    plan = None
    try:
        with db.begin_nested():
            group = Group(**service.fields(scope, actor), service_order_id=order.id, request_key=str(data.request_key), request_sha256=service.digest('tab.split_bill', ident, data))
            db.add(group); db.flush()
            rows = []
            for snapshot, part in planned:
                row = Line(**service.fields(scope, actor), group_id=group.id, snapshot_id=snapshot.id,
                    **{key: getattr(part, key) for key in ('quantity', 'unit_price', 'tax_amount', 'line_total')})
                db.add(row); db.flush(); rows.append(row)
            if db in _active:
                service.fail('Restaurant split commands cannot nest')
            plan = _Issue(actor, scope, capture(db, actor, scope, order=False, billing=True, payments=False, write=True), order, group,
                tuple(row.id for row in rows), native_order.id, _hash(dict(_row(db, SRMSalesOrder, native_order.id))),
                _hash([dict(row) for row in db.connection().execute(select(SRMSalesOrderLine.__table__).where(
                    SRMSalesOrderLine.sales_order_id == native_order.id).order_by(SRMSalesOrderLine.id)).mappings()]))
            _active[db] = plan; _issued.add(plan)
            invoice = native._create_invoice_from_lines(db, actor, 'restaurant_bill', group.id, None, native_order,
                [{'source_type': 'restaurant_bill_line', 'source_id': row.id, 'description': snapshot.item, 'discount_amount': 0,
                    **{key: getattr(row, key) for key in ('quantity', 'unit_price', 'tax_amount', 'line_total')}} for row, (snapshot, _) in zip(rows, planned)], native_order.currency)
            _invoice_objects[plan] = invoice
            db.flush()
            checkout._stamp_new(db, scope, scope.company_id, scope.branch_id, [invoice, *db.query(SRMInvoiceLine).filter_by(invoice_id=invoice.id).all()])
            native.approve_invoice_operation(invoice.id, db, actor, commit=False)
            issued = Issue(**service.fields(scope, actor), group_id=group.id, invoice_id=invoice.id)
            db.add(issued); order.revision += 1; db.flush()
            answer = {'order_id': order.id, 'order_revision': order.revision, 'bill_id': issued.id, 'invoice_id': invoice.id,
                'bill': next(row for row in graph(db, scope, order)['bills'] if row['bill_id'] == issued.id)}
            service.save_command(db, actor, scope, 'tab.split_bill', ident, data, answer, order=order)
        _current(db, plan)
        graph(db, scope, order, require_complete=True)
        _guard_until_commit(db, actor, scope, order, billing=True, facts=[(SRMInvoice, invoice.id),
            *((SRMInvoiceLine, ident) for ident in db.connection().execute(select(SRMInvoiceLine.id).where(SRMInvoiceLine.invoice_id == invoice.id)).scalars())])
        if commit:
            db.commit()
        return answer
    finally:
        if plan is not None:
            _active.pop(db, None); _issued.discard(plan); _invoice_objects.pop(plan, None)


def listing(ident, db, actor):
    scope = settlement.authority(db, actor, write=False)
    order = service.record(db, Order, scope, ident)
    from .tabs import source
    source(db, actor, scope, order)
    proof = graph(db, scope, order)
    return {'order_id': order.id, 'order_revision': order.revision, 'bills': [] if proof is None else proof['bills']}


def pay(ident, bill_id, data, db, actor, *, commit=True):
    from app.apps.srm.api import router as native
    from app.apps.srm import service_checkout as checkout
    from app.apps.srm.schemas import SRMReceiptCreate, SRMReceiptAllocationRequest
    from app.apps.srm.register_currency import require_cash_currency
    from .tabs import source
    scope = settlement.writer(db, actor, payments=True)
    epoch = capture(db, actor, scope, order=False, billing=False, payments=True, write=True)
    order = service.record(db, Order, scope, ident)
    replay = service.prior(db, actor, scope, 'tab.split_payment', bill_id, data)
    if replay is not None:
        if replay.get('order_id') != order.id:
            service.fail('Split payment belongs to a different original tab', 409)
        return replay
    proof = graph(db, scope, order)
    bill = next((row for row in (proof or {}).get('bills', ()) if row['bill_id'] == bill_id), None)
    if bill is None:
        service.fail('Restaurant split bill is unavailable', 404)
    if order.state != 'open' or order.revision != data.expected_revision or Decimal(bill['balance']) != data.expected_balance:
        service.fail('Split bill changed; reload its current balance', 409)
    if data.payment.amount > Decimal(bill['balance']):
        service.fail('Split payment exceeds its current native invoice balance', 422)
    if db.connection().scalar(select(Payment.id).where(Payment.payment_key == str(data.payment.payment_key),
            Payment.pack_context_id == scope.context_id)):
        service.fail('Split payment key was already used by another command', 409)
    source(db, actor, scope, order)
    plan = None
    try:
        with db.begin_nested():
            register = checkout._collection_register(db, actor, scope.company_id, scope.branch_id, scope, data.pos_session_id)
            invoice = db.get(SRMInvoice, bill['invoice_id'])
            if data.payment.method == 'cash':
                require_cash_currency(db, register, invoice.currency)
            if db in _collections:
                service.fail('Restaurant split collections cannot nest')
            actual_register = _row(db, SRMPOSSession, register.id)
            plan = _Collection(actor, scope, epoch, order, bill_id, invoice.id, register, str(data.request_key),
                service.digest('tab.split_payment', bill_id, data), str(data.payment.payment_key), data.payment.method, data.payment.amount, data.payment.reference,
                actual_register['cashier_user_id'], _currency(actual_register))
            _collections[db] = plan; _issued.add(plan)
            _current_collection(db, plan)
            receipt_data = SRMReceiptCreate(customer_id=invoice.customer_id, currency=invoice.currency, amount=data.payment.amount,
                payment_method=data.payment.method, reference_number=data.payment.reference)
            created = native.create_receipt_operation(receipt_data, db, actor, commit=False)
            receipt = db.get(SRMReceipt, created['id'])
            _receipt_objects[plan] = receipt
            _current_collection(db, plan)
            checkout._stamp_new(db, scope, scope.company_id, scope.branch_id, [receipt])
            native.confirm_receipt_operation(receipt.id, db, actor, commit=False)
            _current_collection(db, plan)
            result = native.allocate_receipt_operation(receipt.id, SRMReceiptAllocationRequest(invoice_id=invoice.id,
                amount=data.payment.amount, request_id=data.payment.payment_key), db, actor, commit=False)
            allocation = db.get(SRMReceiptAllocation, result['allocation']['id'])
            checkout._stamp_new(db, scope, scope.company_id, scope.branch_id, [allocation])
            mapped = Payment(**service.fields(scope, actor), issue_id=bill_id, receipt_id=receipt.id, allocation_id=allocation.id,
                collection_session_id=register.id, payment_key=str(data.payment.payment_key),
                collection_cashier_id=plan.cashier_id, collection_currency=plan.currency,
                request_key=str(data.request_key), request_sha256=service.digest('tab.split_payment', bill_id, data))
            db.add(mapped); order.revision += 1; db.flush()
            # Preserve both native create and pack payment authority after all callbacks.
            if capture(db, actor, scope, order=False, billing=False, payments=True, write=True) != epoch:
                service.fail('Restaurant split collection authority changed')
            proof = source(db, actor, scope, order)
            settlement.close_if_settled(db, scope, order, proof)
            answer = {'order_id': order.id, 'order_revision': order.revision, 'bill_id': bill_id,
                'receipt_id': receipt.id, 'allocation_id': allocation.id,
                'bill': next(row for row in graph(db, scope, order)['bills'] if row['bill_id'] == bill_id)}
            service.save_command(db, actor, scope, 'tab.split_payment', bill_id, data, answer, order=order)
        _current_collection(db, plan)
        _guard_until_commit(db, actor, scope, order, payments=True, facts=[(SRMReceipt, receipt.id),
            (SRMReceiptAllocation, allocation.id), (SRMInvoice, invoice.id)])
        graph(db, scope, order, require_complete=True)
        if commit:
            db.commit()
        return answer
    finally:
        if plan is not None:
            _collections.pop(db, None); _issued.discard(plan); _receipt_objects.pop(plan, None)
