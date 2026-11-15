"""Real Construction planning screen uses certified native source data and downloads."""
import json
import tempfile
from pathlib import Path
from uuid import uuid4
from datetime import date
from decimal import Decimal

from app.apps.project_management.models import PMSProject
from tests.test_construction_controls import controls, prepare, approve, post
from tests.test_construction_planning import site_plan, selected, construction, scenario, catalog, directory_identity
from tests.test_construction_documents import documents
from tests.test_business_pack_construction import construction_approver


def test_construction_planning_desktop_mobile_native_bytes(client, db, controls, documents, monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    case = controls
    actor, branch, context_id, project_id = case['case']
    headers = case['headers']
    baseline = prepare(client, case)
    approve(client, case, baseline)
    measured = post(client, headers, '/measurements', {'request_id': str(uuid4()),
        'title': 'Browser certified physical quantity', 'boq_id': case['boq']['id'],
        'work_package_id': case['packages'][0]['id'], 'quantity': '3', 'measured_on': date.today().isoformat()})
    post(client, case['reviewer'], f'/records/{measured["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    identity = client.get('/api/v1/auth/me', headers=headers)
    access = client.get('/api/v1/access/me', headers=headers)
    assert identity.status_code == access.status_code == 200
    user = identity.json()
    primary = user['role'] if isinstance(user['role'], str) else (user['role'] or {}).get('name')
    user.update(role=primary, primary_role=primary, access=access.json())
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'construction-planning-native.cjs')
    with tempfile.TemporaryDirectory(prefix='construction-planning-browser-') as temporary:
        auth_file = Path(temporary) / 'identity.json'
        auth_file.write_text(json.dumps({'token': headers['Authorization'].split(' ', 1)[1], 'user': user,
            'branch': str(branch), 'context': str(context_id), 'project': project_id, 'baseline': baseline['id'], 'as_of': date.today().isoformat()}), encoding='utf-8')
        monkeypatch.setenv('SUITE_QA_AUTH_FILE', str(auth_file))
        test_control_center_real_browser(client, db, None, headers)
    db.expire_all()
    assert db.get(PMSProject, project_id).estimated_cost == Decimal('1100')
