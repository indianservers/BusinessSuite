"""Literal HRMS attendance, verification and account lookup searches."""
from datetime import date
from uuid import uuid4
import pytest
from app.models.employee import Employee
from tests.test_import_workspace import import_headers
from tests.rich_text_test_utils import organization_context

@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
@pytest.mark.parametrize('path',['/attendance/register','/background-verification/employees','/background-verification/register'])
def test_hrms_people_search_is_literal(client,db,import_headers,needle,path):
    rows=[Employee(employee_id=uuid4().hex[:12],first_name=name,last_name='Person',status='Active',date_of_joining=date(2020,1,1),branch_id=int(import_headers['X-Suite-Branch'])) for name in ['QA'+needle+'Literal','QAplainLiteral']]
    db.add_all(rows);db.commit()
    r=client.get('/api/v1'+path,headers=import_headers,params={'search':needle,'date':'2026-11-14'})
    assert r.status_code==200,r.text
    result=r.json()
    items=result['items'] if isinstance(result,dict) else result
    key='employee_id' if path.startswith('/attendance') else 'id'
    ids={x[key] for x in items}
    assert rows[0].id in ids
    assert rows[1].id not in ids

@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
@pytest.mark.parametrize('path',['/employees/accounts','/background-verification/owners','/employees/user-options'])
def test_hrms_account_search_is_literal(client,db,import_headers,needle,path):
    from app.models.user import User
    from app.access.models import AccessMembership
    from test_identity_utils import attach_test_identity,attach_workflow_branch
    marker=uuid4().hex[:8]
    rows=[User(email=f'qa{part}{marker}@example.com',hashed_password='unused-synthetic',is_active=True,is_superuser=False) for part in [needle,'plain']]
    db.add_all(rows);db.flush()
    for user in rows:
        attach_test_identity(db,user)
        attach_workflow_branch(db,user)
        db.add(AccessMembership(user_id=user.id,company_id=1,active=True,is_admin=False))
    db.commit()
    r=client.get('/api/v1'+path,headers=import_headers,params={'search':needle})
    assert r.status_code==200,r.text
    result=r.json()
    items=result['items'] if isinstance(result,dict) else result
    ids={x['id'] for x in items}
    assert rows[0].id in ids
    assert rows[1].id not in ids
