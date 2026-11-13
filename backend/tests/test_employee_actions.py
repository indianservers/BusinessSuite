"""Employee action permissions, native version guards and persistent proposals."""
from datetime import date
from uuid import uuid4
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,prepare,approve,tick
from tests.test_suite_conversations import create,say,ROOT
from app.ai_operator.employee_actions import EmployeeProfileUpdate,interpret,projection,proposal,followup
from app.ai_operator.local_nlp import parse,contexts,Interpretation
from app.ai_operator.suite_models import SuiteRun
from app.apps.project_management.models import PMSProject
from app.models.employee import Employee
from ai_test_utils import auth_headers


@pytest.mark.parametrize('field',['role_id','user_id','status','employment_type','branch_id','bank_name','account_number','salary_currency','aadhaar_number','allow_contact_duplicate','profile_completeness'])
def test_protected_employee_fields_are_not_bot_actions(field):
    with pytest.raises(ValueError):EmployeeProfileUpdate.model_validate({field:1})


@pytest.mark.parametrize('payload',[{}, {'first_name':None},{'first_name':' '},{'work_email':'bad'},
    {'timezone':'Not/A_Timezone'},{'department_id':True},{'department_id':0},{'reporting_manager_id':2147483648}])
def test_profile_payload_reuses_native_validation(payload):
    with pytest.raises(ValueError):EmployeeProfileUpdate.model_validate(payload)


@pytest.mark.parametrize('text',[
    'HRMS: update employee #12 office extension: 204',
    'Please edit the employee profile #12 desk: "B-24", timezone: Asia/Kolkata',
    'Change staff #12 department id: 3, designation id: 4',
])
def test_explicit_local_employee_commands(text):
    value=parse(text,'HRMS')
    assert value.intent=='employee.update' and not value.question
    assert contexts(value)==[{'tool':'hrms.employee','record_id':12}]


def test_local_employee_followups_reject_acknowledgements_and_wrong_record_types():
    value=parse('HRMS: update employee','HRMS');assert proposal(value,[])['question']
    prior={'intent':value.intent,'slots':value.slots,'module':'HRMS'}
    for text in ('yes','task #12','EMP00012'):
        reply=followup(Interpretation('HRMS','unsupported'),prior,text)
        assert reply.question and not reply.slots.get('record_id')
    reply=followup(Interpretation('HRMS','unsupported'),prior,'employee #12')
    assert proposal(reply,[{'tool':'hrms.employee','records':{'id':12}}])['question']
    prior={'intent':reply.intent,'slots':reply.slots,'module':'HRMS'}
    reply=followup(Interpretation('HRMS','unsupported'),prior,'office extension: 204, desk: clear')
    assert proposal(reply,[{'tool':'hrms.employee','records':{'id':12}}])['steps'][0]['payload']=={'office_extension':'204','desk_code':None}
    assert followup(Interpretation('HRMS','unsupported'),prior,'cancel').intent=='cancelled'
    assert interpret('Update employee #'+('9'*5000)).question


def test_employee_source_projection_drops_sensitive_and_personal_fields():
    value=projection({'id':12,'first_name':'Asha','office_extension':'101','work_email':'work@example.com',
        'personal_email':'private@example.com','phone_number':'9999999999','bank_name':'Private','aadhaar_number':'Secret',
        'documents':[{'document_url':'private'}],'role_id':1,'health_information':'Private medical data'})
    assert value=={'id':12,'first_name':'Asha','office_extension':'101','work_email':'work@example.com'}


def seed(client,db):
    h,user,project,_=setup_suite(client,db)
    employee=Employee(employee_id='BOT-'+uuid4().hex[:10],first_name='Synthetic',last_name='Employee',
        date_of_joining=date(2026,1,1),branch_id=db.get(PMSProject,project).branch_id,
        office_extension='101',desk_code='A-12')
    db.add(employee);db.commit()
    return h,user,employee.id


def final(client,h,ident):
    response=client.get(ROOT+f'/runs/{ident}',headers=h)
    assert response.status_code==200,response.text
    return response.json()


def test_employee_conversation_collects_and_revises_then_updates_only_after_approval(client,db):
    h,user,ident=seed(client,db);chat=create(client,h)
    value=say(client,h,chat,'HRMS: update employee')
    assert value['status']=='needs_clarification'
    value=say(client,h,chat,f'employee #{ident}')
    assert value['status']=='needs_clarification'
    value=say(client,h,chat,'yes')
    assert value['status']=='needs_clarification' and not value['plan']['steps']
    value=say(client,h,chat,'office extension: 204, desk: clear')
    assert value['status']=='awaiting_approval',value
    assert value['result']['profile_changes']['1']=={'record_id':ident,'changes':[
        {'field':'office_extension','before':'101','after':'204'},{'field':'desk_code','before':'A-12','after':None}]}
    assert db.get(Employee,ident).office_extension=='101'
    value=say(client,h,chat,'office extension: 205')
    assert value['plan']['steps'][0]['payload']=={'office_extension':'205','desk_code':None}
    approve(client,h,value);tick(client,db)
    completed=final(client,h,value['id'])
    assert completed['status']=='succeeded',completed
    assert completed['result_cards'][0]['href']==f'/hrms/employees/{ident}'
    db.expire_all();assert db.get(Employee,ident).office_extension=='205' and db.get(Employee,ident).desk_code is None
    approve(client,h,completed);assert tick(client,db)==0


def test_employee_stale_snapshot_pauses_before_dispatch(client,db):
    h,user,ident=seed(client,db)
    value=prepare(client,h,[{'tool':'hrms.update_employee','record_id':ident,'payload':{'office_extension':'204'}}])
    approve(client,h,value)
    assert client.put(f'/api/v1/employees/{ident}',headers=h,json={'work_location':'Changed elsewhere'}).status_code==200
    tick(client,db);completed=final(client,h,value['id'])
    assert completed['status']=='paused' and completed['error_code']=='CANONICAL_STEP_409',completed
    db.expire_all();assert db.get(Employee,ident).office_extension=='101'


def test_employee_native_version_guard_rejects_change_between_read_and_write(client,db,monkeypatch):
    from app.ai_operator import suite
    h,user,ident=seed(client,db)
    value=prepare(client,h,[{'tool':'hrms.update_employee','record_id':ident,'payload':{'office_extension':'204'}}])
    approve(client,h,value);original=suite.api_call;observed=[]
    async def concurrent(app,auth,method,path,payload=None,**kwargs):
        if method=='PUT' and path==f'/employees/{ident}' and kwargs.get('if_match'):
            observed.append(kwargs['if_match'])
            await original(app,auth,method,path,{'work_location':'Concurrent update'})
        return await original(app,auth,method,path,payload,**kwargs)
    monkeypatch.setattr(suite,'api_call',concurrent)
    tick(client,db);completed=final(client,h,value['id'])
    assert len(observed)==1 and len(observed[0])==64
    assert completed['status']=='needs_reconciliation' and completed['error_code']=='CANONICAL_STEP_409',completed
    assert not completed['receipts']
    db.expire_all();employee=db.get(Employee,ident)
    assert employee.office_extension=='101' and employee.work_location=='Concurrent update'


def test_employee_read_only_user_cannot_prepare_update(client,db):
    h,user,ident=seed(client,db)
    headers,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','employee_view'])
    value=prepare(client,headers,[{'tool':'hrms.update_employee','record_id':ident,'payload':{'office_extension':'204'}}])
    assert value['status']=='failed' and not value['approval_id']
    assert db.get(Employee,ident).office_extension=='101'


def test_employee_personal_contact_requires_native_sensitive_permission(client,db):
    h,user,ident=seed(client,db)
    headers,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','employee_view','employee_update'])
    value=prepare(client,headers,[{'tool':'hrms.update_employee','record_id':ident,'payload':{'personal_email':'new@example.com'}}])
    assert value['status']=='awaiting_approval',value
    approve(client,headers,value);tick(client,db)
    completed=final(client,headers,value['id'])
    assert completed['status']=='needs_reconciliation' and completed['error_code']=='CANONICAL_STEP_403',completed
    db.expire_all();assert db.get(Employee,ident).personal_email is None


def test_authorized_hr_can_update_personal_contact_without_exposing_it_as_model_context(client,db):
    h,user,ident=seed(client,db)
    headers,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','employee_view','employee_update','employee_sensitive_view'])
    value=prepare(client,headers,[{'tool':'hrms.update_employee','record_id':ident,'payload':{'personal_email':'synthetic-personal@example.com'}}])
    assert value['status']=='awaiting_approval',value
    approve(client,headers,value);tick(client,db)
    assert final(client,headers,value['id'])['status']=='succeeded'
    db.expire_all();assert db.get(Employee,ident).personal_email=='synthetic-personal@example.com'
    assert 'personal_email' not in projection(client.get(f'/api/v1/employees/{ident}',headers=headers).json())


def test_cross_company_employee_cannot_be_read_or_updated(client,db):
    from app.models.company import Company,Branch
    h,user,ident=seed(client,db)
    other=Company(name='Other synthetic employer',is_active=True);db.add(other);db.flush()
    branch=Branch(name='Other synthetic branch',company_id=other.id);db.add(branch);db.flush()
    employee=Employee(employee_id='FOREIGN-'+uuid4().hex[:8],first_name='Foreign',last_name='Employee',date_of_joining=date(2026,1,1),branch_id=branch.id,office_extension='901')
    db.add(employee);db.commit();target=employee.id
    headers,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','employee_view','employee_update'])
    assert client.get(f'/api/v1/employees/{target}',headers=headers).status_code==404
    value=prepare(client,headers,[{'tool':'hrms.update_employee','record_id':target,'payload':{'office_extension':'204'}}])
    assert value['status']=='failed' and not value['approval_id']
    db.expire_all();assert db.get(Employee,target).office_extension=='901'


def test_employee_lost_receipt_never_automatically_repeats_write(client,db,monkeypatch):
    from app.ai_operator import suite
    h,user,ident=seed(client,db)
    value=prepare(client,h,[{'tool':'hrms.update_employee','record_id':ident,'payload':{'office_extension':'204'}}])
    approve(client,h,value);original=suite.api_call;writes=[]
    async def lost(app,auth,method,path,payload=None,**kwargs):
        result=await original(app,auth,method,path,payload,**kwargs)
        if method=='PUT' and path==f'/employees/{ident}':
            writes.append(path);raise RuntimeError('Synthetic lost receipt')
        return result
    monkeypatch.setattr(suite,'api_call',lost)
    tick(client,db)
    assert final(client,h,value['id'])['status']=='needs_reconciliation'
    db.expire_all();assert db.get(Employee,ident).office_extension=='204'
    assert tick(client,db)==0 and len(writes)==1


@pytest.mark.parametrize('method,path,version',[
    ('POST','/employees/12','a'*64),('PUT','/crm/leads/12','a'*64),
    ('PUT','/employees/12','invalid'),('PUT','/employees/12',1),('PUT','/employees/12','a'*64+'\r\nInjected: true'),
])
def test_native_employee_version_header_is_fixed_path_and_shape(method,path,version):
    import asyncio
    from fastapi import HTTPException
    from app.ai_operator.suite import api_call
    with pytest.raises(HTTPException) as error:
        asyncio.run(api_call(None,'',method,path,{},if_match=version))
    assert error.value.status_code==422


@pytest.mark.parametrize('tool',['crm.update_lead','crm.qualify_lead','crm.convert_lead','hrms.update_employee'])
def test_unrelated_creation_receipts_cannot_select_leads_or_employees(client,db,tool):
    setup_suite(client,db)
    from app.ai_operator.suite import Plan
    from app.ai_operator.workflows import validate_reference_types
    from fastapi import HTTPException
    payload={'values':{'status':'Qualified'}} if tool=='crm.qualify_lead' else {'createContact':True,'createCompany':True,'createDeal':False} if tool=='crm.convert_lead' else {'office_extension':'204'} if tool=='hrms.update_employee' else {'notes':'wrong target'}
    plan=Plan.model_validate({'summary':'Invalid reference','steps':[{'tool':'crm.create_task','payload':{'title':'Task'}},
        {'tool':tool,'record_id':{'$step':1,'field':'id'},'payload':payload}]})
    with pytest.raises(HTTPException):validate_reference_types(plan)



def test_employee_partial_restatement_preserves_selection_and_other_fields():
    prior={'intent':'employee.update','slots':{'record_id':12,'values':{'desk_code':'B-24','office_extension':'204'}}}
    text='Update employee office extension: 205'
    result=followup(interpret(text),prior,text)
    assert result.slots=={'record_id':12,'values':{'desk_code':'B-24','office_extension':'205'}}


def test_employee_explicit_different_record_does_not_inherit_fields():
    prior={'intent':'employee.update','slots':{'record_id':12,'values':{'desk_code':'B-24'}}}
    text='Update employee #13 office extension: 205'
    result=followup(interpret(text),prior,text)
    assert result.slots=={'record_id':13,'values':{'office_extension':'205'}}


def test_employee_fields_can_be_corrected_before_record_selection():
    prior={'intent':'employee.update','slots':{'_awaiting':'record_id','values':{'desk_code':'B-24'}}}
    result=followup(Interpretation('HRMS','unsupported'),prior,'office extension: 205')
    assert result.slots['values']=={'desk_code':'B-24','office_extension':'205'}
    assert not result.slots.get('record_id')
    result=followup(Interpretation('HRMS','unsupported'),{'slots':result.slots},'employee #12')
    assert result.slots['record_id']==12 and result.slots['values']['office_extension']=='205'


def test_employee_early_fields_and_partial_restatement_execute_only_after_review(client,db):
    h,user,ident=seed(client,db);chat=create(client,h)
    value=say(client,h,chat,'HRMS: update employee desk: B-24')
    assert value['status']=='needs_clarification'
    value=say(client,h,chat,'office extension: 204')
    assert value['status']=='needs_clarification' and not value['plan']['steps']
    value=say(client,h,chat,f'Update employee #{ident}')
    assert value['status']=='awaiting_approval'
    value=say(client,h,chat,'Update employee office extension: 205')
    assert value['status']=='awaiting_approval'
    assert value['plan']['steps'][0]['record_id']==ident
    assert value['plan']['steps'][0]['payload']=={'desk_code':'B-24','office_extension':'205'}
    db.expire_all();assert db.get(Employee,ident).office_extension=='101'
    approve(client,h,value);tick(client,db)
    assert final(client,h,value['id'])['status']=='succeeded'
    db.expire_all();assert db.get(Employee,ident).office_extension=='205'
    assert db.get(Employee,ident).desk_code=='B-24'
