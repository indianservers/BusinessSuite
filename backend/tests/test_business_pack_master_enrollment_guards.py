"""Private operational identities cannot become canonical shared masters."""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.business_packs import master_sharing as sharing
from app.business_packs.master_sharing_schemas import ShareMaster
from app.business_packs.models import PackMasterAvailability, PackRecordOwnership
from app.branches.models import BranchOwnership
from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMWarehouse
from tests.test_business_pack_master_sharing import enrollment
from tests.test_business_pack_configuration import owner


@pytest.fixture(params=('employees', 'customers', 'products', 'warehouses'))
def private_master(db, enrollment, request):
    actor, branch, _, _, ctx, employee, _, product = enrollment
    kind = request.param
    if kind == 'employees':
        source = employee
    elif kind == 'products':
        source = product
    elif kind == 'customers':
        source = db.query(CRMCompany).filter_by(organization_id=1, name='Chennai customer').one()
    else:
        source = SRMWarehouse(organization_id=1, warehouse_code='PRIVATE-' + uuid4().hex[:8],
                              warehouse_name='Private operational warehouse')
        db.add(source); db.flush()
        db.add(BranchOwnership(company_id=1, branch_id=branch.id,
            resource_table=source.__tablename__, resource_key=str(source.id), source='verified-test-native-source'))
        db.commit()
    anchor = PackRecordOwnership(company_id=1, branch_id=branch.id, context_id=ctx['id'],
        resource_table=source.__tablename__, resource_key=str(source.id), source='private-operational-test-source')
    db.add(anchor); db.commit()
    return actor, ctx, kind, source, anchor


def share_input(ctx, kind, source, *, active=True, revision=0):
    return ShareMaster(kind=kind, id=source.id, active=active,
        expected_context_revision=ctx['revision'], expected_revision=revision,
        reason='Only canonical native masters may be enrolled')


def test_private_operational_master_is_neither_listed_nor_adopted(db, private_master):
    actor, ctx, kind, source, anchor = private_master
    before = db.query(PackMasterAvailability).count()
    with pytest.raises(HTTPException) as rejected:
        sharing.share_master(db, actor, ctx['id'], share_input(ctx, kind, source))
    assert rejected.value.status_code == 404
    result = sharing.master_options(db, actor, ctx['id'], kind)
    assert source.id not in {row['id'] for row in result['items']}
    assert db.query(PackMasterAvailability).count() == before
    assert db.get(type(source), source.id) is not None
    assert db.get(PackRecordOwnership, anchor.id).context_id == ctx['id']


def test_historical_private_enrollment_is_unavailable_but_revocable(db, private_master):
    actor, ctx, kind, source, anchor = private_master
    old = PackMasterAvailability(company_id=1, branch_id=anchor.branch_id, context_id=ctx['id'],
        resource_table=source.__tablename__, resource_key=str(source.id), active=True)
    db.add(old); db.commit()
    item = next(row for row in sharing.master_options(db, actor, ctx['id'], kind)['items'] if row['id'] == source.id)
    assert item['name'] == 'Unavailable master' and item['eligible'] is False and item['active'] is True
    with pytest.raises(HTTPException) as rejected:
        sharing.share_master(db, actor, ctx['id'], share_input(ctx, kind, source, revision=1))
    assert rejected.value.status_code == 404
    changed = sharing.share_master(db, actor, ctx['id'], share_input(ctx, kind, source, active=False, revision=1))
    assert changed['active'] is False
    assert db.get(PackMasterAvailability, old.id).revision == 2
    assert db.get(PackRecordOwnership, anchor.id).context_id == ctx['id']
    assert db.get(type(source), source.id) is not None
