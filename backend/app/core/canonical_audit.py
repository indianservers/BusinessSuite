"""Single-use native Product birth reference for HTTP audit metadata, never access authority."""
from dataclasses import dataclass
from weakref import WeakKeyDictionary,WeakSet
from sqlalchemy import event,inspect,select
from .audit_context import context

_PENDING=WeakKeyDictionary()
_ISSUED=WeakSet()

@dataclass(frozen=True,eq=False)
class _ProductBirth:
    context_identity:int
    product_id:int
    company_id:int
    actor_id:int


def _born(mapper,connection,row):
    plan=_PENDING.pop(row,None)
    if plan is None:return
    db,value,company,actor=plan
    state=inspect(row)
    if state.session is not db or row.organization_id!=company or row.created_by!=actor or row.id is None:
        raise ValueError('Canonical product audit birth differs from its native producer')
    ref=_ProductBirth(id(value),row.id,company,actor)
    _ISSUED.add(ref);value['canonical_product_birth']=ref


def arm_product_birth(db,actor,row):
    from app.apps.srm.models import SRMProduct
    value=context.get()
    if value is None:return lambda:None
    state=inspect(row,raiseerr=False)
    if (type(row) is not SRMProduct or state is None or state.session is not db or not state.pending
            or row.id is not None or row.organization_id!=actor.organization_id or row.created_by!=actor.id
            or value.get('storage_session') is not db or value.get('actor',{}).get('user_id')!=actor.id or row in _PENDING):
        raise ValueError('Canonical product audit requires its actual pending native source')
    if not event.contains(SRMProduct,'after_insert',_born):event.listen(SRMProduct,'after_insert',_born)
    _PENDING[row]=(db,value,row.organization_id,actor.id)
    def cleanup():_PENDING.pop(row,None)
    return cleanup


def take_product_birth(value,db,request,status):
    ref=value.pop('canonical_product_birth',None)
    if type(ref) is not _ProductBirth or ref not in _ISSUED:return None
    _ISSUED.discard(ref)
    if ref.context_identity!=id(value) or request.method!='POST' or request.url.path!='/api/v1/srm/inventory/items' or status!=201:return None
    from app.apps.srm.api.router import create_srm_product
    if getattr(request.scope.get('route'),'endpoint',None) is not create_srm_product:return None
    from app.apps.srm.models import SRMProduct
    t=SRMProduct.__table__
    actual=db.connection().execute(select(t.c.organization_id,t.c.created_by,t.c.deleted_at).where(t.c.id==ref.product_id)).first()
    if actual is None or tuple(actual)!=(ref.company_id,ref.actor_id,None):return None
    return ('canonical:srm_product_created',ref.product_id)
