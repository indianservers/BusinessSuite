"""Original production invoice screen against real native HTTP and owned test DB."""
import json
import tempfile
from pathlib import Path
from decimal import Decimal
from uuid import uuid4

from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMReceiptAllocation, SRMInventoryMovement
from app.apps.srm.commercial_models import ProjectCommercial
from app.apps.project_management.models import PMSProjectMember
from app.access.models import AccessPolicy
from app.business_packs.models import PackContext, PackMasterAvailability
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity
from tests.test_business_pack_http_integration import grant


def test_actual_app_construction_invoice_collection_only_actor(client, db, construction, catalog, monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    actor, branch, context_id, project_id = construction
    db.add(ProjectCommercial(project_id=project_id, customer_id=101, seller_id=1, currency='INR', updated_by=actor.id))
    db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context_id,
        resource_table='crm_companies', resource_key='101', active=True))
    db.commit()
    manager = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    root = '/api/v1/srm/industry'
    def post(path, data, expected=201):
        response = client.post(root + path, headers=manager, json=data)
        assert response.status_code == expected, response.text
        return response.json()
    boq = post('/boq', {'request_id': str(uuid4()), 'title': 'Browser certified work', 'project_id': project_id,
        'code': 'BROWSER', 'unit': 'm3', 'quantity': '10', 'unit_rate': '1000', 'tax_rate': '18'})
    post(f'/records/{boq["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    measured = post('/measurements', {'request_id': str(uuid4()), 'title': 'Browser measured work',
        'boq_id': boq['id'], 'quantity': '6', 'measured_on': '2026-11-15'})
    measured = post(f'/records/{measured["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    invoice = post(f'/records/{measured["id"]}/invoice', {'expected_revision': measured['revision'], 'retention_percent': '5'})
    issued = client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve', headers=manager)
    assert issued.status_code == 200, issued.text
    from tests.test_settings_hub import actor as create_actor
    from app.branches.models import BranchGrant
    permissions = ['srm_invoice_view', 'srm_collection_view', 'srm_collection_create']
    headers, collector = create_actor(db, role='collector-'+uuid4().hex, permissions=[*permissions, 'pms_view'])
    collector.organization_id = 1
    db.add(BranchGrant(company_id=1, branch_id=branch, user_id=collector.id, can_write=True))
    db.add(AccessPolicy(company_id=1, user_id=collector.id, status='active', grants={
        'srm': {'enabled': True, 'permissions': permissions, 'actions': ['view', 'create', 'approve'], 'scope': 'organization'},
        'project_management': {'enabled': True, 'permissions': ['pms_view'], 'actions': ['view'], 'scope': 'organization'}}))
    db.add(PMSProjectMember(project_id=project_id, user_id=collector.id, role='Viewer'))
    db.commit()
    grant(db, collector, branch, 'construction', 'billing_officer', db.get(PackContext, context_id))
    headers = {**headers, 'X-Suite-Branch': str(branch), 'X-Suite-Pack-Context': str(context_id)}
    detail = client.get(f'/api/v1/srm/business/invoices/{invoice["id"]}', headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()['can_issue'] is False and detail.json()['can_edit'] is False
    assert detail.json()['can_record_payment'] is True
    forbidden_issue = client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve', headers=headers)
    assert forbidden_issue.status_code == 403, forbidden_issue.text
    identity = client.get('/api/v1/auth/me', headers=headers)
    access = client.get('/api/v1/access/me', headers=headers)
    assert identity.status_code == access.status_code == 200, (identity.text, access.text)
    user = identity.json()
    primary = user['role'] if isinstance(user['role'], str) else (user['role'] or {}).get('name')
    user.update(role=primary, primary_role=primary, access=access.json())
    before = db.query(SRMInventoryMovement).count()
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'construction-invoice-native.cjs')
    with tempfile.TemporaryDirectory(prefix='construction-native-auth-') as temporary:
        auth_file = Path(temporary) / 'identity.json'
        auth_file.write_text(json.dumps({'token': headers['Authorization'].split(' ', 1)[1], 'user': user,
            'branch': str(branch), 'context': str(context_id), 'invoice': invoice['id'],
            'invoice_number': invoice['invoice_number'], 'measurement': measured['id']}), encoding='utf-8')
        monkeypatch.setenv('SUITE_QA_AUTH_FILE', str(auth_file))
        test_control_center_real_browser(client, db, None, manager)
    assert db.query(SRMInvoice).one().paid_amount == Decimal('7080.00')
    assert db.query(SRMInvoice).one().balance_amount == 0
    assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 2
    assert db.query(SRMInventoryMovement).count() == before
