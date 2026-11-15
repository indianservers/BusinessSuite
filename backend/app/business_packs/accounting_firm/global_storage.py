"""Pack-local bounded native S3/Blob reads after actual Accounts file authorization."""
from hashlib import sha256
from weakref import WeakKeyDictionary
from urllib.parse import quote
from starlette.responses import Response
from fastapi import HTTPException
from . import service

_PLANS=WeakKeyDictionary()

def _epoch():
    from app.core.config import settings
    names=('STORAGE_BACKEND','UPLOAD_DIR','S3_PREFIX','S3_ENDPOINT_URL','S3_BUCKET','S3_REGION','S3_ACCESS_KEY_ID','S3_SECRET_ACCESS_KEY','BLOB_READ_WRITE_TOKEN')
    return sha256(repr(tuple(getattr(settings,key,None) for key in names)).encode()).hexdigest()


def _bytes(path,expected):
    from app.core import storage
    from app.core.config import settings
    backend=settings.STORAGE_BACKEND
    key=storage.storage_key(path)  # Only the already-authorized canonical path.
    if backend=='s3':
        body=None
        try:
            result=storage.s3_client().get_object(Bucket=settings.S3_BUCKET,Key=key)
            body=result['Body'];declared=result.get('ContentLength')
            if declared is not None and (type(declared) is not int or declared!=expected):service.fail('Stored attachment length changed',409)
            chunks=[];size=0
            while size<=expected:
                chunk=body.read(expected+1-size)
                if not isinstance(chunk,bytes):service.fail('Stored attachment response is invalid',502)
                if not chunk:break
                size+=len(chunk)
                if size>expected:service.fail('Stored attachment length changed',409)
                chunks.append(chunk)
            return b''.join(chunks)
        finally:
            if body is not None:
                try:body.close()
                except Exception:pass
    if backend=='vercel_blob':
        from vercel.blob.sync import stream_blob
        with storage.blob_session(),stream_blob(key,access='private') as stream:
            declared=getattr(getattr(stream,'metadata',None),'size',None)
            if declared is not None and (type(declared) is not int or declared!=expected):service.fail('Stored attachment length changed',409)
            chunks=[];size=0;empty=0
            for chunk in stream:
                if not isinstance(chunk,bytes):service.fail('Stored attachment response is invalid',502)
                if not chunk:
                    empty+=1
                    if empty>8:service.fail('Native cloud storage made no progress',502)
                    continue
                empty=0
                size+=len(chunk)
                if size>expected:service.fail('Stored attachment length changed',409)
                chunks.append(chunk)
            return b''.join(chunks)
    service.fail('This storage backend is not integrated',503)


def response(db,actor,scope,asset,stored):
    from app.core.config import settings
    from app.core.audit_context import context
    from app.apps.project_management.api.router import PMS_MAX_ATTACHMENT_BYTES
    from .cloud_download import _owned
    if (stored is None or stored['status']!='local' or stored['provider']!=settings.STORAGE_BACKEND
            or settings.STORAGE_BACKEND not in {'s3','vercel_blob'} or stored['connection_id'] is not None
            or stored['remote_id'] is not None):service.fail('This attachment needs a verified native storage source',503)
    _owned(db,scope,stored['id'])
    size=stored['size']
    if type(size) is not int or not 0<size<=PMS_MAX_ATTACHMENT_BYTES or size!=asset.size_bytes:
        service.fail('Stored attachment size requires reconciliation',409)
    if db.info.get('business_pack_scope') is not scope:service.fail('Attachment authorization changed')
    epoch=_epoch()
    try:content=_bytes(asset.storage_path,size)
    except HTTPException:raise
    except Exception:service.fail('Native cloud storage is unavailable',502)
    if _epoch()!=epoch:service.fail('Native storage configuration changed',409)
    if len(content)!=size or sha256(content).hexdigest()!=stored['sha256']:
        service.fail('Stored attachment contents changed',409)
    evidence=context.get()
    if evidence is not None:evidence['file_response_path']=str(asset.storage_path)
    result=Response(content,media_type=asset.mime_type or stored['content_type'] or 'application/octet-stream',headers={
        'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':'sandbox',
        'Content-Disposition':"attachment; filename*=UTF-8''"+quote(asset.original_name or asset.file_name,safe='')})
    _PLANS[result]=(db,actor,scope,asset.storage_path,dict(stored),epoch)
    return result


def pending(response):return response in _PLANS


def finish(response,db,actor,scope):
    from .cloud_download import _owned,_locator
    plan=_PLANS.pop(response,None)
    if plan is None:service.fail('An actual verified native storage read is required')
    outer,actual,original,path,stored,epoch=plan
    if (outer is not db or actual is not actor or original is not scope or db.info.get('business_pack_scope') is not scope):
        service.fail('Attachment authorization changed')
    _owned(db,scope,stored['id'])
    if _epoch()!=epoch or _locator(db,scope,path)!=stored:service.fail('Native storage source changed',409)
    return response


def abort(response):
    if isinstance(response,Response):_PLANS.pop(response,None)
