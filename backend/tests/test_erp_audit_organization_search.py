"""IMP-18: literal wildcard searches in organization masters and employee directory."""
from datetime import date
from uuid import uuid4
import pytest
from app.models.company import Company,Branch,Department,Designation
from app.models.employee import Employee
from tests.test_import_workspace import import_headers
from tests.rich_text_test_utils import organization_context

@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
@pytest.mark.parametrize('kind',['departments','designations'])
def test_organization_master_search_is_literal(client,db,import_headers,needle,kind):
    branch=int(import_headers['X-Suite-Branch'])
    department=Department(name='Parent',organization_id=1,branch_id=branch,is_active=True)
    db.add(department);db.flush()
    model=Department if kind=='departments' else Designation
    parent={'branch_id':branch} if kind=='departments' else {'department_id':department.id}
    rows=[model(name=name,organization_id=1,is_active=True,**parent) for name in ['QA'+needle+'Literal','QAplainLiteral']]
    db.add_all(rows);db.commit()
    r=client.get('/api/v1/company/'+kind+'/',headers=import_headers,params={'search':needle})
    assert r.status_code==200,r.text
    ids={x['id'] for x in r.json()}
    assert rows[0].id in ids
    assert rows[1].id not in ids

@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
@pytest.mark.parametrize('kind',['company','branches'])
def test_visible_company_and_branch_search_is_literal(client,db,import_headers,needle,kind):
    model=Company if kind=='company' else Branch
    row=db.get(model,1 if kind=='company' else int(import_headers['X-Suite-Branch']))
    row.name='QA'+needle+'Literal';db.commit()
    path='/api/v1/company/' if kind=='company' else '/api/v1/company/branches/'
    first=client.get(path,headers=import_headers,params={'search':needle})
    assert first.status_code==200,first.text
    assert row.id in {x['id'] for x in first.json()}
    row.name='QAplainLiteral';db.commit()
    second=client.get(path,headers=import_headers,params={'search':needle})
    assert second.status_code==200,second.text
    assert row.id not in {x['id'] for x in second.json()}

@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
def test_employee_directory_and_export_search_is_literal(client,db,import_headers,needle):
    rows=[Employee(employee_id=uuid4().hex[:12],first_name=name,last_name='Person',skills_tags=name,status='Active',date_of_joining=date(2020,1,1),branch_id=int(import_headers['X-Suite-Branch'])) for name in ['QA'+needle+'Literal','QAplainLiteral']]
    db.add_all(rows);db.commit()
    result=client.get('/api/v1/employees/',headers=import_headers,params={'search':needle})
    assert result.status_code==200,result.text
    ids={x['id'] for x in result.json()['items']}
    assert rows[0].id in ids
    assert rows[1].id not in ids
    export=client.get('/api/v1/employees/export',headers=import_headers,params={'search':needle})
    assert export.status_code==200,export.text
    assert rows[0].employee_id in export.text
    assert rows[1].employee_id not in export.text

    for path,params in [('/employees/directory',{'search':needle}),('/employees/org-search',{'q':needle}),('/employees/directory',{'skills':needle})]:
        response=client.get('/api/v1'+path,headers=import_headers,params=params)
        assert response.status_code==200,response.text
        values=response.json()
        items=values['items'] if isinstance(values,dict) else values
        ids={x['id'] for x in items}
        assert rows[0].id in ids
        assert rows[1].id not in ids
