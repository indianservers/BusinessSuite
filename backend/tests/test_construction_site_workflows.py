"""Selected Construction HTTP workflows over canonical PMS/CRM sources."""
from decimal import Decimal
from uuid import uuid4

import pytest

from app.apps.project_management.models import PMSFileAsset, PMSProject, PMSProjectMember
from app.business_packs.models import PackContext, PackMasterAvailability
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity

ROOT = '/api/v1/srm/industry'


def post(client, headers, path, body, status=201):
    response = client.post(ROOT + path, headers=headers, json=body)
    assert response.status_code == status, response.text
    return response.json()


def payload(**values):
    return {'request_id': str(uuid4()), 'title': 'Site delivery', **values}


def native_member(db, branch, context_id, project_id, role):
    from app.access.models import AccessPolicy
    from tests.test_business_pack_http_integration import native_actor, grant
    headers, actor = native_actor(db, branch)
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {**policy.grants, 'project_management': {'enabled': True,
        'permissions': ['pms_view'], 'actions': ['view', 'create', 'edit', 'approve'], 'scope': 'organization'}}
    db.add(PMSProjectMember(project_id=project_id, user_id=actor.id, role=role))
    db.commit()
    grant(db, actor, branch, 'construction', 'project_manager', db.get(PackContext, context_id))
    return {**headers, 'X-Suite-Pack-Context': str(context_id)}, actor


def test_subcontract_native_manager_independent_approval_and_commitment(client, db, construction, catalog):
    from app.apps.crm.models import CRMCompany
    _, branch, context_id, project_id = construction
    creator, author = native_member(db, branch, context_id, project_id, 'Manager')
    reviewer, approver = native_member(db, branch, context_id, project_id, 'Manager')
    vendor = db.get(CRMCompany, 101)
    from app.shared.master_data_models import BusinessRelationship
    vendor.account_type = 'Customer'
    db.add(BusinessRelationship(organization_id=1, account_id=101, role='Vendor'))
    db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context_id,
        resource_table='crm_companies', resource_key='101', active=True))
    db.commit()
    body = payload(project_id=project_id, vendor_id=101, scope='Reinforcement installation', amount='12500', due_date='2026-11-30')
    row = post(client, creator, '/subcontracts', body)
    assert post(client, creator, '/subcontracts', body)['id'] == row['id']
    post(client, creator, '/subcontracts', {**body, 'amount': '12501'}, 409)
    def summary():
        response = client.get(ROOT + f'/projects/{project_id}/summary', headers=reviewer)
        assert response.status_code == 200, response.text
        return Decimal(str(response.json()['committed_subcontracts']))
    assert summary() == 0
    transition = {'expected_revision': 1, 'status': 'approved'}
    post(client, creator, f'/records/{row["id"]}/transition', transition, 403)
    approved = post(client, reviewer, f'/records/{row["id"]}/transition', transition, 200)
    assert approved['created_by'] == author.id and approved['approved_by'] == approver.id
    assert summary() == Decimal('12500')
    post(client, reviewer, f'/records/{row["id"]}/transition', transition, 409)
    # A native task lead cannot perform the native project edit action.
    lead, _ = native_member(db, branch, context_id, project_id, 'Lead')
    post(client, lead, '/subcontracts', {**body, 'request_id': str(uuid4())}, 403)


def test_diary_uses_project_files_and_rejects_foreign_deleted_private_sources(client, db, construction, catalog):
    actor, branch, context_id, project_id = construction
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    other = PMSProject(organization_id=1, branch_id=branch, name='Other site', project_key=uuid4().hex[:16], manager_user_id=actor.id)
    db.add(other); db.flush()
    from datetime import datetime, timezone
    assets = []
    for project, uploader, deleted in ((project_id, actor.id, None), (other.id, actor.id, None),
                                     (project_id, actor.id, datetime.now(timezone.utc)), (project_id, None, None)):
        asset = PMSFileAsset(project_id=project, uploaded_by_user_id=uploader,
            file_name='site.jpg', original_name='Site progress.jpg', storage_path='test-only/site.jpg',
            visibility='Work Evidence' if uploader is None else 'Project Team', deleted_at=deleted)
        db.add(asset); db.flush(); assets.append(asset.id)
    db.commit()
    body = payload(project_id=project_id, entry_date='2026-11-15', work_done='Foundation placed', workforce=12, file_ids=[assets[0]])
    row = post(client, headers, '/site-diaries', body)
    assert row['data']['workforce'] == 12 and row['data']['file_ids'] == [assets[0]]
    assert post(client, headers, '/site-diaries', body)['id'] == row['id']
    for asset, status in zip(assets[1:], (422, 422, 403)):
        post(client, headers, '/site-diaries', {**body, 'request_id': str(uuid4()), 'file_ids': [asset]}, status)
    response = client.get(ROOT + '/records', headers=headers, params={'kind': 'site_diary', 'project_id': project_id, 'include_files': True})
    assert response.status_code == 200, response.text
    assert [item['id'] for item in response.json()['project_files']] == [assets[0]]
    foreign = client.get(ROOT + '/records', headers=headers, params={'kind': 'site_diary', 'project_id': other.id, 'include_files': True})
    assert foreign.status_code == 404, foreign.text


def test_superuser_author_still_requires_independent_review_and_currency_reconciliation(client, db, construction, catalog):
    from tests.test_business_pack_construction import independent_approver
    from app.apps.srm.commercial_models import ProjectCommercial
    actor, branch, context_id, project_id = construction
    assert actor.is_superuser
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    reviewer, approver = independent_approver(db, branch, context_id, project_id)
    assert approver.id != actor.id
    commercial = ProjectCommercial(project_id=project_id, customer_id=101, seller_id=1, currency='INR')
    db.add(commercial)
    db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context_id,
        resource_table='crm_companies', resource_key='101', active=True))
    db.commit()
    def approve(row):
        change = {'expected_revision': 1, 'status': 'approved'}
        post(client, headers, f'/records/{row["id"]}/transition', change, 403)
        return post(client, reviewer, f'/records/{row["id"]}/transition', change, 200)
    boq = post(client, headers, '/boq', payload(project_id=project_id, code='CURRENCY', unit='m3', quantity='2', unit_rate='100'))
    post(client, headers, '/measurements', payload(boq_id=boq['id'], quantity='1', measured_on='2026-11-15'), 422)
    approve(boq)
    variation = post(client, headers, '/boq', payload(project_id=project_id, code='EXTRA-CURRENCY', unit='m3', quantity='1', unit_rate='120', variation_of=boq['id']))
    approve(variation)
    measurement = post(client, headers, '/measurements', payload(boq_id=boq['id'], quantity='1', measured_on='2026-11-15'))
    post(client, headers, f'/records/{measurement["id"]}/invoice', {'expected_revision': 1}, 409)
    approved = approve(measurement)
    commercial.currency = 'USD'; db.commit()
    post(client, headers, f'/records/{measurement["id"]}/invoice', {'expected_revision': approved['revision']}, 409)
    summary = client.get(ROOT + f'/projects/{project_id}/summary', headers=headers)
    assert summary.status_code == 409, summary.text
    commercial.currency = 'INR'; db.commit()
    invoice = post(client, headers, f'/records/{measurement["id"]}/invoice', {'expected_revision': approved['revision']})
    assert invoice['currency'] == 'INR' and Decimal(str(invoice['total_amount'])) == 100


def test_material_public_api_stock_cost_failure_and_retry(client, db, construction, catalog, monkeypatch):
    from app.apps.srm.models import SRMProduct, SRMInventoryMovement
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm import stock_resource
    _, branch, context_id, project_id = construction
    headers, warehouse, products = catalog
    headers = {**headers, 'X-Suite-Pack-Context': str(context_id)}
    for table, ident in (('srm_products', products[0]), ('srm_warehouses', warehouse)):
        db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context_id,
            resource_table=table, resource_key=str(ident), active=True))
    db.commit()
    body = payload(project_id=project_id, product_id=products[0], warehouse_id=warehouse,
        quantity='1.250', issue_date='2026-11-15', notes='Canonical valued material')
    original = stock_resource._write_quantity_cache
    def fail_late(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('Site issue late failure')
    before = db.query(SRMInventoryMovement).count()
    with monkeypatch.context() as fault:
        fault.setattr(stock_resource, '_write_quantity_cache', fail_late)
        with pytest.raises(RuntimeError, match='Site issue late failure'):
            post(client, headers, '/material-issues', body)
    db.expire_all()
    assert db.query(SRMInventoryMovement).count() == before
    assert db.query(IndustryRecord).filter_by(kind='material_issue').count() == 0
    assert db.get(SRMProduct, products[0]).current_quantity == Decimal('5')
    row = post(client, headers, '/material-issues', body)
    assert post(client, headers, '/material-issues', body)['id'] == row['id']
    post(client, headers, '/material-issues', {**body, 'quantity': '1.251'}, 409)
    post(client, headers, '/material-issues', {**body, 'request_id': str(uuid4()), 'quantity': '3.751'}, 409)
    db.expire_all()
    assert db.query(SRMInventoryMovement).count() == before + 1
    assert db.get(SRMProduct, products[0]).current_quantity == Decimal('3.750')
    response = client.get(ROOT + f'/projects/{project_id}/summary', headers=headers)
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()['actual_material_cost'])) == Decimal('50.00')


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_specialist_same_actor_cannot_access_site_workflows(client, db, construction, catalog, pack, role):
    from tests.test_business_pack_http_integration import grant
    actor, branch, _, project_id = construction
    context, _ = grant(db, actor, branch, pack, role)
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context.id)}
    for path, params in (('/project-options', {}), (f'/projects/{project_id}/summary', {}),
                         ('/records', {'kind': 'site_diary', 'project_id': project_id, 'include_files': True})):
        response = client.get(ROOT + path, headers=headers, params=params)
        assert response.status_code == 403, response.text
    for path, body in (
        ('/site-diaries', payload(project_id=project_id, entry_date='2026-11-15', work_done='Forbidden', workforce=1)),
        ('/subcontracts', payload(project_id=project_id, vendor_id=101, scope='Forbidden', amount='1', due_date='2026-11-30')),
        ('/material-issues', payload(project_id=project_id, product_id=catalog[2][0], warehouse_id=catalog[1], quantity='1', issue_date='2026-11-15'))):
        post(client, headers, path, body, 403)


@pytest.mark.parametrize('foreign_field', ['organization_id', 'branch_id'])
def test_context_ownership_cannot_override_native_foreign_project(client, db, construction, catalog, foreign_field):
    from sqlalchemy import update
    from app.models.company import Company, Branch
    _, _, context_id, project_id = construction
    foreign = Company(name='Foreign company') if foreign_field == 'organization_id' else Branch(company_id=1, name='Foreign branch', code='FOREIGN-SITE', is_active=True)
    db.add(foreign); db.flush()
    # Retain the old pack/branch ownership deliberately: those stamps cannot
    # authorize a canonical PMS source that now belongs elsewhere.
    db.connection().execute(update(PMSProject.__table__).where(PMSProject.__table__.c.id == project_id).values({foreign_field: foreign.id}))
    db.commit()
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    options = client.get(ROOT + '/project-options', headers=headers)
    assert options.status_code == 200 and options.json()['items'] == [], options.text
    summary = client.get(ROOT + f'/projects/{project_id}/summary', headers=headers)
    assert summary.status_code == 404, summary.text
    post(client, headers, '/boq', payload(project_id=project_id, code='FOREIGN', unit='m3', quantity='1', unit_rate='1'), 404)

