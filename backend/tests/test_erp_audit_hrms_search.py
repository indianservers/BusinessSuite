"""IMP-18: HRMS search must treat user-entered wildcard characters literally."""
from datetime import date
from uuid import uuid4
import pytest
from app.models.employee import Employee
from app.models.asset import Asset, AssetAssignment
from tests.test_import_workspace import import_headers
from tests.rich_text_test_utils import organization_context

@pytest.mark.parametrize('path',['/assets/employees','/expenses/employees','/exit/employees','/payroll/employee-options'])
@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
def test_employee_lookup_search_is_literal(client,db,import_headers,path,needle):
    marker=uuid4().hex[:8]
    rows=[Employee(employee_id=marker+str(i),first_name=name,last_name='Person',status='Active',date_of_joining=date(2020,1,1),branch_id=int(import_headers['X-Suite-Branch'])) for i,name in enumerate(['QA'+needle+'Literal','QAplainLiteral'])]
    db.add_all(rows);db.commit()
    r=client.get('/api/v1'+path,headers=import_headers,params={'search':needle})
    assert r.status_code==200,r.text
    ids={row['id'] for row in r.json()}
    assert rows[0].id in ids
    assert rows[1].id not in ids

@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
def test_asset_register_and_export_search_are_literal(client,db,import_headers,needle):
    rows=[Asset(name=name,asset_tag=uuid4().hex,organization_id=1) for name in ['QA'+needle+'Literal','QAplainLiteral']]
    db.add_all(rows);db.commit()
    r=client.get('/api/v1/assets/',headers=import_headers,params={'search':needle})
    assert r.status_code==200,r.text
    assert rows[0].id in {row['id'] for row in r.json()}
    assert rows[1].id not in {row['id'] for row in r.json()}
    export=client.get('/api/v1/assets/export',headers=import_headers,params={'search':needle,'format':'csv'})
    assert export.status_code==200,export.text
    assert rows[0].asset_tag in export.text
    assert rows[1].asset_tag not in export.text

    employee=Employee(employee_id=uuid4().hex,first_name='Custody',last_name='Person',status='Active',date_of_joining=date(2020,1,1),branch_id=int(import_headers['X-Suite-Branch']))
    db.add(employee);db.flush()
    assignments=[AssetAssignment(asset_id=row.id,employee_id=employee.id,assigned_date=date.today(),is_active=True) for row in rows]
    db.add_all(assignments);db.commit()
    listed=client.get('/api/v1/assets/assignments',headers=import_headers,params={'search':needle})
    assert listed.status_code==200,listed.text
    assert {a['id'] for a in listed.json()}=={assignments[0].id}
    for register in ['custody','history']:
        if register=='history':
            for item in assignments:
                item.is_active=False
                item.returned_date=date.today()
            db.commit()
        exported=client.get('/api/v1/assets/export',headers=import_headers,params={'search':needle,'format':'csv','register':register})
        assert exported.status_code==200,exported.text
        assert rows[0].asset_tag in exported.text
        assert rows[1].asset_tag not in exported.text
    ordinary=client.get('/api/v1/assets/',headers=import_headers,params={'search':'qaplain'})
    assert ordinary.status_code==200,ordinary.text
    assert {a['id'] for a in ordinary.json()}=={rows[1].id}

@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
def test_asset_approver_search_is_literal(client,db,import_headers,needle):
    from app.models.user import User
    from test_identity_utils import attach_test_identity, attach_workflow_branch, own_workflow_records
    marker=uuid4().hex[:8]
    rows=[User(email=f'qa{part}{marker}@example.com',hashed_password='unused-synthetic',is_active=True,is_superuser=True) for part in [needle,'plain']]
    db.add_all(rows);db.flush()
    for user in rows:
        attach_test_identity(db,user)
        attach_workflow_branch(db,user)
    from app.access.models import AccessMembership
    db.add_all([AccessMembership(user_id=user.id,company_id=1,active=True,is_admin=True) for user in rows])
    own_workflow_records(db,*rows)
    db.commit()
    r=client.get('/api/v1/assets/approvers',headers=import_headers,params={'search':needle})
    assert r.status_code==200,r.text
    ids={item['id'] for item in r.json()}
    assert rows[0].id in ids, ([(u.id,u.email,u.is_superuser,u.is_active) for u in rows],client.get('/api/v1/assets/approvers',headers=import_headers).json())
    assert rows[1].id not in ids
