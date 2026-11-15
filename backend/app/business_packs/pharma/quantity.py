"""Three decimal quantities belong only to the selected native Pharma lot path."""
from decimal import Decimal, DecimalException
from .receipts import fail


def validate(db, product_id, value, *, maximum=Decimal('1000000000')):
    try:
        quantity = Decimal(str(value))
    except (DecimalException, ValueError, TypeError):
        fail('Invalid sale quantity', 422)
    if not quantity.is_finite() or quantity <= 0 or quantity > maximum:
        fail('Sale quantity must be positive, finite and within native capacity', 422)
    if quantity != quantity.quantize(Decimal('.001')):
        fail('Sale quantities support at most three decimal places', 422)
    if quantity == quantity.quantize(Decimal('.01')):
        return
    scope = db.info.get('business_pack_scope')
    if scope is None or scope.pack_key != 'pharma':
        fail('Three-decimal sale quantities require the authorized Pharma lot workflow', 422)
    from app.business_packs.native_policy import native_srm_policy
    if db.info.get('business_pack_policy') != native_srm_policy('pharma').policy:
        fail('Audited Pharma isolation adapter is not installed', 503)
    from app.apps.srm.models import SRMProduct
    from app.apps.srm.service_checkout import _source_scope
    from .fefo import supported
    product = db.get(SRMProduct, product_id) if product_id else None
    if product is None or product.organization_id != scope.company_id or not supported(scope, product):
        fail('Three-decimal quantities require a batch-and-expiry tracked medicine', 422)
    _source_scope(db, scope, scope.company_id, scope.branch_id, SRMProduct, product_id, master=True)
