from datetime import date
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.business_packs import master_sharing as sharing, service
from app.business_packs.master_sharing_schemas import ShareMaster, GrantPreview
from app.business_packs.models import PackMasterAvailability, PackUserGrant
from app.access.models import AccessAudit, AccessMembership
from app.models.employee import Employee
from app.apps.srm.models import SRMProduct, SRMWarehouse
from app.apps.crm.models import CRMCompany
from app.models.company import Company
from app.branches.models import BranchOwnership, BranchLifecycle
from tests.test_business_pack_configuration import owner, context, grant_input


@pytest.fixture
def enrollment(db, owner):
    actor, branch, other, target = owner
    actor.is_superuser = True
    db.flush()
    _, ctx = context(db, actor, branch)
    employee = Employee(employee_id='PACK-SHARE', first_name='Shared', last_name='Specialist',
        branch_id=branch.id, user_id=target.id, date_of_joining=date(2026, 1, 1), status='Active')
    foreign_branch = Employee(employee_id='PACK-OTHER', first_name='Hidden', last_name='Specialist',
        branch_id=other.id, date_of_joining=date(2026, 1, 1), status='Active')
    product = SRMProduct(organization_id=1, sku='SHARE-1', item_name='Shared service', product_type='service')
    db.add_all([employee, foreign_branch, product]); db.commit()
    return actor, branch, other, target, ctx, employee, foreign_branch, product


def request(ctx, identity, **kw):
    return ShareMaster(kind='employees', id=identity, active=kw.pop('active', True),
        expected_context_revision=ctx['revision'], expected_revision=kw.pop('revision', 0), reason='Explicit reviewed master sharing', **kw)


def test_draft_master_sharing_is_explicit_revisioned_and_audited_without_native_changes(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    before_grants = db.query(PackUserGrant).count()
    before_members = [(row.user_id, row.is_admin) for row in db.query(AccessMembership)]
    options = sharing.master_options(db, actor, ctx['id'], 'employees')
    assert [row['id'] for row in options['items']] == [employee.id]
    assert set(options['items'][0]) == {'id', 'name', 'availability_id', 'availability_revision', 'active', 'eligible'}
    result = sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id))
    assert result['active'] and result['availability_revision'] == 1
    assert service.configuration(db, actor)['contexts'][0]['state'] == 'draft'
    with pytest.raises(HTTPException) as error:
        sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id))
    assert error.value.status_code == 409
    ctx['revision'] = result['context_revision']
    result = sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id, revision=1, active=False))
    assert not result['active'] and result['availability_revision'] == 2
    assert db.query(PackUserGrant).count() == before_grants
    assert [(row.user_id, row.is_admin) for row in db.query(AccessMembership)] == before_members
    assert db.query(AccessAudit).filter(AccessAudit.operation.like('settings.business-packs.master.%')).count() == 2


def test_wrong_branch_inactive_and_unrecognized_sources_are_rejected(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    with pytest.raises(HTTPException) as error:
        sharing.share_master(db, actor, ctx['id'], request(ctx, hidden.id))
    assert error.value.status_code == 404
    employee.status = 'Terminated'; db.commit()
    assert sharing.master_options(db, actor, ctx['id'], 'employees')['items'] == []
    with pytest.raises(HTTPException): sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id))
    with pytest.raises(ValidationError): ShareMaster(kind='payroll_runs', id=1, active=True, expected_context_revision=1, expected_revision=0, reason='Not a native master')


def test_user_options_and_grant_preview_share_real_validator_without_side_effects(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    users = sharing.user_options(db, actor, ctx['id'], 'Shared')
    assert users['items'] == [{'id': target.id, 'name': 'Shared Specialist'}]
    data = GrantPreview(user_id=target.id, **grant_input(ctx).model_dump())
    before = db.query(AccessAudit).count()
    result = sharing.grant_preview(db, actor, ctx['id'], data)
    assert result['allowed'] and result['after']['role'] == 'doctor' and not result['grants_native_permissions']
    assert db.query(PackUserGrant).count() == 0 and db.query(AccessAudit).count() == before
    data.role = 'chef'
    with pytest.raises(HTTPException) as error: sharing.grant_preview(db, actor, ctx['id'], data)
    assert error.value.status_code == 422


def test_pack_manager_label_is_not_company_administrator(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    actor.is_superuser = False
    db.query(AccessMembership).filter_by(user_id=actor.id, company_id=1).update({'is_admin': False}); db.commit()
    with pytest.raises(HTTPException) as error: sharing.master_options(db, actor, ctx['id'], 'products')
    assert error.value.status_code == 403


def test_catalog_branch_policy_and_warehouse_sidecar_are_authoritative(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    assert sharing.master_options(db, actor, ctx['id'], 'products')['items'][0]['id'] == product.id
    product.metadata_json = {'catalog_branches': {'default': False}}
    warehouse = SRMWarehouse(organization_id=1, warehouse_code='PACK-WH', warehouse_name='Warehouse', branch=branch.name)
    db.add(warehouse); db.commit()
    assert sharing.master_options(db, actor, ctx['id'], 'products')['items'] == []
    assert sharing.master_options(db, actor, ctx['id'], 'warehouses')['items'] == []
    db.add(BranchOwnership(company_id=1, branch_id=branch.id, resource_table=SRMWarehouse.__tablename__, resource_key=str(warehouse.id), source='test-native-source'))
    db.commit()
    assert sharing.master_options(db, actor, ctx['id'], 'warehouses')['items'][0]['name'] == 'Warehouse'
    customers = sharing.master_options(db, actor, ctx['id'], 'customers')['items']
    assert {row['name'] for row in customers} == {'Chennai customer'}


def test_stale_context_readonly_inactive_actor_and_branch_lifecycle(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    data = request(ctx, employee.id)
    data.expected_context_revision += 1
    with pytest.raises(HTTPException) as error: sharing.share_master(db, actor, ctx['id'], data)
    assert error.value.status_code == 409
    data.expected_context_revision = ctx['revision']
    db.info['security_write_request'] = False
    with pytest.raises(HTTPException) as error: sharing.share_master(db, actor, ctx['id'], data)
    assert error.value.status_code == 403
    db.info.pop('security_write_request')
    db.connection().execute(type(actor).__table__.update().where(type(actor).id == actor.id).values(is_active=False))
    with pytest.raises(HTTPException) as error: sharing.master_options(db, actor, ctx['id'], 'employees')
    assert error.value.status_code == 403
    db.connection().execute(type(actor).__table__.update().where(type(actor).id == actor.id).values(is_active=True))
    branch.is_active = False; db.commit()
    with pytest.raises(HTTPException) as error: sharing.master_options(db, actor, ctx['id'], 'employees')
    assert error.value.status_code == 404


def test_foreign_company_source_and_revoked_membership_user_are_hidden(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    foreign = Company(name='Foreign master company'); db.add(foreign); db.flush()
    secret = SRMProduct(organization_id=foreign.id, sku='FOREIGN-PACK', item_name='Hidden product')
    db.add(secret); db.commit()
    body = ShareMaster(kind='products', id=secret.id, active=True, expected_context_revision=1, expected_revision=0, reason='Reviewed selected product')
    with pytest.raises(HTTPException) as error: sharing.share_master(db, actor, ctx['id'], body)
    assert error.value.status_code == 404
    member = db.query(AccessMembership).filter_by(company_id=1, user_id=target.id).first()
    if member is None:
        member = AccessMembership(company_id=1, user_id=target.id, active=True)
        db.add(member)
    member.active = False; db.commit()
    assert target.id not in {row['id'] for row in sharing.user_options(db, actor, ctx['id'])['items']}


def test_bounded_search_finds_candidate_outside_first_hundred(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    for index in range(102):
        db.add(SRMProduct(organization_id=1, sku=f'BOUND-{index}', item_name=f'Candidate {index:03}', product_type='service'))
    db.commit()
    page = sharing.master_options(db, actor, ctx['id'], 'products')
    assert len(page['items']) == 100 and page['has_more'] is True
    result = sharing.master_options(db, actor, ctx['id'], 'products', 'Candidate 101')
    assert len(result['items']) == 1 and result['items'][0]['name'] == 'Candidate 101' and result['has_more'] is False


def test_static_control_api_validates_kind_search_and_preview_without_writes(db, enrollment):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.deps import get_db, get_current_user
    from app.business_packs.master_sharing_api import router
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    app = FastAPI(); app.include_router(router, prefix='/api/v1/access/settings')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: actor
    prefix = f'/api/v1/access/settings/business-packs/contexts/{ctx["id"]}'
    with TestClient(app) as client:
        response = client.get(prefix + '/master-options', params={'kind': 'employees'})
        assert response.status_code == 200 and response.json()['items'][0]['id'] == employee.id
        assert client.get(prefix + '/master-options', params={'kind': 'payroll_runs'}).status_code == 422
        assert client.get(prefix + '/user-options', params={'search': 'x' * 101}).status_code == 422
        preview = client.post(prefix + '/grant-preview', json=GrantPreview(user_id=target.id, **grant_input(ctx).model_dump()).model_dump())
        assert preview.status_code == 200 and preview.json()['grants_native_permissions'] is False
    assert db.query(PackUserGrant).count() == 0


def test_cached_target_user_revocation_is_fresh_for_preview_and_actual_grant(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    assert target.is_active
    db.connection().execute(type(target).__table__.update().where(type(target).id == target.id).values(is_active=False))
    before = db.query(AccessAudit).count()
    data = GrantPreview(user_id=target.id, **grant_input(ctx).model_dump())
    with pytest.raises(HTTPException) as error: sharing.grant_preview(db, actor, ctx['id'], data)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error: service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx))
    assert error.value.status_code == 409
    assert db.query(PackUserGrant).count() == 0 and db.query(AccessAudit).count() == before


def test_company_admin_does_not_implicitly_receive_hrms_source_view(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    actor.is_superuser = False; db.commit()
    with pytest.raises(HTTPException) as error: sharing.master_options(db, actor, ctx['id'], 'employees')
    assert error.value.status_code == 403
    users = sharing.user_options(db, actor, ctx['id'])['items']
    assert next(row for row in users if row['id'] == target.id)['name'] == target.email


def test_enrolled_inactive_and_moved_sources_can_be_discovered_and_unshared(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    result = sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id))
    ctx['revision'] = result['context_revision']
    employee.status = 'Terminated'; db.commit()
    item = sharing.master_options(db, actor, ctx['id'], 'employees')['items'][0]
    assert item['id'] == employee.id and item['eligible'] is False and item['active'] is True
    with pytest.raises(HTTPException) as error:
        sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id, revision=1))
    assert error.value.status_code == 404
    employee.branch_id = other.id; db.commit()
    item = sharing.master_options(db, actor, ctx['id'], 'employees')['items'][0]
    assert item['name'] == 'Unavailable master' and item['eligible'] is False
    changed = sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id, revision=1, active=False))
    assert changed['active'] is False and changed['context_revision'] == ctx['revision'] + 1
    assert employee.branch_id == other.id  # Never retag/adopt the native source.


def test_unshare_invalidates_retained_pack_scope(db, enrollment):
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import _current
    from app.branches.service import context as branch_context
    from app.business_packs.models import PackContext, PackActivation
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    parent = db.get(PackContext, ctx['id'])
    db.get(PackActivation, parent.activation_id).state = 'active'; parent.state = 'active'; db.commit()
    ctx['revision'] = parent.revision
    service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx))
    first = sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id))
    ctx['revision'] = first['context_revision']
    target.organization_id = 1
    scope = resolve_context(db, target, branch_context(db, target, 1, str(branch.id)), ctx['id'])
    _current(scope, db.connection())
    sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id, revision=1, active=False))
    with pytest.raises(HTTPException) as error: _current(scope, db.connection())
    assert error.value.status_code == 403


def test_existing_grant_to_inactive_user_can_be_explicitly_revoked(db, enrollment):
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    assigned = service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx))
    target.is_active = False; db.commit()
    data = GrantPreview(user_id=target.id, **grant_input(ctx, revision=assigned['revision'], active=False).model_dump())
    assert sharing.grant_preview(db, actor, ctx['id'], data)['after']['active'] is False
    revoked = service.grant_role(db, actor, ctx['id'], target.id, grant_input(ctx, revision=assigned['revision'], active=False))
    assert revoked['active'] is False


def test_real_draft_share_unshare_keeps_legacy_access_and_effective_profile(db, enrollment):
    from app.business_packs.access import resolve_context
    from app.business_packs.presentation import effective_profile
    from app.branches.service import context as branch_context
    from app.business_packs.models import PackContext
    actor, branch, other, target, ctx, employee, hidden, product = enrollment
    first = sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id))
    ctx['revision'] = first['context_revision']
    sharing.share_master(db, actor, ctx['id'], request(ctx, employee.id, revision=1, active=False))
    row = db.get(PackContext, ctx['id'])
    assert row.revision == 3 and row.state == 'draft' and row.ever_activated is False
    native = branch_context(db, actor, 1, str(branch.id))
    assert resolve_context(db, actor, native) is None
    assert 'packContextId' not in effective_profile(db, actor, native)
