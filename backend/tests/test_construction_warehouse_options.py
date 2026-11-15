from uuid import uuid4
import pytest
from app.apps.srm.models import SRMWarehouse, SRMInventoryMovement
from app.business_packs.models import PackMasterAvailability, PackRecordOwnership, PackUserGrant
from app.branches.models import BranchOwnership
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity

PATH='/api/v1/srm/industry/material-warehouse-options'

@pytest.fixture
def selected(db, construction, catalog):
    actor, branch, context, _ = construction
    _, warehouse, _ = catalog
    from tests.test_business_pack_http_integration import native_actor,grant
    from app.business_packs.models import PackContext
    headers,actor=native_actor(db,branch,actions=('view',))
    grant(db,actor,branch,'construction','project_manager',db.get(PackContext,context))
    db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context,
        resource_table='srm_warehouses', resource_key=str(warehouse), active=True))
    db.commit()
    return actor, branch, context, warehouse, {**headers, 'X-Suite-Pack-Context':str(context)}

def test_actual_selector_returns_only_canonical_id_and_name(client,db,selected):
    _,_,_,warehouse,headers=selected
    before=db.query(SRMInventoryMovement).count()
    response=client.get(PATH,headers=headers)
    assert response.status_code==200,response.text
    assert response.json()=={'items':[{'id':warehouse,'name':db.get(SRMWarehouse,warehouse).warehouse_name}],'has_more':False}
    assert db.query(SRMInventoryMovement).count()==before
    assert client.get('/api/v1/srm/inventory/warehouses',headers=headers).status_code==503

@pytest.mark.parametrize('fault',['inactive','unenrolled','revoked','foreignbranch','foreigncompany','privateown','privateforeign'])
def test_unavailable_and_private_operational_warehouses_never_become_options(client,db,selected,fault):
    _,branch,context,warehouse,headers=selected
    a=db.query(PackMasterAvailability).filter_by(context_id=context,resource_table='srm_warehouses').one()
    if fault=='inactive': db.get(SRMWarehouse,warehouse).active=False
    elif fault=='unenrolled': db.delete(a)
    elif fault=='revoked': a.active=False
    elif fault in {'foreignbranch','foreigncompany'}:
        from app.models.company import Company,Branch
        company=Company(name='Other company '+uuid4().hex);db.add(company);db.flush()
        other=Branch(company_id=company.id,name='Foreign source',code=uuid4().hex[:12]);db.add(other);db.flush()
        b=db.query(BranchOwnership).filter_by(resource_table='srm_warehouses',resource_key=str(warehouse)).one()
        if fault=='foreigncompany': db.get(SRMWarehouse,warehouse).organization_id=company.id
        else:b.company_id=company.id;b.branch_id=other.id
    else:
        if fault=='privateforeign':
            from tests.test_business_pack_http_integration import grant
            other,_=grant(db,selected[0],branch,'hospital','doctor');context=other.id
        db.add(PackRecordOwnership(company_id=1,branch_id=branch,context_id=context,
            resource_table='srm_warehouses',resource_key=str(warehouse),source='explicit-test-private'))
    db.commit()
    response=client.get(PATH,headers=headers)
    assert response.status_code==200,response.text
    assert response.json()=={'items':[],'has_more':False}

@pytest.mark.parametrize('pack,role',[('hospital','doctor'),('restaurant','chef'),('construction','billing_officer')])
def test_other_roles_and_foreign_contexts_do_not_gain_warehouse_inventory(client,db,selected,pack,role):
    from tests.test_business_pack_http_integration import grant
    actor,branch,current,_,headers=selected
    if pack=='construction':
        row=db.query(PackUserGrant).filter_by(context_id=current,user_id=actor.id).one();row.role=role;row.revision+=1;db.commit()
        from app.business_packs.models import PackContext
        other=db.get(PackContext,current)
    else:other,_=grant(db,actor,branch,pack,role)
    response=client.get(PATH,headers={**headers,'X-Suite-Pack-Context':str(other.id)})
    assert response.status_code==403,response.text
    assert 'warehouse_name' not in response.text

@pytest.mark.parametrize('fault',['packrevoked','nativeviewrevoked'])
def test_fresh_native_and_context_revocation_is_denied(client,db,selected,fault):
    actor,_,context,_,headers=selected
    assert client.get(PATH,headers=headers).status_code==200
    if fault=='packrevoked':db.query(PackUserGrant).filter_by(context_id=context,user_id=actor.id).one().active=False
    else:
        from app.access.models import AccessPolicy
        policy=db.query(AccessPolicy).filter_by(company_id=1,user_id=actor.id).one_or_none()
        if policy is None:
            policy=AccessPolicy(company_id=1,user_id=actor.id,status='active',grants={});db.add(policy)
        else:policy.grants={}
    db.commit()
    response=client.get(PATH,headers=headers)
    assert response.status_code==403,response.text

@pytest.mark.parametrize('query',['?offset=-1','?offset=100001','?search='+('x'*181)])
def test_selector_validation_is_native_http(client,selected,query):
    assert client.get(PATH+query,headers=selected[-1]).status_code==422

def test_sql_paging_and_literal_search_do_not_enumerate_warehouse_bodies(client,db,selected):
    actor,branch,context,_,headers=selected
    for n in range(53):
        row=SRMWarehouse(organization_id=1,warehouse_code=uuid4().hex[:20],warehouse_name=f'Filtered {n:03}',active=True,created_by=actor.id)
        db.add(row);db.flush()
        if not db.query(BranchOwnership).filter_by(resource_table='srm_warehouses',resource_key=str(row.id)).first():
            db.add(BranchOwnership(company_id=1,branch_id=branch,resource_table='srm_warehouses',resource_key=str(row.id),source='test-native'))
        db.add(PackMasterAvailability(company_id=1,branch_id=branch,context_id=context,resource_table='srm_warehouses',resource_key=str(row.id),active=True))
    db.commit()
    first=client.get(PATH,params={'search':'Filtered'},headers=headers);assert first.status_code==200,first.text
    assert len(first.json()['items'])==50 and first.json()['has_more'] is True
    second=client.get(PATH,params={'search':'Filtered','offset':50},headers=headers)
    assert second.status_code==200 and len(second.json()['items'])==3 and second.json()['has_more'] is False
    assert not {x['id'] for x in first.json()['items']} & {x['id'] for x in second.json()['items']}
    literal=client.get(PATH,params={'search':'%'},headers=headers)
    assert literal.status_code==200 and literal.json()['items']==[]
