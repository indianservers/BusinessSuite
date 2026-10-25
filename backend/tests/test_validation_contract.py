"""Synthetic validation regression tests; all databases are isolated by conftest."""
import importlib.util
from pathlib import Path
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine,text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.input_validation import national_phone,calling_code,email_address,clean_text,PHONE_ERROR
from app.apps.interns_hub.applications import ApplicationInput,today
from app.core.audit_context import context
from app.models.company import Company
from app.core.orm_validation import contact_issues
from fastapi import HTTPException

@pytest.mark.parametrize('value',['9876543210','0001234567'])
def test_phone_preserves_valid_strings(value):assert national_phone(value)==value

@pytest.mark.parametrize('value',['987654321','98765432101','abcdefghij','98765abc10','+919876543210','98765 43210','98765.3210','-987654321','1e00000009','😀123456789','９８７６５４３２１０',9876543210,None])
def test_phone_rejects_malformed_without_truncation(value):
    with pytest.raises(ValueError,match='Enter exactly 10 digits'):national_phone(value)

@pytest.mark.parametrize('code',[None,'','91','+999','+910',91])
def test_missing_unsupported_country_code(code):
    with pytest.raises(ValueError):calling_code(code)

@pytest.mark.parametrize('value',['bad','a@','@example.com','a b@example.com',' a@example.com','a@example.com '])
def test_email_invalid(value):
    with pytest.raises(ValueError):email_address(value)

@pytest.mark.parametrize('value',["o.brien+intern@example.com",'名@example.com'])
def test_email_accepts_legitimate_syntax(value):assert email_address(value)==value

def test_unicode_mononym_and_controls():
    assert clean_text('  李  ',160)=='李'
    assert clean_text("O’Brien-Smith",160)=="O’Brien-Smith"
    for value in ['   ','\u200b','Name\x00']:
        with pytest.raises(ValueError):clean_text(value,160)

@pytest.fixture
def valid_application():
    return dict(full_name='李',parent_name="O’Brien",mobile='0001234567',mobile_country_code='+1',email='synthetic@example.com',identity_type='Other',identity_number='TEST-ONLY',gender='Prefer not to say',date_of_birth='2000-01-01',city='São Paulo',state='Other',tenth_marks=0,twelfth_marks=None,degree='Other',current_year='Graduated',college='Example University',specialization='Design',passout_year=2020,area_of_interest='Software Development',skills='Python, Python',role='Other',mode='Remote',available_from=str(today()),duration='3 Months',address='Example address',emergency_contact='2025550100',emergency_contact_country_code='+1',password='Synthetic@123456',consent=True)

@pytest.mark.parametrize('patch',[{'mobile':'98765432101'},{'mobile_country_code':None},{'email':'invalid'},{'full_name':'   '},{'date_of_birth':'2025-02-30'},{'date_of_birth':'2099-01-01'},{'tenth_marks':101},{'tenth_marks':-1},{'tenth_marks':True},{'tenth_marks':float('inf')},{'gender':'tampered'},{'state':'tampered'},{'degree':'tampered'},{'consent':False},{'identity_type':'PAN','identity_number':'bad'}])
def test_api_bypass_rejected(client,valid_application,patch):
    result=client.post('/api/v1/interns-hub/applications',json={**valid_application,**patch}) if patch.get('tenth_marks')!=float('inf') else None
    if result is not None:
        assert result.status_code==422,result.text
        assert 'input' not in str(result.json().get('detail'))
    else:
        with pytest.raises(ValidationError):ApplicationInput(**{**valid_application,**patch})

def test_valid_application_keeps_leading_zero_and_optional_blank(valid_application):
    record=ApplicationInput(**valid_application)
    assert record.mobile=='0001234567' and record.mobile_country_code=='+1'
    assert record.twelfth_marks is None and record.skills=='Python'

@pytest.mark.parametrize('folder,prefix',[('alembic',''),('alembic_postgresql','pg_')])
def test_migration_is_retryable_and_never_guesses_country(tmp_path,folder,prefix):
    path=Path(__file__).resolve().parents[1]/folder/'versions'/f'{prefix}20261025_021_contact_codes.py'
    spec=importlib.util.spec_from_file_location('contact_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite:///'+str(tmp_path/'legacy.db'))
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE companies (id INTEGER PRIMARY KEY, phone VARCHAR(30))')
        connection.exec_driver_sql("INSERT INTO companies VALUES (1,'+91 12345 67890')")
        with Operations.context(MigrationContext.configure(connection)):module.upgrade();module.upgrade()
        assert tuple(connection.execute(text('SELECT phone,phone_country_code FROM companies')).one())==('+91 12345 67890',None)
    engine.dispose()

def test_orm_legacy_is_flagged_and_unchanged_edit_survives(db):
    company=Company(name='Synthetic Legacy',phone='+91 12345 67890');db.add(company);db.commit()
    assert 'phone' in contact_issues(company)
    token=context.set({'actor':{'authenticated':True}})
    try:
        company.name='Updated';db.commit()
        company.phone='2025550100';company.phone_country_code='+1';db.commit()
        db.expire_all();assert company.phone=='2025550100' and company.phone_country_code=='+1'
        company.phone='123'
        with pytest.raises(HTTPException):db.flush()
        db.rollback()
    finally:context.reset(token)

@pytest.mark.parametrize('number,code',[('987654321','+91'),('98765432101','+91'),('9876543210',None),('+919876543210','+91'),('98765 43210','+91')])
def test_authenticated_employee_api_rejects_bad_phones(client,superuser_headers,number,code):
    payload={'first_name':'Synthetic','last_name':'QA','date_of_joining':str(today()),'create_user_account':False,'phone_number':number,'phone_number_country_code':code}
    result=client.post('/api/v1/employees/',headers=superuser_headers,json=payload)
    assert result.status_code==422,result.text

def test_employee_create_edit_roundtrip_and_export(client,superuser_headers):
    payload={'first_name':'Synthetic','last_name':'QA','date_of_joining':str(today()),'create_user_account':False,'phone_number':'0001234567','phone_number_country_code':'+1'}
    created=client.post('/api/v1/employees/',headers=superuser_headers,json=payload)
    assert created.status_code==201,created.text
    employee_id=created.json()['id']
    assert created.json()['phone_number']=='0001234567'
    assert created.json()['phone_number_country_code']=='+1'
    edited=client.put(f'/api/v1/employees/{employee_id}',headers=superuser_headers,json={'phone_number':'2025550100','phone_number_country_code':'+44'})
    assert edited.status_code==200,edited.text
    reopened=client.get(f'/api/v1/employees/{employee_id}',headers=superuser_headers).json()
    assert (reopened['phone_number'],reopened['phone_number_country_code'])==('2025550100','+44')

def test_crm_contact_roundtrip(client,superuser_headers):
    payload={'firstName':'Synthetic','fullName':'Synthetic QA','phone':'0001234567','phone_country_code':'+1'}
    created=client.post('/api/v1/crm/contacts',headers=superuser_headers,json=payload)
    assert created.status_code==201,created.text
    assert created.json()['phone']=='0001234567' and created.json()['phone_country_code']=='+1'
    item_id=created.json()['id']
    result=client.put(f'/api/v1/crm/contacts/{item_id}',headers=superuser_headers,json={'phone_country_code':'+44'})
    assert result.status_code==200,result.text
    assert result.json()['phone_country_code']=='+44'
    assert client.put(f'/api/v1/crm/contacts/{item_id}',headers=superuser_headers,json={'phone':'123'}).status_code==422

@pytest.mark.parametrize('patch',[{'first_name':'   '},{'first_name':'Synthetic\x00'},{'personal_email':' a@example.com'},{'date_of_birth':'2099-01-01'},{'gender':'tampered'}])
def test_employee_other_fields_are_validated(client,superuser_headers,patch):
    payload={'first_name':'Synthetic','last_name':'','date_of_joining':str(today()),'create_user_account':False,**patch}
    assert client.post('/api/v1/employees/',headers=superuser_headers,json=payload).status_code==422

def test_employee_mononym_is_supported(client,superuser_headers):
    result=client.post('/api/v1/employees/',headers=superuser_headers,json={'first_name':'李','date_of_joining':str(today()),'create_user_account':False})
    assert result.status_code==201,result.text
    assert result.json()['first_name']=='李' and result.json()['last_name']==''

def test_pms_phone_field_roundtrip_and_missing_code_rejection(db):
    from tests.test_pms_project_access import _user
    from app.apps.project_management.api.router import create_project,create_task
    from app.apps.project_management.schemas import PMSProjectCreate,PMSTaskCreate
    from app.apps.project_management.custom_fields import create_field,save_value,task_fields,FieldInput,ValueInput
    manager=_user(db,'phone-fields@example.com',['pms_manage_projects'])
    project=create_project(PMSProjectCreate(name='Phone QA',project_key='PHN'),db=db,current_user=manager)
    task=create_task(project.id,PMSTaskCreate(title='Synthetic phone',task_key='PHN-1'),db=db,current_user=manager)
    definition=create_field(project.id,FieldInput(name='Contact phone',field_type='phone'),db=db,user=manager)
    with pytest.raises(HTTPException):save_value(task.id,definition['id'],ValueInput(value='0001234567'),db=db,user=manager)
    save_value(task.id,definition['id'],ValueInput(value='0001234567',country_code='+1'),db=db,user=manager)
    field=task_fields(task.id,db=db,user=manager)['fields'][0]
    assert (field['value'],field['country_code'])==('0001234567','+1')
    save_value(task.id,definition['id'],ValueInput(value='2025550100',country_code='+44'),db=db,user=manager)
    field=task_fields(task.id,db=db,user=manager)['fields'][0]
    assert (field['value'],field['country_code'])==('2025550100','+44')

def test_shared_form_phone_retains_separate_code_and_validates_paste():
    from app.forms.schema import Definition,clean_answers
    definition=Definition(name='Synthetic phone form',fields=[{'id':'phone','type':'phone','label':'Phone','required':True}])
    assert clean_answers(definition,{'phone':'0001234567','phone_country_code':'+1'})=={'phone':'0001234567','phone_country_code':'+1'}
    for answer in [{'phone':'+919876543210','phone_country_code':'+91'},{'phone':'9876543210'},{'phone':'9876543210','phone_country_code':'+999'}]:
        with pytest.raises(HTTPException):clean_answers(definition,answer)

@pytest.mark.parametrize('folder,prefix',[('alembic',''),('alembic_postgresql','pg_')])
def test_consent_unique_identity_includes_country_without_rewriting_history(tmp_path,folder,prefix):
    path=Path(__file__).resolve().parents[1]/folder/'versions'/f'{prefix}20261025_021_contact_codes.py'
    spec=importlib.util.spec_from_file_location('contact_consent_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite:///'+str(tmp_path/'consent.db'))
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE communication_consents (id INTEGER PRIMARY KEY,email VARCHAR(180),phone VARCHAR(60),record_type VARCHAR(60),record_id INTEGER,consent_type VARCHAR(60),CONSTRAINT uq_communication_consent_subject UNIQUE (email,phone,record_type,record_id,consent_type))')
        connection.exec_driver_sql("INSERT INTO communication_consents VALUES (1,'qa@example.com','+91 12345 67890','contact',1,'sms')")
        with Operations.context(MigrationContext.configure(connection)):module.upgrade();module.upgrade()
        assert tuple(connection.execute(text('SELECT phone,phone_country_code FROM communication_consents WHERE id=1')).one())==('+91 12345 67890',None)
        for ident,code in [(2,'+1'),(3,'+44')]:
            connection.execute(text('INSERT INTO communication_consents (id,email,phone,phone_country_code,record_type,record_id,consent_type) VALUES (:id,:email,:phone,:code,:kind,:record_id,:consent)'),{'id':ident,'email':'qa@example.com','phone':'0001234567','code':code,'kind':'contact','record_id':1,'consent':'sms'})
    engine.dispose()

def test_mononym_can_be_edited_without_null_last_name_conflict(client,superuser_headers):
    result=client.post('/api/v1/employees/',headers=superuser_headers,json={'first_name':'李','date_of_joining':str(today()),'create_user_account':False,'phone_number':'0001234567','phone_number_country_code':'+1'})
    assert result.status_code==201,result.text
    employee_id=result.json()['id']
    updated=client.put(f'/api/v1/employees/{employee_id}',headers=superuser_headers,json={'last_name':None,'phone_number':'2025550100','phone_number_country_code':'+44'})
    assert updated.status_code==200,updated.text
    assert updated.json()['last_name']=='' and updated.json()['phone_number_country_code']=='+44'
    assert client.put(f'/api/v1/employees/{employee_id}',headers=superuser_headers,json={'first_name':None}).status_code==422


def test_lms_callback_requires_permission_and_finite_typed_score(client,superuser_headers):
    path='/api/v1/lms/assignments/999999/completion-callback'
    assert client.post(path,json={'score':'92.5'}).status_code in (401,403)
    for score in ('NaN','Infinity',True,{},'1000000'):
        assert client.post(path,headers=superuser_headers,json={'score':score}).status_code==422
    assert client.post(path,headers=superuser_headers,json={'score':'92.5'}).status_code==404

def test_account_creation_rejects_oversized_password_and_email_spaces(client,superuser_headers):
    result=client.post('/api/v1/employees/',headers=superuser_headers,json={'first_name':'Synthetic','date_of_joining':str(today()),'create_user_account':False})
    assert result.status_code==201,result.text
    path=f"/api/v1/employees/{result.json()['id']}/user-account"
    assert client.post(path,headers=superuser_headers,json={'email':' qa@example.com','password':'Synthetic@123456'}).status_code==422
    assert client.post(path,headers=superuser_headers,json={'email':'qa@example.com','password':'🔐'*24}).status_code==400
    assert client.post('/api/v1/auth/login',json={'email':' qa@example.com','password':'Synthetic@123456'}).status_code==422

def test_identity_sync_does_not_guess_legacy_codes_and_supports_explicit_clear(db):
    from app.models.user import User
    from app.models.employee import Employee
    from app.common.services.identity import SharedIdentityService
    user=User(email='legacy-sync@example.com',hashed_password='SYNTHETIC-UNUSED-HASH',is_active=True)
    db.add(user);db.flush()
    employee=Employee(employee_id='LEGACY-SYNC',first_name='Synthetic',last_name='',user_id=user.id,date_of_joining=today(),phone_number='+91 12345 67890')
    db.add(employee);db.commit()
    token=context.set({'actor':{'authenticated':True}})
    try:
        person=SharedIdentityService.sync_from_employee(db,employee);db.commit()
        assert employee.phone_number=='+91 12345 67890' and employee.phone_number_country_code is None
        assert person.phone_number is None and 'phone_number' in contact_issues(employee)
        employee.phone_number='0001234567';employee.phone_number_country_code='+1'
        SharedIdentityService.sync_from_employee(db,employee);db.commit()
        assert (person.phone_number,person.phone_number_country_code)==('0001234567','+1')
        employee.phone_number=None;employee.phone_number_country_code=None
        SharedIdentityService.sync_from_employee(db,employee);db.commit()
        assert person.phone_number is None and person.phone_number_country_code is None
    finally:context.reset(token)
