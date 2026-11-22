"""Private, exact canonical metadata exclusion for native catalog commands.

This certifies one correlated EXISTS occurrence, never a table or a column.
Its Core alias intentionally has no private ORM loader criteria: only the
validated canonical parent relationship can determine this negative filter.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import weakref

from fastapi import HTTPException
from sqlalchemy import and_,exists,or_,select
from sqlalchemy.sql import visitors

_MARKER='_native_catalog_projection'
_REGISTRY=weakref.WeakKeyDictionary()


@dataclass(frozen=True)
class _Projection:
    scope:object
    actor:object
    source:str
    kinds:tuple
    purpose:str="catalog"


@contextmanager
def _projection(db,actor,scope,source,kinds):
    from .catalog_management import authority
    if db.info.get(_MARKER) is not None or not kinds:
        raise HTTPException(403,'Catalog projection purpose cannot be nested or inferred')
    for kind in kinds:
        verified,_=authority(db,actor,source,kind)
        if verified is not scope:
            raise HTTPException(403,'Catalog projection requires its exact verified context')
    proof=_Projection(scope,actor,source,tuple(kinds))
    db.info[_MARKER]=proof
    try:yield
    finally:
        if db.info.get(_MARKER) is proof:db.info.pop(_MARKER,None)


@contextmanager
def _pos_projection(db,actor,scope):
    from app.apps.srm.pos_surface import authority
    company,branch,verified=authority(db,actor,str(scope.context_id))
    if verified!=scope or db.info.get('business_pack_scope')!=scope or db.info.get(_MARKER) is not None:
        raise HTTPException(403,'A verified native POS projection is required')
    scope=db.info['business_pack_scope']
    proof=_Projection(scope,actor,'srm',('product','service'),'pos')
    db.info[_MARKER]=proof
    try:yield
    finally:
        if db.info.get(_MARKER) is proof:db.info.pop(_MARKER,None)


def _pos_workspace_predicate(db,scope):
    proof=db.info.get(_MARKER)
    if not isinstance(proof,_Projection) or proof.purpose!='pos':
        raise HTTPException(503,'This selected product workflow is not integrated')
    return _workspace_predicate(db,scope)


def _assert_pos_product(db,actor,scope,product):
    """Existence bit only, after canonical available native parent validation."""
    from sqlalchemy import inspect
    from app.apps.srm.models import SRMProduct
    from app.apps.srm.service_checkout import _source_scope
    from app.shared.catalog_branches import assert_available
    if type(product) is not SRMProduct or inspect(product).session is not db or product.organization_id!=scope.company_id:
        raise HTTPException(403,'A verified native POS product is required')
    _source_scope(db,scope,scope.company_id,scope.branch_id,SRMProduct,product.id,master=True)
    assert_available(product,actor)
    with _pos_projection(db,actor,scope):
        node=_workspace_predicate(db,scope)
        if db.connection().scalar(select(node).select_from(SRMProduct.__table__).where(SRMProduct.id==product.id,SRMProduct.organization_id==scope.company_id)):
            raise HTTPException(503,'Workspace offerings are not integrated in selected POS')


def _fingerprint(node,dialect):
    compiled=node.compile(dialect=dialect)
    return (str(compiled),tuple(sorted((key,type(value).__name__,repr(value)) for key,value in compiled.params.items())),
        tuple((id(child),type(child),tuple(id(value) for value in (getattr(child,'_correlate',()) or ())),
            tuple(id(value) for value in (getattr(child,'_correlate_except',()) or ())),getattr(child,'_auto_correlate',None))
            for child in visitors.iterate(node)))


def _workspace_predicate(db,scope):
    from app.apps.srm.models import SRMProduct
    from app.shared.catalog_models import CatalogDetails
    from .operations import capabilities, can_view_booking_service
    proof=db.info.get(_MARKER)
    if isinstance(proof,_Projection) and proof.purpose=='pos' and proof.scope==scope:
        scope=proof.scope
    if not isinstance(proof,_Projection) or proof.scope is not scope or db.info.get('business_pack_scope') is not scope:
        raise HTTPException(403,'A verified native catalog projection is required')
    if proof.purpose == 'catalog':
        allowed = capabilities(db, proof.actor) or ()
        if 'catalog.view' not in allowed and not (
            proof.kinds == ('service',) and can_view_booking_service(scope, allowed, proof.source, 'service')
        ):
            raise HTTPException(403, 'Native catalog view capability is required')
    detail=CatalogDetails.__table__.alias('native_catalog_private_workspace')
    parent=SRMProduct.__table__
    node=exists(select(detail.c.id).where(detail.c.organization_id==scope.company_id,
        parent.c.organization_id==scope.company_id,detail.c.workspace_id.is_not(None),or_(
            and_(parent.c.product_type=='service',detail.c.service_id==parent.c.id,detail.c.product_id.is_(None)),
            and_(or_(parent.c.product_type.is_(None),parent.c.product_type!='service'),
                detail.c.product_id==parent.c.id,detail.c.service_id.is_(None))))).correlate(parent)
    _REGISTRY[node]=(weakref.ref(db),weakref.ref(proof),scope,_fingerprint(node,db.get_bind().dialect))
    return node


def _verified_workspace_predicate(db,scope,node):
    entry=_REGISTRY.get(node)
    if entry is None:return False
    session,proof_ref,actual,fingerprint=entry
    proof=proof_ref()
    return (proof is not None and session() is db and actual is scope and db.info.get('business_pack_scope') is scope
        and db.info.get(_MARKER) is proof and proof.scope is scope
        and _fingerprint(node,db.get_bind().dialect)==fingerprint)
