"""Native company/invoice locks preserve certified measurement collections."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from tests.test_pms_workflow_postgresql import live, race
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity, independent_approver
from tests.test_business_pack_http_integration import native_actor, grant
from tests.srm_test_utils import seed_invoice_parties
from app.access.models import AccessPolicy
from app.apps.project_management.models import PMSProject, PMSProjectMember
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMReceiptAllocation, SRMRevenueEvent
from app.apps.srm.commercial_models import ProjectCommercial
from app.branches.models import BranchOwnership
from app.business_packs.models import PackContext, PackMasterAvailability, PackRecordOwnership, PackUserGrant

BASE = '/api/v1/srm/industry'


def prepare(client, db, creator_headers, branch, context_id, project_id, approver_headers=None):
    seed_invoice_parties(db)
    db.add(ProjectCommercial(project_id=project_id, customer_id=101, seller_id=1, currency='INR'))
    db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context_id,
        resource_table='crm_companies', resource_key='101', active=True))
    headers, collector = native_actor(db, branch)
    assert not collector.is_superuser
    grant(db, collector, branch, 'construction', 'billing_officer', db.get(PackContext, context_id))
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=collector.id).one()
    # Explicit project membership supplies native browse authority; no global
    # pms_view/manage privilege may mask its later revocation.
    policy.grants = {**policy.grants, 'project_management': {
        'enabled': True, 'permissions': [], 'actions': ['view'], 'scope': 'own'}}
    member = PMSProjectMember(project_id=project_id, user_id=collector.id, role='Viewer')
    db.add(member); db.commit()
    collector_id, membership_id, policy_id = collector.id, member.id, policy.id
    creator_headers = {**creator_headers, 'X-Suite-Branch': str(branch), 'X-Suite-Pack-Context': str(context_id)}
    if approver_headers is None:
        approver_headers, _ = independent_approver(db, branch, context_id, project_id)
    approver_headers = {**approver_headers, 'X-Suite-Branch': str(branch), 'X-Suite-Pack-Context': str(context_id)}
    headers = {**headers, 'X-Suite-Pack-Context': str(context_id)}
    def post(path, body, auth=creator_headers, status=201):
        response = client.post(BASE+path, headers=auth, json=body)
        assert response.status_code == status, response.text
        return response.json()
    boq = post('/boq', {'request_id':str(uuid4()), 'title':'Native race certified scope', 'project_id':project_id,
        'code':'RACE', 'unit':'m3', 'quantity':'10', 'unit_rate':'1000', 'tax_rate':'18'})
    post(f'/records/{boq["id"]}/transition', {'expected_revision':1, 'status':'approved'}, auth=approver_headers, status=200)
    measured = post('/measurements', {'request_id':str(uuid4()), 'title':'Native race actual measurement',
        'boq_id':boq['id'], 'quantity':'6', 'measured_on':'2026-11-15'})
    approved = post(f'/records/{measured["id"]}/transition', {'expected_revision':1,'status':'approved'}, auth=approver_headers, status=200)
    invoice = post(f'/records/{measured["id"]}/invoice', {'expected_revision':approved['revision'],
        'retention_percent':'5'}, auth=headers)
    response = client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve', headers=headers)
    assert response.status_code == 200, response.text
    return SimpleNamespace(headers=headers, actor_id=collector_id, member_id=membership_id,
        policy_id=policy_id, context_id=context_id, project_id=project_id, invoice_id=invoice['id'],
        path=BASE+f'/records/{measured["id"]}/payments')


def complete_native_setup(client, db, branch):
    creator_headers, creator = native_actor(db, branch)
    reviewer_headers, reviewer = native_actor(db, branch)
    assert not creator.is_superuser and not reviewer.is_superuser and creator.id != reviewer.id
    for actor in (creator, reviewer):
        policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one()
        policy.grants = {**policy.grants, 'project_management': {'enabled':True,
            'permissions':['pms_view','pms_manage_projects','pms_manage_tasks'],
            'actions':['view','create','edit','approve'], 'scope':'organization'}}
    db.commit()
    context, _ = grant(db, creator, branch, 'construction', 'project_manager')
    grant(db, reviewer, branch, 'construction', 'project_manager', context)
    project = PMSProject(organization_id=1, branch_id=branch, name='Native certified race site',
        project_key='R'+uuid4().hex[:14], manager_user_id=creator.id)
    db.add(project); db.flush()
    db.add(PMSProjectMember(project_id=project.id, user_id=reviewer.id, role='Manager'))
    db.add(BranchOwnership(company_id=1, branch_id=branch, resource_table='pms_projects',
        resource_key=str(project.id), source='explicit-test-enrollment'))
    db.add(PackRecordOwnership(company_id=1, branch_id=branch, context_id=context.id,
        resource_table='pms_projects', resource_key=str(project.id), source='explicit-test-enrollment'))
    db.commit()
    return prepare(client, db, creator_headers, branch, context.id, project.id, reviewer_headers)


def prepared(live):
    with live.factory() as db:
        owner = db.query(BranchOwnership).filter_by(company_id=1, resource_table='pms_projects',
            resource_key=str(live.pid)).one()
        return complete_native_setup(live.client, db, owner.branch_id)

def body():
    return {'request_id':str(uuid4()), 'amount':'7080.00', 'payment_method':'bank_transfer',
            'reference':'Native race certified work payment'}


def assert_money(db, case, *, collected):
    invoice = db.get(SRMInvoice, case.invoice_id)
    assert invoice.total_amount == Decimal('7080.00')
    assert invoice.paid_amount == (Decimal('7080.00') if collected else 0)
    assert invoice.balance_amount == (0 if collected else Decimal('7080.00'))
    assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == int(collected)
    events = db.query(SRMRevenueEvent).filter_by(invoice_id=case.invoice_id, event_type='cash_collected').all()
    assert sum((row.amount for row in events), Decimal(0)) == (Decimal('7080.00') if collected else 0)


def test_membership_only_native_collector_precondition(client, db, construction, catalog):
    _, branch, context_id, project_id = construction
    case = prepare(client, db, catalog[0], branch, context_id, project_id)
    response = client.post(case.path, headers=case.headers, json=body())
    assert response.status_code == 201, response.text
    db.expire_all(); assert_money(db, case, collected=True)


def test_exact_race_actor_factory_and_full_http_prerequisite(client, db, scenario):
    case = complete_native_setup(client, db, scenario[1])
    response = client.post(case.path, headers=case.headers, json=body())
    assert response.status_code == 201, response.text
    db.expire_all(); assert_money(db, case, collected=True)


@pytest.mark.parametrize('same_key', [False, True])
def test_last_certified_balance_cannot_be_collected_twice(live, same_key):
    case = prepared(live)
    first = body(); second = first if same_key else body()
    results = race(lambda:live.client.post(case.path, headers=case.headers, json=first),
                   lambda:live.client.post(case.path, headers=case.headers, json=second))
    assert sorted(row.status_code for row in results) == ([201,201] if same_key else [201,422]), [row.text for row in results]
    if same_key:
        assert results[0].json()['receipt_id'] == results[1].json()['receipt_id']
    with live.factory() as db:
        assert_money(db, case, collected=True)


@pytest.mark.parametrize('revocation', ['native_approve', 'pack_grant', 'project_membership'])
def test_collection_authority_revoked_during_company_writer_wait(live, monkeypatch, revocation):
    from app.apps.srm.services import commercial
    from app.core.company_writer import lock_company_writer
    case = prepared(live)
    original, waiting = commercial.lock_tenant, Event()
    def observed(db, actor):
        if actor.id == case.actor_id:
            waiting.set()
        return original(db, actor)
    monkeypatch.setattr(commercial, 'lock_tenant', observed)
    with live.factory() as blocker:
        lock_company_writer(blocker, 1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(lambda:live.client.post(case.path, headers=case.headers, json=body()))
            assert waiting.wait(timeout=20), 'Collection did not reach company writer lock'
            if revocation == 'native_approve':
                table = AccessPolicy.__table__
                grants = blocker.connection().scalar(select(table.c.grants).where(table.c.id == case.policy_id))
                grants = {**grants, 'srm':{**grants['srm'], 'actions':['view','create','edit']}}
                blocker.connection().execute(table.update().where(table.c.id == case.policy_id)
                    .values(grants=grants, version=table.c.version+1))
            elif revocation == 'pack_grant':
                table = PackUserGrant.__table__
                blocker.connection().execute(table.update().where(table.c.context_id == case.context_id,
                    table.c.user_id == case.actor_id).values(active=False, revision=table.c.revision+1))
            else:
                table = PMSProjectMember.__table__
                blocker.connection().execute(table.delete().where(table.c.id == case.member_id))
            blocker.commit()
            response = future.result(timeout=40)
            assert response.status_code in {403,404}, response.text
    with live.factory() as db:
        assert_money(db, case, collected=False)
