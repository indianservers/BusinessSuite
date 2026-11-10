"""Persistent conversations retain verified context without bypassing action review."""
from uuid import uuid4
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from app.apps.crm.models import CRMTask
from app.ai_operator.suite_models import SuiteRun
from ai_test_utils import auth_headers

ROOT='/api/v1/ai-operator/suite'


def create(client,h):
    r=client.post(ROOT+'/conversations',headers=h,json={'title':'Customer recovery'})
    assert r.status_code==201,r.text
    return r.json()['id']


def say(client,h,chat,text,**extra):
    r=client.post(ROOT+'/commands',headers=h,json={'conversation_id':chat,'text':text,'provider':'local','request_key':str(uuid4()),**extra})
    assert r.status_code==200,r.text
    assert r.json()['status']!='failed',r.text
    return r.json()


def test_conversation_restores_clarification_and_follows_completed_task(client,db):
    h,user,_,_=setup_suite(client,db);chat=create(client,h)
    first=say(client,h,chat,'CRM: create a task')
    assert first['status']=='needs_clarification'
    restored=client.get(f'{ROOT}/conversations/{chat}',headers=h).json()
    assert restored['runs'][0]['id']==first['id']
    draft=say(client,h,chat,'Review renewal',parent_run_id=first['id'])
    assert draft['status']=='awaiting_approval',draft
    assert db.query(CRMTask).count()==0
    approve(client,h,draft);tick(client,db)
    follow=say(client,h,chat,'mark it done',parent_run_id=draft['id'])
    assert follow['status']=='awaiting_approval',follow
    assert follow['plan']['steps'][0]['tool']=='crm.update_task'
    assert follow['plan']['steps'][0]['record_id']==db.query(CRMTask).one().id
    approve(client,h,follow);tick(client,db)
    summary=say(client,h,chat,'what changed?',parent_run_id=follow['id'])
    assert summary['status']=='answered' and 'crm.update_task' in summary['plan']['summary']
    assert db.query(CRMTask).count()==1
    assert len(client.get(f'{ROOT}/conversations/{chat}',headers=h).json()['runs'])==4
    create(client,h)
    assert client.post(f'{ROOT}/conversations/{chat}/resume',headers=h).status_code==200
    assert client.get(ROOT+'/conversations',headers=h).json()['items'][0]['id']==chat


def test_conversation_switches_modules_and_rejects_stale_and_foreign_links(client,db):
    h,user,_,_=setup_suite(client,db);chat=create(client,h)
    crm=say(client,h,chat,'CRM: what are todays jobs')
    hr=say(client,h,chat,'HRMS: list employees',parent_run_id=crm['id'])
    assert hr['result']['request']['module']=='HRMS'
    pms=say(client,h,chat,'PMS: list projects',parent_run_id=hr['id'])
    assert pms['result']['request']['module']=='PMS'
    stale=client.post(ROOT+'/commands',headers=h,json={'conversation_id':chat,'parent_run_id':crm['id'],'provider':'local','text':'CRM: list tasks','request_key':str(uuid4())})
    assert stale.status_code==409
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(f'{ROOT}/conversations/{chat}',headers=other).status_code==404
    listed=client.get(ROOT+'/conversations',headers=other)
    assert listed.status_code in (200,403)
    if listed.status_code==200:assert not listed.json()['items']
    foreign=create(client,h)
    bad=client.post(ROOT+'/commands',headers=h,json={'conversation_id':foreign,'parent_run_id':pms['id'],'provider':'local','text':'list tasks','request_key':str(uuid4())})
    assert bad.status_code==409


def test_conversation_retry_archive_and_pending_module_guard(client,db):
    h,_,_,_=setup_suite(client,db);chat=create(client,h)
    payload={'conversation_id':chat,'module':'CRM','provider':'local','text':'create a task','request_key':str(uuid4())}
    first=client.post(ROOT+'/commands',headers=h,json=payload)
    retry=client.post(ROOT+'/commands',headers=h,json=payload)
    assert first.status_code==retry.status_code==200
    assert first.json()['id']==retry.json()['id']
    assert db.query(SuiteRun).count()==1
    blocked=client.post(ROOT+'/commands',headers=h,json={**payload,'request_key':str(uuid4()),'text':'HRMS: show leave balance'})
    assert blocked.status_code==409
    assert client.patch(f'{ROOT}/conversations/{chat}',headers=h,json={'title':'Renamed job'}).status_code==200
    assert client.get(ROOT+'/conversations',headers=h).json()['items'][0]['title']=='Renamed job'
    assert client.delete(f'{ROOT}/conversations/{chat}',headers=h).status_code==200
    assert client.get(f'{ROOT}/conversations/{chat}',headers=h).status_code==404
    assert client.get(ROOT+'/conversations',headers=h).json()['items']==[]


def test_hrms_conversation_restores_multiple_field_answers(client,db):
    from app.models.employee import Employee
    from datetime import date
    h,user,_,_=setup_suite(client,db)
    db.add(Employee(employee_id='CHAT-HR-QA',user_id=user.id,first_name='HR',last_name='QA',date_of_joining=date.today()))
    db.commit();db.expire_all()
    chat=create(client,h)
    first=say(client,h,chat,'HRMS: create HR ticket')
    assert first['status']=='needs_clarification'
    second=say(client,h,chat,'Laptop repair',parent_run_id=first['id'])
    assert second['status']=='awaiting_approval',second
    third=say(client,h,chat,'change title to "Laptop replacement"',parent_run_id=second['id'])
    assert third['status']=='awaiting_approval',third
    assert third['plan']['steps'][0]['payload']['subject']=='Laptop replacement'
    assert client.get(f'{ROOT}/conversations/{chat}',headers=h).json()['runs'][-1]['id']==third['id']


def test_ambiguous_completed_task_references_are_not_guessed():
    from types import SimpleNamespace
    from app.ai_operator.suite_conversations import resolve_task_reference
    row=SimpleNamespace(status='succeeded',result={'request':{'module':'CRM'}},receipts=[
        {'status':'succeeded','tool':'crm.create_task','record_id':1},
        {'status':'succeeded','tool':'crm.create_task','record_id':2}])
    assert resolve_task_reference('mark it done',[row],'CRM')=='mark it done'
    row.receipts.pop()
    assert resolve_task_reference('mark it done',[row],'CRM')=='mark task #1 done'
    assert resolve_task_reference('mark it done',[row],'PMS')=='mark it done'
