"""Regression coverage for shared identities through legacy module entry points."""
from app.apps.crm.models import CRMCompany
from app.apps.project_management.models import PMSClient
from app.apps.srm.commercial_models import CustomerLink
from tests.test_contact_directory import directory_identity


def test_pms_client_creation_and_edits_use_shared_customer(client, db, superuser_headers, directory_identity):
    response = client.post('/api/v1/project-management/clients', headers=superuser_headers, json={'name':'Shared PMS client','email':'pms@example.com','phone':'9876543210','phone_country_code':'+91'})
    assert response.status_code == 200, response.text
    local = response.json()
    link = db.query(CustomerLink).filter_by(source_type='pms_client', source_id=local['id']).first()
    assert link is not None, 'Legacy PMS capture must create an explicit canonical link'
    ident = link.customer_id
    assert local['shared_customer_id'] == ident
    listing = client.get('/api/v1/master-data/companies', headers=superuser_headers, params={'source':'srm'}).json()
    assert ident in [x['id'] for x in listing['items']]
    edited = client.patch(f"/api/v1/project-management/clients/{local['id']}", headers=superuser_headers, json={'email':'changed@example.com','phone':'9123456780','phone_country_code':'+91'})
    assert edited.status_code == 200, edited.text
    profile = client.get(f'/api/v1/master-data/companies/{ident}', headers=superuser_headers).json()
    assert profile['email'] == 'changed@example.com'
    assert profile['phone_country_code'] == '+91'
    saved = client.patch(f'/api/v1/master-data/companies/{ident}', headers=superuser_headers, json={'name':profile['name'],'version':profile['version'],'email':'sales@example.com','roles':['Customer','Vendor']}, params={'source':'srm'})
    assert saved.status_code == 200, saved.text
    db.expire_all()
    assert db.get(PMSClient,local['id']).email == 'sales@example.com'
    assert db.query(CRMCompany).filter_by(id=ident).count() == 1


def test_explicit_pms_customer_selection_reuses_identity(client, db, superuser_headers, directory_identity):
    shared = client.post('/api/v1/master-data/companies', headers=superuser_headers, json={'name':'Existing customer','email':'existing@example.com'}).json()
    before = db.query(CRMCompany).count()
    result = client.post('/api/v1/project-management/clients', headers=superuser_headers, json={'name':'Existing customer','shared_customer_id':shared['id']})
    assert result.status_code == 200, result.text
    assert result.json()['shared_customer_id'] == shared['id']
    assert result.json()['email'] == 'existing@example.com'
    assert db.query(CRMCompany).count() == before


def test_revoked_pms_policy_blocks_existing_project_membership(db, directory_identity):
    from app.models.user import User
    from app.common.services.identity import SharedIdentityService
    from app.apps.project_management.models import PMSProject,PMSProjectMember
    from app.apps.project_management.access import can_access_project
    from app.access.models import AccessPolicy
    user=User(email="revoked-pms@example.com",hashed_password="unused",is_active=True)
    db.add(user);db.flush()
    SharedIdentityService.ensure_person_for_user(db,user,organization_id=1)
    project=PMSProject(organization_id=1,name="Membership survives revocation",project_key="REVOKE")
    db.add(project);db.flush()
    db.add(PMSProjectMember(project_id=project.id,user_id=user.id,role="Member"));db.commit()
    assert can_access_project(db,project,user)
    policy=AccessPolicy(user_id=user.id,company_id=1,status="active",grants={"project_management":{"enabled":False,"actions":["view"]}})
    db.add(policy);db.commit()
    assert not can_access_project(db,project,user)
    policy.grants={"project_management":{"enabled":True,"actions":["view"],"permissions":[],"scope":"own"}};db.commit()
    assert can_access_project(db,project,user)
    user.is_active=False;db.commit()
    assert not can_access_project(db,project,user)


def test_shared_gateway_retains_selected_branch(db, superuser_headers, directory_identity, monkeypatch):
    import pytest
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.shared import gateway
    from app.models.user import User
    actor=db.query(User).filter_by(email="testadmin@test.com").one()
    observed={}
    async def canonical(user, company, method, path, payload=None, *, branch=None):
        observed.update(company=company,branch=branch,path=path)
        return {"id":1}
    monkeypatch.setattr(gateway,"canonical",canonical)
    prior=db.info.get("branch_context")
    db.info["branch_context"]=SimpleNamespace(company_id=1,branch_id=directory_identity.id)
    try:
        assert gateway.read_record(db,actor,1,"crm","lead",1)=={"id":1}
        assert observed["branch"]==directory_identity.id
        with pytest.raises(HTTPException) as denied:
            gateway.selected_branch(db,2)
        assert denied.value.status_code==403
    finally:
        if prior is None:db.info.pop("branch_context",None)
        else:db.info["branch_context"]=prior


def test_catalog_requests_use_calling_module_permissions():
    from types import SimpleNamespace
    from app.access.catalog import request_module
    for source,expected in [("crm","crm"),("srm","srm"),("pms","project_management")]:
        request=SimpleNamespace(url=SimpleNamespace(path="/api/v1/catalog/items"),query_params={"source":source})
        assert request_module(request)==expected


def test_company_profile_uses_verified_sales_accounting_mapping(client,db,superuser_headers,directory_identity):
    from app.apps.fam.models import FAMParty,FAMSRMMapping
    from test_identity_utils import own_workflow_records
    company=client.post('/api/v1/master-data/companies',headers=superuser_headers,json={"name":"Mapped counterparty"}).json()
    party=FAMParty(company_id=1,party_code="VERIFIED-CUSTOMER",party_type="customer",legal_name="Verified party")
    db.add(party);db.flush()
    mapping=FAMSRMMapping(company_id=1,srm_record_type="customer",srm_record_id=company['id'],fam_record_type="party",fam_record_id=party.id,mapping_status="active")
    db.add(mapping);own_workflow_records(db,party,mapping);db.commit()
    profile=client.get(f"/api/v1/master-data/companies/{company['id']}",headers=superuser_headers)
    assert profile.status_code==200,profile.text
    assert profile.json()['financialNote'].startswith('Verified accounting')
    mapping.mapping_status="inactive";db.commit()
    profile=client.get(f"/api/v1/master-data/companies/{company['id']}",headers=superuser_headers).json()
    assert profile['payables'] is None


def test_scoped_out_private_profile_is_never_recreated(client,db,superuser_headers,directory_identity):
    from datetime import date
    from app.models.user import User
    from app.models.employee import Employee
    from app.common.models import CommonProfile
    from app.common.services.identity import SharedIdentityService
    from test_identity_utils import own_workflow_records
    user=User(email="unassigned-profile@example.com",hashed_password="unused",is_active=True)
    db.add(user);db.flush()
    SharedIdentityService.ensure_person_for_user(db,user,organization_id=1)
    employee=Employee(user_id=user.id,employee_id="UNASSIGNED-PROFILE",first_name="Private",last_name="Person",date_of_joining=date(2026,1,1))
    db.add(employee);own_workflow_records(db,employee);db.commit()
    before=db.query(CommonProfile).count()
    response=client.get(f"/api/v1/project-management/people-management/{user.id}",headers=superuser_headers)
    assert response.status_code==404,response.text
    assert db.query(CommonProfile).count()==before


def test_pms_only_policy_can_use_shared_company_without_crm_access(client,db,superuser_headers,directory_identity):
    from tests.test_crm_phase_1_core_foundation import _headers_for_permissions
    from app.models.user import User
    from app.access.models import AccessPolicy
    from app.branches.models import BranchGrant
    company=client.post('/api/v1/master-data/companies',headers=superuser_headers,json={"name":"Shared across authorized modules","phone":"9345678901","phone_country_code":"+91"}).json()
    headers=_headers_for_permissions(client,db,"pms-only-master@example.com",["pms_admin"])
    user=db.query(User).filter_by(email="pms-only-master@example.com").one()
    db.add(BranchGrant(company_id=1,user_id=user.id,branch_id=directory_identity.id,can_write=True))
    db.add(AccessPolicy(user_id=user.id,company_id=1,status="active",grants={"project_management":{"enabled":True,"scope":"organization","actions":["view","create","edit"],"permissions":["pms_admin"]}}));db.commit()
    assert client.get('/api/v1/crm/companies',headers=headers).status_code==403
    response=client.get('/api/v1/master-data/companies',headers=headers,params={"source":"project_management"})
    assert response.status_code==200,response.text
    assert company['id'] in [row['id'] for row in response.json()['items']]
    response=client.patch(f"/api/v1/master-data/companies/{company['id']}",headers=headers,params={"source":"project_management"},json={"name":company['name'],"version":company['version'],"phone":company['phone'],"phone_country_code":"+91","roles":["Customer","Vendor"]})
    assert response.status_code==200,response.text
    assert set(response.json()['roles']) >= {"Customer","Vendor"}
