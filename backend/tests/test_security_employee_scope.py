from datetime import date
from app.core.security import create_access_token
from app.models.user import User, Role, Permission
from app.models.company import Company, Branch
from app.models.employee import Employee


def test_employee_permission_does_not_grant_other_company_records(client, db):
    companies = [Company(name='Synthetic Tenant A'), Company(name='Synthetic Tenant B')]
    db.add_all(companies); db.flush()
    branches = [Branch(name='Synthetic HQ', company_id=c.id) for c in companies]
    db.add_all(branches); db.flush()
    role = Role(name='hr_security_test', permissions=[Permission(name='employee_view'), Permission(name='employee_update')])
    user = User(email='synthetic-scope@example.com', hashed_password='unused', role=role, is_active=True)
    db.add(user); db.flush()
    own = Employee(employee_id='SCOPE-OWN', first_name='Synthetic', last_name='Own', date_of_joining=date.today(), branch_id=branches[0].id, user_id=user.id)
    other = Employee(employee_id='SCOPE-OTHER', first_name='Canary', last_name='Other tenant', date_of_joining=date.today(), branch_id=branches[1].id)
    db.add_all([own, other]); db.commit()
    headers = {'Authorization':'Bearer '+create_access_token(user.id)}
    result = client.get('/api/v1/employees/', headers=headers)
    assert result.status_code == 200, result.text
    assert {item['id'] for item in result.json()['items']} == {own.id}
    assert client.get(f'/api/v1/employees/{other.id}', headers=headers).status_code == 404
    assert client.put(f'/api/v1/employees/{other.id}', headers=headers, json={'first_name':'Tampered'}).status_code == 404
    assert client.put(f'/api/v1/employees/{own.id}', headers=headers, json={'branch_id':branches[1].id}).status_code == 404
    assert client.post(f'/api/v1/employees/{other.id}/education', headers=headers, json={}).status_code in {404, 405}
    db.refresh(other)
    assert other.first_name == 'Canary'
    assert client.get(f'/api/v1/employees/{own.id}', headers=headers).status_code == 200


def test_document_policies_and_templates_do_not_cross_company_boundaries(client,db):
    from app.models.document import CompanyPolicy,DocumentTemplate
    company=Company(name='Synthetic Policy Tenant');db.add(company);db.flush()
    branch=Branch(name='Synthetic Policy HQ',company_id=company.id);db.add(branch);db.flush()
    role=Role(name='policy_security_test',permissions=[Permission(name='company_view'),Permission(name='company_manage')])
    user=User(email='synthetic-policy@example.com',hashed_password='unused',role=role,is_active=True)
    db.add(user);db.flush()
    db.add(Employee(employee_id='POLICY-OWN',first_name='Synthetic',last_name='Policy',date_of_joining=date.today(),branch_id=branch.id,user_id=user.id))
    foreign_company=company.id+100
    db.add_all([CompanyPolicy(title='Own policy',organization_id=company.id),CompanyPolicy(title='FOREIGN POLICY CANARY',organization_id=foreign_company),DocumentTemplate(name='Own template',organization_id=company.id),DocumentTemplate(name='FOREIGN TEMPLATE CANARY',organization_id=foreign_company)])
    db.commit()
    headers={'Authorization':'Bearer '+create_access_token(user.id)}
    policies=client.get('/api/v1/documents/policies',headers=headers)
    templates=client.get('/api/v1/documents/templates',headers=headers)
    assert policies.status_code==templates.status_code==200
    assert 'FOREIGN' not in policies.text+templates.text
    created=client.post('/api/v1/documents/policies',headers=headers,json={'title':'New own policy'})
    assert created.status_code==201,created.text
    assert db.get(CompanyPolicy,created.json()['id']).organization_id==company.id
