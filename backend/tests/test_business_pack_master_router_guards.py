"""Native authenticated enrollment keeps private sources out of all four kinds."""
from datetime import date
from uuid import uuid4
import pytest
from app.core.security import create_access_token
from app.models.user import Role, Permission
from app.models.employee import Employee
from app.models.company import Company
from app.access.models import AccessPolicy
from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMProduct, SRMWarehouse
from app.branches.models import BranchOwnership
from app.business_packs.models import PackMasterAvailability
from tests.test_business_pack_master_enrollment_guards import private_master, enrollment, owner, share_input


def native_admin(db, actor):
    grants = {}
    permissions = []
    for module, name in [('hrms', 'employee_view'), ('crm', 'crm_view'), ('srm', 'srm_view')]:
        permission = db.query(Permission).filter_by(name=name).first()
        if permission is None:
            permission = Permission(name=name, module=module)
            db.add(permission); db.flush()
        permissions.append(permission)
        grants[module] = {'enabled': True, 'permissions': [name], 'actions': ['view'], 'scope': 'organization'}
    actor.role = Role(name='ms-' + uuid4().hex, permissions=permissions)
    actor.is_superuser = False
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).first()
    if policy is None:
        policy = AccessPolicy(company_id=1, user_id=actor.id, status='active', grants=grants)
        db.add(policy)
    else:
        policy.grants = grants
    db.commit()
    return {'Authorization': 'Bearer ' + create_access_token(actor.id), 'X-Suite-Organization': '1'}


def canonical_source(db, kind, branch):
    if kind == 'employees':
        source = Employee(employee_id='CANON-' + uuid4().hex[:8], first_name='Canonical', last_name='Provider',
            branch_id=branch.id, date_of_joining=date(2026, 1, 1), status='Active')
    elif kind == 'customers':
        source = CRMCompany(organization_id=1, name='Canonical customer', status='Active')
    elif kind == 'products':
        source = SRMProduct(organization_id=1, sku='CANON-' + uuid4().hex[:8], item_name='Canonical offering', product_type='service')
    else:
        source = SRMWarehouse(organization_id=1, warehouse_code='CANON-' + uuid4().hex[:8], warehouse_name='Canonical warehouse')
    db.add(source); db.flush()
    if kind in {'customers', 'warehouses'}:
        db.add(BranchOwnership(company_id=1, branch_id=branch.id, resource_table=source.__tablename__,
            resource_key=str(source.id), source='verified-test-canonical-source'))
    db.commit()
    return source


def test_actual_router_native_admin_can_enroll_only_canonical_source(client, db, private_master, enrollment):
    actor, ctx, kind, source, anchor = private_master
    branch, member = enrollment[1], enrollment[3]
    allowed = canonical_source(db, kind, branch)
    headers = {**native_admin(db, actor), 'X-Suite-Branch': str(branch.id)}
    assert not actor.is_superuser
    prefix = f'/api/v1/access/settings/business-packs/contexts/{ctx["id"]}'
    found = client.get(prefix + '/master-options', headers=headers, params={'kind': kind})
    assert found.status_code == 200, found.text
    assert source.id not in {row['id'] for row in found.json()['items']}
    assert allowed.id in {row['id'] for row in found.json()['items']}
    before = db.query(PackMasterAvailability).count()
    denied = client.put(prefix + '/masters', headers=headers,
        json=share_input(ctx, kind, source).model_dump())
    assert denied.status_code == 404, denied.text
    assert denied.json()['detail'] == 'Native master is unavailable in this company branch'
    assert db.query(PackMasterAvailability).count() == before
    peer = {**headers, 'Authorization': 'Bearer ' + create_access_token(member.id), 'X-Suite-Pack-Context': str(ctx['id'])}
    member_read = client.get(prefix + '/master-options', headers=peer, params={'kind': kind})
    assert member_read.status_code == 403, member_read.text
    assert member_read.json()['detail'] == 'Company access administrator required for Business Packs'
    enrolled = client.put(prefix + '/masters', headers=headers,
        json=share_input(ctx, kind, allowed).model_dump())
    assert enrolled.status_code == 200, enrolled.text
    assert enrolled.json()['active'] is True
    assert db.query(PackMasterAvailability).count() == before + 1


def test_actual_router_foreign_company_master_remains_unavailable(client, db, enrollment):
    actor, branch, _, _, ctx, _, _, _ = enrollment
    foreign = Company(name='Foreign protected company')
    db.add(foreign); db.flush()
    source = SRMProduct(organization_id=foreign.id, sku='FOREIGN-' + uuid4().hex[:8],
                        item_name='Foreign protected offering', product_type='service')
    db.add(source); db.commit()
    headers = {**native_admin(db, actor), 'X-Suite-Branch': str(branch.id)}
    prefix = f'/api/v1/access/settings/business-packs/contexts/{ctx["id"]}'
    result = client.get(prefix + '/master-options', headers=headers, params={'kind': 'products'})
    assert result.status_code == 200, result.text
    assert source.id not in {row['id'] for row in result.json()['items']}
    before = db.query(PackMasterAvailability).count()
    denied = client.put(prefix + '/masters', headers=headers,
        json=share_input(ctx, 'products', source).model_dump())
    assert denied.status_code == 404, denied.text
    assert db.query(PackMasterAvailability).count() == before
