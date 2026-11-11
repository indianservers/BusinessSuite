import asyncio,json
import pytest
from uuid import uuid4
from fastapi import HTTPException
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite
from tests.test_saved_agents import profile
from tests.test_agent_workflows import start,process,state,isolate_fixture_planning_sessions
from app.ai_operator.suite_models import SuiteRun
from app.apps.crm.models import CRMTask

ROOT='/api/v1/ai-operator/suite/agents/workflows'
SUITE='/api/v1/ai-operator/suite'


def independent(client,db,count=2):
    h,_,_,_=setup_suite(client,db);agent=profile(client,h)
    r=client.post(ROOT+'/preview',headers=h,json={'request_key':str(uuid4()),'name':'Bounded concurrent planning','parallel_limit':2,
        'nodes':[{'agent_id':agent['id'],'instructions':f'Create CRM task called Independent draft {i}'} for i in range(count)]})
    assert r.status_code==200,r.text
    return h,r.json()


def test_ready_planning_calls_overlap_and_respect_concurrency_limit(client,db,monkeypatch):
    from app.ai_operator import agent_workflows as flows
    h,flow=independent(client,db,4);start(client,h,flow);real=flows.prepare_agent
    async def scenario():
        barrier=asyncio.Event();active=0;peak=0
        async def prepare(*args,**kwargs):
            nonlocal active,peak
            active+=1;peak=max(peak,active)
            if active==2:barrier.set()
            try:
                await asyncio.wait_for(barrier.wait(),3)
                return await real(*args,**kwargs)
            finally:active-=1
        monkeypatch.setattr(flows,'prepare_agent',prepare)
        assert (await flows.dispatch(db,client.app))['processed']==1
        assert peak==2
    asyncio.run(scenario())
    nodes=state(client,h,flow)['nodes']
    assert all(n.get('run_id') for n in nodes[:2]) and not any(n.get('run_id') for n in nodes[2:])
    assert state(client,h,flow)['status']=='active' and db.query(CRMTask).count()==0


def test_partial_wave_keeps_success_and_recovers_lost_response_without_duplication(client,db,monkeypatch):
    from app.ai_operator import agent_workflows as flows
    h,flow=independent(client,db);start(client,h,flow);real=flows.prepare_agent;lost=[]
    async def prepare(*args,**kwargs):
        result=await real(*args,**kwargs)
        if args[-1]['workflow_step']==1 and not lost:
            lost.append(result['id']);raise HTTPException(503,'Synthetic response loss')
        return result
    monkeypatch.setattr(flows,'prepare_agent',prepare)
    assert process(client,db)['processed']==1
    current=state(client,h,flow);assert current['status']=='blocked'
    assert not current['nodes'][0].get('run_id') and current['nodes'][1].get('run_id')
    assert client.post(ROOT+f'/{flow["id"]}/resume',headers=h).status_code==200
    assert process(client,db)['processed']==1
    current=state(client,h,flow);assert current['nodes'][0]['run_id']==lost[0]
    assert db.query(SuiteRun).count()==3 and db.query(CRMTask).count()==0


def test_cancellation_after_parallel_plans_cancels_every_late_result(client,db,monkeypatch):
    from app.ai_operator import agent_workflows as flows
    h,flow=independent(client,db);start(client,h,flow);real=flows.prepare_agent
    async def scenario():
        complete=asyncio.Event();prepared=[]
        async def prepare(*args,**kwargs):
            result=await real(*args,**kwargs);prepared.append(result)
            if len(prepared)==2:
                parent=db.get(SuiteRun,flow['id']);parent.status='workflow_cancelled';parent.lease_until=None;db.commit();complete.set()
            await asyncio.wait_for(complete.wait(),5)
            return result
        monkeypatch.setattr(flows,'prepare_agent',prepare)
        await flows.dispatch(db,client.app)
    asyncio.run(scenario())
    current=state(client,h,flow)
    assert current['status']=='cancelled' and not current['cancel_errors']
    assert all(n['run_status']=='cancelled' for n in current['nodes'])
    assert all(client.get(SUITE+f'/runs/{n["run_id"]}',headers=h).json()['status']=='cancelled' for n in current['nodes'])
    assert db.query(CRMTask).count()==0


def test_stop_recovers_unrecorded_child_id_before_cancelling(client,db):
    h,flow=independent(client,db,1);start(client,h,flow);process(client,db)
    parent=db.get(SuiteRun,flow['id']);nodes=[dict(n) for n in parent.result['nodes']];child=nodes[0].pop('run_id')
    nodes[0]['state']='planning';parent.result={**parent.result,'nodes':nodes};db.commit()
    r=client.post(ROOT+f'/{flow["id"]}/stop',headers=h);assert r.status_code==200,r.text
    assert r.json()['nodes'][0]['run_id']==child and r.json()['cancel_errors']==[]
    assert client.get(SUITE+f'/runs/{child}',headers=h).json()['status']=='cancelled'


def reports(client,db,provider='local'):
    h,_,_,_=setup_suite(client,db)
    crm=profile(client,h,name='Customer reviewer',tools=['crm.tasks'])
    pms=profile(client,h,name='Project reviewer',modules=['PMS'],tools=['pms.projects'])
    report=profile(client,h,name='Report writer',modules=['HRMS'],tools=['hrms.directory'],provider=provider)
    r=client.post(ROOT+'/preview',headers=h,json={'request_key':str(uuid4()),'name':'Cross-module dependency analysis','nodes':[
        {'agent_id':crm['id'],'instructions':'Show CRM tasks'},{'agent_id':pms['id'],'instructions':'List PMS projects'},
        {'agent_id':report['id'],'instructions':'Summarize previous findings','depends_on':[1,2]}]})
    assert r.status_code==200,r.text
    return h,r.json()


def test_local_reporter_uses_completed_cross_module_answers_with_citations(client,db):
    h,flow=reports(client,db);start(client,h,flow)
    assert process(client,db)['processed']==1
    first=state(client,h,flow);assert not first['nodes'][2].get('run_id')
    assert process(client,db)['processed']==1
    current=state(client,h,flow);third=current['nodes'][2]
    result=client.get(SUITE+f'/runs/{third["run_id"]}',headers=h).json()
    assert result['status']=='answered',result
    assert len(result['result']['handoffs'])==2 and len(result['result']['citations'])==2
    assert {s['kind'] for s in result['result']['citations']}=={'agent_answer'}
    assert result['plan']['steps']==[] and result['receipts']==[]
    process(client,db);combined=client.get(ROOT+f'/{flow["id"]}/results',headers=h).json()
    assert combined['complete'] and len(combined['items'])==3


@pytest.mark.parametrize('invented',[False,True])
def test_provider_gets_server_dependency_context_and_checked_citations(client,db,monkeypatch,invented):
    from app.ai_operator import suite
    h,flow=reports(client,db,provider='gemini');calls=[]
    def generate(*a,**k):
        packet=json.loads(k['prompt']);calls.append(packet)
        assert len(packet['dependency_results'])==2
        source=packet['dependency_results'][0]['sources'][0]['id']
        assert source in {s['id'] for s in packet['evidence']}
        return {'summary':'The two specialist source reviews are available; coverage is bounded.','steps':[],'source_ids':['w999:step99:answer' if invented else source]}
    monkeypatch.setattr(suite,'generate_json',generate)
    start(client,h,flow);process(client,db);process(client,db)
    node=state(client,h,flow)['nodes'][2];result=client.get(SUITE+f'/runs/{node["run_id"]}',headers=h).json()
    assert result['status']==('failed' if invented else 'answered'),result
    assert len(calls)==1
    if not invented:assert result['result']['citations'][0]['kind']=='agent_answer'
    else:assert result['approval_id'] is None and '422' in result['error_code']
    assert result['result']['request']['workflow_step']==3


def test_client_cannot_attach_another_steps_handoff_context(client,db):
    h,flow=reports(client,db);start(client,h,flow);process(client,db)
    current=state(client,h,flow)
    r=client.post(SUITE+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','text':'Summarize previous findings',
        'workflow_id':flow['id'],'workflow_step':3,'conversation_id':current['nodes'][0]['conversation_id'],'agent_id':flow['spec']['nodes'][2]['agent_id']})
    assert r.status_code==403,r.text


def test_old_workflow_replay_keeps_serial_preparation(client,db):
    from app.ai_agents.security import seal
    from app.ai_operator.service import digest
    from app.models.user import User
    h,flow=independent(client,db)
    run=db.get(SuiteRun,flow['id']);spec={k:v for k,v in run.result['spec'].items() if k!='parallel_limit'}
    run.result={**run.result,'spec':spec}
    run.request_hash=digest({'spec':spec,'agents':run.result['agents'],'branch_id':run.snapshots['branch_id']})
    run.snapshots={**run.snapshots,'workflow_grant':seal(db,db.get(User,run.user_id),run.request_hash,session_id=run.session_id)};db.commit()
    key=run.request_key.removeprefix('agent-workflow:')
    r=client.post(ROOT+'/preview',headers=h,json={'request_key':key,**spec})
    assert r.status_code==200,r.text
    assert r.json()['id']==flow['id'] and 'parallel_limit' not in r.json()['spec']
    start(client,h,r.json());process(client,db)
    nodes=state(client,h,flow)['nodes'];assert nodes[0].get('run_id') and not nodes[1].get('run_id')


def test_stale_parallel_worker_does_not_overwrite_newer_lease(client,db,monkeypatch):
    from datetime import timedelta
    from app.ai_operator import agent_workflows as flows
    h,flow=independent(client,db,1);start(client,h,flow);real=flows.prepare_agent;new_lease=flows.now()+timedelta(hours=1)
    async def prepare(*args,**kwargs):
        result=await real(*args,**kwargs)
        run=db.get(SuiteRun,flow['id']);run.status='workflow_running';run.lease_until=new_lease;db.commit()
        return result
    monkeypatch.setattr(flows,'prepare_agent',prepare)
    assert process(client,db)['processed']==0
    db.expire_all();run=db.get(SuiteRun,flow['id'])
    assert run.status=='workflow_running' and flows.utc(run.lease_until)==flows.utc(new_lease)
    assert not run.result['nodes'][0].get('run_id') and run.error_code is None
