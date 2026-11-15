"""Immutable cash denomination; legacy evidence is read without changing history."""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, inspect, or_
from app.apps.srm.models import SRMPOSSession, SRMPOSCashMovement, SRMSalesOrder
from app.apps.srm.service_checkout_register import group_register_cash

KEY = 'cash_currency'

def valid_currency(value):
    return isinstance(value, str) and len(value) == 3 and value.isascii() and value.isalpha() and value == value.upper()

def evidence(db, session, orders=None):
    from app.apps.srm.cash_movement_intents import require_schema
    require_schema(db)
    # Raw source columns avoid adopting stale ORM/JSON caches after writer wait.
    row = db.connection().execute(select(SRMPOSSession.metadata_json, SRMPOSSession.opening_cash).where(
        SRMPOSSession.id == session.id, SRMPOSSession.organization_id == session.organization_id)).first()
    if row is None:
        raise HTTPException(409, 'Register requires cash reconciliation')
    metadata = row.metadata_json
    malformed = metadata is not None and not isinstance(metadata, dict)
    metadata = metadata if isinstance(metadata, dict) else {}
    bound = metadata.get(KEY)
    malformed = malformed or (KEY in metadata and not valid_currency(bound))
    if orders is None:
        candidates = db.query(SRMSalesOrder).filter(SRMSalesOrder.organization_id == session.organization_id,
            SRMSalesOrder.deleted_at.is_(None)).all()
        orders = [order for order in candidates if (order.metadata_json or {}).get('source') == 'pos'
            and str((order.metadata_json or {}).get('pos_session_id') or '') == str(session.id)]
    grouped = group_register_cash(db, session, orders, include_currency=True)
    amounts = dict(grouped['cash_by_currency'])
    legacy_cash = False
    for order in orders:
        if order.id not in grouped['group_order_ids'] and (order.metadata_json or {}).get('payment_mode') in {'Cash', 'Split'}:
            legacy_cash = legacy_cash or Decimal(order.total_amount or 0) != 0
            if not valid_currency(order.currency):
                malformed = True
            else:
                amounts[order.currency] = amounts.get(order.currency, Decimal(0)) + Decimal(order.total_amount or 0)
    movements = db.connection().execute(select(SRMPOSCashMovement.id).where(
        SRMPOSCashMovement.session_id == session.id).limit(1)).first() is not None
    intent_currencies = set(db.connection().execute(select(SRMPOSCashMovement.request_currency).where(
        SRMPOSCashMovement.session_id == session.id, SRMPOSCashMovement.request_key.is_not(None))).scalars())
    malformed = malformed or any(not valid_currency(code) for code in intent_currencies)
    untyped = not bound and (Decimal(row.opening_cash or 0) != 0 or movements)
    totals_ambiguous = malformed or untyped or (not bound and legacy_cash) or len(amounts) > 1 or bool(grouped['invalid_currency_count'])
    if bound and any(currency != bound for currency in amounts):
        totals_ambiguous = True
    if len(intent_currencies) > 1 or bound and any(code != bound for code in intent_currencies):
        totals_ambiguous = True
    ambiguous = totals_ambiguous or bool(grouped['unattributed_cash_count'])
    currency = bound or (next(iter(amounts)) if len(amounts) == 1 and not ambiguous else None)
    empty = not bound and not ambiguous and Decimal(row.opening_cash or 0) == 0 and not movements and not orders and not amounts and not grouped.get('split_collection_count', 0)
    if empty:
        from app.apps.srm.service_checkout_models import POSCheckoutPayment, POSServiceCheckout
        if inspect(db.connection()).has_table(POSCheckoutPayment.__tablename__):
            payment, root = POSCheckoutPayment.__table__, POSServiceCheckout.__table__
            empty = db.connection().execute(select(payment.c.id).join(root, root.c.id == payment.c.checkout_id).where(
                or_(payment.c.collection_session_id == session.id, root.c.pos_session_id == session.id)).limit(1)).first() is None
    return {'empty_unbound': empty, 'currency': currency, 'bound': bound, 'ambiguous': ambiguous, 'totals_ambiguous': totals_ambiguous,
        'cash_by_currency': amounts, 'grouped': grouped, 'metadata': metadata}

def require_cash_currency(db, session, currency=None):
    state = evidence(db, session)
    if currency is not None and not valid_currency(currency):
        raise HTTPException(409, 'Cash transaction currency is invalid')
    if state['ambiguous'] or (state['currency'] and currency and state['currency'] != currency):
        raise HTTPException(409, 'Register cash currency differs or requires reconciliation; select a matching register')
    resolved = state['currency'] or currency
    if resolved is None:
        raise HTTPException(409, 'Register cash currency is unknown; reconcile before continuing')
    if not state['bound']:
        session.metadata_json = {**state['metadata'], KEY: resolved}
        db.flush()
    return resolved


def require_cash_closing(db, session, counted_cash):
    # Zero has no denomination: an actually empty legacy drawer may close without
    # inventing or persisting a currency. No cash write uses this exception.
    state = evidence(db, session)
    if Decimal(counted_cash) == 0 and state['empty_unbound']:
        return None
    return require_cash_currency(db, session)
