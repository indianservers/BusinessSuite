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
