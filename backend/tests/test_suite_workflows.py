from uuid import uuid4
from datetime import date,timedelta
from fastapi import HTTPException
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite,prepare,approve,tick
from app.ai_operator.suite import now
from app.ai_operator.suite_models import SuiteRun
from app.apps.crm.models import CRMTask
from app.apps.project_management.models import PMSTask
from app.models.helpdesk import HelpdeskTicket
from app.models.employee import Employee

ROOT='/api/v1/ai-operator/suite'


def test_local_three_module_workflow_collects_project_and_executes_once(client,db):
    h,user,project,_=setup_suite(client,db)
    db.add(Employee(employee_id='WORKFLOW-HR',user_id=user.id,first_name='Workflow',last_name='QA',date_of_joining=date.today()))
    db.commit();db.expire_all()
    chat=client.post(ROOT+'/conversations',headers=h,json={'title':'Delivery workflow'}).json()['id']
    text='CRM: create task "Contact delivery customer" then PMS: create task "Recover delivery" then HRMS: create HR ticket "Delivery staffing support"'
    def send(text,**extra):
        r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'local','conversation_id':chat,'text':text,**extra})
        assert r.status_code==200,r.text
        assert r.json()['status']!='failed',r.text
        return r.json()
    first=send(text)
    assert first['status']=='needs_clarification',first
    assert 'project' in first['plan']['question'].lower()
    first=send('show projects',parent_run_id=first['id'])
    assert first['status']=='needs_clarification' and first['result']['workflow']['pending']==1,first
    run=send(f'project #{project}',parent_run_id=first['id'])
    assert run['status']=='awaiting_approval',run
    assert [s['tool'] for s in run['plan']['steps']]==['crm.create_task','pms.create_task','hrms.create_ticket']
    assert run['workflow_steps'][1]['depends_on']==[1]
    assert run['workflow_steps'][1]['status']=='blocked'
    assert db.query(CRMTask).count()==db.query(HelpdeskTicket).count()==0
    approve(client,h,run);assert tick(client,db)==3
    final=client.get(f'{ROOT}/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded',final
    assert all(s['status']=='succeeded' for s in final['workflow_steps'])
    assert db.query(CRMTask).count()==db.query(HelpdeskTicket).count()==1
    assert db.query(PMSTask).filter_by(title='Recover delivery').count()==1
    assert tick(client,db)==0


def test_explicit_dependencies_and_receipt_reference_validate_before_review(client,db):
    h,_,_,_=setup_suite(client,db)
    bad=prepare(client,h,[{'tool':'crm.create_task','payload':{'title':'Unsafe graph'},'depends_on':[2]}])
    assert bad['status']=='failed' and db.query(CRMTask).count()==0
    wrong_kind=prepare(client,h,[{'tool':'crm.create_task','payload':{'title':'Not a project'}},
        {'tool':'pms.create_task','record_id':{'$step':1,'field':'id'},'payload':{'title':'Wrong project reference','task_key':'WRONG-1'}}])
    assert wrong_kind['status']=='failed' and db.query(CRMTask).count()==0
    run=prepare(client,h,[{'tool':'crm.create_task','payload':{'title':'Linked task'}},
        {'tool':'crm.update_task','record_id':{'$step':1,'field':'id'},'payload':{'priority':'High'},'depends_on':[1]}])
    assert run['status']=='awaiting_approval',run
    approve(client,h,run);tick(client,db)
    assert db.query(CRMTask).one().priority=='High'
    final=client.get(f'{ROOT}/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded' and len(final['receipts'])==2


def test_paused_predispatch_resume_keeps_completed_receipts(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    run=prepare(client,h,[{'tool':'crm.create_task','payload':{'title':'First'}},
        {'tool':'crm.create_task','payload':{'title':'Second'},'depends_on':[1]}])
    approve(client,h,run)
    from app.ai_operator import suite
    original=suite.check_tool
    def stop(db,user,workspace,step,write=None):
        if step.payload.get('title')=='Second':raise HTTPException(409,'Temporary setup issue before dispatch')
        return original(db,user,workspace,step,write)
    monkeypatch.setattr(suite,'check_tool',stop)
    tick(client,db)
    paused=client.get(f'{ROOT}/runs/{run["id"]}',headers=h).json()
    assert paused['status']=='paused' and paused['can_resume'],paused
    assert len(paused['receipts'])==1 and db.query(CRMTask).count()==1
    monkeypatch.setattr(suite,'check_tool',original)
    assert client.post(f'{ROOT}/runs/{run["id"]}/resume',headers=h,json={'plan_hash':'0'*64}).status_code==409
    resumed=client.post(f'{ROOT}/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']})
    assert resumed.status_code==200,resumed.text
    tick(client,db)
    assert db.query(CRMTask).count()==2
    assert client.get(f'{ROOT}/runs/{run["id"]}',headers=h).json()['status']=='succeeded'


def test_transient_read_failure_retries_with_backoff_and_limit(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    task=CRMTask(title='Guarded',owner_user_id=1,organization_id=1)
    db.add(task);db.commit()
    run=prepare(client,h,[{'tool':'crm.update_task','record_id':task.id,'payload':{'priority':'High'}}])
    approve(client,h,run)
    from app.ai_operator import suite
    original=suite.api_call
    async def unavailable(*args,**kwargs):
        if args[2]=='GET':raise HTTPException(503,'Read unavailable')
        return await original(*args,**kwargs)
    monkeypatch.setattr(suite,'api_call',unavailable)
    for attempt in range(3):
        tick(client,db)
        row=db.get(SuiteRun,run['id']);db.refresh(row)
        assert row.result['checkpoint']['attempts']['1']==attempt+1
        if attempt<2:
            assert row.status=='queued'
            assert tick(client,db)==0
            row.result={**row.result,'checkpoint':{**row.result['checkpoint'],'retry_at':(now()-timedelta(seconds=1)).isoformat()}}
            db.commit()
    assert row.status=='paused'
    monkeypatch.setattr(suite,'api_call',original)
    assert client.post(f'{ROOT}/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']}).status_code==200
    tick(client,db)
    db.refresh(task);assert task.priority=='High'


def test_unknown_write_outcome_is_never_retried(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    run=prepare(client,h,[{'tool':'crm.create_task','payload':{'title':'Only once'}},
        {'tool':'crm.create_task','payload':{'title':'Dependent'},'depends_on':[1]}])
    approve(client,h,run)
    from app.ai_operator import suite
    original=suite.api_call
    async def lost_response(*args,**kwargs):
        result=await original(*args,**kwargs)
        if args[2]=='POST':raise TimeoutError('Lost response after committed write')
        return result
    monkeypatch.setattr(suite,'api_call',lost_response)
    tick(client,db)
    final=client.get(f'{ROOT}/runs/{run["id"]}',headers=h).json()
    assert final['status']=='needs_reconciliation' and not final['can_resume'],final
    assert db.query(CRMTask).count()==1
    assert tick(client,db)==0
    assert client.post(f'{ROOT}/runs/{run["id"]}/resume',headers=h,json={'plan_hash':run['plan_hash']}).status_code==409


def test_connected_planner_can_fetch_authorized_cross_module_sources(client,db,monkeypatch):
    import json
    h,_,_,_=setup_suite(client,db)
    prompts=[]
    def generate(*args,**kwargs):
        prompts.append(json.loads(kwargs['prompt']))
        if len(prompts)==1:return {'summary':'Check team directory before preparing the task','steps':[],
            'context_requests':[{'tool':'hrms.directory','payload':{'search':'Workflow'}}]}
        return {'summary':'Review recovery follow-up','steps':[{'tool':'crm.create_task','payload':{'title':'Verified recovery follow-up'}}]}
    monkeypatch.setattr('app.ai_operator.suite.generate_json',generate)
    r=client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','text':'Prepare a recovery follow-up after checking HRMS'})
    assert r.status_code==200,r.text
    assert r.json()['status']=='awaiting_approval',r.text
    assert len(prompts)==2
    assert any(v['tool']=='hrms.directory' for v in prompts[1]['authorized_context'])
    assert db.query(CRMTask).count()==0


def test_planner_cannot_execute_writes_as_reads_or_loop_forever(client,db,monkeypatch):
    h,_,_,_=setup_suite(client,db)
    responses=[{'summary':'Invalid read','steps':[],'context_requests':[{'tool':'crm.create_task','payload':{'title':'No write allowed'}}]}]
    monkeypatch.setattr('app.ai_operator.suite.generate_json',lambda *a,**kw:responses[0])
    def send():return client.post(ROOT+'/commands',headers=h,json={'request_key':str(uuid4()),'provider':'gemini','text':'Check workflow sources'})
    invalid=send()
    assert invalid.status_code==200 and invalid.json()['status']=='failed'
    assert db.query(CRMTask).count()==0
    responses[0]={'summary':'Need more records','steps':[],'context_requests':[{'tool':'hrms.directory'}]}
    bounded=send()
    assert bounded.status_code==200 and bounded.json()['status']=='failed'
    assert db.query(CRMTask).count()==0


def test_suite_only_worker_advances_its_pms_child_without_schedulers(client,db,monkeypatch):
    from app.ai_operator.workflows import process_suite_children
    h,_,project,task=setup_suite(client,db)
    run=prepare(client,h,[{'tool':'crm.create_task','payload':{'title':'Prepare delivery'}},
        {'tool':'pms.task_plan','record_id':project,'depends_on':[1],'payload':{'plan':{'summary':'Recovery priority','steps':[
            {'tool':'update_task','task_id':task,'changes':{'priority':'High'}}]}}},
        {'tool':'crm.create_task','depends_on':[2],'payload':{'title':'Confirm recovery'}}],project_id=project)
    assert run['status']=='awaiting_approval',run
    def forbidden(*a,**kw):raise AssertionError('Unrelated scheduler must not run')
    monkeypatch.setattr('app.ai_operator.extensions.check_monitors',forbidden)
    monkeypatch.setattr('app.ai_operator.workbench.tick_rules',forbidden)
    approve(client,h,run);tick(client,db)
    assert client.get(f'{ROOT}/runs/{run["id"]}',headers=h).json()['status']=='waiting_pms'
    assert db.query(CRMTask).count()==1
    assert process_suite_children(db)
    tick(client,db)
    final=client.get(f'{ROOT}/runs/{run["id"]}',headers=h).json()
    assert final['status']=='succeeded',final
    db.expire_all();assert db.get(PMSTask,task).priority=='High'
    assert db.query(CRMTask).count()==2
