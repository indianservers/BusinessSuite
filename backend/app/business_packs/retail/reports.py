"""Read-only Retail projections of native transactions, with currency separation."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from decimal import Decimal
from sqlalchemy import select, exists, cast, String, or_
from app.apps.srm.models import SRMProduct, SRMInventoryMovement, SRMPOSSession, SRMWarehouse, SRMInventoryBalance
from app.apps.srm.service_checkout_models import POSServiceCheckout
from app.apps.srm.service_checkout import checkout_result
from .stock_receipts import authority


def _business_day(stamp, zone):
    # SQLite returns naive native UTC timestamps; PostgreSQL keeps the offset.
    return (stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp).astimezone(zone).date()


def stock(db, actor, *, after=0, limit=100):
    company, branch, scope = authority(db, actor, 'stock.view')
    from app.shared.catalog_branches import availability_clause
    products = db.query(SRMProduct).filter(SRMProduct.organization_id == company, SRMProduct.id > after,
        SRMProduct.active.is_(True), SRMProduct.deleted_at.is_(None), SRMProduct.track_inventory.is_(True),
        or_(SRMProduct.product_type.is_(None), SRMProduct.product_type.notin_(['service', 'services'])), availability_clause(SRMProduct, branch)).order_by(SRMProduct.id).limit(limit + 1).all()
    from app.business_packs.pharma.reads import workspace_bound
    from app.branches.models import BranchOwnership
    from app.business_packs.models import PackRecordOwnership
    warehouses = db.query(SRMWarehouse).filter_by(organization_id=company, active=True).all()
    native = BranchOwnership.__table__
    eligible = [row.id for row in warehouses if db.connection().scalar(select(native.c.resource_key).where(
        native.c.company_id == company, native.c.branch_id == branch,
        native.c.resource_table == SRMWarehouse.__tablename__, native.c.resource_key == str(row.id)))]
    balance, private = SRMInventoryBalance.__table__, PackRecordOwnership.__table__
    items = []
    for product in products[:limit]:
        if db.connection().scalar(select(workspace_bound(db, company, product.id))):
            continue
        balances = db.connection().execute(select(balance.c.warehouse_id, balance.c.quantity).where(
            balance.c.organization_id == company, balance.c.product_id == product.id,
            balance.c.warehouse_id.in_(eligible), ~exists(select(private.c.id).where(
                private.c.resource_table == balance.name, private.c.resource_key == cast(balance.c.id, String))))).all()
        quantities = {row.warehouse_id: Decimal(row.quantity or 0) for row in balances}
        locations = [{'warehouse_id': ident, 'available_quantity': str(quantities.get(ident, Decimal(0)))} for ident in sorted(eligible)]
        available = next((row for row in locations if row['warehouse_id'] == product.default_warehouse_id), None)
        items.append({'product_id': product.id, 'sku': product.sku, 'name': product.item_name,
                      'currency': (product.metadata_json or {}).get('currency', 'INR'), 'stock': available, 'warehouses': locations, 'branch_quantity': str(sum(quantities.values(), Decimal(0))), 'tracked': bool(product.batch_tracking or product.expiry_tracking or product.serial_tracking)})
    from app.apps.srm.services.commercial import require
    from app.access.service import check_background_access
    from fastapi import HTTPException
    can_receive = scope.writable and 'retail.stock.receive' in scope.capabilities
    if can_receive:
        try:
            require(actor, 'srm_manage', 'srm_admin')
            check_background_access(db, actor, 'srm', 'create', stamp=False)
        except HTTPException:
            can_receive = False
    return {'items': items, 'can_receive': can_receive, 'receipt_date': date.today().isoformat(),
            'warehouses': [{'id': row.id, 'warehouse_name': row.warehouse_name} for row in warehouses if row.id in eligible], 'next_after': products[limit - 1].id if len(products) > limit else None,
            'basis': 'Canonical balances in explicitly eligible native branch warehouses; stock selects the product default warehouse'}


def daily(db, actor, day: date | None):
    company, branch, scope = authority(db, actor, 'reports.view')
    from app.models.company import Company
    from fastapi import HTTPException
    name = db.connection().scalar(select(Company.default_timezone).where(Company.id == company))
    try:
        zone = ZoneInfo(name or 'Asia/Kolkata')
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(409, 'Configure a valid company timezone before viewing daily reports')
    day = day or datetime.now(zone).date()
    from app.apps.srm.services.commercial import invoice_query, require
    require(actor, 'srm_invoice_view', 'srm_invoice_create', 'srm_collection_view', 'srm_collection_create', 'srm_admin')
    visible_invoices = {row.id for row in invoice_query(db, actor).all()}
    roots = db.query(POSServiceCheckout).filter_by(organization_id=company, branch_id=branch,
        pack_context_id=scope.context_id, state='committed').all()
    sales = {}
    collections = {}
    register_cash = {}
    drawer_currencies = {}
    for root in roots:
        if root.invoice_id not in visible_invoices:
            continue
        # Validate the complete native invoice/receipt graph before aggregating it.
        result = checkout_result(root, db, scope=scope)
        if _business_day(root.committed_at, zone) == day:
            bucket = sales.setdefault(root.currency, {'count': 0, 'gross': Decimal(0), 'tax': Decimal(0)})
            bucket['count'] += 1
            bucket['gross'] += sum((Decimal(line['total']) for line in result['lines']), Decimal(0))
            bucket['tax'] += sum((Decimal(line['tax']) for line in result['lines']), Decimal(0))
        from app.apps.srm.models import SRMReceipt
        for receipt in result['receipts']:
            source = db.get(SRMReceipt, receipt['id'])
            if source.payment_method == 'cash':
                from app.apps.srm.service_checkout_models import POSCheckoutPayment
                payment = db.query(POSCheckoutPayment).filter_by(checkout_id=root.id, receipt_id=source.id).one()
                drawer_currencies.setdefault(payment.collection_session_id, set()).add(source.currency)
            if source.receipt_date == day:
                key = (source.currency, source.payment_method)
                collections[key] = collections.get(key, Decimal(0)) + Decimal(source.amount)
                if source.payment_method == 'cash':
                    drawer_key = (payment.collection_session_id, source.currency)
                    register_cash[drawer_key] = register_cash.get(drawer_key, Decimal(0)) + Decimal(source.amount)
    from app.apps.srm.api.router import _pos_session_summary
    sessions = db.query(SRMPOSSession).filter_by(organization_id=company, deleted_at=None).all()
    registers = []
    for row in sessions:
        if _business_day(row.opened_at, zone) > day or row.closed_at is not None and _business_day(row.closed_at, zone) < day:
            continue
        lifetime = _pos_session_summary(db, row)
        cash_in = sum((Decimal(m.amount) for m in row.cash_movements if _business_day(m.created_at, zone) == day and m.movement_type == 'cash_in'), Decimal(0))
        cash_out = sum((Decimal(m.amount) for m in row.cash_movements if _business_day(m.created_at, zone) == day and m.movement_type == 'cash_out'), Decimal(0))
        currencies = {currency: amount for (session_id, currency), amount in register_cash.items() if session_id == row.id}
        mixed = len(drawer_currencies.get(row.id, set())) > 1
        cash = sum(currencies.values(), Decimal(0))
        if mixed:
            lifetime = {**lifetime, 'cash_sales': None, 'expected_cash': None, 'reconciliation_required': True}
        amounts = [{'currency': currency, 'amount': str(amount)} for currency, amount in sorted(currencies.items())]
        registers.append({'session_id': row.id, 'status': row.status, 'cash_collected': None if mixed else str(cash), 'cash_collected_by_currency': amounts,
                          'currency_reconciliation_required': mixed,
                          'cash_in': str(cash_in), 'cash_out': str(cash_out), 'net_cash_change': None if mixed else str(cash + cash_in - cash_out),
                          'lifetime_reconciliation': lifetime})
    from .models import RetailReturn
    refunds = {}
    for returned in db.query(RetailReturn).filter_by(organization_id=company, branch_id=branch,
            pack_context_id=scope.context_id, state='committed').all():
        if returned.invoice_id in visible_invoices and _business_day(returned.committed_at, zone) == day:
            refunds[returned.currency] = refunds.get(returned.currency, Decimal(0)) + Decimal(returned.refund_amount)
    movements = db.query(SRMInventoryMovement).filter_by(organization_id=company, movement_date=day).all()
    return {'day': day.isoformat(), 'timezone': zone.key, 'date_basis': 'Native receipt and stock dates; company timezone for checkout, cash movement and register timestamps',
            'sales': [{'currency': currency, 'count': values['count'], 'gross': str(values['gross']), 'tax': str(values['tax'])}
                      for currency, values in sorted(sales.items())],
            'collections': [{'currency': currency, 'method': method, 'amount': str(amount)}
                            for (currency, method), amount in sorted(collections.items())],
            'refunds': [{'currency': currency, 'amount': str(amount)} for currency, amount in sorted(refunds.items())],
            'stock_movements': [{'id': row.id, 'product_id': row.product_id, 'warehouse_id': row.warehouse_id,
                                'quantity_in': str(row.quantity_in), 'quantity_out': str(row.quantity_out)} for row in movements],
            'registers': registers}
