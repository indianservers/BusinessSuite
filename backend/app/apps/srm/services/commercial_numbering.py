"""Closed native company number reservation; no operational records are exposed."""
from dataclasses import dataclass
from types import MappingProxyType
from fastapi import HTTPException
from sqlalchemy import select,func,inspect
from app.apps.srm import models as native
from app.apps.srm.commercial_models import CommercialNumberSequence

@dataclass(frozen=True)
class Series:
    model:type
    column:str
    prefix:str
    extra_number_columns:tuple[str,...]=()

_ITEMS=(
    Series(native.SRMSalesOrder,'order_number','SO'),
    Series(native.SRMEngagement,'engagement_number','ENG'),
    Series(native.SRMContract,'contract_number','CTR'),
    Series(native.SRMInventoryMovement,'movement_number','INV'),
    # Transfer references are stored on paired INV movements, not movement_number.
    Series(native.SRMInventoryMovement,'movement_number','TRF',('reference_number',)),
    Series(native.SRMBillOfMaterial,'bom_number','BOM'),
    Series(native.SRMProductionOrder,'production_number','MFG'),
    Series(native.SRMPurchaseOrder,'po_number','PO'),
    Series(native.SRMGoodsReceipt,'grn_number','GRN'),
    Series(native.SRMPriceList,'price_list_code','PL'),
    Series(native.SRMPOSSession,'session_number','POS'),
    Series(native.SRMPOSHeldBill,'hold_number','HOLD'),
    Series(native.SRMPOSReturn,'return_number','RET'),
    Series(native.SRMReceipt,'receipt_number','RCT'),
)
SERIES=MappingProxyType({(item.model,item.column,item.prefix):item for item in _ITEMS})
_LIMIT=2**63-1


def fail(message,code=403):raise HTTPException(code,message)


def _authority(db,actor,company):
    from app.models.user import User
    from app.models.company import Company
    from app.core.tenant_boundary import company_ids
    from app.apps.srm.services.commercial import tenant
    from app.access.models import AccessPolicy
    if not actor or type(getattr(actor,'id',None)) is not int or tenant(actor)!=company or db.info.get('security_write_request') is False:
        fail('Number reservation requires a verified native writer')
    for bound in (db.info.get('security_boundary'),getattr(db.info.get('branch_context'),'company_id',None)):
        if bound is not None and bound!=company:fail('Number reservation company differs from native authorization')
    shared=db.info.get('shared_actor')
    if shared is not None and shared!=(actor.id,company):fail('Number reservation actor differs from native authorization')
    connection=db.connection()
    current=connection.execute(select(User.is_active,User.is_superuser,User.role_id).where(User.id==actor.id)).first()
    if not current or not current.is_active or current.role_id!=actor.role_id:fail('Native actor authority changed')
    if not connection.scalar(select(Company.id).where(Company.id==company,Company.is_active.is_(True))):fail('Native company is unavailable')
    if not current.is_superuser and company not in company_ids(db,actor):fail('Native company membership was revoked')
    policy=AccessPolicy.__table__
    if inspect(connection).has_table(policy.name):
        row=connection.execute(select(policy.c.status,policy.c.version).where(policy.c.company_id==company,policy.c.user_id==actor.id)).first()
        if not current.is_superuser and row and row.status!='active':fail('Native company access policy was revoked')
        version=getattr(actor,'_suite_policy_version',None)
        if version is not None and (not row or row.version!=version):fail('Native company access policy changed')
    scope=db.info.get('business_pack_scope')
    if scope is not None:
        from app.business_packs.operations import capabilities
        capabilities(db,actor)
    branch=db.info.get('branch_context')
    if branch is not None:
        from app.branches.service import context
        fresh=context(db,actor,company,branch.branch_id or 'all')
        if fresh!=branch:fail('Native branch authorization changed')
        if scope is not None or 'business_pack_request_binding' in db.info:
            from app.business_packs.access import resolve_context
            resolve_context(db,actor,fresh,requested_context_id=getattr(scope,'context_id',None))


def _suffix(value,prefix):
    if not isinstance(value,str) or not value.startswith(prefix+'-'):return 0
    suffix=value.rsplit('-',1)[-1]
    return int(suffix) if suffix.isascii() and suffix.isdigit() else 0


def reserve_number(db,model,prefix,column_name,org_id,*,actor):
    """Reserve inside caller transaction; does not grant any native create right.

    All authority and source values are server-owned. The fixed projection reads
    number columns only, including private/legacy rows invisible to this actor.
    Native callers still own their existing permission/action checks; a CRM won
    handoff is not promoted to a generic SRM administrator by this service.
    """
    spec=SERIES.get((model,column_name,prefix))
    if spec is None:fail('Unsupported native numbering series',422)
    company=1 if org_id is None else org_id
    if type(company) is not int or not 0<company<=2147483647:fail('A verified native company is required')
    _authority(db,actor,company)
    from app.core.company_writer import lock_company_writer
    lock_company_writer(db,company)
    _authority(db,actor,company)
    connection=db.connection();counter=CommercialNumberSequence.__table__
    if not inspect(connection).has_table(counter.name):fail('Native number sequence installation is incomplete',503)
    key=f'srm_company:{company}:{spec.model.__tablename__}:{prefix}'
    if len(key)>80:fail('Unsupported native number series identity',422)
    previous=connection.scalar(select(counter.c.last_number).where(counter.c.series==key).with_for_update())
    last=previous or 0
    table=spec.model.__table__
    names=(spec.column,*spec.extra_number_columns)
    # Reconcile each time: old imports and manual numbers may be added after
    # bootstrap. Bounded result batches never expose record IDs, names or money.
    rows=connection.execute(select(*(table.c[name] for name in names)).where(func.coalesce(table.c.organization_id,1)==company)).yield_per(500)
    for row in rows:
        for value in row:last=max(last,_suffix(value,spec.prefix))
    for pending in db.new:
        if isinstance(pending,spec.model) and (getattr(pending,'organization_id',None) or 1)==company:
            for name in names:last=max(last,_suffix(getattr(pending,name,None),spec.prefix))
    if last>=_LIMIT:fail('Native numbering series is exhausted',409)
    following=last+1
    if previous is None:connection.execute(counter.insert().values(series=key,last_number=following))
    else:connection.execute(counter.update().where(counter.c.series==key).values(last_number=following))
    return f'{spec.prefix}-{following:06d}'
