"""Read only the immutable lot allocations of one authorized original checkout.

This is source discovery, not return authorization or remaining-quantity state.
The posting command must lock and subtract committed returns separately.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.apps.srm.service_checkout_models import POSServiceCheckout, POSCheckoutLine
from app.apps.srm.service_checkout import _scope, _validate_group_sources, _source_scope
from .models import PharmaBatchAllocation
from .fefo import sale_allocations, MAX_ALLOCATIONS
from .receipts import authority, fail


@dataclass(frozen=True)
class OriginalReturnLot:
    checkout_line_id: int
    allocation_id: int
    batch_id: int
    product_id: int
    warehouse_id: int
    batch_number: str
    expiry_date: date
    sold_quantity: Decimal


def original_lots(db, actor, checkout_id: int) -> tuple[OriginalReturnLot, ...]:
    company, branch, scope = authority(db, actor, 'returns.approve', write=False)
    checkout = _scope(db.query(POSServiceCheckout), POSServiceCheckout, company, branch, scope).filter_by(id=checkout_id).one_or_none()
    if checkout is None:
        fail('Original Pharma checkout not found', 404)
    _validate_group_sources(checkout, db, scope)
    lines = db.query(POSCheckoutLine).filter_by(checkout_id=checkout.id).order_by(POSCheckoutLine.id).all()
    # Reuse the actual invoice/order source and complete immutable-lot checks.
    sale_allocations(db, scope, checkout, lines)
    by_source = {line.sales_order_line_id: line for line in lines if line.line_kind == 'product'}
    if not by_source:
        fail('Original sale has no physical medicine lots', 409)
    rows = db.query(PharmaBatchAllocation).filter(
        PharmaBatchAllocation.organization_id == company,
        PharmaBatchAllocation.branch_id == branch,
        PharmaBatchAllocation.pack_context_id == scope.context_id,
        PharmaBatchAllocation.sales_order_line_id.in_(by_source),
    ).order_by(PharmaBatchAllocation.id).limit(MAX_ALLOCATIONS + 1).all()
    if not rows or len(rows) > MAX_ALLOCATIONS:
        fail('Original medicine lot source requires reconciliation', 409)
    result = []
    for row in rows:
        _source_scope(db, scope, company, branch, PharmaBatchAllocation, row.id)
        line = by_source[row.sales_order_line_id]
        result.append(OriginalReturnLot(line.id, row.id, row.batch_id,
                                       row.product_id, row.warehouse_id, row.batch_number,
                                       row.expiry_date, Decimal(row.quantity)))
    return tuple(result)
