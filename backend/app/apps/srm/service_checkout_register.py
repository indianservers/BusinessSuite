"""Receipt-derived checkout cash only; no order-total/payment-mode inference."""
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import inspect, or_, select

from app.apps.srm.service_checkout_models import MODELS, POSCheckoutPayment, POSServiceCheckout
from app.apps.srm.models import SRMPOSSession, SRMReceipt, SRMSalesOrder
from app.branches.models import BranchOwnership
from app.models.company import Branch
from app.business_packs.models import PackRecordOwnership


def _fail():
    raise HTTPException(503, 'Register collection provenance requires reconciliation')


def group_register_cash(db, session, authorized_orders):
    """Caller supplies a natively authorized register/orders; return no buyer data.

    NULL historical cash collection references warn only on the root register.
    They never contribute an inferred cash amount to any register.
    """
    result = {'group_order_ids': set(), 'cash_received': Decimal('0'), 'unattributed_cash_count': 0}
    connection = db.connection()
    inspector = inspect(connection)
    present = [model for model in MODELS if inspector.has_table(model.__tablename__)]
    if not present:
        return result
    complete = len(present) == len(MODELS) and all(set(model.__table__.c.keys()) <=
        {column['name'] for column in inspector.get_columns(model.__tablename__)} for model in present)
    if not complete:
        # Never let actual checkout sources fall back to legacy order totals.
        for model in present:
            if connection.exec_driver_sql('SELECT 1 FROM ' + model.__tablename__ + ' LIMIT 1').first():
                _fail()
        return result
    order_ids = {order.id for order in authorized_orders}
    root, payment, receipt = POSServiceCheckout.__table__, POSCheckoutPayment.__table__, SRMReceipt.__table__
    current = session.id
    candidates = select(payment.c.checkout_id).where(payment.c.collection_session_id == current)
    relevant = or_(root.c.pos_session_id == current, root.c.sales_order_id.in_(order_ids), root.c.id.in_(candidates))
    if not connection.execute(select(root.c.id).where(relevant).limit(1)).first():
        return result  # Unrelated native legacy registers retain their behavior.
    if not inspector.has_table(BranchOwnership.__tablename__) or not inspector.has_table(PackRecordOwnership.__tablename__):
        _fail()
    company = session.organization_id
    if type(company) is not int or company <= 0 or type(current) is not int or current <= 0:
        _fail()
    scope = db.info.get('business_pack_scope')
    if scope is not None:
        from app.business_packs.boundary import _current
        _current(scope, connection)
    branch_table = BranchOwnership.__table__
    first = connection.execute(select(branch_table.c.company_id, branch_table.c.branch_id).where(
        branch_table.c.resource_table == SRMPOSSession.__tablename__, branch_table.c.resource_key == str(current))).first()
    if first is None or first.company_id != company:
        _fail()
    branch = first.branch_id
    if scope is not None and (scope.company_id, scope.branch_id) != (company, branch):
        _fail()
    if not connection.execute(select(Branch.id).where(Branch.id == branch, Branch.company_id == company)).first():
        _fail()
    checked = set()

    def proof(model, identity):
        key = (model.__tablename__, identity)
        if key in checked:
            return
        native = connection.execute(select(branch_table.c.company_id, branch_table.c.branch_id).where(
            branch_table.c.resource_table == key[0], branch_table.c.resource_key == str(identity))).first()
        if native is None or (native.company_id, native.branch_id) != (company, branch):
            _fail()
        owner = PackRecordOwnership.__table__
        anchor = connection.execute(select(owner.c.company_id, owner.c.branch_id, owner.c.context_id).where(
            owner.c.resource_table == key[0], owner.c.resource_key == str(identity))).first()
        if scope is None:
            if anchor is not None:
                _fail()
        elif anchor is None or tuple(anchor) != (company, branch, scope.context_id):
            _fail()
        checked.add(key)

    proof(SRMPOSSession, current)
    actual = connection.execute(select(SRMPOSSession.organization_id).where(SRMPOSSession.id == current)).scalar_one_or_none()
    if actual != company:
        _fail()
    session_companies = {current: company}
    roots = connection.execute(select(root.c.id, root.c.organization_id, root.c.branch_id, root.c.pack_context_id,
        root.c.pos_session_id, root.c.sales_order_id, root.c.customer_id, root.c.currency).where(relevant)).mappings().all()
    seen_receipts = set()
    for source in roots:
        if (source['organization_id'], source['branch_id'], source['pack_context_id']) != (company, branch, scope.context_id if scope else None):
            _fail()
        proof(POSServiceCheckout, source['id'])
        proof(SRMPOSSession, source['pos_session_id'])
        if source['pos_session_id'] not in session_companies:
            session_companies[source['pos_session_id']] = connection.execute(select(SRMPOSSession.organization_id).where(SRMPOSSession.id == source['pos_session_id'])).scalar_one_or_none()
        original_company = session_companies[source['pos_session_id']]
        if original_company != company:
            _fail()
        if source['sales_order_id'] is not None:
            proof(SRMSalesOrder, source['sales_order_id'])
            order = connection.execute(select(SRMSalesOrder.organization_id, SRMSalesOrder.customer_id, SRMSalesOrder.currency).where(SRMSalesOrder.id == source['sales_order_id'])).first()
            if order is None or tuple(order) != (company, source['customer_id'], source['currency']):
                _fail()
            if source['sales_order_id'] in order_ids:
                result['group_order_ids'].add(source['sales_order_id'])
        payments = connection.execute(select(payment.c.id, payment.c.receipt_id, payment.c.organization_id,
            payment.c.branch_id, payment.c.scope_context_key, payment.c.collection_session_id).where(
                payment.c.checkout_id == source['id'], or_(payment.c.collection_session_id == current,
                    payment.c.collection_session_id.is_(None)))).mappings().all()
        for mapped in payments:
            if (mapped['organization_id'], mapped['branch_id'], mapped['scope_context_key']) != (company, branch, scope.context_id if scope else 0):
                _fail()
            proof(POSCheckoutPayment, mapped['id'])
            proof(SRMReceipt, mapped['receipt_id'])
            if mapped['receipt_id'] in seen_receipts:
                _fail()
            seen_receipts.add(mapped['receipt_id'])
            cash = connection.execute(select(receipt.c.organization_id, receipt.c.customer_id, receipt.c.currency,
                receipt.c.status, receipt.c.payment_method, receipt.c.amount).where(receipt.c.id == mapped['receipt_id'])).mappings().first()
            if cash is None or (cash['organization_id'], cash['customer_id'], cash['currency']) != (company, source['customer_id'], source['currency']):
                _fail()
            if (cash['payment_method'] or '').strip().lower() != 'cash' or cash['status'] not in ('confirmed', 'partially_allocated', 'allocated'):
                continue
            try:
                amount = Decimal(str(cash['amount']))
            except (InvalidOperation, ValueError, TypeError):
                _fail()
            if not amount.is_finite() or amount <= 0:
                _fail()
            if mapped['collection_session_id'] is None:
                if source['pos_session_id'] == current:
                    result['unattributed_cash_count'] += 1
            else:
                result['cash_received'] += amount
    return result
