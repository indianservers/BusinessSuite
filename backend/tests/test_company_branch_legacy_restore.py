"""Legacy company definition PUT must preserve authorized branch recovery."""
from uuid import uuid4
import pytest
from app.branches.models import BranchGrant,BranchPolicy,BranchLifecycle
from app.models.company import Branch
from tests.test_settings_hub import actor


def setup_recovery(client,db,superuser_headers,delegated,*,native_trash=False):
    branches=[]
    for index in range(2):
        response=client.post('/api/v1/company/branches/',headers=superuser_headers,json={'company_id':1,'name':'Legacy restore '+uuid4().hex,'code':'REC-'+uuid4().hex[:10]})
        assert response.status_code==201,response.text
        branches.append(response.json()['id'])
    target,other=branches
    headers=superuser_headers
    if delegated:
        native={'enabled':True,'role':'Native company branch writer','permissions':['company_manage'],'actions':['view','configure'],'scope':'organization'}
        headers,user=actor(db,role='legacy-recovery-'+uuid4().hex,permissions=['company_manage'],grants={'hrms':native})
        db.add(BranchPolicy(company_id=1,user_id=user.id,use_home_branch=False,manage_access=True))
        for branch in branches:
            db.add(BranchGrant(company_id=1,user_id=user.id,branch_id=branch,can_write=True,module_grants={'hrms':native}))
        db.commit()
    headers={**headers,'X-Suite-Branch':str(other)}
    response=(client.post('/api/v1/branches/'+str(target)+'/trash',headers=headers,json={'reason':'Authorized native trash proof','expected_version':0}) if native_trash else
        client.put('/api/v1/company/branches/'+str(target),headers=headers,json={'is_active':False}))
    assert response.status_code==200,response.text
    db.expire_all()
    assert db.get(Branch,target).is_active is False
    assert db.get(BranchLifecycle,target).deleted_at is not None
    response=client.get('/api/v1/branches/manage',headers=headers)
    assert response.status_code==200,response.text
    managed=next(row for row in response.json()['branches'] if row['id']==target)
    assert managed['can_manage'] is True and managed['state']=='trash'
    return target,headers


@pytest.mark.parametrize('delegated',[False,True],ids=['superuser','delegated_configurer'])
def test_legacy_company_put_can_trash_and_restore_its_authorized_target(client,db,superuser_headers,delegated):
    target,headers=setup_recovery(client,db,superuser_headers,delegated)
    restored=client.put('/api/v1/company/branches/'+str(target),headers=headers,json={'is_active':True})
    assert restored.status_code==200,restored.text
    db.expire_all()
    assert db.get(Branch,target).is_active is True and db.get(BranchLifecycle,target).deleted_at is None


@pytest.mark.parametrize('delegated',[False,True],ids=['superuser','delegated_configurer'])
def test_standard_native_branch_management_restore_retains_authority(client,db,superuser_headers,delegated):
    target,headers=setup_recovery(client,db,superuser_headers,delegated,native_trash=True)
    restored=client.post('/api/v1/branches/'+str(target)+'/restore',headers=headers,json={'reason':'Authorized native recovery proof','expected_version':1})
    assert restored.status_code==200,restored.text
    db.expire_all()
    assert db.get(Branch,target).is_active is True and db.get(BranchLifecycle,target).deleted_at is None


@pytest.mark.parametrize('delegated',[False,True],ids=['superuser','delegated_configurer'])
def test_legacy_company_put_can_restore_native_trashed_target(client,db,superuser_headers,delegated):
    target,headers=setup_recovery(client,db,superuser_headers,delegated,native_trash=True)
    restored=client.put('/api/v1/company/branches/'+str(target),headers=headers,json={'is_active':True})
    assert restored.status_code==200,restored.text
    db.expire_all()
    assert db.get(Branch,target).is_active is True and db.get(BranchLifecycle,target).deleted_at is None


@pytest.mark.parametrize('restriction', ['module', 'branch_write'])
def test_legacy_restore_retains_target_native_permission_ceiling(client,db,superuser_headers,restriction):
    from app.access.models import AccessPolicy
    target,headers=setup_recovery(client,db,superuser_headers,True,native_trash=True)
    policy=db.query(AccessPolicy).filter_by(company_id=1).one()
    grant=db.query(BranchGrant).filter_by(company_id=1,user_id=policy.user_id,branch_id=target).one()
    if restriction=='module':
        grant.module_grants={'hrms':{'enabled':True,'permissions':['company_manage'],'actions':['view'],'scope':'organization'}}
    else:
        grant.can_write=False
    db.commit()
    denied=client.put('/api/v1/company/branches/'+str(target),headers=headers,json={'is_active':True})
    assert denied.status_code==403,denied.text
    db.expire_all()
    assert db.get(Branch,target).is_active is False
    assert db.get(BranchLifecycle,target).deleted_at is not None


def test_definition_recovery_does_not_enable_operational_access_to_trash(client,db,superuser_headers):
    target,headers=setup_recovery(client,db,superuser_headers,False,native_trash=True)
    denied=client.get('/api/v1/employees/',headers={**headers,'X-Suite-Branch':str(target)})
    assert denied.status_code==403,denied.text
    assert denied.json()['detail']=='Branch access is unavailable or revoked'


@pytest.mark.parametrize('value', [None, 'false', 0])
def test_branch_activation_rejects_non_boolean_values(client,db,superuser_headers,value):
    target,headers=setup_recovery(client,db,superuser_headers,False,native_trash=True)
    denied=client.put('/api/v1/company/branches/'+str(target),headers=headers,json={'is_active':value})
    assert denied.status_code==422,denied.text
    db.expire_all()
    assert db.get(Branch,target).is_active is False
