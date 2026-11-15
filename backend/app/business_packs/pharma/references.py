"""Finite command certificate for a canonical lot FK, never a batch read grant."""
from contextlib import contextmanager
from weakref import WeakKeyDictionary
from sqlalchemy import inspect,select
from app.apps.srm.models import SRMInventoryBatch
from .models import PharmaBatchReceipt,PharmaBatchAllocation

_plans=WeakKeyDictionary()


def _snapshot(row):
    return (row.organization_id,row.branch_id,row.pack_context_id,row.batch_id,row.product_id,row.warehouse_id,
        row.batch_number,row.expiry_date,tuple((column.key,getattr(row,column.key)) for column in row.__table__.columns
            if column.key not in ({'id','created_at','movement_id'} if type(row) is PharmaBatchReceipt else {'id','created_at'})))


@contextmanager
def creation_plan(db,scope,row):
    if type(row) not in (PharmaBatchReceipt,PharmaBatchAllocation) or not inspect(row).transient:
        raise ValueError('Pharma lot certificate requires its newly constructed native command row')
    if _snapshot(row)[:3]!=(scope.company_id,scope.branch_id,scope.context_id):raise ValueError('Pharma lot certificate scope differs')
    plans=_plans.setdefault(db,{})
    if id(row) in plans:raise ValueError('Pharma lot certificate already exists')
    plans[id(row)]=(scope,row,_snapshot(row))
    try:yield
    finally:
        plans.pop(id(row),None)
        if not plans:_plans.pop(db,None)


def reference(db,scope,row,parent,pairs):
    from .return_stock import reference as return_reference
    if return_reference(db,scope,row,parent,pairs):return True
    if parent is not SRMInventoryBatch.__table__ or tuple((name,key.name) for name,key in pairs)!=(('batch_id','id'),):return False
    plan=_plans.get(db,{}).get(id(row))
    if plan is None or plan[0] is not scope or plan[1] is not row or plan[2]!=_snapshot(row):return False
    state=inspect(row)
    if type(row) not in (PharmaBatchReceipt,PharmaBatchAllocation) or state.session is not db or row in db.deleted:return False
    t=SRMInventoryBatch.__table__
    actual=db.connection().execute(select(t.c.organization_id,t.c.product_id,t.c.warehouse_id,t.c.batch_number,t.c.expiry_date).where(t.c.id==row.batch_id).with_for_update()).first()
    if actual is None or tuple(actual)!=(row.organization_id,row.product_id,row.warehouse_id,row.batch_number,row.expiry_date):return False
    from .models import PackBatchAvailability
    a=PackBatchAvailability.__table__
    return bool(db.connection().scalar(select(a.c.id).where(a.c.organization_id==scope.company_id,a.c.branch_id==scope.branch_id,
        a.c.pack_context_id==scope.context_id,a.c.batch_id==row.batch_id,a.c.active.is_(True))))
