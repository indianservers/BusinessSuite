"""Actual native global upload/read logic with only SDK/network boundaries faked."""
import io
from contextlib import contextmanager
from types import SimpleNamespace
from pathlib import Path
import pytest
from sqlalchemy import update
from app.models.file_storage import StorageObject
from app.apps.project_management.models import PMSFileAsset
from app.business_packs.models import PackUserGrant
from app.business_packs.accounting_firm.models import AccountsCommand
from tests.test_accounts_binary_uploads import accounts,binary_task,source,post
from tests.test_accounts_actual_time import delivery
from tests.test_accounts_cloud_download import cloud
from tests.test_accounts_periods import scenario,catalog,directory_identity
from tests.test_pms_attachment_operation import attachment_source

@pytest.fixture(params=['s3','vercel_blob'])
def global_store(request,db,accounts,monkeypatch):
    from copy import deepcopy
    from app.access.models import AccessPolicy
    from app.core import storage
    from app.core.config import settings
    backend=request.param
    monkeypatch.setattr(settings,'STORAGE_BACKEND',backend);monkeypatch.setattr(settings,'PMS_GOOGLE_DRIVE_REQUIRED',False)
    monkeypatch.setattr(settings,'S3_BUCKET','isolated-native-bucket');monkeypatch.setattr(settings,'S3_PREFIX','isolated-native-prefix')
    monkeypatch.setattr(settings,'S3_ACCESS_KEY_ID','fake-sdk-access');monkeypatch.setattr(settings,'S3_SECRET_ACCESS_KEY','fake-sdk-secret')
    monkeypatch.setattr(settings,'BLOB_READ_WRITE_TOKEN','vercel_blob_rw_fixture_token')
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=accounts['preparer']['user'].id).one();grants=deepcopy(policy.grants);grants['srm']['actions'].append('export');policy.grants=grants;db.commit()
    state={'backend':backend,'remote':{},'reads':[],'closed':[],'amounts':[],'fault':None,'during':None,'native_client':0}
    class Body(io.BytesIO):
        def read(self,n=-1):
            assert n>0,'No unbounded SDK read is permitted';state['amounts'].append(n)
            return b'X'*min(n,7) if state['fault']=='endless' else super().read(min(n,7))
        def close(self):state['closed'].append(True);super().close()
    if backend=='s3':
        import boto3
        class S3:
            def upload_file(self,path,bucket,key,ExtraArgs):assert bucket==settings.S3_BUCKET;state['remote'][key]=Path(path).read_bytes()
            def get_object(self,*,Bucket,Key):
                assert Bucket==settings.S3_BUCKET;state['reads'].append(Key)
                if state['during']:state['during']()
                if state['fault']=='disconnected':raise RuntimeError('credential-secret-must-not-leak')
                body=state['remote'][Key]
                if state['fault']=='checksum':body=b'X'+body[1:]
                if state['fault']=='oversize':body+=b'!'
                return {'Body':Body(body),'ContentLength':len(body) if state['fault']!='oversize' else len(body)-1}
            def generate_presigned_url(self,*a,**k):raise AssertionError('No generic signed download URL')
            def delete_object(self,*a,**k):raise AssertionError('No cloud deletion')
        def client(name,**kwargs):assert name=='s3';state['native_client']+=1;return S3()
        storage.s3_client.cache_clear();monkeypatch.setattr(boto3,'client',client)
    else:
        import vercel.api,vercel.blob.sync as blob
        @contextmanager
        def session(**kwargs):assert kwargs['service_options'];state['native_client']+=1;yield
        def put(key,stream,**kwargs):assert kwargs['access']=='private';state['remote'][key]=stream.read()
        @contextmanager
        def stream(key,*,access):
            assert access=='private';state['reads'].append(key)
            if state['during']:state['during']()
            if state['fault']=='disconnected':raise RuntimeError('credential-secret-must-not-leak')
            body=state['remote'][key]
            if state['fault']=='checksum':body=b'X'+body[1:]
            if state['fault']=='oversize':body+=b'!'
            class Download:
                metadata=SimpleNamespace(size=len(body) if state['fault']!='oversize' else len(body)-1)
                def __iter__(self):
                    if state['fault']=='empty_stall':
                        while True:yield b''
                    if state['fault']=='endless':
                        while True:yield b'X'*7
                    for index in range(0,len(body),7):
                        if state['fault']=='empty_finite':yield b'';yield b''
                        yield body[index:index+7]
            try:yield Download()
            finally:state['closed'].append(True)
        monkeypatch.setattr(vercel.api,'session',session);monkeypatch.setattr(blob,'put_blob',put);monkeypatch.setattr(blob,'stream_blob',stream)
    yield state
    storage.s3_client.cache_clear()


def ready(client,accounts,binary_task):
    path,data,row=source(client,accounts,binary_task[0]);post(client,accounts['preparer']['headers'],path,data)
    return path.removesuffix('/upload')+'/download'


def test_global_native_bytes_no_url_no_disk_or_metadata_write(client,db,accounts,binary_task,global_store):
    endpoint=ready(client,accounts,binary_task);asset=db.query(PMSFileAsset).one();stored=db.query(StorageObject).one()
    assert stored.provider==global_store['backend'] and stored.status=='local'
    before=(db.query(PMSFileAsset).count(),db.query(StorageObject).count(),db.query(AccountsCommand).count(),set(binary_task[1].rglob('*')))
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==200,result.text
    assert result.content==b'Actual canonical uploaded client statements' and 'location' not in result.headers
    assert result.headers['cache-control']=='private, no-store' and global_store['native_client']>0 and global_store['closed']
    from app.core.storage import storage_key
    assert global_store['reads']==[storage_key(asset.storage_path)]
    assert before==(db.query(PMSFileAsset).count(),db.query(StorageObject).count(),db.query(AccountsCommand).count(),set(binary_task[1].rglob('*')))


@pytest.mark.parametrize('fault,status',[('checksum',409),('oversize',409),('endless',409),('disconnected',502)])
def test_global_faults_bounded_closed_and_generic(client,db,accounts,binary_task,global_store,fault,status):
    endpoint=ready(client,accounts,binary_task);global_store['fault']=fault
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==status,result.text
    assert 'location' not in result.headers and b'credential-secret-must-not-leak' not in result.content
    assert b'Actual canonical uploaded' not in result.content
    if fault!='disconnected':assert global_store['closed']


@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef'),('construction','site_engineer')])
def test_global_exact_context_pair_before_read(client,db,accounts,binary_task,global_store,pack,role):
    from tests.test_business_pack_http_integration import grant
    endpoint=ready(client,accounts,binary_task);context,_=grant(db,accounts['preparer']['user'],accounts['branch'],pack,role)
    result=client.get(endpoint,headers=accounts['preparer']['headers']|{'X-Suite-Pack-Context':str(context.id)},follow_redirects=False)
    assert result.status_code==403 and global_store['reads']==[] and 'location' not in result.headers


@pytest.mark.parametrize('kind',['grant','native_rights'])
def test_global_revocation_during_sdk_read_never_delivers_private_bytes(client,db,accounts,binary_task,global_store,kind):
    endpoint=ready(client,accounts,binary_task);user_id=accounts['preparer']['user'].id
    if kind=='grant':global_store['during']=lambda:db.connection().execute(update(PackUserGrant).where(PackUserGrant.context_id==accounts['context'],PackUserGrant.user_id==user_id).values(active=False))
    else:
        from copy import deepcopy
        from app.access.models import AccessPolicy
        policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=user_id).one();ident=policy.id;grants=deepcopy(policy.grants);grants['project_management']['enabled']=False
        global_store['during']=lambda:db.connection().execute(update(AccessPolicy).where(AccessPolicy.id==ident).values(grants=grants))
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==403 and 'location' not in result.headers and b'Actual canonical uploaded' not in result.content
    assert global_store['closed']


def test_global_malformed_source_path_never_reaches_sdk(client,db,accounts,binary_task,global_store,tmp_path):
    endpoint=ready(client,accounts,binary_task);db.connection().execute(update(PMSFileAsset).values(storage_path=str(tmp_path/'outside-source.txt')));db.commit()
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==503 and global_store['reads']==[] and 'location' not in result.headers


def test_global_native_size_ceiling_checked_before_fetch(client,db,accounts,binary_task,global_store):
    from app.apps.project_management.api.router import PMS_MAX_ATTACHMENT_BYTES
    endpoint=ready(client,accounts,binary_task)
    db.connection().execute(update(PMSFileAsset).values(size_bytes=PMS_MAX_ATTACHMENT_BYTES+1));db.connection().execute(update(StorageObject).values(size=PMS_MAX_ATTACHMENT_BYTES+1));db.commit()
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==409 and global_store['reads']==[] and 'location' not in result.headers


def test_global_configuration_change_during_fetch_rejected(client,db,accounts,binary_task,global_store,monkeypatch):
    from app.core.config import settings
    endpoint=ready(client,accounts,binary_task)
    global_store['during']=lambda:monkeypatch.setattr(settings,'S3_PREFIX','changed-native-prefix')
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==409 and 'location' not in result.headers and b'Actual canonical uploaded' not in result.content
    assert global_store['closed']


def test_global_missing_owned_locator_rejected_before_fetch(client,db,accounts,binary_task,global_store):
    from app.business_packs.models import PackRecordOwnership
    from sqlalchemy import delete
    endpoint=ready(client,accounts,binary_task);ident=db.query(StorageObject.id).scalar()
    db.connection().execute(delete(PackRecordOwnership).where(PackRecordOwnership.resource_table==StorageObject.__tablename__,PackRecordOwnership.resource_key==str(ident)));db.commit()
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==404 and global_store['reads']==[] and 'location' not in result.headers


@pytest.mark.parametrize('global_store',['vercel_blob'],indirect=True)
def test_blob_empty_stream_stall_is_bounded_and_closed(client,db,accounts,binary_task,global_store):
    endpoint=ready(client,accounts,binary_task);global_store['fault']='empty_stall'
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==502 and 'no progress' in result.text
    assert global_store['closed'] and 'location' not in result.headers


@pytest.mark.parametrize('global_store',['vercel_blob'],indirect=True)
def test_blob_finite_empty_chunks_preserve_legitimate_native_bytes(client,db,accounts,binary_task,global_store):
    endpoint=ready(client,accounts,binary_task);global_store['fault']='empty_finite'
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==200 and result.content==b'Actual canonical uploaded client statements'
    assert global_store['closed'] and 'location' not in result.headers


@pytest.mark.parametrize('phase',['resource_authority','document_source','finish_source'])
def test_global_response_plan_cleared_even_if_failed_response_is_retained(client,db,accounts,binary_task,global_store,monkeypatch,phase):
    from app.business_packs.accounting_firm import global_storage,cloud_download,documents
    from fastapi import HTTPException
    endpoint=ready(client,accounts,binary_task);seen=[];original=global_storage.response
    def observed(*args,**kwargs):
        result=original(*args,**kwargs);seen.append(result);return result
    monkeypatch.setattr(global_storage,'response',observed)
    if phase=='resource_authority':
        ident=accounts['preparer']['user'].id
        global_store['during']=lambda:db.connection().execute(update(PackUserGrant).where(PackUserGrant.context_id==accounts['context'],PackUserGrant.user_id==ident).values(active=False))
    elif phase=='finish_source':
        ident=db.query(StorageObject.id).scalar()
        global_store['during']=lambda:db.connection().execute(update(StorageObject).where(StorageObject.id==ident).values(sha256='a'*64))
    else:
        current=documents._current;calls=[]
        def recheck(*args,**kwargs):
            calls.append(True)
            if len(calls)>1:raise HTTPException(409,'Actual document source recheck failed')
            return current(*args,**kwargs)
        monkeypatch.setattr(documents,'_current',recheck)
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==(403 if phase=='resource_authority' else 409),result.text
    assert len(seen)==1 and not global_storage.pending(seen[0]) and not cloud_download.pending(seen[0])
    assert 'location' not in result.headers and b'Actual canonical uploaded' not in result.content


@pytest.mark.parametrize('phase',['resource_authority','document_source'])
def test_provider_response_plan_cleared_on_failure_without_waiting_for_gc(client,db,accounts,binary_task,cloud,monkeypatch,phase):
    from app.business_packs.accounting_firm import cloud_download,global_storage,documents
    from app.services import file_storage_providers as providers
    from fastapi import HTTPException
    endpoint=ready(client,accounts,binary_task);seen=[];original=cloud_download.response
    def observed(*args,**kwargs):
        result=original(*args,**kwargs);seen.append(result);return result
    monkeypatch.setattr(cloud_download,'response',observed)
    if phase=='resource_authority':
        ident=accounts['preparer']['user'].id
        def revoke(native,connection,key):
            db.connection().execute(update(PackUserGrant).where(PackUserGrant.context_id==accounts['context'],PackUserGrant.user_id==ident).values(active=False))
            return cloud['remote'][key]
        monkeypatch.setattr(providers,'download',revoke)
    else:
        current=documents._current;calls=[]
        def recheck(*args,**kwargs):
            calls.append(True)
            if len(calls)>1:raise HTTPException(409,'Actual document source recheck failed')
            return current(*args,**kwargs)
        monkeypatch.setattr(documents,'_current',recheck)
    result=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==(403 if phase=='resource_authority' else 409),result.text
    assert len(seen)==1 and not cloud_download.pending(seen[0]) and not global_storage.pending(seen[0])
    assert 'location' not in result.headers and b'Actual canonical uploaded' not in result.content
