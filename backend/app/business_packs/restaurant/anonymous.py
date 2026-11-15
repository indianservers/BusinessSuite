"""One atomic full counter settlement over an existing, already-fired tab."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from weakref import WeakKeyDictionary
from uuid import uuid5, NAMESPACE_URL
from sqlalchemy import event, inspect, select
from app.apps.srm.models import SRMSalesOrder, SRMInvoice, SRMReceipt
from app.apps.srm.service_checkout_models import POSServiceCheckout, POSCheckoutPayment
from app.apps.srm import service_checkout as native
from app.apps.srm.anonymous_cash import resolve_account, checkout_permit, _authorized
from app.business_packs.native_checkout_authority import capture
from .models import RestaurantServiceOrder as Order, RestaurantCommand as Command, RestaurantKitchenTicket as Ticket
from .schemas import TabAnonymousSettle, TabAssignCustomer, TabBill
from .service import fail, record, prior, save_command, digest, sent_quantities, scoped
from .sources import paid_source, private

_leases = WeakKeyDictionary()


def key(request, purpose):
    return uuid5(NAMESPACE_URL, f'restaurant-anonymous:{request}:{purpose}')


def _epoch(db, actor, scope):
    return capture(db, actor, scope, order=True, billing=True, payments=True, write=True)


def writer(db, actor):
    from .service import authority, lock_tenant
    scope = db.info.get('business_pack_scope')
    required = {'restaurant.orders.create','restaurant.billing.prepare','restaurant.payments.record'}
    if scope is None or scope.pack_key != 'restaurant' or not required <= scope.capabilities:
        fail('Restaurant order, invoice and collection authority are all required')
    epoch = _epoch(db, actor, scope)  # Before the first company writer wait.
    if authority(db, actor, 'orders.create', write=True) is not scope:
        fail('Restaurant anonymous source scope changed')
    native._authority(db, actor, order=False, billing=True, payments=True)
    lock_tenant(db, actor)
    if (authority(db, actor, 'orders.create', write=True) is not scope or _epoch(db, actor, scope) != epoch):
        fail('Native anonymous settlement authority changed while waiting')
    native._authority(db, actor, order=False, billing=True, payments=True)
    return scope, epoch


@dataclass
class _Plan:
    scope: object
    actor: object
    epoch: object
    order: object
    payload: object
    payload_hash: str
    account: dict
    original: dict
    original_order: dict
    bound: dict | None = None
    stage: str = 'bind'
    complete: bool = False


def _valid_plan(db, plan):
    if not isinstance(plan, _Plan) or _leases.get(db) is not plan:
        return False
    from app.apps.srm.anonymous_cash import _CONTROL
    actual = db.connection().execute(select(_CONTROL).where(_CONTROL.c.id == plan.account['id'])).mappings().one_or_none()
    if (not isinstance(plan, _Plan) or _leases.get(db) is not plan or db.info.get('business_pack_scope') is not plan.scope
            or inspect(plan.actor).session is not db or not inspect(plan.actor).persistent
            or inspect(plan.order).session is not db or not inspect(plan.order).persistent
            or plan.scope.user_id != plan.actor.id or _epoch(db, plan.actor, plan.scope) != plan.epoch
            or digest('tab.settle_anonymous', plan.order.id, plan.payload) != plan.payload_hash
            or actual is None or any(actual[name] != value for name,value in plan.account.items())
            or not _authorized(db.connection(), actual, financial=True)):
        return False
    return True


def _full_group(db, scope, order, result, payload, *, result_snapshot=True):
    """Fixed actual source/money projection; no arbitrary checkout/account IDs."""
    c, invoice, payment, receipt = (model.__table__ for model in (POSServiceCheckout, SRMInvoice, POSCheckoutPayment, SRMReceipt))
    root = db.connection().execute(select(c).where(c.c.sales_order_id == order.sales_order_id,
        c.c.organization_id == scope.company_id, c.c.branch_id == scope.branch_id, c.c.pack_context_id == scope.context_id)).mappings().one_or_none()
    if (root is None or root['id'] != result.get('checkout', {}).get('id') or root['state'] != 'committed'
            or root['request_id'] != str(key(payload.request_key, 'bill'))):
        return False
    bill = db.connection().execute(select(invoice).where(invoice.c.id == root['invoice_id'],
        invoice.c.sales_order_id == root['sales_order_id'], invoice.c.customer_id == root['customer_id'],
        invoice.c.organization_id == scope.company_id, invoice.c.currency == root['currency'])).mappings().one_or_none()
    if (bill is None or bill['total_amount'] != payload.expected_total or bill['paid_amount'] != payload.expected_total
            or bill['balance_amount'] != 0 or bill['status'] != 'paid'):
        return False
    if result_snapshot:
        saved = result.get('checkout', {})
        invoice_dto = saved.get('invoice', {})
        try:
            if (saved.get('sales_order_id') != root['sales_order_id'] or invoice_dto.get('id') != bill['id']
                    or invoice_dto.get('number') != bill['invoice_number'] or invoice_dto.get('currency') != bill['currency']
                    or invoice_dto.get('status') != bill['status'] or Decimal(invoice_dto['total']) != bill['total_amount']
                    or Decimal(invoice_dto['paid']) != bill['paid_amount'] or Decimal(invoice_dto['balance']) != 0):
                return False
        except (ValueError,TypeError,KeyError,ArithmeticError):
            return False
    mapped = db.connection().execute(select(payment.c.payment_key, payment.c.collection_session_id,
        receipt.c.amount, receipt.c.payment_method, receipt.c.reference_number).select_from(
        payment.join(receipt, payment.c.receipt_id == receipt.c.id)).where(payment.c.checkout_id == root['id'])).mappings().all()
    expected = {str(item.payment_key): item for item in payload.payments}
    if len(mapped) != len(expected) or {item['payment_key'] for item in mapped} != set(expected):
        return False
    return all(item['amount'] == expected[item['payment_key']].amount
        and item['payment_method'] == expected[item['payment_key']].method
        and (item['reference_number'] or None) == (expected[item['payment_key']].reference or None)
        and item['collection_session_id'] == payload.pos_session_id for item in mapped)


def authorized_birth(db, scope, order, actual, transition):
    """An anonymous identity is valid only live-atomic or durably fully settled."""
    from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
    account = AnonymousCashAccount.__table__
    account_id = transition['result'].get('account_id')
    source = db.connection().execute(select(account).where(account.c.id == account_id,
        account.c.organization_id == scope.company_id, account.c.branch_id == scope.branch_id,
        account.c.pack_context_id == scope.context_id, account.c.customer_id == actual['customer_id'],
        account.c.kind == 'anonymous_cash')).mappings().one_or_none()
    if source is None:
        return False
    private(db, scope, AnonymousCashAccount, source['id'])
    plan = _leases.get(db)
    if plan is not None:
        if not _valid_plan(db, plan) or plan.order is not order or plan.bound is None or plan.account['id'] != source['id']:
            return False
        native_table = SRMSalesOrder.__table__
        stored = db.connection().execute(select(native_table).where(native_table.c.id == actual['id'])).mappings().one_or_none()
        if stored is None or dict(stored) != plan.bound:
            return False
        table = Order.__table__
        current = db.connection().execute(select(table).where(table.c.id == order.id)).mappings().one()
        fixed = set(table.c.keys()) - {'revision','state'}
        if any(current[name] != plan.original_order[name] for name in fixed):
            return False
        first = plan.payload.expected_revision
        if plan.stage == 'bind':
            return current['revision'] == first+1 and current['state'] == 'open'
        if plan.stage == 'bill' and current['revision'] in {first+1,first+2} and current['state'] == 'open':
            return True
        if plan.stage in {'pay','final'}:
            if current['revision'] == first+2 and current['state'] == 'open':
                return True
            if current['revision'] == first+3 and current['state'] == 'served':
                root = db.connection().execute(select(POSServiceCheckout.id).where(POSServiceCheckout.sales_order_id == order.sales_order_id)).scalar_one_or_none()
                if root is None or not _full_group(db, scope, order, {'checkout': {'id': root}}, plan.payload, result_snapshot=False):
                    return False
                return scoped(db, Ticket, scope).filter(Ticket.service_order_id == order.id, Ticket.state != 'served').first() is None
        return False
    command = Command.__table__
    rows = db.connection().execute(select(command).where(command.c.service_order_id == order.id,
        command.c.organization_id == scope.company_id, command.c.branch_id == scope.branch_id,
        command.c.pack_context_id == scope.context_id, command.c.action == 'tab.settle_anonymous')).mappings().all()
    if len(rows) != 1 or not isinstance(rows[0]['result'], dict):
        return False
    result = rows[0]['result']
    try:
        payload = TabAnonymousSettle.model_validate(result['plan'])
    except (ValueError,KeyError,TypeError):
        return False
    if (str(payload.request_key) != rows[0]['request_key'] or rows[0]['request_sha256'] != digest('tab.settle_anonymous', order.id, payload)
            or transition['request_key'] != str(key(payload.request_key, 'identity'))
            or transition['created_by'] != rows[0]['created_by'] or transition['result'].get('account_id') != result.get('account_id')):
        return False
    private(db, scope, Command, rows[0]['id'])
    return _full_group(db, scope, order, result, payload)


@contextmanager
def _settling(db, plan):
    if db in _leases:
        fail('Anonymous Restaurant settlements cannot nest')
    _leases[db] = plan
    def before_commit(session):
        if session.get_nested_transaction() is not None:
            return  # Releasing a savepoint cannot commit the outer transaction.
        if not plan.complete or not _valid_plan(session, plan):
            fail('An incomplete anonymous Restaurant settlement cannot commit', 409)
        _verify_finished(session, plan)
    event.listen(db, 'before_commit', before_commit)
    try:
        yield
        if not plan.complete:
            fail('Anonymous Restaurant settlement did not complete', 409)
    finally:
        event.remove(db, 'before_commit', before_commit)
        _leases.pop(db, None)


def _verify_finished(db, plan):
    from .tabs import source
    if not _valid_plan(db, plan):
        fail('Anonymous Restaurant source authorization changed')
    proof = source(db, plan.actor, plan.scope, plan.order)
    if not proof.get('billing') or Decimal(proof['billing']['balance']) != 0:
        fail('Anonymous Restaurant invoice must be fully settled', 409)
    row = scoped(db, Command, plan.scope).filter_by(action='tab.settle_anonymous', service_order_id=plan.order.id).one_or_none()
    if (row is None or row.request_key != str(plan.payload.request_key) or row.request_sha256 != plan.payload_hash
            or row.created_by != plan.actor.id or row.result.get('plan') != plan.payload.model_dump(mode='json')
            or row.result.get('account_id') != plan.account['id']
            or not _full_group(db, plan.scope, plan.order, row.result, plan.payload)):
        fail('Anonymous Restaurant final payment provenance is incomplete', 409)
    root = db.query(POSServiceCheckout).filter_by(sales_order_id=plan.order.sales_order_id).one()
    native.checkout_result(root, db, scope=plan.scope)  # Actual native allocations, fiscal snapshots and mappings.


def settle(ident, data, db, actor, *, commit=True):
    from app.apps.crm.models import CRMCompany
    from app.apps.srm.access import get_sales_order_for_user
    from app.apps.srm.service_checkout_schemas import AppendPaymentInput
    from .tabs import source
    from .references import customer_update
    from .settlement import bill, result
    data = TabAnonymousSettle.model_validate(data.model_dump())
    scope, epoch = writer(db, actor)
    order = record(db, Order, scope, ident)
    account = resolve_account(db, actor, scope.company_id, scope.branch_id, scope)
    replay = prior(db, actor, scope, 'tab.settle_anonymous', ident, data)
    if replay is not None:
        source(db, actor, scope, order)
        return replay
    proof = source(db, actor, scope, order)
    if (order.source_kind != 'unpaid_tab' or order.state != 'open' or order.revision != data.expected_revision
            or proof.get('billing') or proof['customer_assigned'] or Decimal(proof['total']) != data.expected_total):
        fail('Choose the current unbilled walk-in tab and its exact full total', 409)
    sent = sent_quantities(db, scope, order)
    if any(sent.get(line['sales_order_line_id'], Decimal(0)) != Decimal(line['quantity']) for line in proof['lines']):
        fail('Send every ordered item to the kitchen before anonymous settlement', 409)
    native._collection_register(db, actor, scope.company_id, scope.branch_id, scope, data.pos_session_id)
    original = get_sales_order_for_user(db, order.sales_order_id, actor)
    snapshots = [deepcopy(dict(db.connection().execute(select(model.__table__).where(model.id == row.id)).mappings().one()))
        for model,row in ((SRMSalesOrder, original), (Order, order))]
    plan = _Plan(scope, actor, epoch, order, data, digest('tab.settle_anonymous', ident, data), account, *snapshots)
    with checkout_permit(db, actor, account, scope) as permit:
        # The same existing native permit contract: a fully funded validated plan,
        # one atomic transaction, and actual full allocations checked before commit.
        permit.financial_ready = True
        with _settling(db, plan):
            with db.begin_nested():
                selected = db.get(CRMCompany, account['customer_id'])
                binding = TabAssignCustomer(request_key=key(data.request_key, 'identity'),
                    expected_revision=data.expected_revision, customer_id=account['customer_id'])
                with customer_update(db, actor, scope, epoch, original, order, selected):
                    original.customer_id = selected.id
                    order.revision += 1
                    db.flush()
                bound = dict(db.connection().execute(select(SRMSalesOrder.__table__).where(SRMSalesOrder.id == original.id)).mappings().one())
                if (bound['customer_id'] != account['customer_id'] or any(bound[name] != plan.original[name]
                        for name in plan.original if name not in {'customer_id','updated_at'})):
                    fail('Anonymous Restaurant binding changed another native source')
                plan.bound = bound
                save_command(db, actor, scope, 'tab.assign_anonymous', ident, binding,
                    {'id': order.id, 'sales_order_id': original.id, 'previous_customer_id': None, 'customer_id': selected.id,
                     'previous_revision': data.expected_revision, 'revision': order.revision,
                     'original_source_sha256': order.source_sha256, 'account_id': account['id']}, order=order)
                plan.stage = 'bill'
                issued = bill(ident, TabBill(request_key=key(data.request_key, 'bill'), expected_revision=order.revision,
                    pos_session_id=data.pos_session_id, expected_total=data.expected_total), db, actor, commit=False)
                plan.stage = 'pay'
                root = db.get(POSServiceCheckout, issued['checkout']['id'])
                for payment in data.payments:
                    native.append_payment(root.id, AppendPaymentInput(expected_revision=root.revision,
                        pos_session_id=data.pos_session_id, payment=payment), db, actor, commit=False)
                plan.stage = 'final'
                answer = {**result(db, scope, order, root), 'account_id': account['id'], 'plan': data.model_dump(mode='json')}
                save_command(db, actor, scope, 'tab.settle_anonymous', ident, data, answer, order=order)
                _verify_finished(db, plan)
                plan.complete = True
            if commit:
                db.commit()
    return answer
