"""Initial canonical PMS commercial setup remains native and freezes at pricing."""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import update

from app.apps.srm.commercial_models import ProjectCommercial
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMAuditLog, SRMInvoice
from app.business_packs.models import PackMasterAvailability
from tests.test_business_pack_construction import construction, construction_approver, scenario, catalog, directory_identity
from tests.test_construction_definition import definition, project_body

ROOT = '/api/v1/srm/industry'


@pytest.fixture
def commercial(db, construction, construction_approver, catalog):
    actor, branch, context, project = construction
    db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context,
        resource_table='crm_companies', resource_key='101', active=True))
    db.commit()
    return {'actor': actor, 'branch': branch, 'context': context, 'project': project,
        'headers': {**catalog[0], 'X-Suite-Pack-Context': str(context)}, 'reviewer': construction_approver[0]}


def link(client, case, body=None, status=200, headers=None):
    response = client.post(ROOT + f'/projects/{case["project"]}/commercial-source', headers=headers or case['headers'],
        json=body or {'request_id': str(uuid4()), 'customer_id': 101, 'currency': 'INR'})
    assert response.status_code == status, response.text
    return response.json()


def post(client, case, path, body, status=201, review=False):
    response = client.post(ROOT + path, headers=case['reviewer'] if review else case['headers'], json=body)
    assert response.status_code == status, response.text
    return response.json()


def test_native_commercial_link_then_boq_certified_invoice_without_duplicate_master(client, db, commercial, definition, construction_approver):
    from app.apps.crm.models import CRMCompany
    from app.apps.project_management.models import PMSProjectMember, PMSWorkspaceMember
    case = commercial
    created = post(client, case, '/site-projects', project_body(definition))
    case['project'] = created['id']
    db.add(PMSProjectMember(project_id=created['id'], user_id=construction_approver[1].id, role='Manager'))
    db.add(PMSWorkspaceMember(workspace_id=definition['workspace'], user_id=construction_approver[1].id, role='Admin'))
    db.commit()
    companies = db.query(CRMCompany).count()
    body = {'request_id': str(uuid4()), 'customer_id': 101, 'currency': 'INR'}
    result = link(client, case, body)
    assert result['customer_id'] == 101 and result['seller_id'] == 1 and result['currency'] == 'INR'
    assert link(client, case, body) == result
    assert db.query(ProjectCommercial).count() == 1
    assert db.query(SRMAuditLog).filter_by(action='commercial_linked').count() == 1
    link(client, case, {**body, 'currency': 'USD'}, 409)
    boq = post(client, case, '/boq', {'request_id': str(uuid4()), 'title': 'Site scope after commercial setup', 'project_id': case['project'],
        'code': 'COMMERCIAL', 'unit': 'm3', 'quantity': '2', 'unit_rate': '1000', 'tax_rate': '18'})
    post(client, case, f'/records/{boq["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200, review=True)
    measured = post(client, case, '/measurements', {'request_id': str(uuid4()), 'title': 'Certified commercial-source work', 'boq_id': boq['id'], 'quantity': '2', 'measured_on': '2026-11-16'})
    approved = post(client, case, f'/records/{measured["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200, review=True)
    invoice = post(client, case, f'/records/{measured["id"]}/invoice', {'expected_revision': approved['revision'], 'retention_percent': '5'})
    assert Decimal(str(invoice['total_amount'])) == Decimal('2360.00')
    assert db.query(SRMInvoice).count() == 1 and db.query(CRMCompany).count() == companies
    link(client, case, {**body, 'request_id': str(uuid4()), 'currency': 'USD'}, 409)
    assert link(client, case, body) == result


def test_even_draft_boq_prevents_initial_or_changed_identity(client, db, commercial):
    case = commercial
    post(client, case, '/boq', {'request_id': str(uuid4()), 'title': 'Already priced draft', 'project_id': case['project'],
        'code': 'DRAFT-PRICED', 'unit': 'm3', 'quantity': '1', 'unit_rate': '1', 'tax_rate': '0'})
    link(client, case, status=409)
    assert db.query(ProjectCommercial).count() == 0


def test_advanced_native_links_are_preserved_without_default_clearing(client, db, commercial):
    from app.apps.crm.models import CRMTeam
    case = commercial
    team = CRMTeam(organization_id=1, name='Existing native team', status='Active')
    db.add(team); db.flush()
    db.add(ProjectCommercial(project_id=case['project'], customer_id=101, seller_id=1, currency='INR', team_id=team.id))
    db.commit()
    result = link(client, case)
    assert result['has_advanced_links'] is True
    assert db.get(ProjectCommercial, case['project']).team_id == team.id
    link(client, case, {'request_id': str(uuid4()), 'customer_id': 101, 'currency': 'USD'}, 409)
    assert db.get(ProjectCommercial, case['project']).currency == 'INR'


def test_foreign_unavailable_customers_and_native_viewer_denied(client, db, commercial):
    from app.apps.crm.models import CRMCompany
    from tests.test_construction_site_workflows import native_member
    case = commercial
    foreign = CRMCompany(organization_id=2, name='Foreign customer', account_type='Customer')
    db.add(foreign); db.commit()
    link(client, case, {'request_id': str(uuid4()), 'customer_id': foreign.id, 'currency': 'INR'}, 404)
    availability = db.query(PackMasterAvailability).filter_by(context_id=case['context'], resource_table='crm_companies', resource_key='101').one()
    availability.active = False; db.commit()
    link(client, case, status=404)
    availability.active = True; db.commit()
    headers, _ = native_member(db, case['branch'], case['context'], case['project'], 'Viewer')
    link(client, case, headers=headers, status=403)
    assert db.query(ProjectCommercial).count() == 0


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_same_actor_other_pack_cannot_link_or_read_construction_commercial(client, db, commercial, pack, role):
    from tests.test_business_pack_http_integration import grant
    case = commercial
    selected, _ = grant(db, case['actor'], case['branch'], pack, role)
    headers = {**case['headers'], 'X-Suite-Pack-Context': str(selected.id)}
    link(client, case, headers=headers, status=403)
    response = client.get(ROOT + f'/projects/{case["project"]}/commercial-source', headers=headers)
    assert response.status_code == 403, response.text


def test_native_link_late_failure_rolls_back_link_audit_and_provenance_then_retry(client, db, commercial, monkeypatch):
    from app.business_packs import construction_commercial as source
    case = commercial
    original = source._native
    def fail_after_native(command):
        original(command)
        raise RuntimeError('Commercial link late failure')
    body = {'request_id': str(uuid4()), 'customer_id': 101, 'currency': 'INR'}
    with monkeypatch.context() as fault:
        fault.setattr(source, '_native', fail_after_native)
        with pytest.raises(RuntimeError, match='Commercial link late failure'):
            link(client, case, body)
    assert db.query(ProjectCommercial).count() == 0
    assert db.query(SRMAuditLog).filter_by(action='commercial_linked').count() == 0
    assert db.query(IndustryRecord).filter_by(kind='commercial_link').count() == 0
    link(client, case, body)
    assert db.query(ProjectCommercial).count() == 1
