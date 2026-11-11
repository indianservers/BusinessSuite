import asyncio
from uuid import uuid4
from datetime import timedelta
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,approve,tick
from tests.test_saved_agents import profile
from ai_test_utils import auth_headers
from app.ai_operator.agent_workflows import dispatch,now
from app.ai_operator.suite_models import SuiteRun
from app.apps.crm.models import CRMTask

ROOT='/api/v1/ai-operator/suite/agents/workflows'
SUITE='/api/v1/ai-operator/suite'


def make(client,db):
    h,user,_,_=setup_suite(client,db)
    first=profile(client,h);second=profile(client,h,tools=['crm.task','crm.update_task'])
    spec={'request_key':str(uuid4()),'name':'Reviewed agent handoff','nodes':[
        {'agent_id':first['id'],'instructions':'Create CRM task called Coordinated delivery review'},
        {'agent_id':second['id'],'instructions':'Set CRM task #{{step.1.record_id}} priority to high','depends_on':[1]}]}
    r=client.post(ROOT+'/preview',headers=h,json=spec);assert r.status_code==200,r.text
    return h,user,first,second,spec,r.json()


def start(client,h,flow):
    r=client.post(ROOT+f'/{flow["id"]}/start',headers=h,json={'preview_hash':flow['preview_hash']});assert r.status_code==200,r.text


def state(client,h,flow):
    r=client.get(ROOT+f'/{flow["id"]}',headers=h);assert r.status_code==200,r.text
    return r.json()


def process(client,db,seconds=0):return asyncio.run(dispatch(db,client.app,instant=now()+timedelta(seconds=seconds)))


def test_two_agents_handoff_receipt_and_review_each_change(client,db):
    h,_,_,_,spec,flow=make(client,db)
    assert client.post(ROOT+'/preview',headers=h,json=spec).json()['id']==flow['id']
    assert process(client,db)['processed']==0 and db.query(SuiteRun).count()==1
    start(client,h,flow);assert process(client,db)['processed']==1
    current=state(client,h,flow);first=current['nodes'][0]
    assert first['run_status']=='awaiting_approval' and not current['nodes'][1].get('run_id')
    assert db.query(CRMTask).count()==0
    assert process(client,db)['processed']==0
    run=client.get(SUITE+f'/runs/{first["run_id"]}',headers=h).json();approve(client,h,run);tick(client,db)
    assert process(client,db,11)['processed']==1
    current=state(client,h,flow);second=current['nodes'][1]
    run=client.get(SUITE+f'/runs/{second["run_id"]}',headers=h).json()
    assert run['status']=='awaiting_approval',run
    assert run['plan']['steps'][0]['record_id']==db.query(CRMTask).one().id
    assert db.query(CRMTask).one().priority!='High'
    approve(client,h,run);tick(client,db);process(client,db)
    assert state(client,h,flow)['status']=='succeeded'
    assert db.query(CRMTask).count()==1 and db.query(CRMTask).one().priority=='High'


def test_workflow_scope_and_revision_are_pinned(client,db):
    h,_,agent,_,_,flow=make(client,db)
    other,_=auth_headers(client,db,email=f'{uuid4()}@example.com',permissions=['ai_assistant'])
    assert client.get(ROOT+f'/{flow["id"]}',headers=other).status_code==404
    assert client.post(ROOT+f'/{flow["id"]}/start',headers=h,json={'preview_hash':'0'*64}).status_code==409
    start(client,h,flow)
    body={k:agent[k] for k in ('name','instructions','modules','tools','memory','workspace_id','project_id','provider','skill_ids','connection_ids','environment','mcp_ids')};body.update(revision=1,instructions='Changed scope')
    assert client.put(SUITE+f'/agents/{agent["id"]}',headers=h,json=body).status_code==200
    process(client,db);assert state(client,h,flow)['status']=='blocked'
    assert db.query(SuiteRun).count()==1


@pytest.mark.parametrize('node',[{'agent_id':1,'instructions':'Do work','depends_on':[1]},
    {'agent_id':1,'instructions':'Use {{step.2.record_id}}'},
    {'agent_id':1,'instructions':'Use {{arbitrary.secret}}'}])
def test_workflow_rejects_cycles_and_unbound_variables(client,db,node):
    h,_,_,_=setup_suite(client,db)
    r=client.post(ROOT+'/preview',headers=h,json={'request_key':str(uuid4()),'name':'Invalid graph','nodes':[node]})
    assert r.status_code==422,r.text


def test_stop_cancels_unapproved_children_and_prevents_successors(client,db):
    h,_,_,_,_,flow=make(client,db);start(client,h,flow);process(client,db)
    first=state(client,h,flow)['nodes'][0]['run_id']
    r=client.post(ROOT+f'/{flow["id"]}/stop',headers=h);assert r.status_code==200,r.text
    assert r.json()['cancel_errors']==[]
    assert client.get(SUITE+f'/runs/{first}',headers=h).json()['status']=='cancelled'
    assert process(client,db,600)['processed']==0 and db.query(CRMTask).count()==0


def test_three_specialists_prepare_crm_pms_hrms_in_order(client,db):
    from datetime import date
    from app.models.employee import Employee
    from app.models.helpdesk import HelpdeskTicket
    h,user,project,_=setup_suite(client,db)
    db.add(Employee(employee_id='FLOW-'+str(user.id),user_id=user.id,first_name='Workflow',last_name='QA',date_of_joining=date.today()));db.commit()
    crm=profile(client,h)
    pms=profile(client,h,modules=['PMS'],tools=['pms.create_task'],project_id=project)
    hr=profile(client,h,modules=['HRMS'],tools=['hrms.create_ticket'])
    r=client.post(ROOT+'/preview',headers=h,json={'request_key':str(uuid4()),'name':'CRM PMS HRMS coordination','nodes':[
        {'agent_id':crm['id'],'instructions':'Create CRM task called Customer recovery'},
        {'agent_id':pms['id'],'instructions':f'Create PMS task called Delivery recovery in project #{project}','depends_on':[1]},
        {'agent_id':hr['id'],'instructions':'Create HR ticket called Staffing support','depends_on':[2]}]})
    assert r.status_code==200,r.text
    flow=r.json();start(client,h,flow)
    for index,tool in enumerate(['crm.create_task','pms.create_task','hrms.create_ticket']):
        assert process(client,db)['processed']==1
        current=state(client,h,flow);node=current['nodes'][index]
        assert not any(n.get('run_id') for n in current['nodes'][index+1:])
        run=client.get(SUITE+f'/runs/{node["run_id"]}',headers=h).json()
        assert run['status']=='awaiting_approval',(run['status'],run.get('plan'))
        assert [s['tool'] for s in run['plan']['steps']]==[tool]
        approve(client,h,run);tick(client,db)
    process(client,db)
    assert state(client,h,flow)['status']=='succeeded'
    assert db.query(CRMTask).count()==1 and db.query(HelpdeskTicket).count()==1


def test_workflow_retry_uses_canonical_planning_recovery_and_is_idempotent(client,db,monkeypatch):
    import httpx
    from app.ai_operator import providers
    from tests.test_ai_operator import mock_provider
    h,_,_,_=setup_suite(client,db);agent=profile(client,h,provider='gemini')
    r=client.post(ROOT+'/preview',headers=h,json={'request_key':str(uuid4()),'name':'Recover provider planning','nodes':[{'agent_id':agent['id'],'instructions':'Create CRM task called Recovered coordination'}]})
    flow=r.json();start(client,h,flow)
    real_client=httpx.Client;monkeypatch.setattr(providers.time,'sleep',lambda _:None)
    mock_provider(monkeypatch,{},status=503);process(client,db);process(client,db)
    assert state(client,h,flow)['status']=='paused'
    monkeypatch.setattr(providers.httpx,'Client',real_client)
    mock_provider(monkeypatch,{'summary':'Recovered agent draft','steps':[{'tool':'crm.create_task','payload':{'title':'Recovered coordination'}}]})
    body={'request_key':str(uuid4())};url=ROOT+f'/{flow["id"]}/steps/1/retry-planning'
    r=client.post(url,headers=h,json=body);assert r.status_code==200,r.text
    child=r.json()['nodes'][0]['run_id']
    assert client.post(url,headers=h,json=body).json()['nodes'][0]['run_id']==child
    assert client.get(SUITE+f'/runs/{child}',headers=h).json()['status']=='awaiting_approval'
    assert db.query(CRMTask).count()==0


def test_independent_agents_prepare_before_either_action_is_approved(client,db):
    h,_,_,_=setup_suite(client,db);first=profile(client,h);second=profile(client,h)
    r=client.post(ROOT+'/preview',headers=h,json={'request_key':str(uuid4()),'name':'Independent specialist work','nodes':[
        {'agent_id':first['id'],'instructions':'Create CRM task called First independent draft'},
        {'agent_id':second['id'],'instructions':'Create CRM task called Second independent draft'}]})
    flow=r.json();start(client,h,flow)
    assert process(client,db)['processed']==1
    assert process(client,db)['processed']==1
    nodes=state(client,h,flow)['nodes'];assert all(n.get('run_id') for n in nodes)
    assert all(client.get(SUITE+f'/runs/{n["run_id"]}',headers=h).json()['status']=='awaiting_approval' for n in nodes)
    assert db.query(CRMTask).count()==0


def test_recovery_after_child_planning_reuses_canonical_request(client,db):
    h,_,_,_,_,flow=make(client,db);start(client,h,flow);process(client,db)
    original=state(client,h,flow)['nodes'][0]['run_id']
    run=db.get(SuiteRun,flow['id']);nodes=[dict(n) for n in run.result['nodes']]
    nodes[0].pop('run_id');nodes[0]['state']='planning';run.result={**run.result,'nodes':nodes}
    run.status='workflow_running';run.lease_until=now()-timedelta(seconds=1);db.commit()
    assert process(client,db)['processed']==1
    assert state(client,h,flow)['nodes'][0]['run_id']==original
    assert db.query(SuiteRun).count()==2 and db.query(CRMTask).count()==0
