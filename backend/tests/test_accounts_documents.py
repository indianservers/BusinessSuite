from uuid import uuid4
import pytest
from app.apps.project_management.models import PMSFileAsset, PMSProjectMember
from app.business_packs.models import PackRecordOwnership
from tests.test_accounts_periods import accounts, scenario, catalog, directory_identity, create, revision, send, prepared
from tests.test_accounts_actual_time import delivery
from tests.test_srm_native_transaction_operations import native_writer


@pytest.fixture
def document(db, accounts, delivery, tmp_path):
    path = tmp_path / 'client-records.txt'
    path.write_text('Authorized client source records', encoding='utf-8')
    with native_writer(db, accounts['manager'], accounts['branch']):
        file = PMSFileAsset(project_id=delivery, uploaded_by_user_id=accounts['preparer']['user'].id,
            file_name=path.name, original_name=path.name, storage_path=str(path), size_bytes=path.stat().st_size,
            mime_type='text/plain', visibility='Internal', version_number=1)
        db.add(file); db.flush(); file_id = file.id
    db.add(PackRecordOwnership(company_id=1, branch_id=accounts['branch'], context_id=accounts['context'],
        resource_table='pms_file_assets', resource_key=str(file_id), source='explicit-test-enrollment'))
    db.commit()
    return file_id


def request(client, case, row):
    data = revision(row) | {'title': 'Bank statements', 'due_on': row['due_on']}
    result = send(client, case['preparer']['headers'], f"/{row['id']}/documents", data, status=201)
    assert send(client, case['preparer']['headers'], f"/{row['id']}/documents", data, status=201) == result
    return result


def test_document_request_checklist_and_authorized_canonical_download(client, db, accounts, delivery, document):
    from app.access.models import AccessPolicy
    from copy import deepcopy
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=accounts['preparer']['user'].id).one()
    grants = deepcopy(policy.grants)
    grants['srm']['actions'].append('export')
    policy.grants = grants
    db.commit()
    row = create(client, accounts)
    requested = request(client, accounts, row)
    path = f"/{row['id']}/documents/{requested['document_key']}"
    data = revision(row) | {'file_id': document, 'expected_document_revision': 1}
    uploaded = send(client, accounts['preparer']['headers'], path, data, method='put')
    assert uploaded['status'] == 'uploaded' and uploaded['revision'] == 2
    assert send(client, accounts['preparer']['headers'], path, data, method='put') == uploaded
    response = client.get('/api/v1/srm/accounts/periods' + path + '/download', headers=accounts['preparer']['headers'])
    assert response.status_code == 200, response.text
    assert response.content == b'Authorized client source records'
    assert 'attachment' in response.headers['content-disposition']
    submitted = prepared(client, accounts, row)
    assert submitted['state'] == 'submitted'
    send(client, accounts['preparer']['headers'], path, revision(submitted) | {
        'file_id': document, 'expected_document_revision': 2}, method='put', status=409)


def test_missing_requested_document_blocks_submission(client, db, accounts):
    row = create(client, accounts)
    request(client, accounts, row)
    row = send(client, accounts['preparer']['headers'], f"/{row['id']}/work",
        revision(row) | {'summary': 'Work requiring supporting records'}, method='put')
    send(client, accounts['preparer']['headers'], f"/{row['id']}/submit", revision(row), status=409)


@pytest.mark.parametrize('fault', ['foreign_file', 'revoked_member', 'deleted_file', 'stale_document'])
def test_unauthorized_or_stale_document_never_becomes_uploaded(client, db, accounts, delivery, document, fault):
    row = create(client, accounts)
    requested = request(client, accounts, row)
    file_id, status = document, 404
    if fault == 'foreign_file': file_id = 999999
    elif fault == 'revoked_member':
        db.query(PMSProjectMember).filter_by(project_id=delivery, user_id=accounts['preparer']['user'].id).delete()
        asset = db.get(PMSFileAsset, document)
        asset.visibility = 'Work Evidence'
        asset.uploaded_by_user_id = accounts['manager'].id
        status = 403
    elif fault == 'deleted_file':
        db.query(PackRecordOwnership).filter_by(resource_table='pms_file_assets', resource_key=str(document)).delete()
    else: status = 409
    db.commit()
    send(client, accounts['preparer']['headers'], f"/{row['id']}/documents/{requested['document_key']}",
        revision(row) | {'file_id': file_id, 'expected_document_revision': 999 if fault == 'stale_document' else 1},
        method='put', status=status)
