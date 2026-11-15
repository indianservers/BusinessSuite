"""Read-only affected sale allocations, anchored to the selected recall case."""
from .receipts import fail
from .recalls import selected, _query, detail
from .recall_models import PharmaRecall
from .models import PharmaBatchAllocation
from .fefo import sale_allocations
from app.apps.srm.service_checkout import _source_scope, _validate_group_sources
from app.apps.srm.service_checkout_models import POSServiceCheckout, POSCheckoutLine


def affected_sales(ident, db, actor, *, after=0, limit=30):
    _, _, scope = selected(db, actor, write=False)
    detail(ident, db, actor)
    root = _query(db, PharmaRecall, scope).filter_by(id=ident).one()
    rows = _query(db, PharmaBatchAllocation, scope).filter(
        PharmaBatchAllocation.batch_id == root.batch_id,
        PharmaBatchAllocation.id > after,
    ).order_by(PharmaBatchAllocation.id).limit(limit + 1).all()
    items = []
    for row in rows[:limit]:
        _source_scope(db, scope, scope.company_id, scope.branch_id, PharmaBatchAllocation, row.id)
        if (row.product_id, row.warehouse_id, row.batch_number, row.expiry_date) != (
                root.product_id, root.warehouse_id, root.batch_number, root.expiry_date):
            fail('Affected lot source differs from recall', 409)
        line = db.query(POSCheckoutLine).filter_by(
            organization_id=scope.company_id, branch_id=scope.branch_id,
            scope_context_key=scope.context_id, sales_order_line_id=row.sales_order_line_id,
        ).one_or_none()
        checkout = _query(db, POSServiceCheckout, scope).filter_by(id=line.checkout_id).one_or_none() if line else None
        if checkout is None:
            fail('Affected sale source requires reconciliation', 409)
        _validate_group_sources(checkout, db, scope)
        lines = db.query(POSCheckoutLine).filter_by(checkout_id=checkout.id).all()
        sale_allocations(db, scope, checkout, lines)
        items.append({'allocation_id': row.id, 'batch_id': row.batch_id,
                      'checkout_id': checkout.id, 'checkout_line_id': line.id,
                      'invoice_id': checkout.invoice_id, 'invoice_line_id': line.invoice_line_id,
                      'sales_order_line_id': row.sales_order_line_id,
                      'movement_id': row.movement_id, 'quantity': str(row.quantity)})
    return {'recall_id': root.id, 'batch_id': root.batch_id, 'items': items,
            'has_more': len(rows) > limit, 'next': rows[limit-1].id if len(rows) > limit else None}
