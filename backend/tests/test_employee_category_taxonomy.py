import pytest
from pydantic import ValidationError
from app.shared.employee_category_taxonomy import TaxonomyInput, options, save
from app.shared.employee_categories import matches_categories
from app.shared.models import ServicePolicy
from tests.test_employee_profile_records import profile_employee

DATA={'version':0,'categories':[{'id':'tech','name':'Technicians','active':True,'children':[{'id':'laptop','name':'Laptop repair','active':True},{'id':'phone','name':'Phone repair','active':False}]},{'id':'consult','name':'Consultants','active':True,'children':[{'id':'tax','name':'Tax','active':True}]}]}

def test_taxonomy_roundtrip_and_existing_options(client,db,superuser_headers,profile_employee):
    response=client.get('/api/v1/access/services/employee-categories',headers=superuser_headers)
    assert response.status_code==200,response.text
    assert response.json()['version']==0
    response=client.put('/api/v1/access/services/employee-categories',headers=superuser_headers,json=DATA)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['version']==1 and result['can_manage']
    assert 'Technicians > Laptop repair' in result['items']
    assert 'Technicians > Phone repair' not in result['items']
    assert result['categories'][0]['children'][0]['parent_value']=='Technicians'
    response=client.get('/api/v1/employees/work-category-options',headers=superuser_headers)
    assert response.status_code==200,response.text
    assert 'Technicians > Laptop repair' in response.json()['items']
    assert client.put('/api/v1/access/services/employee-categories',headers=superuser_headers,json=DATA).status_code==409
    changed={**DATA,'version':1,'categories':[dict(DATA['categories'][0],name='Changed')]}
    response=client.put('/api/v1/access/services/employee-categories',headers=superuser_headers,json=changed)
    assert response.status_code==200,response.text
    assert db.query(ServicePolicy).filter_by(kind='employee_categories').count()==1

@pytest.mark.parametrize('categories',[
 [{'id':'a','name':'A','children':[{'id':'a','name':'B'}]}],
 [{'id':'a','name':'A'},{'id':'b','name':'a'}],
 [{'id':'a','name':'A','children':[{'id':'b','name':'B'},{'id':'c','name':'b'}]}],
 [{'id':'a','name':'A > B'}],
 [{'id':'a','name':'A'*60,'children':[{'id':'b','name':'B'*30}]}],
])
def test_invalid_taxonomies(categories):
    with pytest.raises(ValidationError):TaxonomyInput(version=0,categories=categories)

def test_parent_category_matching_does_not_include_siblings():
    assert matches_categories(['Technicians > Laptop repair'],['technicians'])
    assert matches_categories(['Technicians > Laptop repair'],['Technicians > Laptop repair'])
    assert not matches_categories(['Technicians > Phone repair'],['Technicians > Laptop repair'])
    assert not matches_categories(['Other technicians > Laptop repair'],['Technicians'])


def test_company_registry_isolation_and_read_only_denial(db, superuser_headers, profile_employee):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.models.company import Company
    from app.models.user import User
    actor=db.query(User).filter(User.email=='testadmin@test.com').one()
    other=Company(name='Other category company');db.add(other);db.flush()
    db.add(ServicePolicy(organization_id=other.id,module_key='hrms',kind='employee_categories',scope_key=f'employee-categories:company:{other.id}',values_json={'categories':[{'id':'foreign','name':'Private other category','active':True,'children':[]}]},version=1,updated_by=actor.id));db.commit()
    assert 'Private other category' not in options(db,actor)['items']
    foreign=SimpleNamespace(id=actor.id,organization_id=other.id,is_superuser=True)
    assert options(db,foreign)['items']==['Private other category']
    actor._suite_admin_read=True
    try:
        assert options(db,actor)['can_manage']  # GET admin inspection retains real platform authority
        with pytest.raises(HTTPException) as denied:save(db,actor,TaxonomyInput(**DATA))
        assert denied.value.status_code==403
    finally:del actor._suite_admin_read


def test_category_query_matches_parent_and_excludes_sibling(db):
    from sqlalchemy import literal,select
    from app.shared.employee_categories import category_clause
    value=literal('["Technicians > Laptop repair"]')
    assert db.scalar(select(category_clause(db,value,['Technicians'])))
    assert db.scalar(select(category_clause(db,value,['Technicians > Laptop repair'])))
    assert not db.scalar(select(category_clause(db,value,['Technicians > Phone repair'])))
    assert not db.scalar(select(category_clause(db,value,['Tech'])))


def test_actor_without_hrms_write_permission_cannot_manage(db,superuser_headers,profile_employee):
    from fastapi import HTTPException
    from app.models.user import User
    actor=db.query(User).filter(User.email=='testadmin@test.com').one()
    actor.is_superuser=False
    with pytest.raises(HTTPException) as denied:save(db,actor,TaxonomyInput(**DATA))
    assert denied.value.status_code==403
