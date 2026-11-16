"""Existing Construction screen and canonical site documents through real HTTP."""
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from app.apps.project_management.models import PMSFileAsset
from app.apps.srm.industry_models import IndustryRecord
from tests.test_construction_documents import documents
from tests.test_business_pack_construction import construction, construction_approver, scenario, catalog, directory_identity


def test_existing_construction_site_screen_desktop_mobile(client, db, construction, construction_approver, catalog, monkeypatch, documents):
    from tests.test_control_browser import test_control_center_real_browser
    actor, branch, context_id, project_id = construction
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    asset = PMSFileAsset(project_id=project_id, uploaded_by_user_id=actor.id,
        file_name='site-progress.jpg', original_name='Site progress.jpg', storage_path='test-only/site-progress.jpg', visibility='Project Team')
    db.add(asset); db.commit()
    body = {'request_id': str(uuid4()), 'title': 'Independently approved foundation', 'project_id': project_id,
        'code': 'SITE', 'unit': 'm3', 'quantity': '10', 'unit_rate': '1000'}
    row = client.post('/api/v1/srm/industry/boq', headers=headers, json=body)
    assert row.status_code == 201, row.text
    approval = client.post(f'/api/v1/srm/industry/records/{row.json()["id"]}/transition',
        headers=construction_approver[0], json={'expected_revision': 1, 'status': 'approved'})
    assert approval.status_code == 200, approval.text
    identity = client.get('/api/v1/auth/me', headers=headers)
    access = client.get('/api/v1/access/me', headers=headers)
    assert identity.status_code == access.status_code == 200
    user = identity.json()
    primary = user['role'] if isinstance(user['role'], str) else (user['role'] or {}).get('name')
    user.update(role=primary, primary_role=primary, access=access.json())
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'construction-site-native.cjs')
    with tempfile.TemporaryDirectory(prefix='construction-site-browser-') as temporary:
        auth_file = Path(temporary) / 'identity.json'
        auth_file.write_text(json.dumps({'token': headers['Authorization'].split(' ', 1)[1], 'user': user,
            'branch': str(branch), 'context': str(context_id), 'project': project_id}), encoding='utf-8')
        monkeypatch.setenv('SUITE_QA_AUTH_FILE', str(auth_file))
        test_control_center_real_browser(client, db, None, headers)
    diaries = db.query(IndustryRecord).filter_by(project_id=project_id, kind='site_diary').all()
    assert len(diaries) == 2
    assert all(row.data['workforce'] == 12 and row.data['file_ids'] == [asset.id] for row in diaries)

    uploaded = db.query(PMSFileAsset).filter(PMSFileAsset.project_id == project_id, PMSFileAsset.original_name.like('Native evidence %')).all()
    assert len(uploaded) == 2
    assert all(Path(row.storage_path).read_bytes() == b'Construction native upload and download\n' for row in uploaded)
