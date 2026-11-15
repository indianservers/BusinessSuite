"""Fresh native ceilings for the exact common selected-pack checkout purpose.

No native grant is created here. Legacy operations never enter this helper.
The returned fingerprint is local to one authority call, across its first
company-writer wait; it is never a Session flag or a reusable permission lease.
"""
from fastapi import HTTPException
from .access import PackScope


def capture(db,actor,scope,*,order,billing,payments,write):
    if not isinstance(scope,PackScope) or db.info.get('business_pack_scope')!=scope or scope.user_id!=actor.id:
        raise HTTPException(403,'A verified selected native checkout scope is required')
    from .common_core import _native_authority
    from .catalog_management import _module_grant
    fingerprint=_native_authority(db,actor,scope.company_id)
    grant=_module_grant(db,actor,scope,'srm')
    if not actor.is_superuser:
        actions={'create' if write else 'view'}|({'approve'} if billing else set())
        names=set(grant.get('permissions',()))
        alternatives=[]
        if order:alternatives.append({'srm_manage','srm_admin'})
        if billing:alternatives.extend(({'srm_invoice_create','srm_admin'},{'srm_invoice_approve','srm_admin'}))
        if payments:alternatives.append({'srm_collection_create','srm_admin'})
        if not grant.get('enabled') or not actions<=set(grant.get('actions',())) or any(not names.intersection(required) for required in alternatives):
            raise HTTPException(403,'Fresh native checkout permissions and actions are required')
    return fingerprint
