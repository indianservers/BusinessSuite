"""Exact lot FK certificate for the private recall command, not a read grant."""
from contextlib import contextmanager
from weakref import WeakKeyDictionary
from sqlalchemy import inspect,select
from app.apps.srm.models import SRMInventoryBatch
from .models import PackBatchAvailability,PharmaBatchReceipt
from .recall_models import PharmaRecall

_plans=WeakKeyDictionary()


def _snapshot(row):
    return tuple((column.key,getattr(row,column.key)) for column in row.__table__.columns if column.key not in {'id','created_at','revision','state'})


@contextmanager
def command_plan(db,scope,row):
    state=inspect(row)
    if type(row) is not PharmaRecall or (not state.transient and (state.session is not db or not state.persistent or row in db.deleted)):
        raise ValueError('A new or actual persisted recall source is required')
    if (row.organization_id,row.branch_id,row.pack_context_id)!=(scope.company_id,scope.branch_id,scope.context_id):raise ValueError('Recall source scope differs')
    if state.persistent:
        t=PharmaRecall.__table__
        actual=db.connection().execute(select(*(t.c[name] for name,_ in _snapshot(row))).where(t.c.id==row.id)).first()
        if actual is None or tuple(actual)!=tuple(value for _,value in _snapshot(row)):raise ValueError('Recall persisted source differs')
    plans=_plans.setdefault(db,{})
    if id(row) in plans:raise ValueError('Recall command certificate already exists')
    plans[id(row)]=(scope,row,_snapshot(row))
    try:yield
    finally:
        plans.pop(id(row),None)
        if not plans:_plans.pop(db,None)


def reference(db,scope,row,parent,pairs):
    if type(row) is not PharmaRecall or parent is not SRMInventoryBatch.__table__ or tuple((name,key.name) for name,key in pairs)!=(('batch_id','id'),):return False
    proof=_plans.get(db,{}).get(id(row))
    if proof is None or proof[0] is not scope or proof[1] is not row or proof[2]!=_snapshot(row) or inspect(row).session is not db:return False
    b=SRMInventoryBatch.__table__;a=PackBatchAvailability.__table__;r=PharmaBatchReceipt.__table__
    return bool(db.connection().scalar(select(b.c.id).join(a,a.c.batch_id==b.c.id).where(b.c.id==row.batch_id,
        b.c.organization_id==scope.company_id,b.c.product_id==row.product_id,b.c.warehouse_id==row.warehouse_id,
        b.c.batch_number==row.batch_number,b.c.expiry_date==row.expiry_date,a.c.organization_id==scope.company_id,
        a.c.branch_id==scope.branch_id,a.c.pack_context_id==scope.context_id,a.c.active.is_(True),
        select(r.c.id).where(r.c.batch_id==b.c.id,r.c.organization_id==scope.company_id,r.c.product_id==row.product_id,r.c.warehouse_id==row.warehouse_id).exists())))
