from datetime import date
import pytest
from app.models.user import User


@pytest.fixture(autouse=True)
def employee_setup(client, superuser_headers):
    branches = client.get('/api/v1/company/branches/', headers=superuser_headers).json()
    department = client.post('/api/v1/company/departments/', headers=superuser_headers,
        json={'name':'Password test department','branch_id':branches[0]['id']})
    assert department.status_code == 201, department.text
    designation = client.post('/api/v1/company/designations/', headers=superuser_headers,
        json={'name':'Password test designation','department_id':department.json()['id']})
    assert designation.status_code == 201, designation.text


@pytest.mark.parametrize('password',[None,'Welcome@123','short'])
def test_employee_login_has_no_shared_default_password(client,db,superuser_headers,password):
    response=client.post('/api/v1/employees/',headers=superuser_headers,json={'first_name':'Synthetic','last_name':'Password QA','date_of_joining':str(date.today()),'create_user_account':True,'user_email':'synthetic-password@example.com','user_password':password})
    assert response.status_code==422
    assert not db.query(User).filter_by(email='synthetic-password@example.com').first()


def test_employee_password_has_byte_limit_and_least_privilege_role(client,db,superuser_headers):
    payload={'first_name':'Synthetic','last_name':'Password QA','date_of_joining':str(date.today()),'create_user_account':True,'user_email':'synthetic-password@example.com','user_password':'\U0001f510'*24}
    assert client.post('/api/v1/employees/',headers=superuser_headers,json=payload).status_code==400
    payload['user_password']='Synthetic-Unique@123456'
    response=client.post('/api/v1/employees/',headers=superuser_headers,json=payload)
    assert response.status_code==201,response.text
    assert payload['user_password'] not in response.text
    user=db.query(User).filter_by(email=payload['user_email']).one()
    assert user.role.name=='employee' and not user.is_superuser
    login=client.post('/api/v1/auth/login',json={'email':payload['user_email'],'password':payload['user_password'],'module':'hrms'})
    assert login.status_code==200,login.text
