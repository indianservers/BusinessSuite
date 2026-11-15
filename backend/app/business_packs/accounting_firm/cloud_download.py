"""Immediate Accounts cloud bytes; never mint a context-unbound file capability."""
from hashlib import sha256
from types import SimpleNamespace
from urllib.parse import quote
from weakref import WeakKeyDictionary
from sqlalchemy import select,update,inspect
from starlette.responses import Response
from . import service

_PLANS=WeakKeyDictionary()
_FIELDS=('id','organization_id','relative_path','connection_id','provider','remote_id','sha256','size','content_type','filename','status')
_CONN=('id','organization_id','provider','connected','encrypted_value','expires_at')


def _locator(db,scope,path):
    from app.models.file_storage import StorageObject
    from app.services.file_storage import relative
    from fastapi import HTTPException
    try:relative_path=relative(path)
    except HTTPException:return None  # Original native local attachments may predate upload-root locators.
    t=StorageObject.__table__
    rows=db.connection().execute(select(*(t.c[key] for key in _FIELDS)).where(t.c.organization_id==scope.company_id,t.c.relative_path==relative_path).limit(2)).mappings().all()
    if len(rows)>1:service.fail('Cloud attachment requires reconciliation',409)
    return dict(rows[0]) if rows else None


def _owned(db,scope,ident):
    from app.models.file_storage import StorageObject
    from app.business_packs.models import PackRecordOwnership
    from app.branches.models import BranchOwnership
    key=str(ident)
    pack=db.connection().execute(select(PackRecordOwnership.company_id,PackRecordOwnership.branch_id,PackRecordOwnership.context_id).where(PackRecordOwnership.resource_table==StorageObject.__tablename__,PackRecordOwnership.resource_key==key)).all()
    branch=db.connection().execute(select(BranchOwnership.company_id,BranchOwnership.branch_id).where(BranchOwnership.resource_table==StorageObject.__tablename__,BranchOwnership.resource_key==key)).all()
    if pack!=[(scope.company_id,scope.branch_id,scope.context_id)] or branch!=[(scope.company_id,scope.branch_id)]:
        service.fail('Cloud attachment source is unavailable in this context',404)


class _ProviderRead:
    """Native OAuth refresh capture only; no Session/SQL/transaction handle."""
    __slots__=('_view','_baseline','_changed')
    def __init__(self,values):self._baseline=dict(values);self._view=SimpleNamespace(**values);self._changed=False
    def _deny(self,*args,**kwargs):service.fail('Cloud attachment provider has no general database authority')
    connection=execute=query=get_bind=commit=rollback=add=delete=_deny
    def flush(self,*args,**kwargs):
        if args or kwargs:self._deny()
        actual=vars(self._view)
        if set(actual)!=set(self._baseline) or any(actual[key]!=value for key,value in self._baseline.items() if key not in {'encrypted_value','expires_at'}):self._deny()
        from datetime import datetime
        if (not isinstance(actual['encrypted_value'],str) or not actual['encrypted_value']
                or actual['expires_at'] is not None and not isinstance(actual['expires_at'],datetime)):self._deny()
        self._changed=any(actual[key]!=self._baseline[key] for key in ('encrypted_value','expires_at'))


def response(db,actor,scope,native,asset):
    from app.core.config import settings
    from app.apps.project_management.models import PMSFileAsset
    from app.models.file_storage import StorageConnection
    from app.services import file_storage_providers as providers
    from .pms_sources import _Reader
    if (type(native) is not _Reader or type(asset) is not PMSFileAsset or inspect(asset).session is not native
            or not inspect(asset).persistent or db.info.get('business_pack_scope') is not scope):
        service.fail('Actual native Accounts file authorization is required')
    stored=_locator(db,scope,asset.storage_path)
    if not stored or stored['status']!='cloud':
        if settings.STORAGE_BACKEND!='local':
            from .global_storage import response as global_response
            return global_response(db,actor,scope,asset,stored)
        return None
    _owned(db,scope,stored['id'])
    if stored['size']!=asset.size_bytes:service.fail('Cloud attachment metadata changed',409)
    t=StorageConnection.__table__
    row=db.connection().execute(select(*(t.c[key] for key in _CONN)).where(t.c.id==stored['connection_id'],t.c.organization_id==scope.company_id).with_for_update()).mappings().one_or_none()
    if not row or not row['connected'] or row['provider']!=stored['provider']:service.fail('Reconnect the original storage account',409)
    provider=_ProviderRead(dict(row))
    content=providers.download(provider,provider._view,stored['remote_id'])
    provider.flush()  # Also reject unflushed mutation of immutable provider identity.
    if not isinstance(content,bytes) or len(content)!=stored['size'] or sha256(content).hexdigest()!=stored['sha256']:
        service.fail('Cloud file contents changed; checksum verification failed',409)
    from app.core.audit_context import context as audit_context
    evidence=audit_context.get()
    if evidence is not None:evidence['file_response_path']=str(asset.storage_path)
    result=Response(content,media_type=asset.mime_type or stored['content_type'] or 'application/octet-stream',headers={
        'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':'sandbox',
        'Content-Disposition':"attachment; filename*=UTF-8''"+quote(asset.original_name or asset.file_name,safe='')})
    _PLANS[result]=(db,actor,scope,asset.storage_path,stored,provider)
    return result


def pending(response):
    from .global_storage import pending as global_pending
    return response in _PLANS or global_pending(response)


def finish(response,db,actor,scope):
    from .global_storage import pending as global_pending,finish as global_finish
    if global_pending(response):return global_finish(response,db,actor,scope)
    plan=_PLANS.pop(response,None)
    if plan is None:return response
    outer,actual,original,path,stored,provider=plan
    if outer is not db or actual is not actor or original is not scope or db.info.get('business_pack_scope') is not scope:
        service.fail('Cloud attachment authorization changed')
    _owned(db,scope,stored['id'])
    if _locator(db,scope,path)!=stored:service.fail('Cloud attachment source changed',409)
    provider.flush()
    from app.models.file_storage import StorageConnection
    t=StorageConnection.__table__;old=provider._baseline
    current=db.connection().execute(select(*(t.c[key] for key in _CONN)).where(t.c.id==old['id'],t.c.organization_id==scope.company_id)).mappings().one_or_none()
    if current is None or dict(current)!=old:service.fail('Storage connection changed during download',409)
    if provider._changed:
        predicate=[t.c[key]==value if value is not None else t.c[key].is_(None) for key,value in old.items()]
        changed=db.connection().execute(update(t).where(*predicate).values(encrypted_value=provider._view.encrypted_value,expires_at=provider._view.expires_at))
        if changed.rowcount!=1:service.fail('Storage credentials changed; retry the authorized download',409)
        db.commit()  # Only the exact native provider refresh; no business-row mutation.
    return response


def abort(response):
    from .global_storage import abort as global_abort
    global_abort(response)
    if isinstance(response,Response):_PLANS.pop(response,None)
