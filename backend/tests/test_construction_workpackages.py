"""WBS mappings allocate approved scope over canonical existing PMS tasks."""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import update

from app.apps.project_management.models import PMSTask, PMSProject
from app.apps.srm.industry_models import IndustryRecord
from app.business_packs.models import PackRecordOwnership
from app.branches.models import BranchOwnership
from tests.test_business_pack_construction import construction, construction_approver, scenario, catalog, directory_identity

ROOT = '/api/v1/srm/industry'


def post(client, headers, path, body, status=201):
    response = client.post(ROOT + path, headers=headers, json=body)
    assert response.status_code == status, response.text
    return response.json()


@pytest.fixture
def packages(client, db, construction, construction_approver, catalog):
    actor, branch, context, project = construction
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context)}
    boq = post(client, headers, '/boq', {'request_id': str(uuid4()), 'title': 'Approved native site scope',
        'project_id': project, 'code': 'WBS-SCOPE', 'unit': 'm3', 'quantity': '10', 'unit_rate': '1200', 'tax_rate': '0'})
    post(client, construction_approver[0], f'/records/{boq["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    tasks = []
    for title in ('Native work breakdown', 'Foundation package', 'Excavation package'):
        task = PMSTask(project_id=project, task_key=uuid4().hex[:20], title=title,
            parent_task_id=tasks[0] if tasks else None)
        db.add(task); db.flush()
        tasks.append(task.id)
        db.add(PackRecordOwnership(company_id=1, branch_id=branch, context_id=context,
            resource_table=PMSTask.__tablename__, resource_key=str(task.id), source='explicit-test-enrollment'))
        if db.query(BranchOwnership).filter_by(resource_table=PMSTask.__tablename__, resource_key=str(task.id)).first() is None:
            db.add(BranchOwnership(company_id=1, branch_id=branch, resource_table=PMSTask.__tablename__, resource_key=str(task.id), source='explicit-test-enrollment'))
    db.commit()
    return {'actor': actor, 'branch': branch, 'context': context, 'project': project, 'headers': headers,
        'reviewer': construction_approver[0], 'boq': boq['id'], 'tasks': tasks}


def body(case, **values):
    return {'request_id': str(uuid4()), 'title': 'Canonical work package', 'project_id': case['project'],
        'task_id': case['tasks'][1], 'boq_id': case['boq'], 'quantity': '6', 'budget_cost': '600', **values}


def test_work_package_mapping_retry_update_and_exact_scope_ceiling(client, db, packages):
    case = packages
    original_tasks = db.query(PMSTask).count()
    data = body(case)
    mapped = post(client, case['headers'], '/work-packages', data)
    assert mapped['data']['task_id'] == case['tasks'][1]
    assert mapped['data']['parent_task_id'] == case['tasks'][0]
    assert Decimal(mapped['data']['budget_cost']) == 600
    assert mapped['data']['unit_rate'] == '1200' and mapped['data']['currency'] == 'INR'
    assert post(client, case['headers'], '/work-packages', data)['id'] == mapped['id']
    post(client, case['headers'], '/work-packages', {**data, 'quantity': '7'}, 409)
    post(client, case['headers'], '/work-packages', body(case), 409)
    post(client, case['headers'], '/work-packages', body(case, task_id=case['tasks'][2], quantity='5', budget_cost='500'), 409)
    second = post(client, case['headers'], '/work-packages', body(case, task_id=case['tasks'][2], quantity='4', budget_cost='400'))
    listing = client.get(ROOT + '/work-packages', headers=case['headers'], params={'project_id': case['project']})
    assert listing.status_code == 200 and len(listing.json()['items']) == 2, listing.text
    response = client.put(ROOT + f'/work-packages/{mapped["id"]}', headers=case['headers'],
        json={'expected_revision': 1, 'quantity': '5', 'budget_cost': '550', 'notes': 'Reviewed task allocation'})
    assert response.status_code == 200 and response.json()['revision'] == 2, response.text
    stale = client.put(ROOT + f'/work-packages/{mapped["id"]}', headers=case['headers'],
        json={'expected_revision': 1, 'quantity': '5', 'budget_cost': '550'})
    assert stale.status_code == 409, stale.text
    assert db.query(PMSTask).count() == original_tasks, 'Mapping must not create duplicate PMS task masters'
    assert Decimal(db.get(IndustryRecord, case['boq']).data['quantity']) == 10


def test_work_package_certification_cannot_exceed_its_allocation(client, db, packages):
    case = packages
    mapped = post(client, case['headers'], '/work-packages', body(case))
    measured = post(client, case['headers'], '/measurements', {'request_id': str(uuid4()), 'title': 'Allocated actual work',
        'boq_id': case['boq'], 'work_package_id': mapped['id'], 'quantity': '4', 'measured_on': '2026-11-16'})
    assert measured['data']['work_package_task_id'] == case['tasks'][1]
    post(client, case['reviewer'], f'/records/{measured["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    excess = post(client, case['headers'], '/measurements', {'request_id': str(uuid4()), 'title': 'Over-allocation',
        'boq_id': case['boq'], 'work_package_id': mapped['id'], 'quantity': '3', 'measured_on': '2026-11-16'})
    post(client, case['reviewer'], f'/records/{excess["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 409)
    reduced = client.put(ROOT + f'/work-packages/{mapped["id"]}', headers=case['headers'],
        json={'expected_revision': 1, 'quantity': '3', 'budget_cost': '300'})
    assert reduced.status_code == 409, reduced.text


@pytest.mark.parametrize('invalid', ['cycle', 'foreign_parent', 'unowned_task', 'unowned_ancestor'])
def test_mapping_rejects_invalid_native_task_hierarchy(client, db, packages, invalid):
    case = packages
    if invalid == 'cycle':
        db.connection().execute(update(PMSTask.__table__).where(PMSTask.__table__.c.id == case['tasks'][0]).values(parent_task_id=case['tasks'][1]))
    elif invalid == 'foreign_parent':
        project = PMSProject(organization_id=1, branch_id=case['branch'], project_key=uuid4().hex[:16], name='Foreign WBS')
        db.add(project); db.flush()
        db.connection().execute(update(PMSTask.__table__).where(PMSTask.__table__.c.id == case['tasks'][0]).values(project_id=project.id))
    else:
        unowned = PMSTask(project_id=case['project'], task_key=uuid4().hex[:20], title='Native task not enrolled in this pack')
        db.add(unowned); db.flush()
        if invalid == 'unowned_task':
            case['tasks'][1] = unowned.id
        else:
            db.connection().execute(update(PMSTask.__table__).where(PMSTask.__table__.c.id == case['tasks'][1]).values(parent_task_id=unowned.id))
    db.commit()
    post(client, case['headers'], '/work-packages', body(case), 409 if invalid == 'cycle' else 404)
    assert db.query(IndustryRecord).filter_by(kind='work_package').count() == 0


def test_canonical_task_reparent_requires_mapping_reconciliation(client, db, packages):
    case = packages
    mapped = post(client, case['headers'], '/work-packages', body(case))
    db.connection().execute(update(PMSTask.__table__).where(PMSTask.__table__.c.id == case['tasks'][1]).values(parent_task_id=None))
    db.commit()
    listing = client.get(ROOT + '/work-packages', headers=case['headers'], params={'project_id': case['project']})
    assert listing.status_code == 409, listing.text
    response = client.put(ROOT + f'/work-packages/{mapped["id"]}', headers=case['headers'], json={'expected_revision': 1, 'quantity': '5', 'budget_cost': '500'})
    assert response.status_code == 409, response.text


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_other_pack_role_on_same_actor_cannot_map_canonical_tasks(client, db, packages, pack, role):
    from tests.test_business_pack_http_integration import grant
    case = packages
    selected, _ = grant(db, case['actor'], case['branch'], pack, role)
    headers = {**case['headers'], 'X-Suite-Pack-Context': str(selected.id)}
    post(client, headers, '/work-packages', body(case), 403)


def test_native_project_viewer_cannot_map_scope(client, db, packages):
    from tests.test_construction_site_workflows import native_member
    case = packages
    headers, _ = native_member(db, case['branch'], case['context'], case['project'], 'Viewer')
    post(client, headers, '/work-packages', body(case), 403)


def test_mapping_requires_approved_scope_and_current_currency(client, db, packages):
    from app.apps.srm.commercial_models import ProjectCommercial
    case = packages
    draft = post(client, case['headers'], '/boq', {'request_id': str(uuid4()), 'title': 'Unapproved scope',
        'project_id': case['project'], 'code': 'NOT-APPROVED', 'unit': 'm3', 'quantity': '1', 'unit_rate': '1', 'tax_rate': '0'})
    post(client, case['headers'], '/work-packages', body(case, boq_id=draft['id']), 422)
    db.add(ProjectCommercial(project_id=case['project'], customer_id=101, seller_id=1, currency='USD'))
    db.commit()
    post(client, case['headers'], '/work-packages', body(case), 409)


def test_native_manager_module_view_only_cannot_map_scope(client, db, packages):
    from app.access.models import AccessPolicy
    from tests.test_construction_site_workflows import native_member
    case = packages
    headers, actor = native_member(db, case['branch'], case['context'], case['project'], 'Manager')
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
    policy.grants = {**policy.grants, 'project_management': {**policy.grants['project_management'], 'actions': ['view']}}
    db.commit()
    post(client, headers, '/work-packages', body(case), 403)


@pytest.mark.parametrize('invoiced', [False, True])
def test_legacy_certified_work_attribution_retains_native_financial_source(client, db, packages, invoiced):
    from copy import deepcopy
    from app.apps.srm.commercial_models import ProjectCommercial
    from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMReceiptAllocation
    from app.business_packs.models import PackMasterAvailability, PackUserGrant
    from tests.test_construction_site_workflows import native_member
    case = packages
    mapping = post(client, case['headers'], '/work-packages', body(case))
    measured = post(client, case['headers'], '/measurements', {'request_id': str(uuid4()), 'title': 'Earlier certified work',
        'boq_id': case['boq'], 'quantity': '4', 'measured_on': '2026-11-16'})
    approved = post(client, case['reviewer'], f'/records/{measured["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    certificate, invoice = None, None
    if invoiced:
        db.add(ProjectCommercial(project_id=case['project'], customer_id=101, seller_id=1, currency='INR'))
        db.add(PackMasterAvailability(company_id=1, branch_id=case['branch'], context_id=case['context'], resource_table='crm_companies', resource_key='101', active=True))
        db.commit()
        invoice = post(client, case['headers'], f'/records/{measured["id"]}/invoice', {'expected_revision': approved['revision'], 'retention_percent': '5'})
        response = client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve', headers=case['headers'])
        assert response.status_code == 200, response.text
        certificate = post(client, case['headers'], '/payment-certificates', {'request_id': str(uuid4()), 'title': 'Original financial certificate', 'measurement_id': measured['id']})
    row = db.get(IndustryRecord, measured['id'])
    original, old_revision, original_invoice = deepcopy(row.data), row.revision, row.invoice_id
    payload = {'request_id': str(uuid4()), 'expected_revision': old_revision, 'work_package_id': mapping['id'], 'reason': 'Independent reconciliation of earlier certified work'}
    path = f'/measurements/{row.id}/work-package'
    post(client, case['headers'], path, payload, 403)
    attributed = post(client, case['reviewer'], path, payload, 200)
    assert attributed['revision'] == old_revision + 1 and attributed['invoice_id'] == original_invoice
    assert post(client, case['reviewer'], path, payload, 200) == attributed
    post(client, case['reviewer'], path, {**payload, 'reason': 'Changed request details'}, 409)
    post(client, case['reviewer'], path, {**payload, 'request_id': str(uuid4())}, 409)
    db.expire_all()
    updated = db.get(IndustryRecord, row.id)
    for key, value in original.items():
        if key != 'work_package_id':
            assert updated.data[key] == value
    assert updated.data['work_package_id'] == mapping['id'] and updated.data['work_package_task_id'] == case['tasks'][1]
    if invoiced:
        # Distinct certificate retains its original source snapshot/revision.
        response = post(client, case['reviewer'], f'/delivery/{certificate["id"]}/review', {'expected_revision': 1, 'status': 'approved'}, 200)
        assert response['data']['source_snapshot'] == certificate['data']['source_snapshot']
        exported = client.get(ROOT + f'/delivery/{certificate["id"]}/export', headers=case['headers'])
        assert exported.status_code == 200, exported.text
        collector_headers, collector = native_member(db, case['branch'], case['context'], case['project'], 'Viewer')
        grant = db.query(PackUserGrant).filter_by(context_id=case['context'], user_id=collector.id).one()
        grant.role = 'billing_officer'; db.commit()
        paid = {'request_id': str(uuid4()), 'amount': '100.00', 'payment_method': 'bank_transfer', 'reference': 'Attribution preserves native collections'}
        first = post(client, collector_headers, f'/records/{row.id}/payments', paid)
        assert post(client, collector_headers, f'/records/{row.id}/payments', paid)['receipt_id'] == first['receipt_id']
        post(client, collector_headers, f'/records/{row.id}/payments', {**paid, 'request_id': str(uuid4()), 'amount': '4700.00'})
        db.expire_all()
        native_invoice = db.get(SRMInvoice, invoice['id'])
        assert native_invoice.total_amount == Decimal('4800') and native_invoice.balance_amount == 0
        assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 2


def test_legacy_attribution_late_failure_retry_and_forged_lease_denial(client, db, packages, monkeypatch):
    from fastapi import HTTPException
    from app.apps.srm import industry_api
    from app.business_packs import construction_workpackages as work
    from tests.test_srm_native_transaction_operations import native_writer
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.models.user import User
    from app.apps.project_management.models import PMSProjectMember
    case = packages
    mapping = post(client, case['headers'], '/work-packages', body(case))
    measured = post(client, case['headers'], '/measurements', {'request_id': str(uuid4()), 'title': 'Earlier work for retry',
        'boq_id': case['boq'], 'quantity': '4', 'measured_on': '2026-11-16'})
    approved = post(client, case['reviewer'], f'/records/{measured["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    payload = {'request_id': str(uuid4()), 'expected_revision': approved['revision'], 'work_package_id': mapping['id'], 'reason': 'Independent retry test'}
    path = f'/measurements/{measured["id"]}/work-package'
    original = industry_api.audit
    def fail_after_audit(db, actor, row, action):
        original(db, actor, row, action)
        if action == 'certified_work_package_attributed':
            raise RuntimeError('Late attribution audit failure')
    with monkeypatch.context() as fault:
        fault.setattr(industry_api, 'audit', fail_after_audit)
        with pytest.raises(RuntimeError, match='Late attribution audit failure'):
            post(client, case['reviewer'], path, payload, 200)
    db.expire_all()
    assert db.get(IndustryRecord, measured['id']).revision == approved['revision']
    assert db.get(IndustryRecord, measured['id']).data.get('work_package_id') is None
    post(client, case['reviewer'], path, payload, 200)
    unassigned = post(client, case['headers'], '/measurements', {'request_id': str(uuid4()), 'title': 'Unassigned work cannot borrow a caller flag',
        'boq_id': case['boq'], 'quantity': '2', 'measured_on': '2026-11-16'})
    post(client, case['reviewer'], f'/records/{unassigned["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    reviewer_id = db.query(PMSProjectMember.user_id).filter_by(project_id=case['project'], role='Manager').scalar()
    actor = db.get(User, reviewer_id)
    with native_writer(db, actor, case['branch']):
        scope = resolve_context(db, actor, db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            work.project_for_action(db, actor, case['project'])
            with pytest.raises(HTTPException) as denied:
                with db.begin_nested():
                    row = db.get(IndustryRecord, measured['id'])
                    row.data = {**row.data, 'work_package_id': None, '_work_package_attribution': None}
                    db.flush()
            assert denied.value.status_code == 403
            with pytest.raises(HTTPException) as forged:
                with db.begin_nested():
                    row = db.get(IndustryRecord, unassigned['id'])
                    row.data = {**row.data, 'work_package_id': mapping['id'], 'work_package_task_id': case['tasks'][1],
                        '_work_package_attribution': {'request_id': str(uuid4()), 'from_revision': row.revision,
                            'to_revision': row.revision + 1, 'work_package_id': mapping['id'], 'task_id': case['tasks'][1],
                            'actor_id': actor.id, 'reason': 'Caller supplied marker is not a typed command'}}
                    row.revision += 1
                    row._construction_attribution = True
                    db.flush()
            assert forged.value.status_code == 403
        finally:
            cleanup()


def test_legacy_attribution_rejects_stale_overrun_and_wrong_boq(client, db, packages):
    case = packages
    mapping = post(client, case['headers'], '/work-packages', body(case))
    measured = post(client, case['headers'], '/measurements', {'request_id': str(uuid4()), 'title': 'Earlier approved scope over one package',
        'boq_id': case['boq'], 'quantity': '7', 'measured_on': '2026-11-16'})
    approved = post(client, case['reviewer'], f'/records/{measured["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    path = f'/measurements/{measured["id"]}/work-package'
    payload = {'request_id': str(uuid4()), 'expected_revision': 1, 'work_package_id': mapping['id'], 'reason': 'Independent allocation check'}
    post(client, case['reviewer'], path, payload, 409)
    post(client, case['reviewer'], path, {**payload, 'expected_revision': approved['revision']}, 409)
    variation = post(client, case['headers'], '/boq', {'request_id': str(uuid4()), 'title': 'Distinct approved extra scope',
        'project_id': case['project'], 'code': 'ATTRIBUTION-EXTRA', 'unit': 'm3', 'quantity': '2', 'unit_rate': '1200', 'tax_rate': '0', 'variation_of': case['boq']})
    post(client, case['reviewer'], f'/records/{variation["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    other = post(client, case['headers'], '/work-packages', body(case, task_id=case['tasks'][2], boq_id=variation['id'], quantity='2', budget_cost='200'))
    post(client, case['reviewer'], path, {**payload, 'expected_revision': approved['revision'], 'work_package_id': other['id']}, 422)
    db.expire_all()
    stored = db.get(IndustryRecord, measured['id'])
    assert stored.revision == approved['revision'] and stored.data.get('work_package_id') is None


def test_legacy_attribution_native_authority_revoked_at_writer_wait(client, db, packages, monkeypatch):
    from copy import deepcopy
    from app.access.models import AccessPolicy
    from app.apps.project_management.models import PMSProjectMember
    from app.apps.srm import industry_api
    case = packages
    mapping = post(client, case['headers'], '/work-packages', body(case))
    measured = post(client, case['headers'], '/measurements', {'request_id': str(uuid4()), 'title': 'Native authority must remain current',
        'boq_id': case['boq'], 'quantity': '4', 'measured_on': '2026-11-16'})
    approved = post(client, case['reviewer'], f'/records/{measured["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    reviewer = db.query(PMSProjectMember.user_id).filter_by(project_id=case['project'], role='Manager').scalar()
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=reviewer).one()
    grants = deepcopy(policy.grants)
    grants['project_management']['actions'] = ['view']
    original, revoked = industry_api.context, []
    def revoke_after_wait(database, actor, *args, **kwargs):
        result = original(database, actor, *args, **kwargs)
        if actor.id == reviewer and not revoked:
            revoked.append(True)
            database.connection().execute(update(AccessPolicy.__table__).where(AccessPolicy.__table__.c.id == policy.id).values(grants=grants))
        return result
    with monkeypatch.context() as fault:
        fault.setattr(industry_api, 'context', revoke_after_wait)
        post(client, case['reviewer'], f'/measurements/{measured["id"]}/work-package', {
            'request_id': str(uuid4()), 'expected_revision': approved['revision'], 'work_package_id': mapping['id'], 'reason': 'Native authority fence'}, 403)
    assert revoked
    db.expire_all()
    row = db.get(IndustryRecord, measured['id'])
    assert row.revision == approved['revision'] and row.data.get('work_package_id') is None
