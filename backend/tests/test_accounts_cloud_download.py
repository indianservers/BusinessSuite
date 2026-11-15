"""Pack-local cloud bytes cannot become a context-unbound bearer capability."""
from copy import deepcopy
import pytest
from sqlalchemy import event,update
from app.models.file_storage import StoragePolicy,StorageConnection,StorageObject
from app.business_packs.models import PackUserGrant
from app.business_packs.accounting_firm.models import AccountsCommand
from tests.test_accounts_binary_uploads import accounts,binary_task,source,post
from tests.test_accounts_actual_time import delivery
from tests.test_accounts_periods import scenario,catalog,directory_identity
from tests.test_pms_attachment_operation import attachment_source

@pytest.fixture
def cloud(db,accounts,monkeypatch):
    from app.services import file_storage_providers as providers
    from app.core.config import settings
    from app.access.models import AccessPolicy
    connection=StorageConnection(organization_id=1,provider='google_drive',label='Isolated cloud read',connected=True,created_by=accounts['manager'].id,encrypted_value='fake-not-live')
    db.add(connection);db.flush();db.add(StoragePolicy(organization_id=1,enabled=True,routes={'pms':{'connection_id':connection.id,'folder_id':'root'}}))
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=accounts['preparer']['user'].id).one();grants=deepcopy(policy.grants);grants['srm']['actions'].append('export');policy.grants=grants;db.commit()
    remote={};reads=[]
    def upload(db,conn,folder,name,content,content_type):
        ident='owned-cloud-'+str(len(remote)+1);remote[ident]=content;return ident
    def download(db,conn,ident):reads.append(ident);return remote[ident]
    monkeypatch.setattr(settings,'PMS_GOOGLE_DRIVE_REQUIRED',True);monkeypatch.setattr(providers,'upload',upload);monkeypatch.setattr(providers,'download',download)
    return {'remote':remote,'reads':reads,'connection':connection}


def test_cloud_download_is_immediate_without_unbound_redirect(client,db,accounts,binary_task,cloud):
    path,data,row=source(client,accounts,binary_task[0]);post(client,accounts['preparer']['headers'],path,data)
    response=client.get(path.removesuffix('/upload')+'/download',headers=accounts['preparer']['headers'],follow_redirects=False)
    assert response.status_code==200,response.text
    assert response.content==b'Actual canonical uploaded client statements'
    assert 'location' not in response.headers
    assert response.headers['cache-control']=='private, no-store'


def test_upload_rechecks_after_outer_accounts_savepoint_release(client,db,accounts,binary_task,cloud):
    from app.apps.project_management.models import PMSFileAsset
    path,data,row=source(client,accounts,binary_task[0]);connection=db.connection();hit=[]
    def revoke(session):
        if session.in_nested_transaction():
            connection.execute(update(PackUserGrant).where(PackUserGrant.user_id==accounts['preparer']['user'].id,PackUserGrant.context_id==accounts['context']).values(active=False))
            hit.append(True)
    event.listen(db,'after_commit',revoke)
    try:post(client,accounts['preparer']['headers'],path,data,status=403)
    finally:event.remove(db,'after_commit',revoke)
    assert hit
    assert db.query(PMSFileAsset).count()==db.query(StorageObject).count()==0
    assert db.query(AccountsCommand).filter_by(action='document.upload').count()==0

def test_returned_cloud_capability_cannot_replay_in_doctor_context(client,db,accounts,binary_task,cloud):
    from tests.test_business_pack_http_integration import grant
    path,data,row=source(client,accounts,binary_task[0]);post(client,accounts['preparer']['headers'],path,data)
    endpoint=path.removesuffix('/upload')+'/download'
    initial=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    doctor,_=grant(db,accounts['preparer']['user'],accounts['branch'],'hospital','doctor')
    headers=accounts['preparer']['headers']|{'X-Suite-Pack-Context':str(doctor.id)}
    switched=client.get(endpoint,headers=headers,follow_redirects=False);assert switched.status_code in {403,404}
    if initial.status_code in {302,303,307}:
        replay=client.get(initial.headers['location'],headers=headers,follow_redirects=False)
        assert replay.status_code in {403,404},'A returned unbound cloud capability replayed across contexts'
    else:
        assert initial.status_code==200 and 'location' not in initial.headers


@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef'),('construction','site_engineer')])
def test_cloud_same_user_context_switch_and_revocation_never_returns_capability(client,db,accounts,binary_task,cloud,pack,role):
    from tests.test_business_pack_http_integration import grant
    path,data,row=source(client,accounts,binary_task[0]);post(client,accounts['preparer']['headers'],path,data)
    endpoint=path.removesuffix('/upload')+'/download'
    good=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert good.status_code==200 and 'location' not in good.headers
    context,_=grant(db,accounts['preparer']['user'],accounts['branch'],pack,role)
    before=len(cloud['reads'])
    denied=client.get(endpoint,headers=accounts['preparer']['headers']|{'X-Suite-Pack-Context':str(context.id)},follow_redirects=False)
    assert denied.status_code in {403,404} and 'location' not in denied.headers
    assert len(cloud['reads'])==before
    db.connection().execute(update(PackUserGrant).where(PackUserGrant.user_id==accounts['preparer']['user'].id,PackUserGrant.context_id==accounts['context']).values(active=False));db.commit()
    revoked=client.get(endpoint,headers=accounts['preparer']['headers'],follow_redirects=False)
    assert revoked.status_code==403 and len(cloud['reads'])==before


@pytest.mark.parametrize('change',['grant','native_rights','checksum','immutable_connection','provider_raw','connection_disconnected'])
def test_cloud_rechecks_after_provider_boundary_without_leaking_body(client,db,accounts,binary_task,cloud,monkeypatch,change):
    from app.services import file_storage_providers as providers
    from app.access.models import AccessPolicy
    path,data,row=source(client,accounts,binary_task[0]);post(client,accounts['preparer']['headers'],path,data)
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=accounts['preparer']['user'].id).one()
    connection_id=cloud['connection'].id
    def changed(native,connection,ident):
        if change=='grant':db.connection().execute(update(PackUserGrant).where(PackUserGrant.user_id==accounts['preparer']['user'].id,PackUserGrant.context_id==accounts['context']).values(active=False))
        elif change=='native_rights':
            permissions=deepcopy(policy.grants);permissions['project_management']['enabled']=False
            db.connection().execute(update(AccessPolicy).where(AccessPolicy.id==policy.id).values(grants=permissions))
        elif change=='immutable_connection':connection.organization_id=999;native.flush()
        elif change=='provider_raw':native.connection()
        elif change=='connection_disconnected':db.connection().execute(update(StorageConnection).where(StorageConnection.id==connection_id).values(connected=False))
        return b'wrong private bytes' if change=='checksum' else cloud['remote'][ident]
    monkeypatch.setattr(providers,'download',changed)
    result=client.get(path.removesuffix('/upload')+'/download',headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==(409 if change in {'checksum','connection_disconnected'} else 403),result.text
    assert b'Actual canonical uploaded client statements' not in result.content and 'location' not in result.headers


def test_native_provider_refresh_is_exact_and_retained_without_generic_database_access(client,db,accounts,binary_task,cloud,monkeypatch):
    from datetime import datetime,timedelta,timezone
    from types import SimpleNamespace
    from app.services import file_storage_providers as providers
    from app.apps.power_apps.integrations.vault import CredentialVault
    import importlib.util
    path,data,row=source(client,accounts,binary_task[0]);post(client,accounts['preparer']['headers'],path,data)
    conn=cloud['connection'];conn.encrypted_value=CredentialVault.encrypt({'access_token':'fake-expired','refresh_token':'fake-original-refresh'});conn.expires_at=datetime.now(timezone.utc)-timedelta(hours=1);db.commit()
    # Reload the native adapter as a separate module only to retain its actual
    # authorization/refresh/download implementation; transport remains fake.
    spec=importlib.util.spec_from_file_location('isolated_native_cloud_adapter',providers.__file__);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    monkeypatch.setattr(native,'tokens',lambda *args:{'access_token':'fake-new-access','refresh_token':'fake-new-refresh','expires_in':3600})
    seen=[]
    def transport(method,url,headers,**kwargs):
        seen.append(headers['Authorization']);return SimpleNamespace(status=200,headers={},body=b'Actual canonical uploaded client statements')
    monkeypatch.setattr(native,'request',transport)
    monkeypatch.setattr(providers,'download',native.download)
    result=client.get(path.removesuffix('/upload')+'/download',headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==200,result.text
    assert result.content==b'Actual canonical uploaded client statements' and 'location' not in result.headers
    db.expire_all();stored=db.get(StorageConnection,conn.id)
    assert CredentialVault.decrypt(stored)['refresh_token']=='fake-new-refresh'
    assert seen==['Bearer fake-new-access']
    assert stored.organization_id==1 and stored.connected and stored.provider=='google_drive'


def test_unreviewed_global_cloud_backend_never_falls_back_to_unsigned_context_redirect(client,db,accounts,binary_task,monkeypatch):
    from app.core.config import settings
    from app.core import storage
    path,data,row=source(client,accounts,binary_task[0]);post(client,accounts['preparer']['headers'],path,data)
    from app.access.models import AccessPolicy
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=accounts['preparer']['user'].id).one();permissions=deepcopy(policy.grants);permissions['srm']['actions'].append('export');policy.grants=permissions;db.commit()
    monkeypatch.setattr(settings,'STORAGE_BACKEND','s3')
    def unexpected():raise AssertionError('A private Accounts download must not mint a generic cloud URL')
    monkeypatch.setattr(storage,'s3_client',unexpected)
    result=client.get(path.removesuffix('/upload')+'/download',headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==503,result.text
    assert 'location' not in result.headers


def test_cloud_download_keeps_original_native_export_ceiling(client,db,accounts,binary_task,cloud):
    from app.access.models import AccessPolicy
    path,data,row=source(client,accounts,binary_task[0]);post(client,accounts['preparer']['headers'],path,data)
    policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=accounts['preparer']['user'].id).one();permissions=deepcopy(policy.grants)
    permissions['srm']['actions']=[value for value in permissions['srm']['actions'] if value!='export'];policy.grants=permissions;policy.version+=1;db.commit()
    before=len(cloud['reads'])
    result=client.get(path.removesuffix('/upload')+'/download',headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==403,result.text
    assert len(cloud['reads'])==before and 'location' not in result.headers


def test_existing_pdf_cloud_download_is_not_archived_or_copied_again(client,db,accounts,binary_task,cloud,monkeypatch):
    import json
    from app.services import file_storage_exports
    from app.apps.project_management.models import PMSFileAsset
    path,data,row=source(client,accounts,binary_task[0]);body=b'%PDF-1.4\nActual isolated source bytes\n%%EOF'
    uploaded=client.post(path,headers=accounts['preparer']['headers'],data={'data':json.dumps(data)},files={'file':('source.pdf',body,'application/pdf')})
    assert uploaded.status_code==201,uploaded.text
    before=(db.query(PMSFileAsset).count(),db.query(StorageObject).count(),db.query(AccountsCommand).count(),len(cloud['remote']))
    archived=[]
    monkeypatch.setattr(file_storage_exports,'archive',lambda *args:archived.append(True))
    result=client.get(path.removesuffix('/upload')+'/download',headers=accounts['preparer']['headers'],follow_redirects=False)
    assert result.status_code==200 and result.content==body
    assert result.headers['content-type']=='application/pdf' and 'location' not in result.headers
    assert archived==[]
    assert before==(db.query(PMSFileAsset).count(),db.query(StorageObject).count(),db.query(AccountsCommand).count(),len(cloud['remote']))
