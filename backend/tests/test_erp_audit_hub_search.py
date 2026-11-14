"""Literal intake and workforce searches in the intern hub."""
from datetime import date
from uuid import uuid4
import pytest
from app.models.employee import Employee
from app.apps.interns_hub.models import InternApplication
from tests.test_import_workspace import import_headers
from tests.rich_text_test_utils import organization_context

@pytest.mark.parametrize('kind',['people','intake'])
@pytest.mark.parametrize('needle',['%','_',chr(92),'/'])
def test_hub_search_is_literal(client,db,import_headers,kind,needle):
    rows=[]
    for name in ['QA'+needle+'Literal','QAplainLiteral']:
        if kind=='people':
            row=Employee(employee_id=uuid4().hex[:12],first_name=name,last_name='Person',status='Active',employment_type='Intern',date_of_joining=date(2020,1,1),branch_id=int(import_headers['X-Suite-Branch']))
        else:
            row=InternApplication(organization_id=1,reference=uuid4().hex,email=uuid4().hex+'@example.com',full_name=name,password_hash='unused-synthetic',details={},identity_number_encrypted='synthetic',identity_last4='0000',status='Pending')
        db.add(row);rows.append(row)
    db.commit()
    path='/api/v1/interns-hub/'+('operations/people' if kind=='people' else 'admin/application-intake')
    result=client.get(path,headers=import_headers,params={'search':needle,'per_page':1})
    assert result.status_code==200,result.text
    assert result.json()['total']==1
    assert [item['id'] for item in result.json()['items']]==[rows[0].id]
