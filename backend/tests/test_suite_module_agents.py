import json
from datetime import date
from uuid import uuid4
import pytest
from tests.test_suite_operator import setup_suite,prepare,approve,tick,ROOT
from tests.test_ai_operator import isolate_generic_http_audit,mock_provider
from app.ai_operator.models import OperatorApiLog,OperatorProvider


@pytest.mark.parametrize('module',['HRMS','CRM','SRM','FAM'])
def test_module_memory_is_approved_persistent_scoped_and_forgettable(client,db,monkeypatch,module):
    h,_,_,_=setup_suite(client,db)
    tool=module.lower()+'.remember'
    run=prepare(client,h,[{'tool':tool,'payload':{'text':f'{module} reviews happen on Fridays','category':'decision'}}],module=module)
    assert run['status']=='awaiting_approval',run
    assert client.get(ROOT+'/memories',headers=h,params={'module':module}).json()['items']==[]
    approve(client,h,run)
    tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded',final
    row=client.get(ROOT+'/memories',headers=h,params={'module':module}).json()['items'][0]
    calls=mock_provider(monkeypatch,{'summary':'Reviews are on Fridays.','steps':[]})
    reply=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'module':module,'text':'When should we review work?'})
    assert reply.status_code==200 and reply.json()['status']=='answered',reply.text
    body=json.loads(calls[0].content)
    assert f'{module} reviews happen on Fridays' in json.dumps(body)
    log=db.query(OperatorApiLog).filter_by(suite_run_id=reply.json()['id']).one()
    assert log.provider=='gemini' and module in log.module and log.input_tokens>0
    other='CRM' if module!='CRM' else 'FAM'
    assert client.get(ROOT+'/memories',headers=h,params={'module':other}).json()['items']==[]
    assert client.delete(ROOT+f'/memories/{row["id"]}',headers=h).status_code==200
    assert client.get(ROOT+'/memories',headers=h,params={'module':module}).json()['items']==[]
    assert {p.provider for p in db.query(OperatorProvider)}=={'gemini'}


def test_followup_preserves_module_and_refetches_selected_record(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    task=client.post('/api/v1/crm/tasks',headers=h,json={'title':'First title'}).json()
    context=[{'tool':'crm.task','record_id':task['id'],'payload':{}}]
    parent=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'module':'CRM','text':'Change this task priority',
        'context':context,'local_plan':{'summary':'I need a priority','question':'Which priority?','steps':[]}}).json()
    assert parent['status']=='needs_clarification',parent
    client.patch(f'/api/v1/crm/tasks/{task["id"]}',headers=h,json={'title':'Fresh title'})
    calls=mock_provider(monkeypatch,{'summary':'Raise priority','steps':[{'tool':'crm.update_task','record_id':task['id'],'payload':{'priority':'High'}}]})
    child=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'parent_run_id':parent['id'],'text':'High please'}).json()
    assert child['status']=='awaiting_approval',child
    assert child['result']['request']['context']==context
    assert child['result']['request']['module']=='CRM'
    assert b'Fresh title' in calls[0].content and b'Which priority?' in calls[0].content
    assert client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'parent_run_id':parent['id'],'module':'FAM','text':'High please'}).status_code==409
    approve(client,h,child);tick(client,db)
    assert client.get(f'/api/v1/crm/tasks/{task["id"]}',headers=h).json()['priority']=='High'


def test_four_module_actions_use_canonical_apis_and_keep_drafts(client,db):
    from app.models.employee import Employee
    from app.models.helpdesk import HelpdeskTicket
    from app.apps.srm.models import SRMInvoice
    from app.apps.crm.models import CRMNote
    h,user,_,_=setup_suite(client,db)
    db.add(Employee(employee_id='AGENT-QA',user_id=user.id,first_name='Agent',last_name='QA',date_of_joining=date(2026,1,1)))
    db.commit();db.expire_all()
    customer=client.post('/api/v1/crm/companies',headers=h,json={'name':'Agent QA customer'}).json()['id']
    run=prepare(client,h,[
        {'tool':'hrms.create_ticket','payload':{'subject':'Review onboarding','description':'Check onboarding checklist','priority':'Medium'}},
        {'tool':'crm.add_note','payload':{'company_id':customer,'body':'Internal review note'}},
        {'tool':'srm.draft_invoice','payload':{'customer_id':customer,'currency':'INR','lines':[{'description':'QA service','quantity':1,'unit_price':1}]}},
        {'tool':'fam.create_cost_center','payload':{'code':'AGENT-QA','name':'Agent delivery'}}])
    assert run['status']=='awaiting_approval',run
    assert db.query(HelpdeskTicket).count()==0 and db.query(SRMInvoice).count()==0
    approve(client,h,run);tick(client,db)
    final=client.get(ROOT+f'/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded' and len(final['receipts'])==4,final
    assert db.query(HelpdeskTicket).one().employee_id==user.employee.id
    assert db.query(SRMInvoice).one().status.lower()=='draft'
    assert db.query(CRMNote).one().is_internal


def test_private_memory_is_not_other_users_history(client,db):
    from ai_test_utils import auth_headers
    h,_,_,_=setup_suite(client,db)
    row=client.post(ROOT+'/memories',headers=h,json={'module':'CRM','text':'Private review preference'}).json()
    assert row.get('id'),row
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant','crm_view'])
    assert client.get(ROOT+'/memories',headers=other,params={'module':'CRM'}).json()['items']==[]
    assert client.delete(ROOT+f'/memories/{row["id"]}',headers=other).status_code==404
    conversations=client.get('/api/v1/ai-operator/assistant/conversations',headers=h)
    if conversations.status_code==200:assert row['id'] not in [r['id'] for r in conversations.json()]


def test_external_crm_note_is_rejected(client,db):
    h,_,_,_=setup_suite(client,db)
    run=prepare(client,h,[{'tool':'crm.add_note','payload':{'company_id':1,'body':'Unsafe external note','is_internal':False}}])
    assert run['status']=='failed',run


def test_memory_isolated_between_workspaces(client,db):
    h,_,_,_=setup_suite(client,db)
    first=client.post('/api/v1/project-management/workspaces',headers=h,json={'name':'First agent workspace'}).json()['id']
    second=client.post('/api/v1/project-management/workspaces',headers=h,json={'name':'Second agent workspace'}).json()['id']
    created=client.post(ROOT+'/memories',headers=h,json={'module':'SRM','workspace_id':first,'text':'First workspace preference'})
    assert created.status_code==200,created.text
    assert len(client.get(ROOT+'/memories',headers=h,params={'module':'SRM','workspace_id':first}).json()['items'])==1
    assert client.get(ROOT+'/memories',headers=h,params={'module':'SRM','workspace_id':second}).json()['items']==[]
    assert client.get(ROOT+'/memories',headers=h,params={'module':'SRM'}).json()['items']==[]


def test_usage_attributes_context_and_action_modules(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    mock_provider(monkeypatch,{'summary':'Prepare a finance review task','steps':[{'tool':'crm.create_task','payload':{'title':'Review finance'}}]})
    run=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'text':'Create a review task from this finance context',
        'context':[{'tool':'fam.cost_centers'}]}).json()
    assert run['status']=='awaiting_approval',run
    assert db.query(OperatorApiLog).filter_by(suite_run_id=run['id']).one().module=='CRM+FAM'
