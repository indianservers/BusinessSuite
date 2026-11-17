"""Per-policy resource rules stored on the existing service catalog metadata.

Policy IDs are globally unique and already carry branch/pack authority. This
keeps rules isolated without changing the installed checkout table schema.
"""
from fastapi import HTTPException

RESOURCE_TYPES = {'room', 'chair', 'equipment', 'location'}


def required_types(product, policy_id):
    settings = (product.metadata_json or {}).get('service_resource_requirements', {})
    values = settings.get(str(policy_id), []) if isinstance(settings, dict) else None
    if not isinstance(values, list) or any(type(value) is not str or value not in RESOURCE_TYPES for value in values):
        raise HTTPException(409, 'Service resource requirements need review in scheduling settings')
    return set(values)


def assert_required_resources(product, policy_id, resources):
    missing = required_types(product, policy_id) - {row.data.get('resource_type') for row in resources}
    if missing:
        raise HTTPException(422, 'Required service resources missing: ' + ', '.join(sorted(missing)))


def assert_current_service_requirements(db, actor, branch, product, resource_ids):
    """Cover legacy/manual/public reservations and moves as well as POS selections."""
    if not (product.metadata_json or {}).get('service_resource_requirements'):
        return
    from sqlalchemy import inspect
    from app.apps.srm.service_checkout_models import ServiceBookingPolicy
    from app.apps.srm.service_checkout import _scope, _source_scope
    from app.apps.srm.services.commercial import tenant
    from app.apps.srm.industry_api import get
    if not inspect(db.connection()).has_table(ServiceBookingPolicy.__tablename__):
        raise HTTPException(503, 'Service scheduling installation is incomplete')
    scope = db.info.get('business_pack_scope')
    policy = _scope(db.query(ServiceBookingPolicy), ServiceBookingPolicy, tenant(actor), branch, scope).filter_by(service_product_id=product.id).first()
    if policy is None:
        return
    _source_scope(db,scope,tenant(actor),branch,ServiceBookingPolicy,policy.id)
    if not policy.active:
        raise HTTPException(409, 'Service scheduling policy is inactive')
    assert_required_resources(product,policy.id,[get(db,actor,branch,identity,'resource',lock=False) for identity in resource_ids])
