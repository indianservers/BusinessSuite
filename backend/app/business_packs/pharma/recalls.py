"""Atomic private recall authoring and canonical quarantine; no money or stock quantity changes."""
from hashlib import sha256
import json
from sqlalchemy import select,inspect
from app.apps.srm.models import SRMInventoryBatch,SRMProduct,SRMWarehouse
from app.apps.srm.service_checkout import _source_scope
from app.apps.srm.stock_resource import _native_branch
from .models import PackBatchAvailability,PharmaBatchReceipt
from .recall_models import MODELS,PharmaBatchControl,PharmaRecall,PharmaRecallEvent
from .recall_schemas import RecallInput,RecallCommand
from .recall_references import command_plan
from .receipts import authority,fail


def selected(db,actor,*,write=True):
    company,branch,scope=authority(db,actor,'recalls.manage',write=write)
    from app.business_packs.catalog_management import _module_grant
    from app.business_packs.common_core import _native_authority
    _native_authority(db,actor,company)
    grant=_module_grant(db,actor,scope,'srm')
    required={'create','edit'} if write else {'view'}
    names={'srm_manage','srm_admin'} if write else {'srm_view','srm_manage','srm_admin'}
    if not actor.is_superuser and (not grant.get('enabled') or not required<=set(grant.get('actions',())) or
            not names.intersection(grant.get('permissions',()))):
        fail('Fresh native inventory authority is required for recall operations')
    if write:
        from app.access.service import check_background_access
        check_background_access(db,actor,'srm','edit')
    inspector=inspect(db.connection())
    if not all(inspector.has_table(model.__tablename__) for model in MODELS):fail('Install the Pharma recall extension first',503)
    return company,branch,scope


def _native_fingerprint(db,actor):
    scope=db.info.get('business_pack_scope')
    if scope is None or scope.pack_key!='pharma' or scope.user_id!=actor.id:fail('A verified Pharma request is required')
    from app.business_packs.common_core import _native_authority
    return _native_authority(db,actor,scope.company_id)


def _digest(data,recall_id=None):
    body={'recall_id':recall_id,'command':data.model_dump(mode='json')}
    return sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _query(db,model,scope):
    return db.query(model).filter_by(organization_id=scope.company_id,branch_id=scope.branch_id,pack_context_id=scope.context_id)


def _batch(db,scope,batch_id):
    # Fixed identity lookup first, then canonical product/warehouse/batch lock
    # order. The company writer serializes both recall and native checkout.
    b=SRMInventoryBatch.__table__;a=PackBatchAvailability.__table__
    identity=db.connection().execute(select(b.c.product_id,b.c.warehouse_id).join(a,a.c.batch_id==b.c.id).where(b.c.id==batch_id,
        b.c.organization_id==scope.company_id,a.c.organization_id==scope.company_id,a.c.branch_id==scope.branch_id,
        a.c.pack_context_id==scope.context_id,a.c.active.is_(True))).first()
    if identity is None:fail('Eligible batch is unavailable',404)
    p=SRMProduct.__table__;w=SRMWarehouse.__table__
    product=db.connection().execute(select(p.c.id,p.c.metadata_json).where(p.c.id==identity.product_id,p.c.organization_id==scope.company_id).with_for_update()).mappings().first()
    warehouse=db.connection().execute(select(w.c.id).where(w.c.id==identity.warehouse_id,w.c.organization_id==scope.company_id).with_for_update()).first()
    if product is None or warehouse is None:fail('Eligible batch resources are unavailable',404)
    _source_scope(db,scope,scope.company_id,scope.branch_id,SRMProduct,identity.product_id,master=True)
    _source_scope(db,scope,scope.company_id,scope.branch_id,SRMWarehouse,identity.warehouse_id,master=True)
    from app.shared.catalog_branches import is_available
    from types import SimpleNamespace
    if not is_available(SimpleNamespace(metadata_json=product['metadata_json']),scope.branch_id):fail('Eligible batch resources are unavailable',404)
    _native_branch(db,w.name,identity.warehouse_id,scope.company_id,scope.branch_id)
    _native_branch(db,b.name,batch_id,scope.company_id,scope.branch_id)
    from .reads import workspace_bound
    if db.connection().scalar(select(workspace_bound(db,scope.company_id,identity.product_id))):fail('Workspace offerings are not integrated for Pharma recall',409)
    batch=db.connection().execute(select(b).where(b.c.id==batch_id,b.c.organization_id==scope.company_id).with_for_update()).mappings().first()
    if batch is None or (batch['product_id'],batch['warehouse_id'])!=tuple(identity):fail('Eligible batch source changed',409)
    r=PharmaBatchReceipt.__table__
    if not db.connection().scalar(select(r.c.id).where(r.c.organization_id==scope.company_id,r.c.batch_id==batch_id,
        r.c.product_id==batch['product_id'],r.c.warehouse_id==batch['warehouse_id'])):fail('Recall requires an explicitly received managed batch',409)
    # Canonical lot resources must not be adopted from private legacy records.
    from app.business_packs.models import PackRecordOwnership
    owned=PackRecordOwnership.__table__
    if db.connection().scalar(select(owned.c.id).where(owned.c.resource_table==b.name,owned.c.resource_key==str(batch_id))):fail('Canonical batch has unsupported private ownership')
    control=PharmaBatchControl.__table__
    state=db.connection().execute(select(control.c.id,control.c.revision).where(control.c.organization_id==scope.company_id,control.c.batch_id==batch_id).with_for_update()).first()
    return batch,(state.revision if state else 0),state


def _apply(db,scope,batch,current,control,data):
    if data.expected_batch_revision!=current or data.expected_batch_status!=batch['status']:fail('Batch state changed; reload before continuing',409)
    target={'quarantine':'quarantined','recall':'recalled'}.get(data.action,batch['status'])
    if batch['status'] not in {'available','quarantined','recalled'}:fail('This batch state needs native inventory reconciliation',409)
    if batch['status']=='recalled' and target!='recalled':fail('Recalled stock cannot be released or downgraded',409)
    if data.action=='close':return target,current
    b=SRMInventoryBatch.__table__;c=PharmaBatchControl.__table__
    changed=db.connection().execute(b.update().where(b.c.id==batch['id'],b.c.organization_id==scope.company_id,b.c.status==batch['status'],
        b.c.product_id==batch['product_id'],b.c.warehouse_id==batch['warehouse_id']).values(status=target))
    if changed.rowcount!=1:fail('Batch state changed; reload before continuing',409)
    if control:
        changed=db.connection().execute(c.update().where(c.c.id==control.id,c.c.organization_id==scope.company_id,c.c.revision==current).values(revision=current+1))
        if changed.rowcount!=1:fail('Batch revision changed; reload before continuing',409)
    else:db.connection().execute(c.insert().values(organization_id=scope.company_id,batch_id=batch['id'],revision=1))
    return target,current+1


def _result(root,event):
    return {'id':root.id,'event_id':event.id,'revision':event.revision,'state':event.state_after,'action':event.action,
        'batch_id':root.batch_id,'batch_number':root.batch_number,'expiry_date':root.expiry_date.isoformat(),
        'batch_status':event.batch_status_after,'batch_revision':event.batch_revision_after,'reason':event.reason}


def _replay(db,scope,actor,data,digest,recall_id=None):
    event=_query(db,PharmaRecallEvent,scope).filter_by(request_key=str(data.request_key)).one_or_none()
    if event is None:return None
    if event.created_by!=actor.id or event.request_sha256!=digest or (recall_id is not None and event.recall_id!=recall_id):fail('Recall request key was used for another command',409)
    root=_query(db,PharmaRecall,scope).filter_by(id=event.recall_id).one_or_none()
    if root is None:fail('Recall source is unavailable',409)
    _source_scope(db,scope,scope.company_id,scope.branch_id,PharmaRecall,root.id)
    _source_scope(db,scope,scope.company_id,scope.branch_id,PharmaRecallEvent,event.id)
    return _result(root,event)


def _event(db,scope,actor,root,data,digest,batch,old_revision,new_revision,new_status):
    event=PharmaRecallEvent(recall_id=root.id,organization_id=scope.company_id,branch_id=scope.branch_id,pack_context_id=scope.context_id,
        request_key=str(data.request_key),request_sha256=digest,created_by=actor.id,action=data.action,reason=data.reason,
        revision=root.revision,state_after=root.state,batch_status_before=batch['status'],batch_status_after=new_status,
        batch_revision_before=old_revision,batch_revision_after=new_revision)
    db.add(event);db.flush()
    return event


def create(data,db,actor,*,commit=True):
    data=RecallInput.model_validate(data.model_dump())
    native=_native_fingerprint(db,actor)
    company,branch,scope=selected(db,actor)
    from app.apps.srm.services.commercial import lock_tenant
    lock_tenant(db,actor)
    if selected(db,actor)!=(company,branch,scope) or _native_fingerprint(db,actor)!=native:fail('Recall authorization changed')
    digest=_digest(data)
    replay=_replay(db,scope,actor,data,digest)
    if replay is not None:return replay
    with db.begin_nested():
        batch,revision,control=_batch(db,scope,data.batch_id)
        if selected(db,actor)!=(company,branch,scope) or _native_fingerprint(db,actor)!=native:fail('Recall authorization changed')
        status,next_revision=_apply(db,scope,batch,revision,control,data)
        root=PharmaRecall(organization_id=company,branch_id=branch,pack_context_id=scope.context_id,batch_id=batch['id'],
            product_id=batch['product_id'],warehouse_id=batch['warehouse_id'],batch_number=batch['batch_number'],expiry_date=batch['expiry_date'],
            reason=data.reason,created_by=actor.id,state='open',revision=1)
        with command_plan(db,scope,root):
            db.add(root);db.flush()
            event=_event(db,scope,actor,root,data,digest,batch,revision,next_revision,status)
        result=_result(root,event)
    if commit:db.commit()
    return result


def command(ident,data,db,actor,*,commit=True):
    data=RecallCommand.model_validate(data.model_dump())
    native=_native_fingerprint(db,actor)
    company,branch,scope=selected(db,actor)
    from app.apps.srm.services.commercial import lock_tenant
    lock_tenant(db,actor)
    if selected(db,actor)!=(company,branch,scope) or _native_fingerprint(db,actor)!=native:fail('Recall authorization changed')
    digest=_digest(data,ident)
    replay=_replay(db,scope,actor,data,digest,ident)
    if replay is not None:return replay
    with db.begin_nested():
        root=_query(db,PharmaRecall,scope).filter_by(id=ident).with_for_update().one_or_none()
        if root is None:fail('Recall not found',404)
        _source_scope(db,scope,company,branch,PharmaRecall,root.id)
        if root.revision!=data.expected_revision or root.state!='open':fail('Recall changed or is closed; reload before continuing',409)
        batch,revision,control=_batch(db,scope,root.batch_id)
        if (root.product_id,root.warehouse_id,root.batch_number,root.expiry_date)!=(batch['product_id'],batch['warehouse_id'],batch['batch_number'],batch['expiry_date']):fail('Recall batch source changed',409)
        if selected(db,actor)!=(company,branch,scope) or _native_fingerprint(db,actor)!=native:fail('Recall authorization changed')
        status,next_revision=_apply(db,scope,batch,revision,control,data)
        with command_plan(db,scope,root):
            if data.action=='close':root.state='closed'
            root.revision+=1;db.flush()
            event=_event(db,scope,actor,root,data,digest,batch,revision,next_revision,status)
        result=_result(root,event)
    if commit:db.commit()
    return result


def detail(ident,db,actor):
    _,_,scope=selected(db,actor,write=False)
    root=_query(db,PharmaRecall,scope).filter_by(id=ident).one_or_none()
    if root is None:fail('Recall not found',404)
    _source_scope(db,scope,scope.company_id,scope.branch_id,PharmaRecall,root.id)
    event=_query(db,PharmaRecallEvent,scope).filter_by(recall_id=root.id,revision=root.revision).one_or_none()
    if event is None:fail('Recall event history needs reconciliation',409)
    _source_scope(db,scope,scope.company_id,scope.branch_id,PharmaRecallEvent,event.id)
    return _result(root,event)


def list_cases(db,actor,*,after=0,limit=30):
    _,_,scope=selected(db,actor,write=False)
    rows=_query(db,PharmaRecall,scope).filter(PharmaRecall.id>after).order_by(PharmaRecall.id).limit(limit+1).all()
    latest={}
    if rows:
        events=_query(db,PharmaRecallEvent,scope).join(PharmaRecall,PharmaRecall.id==PharmaRecallEvent.recall_id).filter(
            PharmaRecall.id.in_([row.id for row in rows[:limit]]),PharmaRecallEvent.revision==PharmaRecall.revision).all()
        latest={event.recall_id:event for event in events}
    items=[]
    for row in rows[:limit]:
        _source_scope(db,scope,scope.company_id,scope.branch_id,PharmaRecall,row.id)
        event=latest.get(row.id)
        if event is None:fail('Recall event history needs reconciliation',409)
        _source_scope(db,scope,scope.company_id,scope.branch_id,PharmaRecallEvent,event.id)
        items.append(_result(row,event))
    return {'items':items,'has_more':len(rows)>limit,'next':rows[limit-1].id if len(rows)>limit else None}
