import json
from uuid import uuid4
from pathlib import Path
import pytest
from sqlalchemy import event
from fastapi import HTTPException
from app.apps.project_management.models import PMSFileAsset, PMSActivity, PMSProjectMember
from app.models.file_storage import StorageObject
from app.business_packs.models import PackRecordOwnership
from app.branches.models import BranchOwnership
from app.business_packs.accounting_firm.models import AccountsCommand
from tests.test_accounts_periods import accounts, scenario, catalog, directory_identity, create, revision
from tests.test_accounts_actual_time import delivery
from tests.test_accounts_documents import request
from tests.test_pms_attachment_operation import attachment_source


@pytest.fixture
def binary_task(db, accounts, attachment_source):
    ident, root = attachment_source
    db.add(PackRecordOwnership(company_id=1, branch_id=accounts['branch'], context_id=accounts['context'],
        resource_table='pms_tasks', resource_key=str(ident), source='explicit-test-enrollment'))
    if db.get(BranchOwnership, ('pms_tasks', str(ident))) is None:
        db.add(BranchOwnership(company_id=1, branch_id=accounts['branch'], resource_table='pms_tasks',
            resource_key=str(ident), source='explicit-test-enrollment'))
    db.commit()
    return ident, root


def source(client, case, task):
    row = create(client, case)
    doc = request(client, case, row)
    path = f"/api/v1/srm/accounts/periods/{row['id']}/documents/{doc['document_key']}/upload"
    data = revision(row) | {'task_id':task, 'expected_document_revision':1}
    return path, data, row


def post(client, headers, path, data, content=b'Actual canonical uploaded client statements', status=201):
    response = client.post(path, headers=headers, data={'data':json.dumps(data)},
        files={'file':('statement.txt',content,'text/plain')})
    assert response.status_code == status, response.text
    return response.json()


def test_actual_canonical_binary_upload_and_exact_retry(client, db, accounts, binary_task):
    from copy import deepcopy
    from app.access.models import AccessPolicy
    policy = db.query(AccessPolicy).filter_by(company_id=1,user_id=accounts['preparer']['user'].id).one()
    grants = deepcopy(policy.grants)
    grants['srm']['actions'].append('export')
    policy.grants = grants
    db.commit()
    path, data, row = source(client, accounts, binary_task[0])
    result = post(client, accounts['preparer']['headers'], path, data)
    assert result['status'] == 'uploaded' and result['revision'] == 2
    assert post(client, accounts['preparer']['headers'], path, data) == result
    post(client, accounts['preparer']['headers'], path, data, content=b'Changed bytes', status=409)
    asset = db.query(PMSFileAsset).one()
    assert Path(asset.storage_path).read_bytes() == b'Actual canonical uploaded client statements'
    assert asset.task_id == binary_task[0] and asset.uploaded_by_user_id == accounts['preparer']['user'].id
    assert db.query(StorageObject).count() == 1
    assert db.query(PMSActivity).filter_by(action='attachment.added').count() == 1
    assert db.query(AccountsCommand).filter_by(action='document.upload').count() == 1
    for table, ident in [('pms_file_assets',asset.id), ('file_storage_objects',db.query(StorageObject).one().id)]:
        assert db.query(PackRecordOwnership).filter_by(resource_table=table,resource_key=str(ident),
            context_id=accounts['context']).count() == 1
    downloaded = client.get(path.removesuffix('/upload') + '/download',headers=accounts['preparer']['headers'])
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == b'Actual canonical uploaded client statements'
    db.query(PackRecordOwnership).filter_by(resource_table='pms_tasks',resource_key=str(binary_task[0])).delete()
    db.commit()
    denied = client.get(path.removesuffix('/upload') + '/download',headers=accounts['preparer']['headers'])
    assert denied.status_code == 404, denied.text


@pytest.mark.parametrize('fault',['foreign_task','foreign_pack','native_upload','stale','closed'])
def test_binary_upload_denials_write_no_native_assets(client, db, accounts, binary_task, fault):
    path, data, row = source(client, accounts, binary_task[0])
    headers, status = accounts['preparer']['headers'], 403
    if fault == 'foreign_task':
        db.query(PackRecordOwnership).filter_by(resource_table='pms_tasks',resource_key=str(binary_task[0])).delete()
        status = 404
    elif fault == 'foreign_pack':
        from tests.test_business_pack_http_integration import grant
        selected,_ = grant(db,accounts['preparer']['user'],accounts['branch'],'hospital','doctor')
        headers = headers | {'X-Suite-Pack-Context':str(selected.id)}
    elif fault == 'native_upload':
        db.query(PMSProjectMember).filter_by(user_id=accounts['preparer']['user'].id).one().role = 'Viewer'
    elif fault == 'stale': data['expected_document_revision'] = 999; status = 409
    else:
        from app.apps.srm.models import SRMEngagement
        db.get(SRMEngagement,accounts['engagement']).status = 'closed'
        status = 409
    db.commit()
    post(client,headers,path,data,status=status)
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0
    assert not list(binary_task[1].rglob('*.txt'))


def test_failure_after_native_upload_rolls_back_asset_activity_locator_and_certificate(client, db, accounts, binary_task):
    path, data, row = source(client, accounts, binary_task[0])
    def fail(mapper, connection, command):
        if command.action == 'document.upload':
            raise HTTPException(409,'Injected late Accounts certificate failure')
    event.listen(AccountsCommand,'before_insert',fail)
    try:
        post(client,accounts['preparer']['headers'],path,data,status=409)
    finally:
        event.remove(AccountsCommand,'before_insert',fail)
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0
    assert db.query(PMSActivity).filter_by(action='attachment.added').count() == 0
    assert db.query(AccountsCommand).filter_by(action='document.upload').count() == 0
    assert db.query(PackRecordOwnership).filter(PackRecordOwnership.resource_table.in_(
        ['pms_file_assets','file_storage_objects','pms_activities'])).count() == 0
    assert len(list(binary_task[1].rglob('*.txt'))) == 1  # native recovery staging, never falsely accepted
    post(client,accounts['preparer']['headers'],path,data)
    assert db.query(PMSFileAsset).count() == 1


def test_storage_provider_failure_rolls_back_metadata_and_retains_native_staging(client, db, accounts, binary_task, monkeypatch):
    from app.core import storage
    from app.core.config import settings
    from types import SimpleNamespace
    path, data, row = source(client, accounts, binary_task[0])
    monkeypatch.setattr(settings,'STORAGE_BACKEND','s3')
    def unavailable(*args, **kwargs):
        raise HTTPException(503,'Injected native S3 adapter failure')
    monkeypatch.setattr(storage,'s3_client',lambda:SimpleNamespace(upload_file=unavailable))
    post(client,accounts['preparer']['headers'],path,data,status=503)
    assert db.query(PMSFileAsset).count() == db.query(StorageObject).count() == 0
    assert db.query(PMSActivity).filter_by(action='attachment.added').count() == 0
    assert db.query(AccountsCommand).filter_by(action='document.upload').count() == 0
    assert len(list(binary_task[1].rglob('*.txt'))) == 1


def test_native_storage_quota_counts_other_company_files_without_exposing_them(client, db, accounts, binary_task):
    from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
    from app.access.catalog import MODULES
    from hashlib import sha256
    path, data, row = source(client, accounts, binary_task[0])
    prior = binary_task[1].parent / 'prior.bin'
    prior.write_bytes(b'x' * 1048576)
    db.add(StorageObject(organization_id=1,module='shared',relative_path='prior.bin',filename='prior.bin',
        content_type='application/octet-stream',size=1048576,sha256=sha256(prior.read_bytes()).hexdigest(),
        provider='local',status='local',versions=[]))
    plan = TenantSubscriptionPlan(code=uuid4().hex,name='Native upload quota',config_json={
        'enforce':True,'modules':list(MODULES),'storage_mib':1})
    db.add(plan);db.flush()
    subscription = db.query(TenantSubscription).filter_by(company_id=1).one_or_none()
    if subscription is None:
        subscription = TenantSubscription(company_id=1)
        db.add(subscription)
    subscription.plan_id,subscription.status,subscription.config_json = plan.id,'active',{}
    db.commit()
    post(client,accounts['preparer']['headers'],path,data,status=409)
    assert db.query(PMSFileAsset).count() == 0 and db.query(StorageObject).count() == 1
    assert db.query(AccountsCommand).filter_by(action='document.upload').count() == 0


def test_native_upload_resource_never_exposes_raw_connection_or_foreign_storage(client, db, accounts, binary_task, monkeypatch):
    from app.apps.project_management.api import router
    from sqlalchemy import select
    original = router.upload_task_attachment_operation
    def inspect_native(task, file, native, actor, **kwargs):
        for operation in (lambda:native.get_bind(),lambda:native.bind,
                lambda:native.connection().execute(select(StorageObject.__table__)),
                lambda:native.query(PMSFileAsset).all()):
            with pytest.raises(HTTPException) as error:
                operation()
            assert error.value.status_code == 403
        assert native.query(StorageObject).all() == []
        return original(task,file,native,actor,**kwargs)
    monkeypatch.setattr(router,'upload_task_attachment_operation',inspect_native)
    path,data,row = source(client,accounts,binary_task[0])
    post(client,accounts['preparer']['headers'],path,data)


@pytest.mark.parametrize('late_failure',[False,True])
def test_verified_cloud_staging_is_retained_until_actual_root_commit(client, db, accounts, binary_task, monkeypatch, late_failure):
    from app.models.file_storage import StoragePolicy,StorageConnection
    from app.services import file_storage_providers as providers
    from app.core.config import settings
    remote = {}
    connection = StorageConnection(organization_id=1,provider='google_drive',label='Isolated native storage fixture',
        connected=True,created_by=accounts['manager'].id,encrypted_value='no-live-credential')
    db.add(connection);db.flush()
    db.add(StoragePolicy(organization_id=1,enabled=True,routes={'pms':{
        'connection_id':connection.id,'folder_id':'root'}}))
    db.commit()
    monkeypatch.setattr(settings,'PMS_GOOGLE_DRIVE_REQUIRED',True)
    def provider_upload(db, conn, folder, name, content, content_type):
        ident = 'isolated-upload-' + str(len(remote)+1)
        remote[ident] = content
        return ident
    monkeypatch.setattr(providers,'upload',provider_upload)
    monkeypatch.setattr(providers,'download',lambda db,conn,ident:remote[ident])
    path,data,row = source(client,accounts,binary_task[0])
    staged_during_certificate = []
    def certificate(mapper, conn, command):
        if command.action == 'document.upload':
            staged = list(binary_task[1].rglob('*.txt'))
            assert len(staged) == 1 and staged[0].read_bytes() == b'Actual canonical uploaded client statements'
            staged_during_certificate.extend(staged)
            if late_failure:
                raise HTTPException(409,'Injected certificate failure after verified cloud upload')
    def observe_nested_commit(session):
        if session.in_nested_transaction() and staged_during_certificate:
            assert staged_during_certificate[0].is_file(), 'Native staging was deleted on savepoint release'
    event.listen(AccountsCommand,'before_insert',certificate)
    event.listen(db,'after_commit',observe_nested_commit)
    try:
        post(client,accounts['preparer']['headers'],path,data,status=409 if late_failure else 201)
    finally:
        event.remove(AccountsCommand,'before_insert',certificate)
        event.remove(db,'after_commit',observe_nested_commit)
    assert len(remote) == 1  # provider-side object is never falsely claimed to be deleted on DB rollback
    assert bool(list(binary_task[1].rglob('*.txt'))) is late_failure
    assert db.query(PMSFileAsset).count() == (0 if late_failure else 1)
    assert db.query(StorageObject).count() == (0 if late_failure else 1)
    assert db.query(AccountsCommand).filter_by(action='document.upload').count() == (0 if late_failure else 1)
